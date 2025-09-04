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

from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import create_search_manager
import asyncio
from dataclasses import dataclass

# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL LANGUAGE PROTOCOL SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class QuestionComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    

def  language_protocol() -> str:
    """Simplified language protocol that's more token-efficient."""
    return """
    LANGUAGE RULE: Always respond in the same language as the user's query. 
    If the user switches languages, adapt immediately.
    """

def create_language_aware_prompt(base_prompt: str, detected_language: str = None) -> str:
    """More efficient language-aware prompt creation."""
    protocol =  language_protocol()
    
    if detected_language and detected_language != "english":
        language_note = f"\n🔍 USER LANGUAGE: {detected_language} - maintain this language\n"
    else:
        language_note = ""
    
    return f"{protocol}{language_note}\n{base_prompt}"

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
    
    # Keep only essential query analysis
    question_complexity: Optional[str]
    optimized_queries: Optional[List[str]]


@dataclass
class SearchStrategy:
    """Defines how to search for a specific query type."""
    query_variants: List[str]
    providers: List[str]
    max_results_per_provider: int = 3
    
class SearchInput(BaseModel):
    query: str = Field(description="The search query string.")
# ══════════════════════════════════════════════════════════════════════════════
# INITIALIZE MANAGERS
# ══════════════════════════════════════════════════════════════════════════════


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

@tool("tavily_search", args_schema=SearchInput, parse_docstring=True)
def tavily_search_current(query: str) -> Dict[str, Any]:
    """
    Use ONLY for current, latest, breaking news, or time-sensitive information.
    Best for: "latest news", "current status", "today", "recent developments", etc.
    """
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
            
            # Mark as current/recent source
            result_dict['source_type'] = 'current'
            result_dict['provider'] = 'tavily'
            search_results.append(result_dict)
        
        return {
            "provider": "tavily_current",
            "query": query,
            "search_results": search_results,
            "search_type": "current_information"
        }
    except Exception as e:
        return {"provider": "tavily_current", "query": query, "error": str(e)}

@tool("multisearch", args_schema=SearchInput , parse_docstring=True)
def multisearch_comprehensive(query: str) -> Dict[str, Any]:
    """
    Use for general queries, background information, analysis, or comprehensive research.
    Combines Wikipedia (facts), DuckDuckGo (general web), and some Tavily (recent context).
    Best for: general questions, background info, analysis, comparisons, explanations.
    """
    try:
        all_results = []
        
        # 1. Wikipedia for factual foundation (2-3 results)
        try:
            wiki_res = search_manager.search(
                query=query,
                provider="wikipedia",
                max_results=3,
                full_content=False,
                summary_sentences=4,
            )
            
            for result in wiki_res.get("search_results", []):
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
                
                result_dict['source_type'] = 'factual'
                result_dict['provider'] = 'wikipedia'
                all_results.append(result_dict)
        except:
            pass  # Continue if Wikipedia fails
        
        # 2. DuckDuckGo for general web coverage (3-4 results)
        try:
            ddg_res = search_manager.search(
                query=query,
                provider="duckduckgo",
                max_results=4,
                region="wt-wt",
                safesearch="moderate",
            )
            
            for result in ddg_res.get("search_results", []):
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
                
                result_dict['source_type'] = 'general'
                result_dict['provider'] = 'duckduckgo'
                all_results.append(result_dict)
        except:
            pass  # Continue if DuckDuckGo fails
            
        # 3. Light Tavily for some recent context (1-2 results)
        try:
            tavily_res = search_manager.search(
                query=query,
                provider="tavily",
                max_results=2,
                search_depth="basic",  # Basic for supplementary info
            )
            
            for result in tavily_res.get("search_results", []):
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
                
                result_dict['source_type'] = 'recent_context'
                result_dict['provider'] = 'tavily_supplementary'
                all_results.append(result_dict)
        except:
            pass  # Continue if Tavily fails
        
        # Deduplicate and rank results
        final_results = deduplicate_and_rank_results(all_results, query)
        
        return {
            "provider": "multisearch",
            "query": query,
            "search_results": final_results,
            "search_type": "comprehensive",
            "sources_used": list(set(r.get('provider', '') for r in final_results))
        }
        
    except Exception as e:
        return {"provider": "multisearch", "query": query, "error": str(e)}


