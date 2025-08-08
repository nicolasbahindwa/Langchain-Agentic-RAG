# ------------------------------------------------------------------
# 1. Imports & Global Setup
# ------------------------------------------------------------------
from typing_extensions import TypedDict
from typing import Literal, List
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, AnyMessage
 
from langchain_core.documents import Document 
from pydantic import BaseModel, Field
from langgraph.types import Send
from IPython.display import Markdown
import operator

# Your project-specific imports
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import SearchManager
from pipeline.vector_store import VectorStoreManager
from langgraph.types import interrupt


from langgraph.checkpoint.memory import MemorySaver


 
from utils.logger import get_enhanced_logger   
 

# ------------------------------------------------------------------
# 2. Utilities & Constants
# ------------------------------------------------------------------
search_manager = SearchManager()
manager = LLMManager()

vector_store = VectorStoreManager(
    embedding_model='paraphrase-multilingual-MiniLM-L12-v2',
    collection_name="document_knowledge_base",
    persist_dir="./vector_storage"
)

memory = MemorySaver()

llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=1500
)

llm_light = manager.get_chat_model(provider=LLMProvider.OLLAMA)

logger = get_enhanced_logger("rag_graph")

def safe_node(func):
    """Decorator that catches any Exception and logs via the utils logger."""
    def _wrapper(state: RagState) -> RagState:
        try:
            return func(state)
        except Exception as ex:
            logger.failure(f"Node {func.__name__} failed: {ex}")
            lang_hint = get_language_protocol()
            err_msg = (
                f"{lang_hint}\n\n"
                f"⚠️ System Error (node `{func.__name__}`)\n"
                f"{str(ex)}"
            )
            state.setdefault("messages", []).append(AIMessage(content=err_msg))
            state["error"] = str(ex)
            return state
    return _wrapper
def get_language_protocol() -> str:
    """
    Universal Language Protocol for all LLM interactions.
    MUST be prepended to every system prompt.
    """
    return """
🌍 LANGUAGE PROTOCOL — ABSOLUTE PRIORITY

    UNIVERSAL LANGUAGE RULE:
    ALWAYS detect and respond in the EXACT language used by the user. This is non-negotiable.

    Language Detection Algorithm:
    1. Analyze the user's query for primary language indicators
    2. Identify the dominant language (>60% of content)
    3. For mixed-language queries, prioritize the first language used
    4. NEVER assume or default to any language
    5. NEVER switch languages mid-response unless explicitly requested

    Language Mirroring Examples:
    - User writes in English → Respond entirely in English
    - User writes in Japanese → Respond entirely in Japanese
    - User writes in Chinese → Respond entirely in Chinese
    - User writes "Bonjour, show me data" → Respond in French (first language used)
    - User writes mixed → Match the dominant language

    Explicit Language Respect:
    - Honor the user's linguistic choice as a sign of professional respect
    - Maintain consistent terminology in the chosen language
    - Use culturally appropriate formatting for numbers, dates, and currency
    """
 

# ------------------------------------------------------------------
# 3. State Definition
# ------------------------------------------------------------------
class RagState(TypedDict):
    messages: List[AnyMessage]
    question: str
    original_question: str
    answer: str
    context: List[str]
    ranked_context: List[str]
    context_scores: List[float]
    process_cycle_count: int
    user_feedback: str
    feedback_cycle_count: int
    needs_feedback: bool

# ------------------------------------------------------------------
# 4. Node Functions 
# ------------------------------------------------------------------
@safe_node
def question_rewrite(state: RagState) -> RagState:
    """Rewrite the question for better retrieval while respecting language."""
    language_protocol = get_language_protocol()
    feedback = ""
    messages  = state.get("messages", [])
    if messages  and isinstance(messages[-1], HumanMessage):
        feedback = messages[-1].content

    sys_msg = f"""{language_protocol}
        You are a query-optimization expert. Your task is to improve search queries while maintaining perfect language consistency.
        TASK: Rewrite the user's question to make it more effective for document search while keeping the same language and meaning."""
    
    prompt_content = f"""Original question: "{state["original_question"]}"
            write this question to make it more effective for document search while keeping the same language and meaning."""
    if feedback:
        prompt_content += f"\nUser feedback: {feedback}"

    messages = [
        SystemMessage(content=sys_msg),
        HumanMessage(content=prompt_content)
    ]
    rewritten = llm.invoke(messages).content.strip()
    state["question"] = rewritten
    return state

