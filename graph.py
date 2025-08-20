# from __future__ import annotations

# from typing import TypedDict, List, Optional, Dict, Any, Literal, Annotated, Tuple
# from datetime import datetime
# import asyncio
# import hashlib
# import json

# from langgraph.graph import StateGraph, END, add_messages
# from langgraph.checkpoint.memory import MemorySaver
# from langgraph.cache.memory import InMemoryCache
# from langgraph.types import CachePolicy
# from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
# from langchain_core.prompts import ChatPromptTemplate

# # Import your existing components
# from core.llm_manager import LLMManager, LLMProvider
# from core.search_manager import SearchManager
# from pipeline.vector_store import VectorStoreManager
# from utils.logger import get_enhanced_logger

# # Optional cross-encoder for reranking
# try:
#     from sentence_transformers import CrossEncoder
#     HAS_CROSSENCODER = True
# except ImportError:
#     HAS_CROSSENCODER = False
#     print("Warning: sentence_transformers not available, using fallback ranking")

# # =============================================================================
# # CONFIGURATION & CONSTANTS
# # =============================================================================

# MAX_FEEDBACK_CYCLES = 3
# RETRIEVAL_COUNT = 12
# RERANK_COUNT = 6

# CONFIDENCE_THRESHOLDS = {
#     "HIGH": 0.75,     # Direct comprehensive answer
#     "MEDIUM": 0.45,   # Partial answer with disclaimers  
#     "LOW": 0.25       # Limited info with strong disclaimers
# }

# # Cache TTL settings (in seconds)
# CACHE_TTL = {
#     "LANGUAGE_DETECTION": 3600,      # 1 hour
#     "QUESTION_OPTIMIZATION": 1800,   # 30 minutes
#     "DOCUMENT_RETRIEVAL": 7200,      # 2 hours
#     "DOCUMENT_RANKING": 3600,        # 1 hour
#     "CONTENT_EVALUATION": 1800,      # 30 minutes
#     "ANSWER_GENERATION": 7200        # 2 hours
# }

# # =============================================================================
# # CACHE KEY GENERATION FUNCTIONS
# # =============================================================================

# def generate_cache_key(*args) -> str:
#     """Simple utility to generate consistent cache keys from any arguments."""
    
#     def normalize(value):
#         if value is None:
#             return "null"
#         elif isinstance(value, str):
#             return value.strip().lower()
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

# def language_detection_cache_key(state: 'RAGState') -> str:
#     """Cache key for language detection."""
#     current_question = get_current_question(state)
#     return generate_cache_key("language_detection", current_question[:200])

# def question_optimization_cache_key(state: 'RAGState') -> str:
#     """Cache key for question optimization."""
#     current_question = get_current_question(state)
#     context = get_conversation_context(state)
#     return generate_cache_key("optimize_question", current_question, 
#                              context, state.get("feedback_cycles", 0))

# def retrieval_cache_key(state: 'RAGState') -> str:
#     """Cache key for document retrieval."""
#     question = state.get("_optimized_question", get_current_question(state))
#     return generate_cache_key("retrieve_documents", question)

# def ranking_cache_key(state: 'RAGState') -> str:
#     """Cache key for document ranking."""
#     question = state.get("_optimized_question", get_current_question(state))
#     docs = state.get("documents", [])
#     # Create signature from document content (first 100 chars of each doc)
#     doc_signature = "|".join([doc.get('page_content', '')[:100] for doc in docs[:5]])
#     return generate_cache_key("rank_documents", question, doc_signature)

# def evaluation_cache_key(state: 'RAGState') -> str:
#     """Cache key for content evaluation."""
#     question = get_current_question(state)
#     ranked_docs = state.get("ranked_documents", [])
#     # Create signature from ranked document content
#     content_signature = "|".join([doc.get('page_content', '')[:150] for doc in ranked_docs[:3]])
#     return generate_cache_key("evaluate_content", question, content_signature)

# def answer_generation_cache_key(state: 'RAGState') -> str:
#     """Cache key for answer generation."""
#     question = get_current_question(state)
#     confidence = state.get("confidence_score", 0.0)
#     classification = state.get("content_classification", "")
#     docs_signature = "|".join([doc.get('page_content', '')[:100] for doc in state.get("ranked_documents", [])[:3]])
#     return generate_cache_key("generate_answer", question, confidence, classification, docs_signature)

# # =============================================================================
# # SIMPLIFIED STATE DEFINITION
# # =============================================================================

# class RAGState(TypedDict):
#     # Core conversation - single source of truth
#     messages: Annotated[List[BaseMessage], add_messages]
    
#     # Essential processing state
#     language: str
#     feedback_cycles: int
    
#     # Retrieved content - core to RAG functionality
#     documents: List[Dict[str, Any]]
#     ranked_documents: List[Dict[str, Any]]
    
#     # Evaluation results - needed for routing decisions
#     confidence_score: float
#     content_classification: str  # COMPLETE, PARTIAL, INSUFFICIENT
    
#     # Control flow
#     waiting_for_feedback: bool
    
#     # Optional - for debugging/analytics
#     error_message: Optional[str]

# # =============================================================================
# # COMPONENT INITIALIZATION
# # =============================================================================

# def initialize_components():
#     """Initialize all components with error handling."""
#     try:
#         search_manager = SearchManager()
#         llm_manager = LLMManager()
        
#         vector_store = VectorStoreManager(
#             embedding_model='paraphrase-multilingual-MiniLM-L12-v2',
#             collection_name="document_knowledge_base",
#             persist_dir="./vector_storage"
#         )
        
#         # Primary LLM for complex tasks
#         llm = llm_manager.get_chat_model(
#             provider=LLMProvider.ANTHROPIC,
#             model="claude-3-haiku-20240307",
#             temperature=0.7,
#             max_tokens=1500
#         )
        
#         # Lightweight LLM for simple tasks
#         try:
#             llm_light = llm_manager.get_chat_model(provider=LLMProvider.OLLAMA)
#         except Exception:
#             llm_light = llm  # Fallback to main LLM
        
#         logger = get_enhanced_logger("enhanced_rag_graph")
        
#         return search_manager, llm_manager, vector_store, llm, llm_light, logger
        
#     except Exception as e:
#         print(f"Error initializing components: {e}")
#         raise

# # Initialize global components
# search_manager, llm_manager, vector_store, llm, llm_light, logger = initialize_components()

# # =============================================================================
# # HELPER FUNCTIONS FOR MESSAGE PROCESSING
# # =============================================================================

