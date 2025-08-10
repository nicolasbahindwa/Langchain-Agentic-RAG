from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import SearchManager
from pipeline.vector_store import VectorStoreManager
from utils.logger import get_enhanced_logger
from typing import TypedDict, List, Optional, Annotated, Literal
from langchain_core.documents import Document
from langchain.schema import Document
from pydantic import BaseModel, Field
import json

# Initialize components
search_manager = SearchManager()
llm_manager = LLMManager()

vector_store = VectorStoreManager(
    embedding_model='paraphrase-multilingual-MiniLM-L12-v2',
    collection_name="document_knowledge_base",
    persist_dir="./vector_storage"
)

memory = MemorySaver()

llm = llm_manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=1500
)

llm_light = llm_manager.get_chat_model(provider=LLMProvider.OLLAMA)
logger = get_enhanced_logger("rag_graph")




# ===== 1. State Definition =====
class RAGState(TypedDict):
    """Workflow state container"""
    original_question: Annotated[str, Field(description="User's original question")]
    current_question: Annotated[str, Field(description="Current question version after rewrites")]
    retrieved_docs: Annotated[List[Document], Field(description="Retrieved documents")]
    ranked_docs: Annotated[List[Document], Field(description="Ranked and filtered best documents")]
    context_sufficient: Annotated[bool, Field(False, description="Sufficiency flag")]
    human_feedback: Annotated[Optional[str], Field(None, description="Human input")]
    feedback_cycles: Annotated[int, Field(0, description="Feedback cycle count")]
    structured_response: Annotated[Optional[dict], Field(None, description="Structured answer components")]
    final_answer: Annotated[Optional[str], Field(None, description="Generated answer")]
    error: Annotated[Optional[str], Field(None, description="Error message")]
    # NEW: Field to store the AI's feedback request
    ai_feedback_request: Annotated[Optional[str], Field(None, description="AI's feedback request message")]

# ===== 2. Structured Output Models =====
class ContextSufficiencyCheck(BaseModel):
    sufficient: bool = Field(description="Context adequacy")
    reasoning: str = Field(description="Sufficiency rationale")

class QuestionRewriter(BaseModel):
    rewritten_question: str = Field(description="Optimized question")
    reasoning: str = Field(description="Rewriting rationale")

