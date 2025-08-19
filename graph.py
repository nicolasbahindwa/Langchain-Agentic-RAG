


# from __future__ import annotations

# from typing import TypedDict, List, Optional, Dict, Any, Literal, Annotated, Tuple
# from datetime import datetime
# import hashlib

# import asyncio
# from langgraph.graph import StateGraph, END, add_messages
# from langgraph.cache.memory import InMemoryCache
# from langgraph.types import CachePolicy
# from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from langgraph.checkpoint.memory import MemorySaver

# from core.llm_manager import LLMManager, LLMProvider
# from core.search_manager import SearchManager
# from pipeline.vector_store import VectorStoreManager
# from utils.logger import get_enhanced_logger
# from sentence_transformers import CrossEncoder

# # ------------------------------------------------------------------
# # GLOBAL COMPONENTS
# # ------------------------------------------------------------------
# search_manager = SearchManager()
# llm_manager = LLMManager()

# vector_store = VectorStoreManager(
#     embedding_model='paraphrase-multilingual-MiniLM-L12-v2',
#     collection_name="document_knowledge_base",
#     persist_dir="./vector_storage"
# )

# llm = llm_manager.get_chat_model(
#     provider=LLMProvider.ANTHROPIC,
#     model="claude-3-haiku-20240307",
#     temperature=0.7,
#     max_tokens=1500
# )

# llm_light = llm_manager.get_chat_model(provider=LLMProvider.OLLAMA)

# logger = get_enhanced_logger("rag_graph")

# # ------------------------------------------------------------------
# # CONSTANTS
# # ------------------------------------------------------------------
# MAX_FEEDBACK_CYCLES = 3
# RETRIEVAL_COUNT = 10
# RERANK_COUNT = 5

# CONFIDENCE_THRESHOLDS = {
#     "HIGH_CONFIDENCE": 0.7,      # → Direct answer generation
#     "MEDIUM_CONFIDENCE": 0.5,    # → Partial answer with disclaimer  
#     "LOW_CONFIDENCE": 0.2        # → Human feedback loop
# }

# RETRIEVAL_STRATEGIES = ["hybrid", "keyword", "vector"]

# # ------------------------------------------------------------------
# # SIMPLE MESSAGE EXTRACTION - THE ONLY CHANGE
# # ------------------------------------------------------------------
# def get_latest_human_message(messages: List[BaseMessage]) -> Optional[str]:
#     """Get the latest human message. Simple and clean."""
#     if not messages:
#         return None
    
#     for message in reversed(messages):
#         if isinstance(message, HumanMessage) and message.content.strip():
#             return message.content.strip()
    
#     return None

# # ------------------------------------------------------------------
# # CACHE UTILITIES
# # ------------------------------------------------------------------
# def generate_cache_key(*args) -> str:
#     """Simple utility to generate consistent cache keys from any arguments."""
#     import json
    
#     def normalize(value):
#         if value is None:
#             return "null"
#         elif isinstance(value, str):
#             return value.strip()
#         elif isinstance(value, (int, float, bool)):
#             return str(value)
#         elif isinstance(value, (list, tuple)):
#             return json.dumps(sorted([normalize(v) for v in value]))
#         elif isinstance(value, dict):
#             return json.dumps({k: normalize(v) for k, v in sorted(value.items())})
#         else:
#             return str(value)
    
#     normalized_parts = [normalize(arg) for arg in args]
#     content = "|".join(normalized_parts)
#     return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]

# def question_cache_key(state: 'RAGState') -> str:
#     return generate_cache_key("rewrite_question", state.get("question", ""), 
#                              state.get("feedback", ""), state.get("feedback_cycles", 0))

# def retrieval_cache_key(state: 'RAGState') -> str:
#     return generate_cache_key("retrieve_documents", state.get("question", ""))

# def ranking_cache_key(state: 'RAGState') -> str:
#     docs = state.get("documents", [])
#     doc_signature = f"{len(docs)}_{docs[0].get('page_content', '')[:100]}" if docs else ""
#     return generate_cache_key("rank_documents", state.get("question", ""), doc_signature)

# def evaluation_cache_key(state: 'RAGState') -> str:
#     ranked_docs = state.get("ranked_documents", [])
#     content_signature = f"{len(ranked_docs)}_{ranked_docs[0].get('page_content', '')[:150]}" if ranked_docs else ""
#     return generate_cache_key("evaluate_content", state.get("question", ""), content_signature)

# # ------------------------------------------------------------------
# # STATE WITH CONFIDENCE SCORING
# # ------------------------------------------------------------------
# class RAGState(TypedDict):
#     # Core conversation history
#     messages: Annotated[List[BaseMessage], add_messages]
#     # User question and language
#     question: str
#     original_question: str
#     question_language: str
#     # Retrieved & ranked documents
#     documents: List[dict]
#     ranked_documents: List[dict]
#     # Final answer
#     answer: Optional[str]
#     # Feedback loop bookkeeping
#     feedback: Optional[str]
#     feedback_cycles: int
#     # Error handling
#     status: str
#     error: Optional[str]
#     # Source list shown to user
#     sources: List[str]
#     # Simple loading message shown on the UI
#     loading_message: str
#     # Evaluation results with confidence
#     evaluation_result: Optional[str]
#     confidence_score: float
#     # Retrieval strategy tracking
#     retrieval_strategy_used: str
#     retrieval_attempts: int

# # ------------------------------------------------------------------
# # ENHANCED UTILITIES
# # ------------------------------------------------------------------
# async def detect_question_language(question: str) -> str:
#     """Use LLM to detect the language of the question for consistent responses"""
#     try:
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", """Detect the language of the question and respond with ONLY the language name in English.
            
#             Examples:
#             - "What is AI?" → English
#             - "Qu'est-ce que l'IA?" → French 
#             - "¿Qué es la IA?" → Spanish
#             - "Was ist KI?" → German
#             - "什么是人工智能？" → Chinese
#             - "Che cos'è l'IA?" → Italian
#             - "O que é IA?" → Portuguese
#             - "AI とは何ですか？" → Japanese
#             - "AI란 무엇인가요?" → Korean
#             - "Что такое ИИ?" → Russian
#             - "AI کیا ہے؟" → Urdu
#             - "ما هو الذكاء الاصطناعي؟" → Arabic
            
#             Only respond with the language name in English. Nothing else."""),
#             ("human", "Detect the language of this question: {question}")
#         ])
#         formatted = prompt.format_messages(question=question)
#         response = await llm.ainvoke(formatted)
        
#         detected_language = response.content.strip()
#         logger.info(f"Detected language: {detected_language}")
#         return detected_language
        
#     except Exception as e:
#         logger.warning(f"Language detection failed: {e}")
#         return "English"  # Default fallback

# def fallback_retrieval(query: str, strategy: str) -> Tuple[List[dict], List[float]]:
#     """Implement fallback retrieval strategies with graceful degradation"""
#     try:
#         if strategy == "vector_hybrid":
#             docs, scores = vector_store.query_documents(
#                 query=query, k=RETRIEVAL_COUNT, rerank=False, search_type="hybrid"
#             )
#         elif strategy == "vector_similarity":
#             docs, scores = vector_store.query_documents(
#                 query=query, k=RETRIEVAL_COUNT, rerank=False, search_type="similarity"
#             )
#         elif strategy == "keyword":
#             # Fallback to keyword-based search if vector search fails
#             docs, scores = search_manager.keyword_search(query, k=RETRIEVAL_COUNT)
#         elif strategy == "query_expansion":
#             # Expand query and try vector search again
#             expanded_query = expand_query(query)
#             docs, scores = vector_store.query_documents(
#                 query=expanded_query, k=RETRIEVAL_COUNT, rerank=False, search_type="hybrid"
#             )
#         else:
#             docs, scores = [], []
            
#         return docs, scores
#     except Exception as e:
#         logger.failure(f"Retrieval strategy {strategy} failed: {e}")
#         return [], []

# def expand_query(query: str) -> str:
#     """Expand query using lightweight LLM for better retrieval"""
#     try:
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", "Expand this query with 2-3 related keywords or synonyms. Keep it concise. Return only the expanded query."),
#             ("human", "Query: {query}")
#         ])
#         formatted = prompt.format_messages(query=query)
#         response = llm.ainvoke(formatted)
#         return response.content.strip()
#     except:
#         return query  # Fallback to original query

# def batch_evaluate_documents(question: str, docs: List[dict], language: str) -> Tuple[str, float, str]:
#     """Batched evaluation combining relevance, completeness, and confidence in single call"""
#     if not docs:
#         return "INSUFFICIENT", 0.0, "No documents available"
    