# def get_current_question(state: RAGState) -> str:
#     """Extract the latest human question from messages."""
#     for msg in reversed(state["messages"]):
#         if isinstance(msg, HumanMessage) and msg.content.strip():
#             return msg.content.strip()
#     return ""

# def get_conversation_context(state: RAGState, max_exchanges: int = 2) -> str:
#     """Get recent conversation context for optimization."""
#     context_parts = []
#     human_count = 0
    
#     for msg in reversed(state["messages"][:-1]):  # Exclude latest
#         if human_count >= max_exchanges:
#             break
            
#         if isinstance(msg, HumanMessage):
#             human_count += 1
#             context_parts.append(f"Previous Q: {msg.content[:100]}...")
#         elif isinstance(msg, AIMessage) and human_count > 0:
#             context_parts.append(f"Previous A: {msg.content[:100]}...")
    
#     context_parts.reverse()
#     return "\n".join(context_parts)

# def is_new_question_session(state: RAGState) -> bool:
#     """Detect if this is a new question vs continued conversation."""
#     # If we have no documents and no feedback cycles, definitely new
#     if not state.get("ranked_documents") and state["feedback_cycles"] == 0:
#         return True
    
#     # If we've been waiting for feedback, the next message is likely feedback
#     if state.get("waiting_for_feedback"):
#         return False
    
#     # If we have existing documents but no feedback cycles, likely new question
#     if state.get("ranked_documents") and state["feedback_cycles"] == 0:
#         return True
        
#     return False

# def should_reset_for_new_question(state: RAGState) -> bool:
#     """Determine if we should reset state for a new question."""
#     return (is_new_question_session(state) and 
#             not state.get("waiting_for_feedback") and
#             get_current_question(state))

# def reset_processing_state(state: RAGState) -> None:
#     """Reset processing state while keeping messages and language."""
#     state["feedback_cycles"] = 0
#     state["documents"] = []
#     state["ranked_documents"] = []
#     state["confidence_score"] = 0.0
#     state["content_classification"] = ""
#     state["waiting_for_feedback"] = False
#     state["error_message"] = None
#     logger.info("Processing state reset for new question")

# # =============================================================================
# # UTILITY FUNCTIONS
# # =============================================================================

# def calculate_content_metrics(question: str, docs: List[Dict]) -> Dict[str, float]:
#     """Calculate quantitative content quality metrics."""
#     if not docs:
#         return {"keyword_overlap": 0.0, "content_length": 0, "doc_count": 0, 
#                 "avg_score": 0.0, "source_diversity": 0.0}
    
#     question_words = set(question.lower().split())
#     all_content = " ".join([d.get("page_content", "").lower() for d in docs])
#     content_words = set(all_content.split())
    
#     # Calculate metrics
#     overlap = len(question_words.intersection(content_words))
#     keyword_overlap = overlap / max(len(question_words), 1)
    
#     sources = set([d.get("metadata", {}).get("source", "") for d in docs])
#     source_diversity = len(sources) / len(docs)
    
#     avg_score = sum([d.get("score", 0.0) for d in docs]) / len(docs)
    
#     return {
#         "keyword_overlap": keyword_overlap,
#         "content_length": len(all_content),
#         "doc_count": len(docs),
#         "avg_score": avg_score,
#         "source_diversity": source_diversity
#     }

# def combine_confidence_metrics(llm_confidence: float, metrics: Dict[str, float]) -> float:
#     """Combine LLM confidence with quantitative metrics."""
#     base_confidence = llm_confidence * 0.75
    
#     # Metric bonuses
#     bonus = 0.0
#     if metrics.get("keyword_overlap", 0) > 0.3:
#         bonus += 0.08
#     if metrics.get("content_length", 0) > 800:
#         bonus += 0.07
#     if metrics.get("avg_score", 0) > 0.7:
#         bonus += 0.10
    
#     return min(1.0, base_confidence + bonus)

# def format_sources_from_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
#     """Generate sources info from documents when needed."""
#     sources = []
#     seen_sources = set()
    
#     for doc in docs:
#         metadata = doc.get("metadata", {})
#         source_path = metadata.get("source", "Unknown")
        
#         if source_path not in seen_sources:
#             seen_sources.add(source_path)
#             sources.append({
#                 "file_name": metadata.get("File Name", metadata.get("file_name", "Unknown file")),
#                 "author": metadata.get("Author", metadata.get("author", "")),
#                 "path": source_path,
#                 "creation_date": metadata.get("Creationdate", metadata.get("creation_date", ""))
#             })
    
#     return sources

# def should_use_light_model(task: str) -> bool:
#     """Determine if we can use lighter model for simple tasks."""
#     light_tasks = ["language_detection", "simple_classification", "relevance_check"]
#     return task in light_tasks

# # =============================================================================
# # CACHEABLE GRAPH NODES
# # =============================================================================

# async def process_input(state: RAGState) -> RAGState:
#     """Entry point - validate input and set up processing."""
#     logger.info("=== PROCESSING INPUT ===")
    
#     # Initialize defaults if missing
#     defaults = {
#         "messages": [], "feedback_cycles": 0, "confidence_score": 0.0,
#         "documents": [], "ranked_documents": [], "waiting_for_feedback": False, 
#         "language": "English", "content_classification": "", "error_message": None
#     }
#     for key, default_value in defaults.items():
#         if key not in state:
#             state[key] = default_value
    
#     # Get current question
#     current_question = get_current_question(state)
#     if not current_question:
#         state["error_message"] = "No question found in input"
#         # Add error message to conversation
#         error_msg = "I didn't receive a question. Please ask something I can help you with."
#         state["messages"].append(AIMessage(content=error_msg))
#         return state
    
#     # Check if we should reset for new question
#     if should_reset_for_new_question(state):
#         logger.info(f"NEW QUESTION detected: {current_question[:50]}...")
#         reset_processing_state(state)
    
#     logger.info(f"Processing question: {current_question[:100]}...")
#     return state

# async def detect_language_and_optimize(state: RAGState) -> RAGState:
#     """Detect language and optimize question for search. CACHED."""
#     logger.info("=== LANGUAGE DETECTION & OPTIMIZATION ===")
    
#     current_question = get_current_question(state)
    
#     try:
#         # Detect language (only for new questions)
#         if state["feedback_cycles"] == 0:
#             model = llm_light if should_use_light_model("language_detection") else llm
            
#             language_prompt = ChatPromptTemplate.from_messages([
#                 ("system", """Detect the language and respond with ONLY the language name in English.
#                 Examples: "What is AI?" → English | "¿Qué es IA?" → Spanish | "Qu'est-ce que l'IA?" → French"""),
#                 ("human", "Question: {question}")
#             ])
            
