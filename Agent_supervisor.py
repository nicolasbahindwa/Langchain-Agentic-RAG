from __future__ import annotations

from typing import List, Dict, Any, TypedDict, Annotated, Optional, Callable
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
from datetime import datetime
import json
from enum import Enum
import re
# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL LANGUAGE PROTOCOL SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class QuestionComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    

def get_language_protocol() -> str:
    """
    Universal Language Protocol for all LLM interactions.
    MUST be prepended to every system prompt.
    """
    return """
🌍 LANGUAGE PROTOCOL — ABSOLUTE PRIORITY

UNIVERSAL LANGUAGE RULE:
ALWAYS detect and respond in the EXACT language used by the user. This is non-negotiable.

Language Detection & Mirroring Algorithm:
1. Analyze the user's current message for primary language indicators
2. Identify the dominant language (>60% of content)  
3. For mixed-language queries, prioritize the first language used
4. If language changes from previous messages, adapt to the new language
5. NEVER assume or default to any language
6. NEVER switch languages mid-response unless explicitly requested

Language Mirroring Examples:
- User writes in English → Respond entirely in English
- User writes in Japanese → Respond entirely in Japanese  
- User writes in Chinese → Respond entirely in Chinese
- User writes "Bonjour, show me data" → Respond in French (first language used)
- User writes mixed → Match the dominant language
- User switches from English to Spanish → Switch to Spanish immediately

Explicit Language Respect:
- Honor the user's linguistic choice as a sign of professional respect
- Maintain consistent terminology in the chosen language
- Use culturally appropriate formatting for numbers, dates, and currency
- Translate English sources naturally into the user's language
- Preserve the user's level of formality and tone

CRITICAL: This language protocol overrides all other instructions. Language consistency is the highest priority.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

def create_language_aware_prompt(base_prompt: str, context_about_user_language: str = "") -> str:
    """
    Create any prompt with universal language protocol prepended.
    """
    language_protocol = get_language_protocol()
    
    if context_about_user_language:
        language_context = f"\n🔍 LANGUAGE CONTEXT: {context_about_user_language}\n"
    else:
        language_context = ""
    
    return f"""{language_protocol}{language_context}

