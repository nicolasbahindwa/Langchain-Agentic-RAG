
from __future__ import annotations

from typing import TypedDict, List, Optional, Dict, Any, Literal, Annotated, Tuple
from datetime import datetime
import hashlib

import asyncio
from langgraph.graph import StateGraph, END, add_messages
from langgraph.cache.memory import InMemoryCache
from langgraph.types import CachePolicy
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.checkpoint.memory import MemorySaver

from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import SearchManager
from pipeline.vector_store import VectorStoreManager
from utils.logger import get_enhanced_logger
from sentence_transformers import CrossEncoder

# ------------------------------------------------------------------
# GLOBAL COMPONENTS
# ------------------------------------------------------------------
search_manager = SearchManager()
llm_manager = LLMManager()

vector_store = VectorStoreManager(
    embedding_model='paraphrase-multilingual-MiniLM-L12-v2',
    collection_name="document_knowledge_base",
    persist_dir="./vector_storage"
)

llm = llm_manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=1500
)

llm_light = llm_manager.get_chat_model(provider=LLMProvider.OLLAMA)

logger = get_enhanced_logger("rag_graph")

# ------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------
MAX_FEEDBACK_CYCLES = 3
RETRIEVAL_COUNT = 10
RERANK_COUNT = 5


CONFIDENCE_THRESHOLDS = {
    "HIGH_CONFIDENCE": 0.7,      # → Direct answer generation
    "MEDIUM_CONFIDENCE": 0.5,    # → Partial answer with disclaimer  
    "LOW_CONFIDENCE": 0.2        # → Human feedback loop
}

RETRIEVAL_STRATEGIES = ["hybrid", "keyword", "vector"]
# ------------------------------------------------------------------
# CACHE UTILITIES
# ------------------------------------------------------------------
def generate_cache_key(*args) -> str:
    """Simple utility to generate consistent cache keys from any arguments."""
    import json
    
    def normalize(value):
        if value is None:
            return "null"
        elif isinstance(value, str):
            return value.strip()
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

def question_cache_key(state: 'RAGState') -> str:
    return generate_cache_key("rewrite_question", state.get("question", ""), 
                             state.get("feedback", ""), state.get("feedback_cycles", 0))

def retrieval_cache_key(state: 'RAGState') -> str:
    return generate_cache_key("retrieve_documents", state.get("question", ""))

def ranking_cache_key(state: 'RAGState') -> str:
    docs = state.get("documents", [])
    doc_signature = f"{len(docs)}_{docs[0].get('page_content', '')[:100]}" if docs else ""
    return generate_cache_key("rank_documents", state.get("question", ""), doc_signature)

def evaluation_cache_key(state: 'RAGState') -> str:
    ranked_docs = state.get("ranked_documents", [])
    content_signature = f"{len(ranked_docs)}_{ranked_docs[0].get('page_content', '')[:150]}" if ranked_docs else ""
    return generate_cache_key("evaluate_content", state.get("question", ""), content_signature)

# ------------------------------------------------------------------
# STATE WITH CONFIDENCE SCORING
# ------------------------------------------------------------------
class RAGState(TypedDict):
    # Core conversation history
    messages: Annotated[List[BaseMessage], add_messages]
    # User question and language
    question: str
    original_question: str
    question_language: str
    # Retrieved & ranked documents
    documents: List[dict]
    ranked_documents: List[dict]
    # Final answer
    answer: Optional[str]
    # Feedback loop bookkeeping
    feedback: Optional[str]
    feedback_cycles: int
    # Error handling
    status: str
    error: Optional[str]
    # Source list shown to user
    sources: List[str]
    # Simple loading message shown on the UI
    loading_message: str
    # Evaluation results with confidence
    evaluation_result: Optional[str]
    confidence_score: float
    # Retrieval strategy tracking
    retrieval_strategy_used: str
    retrieval_attempts: int

