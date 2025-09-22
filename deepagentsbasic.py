# import os

# from typing import Annotated, List, Literal, Union, NotRequired

# from langchain_core.messages import ToolMessage
# from langchain_core.tools import InjectedToolCallId, tool
# from langgraph.prebuilt import InjectedState
# from langgraph.types import Command



# from IPython.display import Image, display
# from langchain.chat_models import init_chat_model
# from langchain_core.tools import tool
# from langgraph.prebuilt import create_react_agent
# # from utils import format_messages
# from core.llm_manager import LLMManager, LLMProvider

# from langgraph.prebuilt.chat_agent_executor import AgentState
# from typing_extensions import TypedDict

# from prompts import WRITE_TODOS_DESCRIPTION
# from prompts import (TODO_USAGE_INSTRUCTIONS, LS_DESCRIPTION, READ_FILE_DESCRIPTION, WRITE_FILE_DESCRIPTION)


# manager = LLMManager()

# model = manager.get_chat_model(
#     provider=LLMProvider.OPENAI,
#     model="gpt-4o-mini"
# )

# class Todo(TypedDict):
#     """A structured task item for tracking progress through complex workflows.
    
#     Attributes:
#         content: Short, specific description of the task
#         status: Current state - pending, in_progress, or completed
#     """
#     content: str
#     status: Literal["pending", "in_progress", "completed"]

# def file_reducer(left, right):
#     """Merge two file dictionaries, with right side taking precedence.
    
#     Used as a reducer function for the files field in agent state,
#     allowing incremental updates to the virtual file system.
    
#     Args:
#         left: Left side dictionary (existing files)
#         right: Rigt side dictionary (new/updates files)
        
#     Returns:
#         Merged disctionary with right values overringing left values
#     """
#     if left is None:
#         return right
#     elif right is None:
#         return left
#     else:
#         return {**left, **right}


# class DeepAgentState(AgentState):
#     """Extended agent state that includes task tracking and virtual file system.

#     Inherits from LangGraph's AgentState and adds:
#     - todos: List of Todo items for task planning and progress tracking
#     - files: Virtual file system stored as dict mapping filenames to content
#     """

#     todos: NotRequired[list[Todo]]
#     files: Annotated[NotRequired[dict[str, str]], file_reducer]
    


# @tool(description=WRITE_TODOS_DESCRIPTION,parse_docstring=True)
# def write_todos(
#     todos: list[Todo], tool_call_id: Annotated[str, InjectedToolCallId]
# ) -> Command:
#     """Create or update the agent's TODO list for task planning and tracking.

#     Args:
#         todos: List of Todo items with content and status
#         tool_call_id: Tool call identifier for message response

#     Returns:
#         Command to update agent state with new TODO list
#     """
#     return Command(
#         update={
#             "todos": todos,
#             "messages": [
#                 ToolMessage(f"Updated todo list to {todos}", tool_call_id=tool_call_id)
#             ],
#         }
#     )
    


# @tool(parse_docstring=True)
# def read_todos(
#     state: Annotated[DeepAgentState, InjectedState],
#     tool_call_id: Annotated[str, InjectedToolCallId],
# ) -> str:
#     """Read the current TODO list from the agent state.

#     This tool allows the agent to retrieve and review the current TODO list
#     to stay focused on remaining tasks and track progress through complex workflows.

#     Args:
#         state: Injected agent state containing the current TODO list
#         tool_call_id: Injected tool call identifier for message tracking

#     Returns:
#         Formatted string representation of the current TODO list
#     """
#     todos = state.get("todos", [])
#     if not todos:
#         return "No todos currently in the list."

#     result = "Current TODO List:\n"
#     for i, todo in enumerate(todos, 1):
#         status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}
#         emoji = status_emoji.get(todo["status"], "❓")
#         result += f"{i}. {emoji} {todo['content']} ({todo['status']})\n"

#     return result.strip()


# search_result = """The Model Context Protocol (MCP) is an open standard protocol developed 
# by Anthropic to enable seamless integration between AI models and external systems like 
# tools, databases, and other services. It acts as a standardized communication layer, 
# allowing AI models to access and utilize data from various sources in a consistent and 
# efficient manner. Essentially, MCP simplifies the process of connecting AI assistants 
# to external services by providing a unified language for data exchange. """


# # Mock search tool
# @tool(parse_docstring=True)
# def web_search(
#     query: str,
# ):
#     """Search the web for information on a specific topic.

#     This tool performs web searches and returns relevant results
#     for the given query. Use this when you need to gather information from
#     the internet about any topic.

#     Args:
#         query: The search query string. Be specific and clear about what
#                information you're looking for.

#     Returns:
#         Search results from search engine.

#     Example:
#         web_search("machine learning applications in healthcare")
#     """
#     return search_result