class DocumentRelevanceScore(BaseModel):
    document_index: int = Field(description="Index of the document in the list")
    relevance_score: float = Field(description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Why this document is relevant/irrelevant")

class DocumentRanking(BaseModel):
    rankings: List[DocumentRelevanceScore] = Field(description="List of document rankings")
    selected_count: int = Field(description="Number of top documents to select", ge=1, le=10)

class StructuredAnswer(BaseModel):
    main_answer: str = Field(description="Direct, concise answer to the question")
    explanation: str = Field(description="Detailed explanation of the answer")
    key_points: list[str] = Field(description="Key supporting points")
    examples: list[str] = Field(description="Relevant examples or use cases")
    additional_context: str | None = Field(None, description="Extra context")
    confidence_level: Literal["high", "medium", "low"]

class DocumentRankingLLMResponse(BaseModel):
    ordered_indices: List[int] = Field(description="List of document indices")


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

# ===== 3. Node Implementations =====
 
def rewrite_question_node(state: RAGState) -> RAGState:
    original = state["original_question"].strip()
    feedback = state.get("human_feedback", "").strip()

    try:
        if feedback:
            # Combine original question with human feedback
            combined_prompt = f"""
You are a question refiner.

{get_language_protocol()}

Original question:
{original}

Human feedback:
{feedback}

Task: Rewrite the question to **incorporate** the feedback while **preserving** the original intent and language.
Return ONLY the rewritten question.
"""
            response = llm_light.invoke(combined_prompt)
            rewritten = response.content.strip()
            logger.info(f"Question refined with feedback: '{original}' + feedback → '{rewritten}'")
        else:
            # No feedback, just optimize the original
            prompt = f"""
You are a question-optimiser.

{get_language_protocol()}

Original question:
{original}

Task: Make the question more specific **without changing its meaning** and **without adding any external facts**.
Return ONLY the rewritten question.
"""
            response = llm_light.invoke(prompt)
            rewritten = response.content.strip()
            logger.info(f"Question rewritten (no feedback): '{original}' → '{rewritten}'")

        return {"current_question": rewritten}
    except Exception as e:
        logger.failure(f"Question rewrite failed: {e}")
        return {"error": f"Rewrite failed: {e}"}

def retrieve_documents_node(state: RAGState) -> RAGState:
    try:
        # Get both documents and scores from the vector store
        raw_docs, _ = vector_store.query_documents(state["current_question"])
        
        # Convert to simple Document objects with just page_content
        docs = []
        for doc in raw_docs:
            if isinstance(doc, Document):
                # Create a new Document with only page_content
                docs.append(Document(page_content=doc.page_content))
            elif isinstance(doc, dict):
                # Handle dictionary format
                content = doc.get("page_content", doc.get("content", ""))
                docs.append(Document(page_content=content))
            else:
                # Fallback to string conversion
                docs.append(Document(page_content=str(doc)))
        
        logger.info(f"Retrieved {len(docs)} documents")
        return {"retrieved_docs": docs}
    except Exception as e:
        logger.failure(f"Document retrieval failed: {str(e)}")
        return {"error": f"Retrieval failed: {str(e)}"}


def rank_and_select_documents_node(state: RAGState) -> RAGState:
    docs = state.get("retrieved_docs", [])
    if not docs:
        return {"ranked_docs": []}

    # Build preview (same as before)...
    preview_parts = []
    for idx, doc in enumerate(docs):
        snippet = (doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content)
        preview_parts.append(f"{idx}: {snippet}")
    preview = "\n".join(preview_parts)

    ranking_prompt = f"""
    TASK: Return ONLY numbers separated by commas. No JSON, no explanations.

    Question: "{state['current_question']}"

    Documents:
    {preview}

    Return ONLY indices as: 3,0,1,2
    """

    try:
        response = llm.invoke(ranking_prompt)
        
        # Simple list parsing
        indices_str = response.content.strip()
        indices = [int(x.strip()) for x in indices_str.split(',') if x.strip().isdigit()]
        
        # Validate indices
        valid_indices = [idx for idx in indices if 0 <= idx < len(docs)]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_indices = [idx for idx in valid_indices if not (idx in seen or seen.add(idx))]
        
        # Take top 5
        selected_indices = unique_indices[:5]
        ranked_docs = [docs[i] for i in selected_indices]
        
        return {"ranked_docs": ranked_docs}
        
    except Exception as e:
        logger.error(f"Ranking failed: {e}")
        # Fallback: use first 5 docs
        return {"ranked_docs": docs[:5]}
    
def check_sufficiency_node(state: RAGState) -> RAGState:
    """
    Grade whether the retrieved docs *actually* answer the question.
    Returns False if any required information is missing.
    """
    ranked_docs = state.get("ranked_docs", [])
    if not ranked_docs:
        return {"context_sufficient": False}

    context = "\n\n".join(doc.page_content for doc in ranked_docs)
    question = state["current_question"]

    prompt = f"""You are an evaluator.

    {get_language_protocol()}

    Question: {question}

    Retrieved context:
    {context[:4000]}

    Task: decide if the context **fully answers** the question.
    Return JSON only:
    {{"pass": true_or_false, "reason": "one-sentence reason"}}

    Rules:
    - If any key info is missing → pass=false
    - If only partial or vague answer → pass=false
    - If fully answered → pass=true
    """
    try:
        response = llm.invoke(prompt)
        result = json.loads(response.content)
        sufficient = result.get("pass", False)
        logger.info(f"Sufficiency check: {sufficient} – {result.get('reason','')}")
        return {"context_sufficient": sufficient}
    except Exception as e:
        logger.warning(f"Sufficiency parsing failed: {e}; defaulting to False")
        return {"context_sufficient": False}

def request_feedback_node(state: RAGState) -> RAGState:
    """Prepare for human input - store AI message separately"""
    feedback_msg = f"""
    The current context may not be sufficient to fully answer your question: "{state['current_question']}"
    
    Please provide additional clarification or specify what aspects you'd like me to focus on.
    You can also ask me to search for more specific information.
    """
    
    return {
        "ai_feedback_request": feedback_msg,  # Store separately
        "human_feedback": None,  # Reset human feedback
        "feedback_cycles": state.get("feedback_cycles", 0) + 1
    }

def evaluate_feedback_node(state: RAGState) -> RAGState:
    """Decide how to handle human feedback"""
    feedback = state.get("human_feedback", "").lower()
    
    # Check if human wants to proceed without changes
    if any(keyword in feedback for keyword in ["proceed", "go ahead", "use what you have", "continue"]):
        logger.info("Human instructed to proceed with current context")
        return {"process_feedback": False}
    
    # Default to processing feedback
    logger.info("Processing human feedback for new retrieval")
    return {"process_feedback": True}

def structure_answer_node(state: RAGState) -> RAGState:
    """
    Build the final answer using ONLY the retrieved documents.
    """
    docs = state.get("ranked_docs", [])
    context = "\n\n".join(doc.page_content for doc in docs) or "No documents retrieved."
    question = state["current_question"]

    system = (
        "You are a precise assistant. "
        "Use **only** the provided context. "
        "Do not add external information, assumptions, or paraphrase beyond the text. "
        "Return valid JSON matching the requested schema."
    )

    prompt = f"""{get_language_protocol()}

    Question: {question}

    Context:
    {context}

    Construct the answer using **only** the context above.  
    If the context does not contain the answer, state that clearly.

    Return JSON with this schema:
    {{
    "main_answer": "<concise answer or 'Information not found in provided documents'>",
    "explanation": "<detailed explanation strictly from context>",
    "key_points": ["<point1>", "<point2>"],
    "examples": ["<example from context>"],
    "additional_context": "<extra info only if explicitly in context>",
    "confidence_level": "high|medium|low"
    }}
    """
    try:
        response = llm.invoke([{"role": "system", "content": system},
                               {"role": "user", "content": prompt}])
        structured_data = StructuredAnswer.model_validate_json(response.content)
        return {"structured_response": structured_data.model_dump()}
    except Exception as e:
        logger.warning(f"JSON extraction failed: {e}")
        fallback = {
            "main_answer": "Could not generate a structured answer from the retrieved documents.",
            "explanation": context[:1000],
            "key_points": [],
            "examples": [],
            "additional_context": None,
            "confidence_level": "low"
        }
        return {"structured_response": fallback}

def generate_answer_node(state: RAGState) -> RAGState:
    data = state.get("structured_response", {})
    if not data:
        return {"final_answer": "Error: No structured response available."}

    lines = []

    if ans := data.get("main_answer"):
        lines.append(f"**Answer:** {ans}")

    if expl := data.get("explanation"):
        lines.append(f"**Explanation:**\n{expl}")

    if kps := data.get("key_points"):
        lines.append("**Key Points:**\n" + "\n".join(f"- {kp}" for kp in kps))

    if exs := data.get("examples"):
        lines.append("**Examples:**\n" + "\n".join(f"- {ex}" for ex in exs))

    if ac := data.get("additional_context"):
        lines.append(f"**Additional Context:**\n{ac}")

    if cl := data.get("confidence_level"):
        lines.append(f"**Confidence Level:** {cl.title()}")

    return {"final_answer": "\n\n".join(lines)}

# ===== 4. Routing Logic =====
def route_based_on_sufficiency(state: RAGState) -> str:
    """Determine next workflow step"""
    if state.get("context_sufficient", False):
        return "sufficient"
    if state.get("feedback_cycles", 0) >= 3:  # Max cycles
        return "max_cycles"
    return "insufficient"

def route_after_feedback(state: RAGState) -> str:
    """Decide next step after human feedback"""
    if state.get("process_feedback") is True:
        return "process_feedback"
    return "skip_retrieval"

# ===== 5. Graph Construction =====
def build_rag_workflow():
    """Construct the enhanced RAG workflow graph"""
    builder = StateGraph(RAGState)

    # Define nodes
    builder.add_node("rewrite_question", rewrite_question_node)
    builder.add_node("retrieve_documents", retrieve_documents_node)
    builder.add_node("rank_and_select_documents", rank_and_select_documents_node)
    builder.add_node("check_sufficiency", check_sufficiency_node)
    builder.add_node("request_human_feedback", request_feedback_node)  # This sets ai_feedback_request
    builder.add_node("structure_answer", structure_answer_node)
    builder.add_node("generate_answer", generate_answer_node)

    # Setup workflow structure
    builder.set_entry_point("rewrite_question")

    # Main flow
    builder.add_edge("rewrite_question", "retrieve_documents")
    builder.add_edge("retrieve_documents", "rank_and_select_documents")
    builder.add_edge("rank_and_select_documents", "check_sufficiency")

    # Conditional routing after sufficiency check
    builder.add_conditional_edges(
        "check_sufficiency",
        route_based_on_sufficiency,
        {
            "sufficient": "structure_answer",
            "insufficient": "request_human_feedback",
            "max_cycles": "structure_answer"
        }
    )

    # Feedback loop and final answer generation
    builder.add_edge("request_human_feedback", "rewrite_question")  # Now goes directly to rewrite
    builder.add_edge("structure_answer", "generate_answer")
    builder.add_edge("generate_answer", END)

    return builder.compile(
        # checkpointer=memory,
        interrupt_after=["request_human_feedback"]  # Interrupt after AI prepares feedback request
    )

app = build_rag_workflow()

# ===== 6. Usage Example =====
def run_rag_query(question: str, thread_id: str = "default"):
    """Run a RAG query through the workflow"""
    initial_state = {
        "original_question": question,
        "current_question": question,
        "retrieved_docs": [],
        "ranked_docs": [],
        "context_sufficient": False,
        "feedback_cycles": 0
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        result = app.invoke(initial_state, config=config)
        return result.get("final_answer", "No answer generated")
    except Exception as e:
        logger.failure(f"RAG workflow failed: {str(e)}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Test the workflow
    test_question = "What are the main benefits of using vector databases?"
    answer = run_rag_query(test_question)
    print(f"Question: {test_question}")
    print(f"Answer: {answer}")