#     try:
#         context = format_docs(docs)
#         language_instruction = f"Respond in {language}" if language != "English" else ""
        
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", f"""Evaluate documents for answering the question. {language_instruction}
            
#             Provide evaluation in this EXACT format:
#             CLASSIFICATION: [COMPLETE/PARTIAL/INSUFFICIENT]
#             CONFIDENCE: [0.0-1.0]
#             REASONING: [Brief explanation]
            
#             Classification rules:
#             - COMPLETE (0.8-1.0): Context fully answers the question with specific information
#             - PARTIAL (0.3-0.7): Context has some relevant information but incomplete  
#             - INSUFFICIENT (0.0-0.3): Context lacks relevant information or only general mentions
            
#             Be precise with confidence scoring.
#             IMPORTANT: Respond in the exact same language as the question: {language}"""),
#             ("human", "Question: {question}\n\nContext:\n{context}")
#         ])
        
#         formatted = prompt.format_messages(question=question, context=context)
#         response = llm.ainvoke(formatted)
        
#         # Parse structured response
#         lines = response.content.strip().split('\n')
#         classification = "INSUFFICIENT"
#         confidence = 0.0
#         reasoning = "Evaluation failed"
        
#         for line in lines:
#             if line.startswith("CLASSIFICATION:"):
#                 classification = line.split(":", 1)[1].strip()
#             elif line.startswith("CONFIDENCE:"):
#                 try:
#                     confidence = float(line.split(":", 1)[1].strip())
#                 except:
#                     confidence = 0.0
#             elif line.startswith("REASONING:"):
#                 reasoning = line.split(":", 1)[1].strip()
        
#         return classification, confidence, reasoning
        
#     except Exception as e:
#         logger.failure(f"Batch evaluation failed: {e}")
#         return "INSUFFICIENT", 0.0, f"Evaluation error: {e}"

# def set_loading_message(state: RAGState, text: str) -> RAGState:
#     """Update loading message and log"""
#     state["loading_message"] = text
#     logger.info(text)
#     return state

# def format_docs(docs: List[dict]) -> str:
#     """Format documents for internal prompts"""
#     if not docs:
#         return "No relevant documents found."

#     return "\n\n".join(
#         f"📄 Document {idx + 1} ({d['metadata'].get('source', 'Unknown')}):\n"
#         f"{d['page_content'][:300]}{'...' if len(d['page_content']) > 300 else ''}"
#         for idx, d in enumerate(docs)
#     )

# def reset_state_for_next_question(state: RAGState) -> None:
#     """Reset state for next question while preserving messages - COMPREHENSIVE RESET"""
#     state["question"] = ""
#     state["original_question"] = ""
#     state["question_language"] = "English"  # Reset to default
#     state["documents"] = []
#     state["ranked_documents"] = []
#     state["feedback"] = None
#     state["feedback_cycles"] = 0
#     state["sources"] = []
#     state["error"] = None
#     state["evaluation_result"] = None
#     state["status"] = ""
#     state["loading_message"] = ""
#     state["confidence_score"] = 0.0
#     state["retrieval_strategy_used"] = ""
#     state["retrieval_attempts"] = 0
#     # Clear any waiting flags
#     state.pop("waiting_for_feedback", None)
#     logger.info("State reset for new question")

# # ------------------------------------------------------------------
# # NODES - UPDATED WITH SIMPLE MESSAGE EXTRACTION
# # ------------------------------------------------------------------
# async def rewrite_question(state: RAGState) -> RAGState:
#     """Entry point - get last human message and optimize it"""
#     # Set defaults
#     defaults = {
#         "messages": [], "question": "", "original_question": "", "question_language": "English",
#         "documents": [], "ranked_documents": [], "answer": None, "feedback": None,
#         "feedback_cycles": 0, "status": "", "error": None, "sources": [],
#         "loading_message": "", "evaluation_result": None, "confidence_score": 0.0,
#         "retrieval_strategy_used": "", "retrieval_attempts": 0
#     }
#     state = {**defaults, **state}
    
#     # SIMPLIFIED: Just get the last human message
#     current_input = get_latest_human_message(state["messages"])
    
#     if not current_input:
#         state["status"] = "error"
#         state["error"] = "No input provided"
#         return set_loading_message(state, "Error: no input detected.")
    
#     # Check if this is different from what we processed before
#     if state.get("original_question") and current_input != state["original_question"]:
#         logger.info(f"NEW INPUT detected: '{current_input[:50]}...'")
#         reset_state_for_next_question(state)
    
#     # Set the current input as our question
#     state["question"] = current_input
#     if not state.get("original_question"):
#         state["original_question"] = current_input
    
#     if state["feedback_cycles"] == 0:
#         set_loading_message(state, "Analyzing question and detecting language...")
#         # LLM-based language detection
#         detected_language = await detect_question_language(state["question"])
#         state["question_language"] = detected_language
#         logger.info(f"Detected language: {detected_language}")
#     else:
#         set_loading_message(state, f"Refining search based on feedback (cycle {state['feedback_cycles']})...")
                
#     # Optimize question for search
#     try:
#         # ENFORCE LANGUAGE: All responses must be in the detected language
#         if state["feedback_cycles"] == 0:
#             prompt = ChatPromptTemplate.from_messages([
#                 ("system", f"""Rewrite this question to make it clearer and more searchable.
                
#                 CRITICAL: You MUST respond in {state['question_language']}. Do not use any other language.
#                 Return ONLY the rewritten question in {state['question_language']}."""),
#                 ("human", "Question to rewrite: {question}")
#             ])
#             formatted = prompt.format_messages(question=state["question"])
#         else:
#             prompt = ChatPromptTemplate.from_messages([
#                 ("system", f"""Incorporate the feedback to create a better search query.
                
#                 CRITICAL: You MUST respond in {state['question_language']}. Do not use any other language.
#                 Return ONLY the rewritten question in {state['question_language']}."""),
#                 ("human", """Original question: {original}
# Current version: {current}
# User feedback: {feedback}

# Create a new search query incorporating this feedback:""")
#             ])
#             formatted = prompt.format_messages(
#                 original=state["original_question"],
#                 current=state["question"],
#                 feedback=state["feedback"]
#             )

#         response = await llm.ainvoke(formatted)
#         rewritten = response.content.strip()
#         state["question"] = rewritten
#         state["status"] = "check_existing_documents"
        
#         set_loading_message(state, f"Optimized question → {rewritten}")
#         return state
        
#     except Exception as e:
#         logger.failure(f"Question rewriting failed: {e}")
#         # Graceful degradation: use original question
#         state["status"] = "check_existing_documents"
#         return set_loading_message(state, "Using original question for search...")

# async def check_existing_documents(state: RAGState) -> RAGState:
#     """Smart check if existing documents can answer the current question - PRECISE CHECKING"""
#     set_loading_message(state, "Checking existing documents...")
    
#     # If no existing documents, need to retrieve
#     if not state.get("ranked_documents") and not state.get("documents"):
#         state["status"] = "retrieve_documents"
#         return set_loading_message(state, "No existing documents - retrieving new content...")
    
#     # For NEW questions (feedback_cycles == 0), be more conservative about reusing docs
#     # For FEEDBACK iterations, be more liberal about reusing docs
#     is_new_question = state.get("feedback_cycles", 0) == 0
    
#     # Use ranked docs if available, otherwise use raw documents
#     docs_to_check = state.get("ranked_documents") or state.get("documents", [])[:RERANK_COUNT]
    
#     if not docs_to_check:
#         state["status"] = "retrieve_documents"
#         return set_loading_message(state, "No documents to check - retrieving...")
    
#     try:
#         # For new questions, check if documents are topically relevant first
#         if is_new_question:
#             # Quick topical relevance check for new questions
#             sample_content = " ".join([doc.get("page_content", "")[:200] for doc in docs_to_check[:3]])
            
#             relevance_prompt = ChatPromptTemplate.from_messages([
#                 ("system", f"""Are the documents topically relevant to the question?
                
#                 CRITICAL: You MUST respond in {state['question_language']}. Do not use any other language.
#                 Answer only 'RELEVANT' or 'NOT_RELEVANT' in {state['question_language']}."""),
#                 ("human", "Question: {question}\n\nDocument content sample:\n{content}")
#             ])
#             formatted = relevance_prompt.format_messages(question=state["question"], content=sample_content)
#             response = await llm.ainvoke(formatted)
            