# ------------------------------------------------------------------
# ENHANCED UTILITIES
# ------------------------------------------------------------------
def detect_language_smart(text: str) -> Tuple[str, float]:
    """Smart language detection using lightweight LLM with confidence scoring"""
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Detect the language of the text. Respond with ONLY the language code (en, fr, es, de, etc.) followed by confidence 0-1. Format: 'language_code confidence'. Example: 'fr 0.95'"),
            ("human", "Text: {text}")
        ])
        formatted = prompt.format_messages(text=text[:200])  # Use first 200 chars for efficiency
        response = llm.ainvoke(formatted)
        
        # Parse response
        parts = response.content.strip().split()
        if len(parts) >= 2:
            lang_code = parts[0]
            confidence = float(parts[1])
            return lang_code, confidence
        else:
            return "auto", 0.5
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
        return "auto", 0.5

def fallback_retrieval(query: str, strategy: str) -> Tuple[List[dict], List[float]]:
    """Implement fallback retrieval strategies with graceful degradation"""
    try:
        if strategy == "vector_hybrid":
            docs, scores = vector_store.query_documents(
                query=query, k=RETRIEVAL_COUNT, rerank=False, search_type="hybrid"
            )
        elif strategy == "vector_similarity":
            docs, scores = vector_store.query_documents(
                query=query, k=RETRIEVAL_COUNT, rerank=False, search_type="similarity"
            )
        elif strategy == "keyword":
            # Fallback to keyword-based search if vector search fails
            docs, scores = search_manager.keyword_search(query, k=RETRIEVAL_COUNT)
        elif strategy == "query_expansion":
            # Expand query and try vector search again
            expanded_query = expand_query(query)
            docs, scores = vector_store.query_documents(
                query=expanded_query, k=RETRIEVAL_COUNT, rerank=False, search_type="hybrid"
            )
        else:
            docs, scores = [], []
            
        return docs, scores
    except Exception as e:
        logger.failure(f"Retrieval strategy {strategy} failed: {e}")
        return [], []

def expand_query(query: str) -> str:
    """Expand query using lightweight LLM for better retrieval"""
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Expand this query with 2-3 related keywords or synonyms. Keep it concise. Return only the expanded query."),
            ("human", "Query: {query}")
        ])
        formatted = prompt.format_messages(query=query)
        response = llm.ainvoke(formatted)
        return response.content.strip()
    except:
        return query  # Fallback to original query

