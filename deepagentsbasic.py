# import os
# import json
# import re
# from typing import Literal, Dict, List, Any, Optional
# from core.llm_manager import LLMManager, LLMProvider
# from core.search_manager import create_search_manager
# from deepagents import create_deep_agent

# # Initialize managers
# manager = LLMManager()
# llm = manager.get_chat_model(
#     provider=LLMProvider.OPENAI,
#     temperature=0.7
# )
# search_manager = create_search_manager()

# def internet_search(
#     query: str,
#     max_results: int = 5,
#     topic: Literal["general", "news", "finance"] = "general",
#     include_raw_content: bool = False,
# ):
#     """Run a web search - this tool will be interrupted for sensitive content"""
#     return search_manager.search(
#         query=query,
#         provider="tavily",
#         max_results=max_results,
#         include_raw_content=include_raw_content,
#         topic=topic,
#     )

# def sensitive_content_search(
#     query: str,
#     max_results: int = 5,
#     topic: Literal["general", "news", "finance"] = "general",
#     include_raw_content: bool = False,
# ):
#     """Search tool specifically for sensitive content - requires age verification"""
#     return search_manager.search(
#         query=query,
#         max_results=max_results,
#         include_raw_content=include_raw_content,
#         topic=topic,
#     )

# def extract_and_format_data(content: str) -> Dict[str, Any]:
#     """Comprehensive tool to extract ALL numeric data and create unified JSON for graphs/tables"""
    
#     # Enhanced patterns for maximum data extraction
#     patterns = [
#         # Years with context (2020, 2021, etc.)
#         r'(\b(?:19|20)\d{2})\b[^\d]*?(\d+(?:\.\d+)?%?|\$[\d,]+(?:\.\d+)?)',
#         # Percentages with detailed context
#         r'(\d+(?:\.\d+)?%)\s*([^.!?\n]{5,100})',
#         # Currency with context
#         r'([\$€£¥]\s*[\d,]+(?:\.\d{2})?)\s*([^.!?\n]{5,100})',
#         # Large numbers with commas
#         r'(\b\d{1,3}(?:,\d{3})+(?:\.\d+)?)\s*([^.!?\n]{5,100})',
#         # Growth/decline indicators
#         r'((?:grew|increased|rose|up|declined|fell|dropped|down)\s+(?:by\s+)?(\d+(?:\.\d+)?%?))',
#         # Market share patterns
#         r'(market\s+share[^.!?\n]*?(\d+(?:\.\d+)?%?))',
#         # Time period ranges
#         r'(from\s+(\d+(?:\.\d+)?%?)\s+to\s+(\d+(?:\.\d+)?%?))',
#         # Fold increases (ten-fold, 5-fold, etc.)
#         r'((\d+|\w+)-fold)',
#         # Comparative numbers (more than, less than, under, over)
#         r'((?:more than|less than|under|over)\s+(\d+(?:\.\d+)?%?))',
#         # General numbers with units
#         r'(\b\d+(?:\.\d+)?)\s*(million|billion|thousand|vehicles|cars|units|people)',
#     ]
    
#     extracted_items = []
    
#     # Process each pattern
#     for i, pattern in enumerate(patterns):
#         matches = re.finditer(pattern, content, re.IGNORECASE)
#         for match in matches:
#             groups = match.groups()
#             full_match = match.group(0)
            
#             # Extract numeric values from the match
#             numbers = re.findall(r'\d+(?:\.\d+)?', full_match)
            
#             for num_str in numbers:
#                 try:
#                     numeric_value = float(num_str)
                    
#                     # Determine data type and context
#                     context = full_match
#                     data_type = "number"
                    
#                     if '%' in full_match:
#                         data_type = "percentage"
#                     elif any(symbol in full_match for symbol in ['$', '€', '£', '¥']):
#                         data_type = "currency"
#                     elif any(word in full_match.lower() for word in ['million', 'billion', 'thousand']):
#                         data_type = "large_number"
#                     elif any(word in full_match.lower() for word in ['grew', 'increased', 'declined', 'fell']):
#                         data_type = "growth_metric"
#                     elif 'market share' in full_match.lower():
#                         data_type = "market_share"
#                     elif any(word in full_match.lower() for word in ['fold']):
#                         data_type = "multiplier"
#                     elif re.search(r'\b(?:19|20)\d{2}\b', full_match):
#                         data_type = "yearly_data"
                    
#                     # Extract year if present
#                     year_match = re.search(r'\b((?:19|20)\d{2})\b', context)
#                     year = int(year_match.group(1)) if year_match else None
                    
#                     # Extract company/entity if present
#                     company_patterns = [
#                         r'\b(Tesla|BYD|Ford|GM|Volkswagen|Toyota|BMW|Mercedes|Audi|Nissan|Hyundai)\b',
#                         r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b(?=\s+(?:sales|revenue|market|share))'
#                     ]
                    
#                     entity = None
#                     for comp_pattern in company_patterns:
#                         comp_match = re.search(comp_pattern, context, re.IGNORECASE)
#                         if comp_match:
#                             entity = comp_match.group(1)
#                             break
                    
#                     # Extract measurement unit
#                     unit_match = re.search(r'\b(vehicles|cars|units|people|million|billion|thousand|%|\$|€|£|¥)\b', context.lower())
#                     unit = unit_match.group(1) if unit_match else None
                    
#                     extracted_items.append({
#                         'value': numeric_value,
#                         'original_text': full_match.strip(),
#                         'context': context.strip(),
#                         'data_type': data_type,
#                         'year': year,
#                         'entity': entity,
#                         'unit': unit,
#                         'pattern_index': i,
#                         'position_in_text': match.start()
#                     })
                    