#             if "NOT_RELEVANT" in response.content.upper() or "PAS PERTINENT" in response.content.upper() or "NO RELEVANTE" in response.content.upper():
#                 state["status"] = "retrieve_documents"
#                 return set_loading_message(state, "Existing documents not topically relevant - retrieving fresh content...")
        
#         # Now check if documents can provide meaningful information for the question
#         context = format_docs(docs_to_check)
        
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", f"""Evaluate if the context contains meaningful information to answer the question.
            
#             CRITICAL: You MUST respond in {state['question_language']}. Do not use any other language.
            
#             Be PRECISE:
#             - Answer 'YES' only if context contains specific information that can help answer the question (fully or partially)
#             - Answer 'NO' if context only mentions general topics without specific relevant information
            
#             IMPORTANT: General mentions of topics without specific details should be 'NO'.
#             Respond with YES or NO in {state['question_language']}."""),
#             ("human", "Question: {question}\n\nContext:\n{context}")
#         ])
#         formatted = prompt.format_messages(question=state["question"], context=context)
#         response = llm.ainvoke(formatted)
#         result = response.content.strip().upper()
        
#         if "YES" in result:
#             # Existing documents sufficient - proceed to evaluation
#             state["status"] = "evaluate_content"
#             return set_loading_message(state, "Existing documents contain relevant information - proceeding to evaluation...")
#         else:
#             # Need fresh retrieval
#             state["status"] = "retrieve_documents"
#             return set_loading_message(state, "Existing documents lack specific information - retrieving new content...")
            
#     except Exception as e:
#         logger.failure(f"Check existing documents failed: {e}")
#         state["status"] = "retrieve_documents"
#         return set_loading_message(state, "Check failed - retrieving new documents")

# async def retrieve_documents(state: RAGState) -> RAGState:
#     """Retrieve documents from vector store"""
#     set_loading_message(state, "Searching knowledge base...")
#     try:
#         docs, scores = vector_store.query_documents(
#             query=state["question"],
#             k=RETRIEVAL_COUNT,
#             rerank=False,
#             search_type="hybrid"
#         )
#         state["documents"] = [
#             {"page_content": d.page_content, "metadata": d.metadata, "score": s}
#             for d, s in zip(docs, scores)
#         ]
#         state["status"] = "rank_documents"
#         set_loading_message(state, f"Retrieved {len(state['documents'])} documents")
#         return state
#     except Exception as e:
#         logger.failure(f"Retrieve failed: {e}")
#         state["status"] = "error"
#         state["error"] = f"Retrieval error: {e}"
#         return set_loading_message(state, "Error while retrieving documents.")

# def rank_documents(state: RAGState) -> RAGState:
#     """Re-rank documents by relevance"""
#     set_loading_message(state, "Ranking results by relevance...")
#     if not state["documents"]:
#         state["status"] = "evaluate_content"
#         return set_loading_message(state, "No documents to rank")

#     try:
#         reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
#         pairs = [(state["question"], d["page_content"]) for d in state["documents"]]
#         scores = reranker.predict(pairs)
        
#         ranked = sorted(zip(state["documents"], scores), key=lambda x: x[1], reverse=True)
#         state["ranked_documents"] = [doc for doc, _ in ranked[:RERANK_COUNT]]

#         # Build unique source list
#         seen = set()
#         sources = []
#         for d in state["ranked_documents"]:
#             path = d["metadata"].get("source", "Unknown")
#             if path not in seen:
#                 seen.add(path)
#                 sources.append({
#                     "path": path,
#                     "file_name": d["metadata"].get("File Name", "Unknown file"),
#                     "author": d["metadata"].get("Author", "Unknown"),
#                     "creation_date": d["metadata"].get("Creationdate", "Unknown")
#                 })
#         state["sources"] = sources
#         state["status"] = "evaluate_content"
#         set_loading_message(state, f"Top {len(state['ranked_documents'])} documents selected")
#         return state
#     except Exception as e:
#         logger.failure(f"Rank failed: {e}")
#         state["status"] = "error"
#         state["error"] = f"Ranking error: {e}"
#         return set_loading_message(state, "Error while ranking documents.")

# async def evaluate_content(state: RAGState) -> RAGState:
#     """Evaluate if content can answer the question - PRECISE LOGIC"""
#     set_loading_message(state, "Evaluating content quality...")
#     if not state["ranked_documents"]:
#         state["status"] = "request_feedback"
#         return set_loading_message(state, "No content found - requesting feedback")

#     try:
#         context = format_docs(state["ranked_documents"])
        
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", f"""Evaluate if the context contains relevant information to answer the question.
            
#             CRITICAL: You MUST respond in {state['question_language']}. Do not use any other language.
            
#             Be PRECISE in your evaluation:
            
#             - 'COMPLETE' if context fully answers the question with specific information
#             - 'PARTIAL' if context contains some relevant information that partially addresses the question (can give meaningful partial answer)
#             - 'INSUFFICIENT' if context contains no relevant information or only mentions topics without answering the specific question
            
#             IMPORTANT: If the context talks about general topics but doesn't contain the specific information asked for, classify as 'INSUFFICIENT', not 'PARTIAL'.
            
#             Then explain what specific information was found and what's missing.
            
#             Remember: Respond entirely in {state['question_language']}."""),
#             ("human", "Question: {question}\n\nContext:\n{context}")
#         ])
#         formatted = prompt.format_messages(question=state["question"], context=context)
#         response = await llm.ainvoke(formatted)
#         evaluation = response.content.strip()
        
#         state["evaluation_result"] = evaluation
        
#         # PRECISE ROUTING: Only truly relevant content goes to answer generation
#         if evaluation.startswith("COMPLETE"):
#             state["status"] = "generate_answer"
#             return set_loading_message(state, "Content fully answers question - generating response...")
#         elif evaluation.startswith("PARTIAL"):
#             # Double-check: is there actually meaningful content to work with?
#             state["status"] = "generate_answer"
#             return set_loading_message(state, "Partial answer found - generating response with suggestions...")
#         else:
#             # INSUFFICIENT - go to human feedback
#             state["status"] = "request_feedback"
#             return set_loading_message(state, "No relevant content found - requesting guidance...")
            
#     except Exception as e:
#         logger.failure(f"Evaluate failed: {e}")
#         state["status"] = "request_feedback"
#         return set_loading_message(state, "Evaluation failed - requesting feedback")

# async def request_feedback(state: RAGState) -> RAGState:
#     """Request user feedback for insufficient content - PRECISE FEEDBACK REQUESTS"""
#     set_loading_message(state, "Preparing feedback request...")

#     # Get evaluation details
#     evaluation = state.get("evaluation_result", "No evaluation available")
#     found_content = format_docs(state["ranked_documents"]) if state["ranked_documents"] else "No documents found"
    
#     language_instruction = f"Respond in {state['question_language']}" if state['question_language'] != "English" else ""
    
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", f"""The search did not find sufficient information to answer the user's question. {language_instruction}
        
#         Based on what was found, help the user by:
#         1. Briefly explaining what information was found (if any)
#         2. Asking for more specific keywords, different phrasing, or clarification
#         3. Suggesting what additional details might help improve the search
        
#         Be helpful and constructive - guide them toward a better search strategy."""),
#         ("human", """Question: {question}
        
#         Search evaluation: {evaluation}
        
#         Content found: {content}
        
#         Help the user refine their search.""")
#     ])
    
#     formatted = prompt.format_messages(
#         question=state["question"],
#         evaluation=evaluation,
#         content=found_content[:500] + "..." if len(found_content) > 500 else found_content
#     )
#     response = await llm.ainvoke(formatted)
#     feedback_request = response.content

#     # Add to conversation
#     state["messages"].append(AIMessage(content=feedback_request))
#     state["waiting_for_feedback"] = True
#     state["feedback"] = None
    
#     return state

# def process_feedback(state: RAGState) -> RAGState:
#     """Process user feedback - SIMPLIFIED WITH LAST HUMAN MESSAGE"""
#     set_loading_message(state, "Processing your feedback...")
    
#     # SIMPLIFIED: Just get the last human message as feedback
#     feedback = get_latest_human_message(state["messages"])
    
#     if not feedback:
#         state["status"] = "generate_answer"
#         state["waiting_for_feedback"] = False
#         return set_loading_message(state, "No feedback found - proceeding with available content")

#     # Process commands
#     lower_feedback = feedback.lower().strip()
    
