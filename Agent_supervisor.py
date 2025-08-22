# from __future__ import annotations

# from typing import List, Dict, Any, TypedDict, Annotated, Optional, Callable
# from langgraph.graph import StateGraph, END
# from langgraph.graph.message import add_messages
# from langgraph.prebuilt import ToolNode, tools_condition
# from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
# from langchain_core.tools import tool
# from langchain_core.pydantic_v1 import BaseModel, Field
# from datetime import datetime

# # ── Your LLM manager (adjust provider/model as you like) ──────────────────────
# from core.llm_manager import LLMManager, LLMProvider
# from core.search_manager import create_search_manager  # your search manager

# import json

# # Initialize managers
# llm_manager = LLMManager()
# # "Brain" that decides tools and drafts answers (bind tools to this one)
# llm = llm_manager.get_chat_model(
#     provider=LLMProvider.ANTHROPIC,
#     model="claude-3-haiku-20240307",
#     temperature=0.2,  # low temp for tool-choice stability
#     max_tokens=2000,
# )

# # Separate LLM for evaluation and answer generation (could use a more powerful model)
# llm_evaluator = llm_manager.get_chat_model(
#     provider=LLMProvider.OPENAI,
#     model="gpt-4o-mini",
#     temperature=0.1,
#     max_tokens=4000,
# )

# # ── LOADING MESSAGE HELPER ───────────────────────────────────────────────────
# class LoadingMessage:
#     """Helper class to manage loading messages with timestamps."""
    
#     def __init__(self, message: str, level: str = "info"):
#         self.message = message
#         self.level = level  # info, debug, warning, error, success
#         self.timestamp = datetime.now().isoformat()
    
#     def __str__(self):
#         return f"[{self.timestamp}] {self.level.upper()}: {self.message}"
    
#     def to_dict(self):
#         return {
#             "message": self.message,
#             "level": self.level,
#             "timestamp": self.timestamp
#         }

# def add_loading_message(state: Dict[str, Any], message: str, level: str = "info") -> None:
#     """Add a loading message to the state."""
#     if "loading_messages" not in state:
#         state["loading_messages"] = []
    
#     loading_msg = LoadingMessage(message, level)
#     state["loading_messages"].append(loading_msg.to_dict())

# def print_loading_messages(state: Dict[str, Any], show_all: bool = False, level_filter: List[str] = None) -> None:
#     """Print loading messages from state. Optionally filter by level."""
#     loading_messages = state.get("loading_messages", [])
    
#     if not loading_messages:
#         return
    
#     if level_filter is None:
#         level_filter = ["info", "success", "warning", "error"]
    
#     if show_all:
#         messages_to_show = loading_messages
#     else:
#         # Show only the last few messages
#         messages_to_show = loading_messages[-5:]
    
#     for msg_data in messages_to_show:
#         if msg_data["level"] in level_filter:
#             timestamp = msg_data["timestamp"].split("T")[1][:8]  # Just time part
#             level_emoji = {
#                 "info": "ℹ️",
#                 "debug": "🔧",
#                 "success": "✅", 
#                 "warning": "⚠️",
#                 "error": "❌"
#             }.get(msg_data["level"], "📝")
            
#             print(f"{level_emoji} [{timestamp}] {msg_data['message']}")

# # ── STATE ─────────────────────────────────────────────────────────────────────
# class AgentState(TypedDict):
#     """Conversation state (messages is auto-managed by LangGraph)."""
#     messages: Annotated[List[BaseMessage], add_messages]
#     # Track if we need human clarification
#     needs_clarification: bool
#     # Store search results for evaluation
#     search_results: Optional[List[Dict[str, Any]]]
#     # Store the original user query
#     user_query: str
#     # Track if we've completed search phase
#     search_complete: bool
#     # Store loading messages for user feedback
#     loading_messages: List[Dict[str, Any]]

# # ── TOOLS ─────────────────────────────────────────────────────────────────────
# search_manager = create_search_manager()

# class SearchInput(BaseModel):
#     query: str = Field(description="The search query string.")

# @tool("tavily_search", args_schema=SearchInput)
# def tavily_search(query: str) -> Dict[str, Any]:
#     """Use Tavily for *latest* or *current* info (news, what's new, today/now)."""
#     try:
#         res = search_manager.search(
#             query=query,
#             provider="tavily",
#             max_results=6,
#             search_depth="advanced",
#         )
        
#         # Convert SearchResult objects to plain dictionaries
#         search_results = []
#         for result in res.get("search_results", []):
#             if hasattr(result, '__dict__'):
#                 # It's a SearchResult object, convert to dict
#                 result_dict = {
#                     'title': getattr(result, 'title', ''),
#                     'url': getattr(result, 'url', ''),
#                     'content': getattr(result, 'content', ''),
#                     'snippet': getattr(result, 'snippet', ''),
#                     'score': getattr(result, 'score', 0),
#                     'published_date': getattr(result, 'published_date', ''),
#                     'metadata': getattr(result, 'metadata', {}),
#                 }
#             else:
#                 # Already a dict
#                 result_dict = result
#             search_results.append(result_dict)
        
