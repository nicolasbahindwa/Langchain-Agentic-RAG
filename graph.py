from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.cache.memory import InMemoryCache
from langgraph.types import CachePolicy
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import SearchManager
from pipeline.vector_store import VectorStoreManager
from utils.logger import get_enhanced_logger
from typing import TypedDict, List, Optional, Annotated, Literal
from langchain_core.documents import Document
from langchain.schema import Document
from pydantic import BaseModel, Field
from functools import partial
import json
import hashlib
import html
import re 

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

# ===== Helper Functions =====
def sanitise(text: str, max_len: int = 1000) -> str:
    """Sanitize and truncate text for safe handling"""
    text = html.escape(text.strip())[:max_len]
    return text

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
    ai_feedback_request: Annotated[Optional[str], Field(None, description="AI's feedback request message")]
    # NEW FIELDS
    process_feedback: Annotated[bool, Field(False, description="Internal router flag")]
    max_docs_for_llm: Annotated[int, Field(20, description="Guard against prompt overflow")]

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
    feedback = sanitise(state.get("human_feedback") or "")  # Sanitized input

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
    """Enhanced document retrieval with hybrid search and safety caps"""
    try:
        # Get documents using top_k parameter with safety caps
        top_k = min(state.get("max_docs_for_llm", 20), 50)
        current_question = state["current_question"]
        
        # Retrieve documents using hybrid search with reranking disabled
        documents, scores = vector_store.query_documents(
            query=current_question,
            k=top_k,
            rerank=False,  # Disable cross-encoder reranking since we'll do LLM ranking later
            search_type="hybrid"
        )
        
        # Convert to Document objects with sanitization
        sanitized_docs = []
        for doc in documents:
            # Handle different document formats
            if isinstance(doc, Document):
                content = sanitise(doc.page_content, 5000)
                sanitized_docs.append(Document(
                    page_content=content,
                    metadata=doc.metadata
                ))
            else:
                # Fallback to string conversion with sanitization
                sanitized_docs.append(Document(
                    page_content=sanitise(str(doc), 2000)
                ))
        
        logger.info(f"Retrieved {len(sanitized_docs)} documents")
        return {
            "retrieved_docs": sanitized_docs,
            "error": None  # Clear any previous errors
        }
    except Exception as e:
        logger.failure(f"Document retrieval failed: {str(e)}")
        return {
            "retrieved_docs": [],
            "error": f"Retrieval failed: {str(e)}"
        }


def rank_and_select_documents_node(state: RAGState) -> RAGState:
    """Enhanced document ranking with metadata awareness and fallbacks"""
    docs = state.get("retrieved_docs", [])
    if not docs:
        logger.warning("No documents to rank")
        return {"ranked_docs": []}
    
    question = state["current_question"]
    
    # Build document previews with metadata
    doc_previews = []
    for idx, doc in enumerate(docs):
        # Extract metadata if available
        title = doc.metadata.get("title", "Untitled") if hasattr(doc, 'metadata') else "Untitled"
        source = doc.metadata.get("source", "Unknown source") if hasattr(doc, 'metadata') else "Unknown source"
        
        # Create informative preview
        snippet = doc.page_content
        if len(snippet) > 300:
            snippet = snippet[:250] + " [...] " + snippet[-50:]
        
        doc_previews.append(
            f"DOCUMENT {idx}:\n"
            f"Title: {title}\n"
            f"Source: {source}\n"
            f"Content: {snippet}\n"
            f"-----------------------"
        )
    
    preview = "\n".join(doc_previews[:20])  # Show max 20 docs to avoid overflow

    # Create ranking prompt with clearer instructions
    ranking_prompt = f"""
You are a document relevance expert. Analyze the documents below for relevance to the question.

{get_language_protocol()}

QUESTION: "{question}"

DOCUMENTS:
{preview}

TASK:
1. Score each document's relevance from 0.0 (irrelevant) to 1.0 (perfect match)
2. Return a JSON list of objects with this structure:
   [{{"index": 0, "score": 0.85, "reason": "Brief reason"}}, ...]

Important:
- Score based on specific information match, not general topic similarity
- Higher scores for documents that directly answer key parts of the question
- Include ALL documents in your response
- Return ONLY valid JSON
"""

    try:
        # Get structured ranking from LLM
        response = llm.invoke(ranking_prompt)
        content = response.content.strip()
        
        # Try to parse the JSON response
        try:
            rankings = json.loads(content)
            if not isinstance(rankings, list):
                raise ValueError("Invalid ranking format")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Ranking JSON parse failed: {e}\nResponse: {content}")
            # Fallback to default ordering
            return {"ranked_docs": docs[:5]}

        # Validate and process rankings
        valid_rankings = []
        for item in rankings:
            try:
                idx = int(item["index"])
                score = float(item["score"])
                reason = item.get("reason", "")
                
                if 0 <= idx < len(docs) and 0.0 <= score <= 1.0:
                    valid_rankings.append({
                        "index": idx,
                        "score": score,
                        "reason": reason
                    })
            except (KeyError, TypeError, ValueError):
                continue

        if not valid_rankings:
            logger.warning("No valid rankings returned, using default order")
            return {"ranked_docs": docs[:5]}

        # Sort by score descending
        valid_rankings.sort(key=lambda x: x["score"], reverse=True)
        
        # Log top results for debugging
        for i, rank in enumerate(valid_rankings[:3]):
            logger.debug(f"Top {i+1}: Doc {rank['index']} Score {rank['score']:.2f} - {rank['reason']}")
        
        # Select top 5 documents
        top_indices = [r["index"] for r in valid_rankings[:5]]
        ranked_docs = [docs[i] for i in top_indices]
        
        logger.info(f"Selected {len(ranked_docs)} top documents")
        return {"ranked_docs": ranked_docs}
        
    except Exception as e:
        logger.failure(f"Ranking failed: {e}")
        # Fallback: return first 5 documents with scores
        return {
            "ranked_docs": docs[:5],
            "error": f"Ranking failed: {str(e)}"
        }

    
