import os
from typing import Any, Literal, TypedDict, NotRequired
from deepagents import create_deep_agent

from core.search_manager import create_search_manager
from core.llm_manager import LLMManager, LLMProvider
from langchain.tools import Tool


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
# Tools with Enhanced Logging
# =========================
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False
) -> Any:
    """Run a web search"""
    print(f"🔍 INTERNET SEARCH CALLED: '{query}' (max_results: {max_results}, topic: {topic})")
    try:
        results = search_manager.search(
            query=query,
            max_results=max_results,
            provider="tavily",
            include_raw_content=include_raw_content,
            topic=topic
        )
        print(f"✅ Search completed - found {len(results) if results else 0} results")
        return results
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return []


def content_moderator(text: str) -> ModeratorResult:
    """Check if the given text contains unsafe or disallowed content."""
    print("🛡️ ================== MODERATOR CALLED ========================")
    print(f"Text to moderate: {text}")
    
    blocked_keywords = [
        "violence", "terrorism", "hate", "abuse",
        "promote alcohol", "night clubs", "bar",
        "drinking", "smoking"
    ]

    violations = [kw for kw in blocked_keywords if kw.lower() in text.lower()]
    if violations:
        result = {
            "safe": False,
            "reason": f"Content contains disallowed terms: {', '.join(violations)}"
        }
        print(f"❌ CONTENT BLOCKED: {result['reason']}")
    else:
        result = {"safe": True, "reason": "Content is safe"}
        print("✅ CONTENT APPROVED")
    
    print("================== MODERATOR COMPLETE ========================")
    return result


def fact_checker(statement: str, max_results: int = 3) -> dict[str, Any]:
    """
    Check if a statement is true by searching the internet and summarizing evidence.
    Returns a dictionary with `verified` (bool) and `evidence` (list[str]).
    """
    print(f"🔍 ================== FACT CHECKER CALLED ==================")
    print(f"Statement to verify: {statement}")
    print(f"Searching with max_results: {max_results}")
    
    try:
        search_results = internet_search(statement, max_results=max_results)
        print(f"Found {len(search_results) if search_results else 0} search results")
        
        evidence = []
        if search_results:
            for i, res in enumerate(search_results):
                title = res.get("title", "No title")
                snippet = res.get("snippet", "No snippet")
                evidence_item = f"{title}: {snippet}"
                evidence.append(evidence_item)
                print(f"Evidence {i+1}: {evidence_item[:100]}...")
            
            # Simple heuristic: if at least one source confirms the statement, mark as verified
            verified = any(statement.lower() in (res.get("snippet", "").lower() + res.get("title", "").lower())
                           for res in search_results)
        else:
            verified = False
            evidence = ["No search results found"]
        
        result = {"verified": verified, "evidence": evidence}
        print(f"📊 Verification result: {'✅ VERIFIED' if verified else '❌ NOT VERIFIED'}")
        print(f"Evidence count: {len(evidence)}")
        print("================== FACT CHECKER COMPLETE ==================")
        
        return result
        
    except Exception as e:
        print(f"❌ ERROR in fact checker: {e}")
        return {"verified": False, "evidence": [f"Error during fact checking: {str(e)}"]}


# Wrap tools as Tool objects
content_moderator_tool: Tool = Tool(
    name="content_moderator",
    func=content_moderator,
    description="Check if the given text contains unsafe or disallowed content."
)

internet_search_tool: Tool = Tool(
    name="internet_search",
    func=internet_search,
    description="Perform an internet search on general, news, or finance topics."
)

