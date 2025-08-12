# ------------------------------------------------------------------
# 1. Imports & Global Setup
# ------------------------------------------------------------------
from typing import Literal, List, TypedDict
from langgraph.graph import StateGraph
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

# Project-specific imports
from core.llm_manager import LLMManager, LLMProvider
from pipeline.vector_store import VectorStoreManager
from utils.logger import get_enhanced_logger

# Initialize core components
llm_manager = LLMManager()
logger = get_enhanced_logger("rag_graph")
memory = MemorySaver()

# ------------------------------------------------------------------
# 2. State Definition
# ------------------------------------------------------------------
class RagState(TypedDict):
    """State container for the RAG workflow"""
    messages: List  # Conversation history
    question: str  # Current search-optimized question
    original_question: str  # User's initial question
    context: List[str]  # Retrieved documents
    ranked_context: List[str]  # Relevance-ordered documents
    context_scores: List[float]  # Relevance scores (0-10)
    feedback_cycle_count: int  # Feedback attempts (0-3)
    needs_feedback: bool  # Flag for requesting feedback
    user_feedback: str  # Collected user input

# ------------------------------------------------------------------
# 3. Core Utilities
# ------------------------------------------------------------------
def get_language_protocol() -> str:
    """Universal language handling instructions"""
    return """
🌍 LANGUAGE PROTOCOL — ABSOLUTE PRIORITY

1. DETECT user's primary language from their first message
2. RESPOND in the exact same language consistently
3. NEVER switch languages mid-conversation
4. PRESERVE cultural formatting (dates, numbers, units)"""

def safe_node(func):
    """Error-handling decorator for graph nodes"""
    def wrapper(state: RagState):
        try:
            return func(state)
        except Exception as e:
            logger.error(f"Node failure: {func.__name__} - {str(e)}")
            error_msg = f"{get_language_protocol()}\n\n🚨 System Error: {str(e)}"
            state["messages"].append(AIMessage(content=error_msg))
            state["needs_feedback"] = True
            return state
    return wrapper

# Initialize AI models
llm = llm_manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307"
)

# ------------------------------------------------------------------
# 4. Node Implementations
# ------------------------------------------------------------------
@safe_node
def initialize_question(state: RagState) -> RagState:
    """Setup initial question state"""
    if not state.get("original_question"):
        # Extract from last human message
        state["original_question"] = state["messages"][-1].content
    state["question"] = state["original_question"]
    state.setdefault("feedback_cycle_count", 0)
    return state