#             response = await model.ainvoke(language_prompt.format_messages(question=current_question))
#             state["language"] = response.content.strip()
#             logger.info(f"Detected language: {state['language']}")
        
#         # Optimize question for search
#         if state["feedback_cycles"] == 0:
#             system_msg = f"""Rewrite this question to be more searchable and clear.
#             CRITICAL: Respond in {state['language']} only. Return just the rewritten question."""
#             user_msg = f"Question: {current_question}"
#         else:
#             # We're processing feedback - use it to improve the search
#             system_msg = f"""Incorporate this feedback to create a better search query.
#             CRITICAL: Respond in {state['language']} only. Return just the improved question."""
#             user_msg = f"""Question: {current_question}
#             Context: {get_conversation_context(state)}"""
        
#         optimize_prompt = ChatPromptTemplate.from_messages([("system", system_msg), ("human", user_msg)])
#         response = await llm.ainvoke(optimize_prompt.format_messages())
        
#         optimized_question = response.content.strip()
#         logger.info(f"Optimized question: {optimized_question}")
        
#         # Store optimized question in state for this processing cycle
#         state["_optimized_question"] = optimized_question
        
#         return state
        
#     except Exception as e:
#         logger.failure(f"Language/optimization failed: {e}")
#         # Continue with original question
#         state["_optimized_question"] = current_question
#         return state

# async def retrieve_and_rank_documents(state: RAGState) -> RAGState:
#     """Retrieve and rank documents in one step."""
#     logger.info("=== DOCUMENT RETRIEVAL & RANKING ===")
    
#     # Use optimized question if available, fallback to current question
#     search_query = state.get("_optimized_question", get_current_question(state))
    
#     # Try multiple retrieval strategies using vector_store.query_documents
#     strategies = ["hybrid", "vector", "keyword"]
    
#     for strategy in strategies:
#         try:
#             logger.info(f"Trying retrieval strategy: {strategy}")
            
#             # Use vector_store.query_documents for all strategies
#             docs, scores = vector_store.query_documents(
#                 query=search_query, 
#                 k=RETRIEVAL_COUNT, 
#                 rerank=False, 
#                 search_type=strategy  # This handles "hybrid", "vector", or "keyword"
#             )
            
#             if docs:
#                 # Store retrieved documents
#                 state["documents"] = [
#                     {"page_content": d.page_content, "metadata": d.metadata, "score": s}
#                     for d, s in zip(docs, scores)
#                 ]
                
#                 # Rank documents
#                 try:
#                     if HAS_CROSSENCODER and len(state["documents"]) > 1:
#                         # Re-rank using cross-encoder
#                         reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
#                         pairs = [(search_query, doc["page_content"]) for doc in state["documents"]]
#                         relevance_scores = reranker.predict(pairs)
                        
#                         # Sort by relevance and take top results
#                         ranked_docs_with_scores = sorted(
#                             zip(state["documents"], relevance_scores), 
#                             key=lambda x: x[1], reverse=True
#                         )
                        
#                         state["ranked_documents"] = [doc for doc, _ in ranked_docs_with_scores[:RERANK_COUNT]]
#                         logger.info(f"Re-ranked {len(state['ranked_documents'])} documents using cross-encoder")
#                     else:
#                         # Fallback: use original scores
#                         sorted_docs = sorted(state["documents"], key=lambda x: x.get("score", 0), reverse=True)
#                         state["ranked_documents"] = sorted_docs[:RERANK_COUNT]
#                         logger.info(f"Ranked {len(state['ranked_documents'])} documents using original scores")
                    
#                 except Exception as rank_error:
#                     logger.warning(f"Ranking failed, using original order: {rank_error}")
#                     state["ranked_documents"] = state["documents"][:RERANK_COUNT]
                
#                 logger.info(f"Retrieved {len(docs)} documents using {strategy}")
#                 return state
                
#         except Exception as e:
#             logger.warning(f"Strategy {strategy} failed: {e}")
#             continue
    
#     # All strategies failed
#     state["error_message"] = "Document retrieval failed"
#     logger.error("All retrieval strategies failed")
#     return state

# async def rank_documents(state: RAGState) -> RAGState:
#     """Rank and reorder documents by relevance. CACHED."""
#     logger.info("=== DOCUMENT RANKING ===")
    
#     if not state.get("documents"):
#         logger.warning("No documents to rank")
#         return state
    
#     search_query = state.get("_optimized_question", get_current_question(state))
    
#     try:
#         if HAS_CROSSENCODER and len(state["documents"]) > 1:
#             # Re-rank using cross-encoder
#             reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
#             pairs = [(search_query, doc["page_content"]) for doc in state["documents"]]
#             relevance_scores = reranker.predict(pairs)
            
#             # Sort by relevance and take top results
#             ranked_docs_with_scores = sorted(
#                 zip(state["documents"], relevance_scores), 
#                 key=lambda x: x[1], reverse=True
#             )
            
#             state["ranked_documents"] = [doc for doc, _ in ranked_docs_with_scores[:RERANK_COUNT]]
#             logger.info(f"Re-ranked {len(state['ranked_documents'])} documents using cross-encoder")
#         else:
#             # Fallback: use original scores
#             sorted_docs = sorted(state["documents"], key=lambda x: x.get("score", 0), reverse=True)
#             state["ranked_documents"] = sorted_docs[:RERANK_COUNT]
#             logger.info(f"Ranked {len(state['ranked_documents'])} documents using original scores")
        
#         return state
        
#     except Exception as e:
#         logger.warning(f"Ranking failed, using original order: {e}")
#         state["ranked_documents"] = state["documents"][:RERANK_COUNT]
#         return state

# async def evaluate_content_quality(state: RAGState) -> RAGState:
#     """Evaluate content quality and calculate confidence score. CACHED."""
#     logger.info("=== CONTENT EVALUATION ===")
    
#     current_question = get_current_question(state)
    
#     if not state["ranked_documents"]:
#         state["content_classification"] = "INSUFFICIENT"
#         state["confidence_score"] = 0.0
#         logger.info("No documents available for evaluation")
#         return state
    
#     try:
#         # Calculate quantitative metrics
#         metrics = calculate_content_metrics(current_question, state["ranked_documents"])
        
#         # LLM evaluation
#         context = "\n\n".join([
#             f"Doc {i+1}: {doc['page_content'][:400]}..."
#             for i, doc in enumerate(state["ranked_documents"])
#         ])
        
#         eval_prompt = ChatPromptTemplate.from_messages([
#             ("system", f"""Evaluate if context can answer the question. Respond in {state['language']}.
            