#                 except ValueError:
#                     continue
    
#     # Remove duplicates and sort by position in text
#     seen = set()
#     unique_items = []
#     for item in sorted(extracted_items, key=lambda x: x['position_in_text']):
#         # Create a key for deduplication
#         key = (item['value'], item['data_type'], item['year'], item['entity'])
#         if key not in seen:
#             seen.add(key)
#             unique_items.append(item)
    
#     # Organize data by categories for easy graphing/tabling
#     organized_data = {
#         'yearly_data': {},
#         'market_share': {},
#         'growth_metrics': {},
#         'financial_data': {},
#         'company_data': {},
#         'percentages': {},
#         'large_numbers': {},
#         'multipliers': {}
#     }
    
#     # Group data by type and entity
#     for item in unique_items:
#         data_type = item['data_type']
#         entity = item['entity'] or 'general'
#         year = item['year']
#         value = item['value']
        
#         # Organize by data type
#         if data_type == 'yearly_data' and year:
#             if entity not in organized_data['yearly_data']:
#                 organized_data['yearly_data'][entity] = {}
#             organized_data['yearly_data'][entity][str(year)] = {
#                 'value': value,
#                 'unit': item['unit'],
#                 'context': item['context']
#             }
        
#         elif data_type == 'market_share':
#             if entity not in organized_data['market_share']:
#                 organized_data['market_share'][entity] = {}
#             key = str(year) if year else 'current'
#             organized_data['market_share'][entity][key] = {
#                 'value': value,
#                 'unit': item['unit'],
#                 'context': item['context']
#             }
        
#         elif data_type == 'growth_metric':
#             if entity not in organized_data['growth_metrics']:
#                 organized_data['growth_metrics'][entity] = []
#             organized_data['growth_metrics'][entity].append({
#                 'value': value,
#                 'unit': item['unit'],
#                 'context': item['context'],
#                 'year': year
#             })
        
#         elif data_type == 'currency':
#             if entity not in organized_data['financial_data']:
#                 organized_data['financial_data'][entity] = {}
#             key = str(year) if year else 'current'
#             organized_data['financial_data'][entity][key] = {
#                 'value': value,
#                 'unit': item['unit'],
#                 'context': item['context']
#             }
        
#         elif entity and entity != 'general':
#             if entity not in organized_data['company_data']:
#                 organized_data['company_data'][entity] = []
#             organized_data['company_data'][entity].append({
#                 'value': value,
#                 'data_type': data_type,
#                 'unit': item['unit'],
#                 'context': item['context'],
#                 'year': year
#             })
    
#     # Create comprehensive unified structure
#     unified_data = {
#         'metadata': {
#             'total_data_points': len(unique_items),
#             'extraction_timestamp': '2025-01-01T00:00:00Z',
#             'data_found': len(unique_items) > 0,
#             'text_length': len(content),
#             'unique_entities': list(set(item['entity'] for item in unique_items if item['entity'])),
#             'unique_years': sorted(list(set(item['year'] for item in unique_items if item['year']))),
#             'data_types_found': list(set(item['data_type'] for item in unique_items))
#         },
        
#         'raw_data_points': unique_items,  # All extracted points with full detail
        
#         'organized_data': organized_data,  # Grouped for easy visualization
        
#         'graph_ready_datasets': {
#             'time_series': {},  # For line charts
#             'categorical': {},  # For bar charts
#             'percentage_breakdown': {},  # For pie charts
#             'comparison_data': {}  # For comparative analysis
#         },
        
#         'table_ready_data': {
#             'summary_table': [],
#             'detailed_table': [],
#             'yearly_comparison': {},
#             'entity_comparison': {}
#         }
#     }
    
#     # Prepare graph-ready datasets
#     for entity, years_data in organized_data['yearly_data'].items():
#         if len(years_data) > 1:  # Time series data
#             unified_data['graph_ready_datasets']['time_series'][entity] = {
#                 'labels': sorted(years_data.keys()),
#                 'values': [years_data[year]['value'] for year in sorted(years_data.keys())],
#                 'units': [years_data[year]['unit'] for year in sorted(years_data.keys())]
#             }
    
#     # Prepare table-ready data
#     for item in unique_items:
#         unified_data['table_ready_data']['detailed_table'].append({
#             'Entity': item['entity'] or 'N/A',
#             'Year': item['year'] or 'N/A',
#             'Value': item['value'],
#             'Unit': item['unit'] or 'N/A',
#             'Type': item['data_type'],
#             'Context': item['context'][:100] + '...' if len(item['context']) > 100 else item['context']
#         })
    
#     return unified_data

# # Enhanced agent instructions with focus on unified data
# agent_instructions = """You are a research coordinator that creates comprehensive reports with ALL numeric data in ONE unified JSON structure.

# CRITICAL REQUIREMENTS:
# - Extract EVERY number from search results using extract_and_format_data
# - Include ALL data in a SINGLE comprehensive JSON block
# - NO separate JSON fragments - everything must be unified
# - Structure data for both graphs AND tables
# - Provide maximum detail and context for each data point

# WORKFLOW:
# 1. CONTENT CLASSIFICATION: Call 'content-classifier' to check if content is safe/sensitive/banned
# 2. SEARCH PHASE: Use appropriate search tool based on classification
# 3. DATA EXTRACTION PHASE: Use extract_and_format_data tool on ALL search results
# 4. VISUALIZATION PLANNING: Call 'data-visualizer' with the unified data
# 5. REPORT PHASE: Call 'report-writer' with the complete unified JSON structure