def check_sufficiency_node(state: RAGState) -> RAGState:
    """
    More flexible sufficiency check that allows partial answers
    """
    ranked_docs = state.get("ranked_docs", [])
    if not ranked_docs:
        return {"context_sufficient": False}

    context = "\n\n".join(doc.page_content for doc in ranked_docs)
    question = state["current_question"]

    # Use a more flexible prompt
    prompt = f"""You are an evaluator.

    {get_language_protocol()}

    Question: {question}

    Retrieved context:
    {context[:5000]}

    Task: decide if the context provides USEFUL information to address the question.
    Return JSON only:
    {{"sufficient": true_or_false, "reason": "one-sentence reason"}}

    Evaluation Guidelines:
    1. Consider the context sufficient if it contains ANY relevant information
    2. Partial answers are acceptable - doesn't need to be complete
    3. Allow for reasonable inferences from the context
    4. Only mark insufficient if completely unrelated
    5. When in doubt, mark as sufficient
    """
    try:
        response = llm.invoke(prompt)
        result = json.loads(response.content)
        sufficient = result.get("sufficient", False)
        logger.info(f"Sufficiency check: {sufficient} – {result.get('reason','')}")
        return {"context_sufficient": sufficient}
    except Exception as e:
        logger.warning(f"Sufficiency parsing failed: {e}; defaulting to True")
        return {"context_sufficient": True}  # Default to sufficient on error

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
    """Smart feedback evaluation with multiple conditions"""
    feedback = sanitise(state.get("human_feedback") or "").lower()
    
    # Check if human wants to proceed without changes
    proceed_keywords = [
        "proceed", "go ahead", "use what you have", 
        "continue", "as is", "sufficient"
    ]
    
    if any(keyword in feedback for keyword in proceed_keywords):
        logger.info("Human instructed to proceed with current context")
        return {"process_feedback": False}
    
    # Check if user provided new question
    if feedback.startswith(("search for", "find", "look up")):
        logger.info("Human requested new search")
        return {
            "process_feedback": True,
            "current_question": feedback  # Use feedback as new question
        }
    
    # Default to processing feedback normally
    logger.info("Processing human feedback for refinement")
    return {"process_feedback": True}