fact_checker_tool: Tool = Tool(
    name="fact_checker",
    func=fact_checker,
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

Be sure to announce each step you're taking so the user can follow your progress.
"""

# =========================
# Sub-agents (typed)
# =========================
critic_sub_agent: SubAgent = {
    "name": "critique-agent",
    "description": "Critique the final report and verify facts",
    "prompt": """You are a tough editor that points out issues in clarity, logic, accuracy, and verifies facts.

When reviewing a report:
1. Check for factual accuracy using the fact_checker tool
2. Point out any logical inconsistencies
3. Suggest improvements for clarity
4. Verify that claims are well-supported

Always announce when you're starting your critique and what tools you're using.""",
    "tools": ["fact_checker"],  # attach fact checker to this sub-agent
    "model_settings": {"model": llm}
}


# =========================
# Testing Functions
# =========================
def test_individual_components():
    """Test each component individually"""
    print("\n" + "="*60)
    print("🧪 TESTING INDIVIDUAL COMPONENTS")
    print("="*60)
    
    # Test moderator
    print("\n1. Testing Content Moderator:")
    safe_text = "How to organize elections in Africa"
    unsafe_text = "Best bars for drinking"
    
    print("Safe text test:")
    content_moderator(safe_text)
    
    print("\nUnsafe text test:")
    content_moderator(unsafe_text)
    
    # Test search
    print("\n2. Testing Internet Search:")
    internet_search("democratic elections Africa", max_results=2)
    
    # Test fact checker
    print("\n3. Testing Fact Checker:")
    fact_checker("The capital of France is Paris", max_results=2)
    
    print("\n" + "="*60)
    print("🧪 COMPONENT TESTING COMPLETE")
    print("="*60)


# =========================
# Create Deep Agent
# =========================
agent = create_deep_agent(
    tools=[content_moderator_tool, internet_search_tool, fact_checker_tool],
    instructions=research_instructions,
    model=llm,
    subagents=[critic_sub_agent],
    builtin_tools=["write_todos", "write_file", "read_file", "ls", "edit_file"],
    interrupt_config={
        "content_moderator": {
            "allow_ignore": False,   # must be handled, cannot skip
            "allow_respond": True,   # moderator can respond directly
            "allow_edit": True,
            "allow_accept": True,
        }
    }
)


# =========================
# Enhanced Main Run Logic
# =========================
if __name__ == "__main__":
    # Run component tests first
    test_individual_components()
    
    user_message: str = "Please create a report file named 'final_report.md' on how to organize a fair election in africa."

    config = {"configurable": {"thread_id": "thread1"}}

    print("\n" + "=" * 60)
    print("🚀 STARTING DEEP AGENT EXECUTION")
    print("=" * 60)
    print(f"User message: {user_message}")
    print(f"Available tools: {[tool.name for tool in [content_moderator_tool, internet_search_tool, fact_checker_tool]]}")
    print(f"Sub-agents configured: {[critic_sub_agent['name']]}")
    print("=" * 60)

    try:
        result: dict[str, Any] = agent.invoke(
            {
                "messages": [{"role": "user", "content": user_message}],
                "files": {"intro.txt": "Initial notes about LangGraph..."}
            },
            config=config
        )

        print("=" * 60)
        print("✅ EXECUTION COMPLETE")
        print("=" * 60)
        
        # Print all messages to see the conversation flow
        messages = result.get("messages", [])
        print(f"Total messages exchanged: {len(messages)}")
        
        for i, msg in enumerate(messages):
            # Handle LangChain message objects
            if hasattr(msg, 'type'):
                role = msg.type
            elif hasattr(msg, '__class__'):
                role = msg.__class__.__name__
            else:
                role = "unknown"
            
            # Get content from LangChain message
            if hasattr(msg, 'content'):
                content = str(msg.content)[:200]
            else:
                content = str(msg)[:200]
                
            print(f"📨 Message {i+1} ({role}): {content}...")
        
        print("=" * 60)
        print("🏁 FINAL RESULT:")
        final_message = result["messages"][-1]
        if hasattr(final_message, 'content'):
            print(final_message.content)
        else:
            print(final_message)
        print("=" * 60)

        files: dict[str, str] = result.get("files", {})
        print(f"📁 Files created: {list(files.keys())}")

        if "final_report.md" in files:
            print("\n" + "=" * 40)
            print("📄 CONTENT OF final_report.md:")
            print("=" * 40)
            print(files["final_report.md"])
        else:
            print("❌ File final_report.md not found.")
            
    except Exception as e:
        print(f"❌ ERROR during execution: {e}")
        import traceback
        traceback.print_exc()