# The final report MUST contain ONE comprehensive JSON block with all numeric data organized for easy graphing and table creation."""

# # Content classifier subagent
# content_classifier_subagent = {
#     "name": "content-classifier",
#     "description": "Classifies content as safe, sensitive, or banned",
#     "prompt": """Analyze the user query and classify it as "safe", "sensitive", or "banned".

#     RESPONSE FORMAT (JSON only):
#     {
#         "classification": "safe" | "sensitive" | "banned",
#         "reason": "Brief explanation"
#     }

#     BANNED content includes: illegal activities, violence, hate speech, child exploitation, terrorism, privacy violations, financial crimes, dangerous medical advice."""
# }

# # Enhanced Data Visualizer for unified data
# data_visualizer_subagent = {
#     "name": "data-visualizer",
#     "description": "Analyzes unified numeric data and provides comprehensive visualization strategy",
#     "prompt": """You are a data visualization expert. Analyze the unified numeric data structure and provide comprehensive recommendations.

#     RESPONSE FORMAT (JSON):
#     {
#         "visualization_strategy": {
#             "primary_chart_type": "line" | "bar" | "pie" | "scatter" | "table",
#             "secondary_charts": ["chart_type1", "chart_type2"],
#             "reasoning": "Why these visualizations work best"
#         },
#         "graph_configurations": {
#             "chart1": {
#                 "type": "line",
#                 "title": "Chart title",
#                 "data_source": "path to data in unified JSON",
#                 "x_axis": "label",
#                 "y_axis": "label"
#             }
#         },
#         "table_configurations": {
#             "summary_table": {
#                 "columns": ["col1", "col2", "col3"],
#                 "data_source": "path to data in unified JSON"
#             }
#         }
#     }

#     Focus on extracting maximum value from the unified data structure."""
# }

# # Ban response subagent
# ban_response_subagent = {
#     "name": "ban-response",
#     "description": "Generates appropriate responses for banned content",
#     "prompt": """Generate a clear, professional response for banned content:

#     🚫 **CONTENT BLOCKED**
#     **Reason:** [Specific policy violation]
#     **Alternative:** [Suggest related acceptable topics if possible]"""
# }

# # Enhanced Report writer for unified data presentation
# report_subagent = {
#     "name": "report-writer",
#     "description": "Creates comprehensive reports with unified JSON data structure",
#     "prompt": """Create a professional research report with ONE comprehensive JSON block containing ALL numeric data.

#     STRUCTURE:
    
#     # RESEARCH REPORT: [Topic]

#     ## EXECUTIVE SUMMARY
#     [Key findings in 2-3 sentences, referencing specific numbers from the data]

#     ## KEY FINDINGS
#     [Main discoveries with specific numeric references]

#     ## COMPREHENSIVE DATA ANALYSIS

#     ### Complete Numeric Dataset
#     ```json
#     [Include the COMPLETE unified JSON structure from extract_and_format_data here]
#     ```

#     ### Visualization Recommendations
#     ```json
#     [Include recommendations from data-visualizer here]
#     ```

#     ## DATA INSIGHTS
#     [Detailed analysis referencing specific values from the unified JSON]
#     - Reference specific data points by their path in the JSON
#     - Highlight trends found in the time_series data
#     - Compare entities using the organized_data structure

#     ## CONCLUSIONS & RECOMMENDATIONS
#     [Actionable insights based on comprehensive data analysis]

#     ---
#     *Report with comprehensive unified data extraction*

#     CRITICAL REQUIREMENTS:
#     - Include the COMPLETE unified JSON structure (not fragments)
#     - All numeric data must be in ONE JSON block
#     - Reference specific data paths in your analysis
#     - Ensure data is ready for both graphing and table display"""
# }

# # Human interrupt configuration
# interrupt_config = {
#     "sensitive_content_search": {
#         "allow_ignore": False,
#         "allow_respond": True,  
#         "allow_edit": False,
#         "allow_accept": True
#     }
# }

# # Create the enhanced agent
# app = create_deep_agent(
#     tools=[internet_search, sensitive_content_search, extract_and_format_data],
#     instructions=agent_instructions,
#     subagents=[
#         content_classifier_subagent,
#         data_visualizer_subagent, 
#         ban_response_subagent,
#         report_subagent
#     ],
#     model=llm,
#     interrupt_config=interrupt_config
# )

# def verify_age_and_consent():
#     """Handle age verification for sensitive content"""
#     print("\n" + "="*60)
#     print("AGE VERIFICATION REQUIRED")
#     print("="*60)
#     print("This research contains sensitive content requiring age verification.")
    
#     while True:
#         age_input = input("Are you 18 years or older? (yes/no): ").lower().strip()
#         if age_input in ['yes', 'y']:
#             print("Age verification confirmed.")
#             break
#         elif age_input in ['no', 'n']:
#             print("Access denied. Content only available to users 18+.")
#             return False
#         else:
#             print("Please answer 'yes' or 'no'")
    
#     while True:
#         consent_input = input("Proceed with mature content research? (yes/no): ").lower().strip()
#         if consent_input in ['yes', 'y']:
#             print("Proceeding with research...")
#             return True
#         elif consent_input in ['no', 'n']:
#             print("Research cancelled.")
#             return False
#         else:
#             print("Please answer 'yes' or 'no'")

# def handle_interrupt_response(response_needed=True):
#     """Handle the human-in-the-loop interrupt"""
#     if response_needed:
#         verified = verify_age_and_consent()
#         return "APPROVED: User verified" if verified else "DENIED: Verification failed"
#     return "APPROVED"

