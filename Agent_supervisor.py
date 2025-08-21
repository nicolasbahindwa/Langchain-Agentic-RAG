from __future__ import annotations

from typing import List, Dict, Any, TypedDict, Annotated, Optional, Callable
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field

# ── Your LLM manager (adjust provider/model as you like) ──────────────────────
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import create_search_manager  # your search manager

import json
import ast 

# Initialize managers
llm_manager = LLMManager()
# "Brain" that decides tools and drafts answers (bind tools to this one)
llm = llm_manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.2,  # low temp for tool-choice stability
    max_tokens=2000,
)

# Separate LLM for evaluation and answer generation (could use a more powerful model)
llm_evaluator = llm_manager.get_chat_model(
    provider=LLMProvider.OPENAI,
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=4000,
)

# ── STATE ─────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    """Conversation state (messages is auto-managed by LangGraph)."""
    messages: Annotated[List[BaseMessage], add_messages]
    # Track if we need human clarification
    needs_clarification: bool
    # Store search results for evaluation
    search_results: Optional[List[Dict[str, Any]]]
    # Store the original user query
    user_query: str
    # Track if we've completed search phase
    search_complete: bool

# ── TOOLS ─────────────────────────────────────────────────────────────────────
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
        
        # Convert SearchResult objects to plain dictionaries
        search_results = []
        for result in res.get("search_results", []):
            if hasattr(result, '__dict__'):
                # It's a SearchResult object, convert to dict
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
                # Already a dict
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
        
        # Convert SearchResult objects to plain dictionaries
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
        
        # Convert SearchResult objects to plain dictionaries
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

# Bind tools to the LLM (this is the "ReAct flavor")
llm_with_tools = llm.bind_tools(TOOLS)

# ── NODES ─────────────────────────────────────────────────────────────────────
def system_preamble() -> SystemMessage:
    """Strong routing hints so the model picks the right search tool."""
    return SystemMessage(content=(
        "You are a search agent. Your ONLY job is to decide which search tools to call.\n"
        "IMPORTANT: Do NOT try to answer the user's question directly. Only call search tools.\n"
        "Choose tools based on the user's intent:\n"
        "- Use `tavily_search` for latest, current, breaking, today/now queries.\n"
        "- Use `wikipedia_search` for background, historical, biographical, or evergreen facts.\n"
        "- Use `duckduckgo_search` for broad browsing or general web answers.\n"
        "You may call multiple tools in sequence if needed to gather comprehensive information.\n"
        "Do not provide final answers - just gather information using the tools.\n"
    ))

# def agent_node(state: AgentState) -> Dict[str, Any]:
#     msgs = state["messages"]

#     last_human_message = next((m for m in reversed(msgs) if isinstance(m, HumanMessage)), None)
#     if last_human_message:
#         state["user_query"] = last_human_message.content

#     # Look for tool results
#     recent_tool_results = []
#     for msg in reversed(msgs):
#         if isinstance(msg, ToolMessage):
#             recent_tool_results.append(msg)
#         elif isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
#             break  # stop at the AI message that triggered the tool call

#     if recent_tool_results:
#         search_results = extract_search_results(state)
#         return {
#             "messages": [AIMessage(content="Search completed, ready for evaluation.")],
#             "search_results": search_results,
#             "search_complete": True,
#             "user_query": state["user_query"],
#         }

#     # If we already completed search, don’t search again
#     if state.get("search_complete", False):
#         return {"messages": [AIMessage(content="Search completed, ready for evaluation.")]}

#     # Ensure preamble is present
#     if not msgs or not isinstance(msgs[0], SystemMessage):
#         msgs = [system_preamble()] + msgs

#     # Make tool calls
#     response = llm_with_tools.invoke(msgs)
#     return {"messages": [response]}