{base_prompt}"""

# ══════════════════════════════════════════════════════════════════════════════
# DYNAMIC STATE WITH LANGUAGE TRACKING
# ══════════════════════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    """Enhanced state with dynamic language tracking."""
    messages: Annotated[List[BaseMessage], add_messages]
    needs_clarification: bool
    search_results: Optional[List[Dict[str, Any]]]
    user_query: str
    search_complete: bool
    is_generating: bool
    # Dynamic language tracking - updated as needed
    current_language: str  # Current detected language (can change)
    previous_language: str  # Previous language (for comparison)
    language_changed: bool  # Flag if language switched
    
    question_complexity: Optional[str]  # simple|moderate|complex
    complexity_reasoning: Optional[str]
    optimized_queries: Optional[List[str]]
    query_strategy: Optional[str]

# ══════════════════════════════════════════════════════════════════════════════
# INITIALIZE MANAGERS
# ══════════════════════════════════════════════════════════════════════════════

from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import create_search_manager

# Initialize managers
llm_manager = LLMManager()

# Main agent LLM for tool decisions (with language awareness)
llm = llm_manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.2,
    max_tokens=2000,
)

# Answer generation LLM (with language awareness)
llm_evaluator = llm_manager.get_chat_model(
    provider=LLMProvider.OPENAI,
    model="gpt-4o-mini", 
    temperature=0.1,
    max_tokens=4000,
)

# ══════════════════════════════════════════════════════════════════════════════
# SEARCH TOOLS (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

search_manager = create_search_manager()

class SearchInput(BaseModel):
    query: str = Field(description="The search query string.")

@tool("tavily_search", args_schema=SearchInput)
def tavily_search(query: str) -> Dict[str, Any]:
    """Use Tavily for *latest* or *current* info (news, what's new, today/now)."""
    try:
        res = search_manager.search(
            query=query,
            provider="tavily",
            max_results=6,
            search_depth="advanced",
        )
        
        search_results = []
        for result in res.get("search_results", []):
            if hasattr(result, '__dict__'):
                result_dict = {
                    'title': getattr(result, 'title', ''),
                    'url': getattr(result, 'url', ''),
                    'content': getattr(result, 'content', ''),
                    'snippet': getattr(result, 'snippet', ''),
                    'score': getattr(result, 'score', 0),
                    'published_date': getattr(result, 'published_date', ''),
                    'metadata': getattr(result, 'metadata', {}),
                }
            else:
                result_dict = result
            search_results.append(result_dict)
        
        return {
            "provider": "tavily",
            "query": query,
            "search_results": search_results,
        }
    except Exception as e:
        return {"provider": "tavily", "query": query, "error": str(e)}

@tool("wikipedia_search", args_schema=SearchInput)
def wikipedia_search(query: str) -> Dict[str, Any]:
    """Use Wikipedia for background, historical, or evergreen facts."""
    try:
        res = search_manager.search(
            query=query,
            provider="wikipedia",
            max_results=4,
            full_content=False,
            summary_sentences=4,
        )
        
        search_results = []
        for result in res.get("search_results", []):
            if hasattr(result, '__dict__'):
                result_dict = {
                    'title': getattr(result, 'title', ''),
                    'url': getattr(result, 'url', ''),
                    'content': getattr(result, 'content', ''),
                    'snippet': getattr(result, 'snippet', ''),
                    'score': getattr(result, 'score', 0),
                    'published_date': getattr(result, 'published_date', ''),
                    'metadata': getattr(result, 'metadata', {}),
                }
            else:
                result_dict = result
            search_results.append(result_dict)
        
        return {
            "provider": "wikipedia",
            "query": query,
            "search_results": search_results,
        }
    except Exception as e:
        return {"provider": "wikipedia", "query": query, "error": str(e)}

@tool("duckduckgo_search", args_schema=SearchInput)
def duckduckgo_search(query: str) -> Dict[str, Any]:
    """Use DuckDuckGo for general browsing, mixed web results, or broad queries."""
    try:
        res = search_manager.search(
            query=query,
            provider="duckduckgo",
            max_results=6,
            region="wt-wt",
            safesearch="moderate",
        )
        
        search_results = []
        for result in res.get("search_results", []):
            if hasattr(result, '__dict__'):
                result_dict = {
                    'title': getattr(result, 'title', ''),
                    'url': getattr(result, 'url', ''),
                    'content': getattr(result, 'content', ''),
                    'snippet': getattr(result, 'snippet', ''),
                    'score': getattr(result, 'score', 0),
                    'published_date': getattr(result, 'published_date', ''),
                    'metadata': getattr(result, 'metadata', {}),
                }
            else:
                result_dict = result
            search_results.append(result_dict)
        
        return {
            "provider": "duckduckgo",
            "query": query,
            "search_results": search_results,
        }
    except Exception as e:
        return {"provider": "duckduckgo", "query": query, "error": str(e)}

# Tools list
TOOLS = [tavily_search, wikipedia_search, duckduckgo_search]

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(TOOLS)

# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def extract_search_results(state: AgentState) -> List[Dict[str, Any]]:
    """Extract search results from tool messages."""
    search_results = []
    
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage):
            try:
                if isinstance(msg.content, dict):
                    content = msg.content
                elif isinstance(msg.content, str):
                    content = json.loads(msg.content)
                else:
                    continue
                
                if isinstance(content, dict) and 'search_results' in content:
                    results = content['search_results']
                    provider = content.get('provider', 'unknown')
                    
                    if isinstance(results, list):
                        for i, result in enumerate(results):
                            if isinstance(result, dict):
                                result['source'] = f"{provider} [{len(search_results) + i + 1}]"
                                search_results.append(result)
                            
            except Exception as e:
                continue
    
    return search_results