def batch_evaluate_documents(question: str, docs: List[dict], language: str) -> Tuple[str, float, str]:
    """Batched evaluation combining relevance, completeness, and confidence in single call"""
    if not docs:
        return "INSUFFICIENT", 0.0, "No documents available"
    
    try:
        context = format_docs(docs)
        language_instruction = f"Respond in {language}" if language != "auto" else ""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Evaluate documents for answering the question. {language_instruction}
            
            Provide evaluation in this EXACT format:
            CLASSIFICATION: [COMPLETE/PARTIAL/INSUFFICIENT]
            CONFIDENCE: [0.0-1.0]
            REASONING: [Brief explanation]
            
            Classification rules:
            - COMPLETE (0.8-1.0): Context fully answers the question with specific information
            - PARTIAL (0.3-0.7): Context has some relevant information but incomplete  
            - INSUFFICIENT (0.0-0.3): Context lacks relevant information or only general mentions
            
            Be precise with confidence scoring."""),
            ("human", "Question: {question}\n\nContext:\n{context}")
        ])
        
        formatted = prompt.format_messages(question=question, context=context)
        response = llm.ainvoke(formatted)
        
        # Parse structured response
        lines = response.content.strip().split('\n')
        classification = "INSUFFICIENT"
        confidence = 0.0
        reasoning = "Evaluation failed"
        
        for line in lines:
            if line.startswith("CLASSIFICATION:"):
                classification = line.split(":", 1)[1].strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except:
                    confidence = 0.0
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
        
        return classification, confidence, reasoning
        
    except Exception as e:
        logger.failure(f"Batch evaluation failed: {e}")
        return "INSUFFICIENT", 0.0, f"Evaluation error: {e}"

def set_loading_message(state: RAGState, text: str) -> RAGState:
    """Update loading message and log"""
    state["loading_message"] = text
    logger.info(text)
    return state

def format_docs(docs: List[dict]) -> str:
    """Format documents for internal prompts"""
    if not docs:
        return "No relevant documents found."

    return "\n\n".join(
        f"📄 Document {idx + 1} ({d['metadata'].get('source', 'Unknown')}):\n"
        f"{d['page_content'][:300]}{'...' if len(d['page_content']) > 300 else ''}"
        for idx, d in enumerate(docs)
    )

def reset_state_for_next_question(state: RAGState) -> None:
    """Reset state for next question while preserving messages - COMPREHENSIVE RESET"""
    state["question"] = ""
    state["original_question"] = ""
    state["question_language"] = ""
    state["documents"] = []
    state["ranked_documents"] = []
    state["feedback"] = None
    state["feedback_cycles"] = 0
    state["sources"] = []
    state["error"] = None
    state["evaluation_result"] = None
    state["status"] = ""
    state["loading_message"] = ""
    # Clear any waiting flags
    state.pop("waiting_for_feedback", None)
    logger.info("State reset for new question")

# ------------------------------------------------------------------
# NODES
# ------------------------------------------------------------------
async def rewrite_question(state: RAGState) -> RAGState:
    """Entry point - optimize question and detect language efficiently"""
    # Set defaults
    defaults = {
        "messages": [], "question": "", "original_question": "", "question_language": "",
        "documents": [], "ranked_documents": [], "answer": None, "feedback": None,
        "feedback_cycles": 0, "status": "", "error": None, "sources": [],
        "loading_message": "", "evaluation_result": None, "confidence_score": 0.0,
        "retrieval_strategy_used": "", "retrieval_attempts": 0
    }
    state = {**defaults, **state}
    
    # Handle new questions vs feedback with smart detection
    if not state["question"] and state["feedback_cycles"] == 0:
        latest_human_message = None
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage) and m.content.strip():
                latest_human_message = m.content.strip()
                break
        
        if latest_human_message:
            # Check if this is a new question
            if state.get("original_question") and latest_human_message != state["original_question"]:
                logger.info(f"NEW QUESTION detected - resetting state")
                reset_state_for_next_question(state)
                state["question"] = state["original_question"] = latest_human_message
            else:
                state["question"] = state["original_question"] = latest_human_message
                
    if state["feedback_cycles"] == 0:
        set_loading_message(state, "Analyzing question and detecting language...")
        # Smart language detection
        lang_code, lang_confidence = detect_language_smart(state["question"])
        state["question_language"] = lang_code
        logger.info(f"Detected language: {lang_code} (confidence: {lang_confidence:.2f})")
    else:
        set_loading_message(state, f"Refining search based on feedback (cycle {state['feedback_cycles']})...")
                
    if not state["question"]:
        state["status"] = "error"
        state["error"] = "No question provided"
        return set_loading_message(state, "Error: no question detected.")

    # Optimize question for search
    try:
        language_instruction = f"Respond in {state['question_language']}" if state['question_language'] != "auto" else ""
        
        if state["feedback_cycles"] == 0:
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"Rewrite this question to make it clearer and more searchable. {language_instruction} Return ONLY the rewritten question."),
                ("human", "Question: {question}")
            ])
            formatted = prompt.format_messages(question=state["question"])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"Incorporate feedback to create a better search query. {language_instruction} Return ONLY the rewritten question."),
                ("human", "Original: {original}\nCurrent: {current}\nFeedback: {feedback}\n\nNew search query:")
            ])
            formatted = prompt.format_messages(
                original=state["original_question"],
                current=state["question"],
                feedback=state["feedback"]
            )

        response = await llm.ainvoke(formatted)  # Use light LLM for efficiency
        rewritten = response.content.strip()
        state["question"] = rewritten
        state["status"] = "retrieve_documents"  # SIMPLIFIED: Go directly to combined step
        
        set_loading_message(state, f"Optimized question → {rewritten}")
        return state
        
    except Exception as e:
        logger.failure(f"Question rewriting failed: {e}")
        # Graceful degradation: use original question
        state["status"] = "retrieve_documents"
        return set_loading_message(state, "Using original question for search...")

 

async def check_existing_documents(state: RAGState) -> RAGState:
    """Smart check if existing documents can answer the current question - PRECISE CHECKING"""
    set_loading_message(state, "Checking existing documents...")
    
    # If no existing documents, need to retrieve
    if not state.get("ranked_documents") and not state.get("documents"):
        state["status"] = "retrieve_documents"
        return set_loading_message(state, "No existing documents - retrieving new content...")
    
    # For NEW questions (feedback_cycles == 0), be more conservative about reusing docs
    # For FEEDBACK iterations, be more liberal about reusing docs
    is_new_question = state.get("feedback_cycles", 0) == 0
    
    # Use ranked docs if available, otherwise use raw documents
    docs_to_check = state.get("ranked_documents") or state.get("documents", [])[:RERANK_COUNT]
    
    if not docs_to_check:
        state["status"] = "retrieve_documents"
        return set_loading_message(state, "No documents to check - retrieving...")
    
    try:
        # For new questions, check if documents are topically relevant first
        if is_new_question:
            # Quick topical relevance check for new questions
            sample_content = " ".join([doc.get("page_content", "")[:200] for doc in docs_to_check[:3]])
            language_instruction = f"Respond in the same language as the question: {state['question_language']}" if state['question_language'] != "auto" else ""
            
            relevance_prompt = ChatPromptTemplate.from_messages([
                ("system", f"Are the documents topically relevant to the question? {language_instruction} Answer only 'RELEVANT' or 'NOT_RELEVANT'."),
                ("human", "Question: {question}\n\nDocument content sample:\n{content}")
            ])
            formatted = relevance_prompt.format_messages(question=state["question"], content=sample_content)
            response = await llm.ainvoke(formatted)
            
            if "NOT_RELEVANT" in response.content.upper():
                state["status"] = "retrieve_documents"
                return set_loading_message(state, "Existing documents not topically relevant - retrieving fresh content...")
        
        # Now check if documents can provide meaningful information for the question
        context = format_docs(docs_to_check)
        language_instruction = f"Respond in the same language as the question: {state['question_language']}" if state['question_language'] != "auto" else ""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Evaluate if the context contains meaningful information to answer the question. {language_instruction}
            
            Be PRECISE:
            - Answer 'YES' only if context contains specific information that can help answer the question (fully or partially)
            - Answer 'NO' if context only mentions general topics without specific relevant information
            
            IMPORTANT: General mentions of topics without specific details should be 'NO'."""),
            ("human", "Question: {question}\n\nContext:\n{context}")
        ])
        formatted = prompt.format_messages(question=state["question"], context=context)
        response = llm.ainvoke(formatted)
        result = response.content.strip().upper()
        
        if "YES" in result:
            # Existing documents sufficient - proceed to evaluation
            state["status"] = "evaluate_content"
            return set_loading_message(state, "Existing documents contain relevant information - proceeding to evaluation...")
        else:
            # Need fresh retrieval
            state["status"] = "retrieve_documents"
            return set_loading_message(state, "Existing documents lack specific information - retrieving new content...")
            
    except Exception as e:
        logger.failure(f"Check existing documents failed: {e}")
        state["status"] = "retrieve_documents"
        return set_loading_message(state, "Check failed - retrieving new documents")

