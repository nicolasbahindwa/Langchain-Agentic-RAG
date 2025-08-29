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

# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL LANGUAGE PROTOCOL SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

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

def process_query_node(state: AgentState) -> Dict[str, Any]:
    """
    Extract user query and prepare for language-aware processing.
    Language detection will happen naturally in the agent node.
    """
    msgs = state["messages"]
    
    # Get the latest user query
    user_query = ""
    for msg in reversed(msgs):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
    
    # Get previous language state
    previous_language = state.get("current_language", "unknown")
    
    return {
        "user_query": user_query,
        "previous_language": previous_language,
        "current_language": "unknown",  # Will be updated by LLM
        "language_changed": False,
        "needs_clarification": False,
        "search_complete": False,
        "search_results": None,
        "is_generating": False
    }

def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node that detects language and decides which tools to call.
    """
    msgs = state["messages"]
    state_update = {"is_generating": False}
    
    user_query = state.get("user_query", "")
    previous_language = state.get("previous_language", "unknown")

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

    # If search is already finished, do nothing
    if state.get("search_complete"):
        state_update["messages"] = msgs
        return state_update

    # Prepare clean message list for LLM with language-aware system prompt
    clean_msgs = []
    
    # Add language-aware system message with context about previous language
    language_context = ""
    if previous_language != "unknown":
        language_context = f"Previous conversation was in: {previous_language}. Detect if user switched languages."
    
    system_prompt = create_language_aware_prompt(
        system_preamble_for_agent(), 
        language_context
    )
    clean_msgs.append(SystemMessage(content=system_prompt))
    
    # Add existing messages, skipping duplicate system messages
    for msg in msgs:
        if isinstance(msg, SystemMessage):
            continue  # Skip, we already added our language-aware system message
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

def process_feedback(state: AgentState) -> Dict[str, Any]:
    """
    Process human feedback and prepare for new search.
    Allow language to change if user switches languages.
    """
    # Find the latest human message (the feedback)
    feedback = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            feedback = msg.content
            break   
    
    # Keep track of previous language for comparison
    previous_language = state.get("current_language", "unknown")
    
    # Reset search state for new query, allow language detection on new feedback
    return {
        "user_query": feedback,
        "previous_language": previous_language,  # Track previous for comparison
        "current_language": "unknown",  # Will be re-detected
        "language_changed": False,
        "needs_clarification": False,
        "search_complete": False,
        "search_results": None,
        "is_generating": False
    }


def final_answer_node(state: AgentState) -> Dict[str, Any]:
    """
    Generate comprehensive answer with language protocol and multiple format options.
    """
    state_update = {"is_generating": True}
    
    search_results = state.get("search_results", [])
    user_query = state.get("user_query", "")
    current_language = state.get("current_language", "unknown")
    
    # Enhanced base prompt with multiple format options
    base_prompt = f"""User question: "{user_query}"

Based on the search results below, provide a comprehensive answer in the MOST APPROPRIATE format:

AVAILABLE FORMATS:
1. TEXT: For general information, explanations, and narratives
2. TABLE: For comparative data, lists, statistics, or structured information
3. GRAPH: For trends, relationships, quantitative data, or visual patterns
4. SOURCE CODE: For code examples, algorithms, or programming solutions
5. PICTURE/IMAGE: For visual content (describe images found in search results)

Choose the best format based on the content:
- Use TABLES for data that can be compared side-by-side
- Use GRAPHS for showing trends, distributions, or relationships
- Use TEXT for explanations, stories, or unstructured information
- Use SOURCE CODE for programming-related queries
- Use PICTURE/IMAGE descriptions when visual content is relevant

FORMATTING GUIDELINES:
For TABLES:
- Create a markdown table with clear headers
- Ensure data is properly aligned
- Include a title explaining what the table shows

For GRAPHS:
- Describe the graph type (bar, line, pie, scatter, etc.)
- Provide the data points in a structured format
- Explain what the graph demonstrates
- Use format: "GRAPH: [chart type] showing [title]\nDATA: x=[values], y=[values]"

For SOURCE CODE:
- Use markdown code blocks with language specification
- Include comments and explanations
- Format: ```python\n# Your code here\n```

For PICTURES/IMAGES:
- Describe the image content in detail
- Mention if any images were found in search results
- Include image URLs if available

SEARCH RESULTS:
{format_search_results_for_answer(search_results)}

Provide your answer in the most appropriate format for the content. If multiple formats are suitable, combine them effectively."""

    # Add language context
    language_context = f"User's query language: {current_language}. Translate any English sources naturally." if current_language != "unknown" else "Detect user's language and respond in the same language"
    
    # Create language-aware prompt
    enforced_prompt = create_language_aware_prompt(base_prompt, language_context)
    
    answer_response = llm_evaluator.invoke([
        SystemMessage(content=enforced_prompt)
    ])
    
    state_update.update({
        "messages": [AIMessage(content=answer_response.content)],
        "is_generating": False
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

 