#         return {
#             "provider": "tavily",
#             "query": query,
#             "search_results": search_results,
#         }
#     except Exception as e:
#         return {"provider": "tavily", "query": query, "error": str(e)}

# @tool("wikipedia_search", args_schema=SearchInput)
# def wikipedia_search(query: str) -> Dict[str, Any]:
#     """Use Wikipedia for background, historical, or evergreen facts."""
#     try:
#         res = search_manager.search(
#             query=query,
#             provider="wikipedia",
#             max_results=4,
#             full_content=False,
#             summary_sentences=4,
#         )
        
#         # Convert SearchResult objects to plain dictionaries
#         search_results = []
#         for result in res.get("search_results", []):
#             if hasattr(result, '__dict__'):
#                 result_dict = {
#                     'title': getattr(result, 'title', ''),
#                     'url': getattr(result, 'url', ''),
#                     'content': getattr(result, 'content', ''),
#                     'snippet': getattr(result, 'snippet', ''),
#                     'score': getattr(result, 'score', 0),
#                     'published_date': getattr(result, 'published_date', ''),
#                     'metadata': getattr(result, 'metadata', {}),
#                 }
#             else:
#                 result_dict = result
#             search_results.append(result_dict)
        
#         return {
#             "provider": "wikipedia",
#             "query": query,
#             "search_results": search_results,
#         }
#     except Exception as e:
#         return {"provider": "wikipedia", "query": query, "error": str(e)}

# @tool("duckduckgo_search", args_schema=SearchInput)
# def duckduckgo_search(query: str) -> Dict[str, Any]:
#     """Use DuckDuckGo for general browsing, mixed web results, or broad queries."""
#     try:
#         res = search_manager.search(
#             query=query,
#             provider="duckduckgo",
#             max_results=6,
#             region="wt-wt",
#             safesearch="moderate",
#         )
        
#         # Convert SearchResult objects to plain dictionaries
#         search_results = []
#         for result in res.get("search_results", []):
#             if hasattr(result, '__dict__'):
#                 result_dict = {
#                     'title': getattr(result, 'title', ''),
#                     'url': getattr(result, 'url', ''),
#                     'content': getattr(result, 'content', ''),
#                     'snippet': getattr(result, 'snippet', ''),
#                     'score': getattr(result, 'score', 0),
#                     'published_date': getattr(result, 'published_date', ''),
#                     'metadata': getattr(result, 'metadata', {}),
#                 }
#             else:
#                 result_dict = result
#             search_results.append(result_dict)
        
#         return {
#             "provider": "duckduckgo",
#             "query": query,
#             "search_results": search_results,
#         }
#     except Exception as e:
#         return {"provider": "duckduckgo", "query": query, "error": str(e)}

# # Tools list
# TOOLS = [tavily_search, wikipedia_search, duckduckgo_search]

# # Bind tools to the LLM (this is the "ReAct flavor")
# llm_with_tools = llm.bind_tools(TOOLS)

# # ── NODES ─────────────────────────────────────────────────────────────────────
# def system_preamble() -> SystemMessage:
#     """Strong routing hints so the model picks the right search tool."""
#     return SystemMessage(content=(
#         "You are a search agent. Your ONLY job is to decide which search tools to call.\n"
#         "IMPORTANT: Do NOT try to answer the user's question directly. Only call search tools.\n"
#         "Choose tools based on the user's intent:\n"
#         "- Use `tavily_search` for latest, current, breaking, today/now queries.\n"
#         "- Use `wikipedia_search` for background, historical, biographical, or evergreen facts.\n"
#         "- Use `duckduckgo_search` for broad browsing or general web answers.\n"
#         "You may call multiple tools in sequence if needed to gather comprehensive information.\n"
#         "Do not provide final answers - just gather information using the tools.\n"
#     ))

# def agent_node(state: AgentState) -> Dict[str, Any]:
#     """
#     LangGraph node that:
#     1. stores the original user query (once),
#     2. decides which tools to call,
#     3. after NEW tool results arrive, extracts the search_results list,
#     4. keeps the ToolMessages in the conversation for downstream nodes.
#     """
#     msgs = state["messages"]

#     # Initialize state with loading messages if not present
#     state_update = {}
#     if "loading_messages" not in state:
#         state_update["loading_messages"] = []

#     # ------------------------------------------------------------------
#     # 1. Cache the very first human query so later nodes can reference it
#     # ------------------------------------------------------------------
#     if not state.get("user_query"):
#         for m in msgs:
#             if isinstance(m, HumanMessage):
#                 state_update["user_query"] = m.content
#                 add_loading_message(state_update, f"Starting research for query: '{m.content}'", "info")
#                 break

#     # ------------------------------------------------------------------
#     # 2. Ensure the system-preamble is at the top (only once)
#     # ------------------------------------------------------------------
#     if not msgs or not isinstance(msgs[0], SystemMessage):
#         msgs = [system_preamble()] + msgs
#         add_loading_message(state_update, "Initialized search agent system", "debug")