async def retrieve_documents(state: RAGState) -> RAGState:
    """Retrieve documents from vector store"""
    set_loading_message(state, "Searching knowledge base...")
    try:
        docs, scores =  vector_store.query_documents(
            query=state["question"],
            k=RETRIEVAL_COUNT,
            rerank=False,
            search_type="hybrid"
        )
        state["documents"] = [
            {"page_content": d.page_content, "metadata": d.metadata, "score": s}
            for d, s in zip(docs, scores)
        ]
        state["status"] = "rank_documents"
        set_loading_message(state, f"Retrieved {len(state['documents'])} documents")
        return state
    except Exception as e:
        logger.failure(f"Retrieve failed: {e}")
        state["status"] = "error"
        state["error"] = f"Retrieval error: {e}"
        return set_loading_message(state, "Error while retrieving documents.")
def rank_documents(state: RAGState) -> RAGState:
    """Re-rank documents by relevance"""
    set_loading_message(state, "Ranking results by relevance...")
    if not state["documents"]:
        state["status"] = "evaluate_content"
        return set_loading_message(state, "No documents to rank")

    try:
        reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        pairs = [(state["question"], d["page_content"]) for d in state["documents"]]
        scores = reranker.predict(pairs)
        
        ranked = sorted(zip(state["documents"], scores), key=lambda x: x[1], reverse=True)
        state["ranked_documents"] = [doc for doc, _ in ranked[:RERANK_COUNT]]

        # Build unique source list
        seen = set()
        sources = []
        for d in state["ranked_documents"]:
            path = d["metadata"].get("source", "Unknown")
            if path not in seen:
                seen.add(path)
                sources.append({
                    "path": path,
                    "file_name": d["metadata"].get("File Name", "Unknown file"),
                    "author": d["metadata"].get("Author", "Unknown"),
                    "creation_date": d["metadata"].get("Creationdate", "Unknown")
                })
        state["sources"] = sources
        state["status"] = "evaluate_content"
        set_loading_message(state, f"Top {len(state['ranked_documents'])} documents selected")
        return state
    except Exception as e:
        logger.failure(f"Rank failed: {e}")
        state["status"] = "error"
        state["error"] = f"Ranking error: {e}"
        return set_loading_message(state, "Error while ranking documents.")