# def is_content_banned_response(content: str) -> bool:
#     """Check if response indicates banned content"""
#     return "🚫 **CONTENT BLOCKED**" in content

# if __name__ == "__main__":
#     print("🚀 COMPREHENSIVE RESEARCH AGENT v2.0")
#     print("="*60)
#     print("✅ Advanced content safety classification")
#     print("✅ Age verification for sensitive content") 
#     print("✅ Comprehensive numerical data extraction")
#     print("✅ File management for workflow control")
#     print("✅ Unified JSON structure for all data")
#     print("✅ Professional report generation")
#     print("✅ Recursion prevention & error handling")
#     print("✅ Markdown formatting ready for rendering")
#     print("✅ Graph and table ready datasets")
#     print("="*60)
#     print("\nFEATURES:")
#     print("📊 Detailed reports with Introduction, Overview, Insights, Summary")
#     print("📁 File-based workflow management")
#     print("🎯 Single comprehensive JSON with all numeric data")
#     print("📈 Visualization recommendations included")
#     print("🎨 Well-styled markdown output")
#     print("\nAgent ready for comprehensive research tasks!")
#     print("Recursion limit set to 15 to prevent infinite loops.")
#     print("All data will be unified in markdown with embedded JSON!")


import json
import re
import asyncio
import time
from typing import Literal, Dict, List, Any, Optional, Tuple
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import create_search_manager
from deepagents import create_deep_agent
import logging
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enhanced error handling and retry decorators
def retry_on_api_error(max_retries=3, delay=2.0, backoff_factor=2.0):
    """Decorator for retrying API calls with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    retryable_errors = [
                        'server had an error', 'timeout', 'rate limit',
                        'service unavailable', 'internal server error',
                        'bad gateway', 'connection error'
                    ]
                    
                    is_retryable = any(err in error_msg for err in retryable_errors)
                    
                    if attempt < max_retries and is_retryable:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor
                    elif not is_retryable:
                        logger.error(f"Non-retryable error: {e}")
                        break
                    else:
                        logger.error(f"Max retries ({max_retries}) exceeded")
                        break
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    retryable_errors = [
                        'server had an error', 'timeout', 'rate limit',
                        'service unavailable', 'internal server error',
                        'bad gateway', 'connection error'
                    ]
                    
                    is_retryable = any(err in error_msg for err in retryable_errors)
                    
                    if attempt < max_retries and is_retryable:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s...")
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    elif not is_retryable:
                        logger.error(f"Non-retryable error: {e}")
                        break
                    else:
                        logger.error(f"Max retries ({max_retries}) exceeded")
                        break
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

# Initialize managers with error handling
try:
    manager = LLMManager()
    llm = manager.get_chat_model(
        provider=LLMProvider.OPENAI,
        temperature=0.7,
        request_timeout=60,
        max_retries=3
    )
    search_manager = create_search_manager()
    logger.info("✅ Managers initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize managers: {e}")
    raise

@retry_on_api_error(max_retries=3, delay=1.0)
def multi_provider_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = True,
) -> Dict[str, Any]:
    """Search using ALL providers and consolidate results"""
    try:
        logger.info(f"🔍 Multi-provider search for: {query}")
        
        # Define all available providers
        providers = ["tavily", "duckduckgo", "wikipedia"]
        all_results = {}
        consolidated_results = []
        search_metadata = {
            "query": query,
            "providers_used": [],
            "providers_failed": [],
            "total_results": 0,
            "search_timestamp": datetime.now().isoformat()
        }
        
        # Search with each provider
        for provider in providers:
            try:
                logger.info(f"🔍 Searching with {provider}...")
                result = search_manager.search(
                    query=query,
                    provider=provider,
                    max_results=max_results,
                    include_raw_content=include_raw_content,
                    topic=topic,
                )
                
                if result and 'results' in result:
                    all_results[provider] = result
                    search_metadata["providers_used"].append(provider)
                    
                    # Add provider info to each result
                    for res in result['results']:
                        res['source_provider'] = provider
                        res['confidence_score'] = calculate_source_confidence(res, provider)
                        consolidated_results.append(res)
                    
                    logger.info(f"✅ {provider} returned {len(result['results'])} results")
                else:
                    logger.warning(f"⚠️ {provider} returned no results")
                    search_metadata["providers_failed"].append(f"{provider}: No results")
                    
            except Exception as e:
                logger.error(f"❌ {provider} search failed: {e}")
                search_metadata["providers_failed"].append(f"{provider}: {str(e)}")
                all_results[provider] = {"error": str(e), "results": []}
        
        # Sort consolidated results by confidence score
        consolidated_results.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)
        search_metadata["total_results"] = len(consolidated_results)
        
        # Create comprehensive response
        consolidated_response = {
            "consolidated_results": consolidated_results[:max_results * len(providers)],
            "provider_breakdown": all_results,
            "search_metadata": search_metadata,
            "data_quality": analyze_result_quality(consolidated_results),
            "numeric_data_preview": extract_numeric_preview(consolidated_results)
        }
        
        logger.info(f"✅ Multi-provider search completed. Total results: {len(consolidated_results)}")
        return consolidated_response
        
    except Exception as e:
        logger.error(f"❌ Multi-provider search failed: {e}")
        return {
            "consolidated_results": [],
            "provider_breakdown": {},
            "search_metadata": {
                "query": query,
                "error": str(e),
                "providers_used": [],
                "providers_failed": ["all"],
                "total_results": 0
            },
            "data_quality": {"overall_score": 0, "issues": ["Search system failure"]},
            "numeric_data_preview": []
        }

def calculate_source_confidence(result: Dict, provider: str) -> float:
    """Calculate confidence score for a search result"""
    try:
        score = 0.0
        
        # Base score by provider reliability
        provider_scores = {"wikipedia": 0.9, "tavily": 0.8, "duckduckgo": 0.7}
        score += provider_scores.get(provider, 0.5)
        
        # Content quality indicators
        content = result.get('content', '') or result.get('snippet', '')
        if content:
            # Check for numeric data
            if re.search(r'\d+(?:\.\d+)?%|\$[\d,]+|\d{4}|\d+(?:,\d{3})+', content):
                score += 0.1
            
            # Check for authoritative terms
            auth_terms = ['study', 'research', 'report', 'data', 'statistics', 'official']
            if any(term in content.lower() for term in auth_terms):
                score += 0.1
        
        # URL authority
        url = result.get('url', '')
        if url:
            authoritative_domains = ['.gov', '.edu', '.org', 'wikipedia', 'reuters', 'bloomberg']
            if any(domain in url for domain in authoritative_domains):
                score += 0.2
        
        return min(score, 1.0)
        
    except Exception:
        return 0.5

def analyze_result_quality(results: List[Dict]) -> Dict[str, Any]:
    """Analyze overall quality of search results"""
    try:
        if not results:
            return {"overall_score": 0, "issues": ["No results found"], "strengths": []}
        
        total_confidence = sum(r.get('confidence_score', 0) for r in results)
        avg_confidence = total_confidence / len(results)
        
        # Count data-rich results
        data_rich_count = sum(1 for r in results if has_numeric_data(r.get('content', '')))
        
        # Identify issues and strengths
        issues = []
        strengths = []
        
        if avg_confidence < 0.6:
            issues.append("Low average source confidence")
        else:
            strengths.append("High-quality sources")
            
        if data_rich_count < len(results) * 0.3:
            issues.append("Limited numeric data available")
        else:
            strengths.append("Rich numeric data found")
        
        return {
            "overall_score": avg_confidence,
            "data_richness": data_rich_count / len(results),
            "total_sources": len(results),
            "issues": issues,
            "strengths": strengths
        }
        
    except Exception as e:
        return {"overall_score": 0, "issues": [f"Analysis error: {str(e)}"], "strengths": []}

def has_numeric_data(content: str) -> bool:
    """Check if content contains significant numeric data"""
    try:
        numeric_patterns = [
            r'\d+(?:\.\d+)?%',  # Percentages
            r'\$[\d,]+(?:\.\d+)?',  # Currency
            r'\b\d{4}\b',  # Years
            r'\d+(?:,\d{3})+',  # Large numbers with commas
            r'\d+(?:\.\d+)?\s*(?:million|billion|thousand)',  # Scaled numbers
        ]
        return any(re.search(pattern, content) for pattern in numeric_patterns)
    except Exception:
        return False

def extract_numeric_preview(results: List[Dict]) -> List[Dict]:
    """Extract preview of numeric data from search results"""
    try:
        preview_data = []
        for result in results[:5]:  # Preview from top 5 results
            content = result.get('content', '') or result.get('snippet', '')
            if has_numeric_data(content):
                numbers = re.findall(r'\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?|\b\d{4}\b|\d+(?:,\d{3})+', content)
                if numbers:
                    preview_data.append({
                        "source": result.get('url', 'Unknown'),
                        "provider": result.get('source_provider', 'Unknown'),
                        "sample_numbers": numbers[:3],  # First 3 numbers found
                        "confidence": result.get('confidence_score', 0)
                    })
        return preview_data
    except Exception:
        return []

@retry_on_api_error(max_retries=3, delay=1.0)
def enhanced_data_extraction(content: str) -> Dict[str, Any]:
    """Enhanced data extraction with comprehensive numeric analysis"""
    try:
        logger.info("📊 Starting enhanced data extraction...")
        
        if not content or len(content.strip()) == 0:
            return create_empty_data_structure("Empty content provided")
        
        # Enhanced patterns for maximum data extraction
        extraction_patterns = {
            'percentages': r'(\d+(?:\.\d+)?%)',
            'currency': r'([\$€£¥]\s*[\d,]+(?:\.\d{2})?)',
            'years': r'\b((?:19|20)\d{2})\b',
            'large_numbers': r'(\b\d{1,3}(?:,\d{3})+(?:\.\d+)?)',
            'decimal_numbers': r'(\b\d+\.\d+\b)',
            'growth_metrics': r'((?:grew|increased|rose|up|declined|fell|dropped|down)\s+(?:by\s+)?(\d+(?:\.\d+)?%?))',
            'market_data': r'(market\s+share[^.!?\n]*?(\d+(?:\.\d+)?%?))',
            'comparisons': r'(from\s+(\d+(?:\.\d+)?%?)\s+to\s+(\d+(?:\.\d+)?%?))',
            'multipliers': r'((\d+|\w+)-fold)',
            'scaled_numbers': r'(\b\d+(?:\.\d+)?)\s*(million|billion|thousand|vehicles|cars|units|people)',
        }
        
        extracted_data = []
        
        # Extract using each pattern
        for pattern_name, pattern in extraction_patterns.items():
            try:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    process_match(match, pattern_name, content, extracted_data)
            except Exception as e:
                logger.warning(f"⚠️ Pattern '{pattern_name}' failed: {e}")
                continue
        
        # Remove duplicates and organize
        unique_data = deduplicate_data(extracted_data)
        organized_data = organize_data_by_category(unique_data)
        
        # Generate tables and charts data
        table_data = generate_table_data(unique_data)
        chart_data = generate_chart_data(organized_data)
        
        # Create comprehensive response
        result = {
            'metadata': {
                'total_data_points': len(unique_data),
                'extraction_timestamp': datetime.now().isoformat(),
                'data_found': len(unique_data) > 0,
                'text_length': len(content),
                'extraction_success': True,
                'data_categories': list(organized_data.keys())
            },
            'raw_data_points': unique_data,
            'organized_data': organized_data,
            'table_data': table_data,
            'chart_data': chart_data,
            'numeric_summary': generate_numeric_summary(unique_data)
        }
        
        logger.info(f"✅ Enhanced extraction completed. Found {len(unique_data)} data points")
        return result
        
    except Exception as e:
        logger.error(f"❌ Enhanced data extraction failed: {e}")
        return create_empty_data_structure(f"Extraction error: {str(e)}")

def process_match(match, pattern_name, content, extracted_data):
    """Process a regex match and extract structured data"""
    try:
        full_match = match.group(0)
        position = match.start()
        
        # Extract context (surrounding text)
        context_start = max(0, position - 100)
        context_end = min(len(content), position + len(full_match) + 100)
        context = content[context_start:context_end]
        
        # Extract numeric values
        numbers = re.findall(r'\d+(?:\.\d+)?', full_match)
        
        for num_str in numbers:
            try:
                numeric_value = float(num_str)
                
                # Extract additional metadata
                year = extract_year_from_context(context)
                entity = extract_entity_from_context(context)
                unit = extract_unit_from_match(full_match)
                
                extracted_data.append({
                    'value': numeric_value,
                    'original_text': full_match.strip(),
                    'context': context.strip(),
                    'data_type': pattern_name,
                    'year': year,
                    'entity': entity,
                    'unit': unit,
                    'position': position,
                    'confidence': calculate_data_confidence(full_match, context, pattern_name)
                })
                
            except (ValueError, TypeError):
                continue
                
    except Exception as e:
        logger.warning(f"⚠️ Failed to process match: {e}")

def extract_year_from_context(context: str) -> Optional[int]:
    """Extract year from context"""
    year_match = re.search(r'\b((?:19|20)\d{2})\b', context)
    return int(year_match.group(1)) if year_match else None

def extract_entity_from_context(context: str) -> Optional[str]:
    """Extract entity/company name from context"""
    # Common entity patterns
    entity_patterns = [
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b(?=\s+(?:sales|revenue|market|share|grew|increased))',
        r'\b(Tesla|BYD|Ford|GM|Volkswagen|Toyota|BMW|Mercedes|Audi|Nissan|Hyundai)\b',
        r'\b([A-Z]{2,})\b'  # Acronyms
    ]
    
    for pattern in entity_patterns:
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def extract_unit_from_match(match_text: str) -> Optional[str]:
    """Extract measurement unit from match"""
    unit_pattern = r'\b(vehicles|cars|units|people|million|billion|thousand|%|\$|€|£|¥|USD|EUR)\b'
    unit_match = re.search(unit_pattern, match_text.lower())
    return unit_match.group(1) if unit_match else None

def calculate_data_confidence(match_text: str, context: str, pattern_name: str) -> float:
    """Calculate confidence score for extracted data"""
    try:
        score = 0.5  # Base score
        
        # Pattern-based confidence
        pattern_confidence = {
            'percentages': 0.9,
            'currency': 0.8,
            'years': 0.7,
            'large_numbers': 0.6,
            'growth_metrics': 0.8
        }
        score += pattern_confidence.get(pattern_name, 0.5) * 0.3
        
        # Context quality indicators
        quality_indicators = ['official', 'report', 'study', 'data', 'statistics']
        if any(indicator in context.lower() for indicator in quality_indicators):
            score += 0.2
            
        return min(score, 1.0)
    except Exception:
        return 0.5

def deduplicate_data(data_list: List[Dict]) -> List[Dict]:
    """Remove duplicate data points"""
    try:
        seen = set()
        unique_data = []
        
        for item in sorted(data_list, key=lambda x: x['position']):
            key = (item['value'], item['data_type'], item['year'], item['entity'])
            if key not in seen:
                seen.add(key)
                unique_data.append(item)
        
        return unique_data
    except Exception:
        return data_list

def organize_data_by_category(data_list: List[Dict]) -> Dict[str, Any]:
    """Organize data by categories for analysis"""
    try:
        categories = {
            'temporal_data': {},
            'financial_data': {},
            'performance_metrics': {},
            'market_data': {},
            'comparative_data': {}
        }
        
        for item in data_list:
            # Categorize by data type and content
            if item['year']:
                if item['entity'] not in categories['temporal_data']:
                    categories['temporal_data'][item['entity']] = {}
                categories['temporal_data'][item['entity']][str(item['year'])] = item
            
            if item['data_type'] in ['currency', 'financial']:
                entity = item['entity'] or 'general'
                if entity not in categories['financial_data']:
                    categories['financial_data'][entity] = []
                categories['financial_data'][entity].append(item)
            
            # Add to other categories based on patterns
            if 'market' in item['context'].lower():
                entity = item['entity'] or 'general'
                if entity not in categories['market_data']:
                    categories['market_data'][entity] = []
                categories['market_data'][entity].append(item)
        
        return categories
    except Exception:
        return {}

def generate_table_data(data_list: List[Dict]) -> Dict[str, Any]:
    """Generate table-ready data structures"""
    try:
        # Summary table
        summary_table = []
        for item in data_list:
            summary_table.append({
                'Entity': item.get('entity', 'N/A'),
                'Year': item.get('year', 'N/A'),
                'Value': item['value'],
                'Unit': item.get('unit', 'N/A'),
                'Type': item['data_type'],
                'Confidence': f"{item.get('confidence', 0):.1%}"
            })
        
        # Detailed analysis table
        detailed_table = []
        for item in data_list:
            detailed_table.append({
                'Data Point': item['original_text'],
                'Numeric Value': item['value'],
                'Context': item['context'][:100] + '...' if len(item['context']) > 100 else item['context'],
                'Source Position': item['position'],
                'Confidence Score': f"{item.get('confidence', 0):.1%}"
            })
        
        return {
            'summary_table': summary_table,
            'detailed_table': detailed_table,
            'total_records': len(data_list)
        }
    except Exception:
        return {'summary_table': [], 'detailed_table': [], 'total_records': 0}

def generate_chart_data(organized_data: Dict) -> Dict[str, Any]:
    """Generate chart-ready data structures"""
    try:
        chart_configs = {}
        
        # Time series charts
        for entity, yearly_data in organized_data.get('temporal_data', {}).items():
            if len(yearly_data) > 1:
                years = sorted(yearly_data.keys())
                values = [yearly_data[year]['value'] for year in years]
                
                chart_configs[f'timeseries_{entity}'] = {
                    'type': 'line',
                    'title': f'{entity} - Temporal Analysis',
                    'data': {
                        'labels': years,
                        'values': values,
                        'entity': entity
                    }
                }
        
        # Comparison charts
        entities_data = {}
        for item_list in organized_data.values():
            if isinstance(item_list, dict):
                for entity, data in item_list.items():
                    if entity not in entities_data:
                        entities_data[entity] = []
                    if isinstance(data, list):
                        entities_data[entity].extend(data)
                    else:
                        entities_data[entity].append(data)
        
        if len(entities_data) > 1:
            chart_configs['entity_comparison'] = {
                'type': 'bar',
                'title': 'Entity Comparison',
                'data': {
                    'entities': list(entities_data.keys()),
                    'values': [len(data) for data in entities_data.values()],
                    'description': 'Number of data points per entity'
                }
            }
        
        return chart_configs
    except Exception:
        return {}

def generate_numeric_summary(data_list: List[Dict]) -> Dict[str, Any]:
    """Generate summary statistics"""
    try:
        if not data_list:
            return {'total_points': 0, 'summary': 'No numeric data found'}
        
        values = [item['value'] for item in data_list if isinstance(item['value'], (int, float))]
        
        summary = {
            'total_data_points': len(data_list),
            'numeric_values_count': len(values),
            'value_range': {
                'min': min(values) if values else 0,
                'max': max(values) if values else 0,
                'average': sum(values) / len(values) if values else 0
            },
            'data_types_found': list(set(item['data_type'] for item in data_list)),
            'entities_found': list(set(item['entity'] for item in data_list if item['entity'])),
            'years_covered': sorted(list(set(item['year'] for item in data_list if item['year'])))
        }
        
        return summary
    except Exception:
        return {'total_points': 0, 'summary': 'Summary generation failed'}

def create_empty_data_structure(error_msg: str) -> Dict[str, Any]:
    """Create empty data structure for error cases"""
    return {
        'metadata': {
            'total_data_points': 0,
            'extraction_timestamp': datetime.now().isoformat(),
            'data_found': False,
            'extraction_success': False,
            'error': error_msg
        },
        'raw_data_points': [],
        'organized_data': {},
        'table_data': {'summary_table': [], 'detailed_table': [], 'total_records': 0},
        'chart_data': {},
        'numeric_summary': {'total_points': 0, 'summary': error_msg}
    }

# Enhanced agent instructions
agent_instructions = """You are a comprehensive research coordinator that ALWAYS uses ALL available search providers and delivers complete reports with numeric proof.