#     # ------------------------------------------------------------------
#     # 3. Check if we just got NEW tool results (not previously processed)
#     # ------------------------------------------------------------------
#     def has_new_tool_results():
#         """Check if the most recent message sequence has unprocessed tool results."""
#         if state.get("search_complete"):
#             return False
            
#         # Look for the pattern: AIMessage with tool_calls followed by ToolMessage(s)
#         for i in range(len(msgs) - 1, -1, -1):
#             msg = msgs[i]
#             if isinstance(msg, ToolMessage):
#                 # Found a tool message, check if there's a preceding AI message with tool_calls
#                 for j in range(i - 1, -1, -1):
#                     prev_msg = msgs[j]
#                     if isinstance(prev_msg, AIMessage):
#                         if hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
#                             return True  # Found new tool results
#                         else:
#                             return False  # Found AI message without tool calls
#                     elif isinstance(prev_msg, ToolMessage):
#                         continue  # Keep looking back through tool messages
#                     else:
#                         return False  # Found non-AI, non-tool message
#                 return False
#             elif isinstance(msg, AIMessage):
#                 return False  # Found AI message before any tool messages
#         return False

#     if has_new_tool_results():
#         add_loading_message(state_update, "Processing search results from tools", "info")
#         search_results = extract_search_results(state)
#         add_loading_message(state_update, f"Extracted {len(search_results)} search results", "success")
        
#         state_update.update({
#             "messages": msgs,  # Keep all existing messages
#             "search_results": search_results,
#             "search_complete": True,
#         })
#         return state_update

#     # ------------------------------------------------------------------
#     # 4. If search is already finished, do nothing (pass-through)
#     # ------------------------------------------------------------------
#     if state.get("search_complete"):
#         add_loading_message(state_update, "Search already completed, proceeding to next phase", "debug")
#         state_update["messages"] = msgs
#         return state_update

#     # ------------------------------------------------------------------
#     # 5. Otherwise, decide next tool call(s) with the LLM
#     # ------------------------------------------------------------------
#     add_loading_message(state_update, "Analyzing query to determine best search strategy", "info")
#     response = llm_with_tools.invoke(msgs)
    
#     # Log what tools the agent wants to call
#     if hasattr(response, 'tool_calls') and response.tool_calls:
#         tool_names = [tool_call['name'] for tool_call in response.tool_calls]
#         add_loading_message(state_update, f"Planning to search using: {', '.join(tool_names)}", "info")
#         for tool_call in response.tool_calls:
#             query = tool_call['args'].get('query', 'unknown')
#             add_loading_message(state_update, f"Preparing {tool_call['name']} search: '{query}'", "debug")
#     else:
#         add_loading_message(state_update, "No search tools selected by agent", "warning")
    
#     state_update["messages"] = [response]
#     return state_update

# def extract_search_results(state: AgentState) -> List[Dict[str, Any]]:
#     """Extract search results from tool messages (simplified version for plain dicts)."""
#     search_results = []
    
#     for msg in reversed(state["messages"]):
#         if isinstance(msg, ToolMessage):
#             try:
#                 # Parse the content
#                 if isinstance(msg.content, dict):
#                     content = msg.content
#                 elif isinstance(msg.content, str):
#                     content = json.loads(msg.content)
#                 else:
#                     continue
                
#                 # Extract results
#                 if isinstance(content, dict) and 'search_results' in content:
#                     results = content['search_results']
#                     provider = content.get('provider', 'unknown')
                    
#                     if isinstance(results, list):
#                         for i, result in enumerate(results):
#                             if isinstance(result, dict):
#                                 # Add source info
#                                 result['source'] = f"{provider} [{len(search_results) + i + 1}]"
#                                 search_results.append(result)
                            
#             except Exception as e:
#                 # Note: We're not adding loading messages here since this function 
#                 # doesn't have access to modify state directly
#                 continue
    
#     return search_results

# def evaluate_results_node(state: AgentState) -> Dict[str, Any]:
#     """
#     Use LLM to evaluate if search results are sufficient or need clarification.
#     Uses search_results from state (set by agent node).
#     """
#     state_update = {"loading_messages": state.get("loading_messages", [])}
    
#     # Get search results from state (should be set by agent node)
#     search_results = state.get("search_results", [])
    
#     # If state doesn't have results, try to extract them (fallback)
#     if not search_results:
#         add_loading_message(state_update, "No search results in state, attempting to extract from messages", "warning")
#         search_results = extract_search_results(state)
    
#     # Get the original user query
#     user_query = state.get("user_query", "")
#     if not user_query:
#         for msg in state["messages"]:
#             if isinstance(msg, HumanMessage):
#                 user_query = msg.content
#                 break
    
#     add_loading_message(state_update, f"Evaluating {len(search_results)} search results for relevance", "info")
    
#     # If we have no search results at all, we definitely need clarification
#     if not search_results:
#         add_loading_message(state_update, "No search results found, will request user clarification", "warning")
#         state_update.update({
#             "search_results": search_results,
#             "needs_clarification": True,
#             "search_complete": True,
#             "user_query": user_query
#         })
#         return state_update
    