async def evaluate_content(state: RAGState) -> RAGState:
    """Evaluate if content can answer the question - PRECISE LOGIC"""
    set_loading_message(state, "Evaluating content quality...")
    if not state["ranked_documents"]:
        state["status"] = "request_feedback"
        return set_loading_message(state, "No content found - requesting feedback")

    try:
        context = format_docs(state["ranked_documents"])
        language_instruction = f"Respond in the same language as the question: {state['question_language']}" if state['question_language'] != "auto" else ""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Evaluate if the context contains relevant information to answer the question. {language_instruction}
            
            Be PRECISE in your evaluation:
            
            - 'COMPLETE' if context fully answers the question with specific information
            - 'PARTIAL' if context contains some relevant information that partially addresses the question (can give meaningful partial answer)
            - 'INSUFFICIENT' if context contains no relevant information or only mentions topics without answering the specific question
            
            IMPORTANT: If the context talks about general topics but doesn't contain the specific information asked for, classify as 'INSUFFICIENT', not 'PARTIAL'.
            
            Then explain what specific information was found and what's missing."""),
            ("human", "Question: {question}\n\nContext:\n{context}")
        ])
        formatted = prompt.format_messages(question=state["question"], context=context)
        response = await llm.ainvoke(formatted)
        evaluation = response.content.strip()
        
        state["evaluation_result"] = evaluation
        
        # PRECISE ROUTING: Only truly relevant content goes to answer generation
        if evaluation.startswith("COMPLETE"):
            state["status"] = "generate_answer"
            return set_loading_message(state, "Content fully answers question - generating response...")
        elif evaluation.startswith("PARTIAL"):
            # Double-check: is there actually meaningful content to work with?
                state["status"] = "generate_answer"
                return set_loading_message(state, "Partial answer found - generating response with suggestions...")
           
        else:
            # INSUFFICIENT - go to human feedback
            state["status"] = "request_feedback"
            return set_loading_message(state, "No relevant content found - requesting guidance...")
            
    except Exception as e:
        logger.failure(f"Evaluate failed: {e}")
        state["status"] = "request_feedback"
        return set_loading_message(state, "Evaluation failed - requesting feedback")


