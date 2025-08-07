# ------------------------------------------------------------------
# 1. Imports & Global Setup
# ------------------------------------------------------------------
from typing_extensions import TypedDict
from typing import Literal, List
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, AnyMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import NodeInterrupt
from langchain_core.documents import Document 
from pydantic import BaseModel, Field
from langgraph.types import Send
from langchain_core.messages import get_buffer_string
from IPython.display import Markdown
import operator

# Your project-specific imports
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import SearchManager
from pipeline.vector_store import VectorStoreManager
from pipeline.orchestrator import DataExtractionPipeline

# ------------------------------------------------------------------
# 2. Utilities & Constants
# ------------------------------------------------------------------
search_manager = SearchManager()
manager = LLMManager()

vector_store = VectorStoreManager(
    embedding_model='BAAI/bge-small-en-v1.5',
    collection_name="document_knowledge_base",
    persist_dir="./vector_storage"
)

llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=1500
)

llm_light = manager.get_chat_model(provider=LLMProvider.OLLAMA)

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

def retrieve_context(state: RagState) -> RagState:
    """Retrieve relevant documents."""
    query = state["question"]
    k = 8 if state.get("needs_feedback") else 4
    docs: list[Document] = vector_store.query_documents(query, k=k)
    # Extract the text and filter
    texts = [
        doc.page_content.strip()
        for doc in docs
        if doc.page_content and len(doc.page_content.strip()) > 20
    ]

    state["context"] = texts
    return state

def context_ranking(state: RagState) -> RagState:
    """Rank contexts by relevance."""
    language_protocol = get_language_protocol()
    question = state["question"]
    contexts = state["context"]

    scoring_prompt = f"""{language_protocol}
        You are a relevance-evaluation expert. Score each context snippet (1-10) for its ability to answer this question:

        QUESTION: {question}

        SCORING CRITERIA:
        10 = Directly answers the question with supporting evidence
        7-9  = Relevant but incomplete or indirect
        4-6  = Somewhat related but not sufficient alone
        1-3  = Unrelated or contradictory

        Return ONLY a comma-separated list of scores. No explanations.
        Example: "7.5, 3.0, 9.2"

        CONTEXTS:
        """
    for i, ctx in enumerate(contexts, 1):
        scoring_prompt += f"\n\n-- CONTEXT {i} --\n {ctx[:500]}"

    messages = [
        SystemMessage(content=f"You are a relevance scoring specialist.\n{language_protocol}"),
        HumanMessage(content=scoring_prompt)
    ]
    response = llm.invoke(messages).content.strip()
    try:
        scores = [float(s.strip()) for s in response.split(",")]
    except Exception:
        scores = [len(ctx) for ctx in contexts]

    scored = sorted(zip(contexts, scores), key=lambda x: x[1], reverse=True)
    ranked_contexts = [c for c, _ in scored]
    ranked_scores = [s for _, s in scored]

    top_score = max(scores) if scores else 0
    state["needs_feedback"] = top_score < 6.0
    state["ranked_context"] = ranked_contexts
    state["context_scores"] = ranked_scores
    return state

def collect_user_feedback(state: RagState) -> RagState:
    """Ask the user for feedback if needed."""
    if not state["needs_feedback"]:
        return state

    language_protocol = get_language_protocol()
    question = state["original_question"]
    top_ctx = state["ranked_context"][:3]

    feedback_msg = f"""{language_protocol}
        I found some information about your question: **"{question}"**  
        but I’m not 100 % sure it fully answers what you’re looking for.

        Could you help me by:
        - Clarifying what specifically you need?
        - Confirming if any of this is relevant?
        - Adding any details I might be missing?

        Here’s what I found most relevant:
        """
    for i, ctx in enumerate(top_ctx, 1):
        feedback_msg += f"\n\n**Excerpt {i}:** {ctx[:150]}..."

    state["messages"].append(AIMessage(content=feedback_msg))
    state["feedback_cycle_count"] = state.get("feedback_cycle_count", 0) + 1
    return state

def process_feedback(state: RagState) -> RagState:
    """Process user feedback for the next cycle."""
    if state["messages"] and isinstance(state["messages"][-1], HumanMessage):
        state["user_feedback"] = state["messages"][-1].content
        state["needs_feedback"] = False
    return state

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
    needs_fb = state.get("needs_feedback", False)
    under_limit = state.get("feedback_cycle_count", 0) < 3
    return "collect_user_feedback" if needs_fb and under_limit else "answer_generation"

def should_retry_retrieval(state: RagState) -> Literal["question_rewrite", "answer_generation"]:
    has_feedback = bool(state.get("user_feedback", "").strip())
    under_limit = state.get("feedback_cycle_count", 0) < 3
    return "question_rewrite" if has_feedback and under_limit else "answer_generation"

# ------------------------------------------------------------------
# 6. Graph Construction
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

# Conditional edges
graph.add_conditional_edges(
    "context_ranking",
    should_request_feedback,
    {
        "collect_user_feedback": "collect_user_feedback",
        "answer_generation": "answer_generation"
    }
)

graph.add_edge("collect_user_feedback", "process_feedback")
graph.add_conditional_edges(
    "process_feedback",
    should_retry_retrieval,
    {
        "question_rewrite": "question_rewrite",
        "answer_generation": "answer_generation"
    }
)

graph.add_edge("answer_generation", END)

 
app = graph.compile()

 