@safe_node
def rewrite_question(state: RagState) -> RagState:
    """Optimize question for retrieval using feedback"""
    lang = get_language_protocol()
    feedback = state.get("user_feedback", "")
    
    prompt = f"""{lang}
    TASK: Improve this search query while keeping original meaning and language.
    
    Original: {state['original_question']}
    {f"Feedback: {feedback}" if feedback else ""}
    
    Rewritten query:"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    state["question"] = response.content.strip()
    return state

@safe_node
def retrieve_documents(state: RagState) -> RagState:
    """Fetch relevant documents from vector store"""
    vector_store = VectorStoreManager.get_instance()
    k = 8 if state.get("needs_feedback") else 4  # More docs when struggling
    state["context"] = vector_store.query_documents(
        state["question"], 
        k=k
    )
    return state

@safe_node
def rank_documents(state: RagState) -> RagState:
    """Evaluate and rank document relevance"""
     
    """Rank contexts by relevance with better low-quality detection."""
    language_protocol = get_language_protocol()
    question = state["question"]
    contexts = state["context"]
    
    logger.info("=== CONTEXT RANKING DEBUG ===")
    logger.info(f"Question: {question}")
    logger.info(f"Number of contexts: {len(contexts)}")
    
    if not contexts:
        logger.warning("No contexts retrieved, triggering feedback")
        state["needs_feedback"] = True
        state["ranked_context"] = []
        state["context_scores"] = []
        return state

    scoring_prompt = f"""{language_protocol}
        You are a strict relevance-evaluation expert. Analyze these contexts for their relevance to the question: "{question}"
        
        CRITICAL RULES:
        - Score 1-3: Context is completely irrelevant, off-topic, or about different subjects
        - Score 4-6: Context is somewhat related but doesn't contain specific information needed
        - Score 7-9: Context is relevant but may be incomplete
        - Score 10: Context directly answers the question
        
        EXAMPLES:
        - Olympics question + legal documents = Score 1-2
        - Olympics question + sports documents = Score 7-10
        - Olympics question + general sports = Score 4-6
        
        Return ONLY comma-separated scores (e.g., "1.5, 8.0, 2.0")
        
        CONTEXTS TO SCORE:
        """
    
    for i, ctx in enumerate(contexts, 1):
        scoring_prompt += f"\n\n-- CONTEXT {i} --\n{ctx[:400]}..."

    messages = [
        SystemMessage(content=f"You are a strict relevance scoring specialist.\n{language_protocol}"),
        HumanMessage(content=scoring_prompt)
    ]
    
    try:
        response = llm.invoke(messages).content.strip()
        logger.debug(f"Relevance scores: {response}")
        
        # Parse scores more robustly
        scores = []
        for s in response.split(","):
            try:
                score = float(s.strip())
                scores.append(max(0, min(10, score)))  # Clamp between 0-10
            except ValueError:
                scores.append(2.0)  # Default low score for parsing errors
        
        # Ensure we have scores for all contexts
        while len(scores) < len(contexts):
            scores.append(2.0)
        
    except Exception as e:
        logger.error(f"Failed to parse scores: {e}, using length-based fallback")
        scores = [max(1, min(10, len(ctx)/100)) for ctx in contexts]

    # More aggressive low-quality detection
    scored = sorted(zip(contexts, scores), key=lambda x: x[1], reverse=True)
    ranked_contexts = [c for c, _ in scored]
    ranked_scores = [s for _, s in scored]
    
    # Determine if we need user feedback
    top_score = max(state["context_scores"]) if state["context_scores"] else 0
    state["needs_feedback"] = (
        top_score < 6.0 and 
        state["feedback_cycle_count"] < 3
    )
    return state

@safe_node
def request_feedback(state: RagState) -> RagState:
    """Interrupt flow to collect human input"""
    if not state["needs_feedback"]:
        return state

    prompt = f"""{get_language_protocol()}
    
🔍 I need more information about:
"{state['original_question']}"

Please help by:
1. Clarifying your question
2. Adding specific details
3. Confirming if I misunderstood"""

    # Pause execution and collect user input
    feedback = interrupt({
        "type": "human_feedback",
        "message": prompt
    })
    
    # Update state
    state["user_feedback"] = str(feedback)
    state["feedback_cycle_count"] += 1
    state["needs_feedback"] = False
    state["messages"].append(HumanMessage(content=feedback))
    
    return state

@safe_node
def generate_answer(state: RagState) -> RagState:
    """Produce final response with citations"""
    lang = get_language_protocol()
    context_str = "\n\n".join(f"[Source {i+1}]: {ctx[:300]}..." 
        for i, ctx in enumerate(state["ranked_context"][:3]))
    
    prompt = f"""{lang}
    QUESTION: {state['original_question']}
    {f"USER GUIDANCE: {state['user_feedback']}" if state.get('user_feedback') else ""}
    SOURCES:
    {context_str}
    
    INSTRUCTIONS:
    1. Answer using ONLY provided sources
    2. Cite sources with [1][2] notation
    3. Maintain question's original language"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    state["messages"].append(AIMessage(content=response.content))
    return state

# ------------------------------------------------------------------
# 5. Graph Construction - Clear Feedback Loop
# ------------------------------------------------------------------
workflow = StateGraph(RagState)

# Define nodes
workflow.add_node("initialize", initialize_question)
workflow.add_node("rewrite", rewrite_question)
workflow.add_node("retrieve", retrieve_documents)
workflow.add_node("rank", rank_documents)
workflow.add_node("get_feedback", request_feedback)
workflow.add_node("answer", generate_answer)

# Set initial workflow
workflow.set_entry_point("initialize")
workflow.add_edge("initialize", "rewrite")
workflow.add_edge("rewrite", "retrieve")
workflow.add_edge("retrieve", "rank")

# Feedback decision point
workflow.add_conditional_edges(
    "rank",
    lambda s: "get_feedback" if s["needs_feedback"] else "answer",
)

# Feedback handling path
workflow.add_conditional_edges(
    "get_feedback",
    lambda s: "rewrite" if s["feedback_cycle_count"] <= 3 else "answer",
)

# Final answer path
workflow.add_edge("answer", END)

# Compile with checkpointing
rag_graph = workflow.compile(
    interrupt_before=["get_feedback"],
    checkpointer=memory
)