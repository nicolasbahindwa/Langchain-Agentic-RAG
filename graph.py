from __future__ import annotations

from typing import TypedDict, List, Optional, Dict, Any, Literal, Annotated
from datetime import datetime

from langgraph.graph import StateGraph, END, add_messages
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

# ------------------------------------------------------------------
# STATE
# ------------------------------------------------------------------
class RAGState(TypedDict):
    # Core conversation history
    messages: Annotated[List[BaseMessage], add_messages]
    # User question
    question: str
    original_question: str
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

# ------------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------------
def set_loading_message(state: RAGState, text: str) -> RAGState:
    """
    Convenience helper: update the user-facing loading message
    and log the same text at INFO level for the backend log.
    """
    state["loading_message"] = text
    logger.info(text)
    return state

def format_docs(docs: List[dict]) -> str:
    """
    Converts a list of document dicts into a concise human-readable block.
    Used only for internal prompts, not for the final answer.
    """
    if not docs:
        return "No relevant documents found."

    return "\n\n".join(
        f"📄 Document {idx + 1} ({d['metadata'].get('source', 'Unknown')}):\n"
        f"{d['page_content'][:300]}{'...' if len(d['page_content']) > 300 else ''}"
        for idx, d in enumerate(docs)
    )

# ------------------------------------------------------------------
# NODES
# ------------------------------------------------------------------
def rewrite_question(state: RAGState) -> RAGState:
    """
    Entry point.
    - On first run: optimizes the user's question for retrieval.
    - On feedback loops: incorporates user feedback into a new search query.
    """
    # Ensure defaults FIRST before accessing any keys
    defaults = {
        "messages": [],
        "question": "",
        "original_question": "",
        "documents": [],
        "ranked_documents": [],
        "answer": None,
        "feedback": None,
        "feedback_cycles": 0,
        "status": "",
        "error": None,
        "sources": [],
        "loading_message": ""
    }
    state = {**defaults, **state}
    
    # FIXED: Get the LATEST human message, not the first one
    if not state["question"] and state["feedback_cycles"] == 0:
        # Reverse the messages to get the most recent human message
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage) and m.content.strip():
                state["question"] = state["original_question"] = m.content.strip()
                break
                
    if state["feedback_cycles"] == 0:
        set_loading_message(state, "Optimising your question…")
    else:
        set_loading_message(state, f"Rewriting question based on feedback (cycle {state['feedback_cycles']})…")
                
    if not state["question"] and not state["original_question"]:
        state["status"] = "error"
        state["error"] = "No question provided"
        return set_loading_message(state, "Error: no question detected.")

    # Build prompt based on whether this is first run or feedback loop
    if state["feedback_cycles"] == 0:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Rewrite the question to make it clearer and more searchable. "
             "Return ONLY the rewritten question."),
            ("human", "Original question: {question}")
        ])
        formatted = prompt.format_messages(question=state["question"])
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "The user provided feedback about the search results. "
             "Incorporate this feedback to create a better search query. "
             "Return ONLY the rewritten question."),
            ("human",
             "Original question: {original}\n"
             "Previous search: {current}\n"
             "User feedback: {feedback}\n\n"
             "Create a new search query:")
        ])
        formatted = prompt.format_messages(
            original=state["original_question"],
            current=state["question"],
            feedback=state["feedback"]
        )

    try:
        response = llm.invoke(formatted)
        rewritten = response.content.strip()
        state["question"] = rewritten
        state["status"] = "retrieve_documents"
        
        if state["feedback_cycles"] == 0:
            set_loading_message(state, f"Rewrote question → {rewritten}")
        else:
            set_loading_message(state, f"New search query → {rewritten}")
            
        return state
    except Exception as e:
        logger.error(f"Error in rewrite_question: {e}")
        state["status"] = "error"
        state["error"] = f"Question rewriting failed: {e}"
        return set_loading_message(state, "Error rewriting question")