#             Format your response EXACTLY as:
#             CLASSIFICATION: [COMPLETE/PARTIAL/INSUFFICIENT]
#             CONFIDENCE: [0.0-1.0]
#             REASONING: [Brief explanation in {state['language']}]
            
#             Rules:
#             - COMPLETE (0.7-1.0): Context fully answers with specific information
#             - PARTIAL (0.3-0.7): Some relevant info but incomplete  
#             - INSUFFICIENT (0.0-0.3): No relevant specific information"""),
#             ("human", "Question: {question}\n\nContext:\n{context}")
#         ])
        
#         response = await llm.ainvoke(eval_prompt.format_messages(
#             question=current_question, context=context
#         ))
        
#         # Parse structured response
#         content = response.content.strip()
#         classification = "INSUFFICIENT"
#         llm_confidence = 0.0
        
#         for line in content.split('\n'):
#             if line.startswith("CLASSIFICATION:"):
#                 classification = line.split(":", 1)[1].strip()
#             elif line.startswith("CONFIDENCE:"):
#                 try:
#                     llm_confidence = float(line.split(":", 1)[1].strip())
#                 except Exception:
#                     llm_confidence = 0.0
        
#         # Combine with quantitative metrics
#         final_confidence = combine_confidence_metrics(llm_confidence, metrics)
        
#         state["content_classification"] = classification
#         state["confidence_score"] = final_confidence
        
#         logger.info(f"Evaluation: {classification}, confidence: {final_confidence:.2f}")
#         return state
        
#     except Exception as e:
#         logger.failure(f"Content evaluation failed: {e}")
#         state["content_classification"] = "INSUFFICIENT"
#         state["confidence_score"] = 0.0
#         return state

# async def request_user_feedback(state: RAGState) -> RAGState:
#     """Request user feedback when content is insufficient."""
#     logger.info("=== REQUESTING FEEDBACK ===")

#     current_question = get_current_question(state)

#     # ------------------------------------------------------------------
#     # 1. Build a short, factual summary of what *was* retrieved
#     # ------------------------------------------------------------------
#     if state["ranked_documents"]:
#         snippets = [
#             f"  - Doc {i+1} “{doc.get('metadata', {}).get('title', 'Untitled')}” "
#             f"(score={doc.get('score', 0):.2f}): "
#             f"{doc.get('page_content', '')[:120]}..."
#             for i, doc in enumerate(state["ranked_documents"][:3])
#         ]
#         found_info = (
#             f"I located {len(state['ranked_documents'])} document(s). "
#             f"The best matches are:\n" + "\n".join(snippets)
#         )
#     else:
#         found_info = "No documents in the knowledge base matched the query."

#     # ------------------------------------------------------------------
#     # 2. Construct the prompt that asks the user to refine the query
#     # ------------------------------------------------------------------
#     feedback_prompt = ChatPromptTemplate.from_messages([
#         ("system", f"""
# You are a helpful assistant. The user asked a question, but the retrieved
# documents are insufficient for a complete answer.

# Start your reply with a concise, neutral summary of what was found.
# Then, in 2-3 short bullet points:
# • Ask clarifying questions or request additional keywords.
# • Suggest alternative phrasing or more specific details.

# Keep the tone constructive and friendly. Respond in {state['language']}.
# """.strip()),
#         ("human", """
# Question: {question}

# Retrieved information:
# {found_info}

# Help the user refine their search.
# """.strip())
#     ])

#     try:
#         response = await llm.ainvoke(
#             feedback_prompt.format_messages(
#                 question=current_question,
#                 found_info=found_info
#             )
#         )

#         state["messages"].append(AIMessage(content=response.content.strip()))
#         state["waiting_for_feedback"] = True
#         logger.info("Feedback requested from user")
#         return state

#     except Exception as e:
#         logger.failure("Feedback request failed: %s", e)
#         # Fallback: let the pipeline continue with whatever it has
#         return state

# async def process_user_feedback(state: RAGState) -> RAGState:
#     """Process user feedback and determine next action."""
#     logger.info("=== PROCESSING FEEDBACK ===")
    
#     if not state.get("waiting_for_feedback"):
#         # Check if this is a new question
#         if should_reset_for_new_question(state):
#             logger.info("New question detected, not feedback")
#             return state
#         else:
#             # No feedback expected, continue to answer
#             return state
    
#     # Extract feedback (should be the latest human message)
#     feedback = get_current_question(state)
    
#     if not feedback:
#         state["waiting_for_feedback"] = False
#         return state
    
#     # Process feedback commands
#     feedback_lower = feedback.lower().strip()
    
#     # Stop/proceed commands
#     stop_commands = {"stop", "abort", "cancel", "quit", "end", "exit", "no"}
#     proceed_commands = {"proceed", "continue", "yes", "go", "ok", "okay", "fine"}
    
#     if feedback_lower in stop_commands or feedback_lower in proceed_commands:
#         state["waiting_for_feedback"] = False
#         logger.info(f"User chose to {feedback_lower}")
#         return state
    
#     # Check max feedback cycles
#     if state["feedback_cycles"] >= MAX_FEEDBACK_CYCLES:
#         state["waiting_for_feedback"] = False
#         logger.info("Max feedback cycles reached")
#         return state
    
#     # Real feedback - iterate
#     state["feedback_cycles"] += 1
#     state["waiting_for_feedback"] = False
    
#     logger.info(f"Processing feedback cycle {state['feedback_cycles']}: {feedback[:50]}...")
#     return state

# async def generate_final_answer(state: RAGState) -> RAGState:
#     """Generate a detailed, Markdown-formatted final answer. CACHED."""
#     logger.info("=== GENERATING ANSWER ===")

#     current_question = get_current_question(state)

#     if not state["ranked_documents"]:
#         # No content available
#         no_content_msg = f"""# ❌ No Information Found

# I couldn't find relevant information in the knowledge base to answer your question:
# > **"{current_question}"**

# ### Suggestions:
# - Rephrase your question with different keywords.
# - Be more specific about what you're looking for.
# - Check if the information might be in the knowledge base under different terms.
# """
#         # Translate if needed
#         if state["language"] != "English":
#             try:
#                 translate_prompt = ChatPromptTemplate.from_messages([
#                     ("system", f"Translate this message to {state['language']}:"),
#                     ("human", no_content_msg)
#                 ])
#                 response = await llm.ainvoke(translate_prompt.format_messages())
#                 no_content_msg = response.content.strip()
#             except:
#                 pass  # Use English fallback

#         state["messages"].append(AIMessage(content=no_content_msg))
#         reset_processing_state(state)
#         return state