CRITICAL WORKFLOW:
1. MULTI-PROVIDER SEARCH: Always use multi_provider_search() to get data from ALL providers (Tavily, DuckDuckGo, Wikipedia)
2. DATA CONSOLIDATION: Merge and analyze results from all providers
3. NUMERIC EXTRACTION: Use enhanced_data_extraction() on ALL content to find numeric proof
4. EVIDENCE COMPILATION: Create tables and charts proving your findings
5. COMPREHENSIVE REPORTING: Generate complete report with all evidence

SEARCH STRATEGY:
- Use broad queries initially, then specific data-focused queries
- Always search for: "[topic] statistics", "[topic] data", "[topic] numbers", "[topic] research"
- Consolidate results from all providers for maximum coverage
- Extract numeric evidence from ALL sources

EVIDENCE REQUIREMENTS:
- Find numerical proof for ALL claims
- Create data tables showing evidence
- Generate charts when temporal or comparative data exists
- Calculate confidence scores for all data points
- Cross-reference data across multiple sources

FINAL OUTPUT: Always end with the complete report from report_writer subagent containing:
- Consolidated multi-provider search results
- Comprehensive data analysis with tables/charts
- Numeric proof supporting all conclusions
- Source attribution with confidence scores"""

# Enhanced subagents
content_classifier_subagent = {
    "name": "content-classifier",
    "description": "Classifies content and determines search strategy",
    "prompt": """Analyze the query and provide classification plus search strategy.

    RESPONSE FORMAT (JSON):
    {
        "classification": "safe" | "sensitive" | "banned",
        "search_strategy": {
            "primary_queries": ["query1", "query2", "query3"],
            "data_focused_queries": ["data query1", "statistics query2"],
            "expected_data_types": ["percentages", "currency", "years", "growth_metrics"]
        },
        "providers_to_emphasize": ["tavily", "wikipedia", "duckduckgo"],
        "confidence": "high" | "medium" | "low"
    }"""
}

data_visualizer_subagent = {
    "name": "data-visualizer", 
    "description": "Creates visualization strategy and chart specifications",
    "prompt": """Analyze extracted data and create comprehensive visualization plan.

    RESPONSE FORMAT (JSON):
    {
        "visualization_strategy": {
            "primary_charts": [
                {
                    "type": "line" | "bar" | "pie" | "scatter" | "table",
                    "title": "Chart Title",
                    "data_source": "path.to.data",
                    "purpose": "What this chart proves/shows"
                }
            ],
            "data_tables": [
                {
                    "title": "Table Title", 
                    "columns": ["col1", "col2", "col3"],
                    "data_source": "path.to.table.data",
                    "purpose": "What this table proves"
                }
            ]
        },
        "evidence_strength": "strong" | "moderate" | "weak",
        "numeric_proof_summary": "Summary of numeric evidence found"
    }"""
}

report_writer_subagent = {
    "name": "report-writer",
    "description": "Creates the final comprehensive report with all evidence",
    "prompt": """Create a complete research report with ALL numeric evidence and visualizations.

    MANDATORY STRUCTURE:

    # 📊 Research Report: [Topic]

    ## 🎯 Executive Summary
    
    **Key Findings with Numeric Proof:**
    • [Finding 1 with specific numbers and sources]
    • [Finding 2 with specific numbers and sources] 
    • [Finding 3 with specific numbers and sources]

    **Data Sources:** [List all providers used]
    **Evidence Strength:** [Strong/Moderate/Weak based on data quality]

    ## 📋 Multi-Provider Search Results

    ### Consolidated Findings
    [Summary of what each provider contributed]

    ### Source Quality Analysis
    | Provider | Results Found | Confidence Score | Data Quality |
    |----------|---------------|------------------|--------------|
    | Wikipedia | X results | Y% | High/Medium/Low |
    | Tavily | X results | Y% | High/Medium/Low |
    | DuckDuckGo | X results | Y% | High/Medium/Low |

    ## 📊 Numeric Evidence & Data Analysis

    ### Summary Statistics Table
    [Insert table_data.summary_table as markdown table]

    ### Detailed Data Points
    [Insert table_data.detailed_table as markdown table]

    ### Key Numeric Findings
    [List the most important numbers found with context]

    ## 📈 Data Visualizations

    ### Chart Recommendations
    [For each chart in chart_data, provide:]
    - **Chart Type:** [line/bar/pie/etc]
    - **Title:** [Chart title]
    - **Data Shown:** [What the chart displays]
    - **Proof Provided:** [What this chart proves about the topic]

    ### Temporal Analysis
    [If time series data exists, show trends over time]

    ### Comparative Analysis  
    [If comparative data exists, show entity comparisons]

    ## 💡 Evidence-Based Insights

    ### Proven Conclusions
    [Only conclusions supported by numeric evidence]

    ### Data Confidence Assessment
    [Assess reliability of findings based on source quality and data consistency]

    ### Cross-Source Validation
    [Where multiple sources confirm the same data points]

    ## 🎯 Final Assessment

    ### Numeric Proof Summary
    - **Total Data Points Found:** [Number]
    - **High Confidence Findings:** [Number] 
    - **Cross-Validated Claims:** [Number]
    - **Evidence Quality:** [Strong/Moderate/Weak]

    ### Recommendations
    [Based on the numeric evidence found]

    ---
    **Report Generated:** [Current timestamp]
    **Sources Used:** [All providers]
    **Evidence Quality:** [Assessment]

    CRITICAL: Include ALL numeric data found. Create actual markdown tables from the data. Reference specific numbers throughout."""
}

# Create the enhanced agent
try:
    app = create_deep_agent(
        tools=[multi_provider_search, enhanced_data_extraction],
        instructions=agent_instructions,
        subagents=[
            content_classifier_subagent,
            data_visualizer_subagent, 
            report_writer_subagent
        ],
        model=llm,
        interrupt_config={}
    )
    logger.info("✅ Enhanced multi-provider research agent created successfully")
except Exception as e:
    logger.error(f"❌ Failed to create enhanced agent: {e}")
    raise

if __name__ == "__main__":
    print("🚀 ENHANCED MULTI-PROVIDER RESEARCH AGENT v7.0")
    print("="*80)
    print("✅ GUARANTEED MULTI-PROVIDER SEARCH:")
    print("   🔍 Tavily: Latest specialized sources and real-time data")
    print("   🦆 DuckDuckGo: Diverse perspectives and current information")  
    print("   📚 Wikipedia: Comprehensive background and verified data")
    print("   🔄 Automatic result consolidation and confidence scoring")
    print("")
    print("✅ COMPREHENSIVE NUMERIC PROOF:")
    print("   📊 Enhanced pattern matching for all numeric data types")
    print("   📈 Automatic table and chart generation from found data")
    print("   🎯 Cross-source validation and confidence assessment") 
    print("   📋 Evidence-based conclusions with specific numbers")
    print("")
    print("✅ STREAMABLE REPORT OUTPUT:")
    print("   📄 Complete markdown report with embedded tables/charts")
    print("   🔍 Multi-provider source attribution")
    print("   📊 Comprehensive data visualization recommendations")
    print("   🎯 Evidence quality assessment and confidence scoring")
    print("")
    print("Agent ready for evidence-based research with numeric proof!")
    print("="*80)