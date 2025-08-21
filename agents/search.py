from typing import List, Dict, Any, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from core.llm_manager import LLMManager, LLMProvider
import json

# Initialize components
llm_manager = LLMManager()
llm = llm_manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=2000
)

llm_light = llm_manager.get_chat_model(
    provider=LLMProvider.OPENAI,
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=2000
)

class AgentState(TypedDict):
    """Agent state with automatic message history management"""
    messages: Annotated[List[BaseMessage], add_messages]  # Auto-managed conversation history
    current_question: str        # Current user question being processed
    search_results: List[Dict]   # Search results for current question
    answer: str                  # Final response for current question

def extract_question(state: AgentState) -> AgentState:
    """Extract the latest user question from messages"""
    messages = state.get("messages", [])
    
    if not messages:
        return {
            **state,
            "current_question": "",
            "search_results": [],
            "answer": ""
        }
    
    # Get the LAST message (most recent)
    last_message = messages[-1]
    
    if isinstance(last_message, HumanMessage):
        current_question = last_message.content
        print(f"📝 Processing question: {current_question[:50]}...")
        
        return {
            **state,
            "current_question": current_question,
            "search_results": [],  # Reset for new question
            "answer": ""          # Reset for new question
        }
    
    # Last message wasn't from human
    return {
        **state,
        "current_question": "",
        "search_results": [],
        "answer": ""
    }

def perform_search(state: AgentState) -> AgentState:
    """Perform search using the search tool"""
    current_question = state.get("current_question", "")
    
    if not current_question:
        print("❌ No question to search for")
        return {"search_results": []}
    
    try:
        from core.search_manager import create_search_manager, ResultCleaner
        
        search_manager = create_search_manager()
        working_providers = ["tavily", "wikipedia", "duckduckgo"]
        
        print(f"🔍 Searching for: {current_question}")
        
        raw_results = search_manager.multi_search(
            query=current_question,
            providers=working_providers[:2],
            max_results=5
        )
        
        if raw_results.get('status') == 'success' and raw_results.get('search_results'):
            cleaner = ResultCleaner()
            clean_results = cleaner.deduplicate_results(raw_results['search_results'])
            quality_results = cleaner.filter_by_quality(clean_results, min_content_length=50)
            sorted_results = cleaner.sort_by_relevance(quality_results)
            
            formatted_results = []
            for result in sorted_results:
                formatted_results.append({
                    'title': result.title,
                    'snippet': result.snippet,
                    'url': result.url,
                    'source': result.source
                })
            
            print(f"✅ Found {len(formatted_results)} relevant results")
            return {"search_results": formatted_results}
        else:
            print("❌ Search failed or no results found")
            return {"search_results": []}
            
    except Exception as e:
        print(f"❌ Error during search: {str(e)}")
        return {"search_results": []}

def generate_answer(state: AgentState) -> AgentState:
    """Generate response using search results and add to message history"""
    current_question = state.get("current_question", "")
    search_results = state.get("search_results", [])
    
    if not current_question:
        return {"answer": "No question provided."}
    
    if not search_results:
        answer = "I couldn't find relevant information. Please try rephrasing your question."
        print("📝 No search results, providing fallback answer")
    else:
        # Format search results for LLM context
        context = "\n\n".join(
            f"🔍 {res['title']}\n{res['snippet']}\nSource: {res['url']}"
            for res in search_results
        )
        
        system_prompt = (
            "You're an AI assistant that answers questions using search results. "
            "Use the following information to respond to the user's query:\n\n"
            f"{context}\n\n"
            "Instructions:\n"
            "1. Answer directly and concisely\n"
            "2. Cite sources when relevant\n"
            "3. If information is incomplete, say so"
        )
        
        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=current_question)
            ])
            
            answer = response.content
            print(f"💡 Generated answer for: {current_question[:50]}...")
            
        except Exception as e:
            answer = f"I encountered an error while generating the answer: {str(e)}"
            print(f"❌ Error generating answer: {str(e)}")
    
    # Return answer and add AI message to conversation history
    return {
        "answer": answer,
        "messages": [AIMessage(content=answer)]  # This will be added to history automatically
    }

def should_continue(state: AgentState) -> str:
    """Decide whether to continue processing or end"""
    current_question = state.get("current_question", "")
    print("**"*100)
    print(current_question)
    return "search" if current_question else "end"

def build_agent():
    """Create the agent workflow"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("extract_question", extract_question)
    workflow.add_node("search", perform_search)
    workflow.add_node("answer", generate_answer)
    
    # Set entry point
    workflow.set_entry_point("extract_question")
    
    # Add edges with conditional logic
    workflow.add_conditional_edges(
        "extract_question",
        should_continue,
        {
            "search": "search",
            "end": END
        }
    )
    
    workflow.add_edge("search", "answer")
    workflow.add_edge("answer", END)
    
    return workflow.compile()

# Create the agent
app = build_agent()
 