@safe_node
def retrieve_context(state: RagState) -> RagState:
    """Retrieve relevant documents with robust type handling."""
    query = state["question"]
    k = 8 if state.get("needs_feedback") else 4
    
    # Call query_documents which returns (documents, scores)
    results = vector_store.query_documents(query, k=k)
    
    # Unpack the tuple properly
    if isinstance(results, tuple) and len(results) == 2:
        documents, scores = results
        logger.debug(f"Vector store returned tuple: {len(documents)} docs, {len(scores)} scores")
    elif isinstance(results, list):
        # Fallback for backward compatibility
        documents = results
        scores = [1.0] * len(documents)
        logger.warning("Vector store returned list instead of tuple, using default scores")
    else:
        logger.error(f"Unexpected return type from vector store: {type(results)}")
        documents = []
        scores = []
    
    # Handle nested lists and flatten if necessary
    if documents and isinstance(documents[0], list):
        documents = [item for sublist in documents for item in sublist]
        logger.debug("Flattened nested document list")
    
    # Extract text content with safety checks
    texts = []
    for doc in documents:
        try:
            # Handle Document objects
            if hasattr(doc, 'page_content'):
                content = doc.page_content.strip()
            elif isinstance(doc, dict) and 'page_content' in doc:
                content = doc['page_content'].strip()
            elif isinstance(doc, str):
                content = doc.strip()
            else:
                logger.warning(f"Unknown document type: {type(doc)}")
                continue
                
            if content and len(content) > 20:
                texts.append(content)
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            continue

    logger.info(f"Retrieved {len(texts)} valid contexts out of {len(documents)} documents")
    state["context"] = texts
    return state

@safe_node
def context_ranking(state: RagState) -> RagState:
     
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

    # Trigger feedback if top score is low OR if average is very low
    top_score = max(scores) if scores else 0
    avg_score = sum(scores) / len(scores) if scores else 0
    
    logger.info(f"Context quality: top={top_score}, avg={avg_score}")
    
    # Lower threshold to catch more cases
    state["needs_feedback"] = top_score < 6.0 or avg_score < 4.0
    
    # Special case: if all scores are very low, definitely ask for feedback
    if all(score <= 3.0 for score in scores):
        state["needs_feedback"] = True
        
    state["ranked_context"] = ranked_contexts
    state["context_scores"] = ranked_scores
    
    logger.info(f"Feedback needed: {state['needs_feedback']}")
    return state

 

@safe_node
def collect_user_feedback(state: RagState) -> RagState:
    """Ask the user for feedback if needed - with proper interrupt."""
    if not state["needs_feedback"]:
        return state

    language_protocol = get_language_protocol()
    question = state["original_question"]
    
    feedback_msg = f"""{language_protocol}
I searched for information about your question: **"{question}"** but couldn't find sufficiently relevant results.

Could you please:
- Clarify what specific information you're looking for?
- Provide additional keywords or context?
- Let me know if I'm misunderstanding your question?"""

    # This will pause execution and wait for human input
    feedback = interrupt({
        "type": "human_feedback",
        "question": question,
        "message": feedback_msg
    })
    
    # The feedback comes back as the return value from interrupt
    state["user_feedback"] = str(feedback)
    state["needs_feedback"] = False
    state["feedback_cycle_count"] = state.get("feedback_cycle_count", 0) + 1
    
    return state


@safe_node
def process_feedback(state: RagState) -> RagState:
    """Process user feedback for the next cycle."""
    if state["messages"] and isinstance(state["messages"][-1], HumanMessage):
        state["user_feedback"] = state["messages"][-1].content
        state["needs_feedback"] = False
    return state

@safe_node
def answer_generation(state: RagState) -> RagState:
    """Generate final answer while respecting language."""
    language_protocol = get_language_protocol()
    context_window = "\n\n".join(
        f"SOURCE {i}:\n {ctx}"
        for i, ctx in enumerate(state["ranked_context"][:3], 1)
    )
    if "messages" not in state:
        state["messages"] = []
    prompt = [
        SystemMessage(content=f"""{language_protocol}
        Answer the question using ONLY the provided sources. Cite sources as [1][2]."""),
                HumanMessage(content=(
                    f"Question: {state['original_question']}\n\n"
                    f"Relevant sources:\n{context_window}\n\n"
                    f"User feedback: {state.get('user_feedback', 'None')}"
                ))
    ]
    response = llm.invoke(prompt)
    state["answer"] = response.content
    state["messages"].append(AIMessage(content=state["answer"]))
    return state

# ------------------------------------------------------------------
# 5. Conditional Edges
# ------------------------------------------------------------------
def should_request_feedback(state: RagState) -> Literal["collect_user_feedback", "answer_generation"]:
    """More nuanced feedback decision."""
    needs_fb = state.get("needs_feedback", False)
    feedback_cycles = state.get("feedback_cycle_count", 0)
    
    # Always request feedback if explicitly needed
    if needs_fb and feedback_cycles < 3:
        logger.info(f"Requesting feedback (cycle {feedback_cycles})")
        return "collect_user_feedback"
    
    # If we've had feedback cycles and still need feedback, we might want to proceed
    if feedback_cycles >= 3:
        logger.warning("Max feedback cycles reached, proceeding to answer")
        return "answer_generation"
    
    return "answer_generation"