#     try:
#         # Prepare context with source information
#         context_parts = []
#         for i, doc in enumerate(state["ranked_documents"], 1):
#             metadata = doc["metadata"]
#             source_name = metadata.get("File Name", metadata.get("file_name", f"Source {i}"))
#             context_parts.append(f"[Source {i}: {source_name}]\n{doc['page_content']}")

#         context = "\n\n".join(context_parts)
#         confidence = state["confidence_score"]

#         # Choose answer style based on confidence
#         if confidence >= CONFIDENCE_THRESHOLDS["HIGH"]:
#             system_msg = f"""Provide a **comprehensive, Markdown-formatted answer** using the context.
#             Guidelines:
#             - Answer thoroughly with clear explanations.
#             - Include **real-life examples** if applicable.
#             - Use bullet points, bold/italics, and headings for readability.
#             - Reference sources by name when citing information.
#             - Respond in {state['language']} only.
#             - Format your answer in Markdown.
#             """
#         elif confidence >= CONFIDENCE_THRESHOLDS["MEDIUM"]:
#             system_msg = f"""Provide a **helpful, Markdown-formatted partial answer** based on available context.
#             Guidelines:
#             - Answer what you CAN with clear explanations.
#             - Include **real-life examples** if applicable.
#             - Use bullet points, bold/italics, and headings for readability.
#             - Reference sources by name when citing information.
#             - End with: "This is a partial answer based on available documents."
#             - Suggest asking more specific questions for areas needing clarification.
#             - Respond in {state['language']} only.
#             - Format your answer in Markdown.
#             """
#         else:
#             system_msg = f"""Provide a **limited, Markdown-formatted answer** based on available context.
#             Guidelines:
#             - Share only clearly available specific information.
#             - Reference sources for any information provided.
#             - Start with: "Based on available documents, I can provide limited information."
#             - Strongly suggest providing more specific search terms.
#             - Respond in {state['language']} only.
#             - Format your answer in Markdown.
#             """

#         # Add instruction to include real-life examples
#         system_msg += "\n\nIf applicable, include a **real-life example** to illustrate the concept."

#         answer_prompt = ChatPromptTemplate.from_messages([
#             ("system", system_msg),
#             ("human", f"""Question: {current_question}

# Context with sources:
# {context}

# ---
# **Instructions:**
# - Format your answer in **Markdown**.
# - Use headings, bullet points, and bold/italics for clarity.
# - Include a real-life example if possible.
# """)
#         ])

#         response = await llm.ainvoke(answer_prompt.format_messages(
#             question=current_question, context=context
#         ))

#         base_answer = response.content.strip()

#         # Add sources section in Markdown
#         sources = format_sources_from_docs(state["ranked_documents"])
#         sources_section = "\n\n## 📚 Sources\n"
#         sources_section += f"Confidence: **{confidence:.1%}**\n\n"
#         for source in sources:
#             sources_section += f"- **{source['file_name']}**"
#             if source.get('author'):
#                 sources_section += f" (Author: {source['author']})"
#             sources_section += "\n"

#         final_answer = f"{base_answer}\n{sources_section}"

#         # Append the Markdown-formatted answer
#         state["messages"].append(AIMessage(content=final_answer))

#         # Reset for next question
#         reset_processing_state(state)

#         logger.info(f"Answer generated with confidence {confidence:.2f}")
#         return state

#     except Exception as e:
#         logger.failure(f"Answer generation failed: {e}")
#         error_msg = """# ⚠️ Error Generating Answer

# I encountered an error while generating the answer.
# Please try rephrasing your question or ask something else.
# """
#         state["messages"].append(AIMessage(content=error_msg))
#         return state

# # =============================================================================
# # ROUTING FUNCTIONS
# # =============================================================================

# def should_retrieve_documents(state: RAGState) -> bool:
#     """Determine if we need to retrieve documents."""
#     # Always retrieve for new questions or after feedback
#     if (state["feedback_cycles"] == 0 and not state.get("ranked_documents")) or state["feedback_cycles"] > 0:
#         return True
    
#     # Check if existing documents are relevant (simplified check)
#     return len(state.get("ranked_documents", [])) < 3

# def should_generate_answer(state: RAGState) -> bool:
#     """Determine if we should generate an answer."""
#     # Generate if we have good content or max feedback cycles reached
#     if state["feedback_cycles"] >= MAX_FEEDBACK_CYCLES:
#         return True
    
#     if state["content_classification"] in ["COMPLETE", "PARTIAL"] and state["confidence_score"] >= CONFIDENCE_THRESHOLDS["LOW"]:
#         return True
    
#     return False

# def route_after_evaluation(state: RAGState) -> Literal["generate_final_answer", "request_user_feedback"]:
#     """Route after content evaluation."""
#     if should_generate_answer(state):
#         return "generate_final_answer"
#     else:
#         return "request_user_feedback"

# def route_after_feedback(state: RAGState) -> Literal["process_input", "detect_language_and_optimize", "generate_final_answer"]:
#     """Route after processing feedback."""
#     if not state["waiting_for_feedback"]:
#         if should_reset_for_new_question(state):
#             return "process_input"
#         elif state["feedback_cycles"] > 0:
#             return "detect_language_and_optimize"  # Retry with feedback
#         else:
#             return "generate_final_answer"
#     else:
#         return "generate_final_answer"  # Shouldn't happen, but safety net

# # =============================================================================
# # GRAPH CONSTRUCTION WITH CACHING
# # =============================================================================

# def create_enhanced_rag_graph():
#     """Create the enhanced RAG graph with node-level caching."""
#     workflow = StateGraph(RAGState)
    
#     # Add nodes with cache policies for expensive operations
#     workflow.add_node("process_input", process_input)
    
#     # Cache language detection and optimization
#     workflow.add_node(
#         "detect_language_and_optimize", 
#         detect_language_and_optimize,
#         cache_policy=CachePolicy(
#             key_func=question_optimization_cache_key,
#             ttl=CACHE_TTL["QUESTION_OPTIMIZATION"]
#         )
#     )
    
#     # Cache document retrieval (most expensive operation)
#     workflow.add_node(
#         "retrieve_documents", 
#         retrieve_and_rank_documents,
#         cache_policy=CachePolicy(
#             key_func=retrieval_cache_key,
#             ttl=CACHE_TTL["DOCUMENT_RETRIEVAL"]
#         )
#     )
    
#     # Cache document ranking
#     workflow.add_node(
#         "rank_documents", 
#         rank_documents,
#         cache_policy=CachePolicy(
#             key_func=ranking_cache_key,
#             ttl=CACHE_TTL["DOCUMENT_RANKING"]
#         )
#     )
    