#     # Check if we have meaningful content in the results
#     has_meaningful_content = False
#     total_content_length = 0
    
#     for result in search_results:
#         content = result.get('content', '') or result.get('text', '') or result.get('snippet', '')
#         title = result.get('title', '')
        
#         if content and len(content.strip()) > 5:  # At least some substantial content
#             has_meaningful_content = True
#             total_content_length += len(content)
    
#     add_loading_message(state_update, f"Content analysis: {total_content_length} characters across {len(search_results)} results", "debug")
    
#     # If we have meaningful content, be more lenient
#     if has_meaningful_content and total_content_length > 50:
#         add_loading_message(state_update, "Search results contain sufficient information, proceeding to generate answer", "success")
#         state_update.update({
#             "search_results": search_results,
#             "needs_clarification": False,
#             "search_complete": True,
#             "user_query": user_query
#         })
#         return state_update
    
#     # For edge cases, use LLM evaluation but with better prompting
#     add_loading_message(state_update, "Running detailed evaluation using LLM to assess result quality", "info")
    
#     evaluation_prompt = f"""
#     You are evaluating search results for the query: "{user_query}"
    
#     SEARCH RESULTS SUMMARY:
#     Number of results: {len(search_results)}
#     Results found: {format_search_results_for_evaluation(search_results)}
    
#     The user wants to know about this topic. Look at the search results above.
    
#     IMPORTANT EVALUATION CRITERIA:
#     - If there are search results with relevant titles and content, even if not perfect, mark as SUFFICIENT
#     - Only mark as NEEDS_CLARIFICATION if the results are completely empty, irrelevant, or contain no useful information
#     - Be generous - if there's ANY useful information that could help answer the query, mark as SUFFICIENT
    
#     Examples of when to mark SUFFICIENT:
#     - Results about the topic exist, even if not perfectly current
#     - General information about the subject is available
#     - Related or background information is present
    
#     Examples of when to mark NEEDS_CLARIFICATION:
#     - No search results at all
#     - All results are completely unrelated to the query
#     - Results contain only error messages or empty content
    
#     Based on the search results above, respond with EXACTLY one word:
#     - "SUFFICIENT" (if there's any useful information about the topic)
#     - "NEEDS_CLARIFICATION" (only if results are empty or completely irrelevant)
#     """
    
#     # Get evaluation from LLM
#     evaluation_response = llm_evaluator.invoke([
#         SystemMessage(content="You are a search results evaluator. Be generous - if there's any useful information, mark as sufficient. Only request clarification if results are truly empty or irrelevant."),
#         HumanMessage(content=evaluation_prompt)
#     ])
    
#     evaluation = evaluation_response.content.strip().upper()
#     add_loading_message(state_update, f"LLM evaluation result: {evaluation}", "debug")
    
#     # Default to sufficient if evaluation is unclear
#     needs_clarification = "NEEDS_CLARIFICATION" in evaluation
    
#     # Extra safety: if we have any results with content, don't ask for clarification
#     if not needs_clarification or has_meaningful_content:
#         add_loading_message(state_update, "Final decision: Results are sufficient for generating answer", "success")
#         state_update.update({
#             "search_results": search_results,
#             "needs_clarification": False,
#             "search_complete": True,
#             "user_query": user_query
#         })
#     else:
#         add_loading_message(state_update, "Final decision: Results insufficient, will request clarification", "warning")
#         state_update.update({
#             "search_results": search_results,
#             "needs_clarification": True,
#             "search_complete": True,
#             "user_query": user_query
#         })
    
#     return state_update

# def format_search_results_for_evaluation(results: List[Dict[str, Any]]) -> str:
#     """Format search results for evaluation prompt."""
#     if not results:
#         return "No search results found."
    
#     formatted = []
#     for i, result in enumerate(results, 1):
#         source = result.get('source', f'Result {i}')
#         content = result.get('content', result.get('text', result.get('snippet', 'No content')))
#         title = result.get('title', '')
        
#         formatted.append(f"{source}: {title}\n{content}\n")
    
#     return "\n".join(formatted[:10])  # Limit to first 10 results for evaluation

# def format_search_results_for_answer(results: List[Dict[str, Any]]) -> str:
#     """Format search results for answer generation."""
#     if not results:
#         return "No search results available."
    
#     formatted = []
#     for result in results:
#         source = result.get('source', 'Unknown source')
#         content = result.get('content', result.get('text', result.get('snippet', 'No content')))
#         title = result.get('title', '')
#         url = result.get('url', result.get('link', ''))
        
#         result_text = f"**{source}**: {title}\n"
#         result_text += f"Content: {content}\n"
#         if url:
#             result_text += f"URL: {url}\n"
        
#         formatted.append(result_text)
    
#     return "\n".join(formatted)

# def request_clarification(state: AgentState) -> Dict[str, Any]:
#     """
#     Node to request human clarification when search results are insufficient.
#     """
#     state_update = {"loading_messages": state.get("loading_messages", [])}
    
#     user_query = state.get("user_query", "the query")
#     add_loading_message(state_update, f"Generating clarification request for insufficient results", "info")
    