def should_retry_retrieval(state: RagState) -> Literal["question_rewrite", "answer_generation"]:
    has_feedback = bool(state.get("user_feedback", "").strip())
    under_limit = state.get("feedback_cycle_count", 0) < 3
    return "question_rewrite" if has_feedback and under_limit else "answer_generation"


# ------------------------------------------------------------------
# 6. Graph Construction - FIXED VERSION
# ------------------------------------------------------------------
graph = StateGraph(RagState)

graph.add_node("question_rewrite", question_rewrite)
graph.add_node("retrieve_context", retrieve_context)
graph.add_node("context_ranking", context_ranking)
graph.add_node("collect_user_feedback", collect_user_feedback)
graph.add_node("process_feedback", process_feedback)
graph.add_node("answer_generation", answer_generation)

graph.set_entry_point("question_rewrite")
graph.add_edge("question_rewrite", "retrieve_context")
graph.add_edge("retrieve_context", "context_ranking")

# FIXED: Add explicit edge for cases where feedback is NOT needed
graph.add_conditional_edges(
    "context_ranking",
    should_request_feedback,
    {
        "collect_user_feedback": "collect_user_feedback",
        "answer_generation": "answer_generation"
    }
)

# This part is correct - feedback processing
graph.add_edge("collect_user_feedback", "process_feedback")

# FIXED: Ensure feedback processing can loop back to question rewrite
graph.add_conditional_edges(
    "process_feedback",
    should_retry_retrieval,
    {
        "question_rewrite": "question_rewrite",
        "answer_generation": "answer_generation"
    }
)

graph.add_edge("answer_generation", END)

compile_graph = graph.compile(interrupt_before=["collect_user_feedback"], checkpointer=memory)


import uuid

def run():
    print("🤖 Welcome to the RAG CLI assistant.")
    original_question = input("📝 Enter your question: ").strip()

    if not original_question:
        print("⚠️ Please enter a valid question.")
        return

    thread_id = f"cli-thread-{uuid.uuid4()}"

    # Configuration for the compiled graph
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # Initial state
    initial_state = {
        "original_question": original_question,
        "question": original_question,
        "messages": [HumanMessage(content=original_question)],
        "context": [],
        "ranked_context": [],
        "context_scores": [],
        "process_cycle_count": 0,
        "user_feedback": "",
        "feedback_cycle_count": 0,
        "needs_feedback": False,
    }

    try:
        current_state = initial_state
        max_attempts = 3
        
        for attempt in range(max_attempts):
            print(f"\n🔍 Attempt {attempt + 1}...")
            
            # Run the graph
            events = list(compile_graph.stream(current_state, config, stream_mode="updates"))
            
            # Check final state
            final_state = compile_graph.get_state(config).values
            
            if final_state.get("answer") and not final_state.get("needs_feedback"):
                print("\n✅ Answer:")
                print(final_state["answer"])
                return
            
            # Handle feedback request
            if final_state.get("needs_feedback"):
                feedback_msg = f"\nI searched for information about your question: **\"{final_state['original_question']}\"** but couldn't find sufficiently relevant results."
                print(feedback_msg)
                user_feedback = input("✍️  Your feedback: ").strip()
                
                if not user_feedback:
                    print("❌ No feedback provided. Exiting.")
                    return
                
                # Prepare next iteration state
                current_state = {
                    "original_question": final_state["original_question"],
                    "question": final_state["question"],  # Will be rewritten by question_rewrite
                    "messages": final_state["messages"] + [HumanMessage(content=user_feedback)],
                    "context": [],
                    "ranked_context": [],
                    "context_scores": [],
                    "process_cycle_count": final_state.get("process_cycle_count", 0) + 1,
                    "user_feedback": user_feedback,
                    "feedback_cycle_count": final_state.get("feedback_cycle_count", 0) + 1,
                    "needs_feedback": False,  # Reset for next cycle
                }
                
                # Force question rewrite with feedback
                rewrite_prompt = [
                    SystemMessage(content=get_language_protocol() + "\nYou are a query-optimization expert. Rewrite the question incorporating user feedback."),
                    HumanMessage(content=f"Original question: {final_state['original_question']}\nUser feedback: {user_feedback}\nRewrite the question to be more effective for document search.")
                ]
                
                rewritten = llm.invoke(rewrite_prompt).content.strip()
                current_state["question"] = rewritten
                print(f"🔄 Rewritten question: {rewritten}")
                
            else:
                # No feedback needed, but no answer - exit
                print("❌ Could not find relevant information.")
                return
        
        print("❌ Max attempts reached. Please try a different question.")
        
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run()