#     # Cache content evaluation
#     workflow.add_node(
#         "evaluate_content_quality", 
#         evaluate_content_quality,
#         cache_policy=CachePolicy(
#             key_func=evaluation_cache_key,
#             ttl=CACHE_TTL["CONTENT_EVALUATION"]
#         )
#     )
    
#     # No cache for feedback (interactive)
#     workflow.add_node("request_user_feedback", request_user_feedback)
#     workflow.add_node("process_user_feedback", process_user_feedback)
    
#     # Cache answer generation
#     workflow.add_node(
#         "generate_final_answer", 
#         generate_final_answer,
#         cache_policy=CachePolicy(
#             key_func=answer_generation_cache_key,
#             ttl=CACHE_TTL["ANSWER_GENERATION"]
#         )
#     )
    
#     # Define the flow
#     workflow.set_entry_point("process_input")
    
#     # Main flow
#     workflow.add_edge("process_input", "detect_language_and_optimize")
#     workflow.add_edge("detect_language_and_optimize", "retrieve_documents")
#     workflow.add_edge("retrieve_documents", "rank_documents")
#     workflow.add_edge("rank_documents", "evaluate_content_quality")
    
#     # Conditional routing after evaluation
#     workflow.add_conditional_edges(
#         "evaluate_content_quality",
#         route_after_evaluation,
#         {
#             "generate_final_answer": "generate_final_answer",
#             "request_user_feedback": "request_user_feedback"
#         }
#     )
    
#     # Feedback loop
#     workflow.add_edge("request_user_feedback", "process_user_feedback")
    
#     workflow.add_conditional_edges(
#         "process_user_feedback",
#         route_after_feedback,
#         {
#             "process_input": "process_input",
#             "detect_language_and_optimize": "detect_language_and_optimize",
#             "generate_final_answer": "generate_final_answer"
#         }
#     )
    
#     # End after generating answer
#     workflow.add_edge("generate_final_answer", END)
    
#     # Compile with InMemoryCache and interrupt capability
#     return workflow.compile(
#         cache=InMemoryCache(),
#         interrupt_after=["request_user_feedback"]
#     )

# # =============================================================================
# # MAIN EXPORTS
# # =============================================================================

# # This is the main export that LangGraph will look for
# app = create_enhanced_rag_graph()

# def clear_cache():
#     """Clear cache by rebuilding the graph."""
#     global app
#     app = create_enhanced_rag_graph()
#     logger.info("Graph cache cleared and rebuilt")

# def update_cache_ttl(**kwargs):
#     """Update cache TTL settings."""
#     for key, value in kwargs.items():
#         if key.upper() in CACHE_TTL:
#             CACHE_TTL[key.upper()] = value
#             logger.info(f"Cache TTL updated: {key.upper()} = {value}s")

# # =============================================================================
# # TESTING & DEBUGGING
# # =============================================================================

# if __name__ == "__main__":
#     print("Enhanced RAG Graph with Node Caching created successfully!")
#     print(f"Graph nodes: {list(app.get_graph().nodes.keys())}")
#     print(f"Cache TTL settings: {CACHE_TTL}")
    
#     # Optional: Add a simple test
#     async def test_cache_flow():
#         """Test cache functionality."""
#         try:
#             test_state = {
#                 "messages": [HumanMessage(content="What is artificial intelligence?")],
#                 "language": "English",
#                 "feedback_cycles": 0,
#                 "documents": [],
#                 "ranked_documents": [],
#                 "confidence_score": 0.0,
#                 "content_classification": "",
#                 "waiting_for_feedback": False,
#                 "error_message": None
#             }
            
#             print("First invocation (cache miss)...")
#             result = await app.ainvoke(test_state)
#             print(f"First query successful! Final message count: {len(result['messages'])}")
            
#             print("\nSecond invocation (should have cache hits)...")
#             # Same question - should hit cache for multiple nodes
#             result2 = await app.ainvoke(test_state)
#             print(f"Second query successful! Final message count: {len(result2['messages'])}")
            
#             # Check for cache metadata in results
#             for msg in result2["messages"]:
#                 if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('cached'):
#                     print(f"✅ Cache hit detected!")
#                     break
                    
#         except Exception as e:
#             print(f"Test failed: {e}")
    
#     # Uncomment to run test
#     # asyncio.run(test_cache_flow())



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
RETRIEVAL_COUNT = 15  # Increased for comprehensive search
RERANK_COUNT = 8      # Increased for better final selection

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
    return generate_cache_key("retrieve_documents_combined", question)

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
    search_strategies_used: List[str]  # Track which strategies were used

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
    state["search_strategies_used"] = []
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

def deduplicate_documents(docs_with_scores: List[Tuple[Any, float, str]]) -> List[Tuple[Any, float, str]]:
    """Remove duplicate documents based on content similarity."""
    if not docs_with_scores:
        return []
    
    unique_docs = []
    seen_content = set()
    
    for doc, score, strategy in docs_with_scores:
        # Create a content hash for deduplication
        content_hash = hashlib.md5(doc.page_content[:500].encode()).hexdigest()[:16]
        
        if content_hash not in seen_content:
            seen_content.add(content_hash)
            unique_docs.append((doc, score, strategy))
    
    return unique_docs

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
        "language": "English", "content_classification": "", "error_message": None,
        "search_strategies_used": []
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