async def request_feedback(state: RAGState) -> RAGState:
    """Request user feedback for insufficient content - PRECISE FEEDBACK REQUESTS"""
    set_loading_message(state, "Preparing feedback request...")

    # Get evaluation details
    evaluation = state.get("evaluation_result", "No evaluation available")
    found_content = format_docs(state["ranked_documents"]) if state["ranked_documents"] else "No documents found"
    
    language_instruction = f"Respond in the same language as the original question: {state['question_language']}" if state['question_language'] != "auto" else ""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""The search did not find sufficient information to answer the user's question. {language_instruction}
        
        Based on what was found, help the user by:
        1. Briefly explaining what information was found (if any)
        2. Asking for more specific keywords, different phrasing, or clarification
        3. Suggesting what additional details might help improve the search
        
        Be helpful and constructive - guide them toward a better search strategy."""),
        ("human", """Question: {question}
        
        Search evaluation: {evaluation}
        
        Content found: {content}
        
        Help the user refine their search.""")
    ])
    
    formatted = prompt.format_messages(
        question=state["question"],
        evaluation=evaluation,
        content=found_content[:500] + "..." if len(found_content) > 500 else found_content
    )
    response = await llm.ainvoke(formatted)
    feedback_request = response.content

    # Add to conversation
    state["messages"].append(AIMessage(content=feedback_request))
    state["waiting_for_feedback"] = True
    state["feedback"] = None
    
    return state

def process_feedback(state: RAGState) -> RAGState:
    """Process user feedback"""
    set_loading_message(state, "Processing your feedback...")
    
    # Extract feedback from latest human message
    feedback = state.get("feedback")
    if not feedback:
        for message in reversed(state["messages"]):
            if isinstance(message, HumanMessage):
                feedback = message.content.strip()
                break
                
    if not feedback:
        state["status"] = "generate_answer"
        state["waiting_for_feedback"] = False
        return set_loading_message(state, "No feedback found - proceeding with available content")

    # Process commands
    lower_feedback = feedback.lower().strip()
    
    # Stop commands
    if lower_feedback in {"stop", "abort", "cancel", "quit", "end", "exit"}:
        state["status"] = "end"
        state["waiting_for_feedback"] = False
        return set_loading_message(state, "Request cancelled")
    
    # Proceed commands
    if lower_feedback in {"proceed", "continue", "yes", "go", "ok", "okay", "fine"}:
        state["status"] = "generate_answer"
        state["waiting_for_feedback"] = False
        return set_loading_message(state, "Proceeding with current content...")
    
    # Check max cycles
    if state.get("feedback_cycles", 0) >= MAX_FEEDBACK_CYCLES:
        state["status"] = "generate_answer"
        state["waiting_for_feedback"] = False
        return set_loading_message(state, "Max feedback cycles reached - generating answer")
    
    # Real feedback - increment cycle and rewrite question
    state["feedback_cycles"] = state.get("feedback_cycles", 0) + 1
    state["status"] = "rewrite_question"
    state["waiting_for_feedback"] = False
    state["feedback"] = feedback
    
    return set_loading_message(state, f"Incorporating feedback (cycle {state['feedback_cycles']})...")

async def generate_answer(state: RAGState) -> RAGState:
    """Generate final answer with confidence-based approach and enhanced source citations"""
    set_loading_message(state, "Generating answer...")
    
    if not state["ranked_documents"]:
        # Graceful degradation: should not happen with new flow, but handle it
        state["status"] = "request_feedback"
        return set_loading_message(state, "No documents available - requesting guidance...")

    try:
        # Prepare enhanced context with source details
        context_parts = []
        source_details = []
        
        for idx, doc in enumerate(state["ranked_documents"], 1):
            metadata = doc["metadata"]
            file_name = metadata.get("File Name", metadata.get("file_name", "Unknown file"))
            source_path = metadata.get("source", "Unknown source")
            author = metadata.get("Author", metadata.get("author", ""))
            creation_date = metadata.get("Creationdate", metadata.get("creation_date", ""))
            
            source_ref = f"Source {idx}: {file_name}"
            if author:
                source_ref += f" (Author: {author})"
            if creation_date:
                source_ref += f" (Created: {creation_date})"
            
            source_details.append({
                "index": idx,
                "file_name": file_name,
                "full_reference": source_ref,
                "path": source_path
            })
            
            context_parts.append(f"{source_ref}\nContent: {doc['page_content']}")

        context = "\n\n".join(context_parts)
        
        # Confidence-based answer generation
        confidence = state.get("confidence_score", 0.0)
        classification = state.get("evaluation_result", "PARTIAL")
        language = state.get("question_language", "auto")
        language_instruction = f"Answer in {language}" if language != "auto" else ""
        
        if confidence >= CONFIDENCE_THRESHOLDS["HIGH_CONFIDENCE"]:
            # High confidence - comprehensive answer
            system_prompt = f"""Provide a comprehensive answer using the available context. {language_instruction}
            
            Guidelines:
            1. Answer the question thoroughly based on the context
            2. Cite specific document names when referencing information
            3. Be detailed and specific
            4. Use authoritative tone since confidence is high"""
            
        elif confidence >= CONFIDENCE_THRESHOLDS["MEDIUM_CONFIDENCE"]:
            # Medium confidence - partial answer with clear limitations
            system_prompt = f"""Provide a helpful partial answer based on available context. {language_instruction}
            
            Guidelines:
            1. Answer what you CAN based on the context
            2. Cite specific document names when referencing information
            3. At the end, clearly state: "This is a partial answer based on available documents"
            4. Suggest asking more specific questions about areas that need clarification
            5. Be helpful but acknowledge limitations"""
            
        else:
            # Low confidence - minimal answer with strong disclaimers
            system_prompt = f"""Provide what limited information is available from the context. {language_instruction}
            
            Guidelines:
            1. Share only what specific information is clearly available
            2. Cite document names for any information provided
            3. Clearly state: "Based on available documents, I can only provide limited information"
            4. Strongly suggest the user provide more specific search terms or clarify their question"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Question: {question}\n\nSources and content:\n{context}\n\nConfidence: {confidence:.2f}")
        ])
        
        formatted = prompt.format_messages(
            question=state["question"], 
            context=context,
            confidence=confidence
        )
        response = await llm.ainvoke(formatted)
        answer = response.content.strip()
        
        # Enhanced sources section
        sources_section = f"\n\n📋 **Sources Used** (Search confidence: {confidence:.2f}):\n"
        for source in source_details:
            sources_section += f"• {source['full_reference']}\n"
            if source['path'] != "Unknown source":
                sources_section += f"  Path: {source['path']}\n"
        
        # Add retrieval strategy info for debugging
        if state.get("retrieval_strategy_used"):
            sources_section += f"\n🔍 Search method: {state['retrieval_strategy_used']}"
            if state.get("retrieval_attempts", 0) > 1:
                sources_section += f" (after {state['retrieval_attempts']} attempts)"
        
        final_answer = answer + sources_section
        state["answer"] = final_answer
        state["status"] = "complete"
        
        reset_state_for_next_question(state)
        set_loading_message(state, "Answer ready")
        return state
        
    except Exception as e:
        logger.failure(f"Answer generation failed: {e}")
        # Graceful degradation
        state["status"] = "request_feedback"
        state["error"] = f"Generation error: {e}"
        return set_loading_message(state, "Error generating answer - requesting guidance...")

 

