import os
from typing import Any, Literal, TypedDict, NotRequired
from deepagents import create_deep_agent

from core.search_manager import create_search_manager
from core.llm_manager import LLMManager, LLMProvider
from langchain.tools import Tool
from langchain.tools import StructuredTool


# =========================
# Type Definitions
# =========================
class SubAgent(TypedDict):
    """Structure for sub-agent configuration."""
    name: str
    description: str
    prompt: str
    tools: NotRequired[list[str]]
    model_settings: NotRequired[dict[str, Any]]


class ModeratorResult(TypedDict):
    """Return type for content moderator."""
    safe: bool
    reason: str


# =========================
# Setup Managers
# =========================
manager: LLMManager = LLMManager()
search_manager = create_search_manager()

llm = manager.get_chat_model(
    provider=LLMProvider.OPENAI,
    temperature=0.7
)


# =========================
# Tools
# =========================
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False
) -> Any:
    """Run a web search"""
    return search_manager.search(
        query=query,
        max_results=max_results,
        provider="tavily",
        include_raw_content=include_raw_content,
        topic=topic
    )


def content_moderator(text: str) -> ModeratorResult:
    """Check if the given text contains unsafe or disallowed content."""
    # print("================== Moderator called ========================")
    blocked_keywords = [
        "violence", "terrorism", "hate", "abuse",
        "promote alcohol", "night clubs", "bar",
        "drinking", "smoking"
    ]

    violations = [kw for kw in blocked_keywords if kw.lower() in text.lower()]
    if violations:
        return {
            "safe": False,
            "reason": f"Content contains disallowed terms: {', '.join(violations)}"
        }

    return {"safe": True, "reason": "Content is safe"}


# =========================
# Fact Check Tool
# =========================
def fact_checker(statement: str, max_results: int = 3) -> dict[str, Any]:
    """
    Check if a statement is true by searching the internet and summarizing evidence.
    Returns a dictionary with `verified` (bool) and `evidence` (list[str]).
    """
    print("================== Fact checker called ========================")
    search_results = internet_search(statement, max_results=max_results)
    evidence = [res["title"] + ": " + res.get("snippet", "") for res in search_results]

    # Simple heuristic: if at least one source confirms the statement, mark as verified
    verified = any(statement.lower() in (res.get("snippet", "").lower() + res.get("title", "").lower())
                   for res in search_results)

    return {"verified": verified, "evidence": evidence}


# Wrap tools as Tool objects
# content_moderator_tool: Tool = Tool(
#     name="content_moderator",
#     func=content_moderator,
#     description="Check if the given text contains unsafe or disallowed content."
# )

# internet_search_tool: Tool = Tool(
#     name="internet_search",
#     func=internet_search,
#     description="Perform an internet search on general, news, or finance topics."
# )

content_moderator_tool = StructuredTool.from_function(
    func=content_moderator,
    name="content_moderator",
    description="Check if the given text contains unsafe or disallowed content."
)

internet_search_tool = StructuredTool.from_function(
    func=internet_search,
    name="internet_search",
    description="Perform an internet search on general, news, or finance topics."
)

fact_checker_tool = StructuredTool.from_function(
    func=fact_checker,
    name="fact_checker",
    description="Verify if a statement is true by searching the internet and providing evidence."
)

# =========================
# Agent Instructions
# =========================
research_instructions: str = """You are an expert researcher with strict content moderation duties. 

WORKFLOW:
1. **FIRST**: Always call `content_moderator` to check if the user request is safe.
   - If unsafe → STOP immediately and return the moderation result, asking for human approval.
   - If safe → continue.
2. Use planning tool to organize your tasks.
3. Conduct research using `internet_search` if needed.
4. Write the report into a file.
5. Send draft to `critique-agent` for review and improvement.
"""



# fact_checker_tool: Tool = Tool(
#     name="fact_checker",
#     func=fact_checker,
#     description="Verify if a statement is true by searching the internet and providing evidence."
# )


# =========================
# Sub-agents (typed)
# =========================
critic_sub_agent: SubAgent = {
    "name": "critique-agent",
    "description": "Critique the final report and verify facts",
    "prompt": "You are a tough editor that points out issues in clarity, logic, accuracy, and verifies facts.",
    "tools": ["fact_checker"],  # attach fact checker to this sub-agent
    "model_settings": {"model": llm}
}


# =========================
# Create Deep Agent
# =========================
agent = create_deep_agent(
    tools=[content_moderator_tool, internet_search_tool,fact_checker_tool],
    instructions=research_instructions,
    model=llm,
    subagents=[critic_sub_agent],
    builtin_tools=["write_todos", "write_file", "read_file", "ls", "edit_file"],
    interrupt_config={
        "content_moderator": {
            "allow_ignore": False,   # must be handled, cannot skip
            "allow_respond": False,   # moderator can respond directly
            "allow_edit": False,
            "allow_accept": True,
        }
    }
)


# =========================
# Main Run Logic
# =========================
if __name__ == "__main__":
    user_message: str = "Please create a report file named 'final_report.md' on search about cancer"

    config = {"configurable": {"thread_id": "thread1"}}

    result: dict[str, Any] = agent.invoke(
        {
            "messages": [{"role": "user", "content": user_message}],
            "files": {"intro.txt": "Initial notes about LangGraph..."}
        },
        config=config
    )

    print("*" * 50)
    print(result["messages"][-1])
    print("*" * 50)

    files: dict[str, str] = result.get("files", {})
    print("Files:", files)

    if "final_report.md" in files:
        print("Content of final_report.md:")
        print(files["final_report.md"])
    else:
        print("File final_report.md not found.")