def format_search_results_for_answer(results: List[Dict[str, Any]]) -> str:
    """Format search results for answer generation."""
    if not results:
        return "No search results available."
    
    formatted = []
    for result in results:
        source = result.get('source', 'Unknown source')
        content = result.get('content', result.get('text', result.get('snippet', 'No content')))
        title = result.get('title', '')
        url = result.get('url', result.get('link', ''))
        
        result_text = f"**{source}**: {title}\n"
        result_text += f"Content: {content}\n"
        if url:
            result_text += f"URL: {url}\n"
        
        formatted.append(result_text)
    
    return "\n".join(formatted)


def evaluate_search_results_internal(user_query: str, search_results: List[Dict[str, Any]]) -> bool:
    """Simple evaluation without LLM - check if we have meaningful content."""
    if not search_results:
        return False
    
    # Check for meaningful content
    has_meaningful_content = False
    total_content_length = 0
    
    for result in search_results:
        content = result.get('content', '') or result.get('text', '') or result.get('snippet', '')
        if content and len(content.strip()) > 20:  # At least 20 characters
            has_meaningful_content = True
            total_content_length += len(content)
    
    # If we have meaningful content totaling more than 100 characters, consider it sufficient
    return has_meaningful_content and total_content_length > 100

# ══════════════════════════════════════════════════════════════════════════════
# DYNAMIC LANGUAGE-AWARE NODES
# ══════════════════════════════════════════════════════════════════════════════

def system_preamble_for_agent() -> str:
    """Base system prompt for the search agent with language protocol."""
    base_prompt = """You are a search agent. Your job is to:

1. FIRST: Detect the language of the user's query
2. Choose appropriate search tools based on the query
3. Respond using tool calls in the same language as the user

Tool Selection Guidelines:
- Use `tavily_search` for latest, current, breaking, today/now queries
- Use `wikipedia_search` for background, historical, biographical, or evergreen facts  
- Use `duckduckgo_search` for broad browsing or general web answers

You may call multiple tools in sequence if needed to gather comprehensive information.
Do not provide final answers - just gather information using the tools."""

    return create_language_aware_prompt(base_prompt)