#     # Stop commands
#     if lower_feedback in {"stop", "abort", "cancel", "quit", "end", "exit"}:
#         state["status"] = "end"
#         state["waiting_for_feedback"] = False
#         return set_loading_message(state, "Request cancelled")
    
#     # Proceed commands
#     if lower_feedback in {"proceed", "continue", "yes", "go", "ok", "okay", "fine"}:
#         state["status"] = "generate_answer"
#         state["waiting_for_feedback"] = False
#         return set_loading_message(state, "Proceeding with current content...")
    
#     # Check max cycles
#     if state.get("feedback_cycles", 0) >= MAX_FEEDBACK_CYCLES:
#         state["status"] = "generate_answer"
#         state["waiting_for_feedback"] = False
#         return set_loading_message(state, "Max feedback cycles reached - generating answer")
    
#     # Real feedback - increment cycle and rewrite question
#     state["feedback_cycles"] = state.get("feedback_cycles", 0) + 1
#     state["status"] = "rewrite_question"
#     state["waiting_for_feedback"] = False
#     state["feedback"] = feedback
    
#     return set_loading_message(state, f"Incorporating feedback (cycle {state['feedback_cycles']})...")

# async def generate_answer(state: RAGState) -> RAGState:
#     """Generate final answer with confidence-based approach and enhanced source citations"""
#     set_loading_message(state, "Generating answer...")
    
#     if not state["ranked_documents"]:
#         # Graceful degradation: should not happen with new flow, but handle it
#         state["status"] = "request_feedback"
#         return set_loading_message(state, "No documents available - requesting guidance...")

#     try:
#         # Prepare enhanced context with source details
#         context_parts = []
#         source_details = []
        
#         for idx, doc in enumerate(state["ranked_documents"], 1):
#             metadata = doc["metadata"]
#             file_name = metadata.get("File Name", metadata.get("file_name", "Unknown file"))
#             source_path = metadata.get("source", "Unknown source")
#             author = metadata.get("Author", metadata.get("author", ""))
#             creation_date = metadata.get("Creationdate", metadata.get("creation_date", ""))
            
#             source_ref = f"Source {idx}: {file_name}"
#             if author:
#                 source_ref += f" (Author: {author})"
#             if creation_date:
#                 source_ref += f" (Created: {creation_date})"
            
#             source_details.append({
#                 "index": idx,
#                 "file_name": file_name,
#                 "full_reference": source_ref,
#                 "path": source_path
#             })
            
#             context_parts.append(f"{source_ref}\nContent: {doc['page_content']}")

#         context = "\n\n".join(context_parts)
        
#         # Confidence-based answer generation
#         confidence = state.get("confidence_score", 0.0)
#         classification = state.get("evaluation_result", "PARTIAL")
#         language = state.get("question_language", "English")
#         language_instruction = f"Answer in {language}" if language != "English" else ""
        
#         if confidence >= CONFIDENCE_THRESHOLDS["HIGH_CONFIDENCE"]:
#             # High confidence - comprehensive answer
#             system_prompt = f"""Provide a comprehensive answer using the available context. {language_instruction}
            
#             Guidelines:
#             1. Answer the question thoroughly based on the context
#             2. Cite specific document names when referencing information
#             3. Be detailed and specific
#             4. Use authoritative tone since confidence is high
#             5. IMPORTANT: Respond in the exact same language as the original question: {language}"""
            
#         elif confidence >= CONFIDENCE_THRESHOLDS["MEDIUM_CONFIDENCE"]:
#             # Medium confidence - partial answer with clear limitations
#             system_prompt = f"""Provide a helpful partial answer based on available context. {language_instruction}
            
#             Guidelines:
#             1. Answer what you CAN based on the context
#             2. Cite specific document names when referencing information
#             3. At the end, clearly state: "This is a partial answer based on available documents"
#             4. Suggest asking more specific questions about areas that need clarification
#             5. Be helpful but acknowledge limitations
#             6. IMPORTANT: Respond in the exact same language as the original question: {language}"""
            
#         else:
#             # Low confidence - minimal answer with strong disclaimers
#             system_prompt = f"""Provide what limited information is available from the context. {language_instruction}
            
#             Guidelines:
#             1. Share only what specific information is clearly available
#             2. Cite document names for any information provided
#             3. Clearly state: "Based on available documents, I can only provide limited information"
#             4. Strongly suggest the user provide more specific search terms or clarify their question
#             5. IMPORTANT: Respond in the exact same language as the original question: {language}"""
        
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", system_prompt),
#             ("human", "Question: {question}\n\nSources and content:\n{context}\n\nConfidence: {confidence:.2f}")
#         ])
        
#         formatted = prompt.format_messages(
#             question=state["question"], 
#             context=context,
#             confidence=confidence
#         )
#         response = await llm.ainvoke(formatted)
#         answer = response.content.strip()
        
#         # Enhanced sources section
#         sources_section = f"\n\n📋 **Sources Used** (Search confidence: {confidence:.2f}):\n"
#         for source in source_details:
#             sources_section += f"• {source['full_reference']}\n"
#             if source['path'] != "Unknown source":
#                 sources_section += f"  Path: {source['path']}\n"
        
#         # Add retrieval strategy info for debugging
#         if state.get("retrieval_strategy_used"):
#             sources_section += f"\n🔍 Search method: {state['retrieval_strategy_used']}"
#             if state.get("retrieval_attempts", 0) > 1:
#                 sources_section += f" (after {state['retrieval_attempts']} attempts)"
        
#         final_answer = answer + sources_section
#         state["answer"] = final_answer
#         state["status"] = "complete"
        
#         reset_state_for_next_question(state)
#         set_loading_message(state, "Answer ready")
#         return state
        
#     except Exception as e:
#         logger.failure(f"Answer generation failed: {e}")
#         # Graceful degradation
#         state["status"] = "request_feedback"
#         state["error"] = f"Generation error: {e}"
#         return set_loading_message(state, "Error generating answer - requesting guidance...")

# # ------------------------------------------------------------------
# # ROUTING FUNCTIONS
# # ------------------------------------------------------------------
# def route_after_check(state: RAGState) -> Literal["retrieve_documents", "evaluate_content"]:
#     """Route after checking existing documents"""
#     return "evaluate_content" if state["status"] == "evaluate_content" else "retrieve_documents"

# def route_after_evaluation(state: RAGState) -> Literal["generate_answer", "request_feedback"]:
#     """Route after content evaluation"""
#     return "generate_answer" if state["status"] == "generate_answer" else "request_feedback"

# def route_after_feedback(state: RAGState) -> Literal["rewrite_question", "generate_answer", "END"]:
#     """Route after processing feedback"""
#     status = state.get("status", "END")
#     if status == "rewrite_question":
#         return "rewrite_question"
#     elif status == "generate_answer":
#         return "generate_answer"
#     else:
#         return "END"

# # ------------------------------------------------------------------
# # GRAPH BUILDER
# # ------------------------------------------------------------------
# def build_rag_graph():
#     """Build the corrected RAG graph"""
#     workflow = StateGraph(RAGState)

#     # Cache settings
#     CACHE_TTLS = {
#         "rewrite_question": 3600,
#         "retrieve_documents": 1800,
#         "rank_documents": 900,
#         "evaluate_content": 600,
#     }

#     # Add nodes with caching for expensive operations
#     workflow.add_node(
#         "rewrite_question", 
#         rewrite_question,
#         cache_policy=CachePolicy(key_func=question_cache_key, ttl=CACHE_TTLS["rewrite_question"])
#     )
    
#     workflow.add_node("check_existing_documents", check_existing_documents)
    
#     workflow.add_node(
#         "retrieve_documents", 
#         retrieve_documents,
#         cache_policy=CachePolicy(key_func=retrieval_cache_key, ttl=CACHE_TTLS["retrieve_documents"])
#     )
    
#     workflow.add_node(
#         "rank_documents", 
#         rank_documents,
#         cache_policy=CachePolicy(key_func=ranking_cache_key, ttl=CACHE_TTLS["rank_documents"])
#     )
    
#     workflow.add_node(
#         "evaluate_content", 
#         evaluate_content,
#         cache_policy=CachePolicy(key_func=evaluation_cache_key, ttl=CACHE_TTLS["evaluate_content"])
#     )

#     # Interactive nodes (no caching)
#     workflow.add_node("request_feedback", request_feedback)
#     workflow.add_node("process_feedback", process_feedback)
#     workflow.add_node("generate_answer", generate_answer)

#     # Define flow
#     workflow.set_entry_point("rewrite_question")
    