#     clarification_request = AIMessage(
#         content=f"I searched for information about '{user_query}', but I couldn't find sufficient relevant results. Could you please:\n\n"
#                 f"1. Provide more specific details about what you're looking for\n"
#                 f"2. Try rephrasing your question with different keywords\n"
#                 f"3. Let me know if there's a particular aspect you're most interested in\n\n"
#                 f"This will help me search more effectively for you."
#     )
    
#     add_loading_message(state_update, "Clarification request generated, waiting for user input", "info")
    
#     state_update.update({
#         "messages": [clarification_request],
#         "needs_clarification": True
#     })
#     return state_update

# def process_feedback(state: AgentState) -> Dict[str, Any]:
#     """
#     Process human feedback and prepare for a new search.
#     """
#     state_update = {"loading_messages": state.get("loading_messages", [])}
    
#     # Find the latest human message (the feedback)
#     feedback = ""
#     for msg in reversed(state["messages"]):
#         if isinstance(msg, HumanMessage):
#             feedback = msg.content
#             break   
    
#     add_loading_message(state_update, f"Processing user feedback: '{feedback}'", "info")
#     add_loading_message(state_update, "Resetting search state for new query", "debug")
    
#     # Reset search state for new query
#     state_update.update({
#         "messages": state["messages"],  # Keep all messages
#         "user_query": feedback,
#         "needs_clarification": False,
#         "search_complete": False,
#         "search_results": None
#     })
#     return state_update

# def final_answer_node(state: AgentState) -> Dict[str, Any]:
#     """
#     Generate a comprehensive, well-structured markdown answer using LLM.
#     """
#     state_update = {"loading_messages": state.get("loading_messages", [])}
    
#     search_results = state.get("search_results", [])
#     user_query = state.get("user_query", "")
    
#     add_loading_message(state_update, f"Generating comprehensive answer using {len(search_results)} search results", "info")
    
#     # Prepare prompt for answer generation
#     answer_prompt = f"""
#     Based on the search results below, provide a comprehensive answer to this question: "{user_query}"

#     Format your response as a well-structured markdown document with:
#     - A clear, direct answer to the question
#     - Organized sections with appropriate headings (##, ###)
#     - Key information highlighted with **bold text**
#     - Bullet points or numbered lists where appropriate
#     - Inline citations using [1], [2], etc. that reference the sources
#     - A "Sources" section at the end listing all referenced sources

#     SEARCH RESULTS:
#     {format_search_results_for_answer(search_results)}

#     Important guidelines:
#     - Answer the user's question directly and comprehensively
#     - Use clear, accessible language
#     - Organize information logically
#     - Include relevant details but stay focused on the question
#     - Cite your sources appropriately
#     """
    
#     add_loading_message(state_update, "Invoking LLM to generate structured answer", "debug")
    
#     # Generate answer with LLM
#     answer_response = llm_evaluator.invoke([
#         SystemMessage(content="You are a helpful research assistant. Create comprehensive, well-structured answers in markdown format with proper citations."),
#         HumanMessage(content=answer_prompt)
#     ])
    
#     add_loading_message(state_update, "Answer generation completed successfully", "success")
    
#     state_update["messages"] = [AIMessage(content=answer_response.content)]
#     return state_update

# # ── CONDITIONAL ROUTING FUNCTIONS ─────────────────────────────────────────────
# def route_after_agent(state: AgentState) -> str:
#     """Route after agent node - check for tool calls or search completion."""
#     last_message = state["messages"][-1]
    
#     # If the agent wants to use tools, go to tools
#     if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
#         return "tools"
    
#     # If search is marked as complete, go to evaluation
#     if state.get("search_complete", False):
#         return "evaluate_results"
    
#     # Otherwise, something went wrong - go to evaluation as fallback
#     return "evaluate_results"

# def route_after_evaluation(state: AgentState) -> str:
#     """Route after evaluation - either to clarification or final answer."""
#     needs_clarification = state.get("needs_clarification", False)
    
#     if needs_clarification:
#         return "request_clarification"
#     else:
#         return "final_answer"

# # ── GRAPH ─────────────────────────────────────────────────────────────────────
# def build_agent():
#     """
#     Build a ReAct LangGraph with human interruption only when clarification is needed.
#     """
#     workflow = StateGraph(AgentState)

#     # Nodes
#     workflow.add_node("agent", agent_node)
#     workflow.add_node("tools", ToolNode(TOOLS))
#     workflow.add_node("evaluate_results", evaluate_results_node)
#     workflow.add_node("request_clarification", request_clarification)
#     workflow.add_node("process_feedback", process_feedback)
#     workflow.add_node("final_answer", final_answer_node)

#     # Flow control
#     workflow.add_conditional_edges(
#         "agent",
#         route_after_agent,
#         {
#             "tools": "tools", 
#             "evaluate_results": "evaluate_results"
#         }
#     )

#     # After tools execute, return to agent to potentially search more or complete
#     workflow.add_edge("tools", "agent")
    