# ------------------------------------------------------------------
# ROUTING FUNCTIONS
# ------------------------------------------------------------------
def route_after_check(state: RAGState) -> Literal["retrieve_documents", "evaluate_content"]:
    """Route after checking existing documents"""
    return "evaluate_content" if state["status"] == "evaluate_content" else "retrieve_documents"

def route_after_evaluation(state: RAGState) -> Literal["generate_answer", "request_feedback"]:
    """Route after content evaluation"""
    return "generate_answer" if state["status"] == "generate_answer" else "request_feedback"

def route_after_feedback(state: RAGState) -> Literal["rewrite_question", "generate_answer", "END"]:
    """Route after processing feedback"""
    status = state.get("status", "END")
    if status == "rewrite_question":
        return "rewrite_question"
    elif status == "generate_answer":
        return "generate_answer"
    else:
        return "END"

# ------------------------------------------------------------------
# GRAPH BUILDER
# ------------------------------------------------------------------
def build_rag_graph():
    """Build the corrected RAG graph"""
    workflow = StateGraph(RAGState)

    # Cache settings
    CACHE_TTLS = {
        "rewrite_question": 3600,
        "retrieve_documents": 1800,
        "rank_documents": 900,
        "evaluate_content": 600,
    }

    # Add nodes with caching for expensive operations
    workflow.add_node(
        "rewrite_question", 
        rewrite_question,
        cache_policy=CachePolicy(key_func=question_cache_key, ttl=CACHE_TTLS["rewrite_question"])
    )
    
    workflow.add_node("check_existing_documents", check_existing_documents)
    
    workflow.add_node(
        "retrieve_documents", 
        retrieve_documents,
        cache_policy=CachePolicy(key_func=retrieval_cache_key, ttl=CACHE_TTLS["retrieve_documents"])
    )
    
    workflow.add_node(
        "rank_documents", 
        rank_documents,
        cache_policy=CachePolicy(key_func=ranking_cache_key, ttl=CACHE_TTLS["rank_documents"])
    )
    
    workflow.add_node(
        "evaluate_content", 
        evaluate_content,
        cache_policy=CachePolicy(key_func=evaluation_cache_key, ttl=CACHE_TTLS["evaluate_content"])
    )

    # Interactive nodes (no caching)
    workflow.add_node("request_feedback", request_feedback)
    workflow.add_node("process_feedback", process_feedback)
    workflow.add_node("generate_answer", generate_answer)

    # Define flow
    workflow.set_entry_point("rewrite_question")
    
    # CORRECTED FLOW:
    workflow.add_edge("rewrite_question", "check_existing_documents")
    
    workflow.add_conditional_edges(
        "check_existing_documents",
        route_after_check,
        {
            "retrieve_documents": "retrieve_documents",
            "evaluate_content": "evaluate_content"
        }
    )
    
    workflow.add_edge("retrieve_documents", "rank_documents")
    workflow.add_edge("rank_documents", "evaluate_content")
    
    workflow.add_conditional_edges(
        "evaluate_content",
        route_after_evaluation,
        {
            "generate_answer": "generate_answer",
            "request_feedback": "request_feedback"
        }
    )
    
    workflow.add_edge("request_feedback", "process_feedback")
    
    workflow.add_conditional_edges(
        "process_feedback",
        route_after_feedback,
        {
            "rewrite_question": "rewrite_question",
            "generate_answer": "generate_answer",
            "END": END
        }
    )
    
    workflow.add_edge("generate_answer", END)

    return workflow.compile(cache=InMemoryCache(), interrupt_after=["request_feedback"])

# Initialize the graph
app = build_rag_graph()

def clear_cache():
    """Clear cache by rebuilding the app"""
    global app
    app = build_rag_graph()
    logger.info("Cache cleared")