#     # CORRECTED FLOW:
#     workflow.add_edge("rewrite_question", "check_existing_documents")
    
#     workflow.add_conditional_edges(
#         "check_existing_documents",
#         route_after_check,
#         {
#             "retrieve_documents": "retrieve_documents",
#             "evaluate_content": "evaluate_content"
#         }
#     )
    
#     workflow.add_edge("retrieve_documents", "rank_documents")
#     workflow.add_edge("rank_documents", "evaluate_content")
    
#     workflow.add_conditional_edges(
#         "evaluate_content",
#         route_after_evaluation,
#         {
#             "generate_answer": "generate_answer",
#             "request_feedback": "request_feedback"
#         }
#     )
    
#     workflow.add_edge("request_feedback", "process_feedback")
    
#     workflow.add_conditional_edges(
#         "process_feedback",
#         route_after_feedback,
#         {
#             "rewrite_question": "rewrite_question",
#             "generate_answer": "generate_answer",
#             "END": END
#         }
#     )
    
#     workflow.add_edge("generate_answer", END)

#     return workflow.compile(cache=InMemoryCache(), interrupt_after=["request_feedback"])

# # Initialize the graph
# app = build_rag_graph()

# def clear_cache():
#     """Clear cache by rebuilding the app"""
#     global app
#     app = build_rag_graph()
#     logger.info("Cache cleared")


from __future__ import annotations

from typing import TypedDict, List, Optional, Dict, Any, Literal, Annotated, Tuple
from datetime import datetime
import asyncio
import hashlib
import json

from langgraph.graph import StateGraph, END, add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.cache.memory import InMemoryCache
from langgraph.types import CachePolicy
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

# Import your existing components
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import SearchManager
from pipeline.vector_store import VectorStoreManager
from utils.logger import get_enhanced_logger

# Optional cross-encoder for reranking
try:
    from sentence_transformers import CrossEncoder
    HAS_CROSSENCODER = True
except ImportError:
    HAS_CROSSENCODER = False
    print("Warning: sentence_transformers not available, using fallback ranking")

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

MAX_FEEDBACK_CYCLES = 3
RETRIEVAL_COUNT = 12
RERANK_COUNT = 6

CONFIDENCE_THRESHOLDS = {
    "HIGH": 0.75,     # Direct comprehensive answer
    "MEDIUM": 0.45,   # Partial answer with disclaimers  
    "LOW": 0.25       # Limited info with strong disclaimers
}

# Cache TTL settings (in seconds)
CACHE_TTL = {
    "LANGUAGE_DETECTION": 3600,      # 1 hour
    "QUESTION_OPTIMIZATION": 1800,   # 30 minutes
    "DOCUMENT_RETRIEVAL": 7200,      # 2 hours
    "DOCUMENT_RANKING": 3600,        # 1 hour
    "CONTENT_EVALUATION": 1800,      # 30 minutes
    "ANSWER_GENERATION": 7200        # 2 hours
}

# =============================================================================
# CACHE KEY GENERATION FUNCTIONS
# =============================================================================

def generate_cache_key(*args) -> str:
    """Simple utility to generate consistent cache keys from any arguments."""
    
    def normalize(value):
        if value is None:
            return "null"
        elif isinstance(value, str):
            return value.strip().lower()
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, (list, tuple)):
            return json.dumps(sorted([normalize(v) for v in value]))
        elif isinstance(value, dict):
            return json.dumps({k: normalize(v) for k, v in sorted(value.items())})
        else:
            return str(value)
    
    normalized_parts = [normalize(arg) for arg in args]
    content = "|".join(normalized_parts)
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]

def language_detection_cache_key(state: 'RAGState') -> str:
    """Cache key for language detection."""
    current_question = get_current_question(state)
    return generate_cache_key("language_detection", current_question[:200])

def question_optimization_cache_key(state: 'RAGState') -> str:
    """Cache key for question optimization."""
    current_question = get_current_question(state)
    context = get_conversation_context(state)
    return generate_cache_key("optimize_question", current_question, 
                             context, state.get("feedback_cycles", 0))

def retrieval_cache_key(state: 'RAGState') -> str:
    """Cache key for document retrieval."""
    question = state.get("_optimized_question", get_current_question(state))
    return generate_cache_key("retrieve_documents", question)

def ranking_cache_key(state: 'RAGState') -> str:
    """Cache key for document ranking."""
    question = state.get("_optimized_question", get_current_question(state))
    docs = state.get("documents", [])
    # Create signature from document content (first 100 chars of each doc)
    doc_signature = "|".join([doc.get('page_content', '')[:100] for doc in docs[:5]])
    return generate_cache_key("rank_documents", question, doc_signature)

def evaluation_cache_key(state: 'RAGState') -> str:
    """Cache key for content evaluation."""
    question = get_current_question(state)
    ranked_docs = state.get("ranked_documents", [])
    # Create signature from ranked document content
    content_signature = "|".join([doc.get('page_content', '')[:150] for doc in ranked_docs[:3]])
    return generate_cache_key("evaluate_content", question, content_signature)

def answer_generation_cache_key(state: 'RAGState') -> str:
    """Cache key for answer generation."""
    question = get_current_question(state)
    confidence = state.get("confidence_score", 0.0)
    classification = state.get("content_classification", "")
    docs_signature = "|".join([doc.get('page_content', '')[:100] for doc in state.get("ranked_documents", [])[:3]])
    return generate_cache_key("generate_answer", question, confidence, classification, docs_signature)

# =============================================================================
# SIMPLIFIED STATE DEFINITION
# =============================================================================

class RAGState(TypedDict):
    # Core conversation - single source of truth
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Essential processing state
    language: str
    feedback_cycles: int
    
    # Retrieved content - core to RAG functionality
    documents: List[Dict[str, Any]]
    ranked_documents: List[Dict[str, Any]]
    
    # Evaluation results - needed for routing decisions
    confidence_score: float
    content_classification: str  # COMPLETE, PARTIAL, INSUFFICIENT
    
    # Control flow
    waiting_for_feedback: bool
    
    # Optional - for debugging/analytics
    error_message: Optional[str]

# =============================================================================
# COMPONENT INITIALIZATION
# =============================================================================

def initialize_components():
    """Initialize all components with error handling."""
    try:
        search_manager = SearchManager()
        llm_manager = LLMManager()
        
        vector_store = VectorStoreManager(
            embedding_model='paraphrase-multilingual-MiniLM-L12-v2',
            collection_name="document_knowledge_base",
            persist_dir="./vector_storage"
        )
        
        # Primary LLM for complex tasks
        llm = llm_manager.get_chat_model(
            provider=LLMProvider.ANTHROPIC,
            model="claude-3-haiku-20240307",
            temperature=0.7,
            max_tokens=1500
        )
        
        # Lightweight LLM for simple tasks
        try:
            llm_light = llm_manager.get_chat_model(provider=LLMProvider.OLLAMA)
        except Exception:
            llm_light = llm  # Fallback to main LLM
        
        logger = get_enhanced_logger("enhanced_rag_graph")
        
        return search_manager, llm_manager, vector_store, llm, llm_light, logger
        
    except Exception as e:
        print(f"Error initializing components: {e}")
        raise

# Initialize global components
search_manager, llm_manager, vector_store, llm, llm_light, logger = initialize_components()

# =============================================================================
# HELPER FUNCTIONS FOR MESSAGE PROCESSING
# =============================================================================