#     # After evaluation, decide next steps
#     workflow.add_conditional_edges(
#         "evaluate_results",
#         route_after_evaluation,
#         {
#             "request_clarification": "request_clarification",
#             "final_answer": "final_answer"
#         }
#     )
    
#     # After requesting clarification, process the feedback
#     workflow.add_edge("request_clarification", "process_feedback")
    
#     # After processing feedback, start over with the agent
#     workflow.add_edge("process_feedback", "agent")
    
#     # Final answer ends the conversation
#     workflow.add_edge("final_answer", END)

#     # Entry point
#     workflow.set_entry_point("agent")

#     # Compile with interrupt after request_clarification
#     return workflow.compile(interrupt_after=["request_clarification"])

# # Create the agent
# app = build_agent()


from __future__ import annotations

from typing import List, Dict, Any, TypedDict, Annotated, Optional, Callable
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
from datetime import datetime

# ── Your LLM manager (adjust provider/model as you like) ──────────────────────
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import create_search_manager  # your search manager

import json

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

# ── LOADING MESSAGE HELPER ───────────────────────────────────────────────────
class LoadingMessage:
    """Helper class to manage loading messages with timestamps and language support."""
    
    def __init__(self, message: str, level: str = "info", language: str = "en"):
        self.message = message
        self.level = level  # info, debug, warning, error, success
        self.language = language
        self.timestamp = datetime.now().isoformat()
    
    def __str__(self):
        return f"[{self.timestamp}] {self.level.upper()}: {self.message}"
    
    def to_dict(self):
        return {
            "message": self.message,
            "level": self.level,
            "language": self.language,
            "timestamp": self.timestamp
        }

def add_loading_message(state_update: Dict[str, Any], message_key: str, level: str = "info") -> None:
    """Add a loading message to the state using the detected language."""
    if "loading_messages" not in state_update:
        state_update["loading_messages"] = []
    
    # Get language from state_update first (most recent), then fallback to "en"
    language = state_update.get("detected_language", "en")
    message = get_localized_message(message_key, language)
    
    loading_msg = LoadingMessage(message, level, language)
    state_update["loading_messages"].append(loading_msg.to_dict())

def get_localized_message(key: str, language: str) -> str:
    """Get localized loading messages. LLM will handle this dynamically."""
    # This is a simple fallback - in practice, the LLM will generate these
    messages = {
        "en": {
            "starting_research": "Starting research for your query...",
            "detecting_language": "Detecting language and optimizing query...",
            "system_initialized": "Search agent initialized",
            "analyzing_query": "Analyzing query to determine best search strategy",
            "processing_results": "Processing search results",
            "evaluating_results": "Evaluating search results for relevance",
            "generating_answer": "Generating comprehensive answer",
            "search_completed": "Search completed successfully",
            "insufficient_results": "Insufficient results found, requesting clarification",
            "processing_feedback": "Processing your feedback"
        }
    }
    return messages.get(language, messages["en"]).get(key, f"Processing: {key}")

def print_loading_messages(state: Dict[str, Any], show_all: bool = False, level_filter: List[str] = None) -> None:
    """Print loading messages from state. Optionally filter by level."""
    loading_messages = state.get("loading_messages", [])
    
    if not loading_messages:
        return
    
    if level_filter is None:
        level_filter = ["info", "success", "warning", "error"]
    
    if show_all:
        messages_to_show = loading_messages
    else:
        # Show only the last few messages
        messages_to_show = loading_messages[-5:]
    
    for msg_data in messages_to_show:
        if msg_data["level"] in level_filter:
            timestamp = msg_data["timestamp"].split("T")[1][:8]  # Just time part
            level_emoji = {
                "info": "ℹ️",
                "debug": "🔧",
                "success": "✅", 
                "warning": "⚠️",
                "error": "❌"
            }.get(msg_data["level"], "📝")
            
            print(f"{level_emoji} [{timestamp}] {msg_data['message']}")

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
    # Store the optimized search queries
    search_queries: List[str]
    # Store detected language
    detected_language: str
    # Track if we've completed search phase
    search_complete: bool
    # Store loading messages for user feedback
    loading_messages: List[Dict[str, Any]]

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
def detect_language_and_rewrite_node(state: AgentState) -> Dict[str, Any]:
    """
    Detect the language of the user's query and rewrite it for better search results.
    """
    msgs = state["messages"]
    state_update = {"loading_messages": state.get("loading_messages", [])}
    
    # Get the LATEST user query (last HumanMessage)
    user_query = ""
    for msg in reversed(msgs):  # Start from the end to get the latest
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
    
    if not user_query:
        # Fallback to English if no query found
        state_update.update({
            "user_query": "",
            "detected_language": "en",
            "search_queries": []
        })
        return state_update
    
    # Use LLM to detect language and rewrite query
    rewrite_prompt = f"""
    User query: "{user_query}"
    
    Please:
    1. Detect the language of this query
    2. Generate 2-3 optimized search queries in the same language that would find better results
    
    Respond in this exact JSON format:
    {{
        "detected_language": "language_code",
        "language_name": "Language Name", 
        "optimized_queries": ["query1", "query2", "query3"],
        "loading_message": "Starting research for your query..."
    }}
    
    The loading_message should be in the detected language and appropriate for the context.
    Language codes: en, es, fr, de, it, pt, ru, zh, ja, ko, ar, hi, etc.
    """
    
    response = llm_evaluator.invoke([
        SystemMessage(content="You are a language detection and query optimization expert. Always respond with valid JSON."),
        HumanMessage(content=rewrite_prompt)
    ])
    
    try:
        result = json.loads(response.content.strip())
        detected_language = result.get("detected_language", "en")
        optimized_queries = result.get("optimized_queries", [user_query])
        loading_message = result.get("loading_message", "Processing your query...")
        
        # Add the localized loading message
        loading_msg = LoadingMessage(loading_message, "info", detected_language)
        state_update["loading_messages"].append(loading_msg.to_dict())
        
        state_update.update({
            "user_query": user_query,
            "detected_language": detected_language,
            "search_queries": optimized_queries
        })
        
    except (json.JSONDecodeError, Exception) as e:
        # Fallback if LLM response is malformed
        state_update.update({
            "user_query": user_query,
            "detected_language": "en",
            "search_queries": [user_query]
        })
        add_loading_message(state_update, "starting_research", "info")
    
    return state_update

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