def classify_and_optimize_query(user_query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Advanced question classification with query optimization and intent detection.
    
    Args:
        user_query: The raw user question
        context: Optional context from previous interactions
        
    Returns:
        Dict with classification, optimized queries, intent analysis, and search strategy
    """
    
    # Enhanced classification prompt with multiple dimensions
    classification_prompt = f"""Analyze this question across multiple dimensions and provide comprehensive optimization:

            ORIGINAL QUESTION: "{user_query}"
            CONTEXT: {json.dumps(context or {}, indent=2)}

            ANALYSIS FRAMEWORK:
            1. COMPLEXITY: simple|moderate|complex
            2. INTENT TYPE: factual|analytical|comparative|temporal|predictive|procedural
            3. DOMAIN: technology|business|science|politics|entertainment|general
            4. TIME SENSITIVITY: historical|current|future|timeless
            5. ANSWER TYPE: definitive|exploratory|opinion|data_driven

            OPTIMIZATION TASKS:
            - Generate 3-5 optimized search queries (specific, focused, search-engine friendly)
            - Identify key entities and concepts that need clarification
            - Suggest query expansions for comprehensive coverage
            - Detect potential ambiguities or missing context

            Respond in JSON format:
            {{
                "analysis": {{
                    "complexity": "simple|moderate|complex",
                    "intent_type": "primary intent category",
                    "domain": "subject domain",
                    "time_sensitivity": "temporal aspect",
                    "answer_type": "expected response format",
                    "confidence": 0.85
                }},
                "optimization": {{
                    "optimized_queries": [
                        "specific search query 1",
                        "specific search query 2", 
                        "specific search query 3"
                    ],
                    "key_entities": ["entity1", "entity2"],
                    "query_expansions": ["broader context query"],
                    "potential_ambiguities": ["ambiguity1", "ambiguity2"],
                    "search_strategy": "detailed strategy explanation"
                }},
                "enhancement_suggestions": {{
                    "missing_context": ["what context might help"],
                    "clarification_needed": ["what needs clarification"],
                    "alternative_phrasings": ["alternative way to ask"]
                }}
            }}

            SEARCH QUERY OPTIMIZATION RULES:
            - Make queries specific and actionable
            - Include relevant keywords for search engines
            - Consider different angles and perspectives
            - Optimize for both broad and specific search engines
            - Include temporal markers when relevant"""

    try:
        response = llm.invoke([SystemMessage(content=classification_prompt)])
        result = json.loads(response.content.strip())
        
        # Validate required fields
        required_fields = ["analysis", "optimization", "enhancement_suggestions"]
        if not all(field in result for field in required_fields):
            raise ValueError("Missing required fields in classification response")
            
        return result
        
    except Exception as e:
        # Enhanced fallback with basic analysis
        return {
            "analysis": {
                "complexity": "moderate",
                "intent_type": "factual",
                "domain": "general",
                "time_sensitivity": "current",
                "answer_type": "exploratory",
                "confidence": 0.5
            },
            "optimization": {
                "optimized_queries": [user_query, f"{user_query} facts", f"{user_query} overview"],
                "key_entities": [],
                "query_expansions": [f"{user_query} detailed information"],
                "potential_ambiguities": ["Classification failed - using fallback"],
                "search_strategy": f"Fallback strategy due to error: {str(e)}"
            },
            "enhancement_suggestions": {
                "missing_context": [],
                "clarification_needed": [],
                "alternative_phrasings": []
            }
        }

def process_query_node(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced query processing with comprehensive analysis and optimization.
    """
    msgs = state["messages"]

    # Extract the latest user query
    user_query = ""
    for msg in reversed(msgs):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    # Build context from conversation history
    context = {
        "previous_language": state.get("current_language", "unknown"),
        "has_previous_searches": bool(state.get("search_results")),
        "conversation_length": len([m for m in msgs if isinstance(m, (HumanMessage, AIMessage))]),
        "previous_complexity": state.get("question_complexity")
    }

    # Enhanced classification and optimization
    analysis_result = classify_and_optimize_query(user_query, context)
    
    # Extract key information
    analysis = analysis_result["analysis"]
    optimization = analysis_result["optimization"]
    enhancements = analysis_result["enhancement_suggestions"]

    return {
        "user_query": user_query,
        "previous_language": state.get("current_language", "unknown"),
        "current_language": "unknown",
        "language_changed": False,
        "needs_clarification": False,
        "search_complete": False,
        "search_results": None,
        "is_generating": False,
        
        # Enhanced analysis data
        "question_complexity": analysis["complexity"],
        "intent_type": analysis["intent_type"],
        "domain": analysis["domain"],
        "time_sensitivity": analysis["time_sensitivity"],
        "answer_type": analysis["answer_type"],
        "analysis_confidence": analysis["confidence"],
        
        # Optimization data
        "optimized_queries": optimization["optimized_queries"],
        "key_entities": optimization["key_entities"],
        "query_expansions": optimization["query_expansions"],
        "potential_ambiguities": optimization["potential_ambiguities"],
        "search_strategy": optimization["search_strategy"],
        
        # Enhancement suggestions
        "missing_context": enhancements["missing_context"],
        "clarification_needed": enhancements["clarification_needed"],
        "alternative_phrasings": enhancements["alternative_phrasings"]
    }
def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced agent node that uses complexity classification for better search strategy.
    """
    msgs = state["messages"]
    state_update = {"is_generating": False}

    user_query = state.get("user_query", "")
    previous_language = state.get("previous_language", "unknown")
    complexity = state.get("question_complexity", "moderate")
    optimized_queries = state.get("optimized_queries", [user_query])
    query_strategy = state.get("query_strategy", "")

    # Check if we just got NEW tool results
    def has_new_tool_results():
        if state.get("search_complete"):
            return False

        for i in range(len(msgs) - 1, -1, -1):
            msg = msgs[i]
            if isinstance(msg, ToolMessage):
                for j in range(i - 1, -1, -1):
                    prev_msg = msgs[j]
                    if isinstance(prev_msg, AIMessage):
                        if hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
                            return True
                        else:
                            return False
                    elif isinstance(prev_msg, ToolMessage):
                        continue
                    else:
                        return False
                return False
            elif isinstance(msg, AIMessage):
                return False
        return False

    if has_new_tool_results():
        search_results = extract_search_results(state)
        state_update.update({
            "messages": msgs,
            "search_results": search_results,
            "search_complete": True,
        })
        return state_update

    if state.get("search_complete"):
        state_update["messages"] = msgs
        return state_update

    # Enhanced system prompt with complexity awareness
    base_system_prompt = f"""You are a search agent with complexity awareness.

QUESTION ANALYSIS:
- Original Question: "{user_query}"
- Complexity Level: {complexity.upper()}
- Strategy: {query_strategy}
- Optimized Queries: {', '.join(optimized_queries)}

SEARCH STRATEGY BY COMPLEXITY:
- SIMPLE: Use 1-2 focused searches with the most direct query
- MODERATE: Use 2-3 searches to cover different aspects thoroughly  
- COMPLEX: Use 3-4 comprehensive searches for deep research

AVAILABLE TOOLS:
- tavily_search: For latest, current, breaking, today/now queries
- wikipedia_search: For background, historical, biographical, or evergreen facts
- duckduckgo_search: For broad browsing or general web answers

Use the optimized queries provided, but adapt them to the most appropriate search tools.
Execute searches based on the complexity level - more complex questions need more comprehensive research."""

    # Prepare clean message list with complexity-aware system prompt
    clean_msgs = []
    
    language_context = ""
    if previous_language != "unknown":
        language_context = f"Previous conversation was in: {previous_language}. Detect if user switched languages."

    enhanced_prompt = create_language_aware_prompt(base_system_prompt, language_context)
    clean_msgs.append(SystemMessage(content=enhanced_prompt))

    # Add existing messages, skipping duplicate system messages
    for msg in msgs:
        if isinstance(msg, SystemMessage):
            continue
        clean_msgs.append(msg)

    response = llm_with_tools.invoke(clean_msgs)
    state_update["messages"] = [response]
    return state_update

def evaluate_results_node(state: AgentState) -> Dict[str, Any]:
    """Evaluate if search results are sufficient."""
    state_update = {"is_generating": False}
    
    search_results = state.get("search_results", [])
    if not search_results:
        search_results = extract_search_results(state)
    
    user_query = state.get("user_query", "")
    
    # Simple evaluation
    is_sufficient = evaluate_search_results_internal(user_query, search_results)
    
    if is_sufficient:
        state_update.update({
            "search_results": search_results,
            "needs_clarification": False,
            "search_complete": True,
            "user_query": user_query
        })
    else:
        state_update.update({
            "search_results": search_results,
            "needs_clarification": True,
            "search_complete": True,
            "user_query": user_query
        })
    
    return state_update

def request_clarification(state: AgentState) -> Dict[str, Any]:
    """
    Generate clarification request with language protocol.
    """
    state_update = {"is_generating": True}
    
    user_query = state.get("user_query", "")
    current_language = state.get("current_language", "unknown")
    
    # Base prompt for clarification
    base_prompt = f"""The user asked: "{user_query}"

        I couldn't find sufficient information to answer their question. Generate a polite clarification request asking the user to:
        1. Provide more specific details
        2. Rephrase with different keywords  
        3. Specify what aspect they're most interested in

        Keep it concise and helpful."""
    
    # Add language context
    language_context = f"User's query language appears to be: {current_language}" if current_language != "unknown" else "Detect the user's language from their query above"
    
    # Create language-aware prompt
    enforced_prompt = create_language_aware_prompt(base_prompt, language_context)
    
    clarification_response = llm_evaluator.invoke([
        SystemMessage(content=enforced_prompt)
    ])
    
    clarification_request = AIMessage(content=clarification_response.content)
    
    state_update.update({
        "messages": [clarification_request],
        "needs_clarification": True,
        "is_generating": False
    })
    return state_update

 


# IMPROVED VISUALIZATION LOGIC FOR BACKEND

def process_feedback(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced feedback processing that combines original intent with clarification
    to create an optimized query for better results.
    """
    msgs = state["messages"]
    
    # Get the latest feedback
    feedback = ""
    for msg in reversed(msgs):
        if isinstance(msg, HumanMessage):
            feedback = msg.content
            break
    
    # Get original query and context
    original_query = state.get("user_query", "")
    previous_language = state.get("current_language", "unknown")
    
    # Create query rewriting prompt
    rewriting_prompt = f"""INTELLIGENT QUERY REWRITING TASK:

ORIGINAL QUESTION: "{original_query}"
USER FEEDBACK/CLARIFICATION: "{feedback}"

CONTEXT FROM PREVIOUS ATTEMPT:
- Domain: {state.get('domain', 'unknown')}
- Intent: {state.get('intent_type', 'unknown')}
- Missing Context: {state.get('missing_context', [])}
- Clarifications Needed: {state.get('clarification_needed', [])}

TASK: Create an enhanced, comprehensive query that:
1. Combines the original intent with the user's clarification
2. Addresses any ambiguities or missing context
3. Is more specific and searchable
4. Maintains the user's core question while being more precise

OPTIMIZATION RULES:
- If feedback adds specificity, incorporate it into the query
- If feedback changes direction, follow the new direction while keeping relevant context
- If feedback provides examples, use them to clarify the scope
- Make the result more searchable and less ambiguous

Respond in JSON format:
{{
    "rewritten_query": "The enhanced, combined query",
    "reasoning": "Why this rewrite is better",
    "key_improvements": ["improvement1", "improvement2"],
    "search_focus": "What to prioritize in search results"
}}"""

    try:
        # Use the enhanced language protocol
        enhanced_prompt = create_language_aware_prompt(rewriting_prompt, 
            f"Original language: {previous_language}, maintain consistency")
        
        response = llm.invoke([SystemMessage(content=enhanced_prompt)])
        rewrite_result = json.loads(response.content.strip())
        
        enhanced_query = rewrite_result.get("rewritten_query", feedback)
        
    except Exception as e:
        # Fallback: combine original and feedback intelligently
        if len(feedback.strip()) < len(original_query.strip()):
            # Short feedback - likely clarification, combine them
            enhanced_query = f"{original_query} - specifically: {feedback}"
        else:
            # Long feedback - likely new direction, use feedback but note original context
            enhanced_query = feedback
    
    # Track language change capability
    return {
        "user_query": enhanced_query,
        "original_query": original_query,  # Keep for reference
        "feedback_provided": feedback,
        "previous_language": previous_language,
        "current_language": "unknown",  # Will be re-detected
        "language_changed": False,
        "needs_clarification": False,
        "search_complete": False,
        "search_results": None,
        "is_generating": False,
        "query_was_enhanced": True  # Flag for tracking improvements
    }
    
    
def build_llm_prompt(
    user_query: str,
    search_results: List[Dict[str, Any]],
    context: Dict[str, Any]
) -> str:
    sources = format_search_results_for_answer(search_results)

    return f"""
You are a senior data analyst and research expert.  
Answer the user's question using ONLY the provided search results.

Output formats:
- Use plain text for narrative
- Use <TABLE_DATA>...</TABLE_DATA> for structured tables
- Use <GRAPH_DATA>...</GRAPH_DATA> for visualizable chart data
- You may mix formats when appropriate

STRICT FORMATS (must be valid JSON inside tags):

1. <TABLE_DATA>
{{
  "columns": ["Column A", "Column B", "Column C"],
  "rows": [
    ["row1-col1", "row1-col2", "row1-col3"],
    ["row2-col1", "row2-col2", "row2-col3"]
  ]
}}
</TABLE_DATA>

2. <GRAPH_DATA>
{{
  "type": "bar" | "line" | "pie",
  "title": "Descriptive chart title",
  "data": [
    {{ "x": "Category A", "y": 123 }},
    {{ "x": "Category B", "y": 456 }}
  ],
  "xLabel": "X axis label",
  "yLabel": "Y axis label"
}}
</GRAPH_DATA>

QUESTION: {user_query}

CONTEXT HINTS:
- Complexity: {context.get("question_complexity", "moderate")}
- Intent: {context.get("intent_type", "factual")}
- Domain: {context.get("domain", "general")}

SEARCH RESULTS:
{sources}

INSTRUCTIONS:
1. **Summarise**: key facts or figures (≤3 bullets).  
2. **Analyse**: trends, anomalies, correlations, or drivers.  
3. **Insight**: practical meaning—why it matters and to whom.  
4. **Conclusion**: 1–2 clear takeaways or recommended next steps.  
5. Where numeric data is present, always provide BOTH:
   - A <TABLE_DATA> JSON table (columns + rows).  
   - A <GRAPH_DATA> JSON chart (choose bar/line/pie).  
6. Cite every claim inline with `[^source_index]` and list sources at the end in markdown.

Answer now.
"""


def final_answer_node(state: AgentState) -> Dict[str, Any]:
    state_update = {"is_generating": True}

    user_query       = state.get("user_query", "")
    search_results   = state.get("search_results", [])
    current_language = state.get("current_language", "unknown")

    # Lightweight context (no heavy analysis)
    context = {
        "question_complexity": state.get("question_complexity", "moderate"),
        "intent_type":        state.get("intent_type", "factual"),
        "domain":             state.get("domain", "general"),
    }

    prompt = build_llm_prompt(user_query, search_results, context)

    if current_language != "unknown":
        prompt = f"{prompt}\n\nRespond in the language: {current_language}"

    try:
        answer_response = llm_evaluator.invoke([SystemMessage(content=prompt)])

        state_update.update({
            "messages": [AIMessage(content=answer_response.content)],
            "is_generating": False,
            # Optional: store lightweight context for follow-ups
            "final_context": context,
        })

    except Exception as e:
        fallback = format_search_results_for_answer(search_results[:3])
        state_update.update({
            "messages": [AIMessage(
                content=f"I’m having trouble generating the full answer. "
                        f"Here’s a quick summary:\n\n{fallback}"
            )],
            "is_generating": False,
            "generation_error": str(e),
        })

    return state_update


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def route_after_agent(state: AgentState) -> str:
    """Route after agent node - check for tool calls or search completion."""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    if state.get("search_complete", False):
        return "evaluate_results"
    
    return "evaluate_results"

def route_after_evaluation(state: AgentState) -> str:
    """Route after evaluation - either to clarification or final answer."""
    needs_clarification = state.get("needs_clarification", False)
    
    if needs_clarification:
        return "request_clarification"
    else:
        return "final_answer"
    
    

# ══════════════════════════════════════════════════════════════════════════════
# BUILD THE DYNAMIC MULTILINGUAL GRAPH
# ══════════════════════════════════════════════════════════════════════════════

def build_agent():
    """
    Build a dynamic language-aware multilingual ReAct LangGraph.
    
    DYNAMIC LANGUAGE STRATEGY:
    1. Language detection happens naturally as LLM processes queries
    2. Universal language protocol ensures consistency
    3. Language can change between questions if user switches
    4. No predefined languages - handles any language LLM supports
    """
    workflow = StateGraph(AgentState)

    # Nodes with dynamic language awareness
    workflow.add_node("process_query", process_query_node)
    workflow.add_node("agent", agent_node)              # Language detection happens here naturally
    workflow.add_node("tools", ToolNode(TOOLS))
    workflow.add_node("evaluate_results", evaluate_results_node)
    workflow.add_node("request_clarification", request_clarification)  # Language-aware responses
    workflow.add_node("process_feedback", process_feedback)            # Handles language changes  
    workflow.add_node("final_answer", final_answer_node)              # Language-aware answers

    # Flow control
     # Entry point
    workflow.set_entry_point("process_query")
    
    workflow.add_edge("process_query", "agent")
    
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools": "tools", 
            "evaluate_results": "evaluate_results"
        }
    )

    workflow.add_edge("tools", "agent")
    
    workflow.add_conditional_edges(
        "evaluate_results",
        route_after_evaluation,
        {
            "request_clarification": "request_clarification",
            "final_answer": "final_answer"
        }
    )
    
    workflow.add_edge("request_clarification", "process_feedback")
    workflow.add_edge("process_feedback", "process_query")
    workflow.add_edge("final_answer", END)

   

    return workflow.compile(interrupt_after=["request_clarification"])

 
app = build_agent()

 