def get_current_question(state: RAGState) -> str:
    """Extract the latest human question from messages."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) and msg.content.strip():
            return msg.content.strip()
    return ""

def get_conversation_context(state: RAGState, max_exchanges: int = 2) -> str:
    """Get recent conversation context for optimization."""
    context_parts = []
    human_count = 0
    
    for msg in reversed(state["messages"][:-1]):  # Exclude latest
        if human_count >= max_exchanges:
            break
            
        if isinstance(msg, HumanMessage):
            human_count += 1
            context_parts.append(f"Previous Q: {msg.content[:100]}...")
        elif isinstance(msg, AIMessage) and human_count > 0:
            context_parts.append(f"Previous A: {msg.content[:100]}...")
    
    context_parts.reverse()
    return "\n".join(context_parts)

def is_new_question_session(state: RAGState) -> bool:
    """Detect if this is a new question vs continued conversation."""
    # If we have no documents and no feedback cycles, definitely new
    if not state.get("ranked_documents") and state["feedback_cycles"] == 0:
        return True
    
    # If we've been waiting for feedback, the next message is likely feedback
    if state.get("waiting_for_feedback"):
        return False
    
    # If we have existing documents but no feedback cycles, likely new question
    if state.get("ranked_documents") and state["feedback_cycles"] == 0:
        return True
        
    return False

def should_reset_for_new_question(state: RAGState) -> bool:
    """Determine if we should reset state for a new question."""
    return (is_new_question_session(state) and 
            not state.get("waiting_for_feedback") and
            get_current_question(state))

def reset_processing_state(state: RAGState) -> None:
    """Reset processing state while keeping messages and language."""
    state["feedback_cycles"] = 0
    state["documents"] = []
    state["ranked_documents"] = []
    state["confidence_score"] = 0.0
    state["content_classification"] = ""
    state["waiting_for_feedback"] = False
    state["error_message"] = None
    logger.info("Processing state reset for new question")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def calculate_content_metrics(question: str, docs: List[Dict]) -> Dict[str, float]:
    """Calculate quantitative content quality metrics."""
    if not docs:
        return {"keyword_overlap": 0.0, "content_length": 0, "doc_count": 0, 
                "avg_score": 0.0, "source_diversity": 0.0}
    
    question_words = set(question.lower().split())
    all_content = " ".join([d.get("page_content", "").lower() for d in docs])
    content_words = set(all_content.split())
    
    # Calculate metrics
    overlap = len(question_words.intersection(content_words))
    keyword_overlap = overlap / max(len(question_words), 1)
    
    sources = set([d.get("metadata", {}).get("source", "") for d in docs])
    source_diversity = len(sources) / len(docs)
    
    avg_score = sum([d.get("score", 0.0) for d in docs]) / len(docs)
    
    return {
        "keyword_overlap": keyword_overlap,
        "content_length": len(all_content),
        "doc_count": len(docs),
        "avg_score": avg_score,
        "source_diversity": source_diversity
    }

def combine_confidence_metrics(llm_confidence: float, metrics: Dict[str, float]) -> float:
    """Combine LLM confidence with quantitative metrics."""
    base_confidence = llm_confidence * 0.75
    
    # Metric bonuses
    bonus = 0.0
    if metrics.get("keyword_overlap", 0) > 0.3:
        bonus += 0.08
    if metrics.get("content_length", 0) > 800:
        bonus += 0.07
    if metrics.get("avg_score", 0) > 0.7:
        bonus += 0.10
    
    return min(1.0, base_confidence + bonus)

def format_sources_from_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Generate sources info from documents when needed."""
    sources = []
    seen_sources = set()
    
    for doc in docs:
        metadata = doc.get("metadata", {})
        source_path = metadata.get("source", "Unknown")
        
        if source_path not in seen_sources:
            seen_sources.add(source_path)
            sources.append({
                "file_name": metadata.get("File Name", metadata.get("file_name", "Unknown file")),
                "author": metadata.get("Author", metadata.get("author", "")),
                "path": source_path,
                "creation_date": metadata.get("Creationdate", metadata.get("creation_date", ""))
            })
    
    return sources

def should_use_light_model(task: str) -> bool:
    """Determine if we can use lighter model for simple tasks."""
    light_tasks = ["language_detection", "simple_classification", "relevance_check"]
    return task in light_tasks

# =============================================================================
# CACHEABLE GRAPH NODES
# =============================================================================

async def process_input(state: RAGState) -> RAGState:
    """Entry point - validate input and set up processing."""
    logger.info("=== PROCESSING INPUT ===")
    
    # Initialize defaults if missing
    defaults = {
        "messages": [], "feedback_cycles": 0, "confidence_score": 0.0,
        "documents": [], "ranked_documents": [], "waiting_for_feedback": False, 
        "language": "English", "content_classification": "", "error_message": None
    }
    for key, default_value in defaults.items():
        if key not in state:
            state[key] = default_value
    
    # Get current question
    current_question = get_current_question(state)
    if not current_question:
        state["error_message"] = "No question found in input"
        # Add error message to conversation
        error_msg = "I didn't receive a question. Please ask something I can help you with."
        state["messages"].append(AIMessage(content=error_msg))
        return state
    
    # Check if we should reset for new question
    if should_reset_for_new_question(state):
        logger.info(f"NEW QUESTION detected: {current_question[:50]}...")
        reset_processing_state(state)
    
    logger.info(f"Processing question: {current_question[:100]}...")
    return state

async def detect_language_and_optimize(state: RAGState) -> RAGState:
    """Detect language and optimize question for search. CACHED."""
    logger.info("=== LANGUAGE DETECTION & OPTIMIZATION ===")
    
    current_question = get_current_question(state)
    
    try:
        # Detect language (only for new questions)
        if state["feedback_cycles"] == 0:
            model = llm_light if should_use_light_model("language_detection") else llm
            
            language_prompt = ChatPromptTemplate.from_messages([
                ("system", """Detect the language and respond with ONLY the language name in English.
                Examples: "What is AI?" → English | "¿Qué es IA?" → Spanish | "Qu'est-ce que l'IA?" → French"""),
                ("human", "Question: {question}")
            ])
            
            response = await model.ainvoke(language_prompt.format_messages(question=current_question))
            state["language"] = response.content.strip()
            logger.info(f"Detected language: {state['language']}")
        
        # Optimize question for search
        if state["feedback_cycles"] == 0:
            system_msg = f"""Rewrite this question to be more searchable and clear.
            CRITICAL: Respond in {state['language']} only. Return just the rewritten question."""
            user_msg = f"Question: {current_question}"
        else:
            # We're processing feedback - use it to improve the search
            system_msg = f"""Incorporate this feedback to create a better search query.
            CRITICAL: Respond in {state['language']} only. Return just the improved question."""
            user_msg = f"""Question: {current_question}
            Context: {get_conversation_context(state)}"""
        
        optimize_prompt = ChatPromptTemplate.from_messages([("system", system_msg), ("human", user_msg)])
        response = await llm.ainvoke(optimize_prompt.format_messages())
        
        optimized_question = response.content.strip()
        logger.info(f"Optimized question: {optimized_question}")
        
        # Store optimized question in state for this processing cycle
        state["_optimized_question"] = optimized_question
        
        return state
        
    except Exception as e:
        logger.failure(f"Language/optimization failed: {e}")
        # Continue with original question
        state["_optimized_question"] = current_question
        return state

async def retrieve_documents(state: RAGState) -> RAGState:
    """Retrieve documents using multiple strategies. CACHED."""
    logger.info("=== DOCUMENT RETRIEVAL ===")
    
    # Use optimized question if available, fallback to current question
    search_query = state.get("_optimized_question", get_current_question(state))
    
    # Try multiple retrieval strategies using vector_store.query_documents
    strategies = ["hybrid", "vector", "keyword"]
    
    for strategy in strategies:
        try:
            logger.info(f"Trying retrieval strategy: {strategy}")
            
            # Use vector_store.query_documents for all strategies
            docs, scores = vector_store.query_documents(
                query=search_query, 
                k=RETRIEVAL_COUNT, 
                rerank=False, 
                search_type=strategy  # This handles "hybrid", "vector", or "keyword"
            )
            
            if docs:
                # Store retrieved documents
                state["documents"] = [
                    {"page_content": d.page_content, "metadata": d.metadata, "score": s}
                    for d, s in zip(docs, scores)
                ]
                
                logger.info(f"Retrieved {len(docs)} documents using {strategy}")
                return state
                
        except Exception as e:
            logger.warning(f"Strategy {strategy} failed: {e}")
            continue
    
    # All strategies failed
    state["error_message"] = "Document retrieval failed"
    logger.failure("All retrieval strategies failed")
    return state

async def rank_documents(state: RAGState) -> RAGState:
    """Rank and reorder documents by relevance. CACHED."""
    logger.info("=== DOCUMENT RANKING ===")
    
    if not state.get("documents"):
        logger.warning("No documents to rank")
        return state
    
    search_query = state.get("_optimized_question", get_current_question(state))
    
    try:
        if HAS_CROSSENCODER and len(state["documents"]) > 1:
            # Re-rank using cross-encoder
            reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            pairs = [(search_query, doc["page_content"]) for doc in state["documents"]]
            relevance_scores = reranker.predict(pairs)
            
            # Sort by relevance and take top results
            ranked_docs_with_scores = sorted(
                zip(state["documents"], relevance_scores), 
                key=lambda x: x[1], reverse=True
            )
            
            state["ranked_documents"] = [doc for doc, _ in ranked_docs_with_scores[:RERANK_COUNT]]
            logger.info(f"Re-ranked {len(state['ranked_documents'])} documents using cross-encoder")
        else:
            # Fallback: use original scores
            sorted_docs = sorted(state["documents"], key=lambda x: x.get("score", 0), reverse=True)
            state["ranked_documents"] = sorted_docs[:RERANK_COUNT]
            logger.info(f"Ranked {len(state['ranked_documents'])} documents using original scores")
        
        return state
        
    except Exception as e:
        logger.warning(f"Ranking failed, using original order: {e}")
        state["ranked_documents"] = state["documents"][:RERANK_COUNT]
        return state