def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node that decides which tools to call using optimized search queries.
    """
    msgs = state["messages"]
    state_update = {
        "loading_messages": state.get("loading_messages", []),
        "detected_language": state.get("detected_language", "en")  # Copy language to state_update
    }

    # Get optimized search queries from state
    search_queries = state.get("search_queries", [])
    if not search_queries:
        search_queries = [state.get("user_query", "")]

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
        add_loading_message(state_update, "processing_results", "info")
        search_results = extract_search_results(state)
        
        state_update.update({
            "messages": msgs,
            "search_results": search_results,
            "search_complete": True,
        })
        return state_update

    # If search is already finished, do nothing
    if state.get("search_complete"):
        add_loading_message(state_update, "search_completed", "debug")
        state_update["messages"] = msgs
        return state_update

    # Prepare clean message list for LLM - ensure proper system message handling
    clean_msgs = []
    
    # Add system message only if not already present at the start
    if not msgs or not isinstance(msgs[0], SystemMessage):
        clean_msgs.append(system_preamble())
        add_loading_message(state_update, "system_initialized", "debug")
    
    # Add all existing messages, but skip any additional system messages to avoid conflicts
    for msg in msgs:
        if isinstance(msg, SystemMessage) and clean_msgs and isinstance(clean_msgs[0], SystemMessage):
            continue  # Skip additional system messages
        clean_msgs.append(msg)

    # Use optimized queries to decide tool calls
    add_loading_message(state_update, "analyzing_query", "info")
    
    # Instead of adding another human message, update the system prompt with context
    if clean_msgs and isinstance(clean_msgs[0], SystemMessage):
        enhanced_system_content = clean_msgs[0].content + f"\n\nCurrent context:\n"
        enhanced_system_content += f"User query: {state.get('user_query', '')}\n"
        enhanced_system_content += f"Optimized search queries to use: {', '.join(search_queries)}"
        clean_msgs[0] = SystemMessage(content=enhanced_system_content)
    
    response = llm_with_tools.invoke(clean_msgs)
    
    state_update["messages"] = [response]
    return state_update

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

def evaluate_results_node(state: AgentState) -> Dict[str, Any]:
    """
    Use LLM to evaluate if search results are sufficient, with multilingual support.
    """
    state_update = {
        "loading_messages": state.get("loading_messages", []),
        "detected_language": state.get("detected_language", "en")  # Copy language to state_update
    }
    
    search_results = state.get("search_results", [])
    if not search_results:
        search_results = extract_search_results(state)
    
    user_query = state.get("user_query", "")
    language = state.get("detected_language", "en")
    
    add_loading_message(state_update, "evaluating_results", "info")
    
    # Simple check first
    if not search_results:
        add_loading_message(state_update, "insufficient_results", "warning")
        state_update.update({
            "search_results": search_results,
            "needs_clarification": True,
            "search_complete": True,
            "user_query": user_query
        })
        return state_update
    
    # Check for meaningful content
    has_meaningful_content = False
    total_content_length = 0
    
    for result in search_results:
        content = result.get('content', '') or result.get('text', '') or result.get('snippet', '')
        if content and len(content.strip()) > 5:
            has_meaningful_content = True
            total_content_length += len(content)
    
    if has_meaningful_content and total_content_length > 50:
        state_update.update({
            "search_results": search_results,
            "needs_clarification": False,
            "search_complete": True,
            "user_query": user_query
        })
        return state_update
    
    # LLM evaluation with language consideration
    evaluation_prompt = f"""
    Language: {language}
    User query: "{user_query}"
    
    Search results: {format_search_results_for_evaluation(search_results)}
    
    Evaluate if these results can answer the user's question.
    Respond with exactly one word: "SUFFICIENT" or "NEEDS_CLARIFICATION"
    """
    
    evaluation_response = llm_evaluator.invoke([
        SystemMessage(content="You are a search results evaluator. Be generous - if there's any useful information, mark as sufficient."),
        HumanMessage(content=evaluation_prompt)
    ])
    
    evaluation = evaluation_response.content.strip().upper()
    needs_clarification = "NEEDS_CLARIFICATION" in evaluation
    
    if not needs_clarification or has_meaningful_content:
        state_update.update({
            "search_results": search_results,
            "needs_clarification": False,
            "search_complete": True,
            "user_query": user_query
        })
    else:
        add_loading_message(state_update, "insufficient_results", "warning")
        state_update.update({
            "search_results": search_results,
            "needs_clarification": True,
            "search_complete": True,
            "user_query": user_query
        })
    
    return state_update

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
    
    return "\n".join(formatted[:10])

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
    Node to request human clarification in the user's language.
    """
    state_update = {
        "loading_messages": state.get("loading_messages", []),
        "detected_language": state.get("detected_language", "en")  # Copy language to state_update
    }
    
    user_query = state.get("user_query", "the query")
    language = state.get("detected_language", "en")
    
    # Generate clarification request in the user's language
    clarification_prompt = f"""
    Language: {language}
    User query: "{user_query}"
    
    Generate a polite clarification request in {language} asking the user to:
    1. Provide more specific details
    2. Rephrase with different keywords  
    3. Specify what aspect they're most interested in
    
    Keep it concise and helpful.
    """
    
    clarification_response = llm_evaluator.invoke([
        SystemMessage(content=f"Generate a helpful clarification request in the specified language."),
        HumanMessage(content=clarification_prompt)
    ])
    
    clarification_request = AIMessage(content=clarification_response.content)
    
    add_loading_message(state_update, "insufficient_results", "info")
    
    state_update.update({
        "messages": [clarification_request],
        "needs_clarification": True
    })
    return state_update