def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node that:
    1. stores the original user query (once),
    2. decides which tools to call,
    3. after NEW tool results arrive, extracts the search_results list,
    4. keeps the ToolMessages in the conversation for downstream nodes.
    """
    msgs = state["messages"]

    # ------------------------------------------------------------------
    # 1. Cache the very first human query so later nodes can reference it
    # ------------------------------------------------------------------
    if not state.get("user_query"):
        for m in msgs:
            if isinstance(m, HumanMessage):
                state["user_query"] = m.content
                break

    # ------------------------------------------------------------------
    # 2. Ensure the system-preamble is at the top (only once)
    # ------------------------------------------------------------------
    if not msgs or not isinstance(msgs[0], SystemMessage):
        msgs = [system_preamble()] + msgs

    # ------------------------------------------------------------------
    # 3. Check if we just got NEW tool results (not previously processed)
    # ------------------------------------------------------------------
    def has_new_tool_results():
        """Check if the most recent message sequence has unprocessed tool results."""
        if state.get("search_complete"):
            return False
            
        # Look for the pattern: AIMessage with tool_calls followed by ToolMessage(s)
        for i in range(len(msgs) - 1, -1, -1):
            msg = msgs[i]
            if isinstance(msg, ToolMessage):
                # Found a tool message, check if there's a preceding AI message with tool_calls
                for j in range(i - 1, -1, -1):
                    prev_msg = msgs[j]
                    if isinstance(prev_msg, AIMessage):
                        if hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
                            return True  # Found new tool results
                        else:
                            return False  # Found AI message without tool calls
                    elif isinstance(prev_msg, ToolMessage):
                        continue  # Keep looking back through tool messages
                    else:
                        return False  # Found non-AI, non-tool message
                return False
            elif isinstance(msg, AIMessage):
                return False  # Found AI message before any tool messages
        return False

    if has_new_tool_results():
        print("DEBUG: Found new tool results, extracting search results...")
        search_results = extract_search_results(state)
        print(f"DEBUG: Extracted {len(search_results)} search results")
        
        return {
            "messages": msgs,  # Keep all existing messages
            "search_results": search_results,
            "search_complete": True,
            "user_query": state["user_query"],
        }

    # ------------------------------------------------------------------
    # 4. If search is already finished, do nothing (pass-through)
    # ------------------------------------------------------------------
    if state.get("search_complete"):
        print("DEBUG: Search already complete, passing through...")
        return {"messages": msgs}

    # ------------------------------------------------------------------
    # 5. Otherwise, decide next tool call(s) with the LLM
    # ------------------------------------------------------------------
    print("DEBUG: Making new tool calls...")
    response = llm_with_tools.invoke(msgs)
    
    # Debug: check if the response has tool calls
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print(f"DEBUG: LLM wants to call {len(response.tool_calls)} tools")
        for tool_call in response.tool_calls:
            print(f"  - {tool_call['name']} with args: {tool_call['args']}")
    else:
        print("DEBUG: LLM didn't request any tool calls")
    
    return {"messages": [response]}

def extract_search_results(state: AgentState) -> List[Dict[str, Any]]:
    """Extract search results from tool messages (simplified version for plain dicts)."""
    search_results = []
    
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage):
            try:
                # Parse the content
                if isinstance(msg.content, dict):
                    content = msg.content
                elif isinstance(msg.content, str):
                    content = json.loads(msg.content)
                else:
                    continue
                
                # Extract results
                if isinstance(content, dict) and 'search_results' in content:
                    results = content['search_results']
                    provider = content.get('provider', 'unknown')
                    
                    if isinstance(results, list):
                        for i, result in enumerate(results):
                            if isinstance(result, dict):
                                # Add source info
                                result['source'] = f"{provider} [{len(search_results) + i + 1}]"
                                search_results.append(result)
                            
            except Exception as e:
                print(f"Error parsing tool message: {e}")
                continue
    
    print(f"DEBUG: Successfully extracted {len(search_results)} search results")
    return search_results

def evaluate_results_node(state: AgentState) -> Dict[str, Any]:
    """
    Use LLM to evaluate if search results are sufficient or need clarification.
    Uses search_results from state (set by agent node).
    """
    # Get search results from state (should be set by agent node)
    search_results = state.get("search_results", [])
    
    # If state doesn't have results, try to extract them (fallback)
    if not search_results:
        search_results = extract_search_results(state)
    
    # Get the original user query
    user_query = state.get("user_query", "")
    if not user_query:
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage):
                user_query = msg.content
                break
    
    print(f"DEBUG: Evaluating {len(search_results)} search results for query: '{user_query}'")
    
    # If we have no search results at all, we definitely need clarification
    if not search_results:
        print("DEBUG: No search results found, requesting clarification")
        return {
            "search_results": search_results,
            "needs_clarification": True,
            "search_complete": True,
            "user_query": user_query
        }
    
    # Check if we have meaningful content in the results
    has_meaningful_content = False
    total_content_length = 0
    
    for result in search_results:
        content = result.get('content', '') or result.get('text', '') or result.get('snippet', '')
        title = result.get('title', '')
        
        if content and len(content.strip()) > 5:  # At least some substantial content
            has_meaningful_content = True
            total_content_length += len(content)
    
    # If we have meaningful content, be more lenient
    if has_meaningful_content and total_content_length > 50:
        print(f"DEBUG: Found meaningful content ({total_content_length} chars), marking as sufficient")
        return {
            "search_results": search_results,
            "needs_clarification": False,
            "search_complete": True,
            "user_query": user_query
        }
    
    # For edge cases, use LLM evaluation but with better prompting
    evaluation_prompt = f"""
    You are evaluating search results for the query: "{user_query}"
    
    SEARCH RESULTS SUMMARY:
    Number of results: {len(search_results)}
    Results found: {format_search_results_for_evaluation(search_results)}
    
    The user wants to know about this topic. Look at the search results above.
    
    IMPORTANT EVALUATION CRITERIA:
    - If there are search results with relevant titles and content, even if not perfect, mark as SUFFICIENT
    - Only mark as NEEDS_CLARIFICATION if the results are completely empty, irrelevant, or contain no useful information
    - Be generous - if there's ANY useful information that could help answer the query, mark as SUFFICIENT
    
    Examples of when to mark SUFFICIENT:
    - Results about the topic exist, even if not perfectly current
    - General information about the subject is available
    - Related or background information is present
    
    Examples of when to mark NEEDS_CLARIFICATION:
    - No search results at all
    - All results are completely unrelated to the query
    - Results contain only error messages or empty content
    
    Based on the search results above, respond with EXACTLY one word:
    - "SUFFICIENT" (if there's any useful information about the topic)
    - "NEEDS_CLARIFICATION" (only if results are empty or completely irrelevant)
    """
    
    # Get evaluation from LLM
    evaluation_response = llm_evaluator.invoke([
        SystemMessage(content="You are a search results evaluator. Be generous - if there's any useful information, mark as sufficient. Only request clarification if results are truly empty or irrelevant."),
        HumanMessage(content=evaluation_prompt)
    ])
    
    evaluation = evaluation_response.content.strip().upper()
    print(f"DEBUG: LLM evaluation result: '{evaluation}'")
    
    # Default to sufficient if evaluation is unclear
    needs_clarification = "NEEDS_CLARIFICATION" in evaluation
    
    # Extra safety: if we have any results with content, don't ask for clarification
    if not needs_clarification or has_meaningful_content:
        print("DEBUG: Final decision: SUFFICIENT")
        return {
            "search_results": search_results,
            "needs_clarification": False,
            "search_complete": True,
            "user_query": user_query
        }
    else:
        print("DEBUG: Final decision: NEEDS_CLARIFICATION")
        return {
            "search_results": search_results,
            "needs_clarification": True,
            "search_complete": True,
            "user_query": user_query
        }

def format_search_results_for_evaluation(results: List[Dict[str, Any]]) -> str:
    """Format search results for evaluation prompt."""
    if not results:
        return "No search results found."
    
    formatted = []
    for i, result in enumerate(results, 1):
        source = result.get('source', f'Result {i}')
        content = result.get('content', result.get('text', result.get('snippet', 'No content')))
        title = result.get('title', '')
        
        formatted.append(f"{source}: {title}\n{content}\n")
    
    return "\n".join(formatted[:10])  # Limit to first 10 results for evaluation

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

def request_clarification(state: AgentState) -> Dict[str, Any]:
    """
    Node to request human clarification when search results are insufficient.
    """
    user_query = state.get("user_query", "the query")
    
    clarification_request = AIMessage(
        content=f"I searched for information about '{user_query}', but I couldn't find sufficient relevant results. Could you please:\n\n"
                f"1. Provide more specific details about what you're looking for\n"
                f"2. Try rephrasing your question with different keywords\n"
                f"3. Let me know if there's a particular aspect you're most interested in\n\n"
                f"This will help me search more effectively for you."
    )
    
    return {
        "messages": [clarification_request],
        "needs_clarification": True
    }

def process_feedback(state: AgentState) -> Dict[str, Any]:
    """
    Process human feedback and prepare for a new search.
    """
    # Find the latest human message (the feedback)
    feedback = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            feedback = msg.content
            break   
    
    # Reset search state for new query
    return {
        "messages": state["messages"],  # Keep all messages
        "user_query": feedback,
        "needs_clarification": False,
        "search_complete": False,
        "search_results": None
    }

def final_answer_node(state: AgentState) -> Dict[str, Any]:
    """
    Generate a comprehensive, well-structured markdown answer using LLM.
    """
    search_results = state.get("search_results", [])
    user_query = state.get("user_query", "")
    
    # Prepare prompt for answer generation
    answer_prompt = f"""
    Based on the search results below, provide a comprehensive answer to this question: "{user_query}"

    Format your response as a well-structured markdown document with:
    - A clear, direct answer to the question
    - Organized sections with appropriate headings (##, ###)
    - Key information highlighted with **bold text**
    - Bullet points or numbered lists where appropriate
    - Inline citations using [1], [2], etc. that reference the sources
    - A "Sources" section at the end listing all referenced sources

    SEARCH RESULTS:
    {format_search_results_for_answer(search_results)}

    Important guidelines:
    - Answer the user's question directly and comprehensively
    - Use clear, accessible language
    - Organize information logically
    - Include relevant details but stay focused on the question
    - Cite your sources appropriately
    """
    
    # Generate answer with LLM
    answer_response = llm_evaluator.invoke([
        SystemMessage(content="You are a helpful research assistant. Create comprehensive, well-structured answers in markdown format with proper citations."),
        HumanMessage(content=answer_prompt)
    ])
    
    return {"messages": [AIMessage(content=answer_response.content)]}

# ── CONDITIONAL ROUTING FUNCTIONS ─────────────────────────────────────────────
# def route_after_agent(state: AgentState) -> str:
#     """Route after agent node - either to tools or to evaluation."""
#     last_message = state["messages"][-1]
    
#     # If the agent wants to use tools, go to tools
#     if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
#         return "tools"
    
#     # If search is complete (agent has processed tool results), go to evaluation
#     if state.get("search_complete", False):
#         return "evaluate_results"
    
#     # Otherwise, go to evaluation (this shouldn't happen but is a safeguard)
#     return "evaluate_results"

def route_after_agent(state: AgentState) -> str:
    """Route after agent node - check for tool calls or search completion."""
    last_message = state["messages"][-1]
    
    # If the agent wants to use tools, go to tools
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        print("DEBUG: Routing to tools (agent made tool calls)")
        return "tools"
    
    # If search is marked as complete, go to evaluation
    if state.get("search_complete", False):
        print("DEBUG: Routing to evaluation (search complete)")
        return "evaluate_results"
    
    # Otherwise, something went wrong - log and go to evaluation as fallback
    print("DEBUG: Unexpected state in routing, going to evaluation as fallback")
    print(f"  Last message type: {type(last_message)}")
    print(f"  Has tool_calls: {hasattr(last_message, 'tool_calls')}")
    print(f"  Search complete: {state.get('search_complete', False)}")
    return "evaluate_results"

def route_after_evaluation(state: AgentState) -> str:
    """Route after evaluation - either to clarification or final answer."""
    needs_clarification = state.get("needs_clarification", False)
    search_results_count = len(state.get("search_results", []))
    
    print(f"DEBUG: Evaluation routing - needs_clarification: {needs_clarification}, results: {search_results_count}")
    
    if needs_clarification:
        print("DEBUG: Routing to request_clarification")
        return "request_clarification"
    else:
        print("DEBUG: Routing to final_answer")
        return "final_answer"

# ── GRAPH ─────────────────────────────────────────────────────────────────────
def build_agent():
    """
    Build a ReAct LangGraph with human interruption only when clarification is needed.
    """
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(TOOLS))
    workflow.add_node("evaluate_results", evaluate_results_node)
    workflow.add_node("request_clarification", request_clarification)
    workflow.add_node("process_feedback", process_feedback)
    workflow.add_node("final_answer", final_answer_node)

    # Flow control
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools": "tools", 
            "evaluate_results": "evaluate_results"
        }
    )

    # After tools execute, return to agent to potentially search more or complete
    workflow.add_edge("tools", "agent")
    
    # After evaluation, decide next steps
    workflow.add_conditional_edges(
        "evaluate_results",
        route_after_evaluation,
        {
            "request_clarification": "request_clarification",
            "final_answer": "final_answer"
        }
    )
    
    # After requesting clarification, process the feedback
    workflow.add_edge("request_clarification", "process_feedback")
    
    # After processing feedback, start over with the agent
    workflow.add_edge("process_feedback", "agent")
    
    # Final answer ends the conversation
    workflow.add_edge("final_answer", END)

    # Entry point
    workflow.set_entry_point("agent")

    # Compile with interrupt after request_clarification
    return workflow.compile(interrupt_after=["request_clarification"])

# Create the agent
app = build_agent()

# Sync test function
def run_once(question: str):
    """Test function with enhanced debugging to track the flow."""
    print(f"🚀 Starting query: '{question}'")
    print("=" * 60)
    
    initial_state = {
        "messages": [HumanMessage(content=question)],
        "needs_clarification": False,
        "search_results": None,
        "user_query": question,
        "search_complete": False
    }
    
    try:
        result = app.invoke(initial_state)
        
        print("\n📊 FINAL STATE SUMMARY:")
        print(f"  🔍 Search complete: {result.get('search_complete')}")
        print(f"  ❓ Needs clarification: {result.get('needs_clarification')}")
        print(f"  📄 Search results count: {len(result.get('search_results', []))}")
        print(f"  💬 Total messages: {len(result.get('messages', []))}")
        
        # Show message types in order
        print("\n📝 MESSAGE FLOW:")
        for i, msg in enumerate(result.get('messages', [])):
            msg_type = type(msg).__name__
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"  {i}: {msg_type} (with {len(msg.tool_calls)} tool calls)")
            else:
                content_preview = (msg.content[:50] + "...") if len(msg.content) > 50 else msg.content
                print(f"  {i}: {msg_type} - {content_preview}")
        
        # Show search results summary
        search_results = result.get('search_results', [])
        if search_results:
            print(f"\n🔍 SEARCH RESULTS SUMMARY ({len(search_results)} results):")
            for i, result_item in enumerate(search_results[:3]):  # Show first 3
                title = result_item.get('title', 'No title')[:60]
                source = result_item.get('source', 'Unknown source')
                print(f"  {i+1}. [{source}] {title}")
            if len(search_results) > 3:
                print(f"  ... and {len(search_results) - 3} more results")
        
        # Show the final answer
        final_ai = next((m for m in reversed(result["messages"]) if isinstance(m, AIMessage)), None)
        if final_ai:
            print("\n✅ FINAL ANSWER:")
            print("-" * 40)
            print(final_ai.content)
        else:
            print("\n❌ No final AI message found")
            
    except Exception as e:
        print(f"\n💥 ERROR during execution: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    return result

# Enhanced run with step-by-step execution for debugging
def run_step_by_step(question: str):
    """Run the agent step by step to see each node execution."""
    print(f"🔧 STEP-BY-STEP EXECUTION for: '{question}'")
    print("=" * 60)
    
    config = {"recursion_limit": 50}
    inputs = {
        "messages": [HumanMessage(content=question)],
        "needs_clarification": False,
        "search_results": None,
        "user_query": question,
        "search_complete": False
    }
    
    step = 1
    for chunk in app.stream(inputs, config=config):
        print(f"\n🔄 STEP {step}:")
        for node_name, node_output in chunk.items():
            print(f"  📍 Node: {node_name}")
            if 'search_results' in node_output:
                count = len(node_output['search_results'] or [])
                print(f"    📊 Search results: {count}")
            if 'search_complete' in node_output:
                print(f"    ✅ Search complete: {node_output['search_complete']}")
            if 'needs_clarification' in node_output:
                print(f"    ❓ Needs clarification: {node_output['needs_clarification']}")
            
            # Show last message added
            messages = node_output.get('messages', [])
            if messages:
                last_msg = messages[-1]
                msg_type = type(last_msg).__name__
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    print(f"    💬 Added: {msg_type} (with {len(last_msg.tool_calls)} tool calls)")
                else:
                    content_preview = (last_msg.content[:50] + "...") if len(last_msg.content) > 50 else last_msg.content
                    print(f"    💬 Added: {msg_type} - {content_preview}")
        step += 1
    
    print(f"\n🏁 Execution completed in {step-1} steps")

if __name__ == "__main__":
    print("Testing the ReAct Agent...")
    print("\n" + "="*50)
    
    print("Test 1: Recent AI Research")
    run_once("What happened in AI research last week?")
    
    print("\n" + "="*50)
    print("Test 2: Historical Biography")
    run_once("Give me a short biography of Ada Lovelace.")
    
    print("\n" + "="*50)
    print("Test 3: General Web Search")
    run_once("Find beginner guides for baking chocolate chip cookies.")