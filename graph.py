from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------
MAX_FEEDBACK_CYCLES = 3

# -----------------------------------------------------------------------------
# STATE
# -----------------------------------------------------------------------------
class RAGState(TypedDict):
    question: str
    original_question: str
    documents: List[dict]
    answer: Optional[str]

    feedback: Optional[str] = None
    feedback_cycles: int = 0

    status: str = "initial"
    error: Optional[str] = None
    sources: List[str] = []

# -----------------------------------------------------------------------------
# NODES
# -----------------------------------------------------------------------------
def rewrite_question(state: RAGState) -> RAGState:
    if state["feedback_cycles"] == 0:                   # first run
        og = state["question"]
        return {"original_question": og, "status": "check_existing_docs"}

    # clarification branch
    og = state["original_question"]
    new_q = f"{og} {state['feedback']}".strip()
    return {"question": new_q, "feedback": None, "status": "check_existing_docs"}


def check_existing_documents(state: RAGState) -> RAGState:
    # decide: re-use docs or retrieve new ones
    if state["documents"] and _docs_cover(state["question"], state["documents"]):
        return {"status": "evaluate"}
    return {"status": "retrieve_documents"}


def retrieve_documents(state: RAGState) -> RAGState:
    docs = []                       # TODO: real retrieval
    return {"documents": docs, "status": "evaluate"}


def evaluator(state: RAGState) -> str:
    """Returns the *next* node name"""
    if state["documents"]:
        return "structure_answer"
    if state["feedback_cycles"] >= MAX_FEEDBACK_CYCLES:
        return "structure_answer"
    return "request_human_feedback"


def request_human_feedback(state: RAGState) -> str:
    """Returns the *next* node name after handling feedback"""
    fb = (state.get("feedback") or "").strip().lower()

    if fb in {"continue", "proceed", "yes"}:
        return "structure_answer"

    if fb in {"stop", "abort"}:
        state["error"] = "Aborted by user"
        return END

    # else: clarification
    state["feedback_cycles"] += 1
    return "rewrite_question"


def structure_answer(state: RAGState) -> RAGState:
    # TODO: real answer generation
    return {"answer": "Generated answer", "status": "complete"}

# -----------------------------------------------------------------------------
# UTILITIES
# -----------------------------------------------------------------------------
def _docs_cover(question: str, docs: List[dict]) -> bool:
    # TODO: real relevance check
    return bool(docs)

# -----------------------------------------------------------------------------
# GRAPH
# -----------------------------------------------------------------------------
def build():
    from langgraph.graph import START

    graph = StateGraph(RAGState)

    graph.add_node("rewrite_question", rewrite_question)
    graph.add_node("check_existing_documents", check_existing_documents)
    graph.add_node("retrieve_documents", retrieve_documents)
    graph.add_node("evaluator", evaluator)
    graph.add_node("request_human_feedback", request_human_feedback)
    graph.add_node("structure_answer", structure_answer)

    graph.set_entry_point("rewrite_question")

    graph.add_edge("rewrite_question", "check_existing_documents")
    graph.add_conditional_edges(
        "check_existing_documents",
        lambda s: "structure_answer" if s["status"] == "evaluate" else "retrieve_documents",
        {"retrieve_documents": "retrieve_documents", "structure_answer": "evaluator"}
    )
    graph.add_edge("retrieve_documents", "evaluator")

    # evaluator → only two targets allowed
    graph.add_conditional_edges(
        "evaluator",
        evaluator,
        {"structure_answer": "structure_answer", "request_human_feedback": "request_human_feedback"}
    )

    # human feedback → only two targets allowed
    graph.add_conditional_edges(
        "request_human_feedback",
        request_human_feedback,
        {"structure_answer": "structure_answer", "rewrite_question": "rewrite_question", END: END}
    )

    graph.add_edge("structure_answer", END)
    return graph.compile()

app = build()