def remove_control_characters(s: str) -> str:
    """Remove non-printable control characters from string"""
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
def structure_answer_node(state: RAGState) -> RAGState:
    """Robust answer structuring with self-healing JSON"""
    docs = state.get("ranked_docs", [])
    context = "\n\n".join(doc.page_content for doc in docs) or "No documents retrieved."
    question = state["current_question"]

    # Create self-healing system prompt
    system = f"""
    You are a precision assistant. Use ONLY the provided context.
    {get_language_protocol()}

    IMPORTANT: You MUST return valid JSON matching this schema:
    {{
    "main_answer": "Concise direct answer",
    "explanation": "Detailed explanation using ONLY context",
    "key_points": ["Bullet 1", "Bullet 2"],
    "examples": ["Example 1", "Example 2"],
    "additional_context": "Optional extra info",
    "confidence_level": "high/medium/low"
    }}

    Rules:
    1. If context doesn't answer question: 
    "main_answer": "Information not found"
    2. Never invent information outside context
    3. Maintain original language from question
    """

    # Create context with document references
    context_str = ""
    for i, doc in enumerate(docs):
        context_str += f"--- DOCUMENT {i} ---\n{doc.page_content}\n\n"
    
    user_prompt = f"""
    QUESTION: {question}

    CONTEXT:
    {context_str[:5000]}  <!-- Truncated if too long -->
    """

    # JSON generation with self-healing
    for attempt in range(3):  # Up to 3 attempts
        try:
            response = llm.invoke([
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt}
            ])
            
            # Clean control characters before parsing
            cleaned_content = remove_control_characters(response.content)
            
            # Try direct JSON parsing
            try:
                structured_data = StructuredAnswer.model_validate_json(cleaned_content)
                return {"structured_response": structured_data.model_dump()}
            except Exception as e:
                logger.warning(f"JSON parse attempt {attempt+1} failed: {e}")
                
                # Self-healing: Ask LLM to fix its own JSON
                # FIXED: Proper schema serialization
                schema_str = json.dumps(StructuredAnswer.model_json_schema(), indent=2)
                repair_prompt = f"""
        Previous response was invalid JSON. Please fix it.

        Invalid JSON:
        {cleaned_content}

        Schema:
        {schema_str}

        Return ONLY valid JSON:
        """
                response = llm.invoke(repair_prompt)
                # Clean repaired response too
                cleaned_repair = remove_control_characters(response.content)
                structured_data = StructuredAnswer.model_validate_json(cleaned_repair)
                return {"structured_response": structured_data.model_dump()}
                
        except Exception as e:
            logger.warning(f"Structure attempt {attempt+1} failed: {e}")
            # Update prompt for next attempt
            user_prompt = f"Previous error: {str(e)[:200]}\n\n{user_prompt}"
    
    # Final fallback after all attempts
    logger.failure("Structured answer generation failed after 3 attempts")
    return {"structured_response": {
        "main_answer": "Could not generate structured answer",
        "explanation": "Technical error in processing documents",
        "key_points": [doc.page_content[:100] for doc in docs[:3]],
        "examples": [],
        "additional_context": None,
        "confidence_level": "low"
    }}

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
    """Determine next workflow step with better thresholds"""
    if state.get("context_sufficient", False):
        return "sufficient"
        
    # Allow 1 retry cycle before giving up
    if state.get("feedback_cycles", 0) >= 1:  
        return "max_cycles"
        
    return "insufficient"

def route_after_feedback(state: RAGState) -> str:
    """Decide next step after human feedback"""
    if state.get("process_feedback") is True:
        return "process_feedback"
    return "skip_retrieval"

# ------------------------------------------------------------------
# Cache Key Generator (extracted outside build function)
# ------------------------------------------------------------------
def create_robust_cache_key(state: RAGState, *key_fields):
    # Handle non-dictionary states (e.g., during visualization)
    if not isinstance(state, dict):
        return "default_cache_key"  # Return a placeholder key
    
    key_data = {}
    for field in key_fields:
        value = state.get(field)
        if value is not None:
            if isinstance(value, dict):
                key_data[field] = dict(sorted(value.items()))
            elif isinstance(value, (list, tuple)):
                key_data[field] = value
            else:
                key_data[field] = value
    try:
        json_str = json.dumps(key_data, sort_keys=True, separators=(',', ':'))
    except (TypeError, ValueError):
        json_str = str(sorted(key_data.items()))
    return hashlib.sha256(json_str.encode()).hexdigest() if len(json_str) > 200 else json_str

# ===== 5. Graph Construction =====
# def build_rag_workflow():
#     """Construct the enhanced RAG workflow graph"""
#     builder = StateGraph(RAGState)