async def retrieve_and_rank_documents_comprehensive(state: RAGState) -> RAGState:
    """Retrieve documents using ALL strategies and combine results for LLM selection."""
    logger.info("=== COMPREHENSIVE DOCUMENT RETRIEVAL & RANKING ===")
    
    # Use optimized question if available, fallback to current question
    search_query = state.get("_optimized_question", get_current_question(state))
    
    # Define all search strategies
    strategies = ["hybrid", "vector", "keyword"]
    all_docs_with_strategy = []
    successful_strategies = []
    
    # Try ALL strategies and collect results
    for strategy in strategies:
        try:
            logger.info(f"Executing retrieval strategy: {strategy}")
            
            # Use vector_store.query_documents for all strategies
            docs, scores = vector_store.query_documents(
                query=search_query, 
                k=RETRIEVAL_COUNT, 
                rerank=False, 
                search_type=strategy
            )
            
            if docs:
                # Add strategy tag to each document
                for doc, score in zip(docs, scores):
                    all_docs_with_strategy.append((doc, score, strategy))
                
                successful_strategies.append(strategy)
                logger.info(f"Strategy '{strategy}' retrieved {len(docs)} documents")
            else:
                logger.warning(f"Strategy '{strategy}' returned no documents")
                
        except Exception as e:
            logger.warning(f"Strategy '{strategy}' failed: {e}")
            continue
    
    # Check if we got any results
    if not all_docs_with_strategy:
        state["error_message"] = "All retrieval strategies failed"
        state["documents"] = []
        state["ranked_documents"] = []
        state["search_strategies_used"] = []
        logger.error("All retrieval strategies failed")
        return state
    
    # Deduplicate documents while preserving best scores
    unique_docs_with_strategy = deduplicate_documents(all_docs_with_strategy)
    
    # Convert to document format with strategy information
    combined_documents = []
    for doc, score, strategy in unique_docs_with_strategy:
        doc_dict = {
            "page_content": doc.page_content,
            "metadata": doc.metadata,
            "score": score,
            "retrieval_strategy": strategy
        }
        combined_documents.append(doc_dict)
    
    # Store all retrieved documents
    state["documents"] = combined_documents
    state["search_strategies_used"] = successful_strategies
    
    logger.info(f"Combined retrieval: {len(combined_documents)} unique documents from strategies: {successful_strategies}")
    
    # Now let LLM rank and select the best documents
    try:
        if len(combined_documents) > RERANK_COUNT:
            # Use LLM to intelligently select the best documents
            doc_summaries = []
            for i, doc in enumerate(combined_documents[:20]):  # Limit to top 20 for LLM processing
                summary = f"Doc {i+1} (Strategy: {doc['retrieval_strategy']}, Score: {doc['score']:.3f}):\n{doc['page_content'][:300]}..."
                doc_summaries.append(summary)
            
            ranking_prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert document ranker. Given a search query and documents from multiple retrieval strategies, select the {RERANK_COUNT} MOST RELEVANT documents.

                Instructions:
                - Consider relevance, specificity, and information quality
                - Diversify by including documents from different strategies when possible
                - Respond with ONLY the document numbers (1-{len(doc_summaries[:20])}) separated by commas
                - Example response: "3,7,1,12,5,9,2,15"
                
                Query: {search_query}"""),
                ("human", "Documents to rank:\n\n" + "\n\n".join(doc_summaries))
            ])
            
            response = await llm.ainvoke(ranking_prompt.format_messages(query=search_query))
            
            # Parse LLM response to get document indices
            try:
                selected_indices = [int(x.strip()) - 1 for x in response.content.strip().split(",")]
                # Ensure indices are valid
                selected_indices = [i for i in selected_indices if 0 <= i < len(combined_documents)]
                
                if selected_indices:
                    state["ranked_documents"] = [combined_documents[i] for i in selected_indices[:RERANK_COUNT]]
                    logger.info(f"LLM selected {len(state['ranked_documents'])} best documents")
                else:
                    raise ValueError("No valid indices returned")
                    
            except Exception as parse_error:
                logger.warning(f"LLM ranking parsing failed: {parse_error}, using fallback ranking")
                raise parse_error
                
        else:
            # Few documents, use all
            state["ranked_documents"] = combined_documents[:RERANK_COUNT]
            logger.info(f"Using all {len(state['ranked_documents'])} documents (below rerank threshold)")
            
    except Exception as ranking_error:
        logger.warning(f"LLM ranking failed: {ranking_error}, using cross-encoder fallback")
        
        # Fallback to cross-encoder or score-based ranking
        try:
            if HAS_CROSSENCODER and len(combined_documents) > 1:
                # Re-rank using cross-encoder
                reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                pairs = [(search_query, doc["page_content"]) for doc in combined_documents]
                relevance_scores = reranker.predict(pairs)
                
                # Sort by relevance and take top results
                ranked_docs_with_scores = sorted(
                    zip(combined_documents, relevance_scores), 
                    key=lambda x: x[1], reverse=True
                )
                
                state["ranked_documents"] = [doc for doc, _ in ranked_docs_with_scores[:RERANK_COUNT]]
                logger.info(f"Re-ranked {len(state['ranked_documents'])} documents using cross-encoder")
            else:
                # Fallback: use original scores
                sorted_docs = sorted(combined_documents, key=lambda x: x.get("score", 0), reverse=True)
                state["ranked_documents"] = sorted_docs[:RERANK_COUNT]
                logger.info(f"Ranked {len(state['ranked_documents'])} documents using original scores")
                
        except Exception as fallback_error:
            logger.warning(f"Fallback ranking failed: {fallback_error}, using original order")
            state["ranked_documents"] = combined_documents[:RERANK_COUNT]
    
    logger.info(f"Final ranking complete: {len(state['ranked_documents'])} documents selected")
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
            f"Doc {i+1} (Strategy: {doc.get('retrieval_strategy', 'unknown')}): {doc['page_content'][:400]}..."
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
    """Request user feedback - provide found information OR nothing found, then suggestions."""
    logger.info("=== REQUESTING FEEDBACK ===")

    current_question = get_current_question(state)

    # ------------------------------------------------------------------
    # 1. First, provide any information that WAS found (if any)
    # ------------------------------------------------------------------
    if state["ranked_documents"]:
        # We have some information - present it first
        try:
            context = "\n\n".join([
                f"From {doc.get('metadata', {}).get('file_name', 'Unknown')}: {doc['page_content'][:200]}..."
                for doc in state["ranked_documents"][:3]
            ])
            
            # Generate a partial answer with available information
            partial_answer_prompt = ChatPromptTemplate.from_messages([
                ("system", f"""Based on the available context, provide what information you CAN find related to the question.
                
                Rules:
                - Present any relevant information found in the documents
                - Be clear about what information is available vs missing
                - Keep it concise but informative
                - Respond in {state['language']}
                - Start with: "Based on available documents, I found:"
                """),
                ("human", f"Question: {current_question}\n\nAvailable context:\n{context}")
            ])
            
            response = await llm.ainvoke(partial_answer_prompt.format_messages())
            found_info = response.content.strip()
            
        except Exception as e:
            logger.warning(f"Failed to generate partial answer: {e}")
            # Fallback to simple summary
            snippets = [
                f"  - {doc.get('metadata', {}).get('file_name', 'Unknown')}: "
                f"{doc.get('page_content', '')[:120]}..."
                for doc in state["ranked_documents"][:3]
            ]
            found_info = f"Based on available documents, I found some related information:\n" + "\n".join(snippets)
    else:
        found_info = "**No relevant information was found** in the knowledge base for your question."

    # ------------------------------------------------------------------
    # 2. Then provide search improvement suggestions
    # ------------------------------------------------------------------
    strategies_used = state.get("search_strategies_used", ["hybrid", "vector", "keyword"])
    
    improvement_prompt = ChatPromptTemplate.from_messages([
        ("system", f"""The user's search didn't find sufficient information. Provide helpful suggestions to improve their search.

        Search strategies used: {', '.join(strategies_used)}
        
        In 2-3 short bullet points, suggest:
        • Different keywords or terms to try
        • More specific details they could provide
        • Alternative ways to phrase the question
        
        Keep suggestions practical and specific. Respond in {state['language']}.
        """),
        ("human", f"Original question: {current_question}")
    ])

    try:
        response = await llm.ainvoke(improvement_prompt.format_messages())
        suggestions = response.content.strip()
        
        # Combine found information with suggestions
        if state["ranked_documents"]:
            feedback_message = f"""{found_info}