# FILE_USAGE_INSTRUCTIONS = """You have access to a virtual file system to help you retain and save context.                                  
                                                                                                                
# ## Workflow Process                                                                                            
# 1. **Orient**: Use ls() to see existing files before starting work                                             
# 2. **Save**: Use write_file() to store the user's request so that we can keep it for later                     
# 3. **Read**: Once you are satisfied with the collected sources, read the saved file and use it to ensure that you directly answer the user's question."""

# # Add mock research instructions
# SIMPLE_RESEARCH_INSTRUCTIONS = """IMPORTANT: Just make a single call to the web_search tool and use the result provided by the tool to answer the user's question."""

# # Full prompt
# INSTRUCTIONS = (
#     FILE_USAGE_INSTRUCTIONS + "\n\n" + "=" * 80 + "\n\n" + SIMPLE_RESEARCH_INSTRUCTIONS
# )




# tools = [write_todos, web_search, read_todos]

# # Add mock research instructions
# SIMPLE_RESEARCH_INSTRUCTIONS = """IMPORTANT: Just make a single call to the web_search tool and use the result provided by the tool to answer the user's question."""

# # Create agent
# app = create_react_agent(
#     model,
#     tools,
#     prompt=TODO_USAGE_INSTRUCTIONS
#     + "\n\n"
#     + "=" * 80
#     + "\n\n"
#     + SIMPLE_RESEARCH_INSTRUCTIONS,
#     state_schema=DeepAgentState,
# )



# =================== TODO list deep agent =========================
import os

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from langgraph.prebuilt import create_react_agent
# from utils import format_messages
from core.llm_manager import LLMManager, LLMProvider

from state import DeepAgentState

 
from prompts import (WRITE_TODOS_DESCRIPTION, TODO_USAGE_INSTRUCTIONS, LS_DESCRIPTION, READ_FILE_DESCRIPTION, WRITE_FILE_DESCRIPTION)


manager = LLMManager()

model = manager.get_chat_model(
    provider=LLMProvider.OPENAI,
    model="gpt-4o-mini"
)

 

@tool(description=LS_DESCRIPTION)
def ls(state: Annotated[DeepAgentState, InjectedState]) -> list[str]:
    """List all files in the virtual filesystem."""
    return list(state.get("files", {}).keys())


@tool(description=READ_FILE_DESCRIPTION, parse_docstring=True)
def read_file(
    file_path: str,
    state: Annotated[DeepAgentState, InjectedState],
    offset: int = 0,
    limit: int = 2000,
) -> str:
    """Read file content from virtual filesystem with optional offset and limit.

    Args:
        file_path: Path to the file to read
        state: Agent state containing virtual filesystem (injected in tool node)
        offset: Line number to start reading from (default: 0)
        limit: Maximum number of lines to read (default: 2000)

    Returns:
        Formatted file content with line numbers, or error message if file not found
    """
    files = state.get("files", {})
    if file_path not in files:
        return f"Error: File '{file_path}' not found"

    content = files[file_path]
    if not content:
        return "System reminder: File exists but has empty contents"

    lines = content.splitlines()
    start_idx = offset
    end_idx = min(start_idx + limit, len(lines))

    if start_idx >= len(lines):
        return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"

    result_lines = []
    for i in range(start_idx, end_idx):
        line_content = lines[i][:2000]  # Truncate long lines
        result_lines.append(f"{i + 1:6d}\t{line_content}")

    return "\n".join(result_lines)