async def evaluate_content_quality(state: RAGState) -> RAGState:
    """Evaluate content quality and calculate confidence score. CACHED."""
    logger.info("=== CONTENT EVALUATION ===")
    
    current_question = get_current_question(state)
    
    if not state["ranked_documents"]:
        state["content_classification"] = "INSUFFICIENT"
        state["confidence_score"] = 0.0
        logger.info("No documents available for evaluation")
        return state
    
    try:
        # Calculate quantitative metrics
        metrics = calculate_content_metrics(current_question, state["ranked_documents"])
        
        # LLM evaluation
        context = "\n\n".join([
            f"Doc {i+1}: {doc['page_content'][:400]}..."
            for i, doc in enumerate(state["ranked_documents"])
        ])
        
        eval_prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Evaluate if context can answer the question. Respond in {state['language']}.
            
            Format your response EXACTLY as:
            CLASSIFICATION: [COMPLETE/PARTIAL/INSUFFICIENT]
            CONFIDENCE: [0.0-1.0]
            REASONING: [Brief explanation in {state['language']}]
            
            Rules:
            - COMPLETE (0.7-1.0): Context fully answers with specific information
            - PARTIAL (0.3-0.7): Some relevant info but incomplete  
            - INSUFFICIENT (0.0-0.3): No relevant specific information"""),
            ("human", "Question: {question}\n\nContext:\n{context}")
        ])
        
        response = await llm.ainvoke(eval_prompt.format_messages(
            question=current_question, context=context
        ))
        
        # Parse structured response
        content = response.content.strip()
        classification = "INSUFFICIENT"
        llm_confidence = 0.0
        
        for line in content.split('\n'):
            if line.startswith("CLASSIFICATION:"):
                classification = line.split(":", 1)[1].strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    llm_confidence = float(line.split(":", 1)[1].strip())
                except Exception:
                    llm_confidence = 0.0
        
        # Combine with quantitative metrics
        final_confidence = combine_confidence_metrics(llm_confidence, metrics)
        
        state["content_classification"] = classification
        state["confidence_score"] = final_confidence
        
        logger.info(f"Evaluation: {classification}, confidence: {final_confidence:.2f}")
        return state
        
    except Exception as e:
        logger.failure(f"Content evaluation failed: {e}")
        state["content_classification"] = "INSUFFICIENT"
        state["confidence_score"] = 0.0
        return state

async def request_user_feedback(state: RAGState) -> RAGState:
    """Request user feedback when content is insufficient."""
    logger.info("=== REQUESTING FEEDBACK ===")
    
    current_question = get_current_question(state)
    
    # Prepare feedback request based on what was found
    if state["ranked_documents"]:
        found_info = f"Found {len(state['ranked_documents'])} documents, but they don't contain specific information to answer your question."
    else:
        found_info = "No relevant documents found in the knowledge base."
    
    feedback_prompt = ChatPromptTemplate.from_messages([
        ("system", f"""The search didn't find sufficient information. Help the user by:
        1. Briefly explaining what was found
        2. Asking for more specific details, keywords, or different phrasing
        3. Suggesting how to improve the search
        
        Be helpful and constructive. Respond in {state['language']}."""),
        ("human", """Question: {question}
        
        Search results: {found_info}
        
        Help the user refine their search.""")
    ])
    
    try:
        response = await llm.ainvoke(feedback_prompt.format_messages(
            question=current_question, found_info=found_info
        ))
        
        feedback_message = response.content.strip()
        
        # Add feedback request to conversation
        state["messages"].append(AIMessage(content=feedback_message))
        state["waiting_for_feedback"] = True
        
        logger.info("Feedback requested from user")
        return state
        
    except Exception as e:
        logger.failure(f"Feedback request failed: {e}")
        # Fallback: generate answer with what we have
        return state

async def process_user_feedback(state: RAGState) -> RAGState:
    """Process user feedback and determine next action."""
    logger.info("=== PROCESSING FEEDBACK ===")
    
    if not state.get("waiting_for_feedback"):
        # Check if this is a new question
        if should_reset_for_new_question(state):
            logger.info("New question detected, not feedback")
            return state
        else:
            # No feedback expected, continue to answer
            return state
    
    # Extract feedback (should be the latest human message)
    feedback = get_current_question(state)
    
    if not feedback:
        state["waiting_for_feedback"] = False
        return state
    
    # Process feedback commands
    feedback_lower = feedback.lower().strip()
    
    # Stop/proceed commands
    stop_commands = {"stop", "abort", "cancel", "quit", "end", "exit", "no"}
    proceed_commands = {"proceed", "continue", "yes", "go", "ok", "okay", "fine"}
    
    if feedback_lower in stop_commands or feedback_lower in proceed_commands:
        state["waiting_for_feedback"] = False
        logger.info(f"User chose to {feedback_lower}")
        return state
    
    # Check max feedback cycles
    if state["feedback_cycles"] >= MAX_FEEDBACK_CYCLES:
        state["waiting_for_feedback"] = False
        logger.info("Max feedback cycles reached")
        return state
    
    # Real feedback - iterate
    state["feedback_cycles"] += 1
    state["waiting_for_feedback"] = False
    
    logger.info(f"Processing feedback cycle {state['feedback_cycles']}: {feedback[:50]}...")
    return state

async def generate_final_answer(state: RAGState) -> RAGState:
    """Generate a detailed, Markdown-formatted final answer. CACHED."""
    logger.info("=== GENERATING ANSWER ===")

    current_question = get_current_question(state)

    if not state["ranked_documents"]:
        # No content available
        no_content_msg = f"""# ❌ No Information Found

I couldn't find relevant information in the knowledge base to answer your question:
> **"{current_question}"**

### Suggestions:
- Rephrase your question with different keywords.
- Be more specific about what you're looking for.
- Check if the information might be in the knowledge base under different terms.
"""
        # Translate if needed
        if state["language"] != "English":
            try:
                translate_prompt = ChatPromptTemplate.from_messages([
                    ("system", f"Translate this message to {state['language']}:"),
                    ("human", no_content_msg)
                ])
                response = await llm.ainvoke(translate_prompt.format_messages())
                no_content_msg = response.content.strip()
            except:
                pass  # Use English fallback

        state["messages"].append(AIMessage(content=no_content_msg))
        reset_processing_state(state)
        return state

    try:
        # Prepare context with source information
        context_parts = []
        for i, doc in enumerate(state["ranked_documents"], 1):
            metadata = doc["metadata"]
            source_name = metadata.get("File Name", metadata.get("file_name", f"Source {i}"))
            context_parts.append(f"[Source {i}: {source_name}]\n{doc['page_content']}")

        context = "\n\n".join(context_parts)
        confidence = state["confidence_score"]

        # Choose answer style based on confidence
        if confidence >= CONFIDENCE_THRESHOLDS["HIGH"]:
            system_msg = f"""Provide a **comprehensive, Markdown-formatted answer** using the context.
            Guidelines:
            - Answer thoroughly with clear explanations.
            - Include **real-life examples** if applicable.
            - Use bullet points, bold/italics, and headings for readability.
            - Reference sources by name when citing information.
            - Respond in {state['language']} only.
            - Format your answer in Markdown.
            """
        elif confidence >= CONFIDENCE_THRESHOLDS["MEDIUM"]:
            system_msg = f"""Provide a **helpful, Markdown-formatted partial answer** based on available context.
            Guidelines:
            - Answer what you CAN with clear explanations.
            - Include **real-life examples** if applicable.
            - Use bullet points, bold/italics, and headings for readability.
            - Reference sources by name when citing information.
            - End with: "This is a partial answer based on available documents."
            - Suggest asking more specific questions for areas needing clarification.
            - Respond in {state['language']} only.
            - Format your answer in Markdown.
            """
        else:
            system_msg = f"""Provide a **limited, Markdown-formatted answer** based on available context.
            Guidelines:
            - Share only clearly available specific information.
            - Reference sources for any information provided.
            - Start with: "Based on available documents, I can provide limited information."
            - Strongly suggest providing more specific search terms.
            - Respond in {state['language']} only.
            - Format your answer in Markdown.
            """

        # Add instruction to include real-life examples
        system_msg += "\n\nIf applicable, include a **real-life example** to illustrate the concept."

        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", f"""Question: {current_question}