def retrieve_documents(state: RAGState) -> RAGState:
    """
    Pull the top-k documents from the vector store using hybrid search.
    """
    set_loading_message(state, "Searching knowledge base…")
    try:
        docs, scores = vector_store.query_documents(
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
        logger.failure("Retrieve failed")
        state["status"] = "error"
        state["error"] = f"Retrieval error: {e}"
        return set_loading_message(state, "Error while retrieving documents.")

def rank_documents(state: RAGState) -> RAGState:
    """
    Re-ranks retrieved documents via cross-encoder and extracts unique source list
    that will be shown to the user in the final answer.
    """
    set_loading_message(state, "Ranking results by relevance…")
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
        logger.failure("Rank failed")
        state["status"] = "error"
        state["error"] = f"Ranking error: {e}"
        return set_loading_message(state, "Error while ranking documents.")

def evaluate_content(state: RAGState) -> RAGState:
    """
    Quick yes/no check: do the ranked documents actually answer the question?
    Drives the conditional edge to either ‘generate_answer’ or ‘request_feedback’.
    """
    set_loading_message(state, "Checking content quality…")
    if not state["ranked_documents"]:
        state["status"] = "request_feedback"
        return set_loading_message(state, "No relevant content found – requesting feedback")

    try:
        context = format_docs(state["ranked_documents"])
        prompt = [
            ("system",
             "Answer only 'yes' or 'no'. Does the context answer the question?"),
            ("human", f"Question: {state['question']}\n\nContext:\n{context}")
        ]
        response = llm.invoke(prompt)
        has_answer = "yes" in response.content.lower()

        if has_answer:
            state["status"] = "generate_answer"
            return set_loading_message(state, "Good content – generating answer…")
        if state["feedback_cycles"] >= MAX_FEEDBACK_CYCLES:
            state["status"] = "generate_answer"
            return set_loading_message(state, "Max loops reached – generating best-effort answer…")

        state["status"] = "request_feedback"
        return set_loading_message(state, "Content insufficient – asking user for help")
    except Exception as e:
        logger.failure("Evaluate failed")
        state["status"] = "request_feedback"
        return set_loading_message(state, "Evaluation failed – requesting user feedback")


def request_feedback(state: RAGState) -> RAGState:
    """
    Build a feedback request and set waiting flag
    """
    set_loading_message(state, "Waiting for user feedback…")

    summary = format_docs(state["ranked_documents"]) if state["ranked_documents"] \
        else "I did not find any documents that seem relevant."

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Briefly summarise what you found and ask the user for clarification "
         "or for permission to proceed with the current documents."),
        ("human", f"Question: {state['question']}\n\nSummary:\n{summary}")
    ])
    
    formatted_prompt = prompt.format_messages(
        question=state["question"],
        summary=summary
    )
    response = llm.invoke(formatted_prompt)
    feedback_text = response.content

    # Append the agent's question to the chat
    state["messages"].append(AIMessage(content=feedback_text))
    
    # Set flags
    state["waiting_for_feedback"] = True
    state["feedback"] = None  # Reset any previous feedback
    
    return state


def process_feedback(state: RAGState) -> RAGState:
    """
    Process feedback - now checks both explicit feedback field and messages
    """
    set_loading_message(state, "Processing your feedback...")
    
    # Method 1: Check explicit feedback field first
    feedback = state.get("feedback")
    
    # Method 2: If no explicit feedback, extract from latest human message
    if not feedback:
        for message in reversed(state["messages"]):
            if isinstance(message, HumanMessage):
                feedback = message.content.strip()
                logger.info(f"DEBUG: Found feedback in messages = '{feedback}'")
                break
                
    if not feedback:
        logger.warning("DEBUG: No feedback found")
        state["status"] = "generate_answer"
        state["waiting_for_feedback"] = False
        return set_loading_message(state, "No feedback found - proceeding with current content")

    # Process feedback - check for commands first
    lower_feedback = feedback.lower().strip()
    logger.info(f"DEBUG: Processing feedback = '{lower_feedback}'")
    
    # Check for stop commands
    stop_commands = {"stop", "abort", "cancel", "quit", "end", "exit"}
    if lower_feedback in stop_commands:
        state["status"] = "end"
        state["waiting_for_feedback"] = False
        return set_loading_message(state, "Request aborted by user")
    
    # Check for proceed commands
    proceed_commands = {"proceed", "continue", "yes", "go", "ok", "okay", "fine"}
    if lower_feedback in proceed_commands:
        state["status"] = "generate_answer"
        state["waiting_for_feedback"] = False
        return set_loading_message(state, "Proceeding with current content…")
    
    # Check if we've exceeded max cycles
    current_cycles = state.get("feedback_cycles", 0)
    if current_cycles >= MAX_FEEDBACK_CYCLES:
        state["status"] = "generate_answer"
        state["waiting_for_feedback"] = False
        return set_loading_message(state, "Max feedback cycles reached - proceeding with current content")
    
    # If we get here, it's actual feedback content - trigger rewrite
    state["feedback_cycles"] = current_cycles + 1
    state["status"] = "rewrite_question"
    state["waiting_for_feedback"] = False
    
    # Store the feedback for the rewrite_question node
    state["feedback"] = feedback
    
    return set_loading_message(state, f"Incorporating your feedback (cycle {state['feedback_cycles']})…")


def route_after_feedback(state: RAGState) -> str:
    status = state.get("status", "END").lower()   # normalise
    if status == "rewrite_question":
        return "rewrite_question"
    elif status == "generate_answer":
        return "generate_answer"
    else:
        return "END"   # keep upper-case
    

def reset_state_for_next_question(state: RAGState) -> None:
    """
    ADDED: Simple state reset after answering a question.
    Clears everything except messages so the next question starts fresh.
    """
    state["question"] = ""
    state["original_question"] = ""
    state["documents"] = []
    state["ranked_documents"] = []
    state["feedback"] = None
    state["feedback_cycles"] = 0
    state["waiting_for_feedback"] = False
    state["sources"] = []
    state["error"] = None

