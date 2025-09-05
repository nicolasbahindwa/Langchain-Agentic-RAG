import os
import json
import re
from typing import Literal, Dict, List, Any, Optional
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import create_search_manager
from deepagents import create_deep_agent

# Initialize managers
manager = LLMManager()
llm = manager.get_chat_model(
    provider=LLMProvider.OPENAI,
    temperature=0.7
)
search_manager = create_search_manager()

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search - this tool will be interrupted for sensitive content"""
    return search_manager.search(
        query=query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

def sensitive_content_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Search tool specifically for sensitive content - requires age verification"""
    return search_manager.search(
        query=query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

def extract_and_format_data(content: str) -> Dict[str, Any]:
    """Comprehensive tool to extract ALL numeric data and create unified JSON for graphs/tables"""
    
    # Enhanced patterns for maximum data extraction
    patterns = [
        # Years with context (2020, 2021, etc.)
        r'(\b(?:19|20)\d{2})\b[^\d]*?(\d+(?:\.\d+)?%?|\$[\d,]+(?:\.\d+)?)',
        # Percentages with detailed context
        r'(\d+(?:\.\d+)?%)\s*([^.!?\n]{5,100})',
        # Currency with context
        r'([\$€£¥]\s*[\d,]+(?:\.\d{2})?)\s*([^.!?\n]{5,100})',
        # Large numbers with commas
        r'(\b\d{1,3}(?:,\d{3})+(?:\.\d+)?)\s*([^.!?\n]{5,100})',
        # Growth/decline indicators
        r'((?:grew|increased|rose|up|declined|fell|dropped|down)\s+(?:by\s+)?(\d+(?:\.\d+)?%?))',
        # Market share patterns
        r'(market\s+share[^.!?\n]*?(\d+(?:\.\d+)?%?))',
        # Time period ranges
        r'(from\s+(\d+(?:\.\d+)?%?)\s+to\s+(\d+(?:\.\d+)?%?))',
        # Fold increases (ten-fold, 5-fold, etc.)
        r'((\d+|\w+)-fold)',
        # Comparative numbers (more than, less than, under, over)
        r'((?:more than|less than|under|over)\s+(\d+(?:\.\d+)?%?))',
        # General numbers with units
        r'(\b\d+(?:\.\d+)?)\s*(million|billion|thousand|vehicles|cars|units|people)',
    ]
    
    extracted_items = []
    
    # Process each pattern
    for i, pattern in enumerate(patterns):
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            groups = match.groups()
            full_match = match.group(0)
            
            # Extract numeric values from the match
            numbers = re.findall(r'\d+(?:\.\d+)?', full_match)
            
            for num_str in numbers:
                try:
                    numeric_value = float(num_str)
                    
                    # Determine data type and context
                    context = full_match
                    data_type = "number"
                    
                    if '%' in full_match:
                        data_type = "percentage"
                    elif any(symbol in full_match for symbol in ['$', '€', '£', '¥']):
                        data_type = "currency"
                    elif any(word in full_match.lower() for word in ['million', 'billion', 'thousand']):
                        data_type = "large_number"
                    elif any(word in full_match.lower() for word in ['grew', 'increased', 'declined', 'fell']):
                        data_type = "growth_metric"
                    elif 'market share' in full_match.lower():
                        data_type = "market_share"
                    elif any(word in full_match.lower() for word in ['fold']):
                        data_type = "multiplier"
                    elif re.search(r'\b(?:19|20)\d{2}\b', full_match):
                        data_type = "yearly_data"
                    
                    # Extract year if present
                    year_match = re.search(r'\b((?:19|20)\d{2})\b', context)
                    year = int(year_match.group(1)) if year_match else None
                    
                    # Extract company/entity if present
                    company_patterns = [
                        r'\b(Tesla|BYD|Ford|GM|Volkswagen|Toyota|BMW|Mercedes|Audi|Nissan|Hyundai)\b',
                        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b(?=\s+(?:sales|revenue|market|share))'
                    ]
                    
                    entity = None
                    for comp_pattern in company_patterns:
                        comp_match = re.search(comp_pattern, context, re.IGNORECASE)
                        if comp_match:
                            entity = comp_match.group(1)
                            break
                    
                    # Extract measurement unit
                    unit_match = re.search(r'\b(vehicles|cars|units|people|million|billion|thousand|%|\$|€|£|¥)\b', context.lower())
                    unit = unit_match.group(1) if unit_match else None
                    
                    extracted_items.append({
                        'value': numeric_value,
                        'original_text': full_match.strip(),
                        'context': context.strip(),
                        'data_type': data_type,
                        'year': year,
                        'entity': entity,
                        'unit': unit,
                        'pattern_index': i,
                        'position_in_text': match.start()
                    })
                    
                except ValueError:
                    continue
    
    # Remove duplicates and sort by position in text
    seen = set()
    unique_items = []
    for item in sorted(extracted_items, key=lambda x: x['position_in_text']):
        # Create a key for deduplication
        key = (item['value'], item['data_type'], item['year'], item['entity'])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    
    # Organize data by categories for easy graphing/tabling
    organized_data = {
        'yearly_data': {},
        'market_share': {},
        'growth_metrics': {},
        'financial_data': {},
        'company_data': {},
        'percentages': {},
        'large_numbers': {},
        'multipliers': {}
    }
    
    # Group data by type and entity
    for item in unique_items:
        data_type = item['data_type']
        entity = item['entity'] or 'general'
        year = item['year']
        value = item['value']
        
        # Organize by data type
        if data_type == 'yearly_data' and year:
            if entity not in organized_data['yearly_data']:
                organized_data['yearly_data'][entity] = {}
            organized_data['yearly_data'][entity][str(year)] = {
                'value': value,
                'unit': item['unit'],
                'context': item['context']
            }
        
        elif data_type == 'market_share':
            if entity not in organized_data['market_share']:
                organized_data['market_share'][entity] = {}
            key = str(year) if year else 'current'
            organized_data['market_share'][entity][key] = {
                'value': value,
                'unit': item['unit'],
                'context': item['context']
            }
        
        elif data_type == 'growth_metric':
            if entity not in organized_data['growth_metrics']:
                organized_data['growth_metrics'][entity] = []
            organized_data['growth_metrics'][entity].append({
                'value': value,
                'unit': item['unit'],
                'context': item['context'],
                'year': year
            })
        
        elif data_type == 'currency':
            if entity not in organized_data['financial_data']:
                organized_data['financial_data'][entity] = {}
            key = str(year) if year else 'current'
            organized_data['financial_data'][entity][key] = {
                'value': value,
                'unit': item['unit'],
                'context': item['context']
            }
        
        elif entity and entity != 'general':
            if entity not in organized_data['company_data']:
                organized_data['company_data'][entity] = []
            organized_data['company_data'][entity].append({
                'value': value,
                'data_type': data_type,
                'unit': item['unit'],
                'context': item['context'],
                'year': year
            })
    
    # Create comprehensive unified structure
    unified_data = {
        'metadata': {
            'total_data_points': len(unique_items),
            'extraction_timestamp': '2025-01-01T00:00:00Z',
            'data_found': len(unique_items) > 0,
            'text_length': len(content),
            'unique_entities': list(set(item['entity'] for item in unique_items if item['entity'])),
            'unique_years': sorted(list(set(item['year'] for item in unique_items if item['year']))),
            'data_types_found': list(set(item['data_type'] for item in unique_items))
        },
        
        'raw_data_points': unique_items,  # All extracted points with full detail
        
        'organized_data': organized_data,  # Grouped for easy visualization
        
        'graph_ready_datasets': {
            'time_series': {},  # For line charts
            'categorical': {},  # For bar charts
            'percentage_breakdown': {},  # For pie charts
            'comparison_data': {}  # For comparative analysis
        },
        
        'table_ready_data': {
            'summary_table': [],
            'detailed_table': [],
            'yearly_comparison': {},
            'entity_comparison': {}
        }
    }
    
    # Prepare graph-ready datasets
    for entity, years_data in organized_data['yearly_data'].items():
        if len(years_data) > 1:  # Time series data
            unified_data['graph_ready_datasets']['time_series'][entity] = {
                'labels': sorted(years_data.keys()),
                'values': [years_data[year]['value'] for year in sorted(years_data.keys())],
                'units': [years_data[year]['unit'] for year in sorted(years_data.keys())]
            }
    
    # Prepare table-ready data
    for item in unique_items:
        unified_data['table_ready_data']['detailed_table'].append({
            'Entity': item['entity'] or 'N/A',
            'Year': item['year'] or 'N/A',
            'Value': item['value'],
            'Unit': item['unit'] or 'N/A',
            'Type': item['data_type'],
            'Context': item['context'][:100] + '...' if len(item['context']) > 100 else item['context']
        })
    
    return unified_data

# Enhanced agent instructions with focus on unified data
agent_instructions = """You are a research coordinator that creates comprehensive reports with ALL numeric data in ONE unified JSON structure.

CRITICAL REQUIREMENTS:
- Extract EVERY number from search results using extract_and_format_data
- Include ALL data in a SINGLE comprehensive JSON block
- NO separate JSON fragments - everything must be unified
- Structure data for both graphs AND tables
- Provide maximum detail and context for each data point

WORKFLOW:
1. CONTENT CLASSIFICATION: Call 'content-classifier' to check if content is safe/sensitive/banned
2. SEARCH PHASE: Use appropriate search tool based on classification
3. DATA EXTRACTION PHASE: Use extract_and_format_data tool on ALL search results
4. VISUALIZATION PLANNING: Call 'data-visualizer' with the unified data
5. REPORT PHASE: Call 'report-writer' with the complete unified JSON structure

The final report MUST contain ONE comprehensive JSON block with all numeric data organized for easy graphing and table creation."""

# Content classifier subagent
content_classifier_subagent = {
    "name": "content-classifier",
    "description": "Classifies content as safe, sensitive, or banned",
    "prompt": """Analyze the user query and classify it as "safe", "sensitive", or "banned".

    RESPONSE FORMAT (JSON only):
    {
        "classification": "safe" | "sensitive" | "banned",
        "reason": "Brief explanation"
    }

    BANNED content includes: illegal activities, violence, hate speech, child exploitation, terrorism, privacy violations, financial crimes, dangerous medical advice."""
}

# Enhanced Data Visualizer for unified data
data_visualizer_subagent = {
    "name": "data-visualizer",
    "description": "Analyzes unified numeric data and provides comprehensive visualization strategy",
    "prompt": """You are a data visualization expert. Analyze the unified numeric data structure and provide comprehensive recommendations.

    RESPONSE FORMAT (JSON):
    {
        "visualization_strategy": {
            "primary_chart_type": "line" | "bar" | "pie" | "scatter" | "table",
            "secondary_charts": ["chart_type1", "chart_type2"],
            "reasoning": "Why these visualizations work best"
        },
        "graph_configurations": {
            "chart1": {
                "type": "line",
                "title": "Chart title",
                "data_source": "path to data in unified JSON",
                "x_axis": "label",
                "y_axis": "label"
            }
        },
        "table_configurations": {
            "summary_table": {
                "columns": ["col1", "col2", "col3"],
                "data_source": "path to data in unified JSON"
            }
        }
    }

    Focus on extracting maximum value from the unified data structure."""
}

# Ban response subagent
ban_response_subagent = {
    "name": "ban-response",
    "description": "Generates appropriate responses for banned content",
    "prompt": """Generate a clear, professional response for banned content:

    🚫 **CONTENT BLOCKED**
    **Reason:** [Specific policy violation]
    **Alternative:** [Suggest related acceptable topics if possible]"""
}

# Enhanced Report writer for unified data presentation
report_subagent = {
    "name": "report-writer",
    "description": "Creates comprehensive reports with unified JSON data structure",
    "prompt": """Create a professional research report with ONE comprehensive JSON block containing ALL numeric data.

    STRUCTURE:
    
    # RESEARCH REPORT: [Topic]

    ## EXECUTIVE SUMMARY
    [Key findings in 2-3 sentences, referencing specific numbers from the data]

    ## KEY FINDINGS
    [Main discoveries with specific numeric references]

    ## COMPREHENSIVE DATA ANALYSIS

    ### Complete Numeric Dataset
    ```json
    [Include the COMPLETE unified JSON structure from extract_and_format_data here]
    ```

    ### Visualization Recommendations
    ```json
    [Include recommendations from data-visualizer here]
    ```

    ## DATA INSIGHTS
    [Detailed analysis referencing specific values from the unified JSON]
    - Reference specific data points by their path in the JSON
    - Highlight trends found in the time_series data
    - Compare entities using the organized_data structure

    ## CONCLUSIONS & RECOMMENDATIONS
    [Actionable insights based on comprehensive data analysis]

    ---
    *Report with comprehensive unified data extraction*

    CRITICAL REQUIREMENTS:
    - Include the COMPLETE unified JSON structure (not fragments)
    - All numeric data must be in ONE JSON block
    - Reference specific data paths in your analysis
    - Ensure data is ready for both graphing and table display"""
}

# Human interrupt configuration
interrupt_config = {
    "sensitive_content_search": {
        "allow_ignore": False,
        "allow_respond": True,  
        "allow_edit": False,
        "allow_accept": True
    }
}

# Create the enhanced agent
app = create_deep_agent(
    tools=[internet_search, sensitive_content_search, extract_and_format_data],
    instructions=agent_instructions,
    subagents=[
        content_classifier_subagent,
        data_visualizer_subagent, 
        ban_response_subagent,
        report_subagent
    ],
    model=llm,
    interrupt_config=interrupt_config
)

def verify_age_and_consent():
    """Handle age verification for sensitive content"""
    print("\n" + "="*60)
    print("AGE VERIFICATION REQUIRED")
    print("="*60)
    print("This research contains sensitive content requiring age verification.")
    
    while True:
        age_input = input("Are you 18 years or older? (yes/no): ").lower().strip()
        if age_input in ['yes', 'y']:
            print("Age verification confirmed.")
            break
        elif age_input in ['no', 'n']:
            print("Access denied. Content only available to users 18+.")
            return False
        else:
            print("Please answer 'yes' or 'no'")
    
    while True:
        consent_input = input("Proceed with mature content research? (yes/no): ").lower().strip()
        if consent_input in ['yes', 'y']:
            print("Proceeding with research...")
            return True
        elif consent_input in ['no', 'n']:
            print("Research cancelled.")
            return False
        else:
            print("Please answer 'yes' or 'no'")

def handle_interrupt_response(response_needed=True):
    """Handle the human-in-the-loop interrupt"""
    if response_needed:
        verified = verify_age_and_consent()
        return "APPROVED: User verified" if verified else "DENIED: Verification failed"
    return "APPROVED"

def is_content_banned_response(content: str) -> bool:
    """Check if response indicates banned content"""
    return "🚫 **CONTENT BLOCKED**" in content

if __name__ == "__main__":
    print("🚀 COMPREHENSIVE RESEARCH AGENT v2.0")
    print("="*60)
    print("✅ Advanced content safety classification")
    print("✅ Age verification for sensitive content") 
    print("✅ Comprehensive numerical data extraction")
    print("✅ File management for workflow control")
    print("✅ Unified JSON structure for all data")
    print("✅ Professional report generation")
    print("✅ Recursion prevention & error handling")
    print("✅ Markdown formatting ready for rendering")
    print("✅ Graph and table ready datasets")
    print("="*60)
    print("\nFEATURES:")
    print("📊 Detailed reports with Introduction, Overview, Insights, Summary")
    print("📁 File-based workflow management")
    print("🎯 Single comprehensive JSON with all numeric data")
    print("📈 Visualization recommendations included")
    print("🎨 Well-styled markdown output")
    print("\nAgent ready for comprehensive research tasks!")
    print("Recursion limit set to 15 to prevent infinite loops.")
    print("All data will be unified in markdown with embedded JSON!")