However, this may not fully answer your question. To find more comprehensive information, you could try:

{suggestions}

Would you like to refine your search or ask a different question?"""
        else:
            feedback_message = f"""{found_info}

To improve your search, you could try:

{suggestions}

Would you like to rephrase your question with more specific terms?"""

        state["messages"].append(AIMessage(content=feedback_message))
        state["waiting_for_feedback"] = True
        logger.info("Feedback requested from user (with found info + suggestions)")
        return state

    except Exception as e:
        logger.failure(f"Feedback request failed: {e}")
        # Fallback message
        fallback_message = f"""{found_info}

Please try rephrasing your question with more specific keywords or ask about a different aspect of the topic."""
        
        state["messages"].append(AIMessage(content=fallback_message))
        state["waiting_for_feedback"] = True
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
        strategies_tried = ', '.join(state.get("search_strategies_used", ["multiple search strategies"]))
        
        no_content_msg = f"""# ❌ No Information Found

I searched the knowledge base using {strategies_tried} but couldn't find relevant information to answer your question:
> **"{current_question}"**

### Suggestions:
- Rephrase your question with different keywords
- Be more specific about what you're looking for
- Try asking about related topics that might be in the knowledge base
- Check if the information might be stored under different terminology

Would you like to try a different question?"""
        
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
        # Prepare context with source and strategy information
        context_parts = []
        for i, doc in enumerate(state["ranked_documents"], 1):
            metadata = doc["metadata"]
            source_name = metadata.get("File Name", metadata.get("file_name", f"Source {i}"))
            strategy = doc.get("retrieval_strategy", "unknown")
            score = doc.get("score", 0.0)
            
            context_parts.append(
                f"[Source {i}: {source_name} (Retrieved via {strategy}, Score: {score:.3f})]\n{doc['page_content']}"
            )

        context = "\n\n".join(context_parts)
        confidence = state["confidence_score"]
        strategies_used = ', '.join(state.get("search_strategies_used", ["multiple strategies"]))

        # Choose answer style based on confidence
        if confidence >= CONFIDENCE_THRESHOLDS["HIGH"]:
            system_msg = f"""Provide a **comprehensive, Markdown-formatted answer** using the context.
            Guidelines:
            - Answer thoroughly with clear explanations
            - Include **real-life examples** if applicable
            - Use bullet points, bold/italics, and headings for readability
            - Reference sources by name when citing information
            - Respond in {state['language']} only
            - Format your answer in Markdown
            """
        elif confidence >= CONFIDENCE_THRESHOLDS["MEDIUM"]:
            system_msg = f"""Provide a **helpful, Markdown-formatted partial answer** based on available context.
            Guidelines:
            - Answer what you CAN with clear explanations
            - Include **real-life examples** if applicable
            - Use bullet points, bold/italics, and headings for readability
            - Reference sources by name when citing information
            - End with: "This is a partial answer based on available documents."
            - Suggest asking more specific questions for areas needing clarification
            - Respond in {state['language']} only
            - Format your answer in Markdown
            """
        else:
            system_msg = f"""Provide a **limited, Markdown-formatted answer** based on available context.
            Guidelines:
            - Share only clearly available specific information
            - Reference sources for any information provided
            - Start with: "Based on available documents, I can provide limited information."
            - Strongly suggest providing more specific search terms
            - Respond in {state['language']} only
            - Format your answer in Markdown
            """

        # Add instruction to include real-life examples
        system_msg += "\n\nIf applicable, include a **real-life example** to illustrate the concept."

        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", f"""Question: {current_question}

Context with sources (retrieved using {strategies_used}):
{context}

---
**Instructions:**
- Format your answer in **Markdown**
- Use headings, bullet points, and bold/italics for clarity
- Include a real-life example if possible
""")
        ])

        response = await llm.ainvoke(answer_prompt.format_messages())
        base_answer = response.content.strip()

        # Add sources section in Markdown
        sources = format_sources_from_docs(state["ranked_documents"])
        sources_section = f"\n\n## 📚 Sources\n"
        sources_section += f"**Search Method:** {strategies_used}  \n"
        sources_section += f"**Confidence:** {confidence:.1%}  \n"
        sources_section += f"**Documents Found:** {len(state['ranked_documents'])}\n\n"
        
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

        logger.info(f"Answer generated with confidence {confidence:.2f} using {strategies_used}")
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
    """Create the enhanced RAG graph with comprehensive search and caching."""
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
    
    # Cache comprehensive document retrieval (most expensive operation)
    workflow.add_node(
        "retrieve_and_rank_documents", 
        retrieve_and_rank_documents_comprehensive,
        cache_policy=CachePolicy(
            key_func=retrieval_cache_key,
            ttl=CACHE_TTL["DOCUMENT_RETRIEVAL"]
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
    
    # Define the flow (note: removed separate rank_documents node)
    workflow.set_entry_point("process_input")
    
    # Main flow
    workflow.add_edge("process_input", "detect_language_and_optimize")
    workflow.add_edge("detect_language_and_optimize", "retrieve_and_rank_documents")
    workflow.add_edge("retrieve_and_rank_documents", "evaluate_content_quality")
    
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
    print("Enhanced RAG Graph with Comprehensive Search created successfully!")
    print(f"Graph nodes: {list(app.get_graph().nodes.keys())}")
    print(f"Cache TTL settings: {CACHE_TTL}")
    
    # Optional: Add a simple test
    async def test_comprehensive_search():
        """Test comprehensive search functionality."""
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
                "error_message": None,
                "search_strategies_used": []
            }
            
            print("Testing comprehensive search flow...")
            result = await app.ainvoke(test_state)
            print(f"Search successful! Strategies used: {result.get('search_strategies_used', [])}")
            print(f"Final documents count: {len(result.get('ranked_documents', []))}")
            print(f"Final message count: {len(result['messages'])}")
                    
        except Exception as e:
            print(f"Test failed: {e}")
    
    # Uncomment to run test
    # asyncio.run(test_comprehensive_search())