def generate_answer(state: RAGState) -> RAGState:
    """
    Produces the final answer, quoting real file names so users can verify sources.
    FIXED: Resets state after generating answer so next question starts fresh.
    """
    set_loading_message(state, "Preparing final answer…")
    if not state["ranked_documents"]:
        state["answer"] = "I couldn't find any relevant documents to answer your question."
        state["status"] = "complete"
        # ADDED: Reset state for next question
        reset_state_for_next_question(state)
        return set_loading_message(state, "Done – no documents found")

    try:
        context_parts = []
        refs = []
        for idx, doc in enumerate(state["ranked_documents"], 1):
            path = doc["metadata"].get("source", "Unknown")
            name = doc["metadata"].get("File Name", "Unknown file")
            ref = f"Source {idx}: {name} (Path: {path})"
            refs.append(ref)
            context_parts.append(f"{ref}\n{doc['page_content']}")

        context = "\n\n".join(context_parts)
        prompt = [
            ("system",
             "Answer the question using the provided context. "
             "Always cite the document/file names, not just 'Source 1, 2, etc.' "
             "If context is insufficient, say so."),
            ("human", f"Question: {state['question']}\n\nContext:\n{context}")
        ]

        response = llm.invoke(prompt)
        answer = response.content.strip()
        sources_section = "\n\nSources referenced:\n" + "\n".join(refs)
        state["answer"] = answer + sources_section
        state["status"] = "complete"
        
        # ADDED: Reset state for next question
        reset_state_for_next_question(state)
        
        set_loading_message(state, "Answer ready")
        return state
    except Exception as e:
        logger.error(f"Generate answer failed: {e}")
        state["status"] = "error"
        state["error"] = f"Generation error: {e}"
        return set_loading_message(state, "Error while generating the answer")

# ------------------------------------------------------------------
# CONDITIONAL EDGE HELPERS
# ------------------------------------------------------------------
def decide_next_step(state: RAGState) -> Literal["generate_answer", "request_feedback"]:
    """Routing function after evaluation."""
    return "generate_answer" if state["status"] == "generate_answer" else "request_feedback"

 

# ------------------------------------------------------------------
# GRAPH BUILDER
# ------------------------------------------------------------------
def build_rag_graph():
    workflow = StateGraph(RAGState)

    # Add all nodes
    workflow.add_node("rewrite_question", rewrite_question)
    workflow.add_node("retrieve_documents", retrieve_documents)
    workflow.add_node("rank_documents", rank_documents)
    workflow.add_node("evaluate_content", evaluate_content)
    workflow.add_node("request_feedback", request_feedback)
    workflow.add_node("process_feedback", process_feedback)
    workflow.add_node("generate_answer", generate_answer)

    # Entry point
    workflow.set_entry_point("rewrite_question")

    # Main flow
    workflow.add_edge("rewrite_question", "retrieve_documents")
    workflow.add_edge("retrieve_documents", "rank_documents")
    workflow.add_edge("rank_documents", "evaluate_content")

    # Conditional edge after evaluation
    workflow.add_conditional_edges(
        "evaluate_content", 
        decide_next_step,
        {
            "generate_answer": "generate_answer",
            "request_feedback": "request_feedback"
        }
    )
    
    # FIXED: Simple edge from request_feedback to process_feedback
    workflow.add_edge("request_feedback", "process_feedback")
    
    # Conditional edges after processing feedback
    workflow.add_conditional_edges(
        "process_feedback",
        route_after_feedback,
        {
            "rewrite_question": "rewrite_question",
            "generate_answer": "generate_answer",
            "END": END
        }
    )

    # Final step
    workflow.add_edge("generate_answer", END)

    # Interrupt after request_feedback to wait for human input
    return workflow.compile(interrupt_after=["request_feedback"])

# Instantiate once
app = build_rag_graph()


"""
Test script to properly test the feedback flow
"""


def test_feedback_flow():
    """Test the complete feedback flow properly"""
    
    # 1. Start initial query
    initial_input = {
        "messages": [HumanMessage(content="what the meaning of the 1st article of the constitution of the Dominican Republic?")],
        "question": "",
        "original_question": "",
        "documents": [],
        "ranked_documents": [],
        "answer": None,
        "feedback": None,
        "feedback_cycles": 0,
        "status": "",
        "error": None,
        "sources": [],
        "loading_message": ""
    }
    
    thread_id = "test-thread-123"
    config = {"configurable": {"thread_id": thread_id}}
    
    print("=== INITIAL RUN ===")
    # This should run until it hits the interrupt after request_feedback
    result = app.invoke(initial_input, config=config)
    print(f"Result after initial run: {result['loading_message']}")
    
    # 2. Simulate user providing feedback
    user_feedback = "Please search for information about constitutional articles and their interpretation"
    
    print(f"\n=== ADDING FEEDBACK: '{user_feedback}' ===")
    
    # Method 1: Add feedback via new invoke
    feedback_input = {
        "messages": [HumanMessage(content=user_feedback)]
    }
    
    print("Resuming graph with feedback...")
    final_result = app.invoke(feedback_input, config=config)
    
    print(f"Final result: {final_result['loading_message']}")
    print(f"Final status: {final_result.get('status', 'No status')}")
    print(f"Feedback cycles: {final_result.get('feedback_cycles', 0)}")
    
    return final_result

# Run the test
if __name__ == "__main__":
    result = test_feedback_flow()