@tool(description=WRITE_FILE_DESCRIPTION, parse_docstring=True)
def write_file(
    file_path: str,
    content: str,
    state: Annotated[DeepAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Write content to a file in the virtual filesystem.

    Args:
        file_path: Path where the file should be created/updated
        content: Content to write to the file
        state: Agent state containing virtual filesystem (injected in tool node)
        tool_call_id: Tool call identifier for message response (injected in tool node)

    Returns:
        Command to update agent state with new file content
    """
    files = state.get("files", {})
    files[file_path] = content
    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(f"Updated file {file_path}", tool_call_id=tool_call_id)
            ],
        }
    )
    
    
# File usage instructions
FILE_USAGE_INSTRUCTIONS = """You are a research assistant with a MANDATORY file-based workflow system. 

## CRITICAL WORKFLOW - YOU MUST FOLLOW THESE STEPS IN ORDER:

### STEP 1: ORIENT & SAVE (REQUIRED)
1. **ALWAYS start by calling ls()** to see what files exist
2. **ALWAYS save the user's request** using write_file() to "user_request.txt"
   - This preserves the original request for reference
   - Include the full user question/request verbatim

### STEP 2: RESEARCH (REQUIRED)
3. **Conduct your research** using web_search() 
4. **SAVE each search result** using write_file() to separate files:
   - "search_result_1.txt", "search_result_2.txt", etc.
   - Include the search query and full results in each file

### STEP 3: SYNTHESIZE & RESPOND (REQUIRED)
5. **Read back your saved files** using read_file() to review:
   - user_request.txt (to remind yourself of the exact question)
   - All search_result_*.txt files (to review your research)
6. **Write your final analysis** to "final_answer.txt" using write_file()
7. **Present your answer** to the user based on the synthesis

## WHY THIS WORKFLOW IS MANDATORY:
- **Persistence**: Your research is saved and won't be lost
- **Accuracy**: You can review the original question before answering
- **Completeness**: You can see all research together before synthesizing
- **Quality**: This prevents overlooking important details

## IMPORTANT RULES:
- **NEVER skip the file operations** - they are not optional
- **ALWAYS use descriptive filenames** that indicate the content
- **READ files before final synthesis** - don't rely on memory alone
- If a user asks multiple questions, save each to separate files

This workflow ensures thorough, accurate research with full traceability."""


# Add mock research instructions
SIMPLE_RESEARCH_INSTRUCTIONS = """IMPORTANT: Just make a single call to the web_search tool and use the result provided by the tool to answer the user's question."""

# Full prompt
INSTRUCTIONS = (
    FILE_USAGE_INSTRUCTIONS + "\n\n" + "=" * 80 + "\n\n" + SIMPLE_RESEARCH_INSTRUCTIONS
)


# Mock search result
search_result = """The Model Context Protocol (MCP) is an open standard protocol developed 
by Anthropic to enable seamless integration between AI models and external systems like 
tools, databases, and other services. It acts as a standardized communication layer, 
allowing AI models to access and utilize data from various sources in a consistent and 
efficient manner. Essentially, MCP simplifies the process of connecting AI assistants 
to external services by providing a unified language for data exchange. """


# Mock search tool
@tool(parse_docstring=True)
def web_search(
    query: str,
):
    """Search the web for information on a specific topic.

    This tool performs web searches and returns relevant results
    for the given query. Use this when you need to gather information from
    the internet about any topic.

    Args:
        query: The search query string. Be specific and clear about what
               information you're looking for.

    Returns:
        Search results from search engine.

    Example:
        web_search("machine learning applications in healthcare")
    """
    return search_result


# Create agent using create_react_agent directly
tools = [ls, read_file, write_file, web_search]

# Create agent with system prompt
app = create_react_agent(
    model, tools, prompt=INSTRUCTIONS, state_schema=DeepAgentState
)


# =================== file  deep agent ===========================

# import os
# from datetime import datetime

# from typing import Annotated, List, Literal, Union, NotRequired

# from langchain_core.messages import ToolMessage
# from langchain_core.tools import InjectedToolCallId, tool
# from langgraph.prebuilt import InjectedState
# from langgraph.types import Command

# from IPython.display import Image, display
# from langchain.chat_models import init_chat_model
# from langchain_core.tools import BaseTool, InjectedToolCallId, tool
# from langgraph.prebuilt import create_react_agent
# # from utils import format_messages
# from core.llm_manager import LLMManager, LLMProvider

# from langgraph.prebuilt.chat_agent_executor import AgentState
# from state import DeepAgentState
# from typing_extensions import TypedDict
# from task_tool import _create_task_tool

 
# from prompts import (WRITE_TODOS_DESCRIPTION, 
#                      TODO_USAGE_INSTRUCTIONS,
#                      LS_DESCRIPTION,
#                      READ_FILE_DESCRIPTION,
#                      WRITE_FILE_DESCRIPTION,
#                      TASK_DESCRIPTION_PREFIX,
#                      SUBAGENT_USAGE_INSTRUCTIONS)
# from state import DeepAgentState


# manager = LLMManager()

# model = manager.get_chat_model(
#     provider=LLMProvider.OPENAI,
#     model="gpt-4o-mini"
# )

 
# max_concurrent_research_units = 3
# max_researcher_iterations = 3

# # Mock search result
# search_result = """The Model Context Protocol (MCP) is an open standard protocol developed 
# by Anthropic to enable seamless integration between AI models and external systems like 
# tools, databases, and other services. It acts as a standardized communication layer, 
# allowing AI models to access and utilize data from various sources in a consistent and 
# efficient manner. Essentially, MCP simplifies the process of connecting AI assistants 
# to external services by providing a unified language for data exchange. """



# # Mock search tool
# @tool(parse_docstring=True)
# def web_search(
#     query: str,
# ):
#     """Search the web for information on a specific topic.

#     This tool performs web searches and returns relevant results
#     for the given query. Use this when you need to gather information from
#     the internet about any topic.

#     Args:
#         query: The search query string. Be specific and clear about what
#                information you're looking for.

#     Returns:
#         Search results from the search engine.

#     Example:
#         web_search("machine learning applications in healthcare")
#     """
#     return search_result


# # Add mock research instructions
# SIMPLE_RESEARCH_INSTRUCTIONS = """You are a researcher. Research the topic provided to you. IMPORTANT: Just make a single call to the web_search tool and use the result provided by the tool to answer the provided topic."""

# # Create research sub-agent
# research_sub_agent = {
#     "name": "research-agent",
#     "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
#     "prompt": SIMPLE_RESEARCH_INSTRUCTIONS,
#     "tools": ["web_search"],
# }




# # Tools for sub-agent
# sub_agent_tools = [web_search]

# # Create task tool to delegate tasks to sub-agents
# task_tool = _create_task_tool(
#     sub_agent_tools, [research_sub_agent], model, DeepAgentState
# )

# # Tools
# delegation_tools = [task_tool]

# # Create agent with system prompt
# app = create_react_agent(
#     model,
#     delegation_tools,
#     prompt=SUBAGENT_USAGE_INSTRUCTIONS.format(
#         max_concurrent_research_units=max_concurrent_research_units,
#         max_researcher_iterations=max_researcher_iterations,
#         # date=datetime.now().strftime("%a %b %-d, %Y"), 
#         date = datetime.now().strftime("%a %b %d, %Y").replace(" 0", " ") # on windows
#     ),
#     state_schema=DeepAgentState,
# )


# deep agent with subagents



# full deepagent

# import os
# from datetime import datetime

# from typing import Annotated, List, Literal, Union, NotRequired

# from langchain_core.messages import ToolMessage
# from langchain_core.tools import InjectedToolCallId, tool
# from langgraph.prebuilt import InjectedState
# from langgraph.types import Command

# from IPython.display import Image, display
# from langchain.chat_models import init_chat_model
# from langchain_core.tools import BaseTool, InjectedToolCallId, tool
# from langgraph.prebuilt import create_react_agent
# # from utils import format_messages
# from core.llm_manager import LLMManager, LLMProvider
# from core.search_manager import create_search_manager

# from langgraph.prebuilt.chat_agent_executor import AgentState
# from state import DeepAgentState
# from typing_extensions import TypedDict
# from task_tool import _create_task_tool
# from todo_tools import write_todos, read_todos
# from research_tools import tavily_search, think_tool, get_today_str
# from file_tools import ls, write_file, read_file


 
# from prompts import (WRITE_TODOS_DESCRIPTION, 
#                      TODO_USAGE_INSTRUCTIONS,
#                      LS_DESCRIPTION,
#                      READ_FILE_DESCRIPTION,
#                      WRITE_FILE_DESCRIPTION,
#                      TASK_DESCRIPTION_PREFIX,
#                      SUBAGENT_USAGE_INSTRUCTIONS, 
#                      RESEARCHER_INSTRUCTIONS,
#                      FILE_USAGE_INSTRUCTIONS)
# from state import DeepAgentState


# manager = LLMManager()

# search_manager = create_search_manager()

# model = manager.get_chat_model(
#     provider=LLMProvider.OPENAI,
#     model="gpt-4o-mini"
# )



# # Limits
# max_concurrent_research_units = 10
# max_researcher_iterations = 10


# # Tools
# sub_agent_tools = [tavily_search, think_tool]
# built_in_tools = [ls, read_file, write_file, write_todos, read_todos, think_tool]


# # Create research sub-agent
# research_sub_agent = {
#     "name": "research-agent",
#     "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
#     "prompt": RESEARCHER_INSTRUCTIONS.format(date=get_today_str()),
#     "tools": ["tavily_search", "think_tool"],
# }

# # Create task tool to delegate tasks to sub-agents
# task_tool = _create_task_tool(
#     sub_agent_tools, [research_sub_agent], model, DeepAgentState
# )

# delegation_tools = [task_tool]
# all_tools = sub_agent_tools + built_in_tools + delegation_tools  # search available to main agent for trivial cases


# # Build prompt
# SUBAGENT_INSTRUCTIONS = SUBAGENT_USAGE_INSTRUCTIONS.format(
#     max_concurrent_research_units=max_concurrent_research_units,
#     max_researcher_iterations=max_researcher_iterations,
#     date = datetime.now().strftime("%a %b %d, %Y").replace(" 0", " "),
# )

# INSTRUCTIONS = (
#     "# TODO MANAGEMENT\n"
#     + TODO_USAGE_INSTRUCTIONS
#     + "\n\n"
#     + "=" * 80
#     + "\n\n"
#     + "# FILE SYSTEM USAGE\n"
#     + FILE_USAGE_INSTRUCTIONS
#     + "\n\n"
#     + "=" * 80
#     + "\n\n"
#     + "# SUB-AGENT DELEGATION\n"
#     + SUBAGENT_INSTRUCTIONS
# )

# app = create_react_agent(
#     model, all_tools, prompt=INSTRUCTIONS, state_schema=DeepAgentState
# )