#     # Define nodes
#     builder.add_node("rewrite_question", rewrite_question_node)
#     builder.add_node("retrieve_documents", retrieve_documents_node)
#     builder.add_node("rank_and_select_documents", rank_and_select_documents_node)
#     builder.add_node("check_sufficiency", check_sufficiency_node)
#     builder.add_node("request_human_feedback", request_feedback_node)
#     builder.add_node("evaluate_feedback", evaluate_feedback_node)
#     builder.add_node("structure_answer", structure_answer_node)
#     builder.add_node("generate_answer", generate_answer_node)

#     # Setup workflow structure
#     builder.set_entry_point("rewrite_question")

#     # Main flow
#     builder.add_edge("rewrite_question", "retrieve_documents")
#     builder.add_edge("retrieve_documents", "rank_and_select_documents")
#     builder.add_edge("rank_and_select_documents", "check_sufficiency")

#     # Conditional routing after sufficiency check
#     builder.add_conditional_edges(
#         "check_sufficiency",
#         route_based_on_sufficiency,
#         {
#             "sufficient": "structure_answer",
#             "insufficient": "request_human_feedback",
#             "max_cycles": "structure_answer"
#         }
#     )

#     # Feedback handling flow
#     builder.add_edge("request_human_feedback", "evaluate_feedback")
#     builder.add_conditional_edges(
#         "evaluate_feedback",
#         route_after_feedback,
#         {
#             "process_feedback": "rewrite_question",
#             "skip_retrieval": "structure_answer"
#         }
#     )

#     # Final answer flow
#     builder.add_edge("structure_answer", "generate_answer")
#     builder.add_edge("generate_answer", END)

#     return builder.compile(
#         # checkpointer=memory,  # UNCOMMENTED
#         interrupt_after=["request_human_feedback"]
#     )

def build_rag_workflow():
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver

    builder = StateGraph(RAGState)

    # Nodes without caching
    builder.add_node("rewrite_question", rewrite_question_node)

    # Node 1 – Document retrieval – cached on current_question + max_docs_for_llm
    builder.add_node(
        "retrieve_documents",
        retrieve_documents_node,
        cache_policy=CachePolicy(
            key_func=partial(create_robust_cache_key, "current_question", "max_docs_for_llm"),
            ttl=3600
        )
    )

    # Node 2 – Document ranking – cached on current_question + retrieved_docs
    builder.add_node(
        "rank_and_select_documents",
        rank_and_select_documents_node,
        cache_policy=CachePolicy(
            key_func=partial(create_robust_cache_key, "current_question", "retrieved_docs"),
            ttl=3600
        )
    )

    # Remaining nodes (no caching)
    builder.add_node("check_sufficiency", check_sufficiency_node)
    builder.add_node("request_human_feedback", request_feedback_node)
    builder.add_node("evaluate_feedback", evaluate_feedback_node)
    builder.add_node("structure_answer", structure_answer_node)
    builder.add_node("generate_answer", generate_answer_node)

    # ------------------------------------------------------------------
    # Edges – unchanged
    # ------------------------------------------------------------------
    builder.set_entry_point("rewrite_question")
    builder.add_edge("rewrite_question", "retrieve_documents")
    builder.add_edge("retrieve_documents", "rank_and_select_documents")
    builder.add_edge("rank_and_select_documents", "check_sufficiency")

    builder.add_conditional_edges(
        "check_sufficiency",
        route_based_on_sufficiency,
        {"sufficient": "structure_answer",
         "insufficient": "request_human_feedback",
         "max_cycles": "structure_answer"}
    )

    builder.add_edge("request_human_feedback", "evaluate_feedback")
    builder.add_conditional_edges(
        "evaluate_feedback",
        route_after_feedback,
        {"process_feedback": "rewrite_question",
         "skip_retrieval": "structure_answer"}
    )
    builder.add_edge("structure_answer", "generate_answer")
    builder.add_edge("generate_answer", END)

    # ------------------------------------------------------------------
    # Compile with in-memory cache backend
    # ------------------------------------------------------------------
    return builder.compile(
        # checkpointer=MemorySaver(),
        interrupt_after=["request_human_feedback"],
        cache=InMemoryCache()
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
        "feedback_cycles": 0,
        "process_feedback": False,
        "max_docs_for_llm": 20
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