def process_feedback(state: AgentState) -> Dict[str, Any]:
    """
    Process human feedback and prepare for a new search.
    """
    state_update = {
        "loading_messages": state.get("loading_messages", []),
        "detected_language": state.get("detected_language", "en")  # Copy language to state_update
    }
    
    # Find the latest human message (the feedback)
    feedback = ""
    for msg in reversed(state["messages"]):  # Also fix this to get latest message
        if isinstance(msg, HumanMessage):
            feedback = msg.content
            break   
    
    add_loading_message(state_update, "processing_feedback", "info")
    
    # Reset search state for new query but preserve message history and language
    state_update.update({
        "user_query": feedback,  # The new feedback becomes the query
        "needs_clarification": False,
        "search_complete": False,
        "search_results": None,
        "search_queries": [],  # Reset search queries so they get regenerated
        # Keep detected_language from state or reset for new detection
        "detected_language": state.get("detected_language", "en")
    })
    return state_update

def final_answer_node(state: AgentState) -> Dict[str, Any]:
    """
    Generate a comprehensive answer in the user's language.
    """
    state_update = {
        "loading_messages": state.get("loading_messages", []),
        "detected_language": state.get("detected_language", "en")  # Copy language to state_update
    }
    
    search_results = state.get("search_results", [])
    user_query = state.get("user_query", "")
    language = state.get("detected_language", "en")
    
    add_loading_message(state_update, "generating_answer", "info")
    
    # Generate answer in the user's language
    answer_prompt = f"""
    Language: {language}
    User question: "{user_query}"
    
    Based on the search results below, provide a comprehensive answer in {language}.
    
    Format as markdown with:
    - Clear, direct answer
    - Organized sections with headings
    - Key information in **bold**
    - Bullet points where appropriate  
    - Citations [1], [2], etc.
    - Sources section at the end
    
    SEARCH RESULTS:
    {format_search_results_for_answer(search_results)}
    
    Answer in {language} and be comprehensive but focused.
    """
    
    answer_response = llm_evaluator.invoke([
        SystemMessage(content=f"You are a helpful research assistant. Create comprehensive answers in the specified language with proper markdown formatting."),
        HumanMessage(content=answer_prompt)
    ])
    
    state_update["messages"] = [AIMessage(content=answer_response.content)]
    return state_update

# ── CONDITIONAL ROUTING FUNCTIONS ─────────────────────────────────────────────
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

# ── GRAPH ─────────────────────────────────────────────────────────────────────
def build_agent():
    """
    Build a multilingual ReAct LangGraph with query optimization.
    """
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("detect_language_and_rewrite", detect_language_and_rewrite_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(TOOLS))
    workflow.add_node("evaluate_results", evaluate_results_node)
    workflow.add_node("request_clarification", request_clarification)
    workflow.add_node("process_feedback", process_feedback)
    workflow.add_node("final_answer", final_answer_node)

    # Flow control
    workflow.add_edge("detect_language_and_rewrite", "agent")
    
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
    workflow.add_edge("process_feedback", "detect_language_and_rewrite")
    workflow.add_edge("final_answer", END)

    # Entry point
    workflow.set_entry_point("detect_language_and_rewrite")

    return workflow.compile(interrupt_after=["request_clarification"])

# Create the agent
app = build_agent()
 
 
 