def deduplicate_and_rank_results(results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Remove duplicates and rank results by relevance."""
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_results = []
    
    for result in results:
        url = result.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            # Calculate simple relevance score
            result['relevance_score'] = calculate_simple_relevance(result, query)
            unique_results.append(result)
        elif not url:  # Include results without URLs (like some Wikipedia entries)
            unique_results.append(result)
    
    # Sort by relevance score (highest first)
    unique_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    # Return top 8 results
    return unique_results[:8]

def calculate_simple_relevance(result: Dict[str, Any], query: str) -> float:
    """Simple relevance scoring."""
    score = 0.0
    
    title = result.get('title', '').lower()
    content = result.get('content', '').lower()
    query_lower = query.lower()
    
    # Exact query match in title (high value)
    if query_lower in title:
        score += 3.0
    
    # Individual words in title
    for word in query_lower.split():
        if len(word) > 2 and word in title:
            score += 1.0
    
    # Content relevance (lower weight)
    for word in query_lower.split():
        if len(word) > 2 and word in content:
            score += 0.3
    
    # Source type bonuses
    source_type = result.get('source_type', '')
    if source_type == 'factual':  # Wikipedia
        score += 1.5
    elif source_type == 'recent_context':  # Recent Tavily
        score += 0.5
    
    return score
# Tools list
TOOLS = [tavily_search_current, multisearch_comprehensive]

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(TOOLS)


# ══════════════════════════════════════════════════════════════════════════════
# LLM PROMPT FOR SMART TOOL SELECTION
# ══════════════════════════════════════════════════════════════════════════════

def create_tool_selection_prompt() -> str:
    """Create prompt that helps LLM choose the right tool automatically."""
    return """
You are a search agent with 2 specialized tools. Choose the RIGHT tool for each query:

🔍 **TOOL SELECTION GUIDE**:

**Use `tavily_search`** when user asks for:
- Current/latest/recent information: "latest news", "current status", "today", "now"
- Breaking news or real-time data: "breaking", "just happened", "this week"
- Time-sensitive queries: "recent developments", "current trends", "latest updates"
- Live data: stock prices, weather, current events, recent statistics

**Use `multisearch`** for everything else:
- General knowledge: "What is...", "How does...", "Explain..."
- Background/historical info: "History of...", "Who was...", "When did..."
- Analysis/comparison: "Compare", "Analyze", "What are the differences"
- Comprehensive research: "Tell me about...", "Overview of...", "Details on..."
- Factual information: definitions, explanations, background context

**DECISION EXAMPLES**:
- "Latest iPhone release" → `tavily_search` (current info)
- "How do smartphones work" → `multisearch` (general knowledge)
- "Current stock price of Apple" → `tavily_search` (real-time data)
- "History of Apple company" → `multisearch` (background info)
- "Recent AI developments" → `tavily_search` (current trends)
- "What is artificial intelligence" → `multisearch` (general explanation)

**WHEN IN DOUBT**: Use `multisearch` - it provides comprehensive coverage including some recent context.

Choose the tool and search immediately. No additional analysis needed.
"""

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

def format_search_results(
    results: List[Dict[str, Any]], 
    format_type: str = "full", 
    max_results: Optional[int] = None
) -> str:
    """
    Unified function to format search results for different purposes.
    
    Args:
        results: List of search result dictionaries
        format_type: "full" for final answers, "preview" for analysis, "compact" for brief summaries
        max_results: Maximum number of results to include (None = all)
        
    Returns:
        Formatted string ready for use in prompts
    """
    if not results:
        return "No search results available."
    
    # Limit results if specified
    if max_results:
        results = results[:max_results]
    
    formatted = []
    
    for i, result in enumerate(results):
        # Get source information
        source = result.get('source', result.get('provider', f'Source {i+1}'))
        title = result.get('title', 'No title')
        content = result.get('content', result.get('text', result.get('snippet', 'No content')))
        url = result.get('url', result.get('link', ''))
        
        # Format based on type
        if format_type == "preview":
            # Short format for analysis - truncate content
            content_preview = content[:200] + "..." if len(content) > 200 else content
            result_text = f"**{source}**: {title}\nPreview: {content_preview}"
            
        elif format_type == "compact":
            # Very brief format - just title and snippet
            snippet = content[:100] + "..." if len(content) > 100 else content
            result_text = f"**{source}**: {title} - {snippet}"
            
        else:  # format_type == "full" (default)
            # Full format for final answer generation
            result_text = f"**{source}**: {title}\n"
            result_text += f"Content: {content}\n"
            if url:
                result_text += f"URL: {url}\n"
        
        formatted.append(result_text)
    
    return "\n\n".join(formatted)



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
    """Simplified agent that lets LLM choose between 2 tools intelligently."""
    msgs = state["messages"]
    state_update = {"is_generating": False}

    user_query = state.get("user_query", "")
    
    # Check if we have new tool results
    def has_new_tool_results():
        if state.get("search_complete"):
            return False

        for i in range(len(msgs) - 1, -1, -1):
            msg = msgs[i]
            if isinstance(msg, ToolMessage):
                return True
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

    # Create system prompt with tool selection guidance
    base_system_prompt = f"""
{create_tool_selection_prompt()}

USER QUERY: "{user_query}"

Analyze the query and choose the appropriate tool. Execute the search immediately.
"""

    # Bind simplified tools to LLM
    llm_with_simplified_tools = llm.bind_tools(TOOLS)
    
    # Prepare messages
    clean_msgs = [SystemMessage(content=base_system_prompt)]
    
    # Add conversation history (skip system messages to avoid conflicts)
    for msg in msgs:
        if not isinstance(msg, SystemMessage):
            clean_msgs.append(msg)

    response = llm_with_simplified_tools.invoke(clean_msgs)
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

# =============================================================
# ANSWER GENERATION
# =============================================================

def analyze_search_results(search_results: List[Dict[str, Any]], user_query: str) -> Dict[str, Any]:
    """Updated analysis function with better JSON handling."""
    
    if not search_results:
        return {"quality": "poor", "confidence": 0.0, "themes": [], "conflicts": []}
    
    # Use preview format for analysis (shorter content)
    results_summary = format_search_results(
        search_results, 
        format_type="preview", 
        max_results=6
    )
    
    analysis_prompt = f"""
    You are an internal analysis system. Analyze these search results for the question: "{user_query}"
    
    SEARCH RESULTS SUMMARY:
    {results_summary}
    
    CRITICAL: Your response must ONLY be valid JSON with no additional text, explanations, or markdown formatting.
    Do not include ```json or ``` tags. Just return the raw JSON object.
    
    {{
        "quality_assessment": {{
            "overall_quality": "excellent|good|fair|poor",
            "confidence_score": 0.85,
            "coverage_completeness": "complete|partial|limited"
        }},
        "content_analysis": {{
            "key_themes": ["theme1", "theme2", "theme3"],
            "main_facts": ["fact1", "fact2", "fact3"],
            "conflicting_information": ["conflict1 (source X vs source Y)"],
            "data_points": ["quantitative finding 1", "quantitative finding 2"],
            "gaps_or_limitations": ["what's missing or unclear"]
        }},
        "source_credibility": {{
            "high_credibility": ["source names with high credibility"],
            "medium_credibility": ["source names with medium credibility"],  
            "questionable": ["sources to be cautious about"]
        }},
        "synthesis_strategy": "How to best synthesize this information"
    }}
    """
    
    try:
        response = llm_evaluator.invoke([SystemMessage(content=analysis_prompt)])
        
        # Clean the response content - remove any markdown formatting
        content = response.content.strip()
        
        # Remove ```json and ``` if present
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'\s*```', '', content)
        content = content.strip()
        
        # Parse JSON
        analysis = json.loads(content)
        return analysis
        
    except Exception as e:
        # Better fallback with proper structure
        return {
            "quality_assessment": {
                "overall_quality": "fair", 
                "confidence_score": 0.6,
                "coverage_completeness": "partial"
            },
            "content_analysis": {
                "key_themes": ["analysis error"], 
                "main_facts": [f"Analysis failed: {str(e)}"], 
                "conflicting_information": [],
                "data_points": [],
                "gaps_or_limitations": ["Internal analysis error"]
            },
            "source_credibility": {
                "high_credibility": [], 
                "medium_credibility": [], 
                "questionable": []
            },
            "synthesis_strategy": "Use fallback approach due to analysis error"
        }

def detect_visualization_opportunity(user_query: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect if a query would benefit from data visualization.
    This helps the LLM understand when to create graphs.
    """
    
    query_lower = user_query.lower()
    
    # Keywords that suggest visualization opportunities
    visualization_indicators = {
        "comparison": ["compare", "vs", "versus", "against", "difference between"],
        "trends": ["trend", "over time", "yearly", "monthly", "annual", "growth", "decline"],
        "rankings": ["top", "bottom", "best", "worst", "ranking", "leading", "highest", "lowest"],
        "distributions": ["market share", "percentage", "portion", "breakdown", "split"],
        "statistics": ["statistics", "data", "numbers", "figures", "metrics", "performance"]
    }
    
    # Time period indicators suggest line charts
    time_indicators = ["2019", "2020", "2021", "2022", "2023", "2024", "2025", 
                      "last year", "this year", "over years", "decade", "quarterly"]
    
    # Detect visualization type based on query
    visualization_type = "none"
    confidence = 0.0
    
    # Check for comparison queries
    if any(word in query_lower for word in visualization_indicators["comparison"]):
        if any(word in query_lower for word in time_indicators):
            visualization_type = "line"  # Comparison over time
            confidence = 0.8
        else:
            visualization_type = "bar"   # Static comparison
            confidence = 0.7
    
    # Check for market share/distribution
    elif any(word in query_lower for word in visualization_indicators["distributions"]):
        visualization_type = "pie"
        confidence = 0.8
    
    # Check for trends over time
    elif any(word in query_lower for word in visualization_indicators["trends"]):
        visualization_type = "line"
        confidence = 0.7
    
    # Check for rankings
    elif any(word in query_lower for word in visualization_indicators["rankings"]):
        visualization_type = "bar"
        confidence = 0.6
    
    return {
        "should_visualize": confidence > 0.5,
        "chart_type": visualization_type,
        "confidence": confidence,
        "reasoning": f"Query suggests {visualization_type} chart with {confidence:.1%} confidence"
    }


def build_visualization_aware_prompt(
    user_query: str,
    search_results: List[Dict[str, Any]],
    context: Dict[str, Any]
) -> str:
    """
    Enhanced prompt that intelligently detects when to create visualizations.
    FIXED: Now properly handles multi-series data for comparisons.
    """
    
    # Detect visualization opportunity
    viz_analysis = detect_visualization_opportunity(user_query, context)
    
    sources = format_search_results(search_results, format_type="full")
    
    # Base visualization guidance
    base_viz_instruction = """
Output formats:
- Use plain text for narrative explanations
- Use <TABLE_DATA>...</TABLE_DATA> for structured tables (ALWAYS when you have tabular data)
- Use <GRAPH_DATA>...</GRAPH_DATA> for visualizable chart data (WHEN DATA IS NUMERIC AND PLOTTABLE)
- You SHOULD use both TABLE and GRAPH when you have numeric data that can be plotted

VISUALIZATION DECISION MATRIX:
🔍 **ALWAYS CREATE GRAPHS when you find:**

1. **COMPARISON DATA** → Bar Chart
   - Multiple entities with numeric values
   - Example: "Browser market share: Chrome 65%, Firefox 15%, Safari 12%"
   - Use: bar chart comparing browsers

2. **TIME SERIES DATA** → Line Chart  
   - Values changing over time (years, months, quarters)
   - Example: "Ford sales: 2019: 5.4M, 2020: 4.2M, 2021: 3.9M, 2022: 4.1M"
   - Use: line chart showing trend over time

3. **MARKET SHARE/PERCENTAGES** → Pie Chart
   - Parts of a whole, percentages that add to 100%
   - Example: "Mobile OS: Android 71%, iOS 28%, Other 1%"
   - Use: pie chart showing distribution

4. **RANKINGS/TOP LISTS** → Bar Chart
   - Ordered lists with numeric values
   - Example: "Top countries by GDP: USA $26.9T, China $17.7T, Japan $4.9T"
   - Use: horizontal bar chart

5. **PERFORMANCE METRICS** → Line or Bar Chart
   - Multiple metrics to compare
   - Growth rates, performance indicators
   - Choose based on whether time is involved
"""

    # Enhanced instruction based on query analysis
    if viz_analysis["should_visualize"]:
        chart_guidance = f"""
🎯 **VISUALIZATION DETECTED FOR THIS QUERY:**
- Suggested Chart Type: {viz_analysis["chart_type"].upper()}
- Confidence: {viz_analysis["confidence"]:.1%}
- Reasoning: {viz_analysis["reasoning"]}

⚡ **MANDATORY**: If you find numeric data in the search results that matches this pattern, 
you MUST create both a <TABLE_DATA> and <GRAPH_DATA> section.
"""
    else:
        chart_guidance = """
📊 **VISUALIZATION CHECK**: 
Scan the search results for any numeric data that could be visualized.
If found, create appropriate charts even if not obviously requested.
"""

    return f"""
You are a senior data analyst and research expert.  
Answer the user's question using ONLY the provided search results.

{base_viz_instruction}

{chart_guidance}

STRICT JSON FORMATS (must be valid JSON inside tags):

<TABLE_DATA>
{{
  "columns": ["Column A", "Column B", "Column C"],
  "rows": [
    ["row1-col1", "row1-col2", "row1-col3"],
    ["row2-col1", "row2-col2", "row2-col3"]
  ]
}}
</TABLE_DATA>

🚨 **FIXED GRAPH_DATA FORMAT** - Now supports multi-series data:

**FOR SINGLE SERIES DATA (simple bar, pie charts):**
<GRAPH_DATA>
{{
  "type": "bar|pie",
  "title": "Descriptive chart title",
  "data": [
    {{ "x": "Category A", "y": 123 }},
    {{ "x": "Category B", "y": 456 }}
  ],
  "xLabel": "X axis label",
  "yLabel": "Y axis label"
}}
</GRAPH_DATA>

**FOR MULTI-SERIES DATA (comparisons, multiple lines):**
<GRAPH_DATA>
{{
  "type": "line|bar",
  "title": "Descriptive chart title",
  "series": [
    {{
      "name": "Series 1 Name (e.g., 'US', 'Company A')",
      "data": [
        {{ "x": "2020", "y": 64.5 }},
        {{ "x": "2021", "y": 66.0 }},
        {{ "x": "2022", "y": 58.5 }}
      ]
    }},
    {{
      "name": "Series 2 Name (e.g., 'EU', 'Company B')",
      "data": [
        {{ "x": "2020", "y": 61.0 }},
        {{ "x": "2021", "y": 63.5 }},
        {{ "x": "2022", "y": 64.0 }}
      ]
    }}
  ],
  "xLabel": "X axis label (e.g., 'Years')",
  "yLabel": "Y axis label (e.g., 'Employment Rate (%)')"
}}
</GRAPH_DATA>

🔥 **CRITICAL RULES FOR DATA STRUCTURE:**

1. **Single Series**: Use simple "data" array for pie charts, simple bar charts
2. **Multi-Series**: Use "series" array when comparing multiple entities over time/categories
3. **Comparisons over time**: ALWAYS use multi-series format with "series" array
4. **Each series needs**: "name" (legend label) and "data" (array of x,y points)

QUESTION: {user_query}

CONTEXT HINTS:
- Complexity: {context.get("question_complexity", "moderate")}
- Intent: {context.get("intent_type", "factual")}
- Domain: {context.get("domain", "general")}

SEARCH RESULTS:
{sources}

RESPONSE STRUCTURE:
1. **EXECUTIVE SUMMARY** (2-3 sentences)
   - Direct answer with key numbers/findings
   
2. **KEY FINDINGS** (3-5 main points)
   - Important facts with specific numbers
   - Use citations [^1], [^2], etc.
   
3. **DATA VISUALIZATION** (when numeric data is present)
   - Create <TABLE_DATA> with the raw numbers
   - Create <GRAPH_DATA> with PROPER multi-series structure for comparisons
   - Both are required when you have plottable data
   
4. **ANALYSIS & INSIGHTS**
   - What the data means and why it matters
   - Trends, patterns, or notable findings
   
5. **CONCLUSION & IMPLICATIONS**
   - Key takeaways and what this means for the user

🚨 **CRITICAL RULE**: 
When comparing multiple entities (like US vs EU), you MUST use the multi-series format with the "series" array. Each comparison entity gets its own series with a "name" and "data" array.

Answer now with PROPER data visualization structure.
"""
 
def final_answer_node(state: AgentState) -> Dict[str, Any]:
    """Final answer node with intelligent visualization detection."""
    state_update = {"is_generating": True}

    user_query = state.get("user_query", "")
    search_results = state.get("search_results", [])
    
    # REMOVED: analyze_search_results call that was causing JSON leakage
    
    # Build context with visualization hints
    context = {
        "question_complexity": state.get("question_complexity", "moderate"),
        "intent_type": state.get("intent_type", "factual"),
        "domain": state.get("domain", "general"),
    }

    # Use visualization-aware prompt
    prompt = build_visualization_aware_prompt(user_query, search_results, context)

    try:
        answer_response = llm_evaluator.invoke([SystemMessage(content=prompt)])

        # Check if visualization was generated (for debugging)
        has_table = "<TABLE_DATA>" in answer_response.content
        has_graph = "<GRAPH_DATA>" in answer_response.content
        
        state_update.update({
            "messages": [AIMessage(content=answer_response.content)],
            "is_generating": False,
            "visualization_created": has_table or has_graph,
            "has_table": has_table,
            "has_graph": has_graph,
            "answer_confidence": 0.8  # Default confidence since we removed analysis
        })

    except Exception as e:
        # Fallback without visualization
        fallback_summary = format_search_results(
            search_results, 
            format_type="compact", 
            max_results=3
        )
        
        fallback_content = f"""Based on available search results:

{fallback_summary}

Note: I encountered an error generating the full analysis and visualizations. The above represents the key findings for: "{user_query}"
"""
        
        state_update.update({
            "messages": [AIMessage(content=fallback_content)],
            "is_generating": False,
            "generation_error": str(e),
            "fallback_used": True,
            "visualization_created": False
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

 