Context with sources:
{context}

---
**Instructions:**
- Format your answer in **Markdown**.
- Use headings, bullet points, and bold/italics for clarity.
- Include a real-life example if possible.
""")
        ])

        response = await llm.ainvoke(answer_prompt.format_messages(
            question=current_question, context=context
        ))

        base_answer = response.content.strip()

        # Add sources section in Markdown
        sources = format_sources_from_docs(state["ranked_documents"])
        sources_section = "\n\n## 📚 Sources\n"
        sources_section += f"Confidence: **{confidence:.1%}**\n\n"
        for source in sources:
            sources_section += f"- **{source['file_name']}**"
            if source.get('author'):
                sources_section += f" (Author: {source['author']})"
            sources_section += "\n"

        final_answer = f"{base_answer}\n{sources_section}"

        # Append the Markdown-formatted answer
        state["messages"].append(AIMessage(content=final_answer))

        # Reset for next question
        reset_processing_state(state)

        logger.info(f"Answer generated with confidence {confidence:.2f}")
        return state

    except Exception as e:
        logger.failure(f"Answer generation failed: {e}")
        error_msg = """# ⚠️ Error Generating Answer

I encountered an error while generating the answer.
Please try rephrasing your question or ask something else.
"""
        state["messages"].append(AIMessage(content=error_msg))
        return state

# =============================================================================
# ROUTING FUNCTIONS
# =============================================================================

def should_retrieve_documents(state: RAGState) -> bool:
    """Determine if we need to retrieve documents."""
    # Always retrieve for new questions or after feedback
    if (state["feedback_cycles"] == 0 and not state.get("ranked_documents")) or state["feedback_cycles"] > 0:
        return True
    
    # Check if existing documents are relevant (simplified check)
    return len(state.get("ranked_documents", [])) < 3

def should_generate_answer(state: RAGState) -> bool:
    """Determine if we should generate an answer."""
    # Generate if we have good content or max feedback cycles reached
    if state["feedback_cycles"] >= MAX_FEEDBACK_CYCLES:
        return True
    
    if state["content_classification"] in ["COMPLETE", "PARTIAL"] and state["confidence_score"] >= CONFIDENCE_THRESHOLDS["LOW"]:
        return True
    
    return False

def route_after_evaluation(state: RAGState) -> Literal["generate_final_answer", "request_user_feedback"]:
    """Route after content evaluation."""
    if should_generate_answer(state):
        return "generate_final_answer"
    else:
        return "request_user_feedback"

def route_after_feedback(state: RAGState) -> Literal["process_input", "detect_language_and_optimize", "generate_final_answer"]:
    """Route after processing feedback."""
    if not state["waiting_for_feedback"]:
        if should_reset_for_new_question(state):
            return "process_input"
        elif state["feedback_cycles"] > 0:
            return "detect_language_and_optimize"  # Retry with feedback
        else:
            return "generate_final_answer"
    else:
        return "generate_final_answer"  # Shouldn't happen, but safety net

# =============================================================================
# GRAPH CONSTRUCTION WITH CACHING
# =============================================================================

def create_enhanced_rag_graph():
    """Create the enhanced RAG graph with node-level caching."""
    workflow = StateGraph(RAGState)
    
    # Add nodes with cache policies for expensive operations
    workflow.add_node("process_input", process_input)
    
    # Cache language detection and optimization
    workflow.add_node(
        "detect_language_and_optimize", 
        detect_language_and_optimize,
        cache_policy=CachePolicy(
            key_func=question_optimization_cache_key,
            ttl=CACHE_TTL["QUESTION_OPTIMIZATION"]
        )
    )
    
    # Cache document retrieval (most expensive operation)
    workflow.add_node(
        "retrieve_documents", 
        retrieve_documents,
        cache_policy=CachePolicy(
            key_func=retrieval_cache_key,
            ttl=CACHE_TTL["DOCUMENT_RETRIEVAL"]
        )
    )
    
    # Cache document ranking
    workflow.add_node(
        "rank_documents", 
        rank_documents,
        cache_policy=CachePolicy(
            key_func=ranking_cache_key,
            ttl=CACHE_TTL["DOCUMENT_RANKING"]
        )
    )
    
    # Cache content evaluation
    workflow.add_node(
        "evaluate_content_quality", 
        evaluate_content_quality,
        cache_policy=CachePolicy(
            key_func=evaluation_cache_key,
            ttl=CACHE_TTL["CONTENT_EVALUATION"]
        )
    )
    
    # No cache for feedback (interactive)
    workflow.add_node("request_user_feedback", request_user_feedback)
    workflow.add_node("process_user_feedback", process_user_feedback)
    
    # Cache answer generation
    workflow.add_node(
        "generate_final_answer", 
        generate_final_answer,
        cache_policy=CachePolicy(
            key_func=answer_generation_cache_key,
            ttl=CACHE_TTL["ANSWER_GENERATION"]
        )
    )
    
    # Define the flow
    workflow.set_entry_point("process_input")
    
    # Main flow
    workflow.add_edge("process_input", "detect_language_and_optimize")
    workflow.add_edge("detect_language_and_optimize", "retrieve_documents")
    workflow.add_edge("retrieve_documents", "rank_documents")
    workflow.add_edge("rank_documents", "evaluate_content_quality")
    
    # Conditional routing after evaluation
    workflow.add_conditional_edges(
        "evaluate_content_quality",
        route_after_evaluation,
        {
            "generate_final_answer": "generate_final_answer",
            "request_user_feedback": "request_user_feedback"
        }
    )
    
    # Feedback loop
    workflow.add_edge("request_user_feedback", "process_user_feedback")
    
    workflow.add_conditional_edges(
        "process_user_feedback",
        route_after_feedback,
        {
            "process_input": "process_input",
            "detect_language_and_optimize": "detect_language_and_optimize",
            "generate_final_answer": "generate_final_answer"
        }
    )
    
    # End after generating answer
    workflow.add_edge("generate_final_answer", END)
    
    # Compile with InMemoryCache and interrupt capability
    return workflow.compile(
        cache=InMemoryCache(),
        interrupt_after=["request_user_feedback"]
    )

# =============================================================================
# MAIN EXPORTS
# =============================================================================

# This is the main export that LangGraph will look for
app = create_enhanced_rag_graph()

def clear_cache():
    """Clear cache by rebuilding the graph."""
    global app
    app = create_enhanced_rag_graph()
    logger.info("Graph cache cleared and rebuilt")

def update_cache_ttl(**kwargs):
    """Update cache TTL settings."""
    for key, value in kwargs.items():
        if key.upper() in CACHE_TTL:
            CACHE_TTL[key.upper()] = value
            logger.info(f"Cache TTL updated: {key.upper()} = {value}s")

# =============================================================================
# TESTING & DEBUGGING
# =============================================================================

if __name__ == "__main__":
    print("Enhanced RAG Graph with Node Caching created successfully!")
    print(f"Graph nodes: {list(app.get_graph().nodes.keys())}")
    print(f"Cache TTL settings: {CACHE_TTL}")
    
    # Optional: Add a simple test
    async def test_cache_flow():
        """Test cache functionality."""
        try:
            test_state = {
                "messages": [HumanMessage(content="What is artificial intelligence?")],
                "language": "English",
                "feedback_cycles": 0,
                "documents": [],
                "ranked_documents": [],
                "confidence_score": 0.0,
                "content_classification": "",
                "waiting_for_feedback": False,
                "error_message": None
            }
            
            print("First invocation (cache miss)...")
            result = await app.ainvoke(test_state)
            print(f"First query successful! Final message count: {len(result['messages'])}")
            
            print("\nSecond invocation (should have cache hits)...")
            # Same question - should hit cache for multiple nodes
            result2 = await app.ainvoke(test_state)
            print(f"Second query successful! Final message count: {len(result2['messages'])}")
            
            # Check for cache metadata in results
            for msg in result2["messages"]:
                if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('cached'):
                    print(f"✅ Cache hit detected!")
                    break
                    
        except Exception as e:
            print(f"Test failed: {e}")
    
    # Uncomment to run test
    # asyncio.run(test_cache_flow())