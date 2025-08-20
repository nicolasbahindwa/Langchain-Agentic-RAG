# import os, json, asyncio
# from typing import TypedDict, List, Dict, Any, Annotated
# from langgraph.graph import StateGraph, END
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
# from langchain_openai import ChatOpenAI
# from langchain_community.utilities import SQLDatabase
# from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
# from core.llm_manager import LLMManager, LLMProvider
# from utils.logger import get_enhanced_logger
# import json
# import re

# # Initialize logger
# logger = get_enhanced_logger(__name__)

# # DB
# db = SQLDatabase.from_uri("sqlite:///dummy.db")
# query_tool = QuerySQLDataBaseTool(db=db)

# # Get database schema information
# def get_database_schema():
#     """Get the database schema to help the LLM write better queries"""
#     try:
#         schema_info = db.get_table_info()
#         logger.success("Successfully retrieved database schema")
#         return schema_info
#     except Exception as e:
#         logger.failure(f"Failed to retrieve database schema: {str(e)}")
#         # Fallback schema description
#         return """
#         Database Schema:
        
#         Products table:
#         - product_id (INTEGER PRIMARY KEY)
#         - name (TEXT)
#         - category (TEXT)
        
#         Prices table:
#         - price_id (INTEGER PRIMARY KEY)
#         - product_id (INTEGER, FK to Products)
#         - price (REAL)
#         - start_date (DATE)
#         - end_date (DATE, can be NULL)
        
#         Sales table:
#         - sale_id (INTEGER PRIMARY KEY)
#         - product_id (INTEGER, FK to Products)
#         - quantity (INTEGER)
#         - sale_date (DATE)
        
#         Inventory table:
#         - inventory_id (INTEGER PRIMARY KEY)
#         - product_id (INTEGER, FK to Products)
#         - quantity (INTEGER)
#         - last_updated (DATE)
#         """

# def extract_sql_from_response(response_text: str) -> str:
#     """Extract SQL query from LLM response, handling various formats"""
#     # Remove any leading/trailing whitespace
#     text = response_text.strip()
    
#     # Pattern 1: Extract from ```sql code blocks
#     sql_block_pattern = r'```(?:sql)?\s*(.*?)\s*```'
#     matches = re.findall(sql_block_pattern, text, re.DOTALL | re.IGNORECASE)
#     if matches:
#         # Get the last SQL block found
#         sql = matches[-1].strip()
#         logger.debug(f"Extracted SQL from code block: {sql}")
#         return sql
    
#     # Pattern 2: Look for SELECT statements (case insensitive)
#     select_pattern = r'(SELECT\s+.*?(?:;|\s*$))'
#     matches = re.findall(select_pattern, text, re.DOTALL | re.IGNORECASE)
#     if matches:
#         # Get the last SELECT statement
#         sql = matches[-1].strip()
#         # Remove trailing semicolon if present
#         if sql.endswith(';'):
#             sql = sql[:-1]
#         logger.debug(f"Extracted SQL from SELECT pattern: {sql}")
#         return sql
    
#     # Pattern 3: If no patterns match, try to clean common prefixes
#     lines = text.split('\n')
#     sql_lines = []
#     found_sql = False
    
#     for line in lines:
#         line = line.strip()
#         # Skip common non-SQL lines
#         if (line.startswith('Here is') or 
#             line.startswith('The SQL') or 
#             line.startswith('```') or
#             line == '' or
#             line.startswith('#')):
#             continue
            
#         # Check if line looks like SQL
#         if re.match(r'^\s*(SELECT|WITH|INSERT|UPDATE|DELETE)\s+', line, re.IGNORECASE):
#             found_sql = True
            
#         if found_sql:
#             sql_lines.append(line)
    
#     if sql_lines:
#         sql = '\n'.join(sql_lines)
#         # Remove trailing semicolon if present
#         if sql.endswith(';'):
#             sql = sql[:-1]
#         logger.debug(f"Extracted SQL from manual parsing: {sql}")
#         return sql
    
#     # If all else fails, return the original text
#     logger.warning("Could not extract clean SQL, returning original text")
#     return text

# # Message reducer function
# def add_messages(existing: List[BaseMessage], new: List[BaseMessage]) -> List[BaseMessage]:
#     """Reducer function to add new messages to existing messages list"""
#     return existing + new

# # Initialize components
# llm_manager = LLMManager()
# llm = llm_manager.get_chat_model(
#     provider=LLMProvider.ANTHROPIC,
#     model="claude-3-haiku-20240307",
#     temperature=0.1,  # Lower temperature for more consistent SQL generation
#     max_tokens=2000
# )

# llm_light = llm_manager.get_chat_model(
#     provider=LLMProvider.OPENAI,
#     model="gpt-4o-mini",
#     temperature=0.1,  # Lower temperature for more consistent SQL generation
#     max_tokens=2000
# )

# class AnalystState(TypedDict):
#     messages: Annotated[List[BaseMessage], add_messages]
#     question: str
#     task: str
#     sql: str
#     data: List[Dict[str, Any]]
#     answer: str
#     report: str
#     error: str

# # ---------- 1. rewrite ------------------------------------------------
# rewrite_prompt = ChatPromptTemplate.from_messages([
#     ("system", """You are a data analyst. Your job is to rewrite the user's question into a clear, specific analytical task that can be answered with SQL queries.

# CRITICAL INSTRUCTIONS:
# - ALWAYS rewrite the question into a clear task, never ask for clarification
# - Be specific about what data to retrieve and any calculations needed
# - Focus on actionable SQL queries
# - If the question is vague, make reasonable assumptions about what the user wants

# Examples:
# - User: "tell me about sales" → Task: "Analyze total sales revenue by product category for the current year"
# - User: "inventory situation" → Task: "Show current inventory levels for all products with quantity and last updated dates"
# - User: "best products" → Task: "Identify top 5 products by total sales revenue"

# Always provide a specific task, never ask for more information."""),
#     ("human", "{question}")
# ])

# async def rewrite_node(state: AnalystState):
#     try:
#         logger.info("Starting rewrite task")
        
#         # Extract the last human message from the conversation history
#         question = None
#         if state.get("messages"):
#             # Reverse the messages to find the most recent human message
#             for msg in reversed(state["messages"]):
#                 if isinstance(msg, HumanMessage):
#                     question = msg.content
#                     logger.info(f"Found latest question in messages: {question}")
#                     break
#                 elif isinstance(msg, dict) and msg.get('type') == 'human':
#                     question = msg.get('content', '')
#                     logger.info(f"Found latest question in dict message: {question}")
#                     break
        
#         # If no human message found, use the question from state or provide default
#         if not question:
#             question = state.get("question", "Analyze the current inventory situation")
#             logger.info(f"Using question from state or default: {question}")
        
#         logger.info(f"Final question to process: {question}")
        
#         prompt_msgs = rewrite_prompt.format_messages(question=question)
#         task_response = await llm_light.ainvoke(prompt_msgs)
        
#         # Handle response (same as before)
#         if hasattr(task_response, 'content'):
#             task = task_response.content.strip()
#         elif isinstance(task_response, dict) and 'content' in task_response:
#             task = task_response['content'].strip()
#         else:
#             task = str(task_response).strip()
        
#         # Validate task (same as before)
#         if any(phrase in task.lower() for phrase in [
#             "please provide", "could you specify", "what specific", 
#             "more information", "clarify", "which", "what type"
#         ]):
#             logger.warning(f"LLM asked for clarification, generating default task for: {question}")
#             if "inventory" in question.lower():
#                 task = "Show current inventory levels for all products with quantities and last updated information"
#             elif "sales" in question.lower():
#                 task = "Analyze total sales revenue and quantities by product for recent periods"
#             elif "revenue" in question.lower():
#                 task = "Calculate total revenue by product category and time period"
#             else:
#                 task = f"Analyze data related to: {question}"
        
#         # Add messages to state
#         new_messages = [
#             AIMessage(content=f"Rewritten task: {task}")
#         ]
        
#         logger.success(f"Task rewritten successfully: {task}")
#         return {"task": task, "messages": new_messages, "question": question}
#     except Exception as e:
#         # Error handling (same as before)
#         logger.failure(f"Error in rewrite: {str(e)}")
#         error_msg = f"Error in rewrite: {str(e)}"
        
#         # Try to get question for error message
#         question = None
#         if state.get("messages"):
#             for msg in reversed(state["messages"]):
#                 if isinstance(msg, HumanMessage):
#                     question = msg.content
#                     break
#                 elif isinstance(msg, dict) and msg.get('type') == 'human':
#                     question = msg.get('content', '')
#                     break
        
#         if not question:
#             question = state.get("question", "Unknown question")
        
#         new_messages = [
#             AIMessage(content=f"Error: {error_msg}")
#         ]
#         return {"error": error_msg, "messages": new_messages, "question": question}

# # ---------- 2. generate_sql ------------------------------------------
# sql_prompt = ChatPromptTemplate.from_messages([
#     ("system",
#      """You are a SQL expert working with SQLite database. Given the analytical task and database schema, write a SINGLE SQLite SELECT query.
     
#      Database Schema:
#      {schema}
     
#      CRITICAL INSTRUCTIONS:
#      - Return ONLY the SQL query, nothing else
#      - No explanations, no markdown, no code blocks
#      - Use proper SQLite syntax
#      - For date operations use: strftime('%Y-%m', date_column) or date() functions
#      - To calculate revenue: JOIN Sales with Products and Prices tables, then multiply quantity * price
#      - Use appropriate JOINs to connect related tables
#      - Always include WHERE clauses for date filtering when needed
     
#      Example format (return exactly like this):
#      SELECT p.category, SUM(s.quantity * pr.price) as total_revenue FROM Sales s JOIN Products p ON s.product_id = p.product_id JOIN Prices pr ON p.product_id = pr.product_id WHERE strftime('%Y', s.sale_date) = '2024' GROUP BY p.category ORDER BY total_revenue DESC LIMIT 1"""),
#     ("human", "Task: {task}")
# ])

# async def generate_sql_node(state: AnalystState):
#     try:
#         logger.info("Starting SQL generation")
        
#         # Get task from state, with multiple fallback methods
#         task = state.get("task")
#         if not task:
#             # Try to extract task from recent AI messages as fallback
#             if state.get("messages"):
#                 for msg in reversed(state["messages"]):
#                     msg_content = ""
#                     if isinstance(msg, AIMessage):
#                         msg_content = msg.content
#                     elif isinstance(msg, dict) and 'content' in msg:
#                         msg_content = msg['content']
                    
#                     if "Rewritten task:" in msg_content:
#                         task = msg_content.replace("Rewritten task:", "").strip()
#                         logger.info(f"Extracted task from messages: {task}")
#                         break
            
#             # If still no task, generate one from the question
#             if not task:
#                 question = state.get("question", "")
#                 if question:
#                     if "inventory" in question.lower():
#                         task = "Show current inventory levels for all products with quantities and last updated information"
#                     elif "sales" in question.lower():
#                         task = "Analyze total sales revenue and quantities by product for recent periods"
#                     elif "revenue" in question.lower():
#                         task = "Calculate total revenue by product category and time period"
#                     else:
#                         task = f"Analyze data related to: {question}"
#                     logger.info(f"Generated fallback task: {task}")
#                 else:
#                     raise ValueError("No task found in state, messages, or question")
        
#         schema = get_database_schema()
#         prompt_msgs = sql_prompt.format_messages(task=task, schema=schema)
#         sql_response = await llm_light.ainvoke(prompt_msgs)
        
#         # Fix: Handle both dict and object responses
#         if hasattr(sql_response, 'content'):
#             sql_content = sql_response.content
#         elif isinstance(sql_response, dict) and 'content' in sql_response:
#             sql_content = sql_response['content']
#         else:
#             sql_content = str(sql_response)
        
#         # Extract and clean the SQL
#         sql_clean = extract_sql_from_response(sql_content)
        
#         # Additional cleaning
#         sql_clean = sql_clean.strip()
#         if sql_clean.endswith(';'):
#             sql_clean = sql_clean[:-1]
        
#         logger.success(f"SQL generated successfully: {sql_clean}")
        
#         # Add messages to state
#         new_messages = [
#             AIMessage(content=f"Generated SQL query: ```sql\n{sql_clean}\n```")
#         ]
        
#         # Ensure we return the task as well to maintain state
#         return {"sql": sql_clean, "messages": new_messages, "task": task}
#     except Exception as e:
#         logger.failure(f"Error generating SQL: {str(e)}")
#         error_msg = f"Error generating SQL: {str(e)}"
#         new_messages = [
#             AIMessage(content=f"Error generating SQL: {error_msg}")
#         ]
#         return {"error": error_msg, "messages": new_messages}

# # ---------- 3. run_sql -----------------------------------------------
# async def run_sql_node(state: AnalystState):
#     try:
#         # Check if there was an error in previous steps
#         if state.get("error"):
#             logger.warning(f"Skipping SQL execution due to previous error: {state['error']}")
#             return {"error": state["error"]}
        
#         sql = state.get("sql")
#         if not sql:
#             # Try to extract SQL from recent AI messages as fallback
#             if state.get("messages"):
#                 for msg in reversed(state["messages"]):
#                     msg_content = ""
#                     if isinstance(msg, AIMessage):
#                         msg_content = msg.content
#                     elif isinstance(msg, dict) and 'content' in msg:
#                         msg_content = msg['content']
                    
#                     if "Generated SQL query:" in msg_content:
#                         # Extract SQL from the message
#                         import re
#                         sql_match = re.search(r'```sql\n(.*?)\n```', msg_content, re.DOTALL)
#                         if sql_match:
#                             sql = sql_match.group(1).strip()
#                             logger.info(f"Extracted SQL from messages: {sql}")
#                             break
            
#             if not sql:
#                 error_msg = "No SQL query found in state or messages"
#                 logger.failure(error_msg)
#                 return {"error": error_msg}
            
#         logger.info(f"Executing SQL query: {sql}")
        
#         # Execute the SQL query
#         result = await asyncio.to_thread(query_tool.invoke, sql)
        
#         logger.debug(f"Raw SQL result: {result}")
        
#         # Parse the result - it should be JSON string or direct result
#         if isinstance(result, str):
#             try:
#                 # Try to parse as JSON first
#                 data = json.loads(result)
#                 if isinstance(data, list):
#                     logger.success(f"SQL executed successfully, returned {len(data)} rows")
#                     new_messages = [
#                         AIMessage(content=f"SQL executed successfully. Retrieved {len(data)} rows of data.")
#                     ]
#                     return {"data": data, "messages": new_messages, "sql": sql}
#                 else:
#                     # Single row or other format
#                     processed_data = [data] if isinstance(data, dict) else [{"result": str(data)}]
#                     logger.success("SQL executed successfully, returned single result")
#                     new_messages = [
#                         AIMessage(content="SQL executed successfully. Retrieved single result.")
#                     ]
#                     return {"data": processed_data, "messages": new_messages, "sql": sql}
#             except json.JSONDecodeError:
#                 # If not JSON, check if it's a simple result string
#                 if result.strip():
#                     # Try to parse as a simple table result
#                     lines = result.strip().split('\n')
#                     if len(lines) > 1:
#                         # Assume first line is headers, rest are data
#                         headers = [h.strip() for h in lines[0].split('|') if h.strip()]
#                         data = []
#                         for line in lines[1:]:
#                             if '|' in line:
#                                 values = [v.strip() for v in line.split('|') if v.strip()]
#                                 if len(values) == len(headers):
#                                     row = dict(zip(headers, values))
#                                     data.append(row)
#                         if data:
#                             logger.success(f"SQL executed successfully, parsed {len(data)} rows from text result")
#                             new_messages = [
#                                 AIMessage(content=f"SQL executed successfully. Parsed {len(data)} rows from result.")
#                             ]
#                             return {"data": data, "messages": new_messages, "sql": sql}
                    
#                     logger.success("SQL executed successfully, returned text result")
#                     new_messages = [
#                         AIMessage(content="SQL executed successfully. Retrieved text result.")
#                     ]
#                     return {"data": [{"result": result}], "messages": new_messages, "sql": sql}
#                 else:
#                     logger.info("SQL executed successfully but returned no data")
#                     new_messages = [
#                         AIMessage(content="SQL executed successfully but returned no data.")
#                     ]
#                     return {"data": [], "messages": new_messages, "sql": sql}
#         else:
#             logger.success("SQL executed successfully, returned direct result")
#             new_messages = [
#                 AIMessage(content="SQL executed successfully. Retrieved direct result.")
#             ]
#             return {"data": [{"result": str(result)}], "messages": new_messages, "sql": sql}
        
#     except Exception as e:
#         logger.failure(f"Error executing SQL: {str(e)}")
#         error_msg = f"Error executing SQL: {str(e)}"
#         new_messages = [
#             AIMessage(content=f"Error executing SQL: {error_msg}")
#         ]
#         return {"error": error_msg, "messages": new_messages}

# def format_data_as_markdown_table(data: List[Dict[str, Any]]) -> str:
#     """Convert list of dictionaries to markdown table format"""
#     if not data:
#         return "No data found."
    
#     # Get headers from first row
#     headers = list(data[0].keys())
    
#     # Create markdown table
#     header_row = "| " + " | ".join(str(h) for h in headers) + " |"
#     separator_row = "| " + " | ".join("---" for _ in headers) + " |"
    
#     data_rows = []
#     for row in data:
#         row_values = [str(row.get(h, "")) for h in headers]
#         data_rows.append("| " + " | ".join(row_values) + " |")
    
#     return "\n".join([header_row, separator_row] + data_rows)

# def format_data_as_text(data: List[Dict[str, Any]]) -> str:
#     """Convert list of dictionaries to readable text format"""
#     if not data:
#         return "No data found."
    
#     # If single row, format as key-value pairs
#     if len(data) == 1:
#         row = data[0]
#         lines = [f"{key}: {value}" for key, value in row.items()]
#         return "\n".join(lines)
    
#     # Multiple rows - format as a simple table
#     headers = list(data[0].keys())
    
#     # Calculate column widths
#     col_widths = {}
#     for header in headers:
#         col_widths[header] = max(len(str(header)), 
#                                max(len(str(row.get(header, ""))) for row in data))
    
#     # Create formatted table
#     lines = []
    
#     # Header row
#     header_line = " | ".join(str(h).ljust(col_widths[h]) for h in headers)
#     lines.append(header_line)
#     lines.append("-" * len(header_line))
    
#     # Data rows
#     for row in data:
#         data_line = " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers)
#         lines.append(data_line)
    
#     return "\n".join(lines)

# # ---------- 4. answer -------------------------------------------------
# answer_prompt = ChatPromptTemplate.from_messages([
#     ("system", 
#      """You are a senior data analyst. Analyze the query results thoroughly and provide a comprehensive, insightful response.

# CRITICAL INSTRUCTIONS:
# 1. ALWAYS structure your response with:
#    - Executive Summary: 1-2 sentence overview of key findings
#    - Detailed Analysis: Breakdown of the data with specific numbers and trends
#    - Key Insights: Actionable business insights and recommendations
#    - Data Summary: Tabular overview when appropriate

# 2. If the data contains numerical information that can be tabulated, present it in markdown table format
# 3. Highlight unusual patterns, outliers, or significant trends
# 4. Provide specific, data-driven recommendations
# 5. Include relevant metrics and percentages where applicable
# 6. Use precise numbers from the data to support your analysis

# Example format for tabular data:
# ## Executive Summary
# Brief overview of main findings.

# ## Detailed Analysis
# Breakdown of the data with specific observations.

# ## Key Insights
# - Insight 1 with data support
# - Insight 2 with recommendation

# ## Data Summary
# | Column 1 | Column 2 | Column 3 |
# |----------|----------|----------|
# | Value 1  | Value 2  | Value 3  |
# | Value 4  | Value 5  | Value 6  |"""),
#     ("human", 
#      """Original question: {question}
#      Analytical task: {task}
#      SQL query: {sql}
#      Results: {data}
     
#      Provide a comprehensive analysis of these results.""")
# ])
# async def answer_node(state: AnalystState):
#     try:
#         # Check if there was an error in previous steps
#         if state.get("error"):
#             logger.warning(f"Providing error response due to previous error: {state['error']}")
#             error_response = f"Sorry, I encountered an error: {state['error']}"
#             error_report = f"## Error\n{state['error']}"
            
#             new_messages = [
#                 AIMessage(content=error_response)
#             ]
            
#             return {
#                 "answer": error_response,
#                 "report": error_report,
#                 "messages": new_messages
#             }
        
#         # Check if data is empty
#         data = state.get("data", [])
#         if not data:
#             logger.info("No data found for query, providing empty result response")
#             no_data_response = "No data found for your query based on the current database."
#             question = state.get("question", "Unknown question")
#             sql = state.get("sql", "Unknown SQL")
#             no_data_report = f"## Question\n{question}\n\n## SQL\n```sql\n{sql}\n```\n\n## Result\nNo data found."
            
#             new_messages = [
#                 AIMessage(content=no_data_response)
#             ]
            
#             return {
#                 "answer": no_data_response,
#                 "report": no_data_report,
#                 "messages": new_messages
#             }
        
#         logger.info("Generating detailed analysis with insights")
        
#         # Generate comprehensive analysis
#         question = state.get("question", "Unknown question")
#         sql = state.get("sql", "Unknown SQL")
#         task = state.get("task", "Unknown task")
        
#         data_str = format_data_as_text(data)
#         prompt_msgs = answer_prompt.format_messages(
#             question=question, 
#             task=task,
#             sql=sql, 
#             data=data_str
#         )
#         summary = await llm_light.ainvoke(prompt_msgs)

#         # Handle response
#         if hasattr(summary, 'content'):
#             summary_content = summary.content.strip()
#         elif isinstance(summary, dict) and 'content' in summary:
#             summary_content = summary['content'].strip()
#         else:
#             summary_content = str(summary).strip()

#         # Create enhanced report in markdown format
#         data_md = format_data_as_markdown_table(data)
        
#         # Calculate basic statistics if we have numerical data
#         stats_section = ""
#         if data and isinstance(data[0], dict):
#             numerical_columns = []
#             for key, value in data[0].items():
#                 if isinstance(value, (int, float)):
#                     numerical_columns.append(key)
            
#             if numerical_columns:
#                 stats_section = "\n## Basic Statistics\n"
#                 for col in numerical_columns:
#                     values = [row[col] for row in data if row[col] is not None and isinstance(row[col], (int, float))]
#                     if values:
#                         stats_section += f"- **{col}**: Avg: {sum(values)/len(values):.2f}, Min: {min(values)}, Max: {max(values)}, Count: {len(values)}\n"
        
#         report_md = (
#             f"# Analytical Report\n\n"
#             f"## Original Question\n{question}\n\n"
#             f"## Analytical Task\n{task}\n\n"
#             f"## SQL Query\n```sql\n{sql}\n```\n\n"
#             f"## Results Overview\nRetrieved {len(data)} records\n\n"
#             f"## Detailed Data\n{data_md}\n"
#             f"{stats_section}\n"
#             f"## Analysis\n{summary_content}"
#         )
        
#         logger.success("Comprehensive analysis completed successfully")
        
#         new_messages = [
#             AIMessage(content=f"Comprehensive Analysis:\n{summary_content}")
#         ]
        
#         return {
#             "answer": summary_content, 
#             "report": report_md,
#             "messages": new_messages
#         }
        
#     except Exception as e:
#         logger.failure(f"Error in analysis: {str(e)}")
#         error_msg = f"Error in analysis: {str(e)}"
        
#         new_messages = [
#             AIMessage(content=error_msg)
#         ]
        
#         return {
#             "answer": error_msg,
#             "report": f"## Error\n{error_msg}",
#             "messages": new_messages
#         }

# # Build workflow
# workflow = StateGraph(AnalystState)

# workflow.add_node("rewrite", rewrite_node)
# workflow.add_node("generate_sql", generate_sql_node)
# workflow.add_node("run_sql", run_sql_node)
# workflow.add_node("answer", answer_node)

# workflow.set_entry_point("rewrite")
# workflow.add_edge("rewrite", "generate_sql")
# workflow.add_edge("generate_sql", "run_sql")
# workflow.add_edge("run_sql", "answer")
# workflow.add_edge("answer", END)

# app = workflow.compile()

# async def main():
#     # Test with the question that requires joining tables and calculating revenue
#     question = "tell me the situation of my current inventory?"
    
#     logger.info(f"Starting analysis for question: {question}")
    
#     # Initialize state with user question as HumanMessage
#     # Try multiple initialization approaches to be compatible with different environments
#     initial_state = {
#         "question": question,
#         "messages": [HumanMessage(content=question)],
#         "task": "",
#         "sql": "",
#         "data": [],
#         "answer": "",
#         "report": "",
#         "error": ""
#     }
    
#     logger.info(f"Initial state keys: {list(initial_state.keys())}")
#     logger.info(f"Initial messages: {[type(msg).__name__ + ': ' + msg.content for msg in initial_state['messages']]}")
    
#     result = await app.ainvoke(initial_state)
    
#     logger.info("Analysis completed")
    
#     print("=== ANSWER ===")
#     print(result.get("answer", "No answer generated"))
#     print("\n=== FULL REPORT ===")
#     print(result.get("report", "No report generated"))
#     print("\n=== MESSAGE HISTORY ===")
#     messages = result.get("messages", [])
#     for i, msg in enumerate(messages):
#         msg_type = "Human" if isinstance(msg, HumanMessage) else "AI"
#         print(f"{i+1}. {msg_type}: {msg.content}")

# # Alternative function for API usage
# async def analyze_question(question: str, initial_messages: List[BaseMessage] = None):
#     """
#     Entry point for API usage - more flexible input handling
#     """
#     logger.info(f"API: Starting analysis for question: {question}")
    
#     # Handle different input scenarios
#     if initial_messages is None:
#         initial_messages = [HumanMessage(content=question)]
    
#     # Ensure we have the question in the initial messages if not already there
#     has_question = any(isinstance(msg, HumanMessage) and question in msg.content for msg in initial_messages)
#     if not has_question:
#         initial_messages.insert(0, HumanMessage(content=question))
    
#     initial_state = {
#         "question": question,
#         "messages": initial_messages,
#         "task": "",
#         "sql": "",
#         "data": [],
#         "answer": "",
#         "report": "",
#         "error": ""
#     }
    
#     logger.info(f"API: Processing with {len(initial_messages)} initial messages")
    
#     result = await app.ainvoke(initial_state)
    
#     logger.info("API: Analysis completed")
#     return result

# if __name__ == "__main__":
#     asyncio.run(main())


# Analyst Graph with Human-in-the-Loop and Better Error Handling

import os, json, asyncio
from typing import TypedDict, List, Dict, Any, Annotated, Literal
from langgraph.graph import StateGraph, END, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from core.llm_manager import LLMManager, LLMProvider
from utils.logger import get_enhanced_logger
import json
import re

# Initialize logger
logger = get_enhanced_logger(__name__)

# Configuration
MAX_FEEDBACK_CYCLES = 3
CLARITY_THRESHOLD = 0.6  # Threshold for question clarity (0-1)

# DB setup
db = SQLDatabase.from_uri("sqlite:///dummy.db")
query_tool = QuerySQLDataBaseTool(db=db)

# Enhanced State with feedback capabilities
class AnalystState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    question: str
    task: str
    sql: str
    data: List[Dict[str, Any]]
    answer: str
    report: str
    error: str
    
    # New fields for human-in-the-loop
    feedback_cycles: int
    waiting_for_feedback: bool
    question_clarity_score: float
    question_clarity_issues: List[str]
    data_quality_score: float
    needs_clarification: bool

# Initialize components
llm_manager = LLMManager()
llm = llm_manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.1,
    max_tokens=2000
)

llm_light = llm_manager.get_chat_model(
    provider=LLMProvider.OPENAI,
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=2000
)

# Get database schema information
def get_database_schema():
    """Get the database schema to help the LLM write better queries"""
    try:
        schema_info = db.get_table_info()
        logger.success("Successfully retrieved database schema")
        return schema_info
    except Exception as e:
        logger.failure(f"Failed to retrieve database schema: {str(e)}")
        # Fallback schema description
        return """
        Database Schema:
        
        Products table:
        - product_id (INTEGER PRIMARY KEY)
        - name (TEXT)
        - category (TEXT)
        
        Prices table:
        - price_id (INTEGER PRIMARY KEY)
        - product_id (INTEGER, FK to Products)
        - price (REAL)
        - start_date (DATE)
        - end_date (DATE, can be NULL)
        
        Sales table:
        - sale_id (INTEGER PRIMARY KEY)
        - product_id (INTEGER, FK to Products)
        - quantity (INTEGER)
        - sale_date (DATE)
        
        Inventory table:
        - inventory_id (INTEGER PRIMARY KEY)
        - product_id (INTEGER, FK to Products)
        - quantity (INTEGER)
        - last_updated (DATE)
        """

def extract_sql_from_response(response_text: str) -> str:
    """Extract SQL query from LLM response, handling various formats"""
    # Remove any leading/trailing whitespace
    text = response_text.strip()
    
    # Pattern 1: Extract from ```sql code blocks
    sql_block_pattern = r'```(?:sql)?\s*(.*?)\s*```'
    matches = re.findall(sql_block_pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        # Get the last SQL block found
        sql = matches[-1].strip()
        logger.debug(f"Extracted SQL from code block: {sql}")
        return sql
    
    # Pattern 2: Look for SELECT statements (case insensitive)
    select_pattern = r'(SELECT\s+.*?(?:;|\s*$))'
    matches = re.findall(select_pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        # Get the last SELECT statement
        sql = matches[-1].strip()
        # Remove trailing semicolon if present
        if sql.endswith(';'):
            sql = sql[:-1]
        logger.debug(f"Extracted SQL from SELECT pattern: {sql}")
        return sql
    
    # Pattern 3: If no patterns match, try to clean common prefixes
    lines = text.split('\n')
    sql_lines = []
    found_sql = False
    
    for line in lines:
        line = line.strip()
        # Skip common non-SQL lines
        if (line.startswith('Here is') or 
            line.startswith('The SQL') or 
            line.startswith('```') or
            line == '' or
            line.startswith('#')):
            continue
            
        # Check if line looks like SQL
        if re.match(r'^\s*(SELECT|WITH|INSERT|UPDATE|DELETE)\s+', line, re.IGNORECASE):
            found_sql = True
            
        if found_sql:
            sql_lines.append(line)
    
    if sql_lines:
        sql = '\n'.join(sql_lines)
        # Remove trailing semicolon if present
        if sql.endswith(';'):
            sql = sql[:-1]
        logger.debug(f"Extracted SQL from manual parsing: {sql}")
        return sql
    
    # If all else fails, return the original text
    logger.warning("Could not extract clean SQL, returning original text")
    return text

# Helper functions
def get_current_question(state: AnalystState) -> str:
    """Extract the latest human question from messages."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) and msg.content.strip():
            return msg.content.strip()
    return state.get("question", "")

def should_reset_for_new_question(state: AnalystState) -> bool:
    """Determine if we should reset state for a new question."""
    return (state["feedback_cycles"] == 0 and 
            not state.get("waiting_for_feedback") and
            get_current_question(state))

def reset_processing_state(state: AnalystState) -> None:
    """Reset processing state while keeping messages."""
    state["feedback_cycles"] = 0
    state["waiting_for_feedback"] = False
    state["question_clarity_score"] = 0.0
    state["question_clarity_issues"] = []
    state["data_quality_score"] = 0.0
    state["needs_clarification"] = False
    state["task"] = ""
    state["sql"] = ""
    state["data"] = []
    state["error"] = ""
    logger.info("Processing state reset for new question")

# ========== NEW NODES FOR HUMAN-IN-THE-LOOP ==========

async def process_input(state: AnalystState):
    """Entry point - validate input and set up processing."""
    logger.info("=== PROCESSING INPUT ===")
    
    # Initialize defaults if missing
    defaults = {
        "messages": [], "feedback_cycles": 0, "waiting_for_feedback": False,
        "question_clarity_score": 0.0, "question_clarity_issues": [],
        "data_quality_score": 0.0, "needs_clarification": False,
        "question": "", "task": "", "sql": "", "data": [], "answer": "", "report": "", "error": ""
    }
    for key, default_value in defaults.items():
        if key not in state:
            state[key] = default_value
    
    # Get current question
    current_question = get_current_question(state)
    if not current_question:
        state["error"] = "No question found in input"
        error_msg = "I didn't receive a question. Please ask something I can help you analyze."
        state["messages"].append(AIMessage(content=error_msg))
        return state
    
    # Check if we should reset for new question
    if should_reset_for_new_question(state):
        logger.info(f"NEW QUESTION detected: {current_question[:50]}...")
        reset_processing_state(state)
    
    state["question"] = current_question
    logger.info(f"Processing question: {current_question[:100]}...")
    return state

async def assess_question_clarity(state: AnalystState):
    """Assess if the question is clear enough for analysis."""
    logger.info("=== ASSESSING QUESTION CLARITY ===")
    
    current_question = get_current_question(state)
    
    try:
        clarity_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert data analyst. Assess if this question is clear enough for SQL analysis.

            Evaluate the question for:
            1. Specific data elements mentioned (tables, columns, metrics)
            2. Clear analytical intent (what type of analysis is needed)
            3. Sufficient context for database querying
            4. Unambiguous language
            
            Respond in this EXACT format:
            CLARITY_SCORE: [0.0-1.0]
            ISSUES: [comma-separated list of specific issues, or "none"]
            ASSESSMENT: [CLEAR/NEEDS_CLARIFICATION]
            
            Examples:
            - "Show me sales data" → CLARITY_SCORE: 0.3, ISSUES: no time period, no specific metrics, ASSESSMENT: NEEDS_CLARIFICATION
            - "What are the top 5 products by revenue in Q3 2024?" → CLARITY_SCORE: 0.9, ISSUES: none, ASSESSMENT: CLEAR
            """),
            ("human", "Question: {question}")
        ])
        
        response = await llm.ainvoke(clarity_prompt.format_messages(question=current_question))
        content = response.content.strip()
        
        # Parse response
        clarity_score = 0.0
        issues = []
        needs_clarification = True
        
        for line in content.split('\n'):
            if line.startswith("CLARITY_SCORE:"):
                try:
                    clarity_score = float(line.split(":", 1)[1].strip())
                except:
                    clarity_score = 0.0
            elif line.startswith("ISSUES:"):
                issues_str = line.split(":", 1)[1].strip()
                if issues_str.lower() != "none":
                    issues = [issue.strip() for issue in issues_str.split(",")]
            elif line.startswith("ASSESSMENT:"):
                assessment = line.split(":", 1)[1].strip()
                needs_clarification = assessment == "NEEDS_CLARIFICATION"
        
        state["question_clarity_score"] = clarity_score
        state["question_clarity_issues"] = issues
        state["needs_clarification"] = needs_clarification
        
        logger.info(f"Clarity assessment: score={clarity_score:.2f}, needs_clarification={needs_clarification}")
        
        return state
        
    except Exception as e:
        logger.failure(f"Clarity assessment failed: {str(e)}")
        # Default to needing clarification on error
        state["question_clarity_score"] = 0.0
        state["question_clarity_issues"] = ["Unable to assess question clarity"]
        state["needs_clarification"] = True
        return state

async def request_clarification(state: AnalystState):
    """Request clarification from user when question is unclear."""
    logger.info("=== REQUESTING CLARIFICATION ===")
    
    current_question = get_current_question(state)
    issues = state.get("question_clarity_issues", [])
    
    try:
        clarification_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful data analyst assistant. The user's question needs clarification for proper analysis.

            Create a helpful response that:
            1. Acknowledges what they're asking about
            2. Explains what specific information is needed
            3. Provides 2-3 specific examples of better questions
            4. Asks them to clarify

            Be friendly and constructive. Help them understand what makes a good analytical question.
            """),
            ("human", """Original question: {question}
            
            Identified issues: {issues}
            
            Help the user clarify their question for better analysis.""")
        ])
        
        response = await llm.ainvoke(clarification_prompt.format_messages(
            question=current_question,
            issues=", ".join(issues) if issues else "Question needs more specificity"
        ))
        
        clarification_message = response.content.strip()
        
        state["messages"].append(AIMessage(content=clarification_message))
        state["waiting_for_feedback"] = True
        
        logger.info("Clarification requested from user")
        return state
        
    except Exception as e:
        logger.failure(f"Clarification request failed: {str(e)}")
        # Fallback message
        fallback_msg = f"""I need more details to analyze your question: "{current_question}"

Could you please specify:
- What specific data or metrics you want to see
- What time period you're interested in  
- What type of analysis you need (trends, comparisons, summaries, etc.)

This will help me provide a more accurate analysis."""
        
        state["messages"].append(AIMessage(content=fallback_msg))
        state["waiting_for_feedback"] = True
        return state

async def process_feedback(state: AnalystState):
    """Process user feedback and determine next action."""
    logger.info("=== PROCESSING FEEDBACK ===")
    
    if not state.get("waiting_for_feedback"):
        return state
    
    feedback = get_current_question(state)
    if not feedback:
        state["waiting_for_feedback"] = False
        return state
    
    # Check for stop commands
    stop_commands = {"stop", "abort", "cancel", "quit", "end", "exit", "no", "skip"}
    if feedback.lower().strip() in stop_commands:
        state["waiting_for_feedback"] = False
        logger.info("User chose to stop")
        return state
    
    # Check max feedback cycles
    if state["feedback_cycles"] >= MAX_FEEDBACK_CYCLES:
        state["waiting_for_feedback"] = False
        logger.info("Max feedback cycles reached, proceeding with available information")
        return state
    
    # Process as improved question
    state["feedback_cycles"] += 1
    state["waiting_for_feedback"] = False
    state["question"] = feedback  # Update question with feedback
    
    logger.info(f"Processing feedback cycle {state['feedback_cycles']}: {feedback[:50]}...")
    return state

async def assess_data_quality(state: AnalystState):
    """Assess the quality and completeness of retrieved data."""
    logger.info("=== ASSESSING DATA QUALITY ===")
    
    data = state.get("data", [])
    task = state.get("task", "")
    question = state.get("question", "")
    
    try:
        if not data:
            state["data_quality_score"] = 0.0
            logger.info("No data retrieved - quality score: 0.0")
            return state
        
        # Basic quality metrics
        row_count = len(data)
        has_meaningful_data = row_count > 0 and any(
            any(str(value).strip() for value in row.values()) 
            for row in data
        )
        
        # LLM assessment for contextual quality
        data_sample = str(data[:3]) if len(data) > 3 else str(data)
        
        quality_prompt = ChatPromptTemplate.from_messages([
            ("system", """Assess if this data adequately answers the analytical question.
            
            Consider:
            - Data completeness and relevance
            - Sufficient records for meaningful analysis
            - Data quality and usefulness
            
            Respond with:
            QUALITY_SCORE: [0.0-1.0]
            ASSESSMENT: [COMPLETE/PARTIAL/INSUFFICIENT]
            """),
            ("human", "Question: {question}\nTask: {task}\nData: {data_sample}\nRow count: {row_count}")
        ])
        
        response = await llm.ainvoke(quality_prompt.format_messages(
            question=question, task=task, data_sample=data_sample, row_count=row_count
        ))
        
        # Parse quality score
        quality_score = 0.5  # Default
        for line in response.content.split('\n'):
            if line.startswith("QUALITY_SCORE:"):
                try:
                    quality_score = float(line.split(":", 1)[1].strip())
                except:
                    pass
        
        state["data_quality_score"] = quality_score
        logger.info(f"Data quality score: {quality_score:.2f}")
        
        return state
        
    except Exception as e:
        logger.failure(f"Data quality assessment failed: {str(e)}")
        state["data_quality_score"] = 0.5  # Default on error
        return state

# ========== ORIGINAL NODES (MODIFIED) ==========

# ---------- 1. rewrite (updated to consider feedback) ---------------------
rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a data analyst. Your job is to rewrite the user's question into a clear, specific analytical task that can be answered with SQL queries.

CRITICAL INSTRUCTIONS:
- ALWAYS rewrite the question into a clear task, never ask for clarification
- Be specific about what data to retrieve and any calculations needed
- Focus on actionable SQL queries
- If the question is vague, make reasonable assumptions about what the user wants

Examples:
- User: "tell me about sales" → Task: "Analyze total sales revenue by product category for the current year"
- User: "inventory situation" → Task: "Show current inventory levels for all products with quantity and last updated dates"
- User: "best products" → Task: "Identify top 5 products by total sales revenue"

Always provide a specific task, never ask for more information."""),
    ("human", "{question}")
])

async def rewrite_node(state: AnalystState):
    try:
        logger.info("Starting rewrite task")
        
        # Get current question, considering feedback
        current_question = state.get("question", get_current_question(state))
        
        # Build context from feedback if available
        context = ""
        if state["feedback_cycles"] > 0:
            context = f" (This is feedback cycle {state['feedback_cycles']} - previous attempts may have been unclear)"
        
        logger.info(f"Final question to process: {current_question}")
        
        prompt_msgs = rewrite_prompt.format_messages(question=current_question + context)
        task_response = await llm_light.ainvoke(prompt_msgs)
        
        # Handle response
        if hasattr(task_response, 'content'):
            task = task_response.content.strip()
        elif isinstance(task_response, dict) and 'content' in task_response:
            task = task_response['content'].strip()
        else:
            task = str(task_response).strip()
        
        # Validate task
        if any(phrase in task.lower() for phrase in [
            "please provide", "could you specify", "what specific", 
            "more information", "clarify", "which", "what type"
        ]):
            logger.warning(f"LLM asked for clarification, generating default task for: {current_question}")
            if "inventory" in current_question.lower():
                task = "Show current inventory levels for all products with quantities and last updated information"
            elif "sales" in current_question.lower():
                task = "Analyze total sales revenue and quantities by product for recent periods"
            elif "revenue" in current_question.lower():
                task = "Calculate total revenue by product category and time period"
            else:
                task = f"Analyze data related to: {current_question}"
        
        # Add messages to state
        new_messages = [
            AIMessage(content=f"Rewritten task: {task}")
        ]
        
        logger.success(f"Task rewritten successfully: {task}")
        return {"task": task, "messages": new_messages, "question": current_question}
    except Exception as e:
        logger.failure(f"Error in rewrite: {str(e)}")
        error_msg = f"Error in rewrite: {str(e)}"
        
        current_question = state.get("question", get_current_question(state))
        
        new_messages = [
            AIMessage(content=f"Error: {error_msg}")
        ]
        return {"error": error_msg, "messages": new_messages, "question": current_question}

# ---------- 2. generate_sql (keep original) -------------------------------
sql_prompt = ChatPromptTemplate.from_messages([
    ("system",
     """You are a SQL expert working with SQLite database. Given the analytical task and database schema, write a SINGLE SQLite SELECT query.
     
     Database Schema:
     {schema}
     
     CRITICAL INSTRUCTIONS:
     - Return ONLY the SQL query, nothing else
     - No explanations, no markdown, no code blocks
     - Use proper SQLite syntax
     - For date operations use: strftime('%Y-%m', date_column) or date() functions
     - To calculate revenue: JOIN Sales with Products and Prices tables, then multiply quantity * price
     - Use appropriate JOINs to connect related tables
     - Always include WHERE clauses for date filtering when needed
     
     Example format (return exactly like this):
     SELECT p.category, SUM(s.quantity * pr.price) as total_revenue FROM Sales s JOIN Products p ON s.product_id = p.product_id JOIN Prices pr ON p.product_id = pr.product_id WHERE strftime('%Y', s.sale_date) = '2024' GROUP BY p.category ORDER BY total_revenue DESC LIMIT 1"""),
    ("human", "Task: {task}")
])

async def generate_sql_node(state: AnalystState):
    try:
        logger.info("Starting SQL generation")
        
        task = state.get("task")
        if not task:
            # Try to extract task from recent AI messages as fallback
            if state.get("messages"):
                for msg in reversed(state["messages"]):
                    msg_content = ""
                    if isinstance(msg, AIMessage):
                        msg_content = msg.content
                    elif isinstance(msg, dict) and 'content' in msg:
                        msg_content = msg['content']
                    
                    if "Rewritten task:" in msg_content:
                        task = msg_content.replace("Rewritten task:", "").strip()
                        logger.info(f"Extracted task from messages: {task}")
                        break
            
            if not task:
                question = state.get("question", "")
                if question:
                    if "inventory" in question.lower():
                        task = "Show current inventory levels for all products with quantities and last updated information"
                    elif "sales" in question.lower():
                        task = "Analyze total sales revenue and quantities by product for recent periods"
                    elif "revenue" in question.lower():
                        task = "Calculate total revenue by product category and time period"
                    else:
                        task = f"Analyze data related to: {question}"
                    logger.info(f"Generated fallback task: {task}")
                else:
                    raise ValueError("No task found in state, messages, or question")
        
        schema = get_database_schema()
        prompt_msgs = sql_prompt.format_messages(task=task, schema=schema)
        sql_response = await llm_light.ainvoke(prompt_msgs)
        
        if hasattr(sql_response, 'content'):
            sql_content = sql_response.content
        elif isinstance(sql_response, dict) and 'content' in sql_response:
            sql_content = sql_response['content']
        else:
            sql_content = str(sql_response)
        
        sql_clean = extract_sql_from_response(sql_content)
        
        sql_clean = sql_clean.strip()
        if sql_clean.endswith(';'):
            sql_clean = sql_clean[:-1]
        
        logger.success(f"SQL generated successfully: {sql_clean}")
        
        new_messages = [
            AIMessage(content=f"Generated SQL query: ```sql\n{sql_clean}\n```")
        ]
        
        return {"sql": sql_clean, "messages": new_messages, "task": task}
    except Exception as e:
        logger.failure(f"Error generating SQL: {str(e)}")
        error_msg = f"Error generating SQL: {str(e)}"
        new_messages = [
            AIMessage(content=f"Error generating SQL: {error_msg}")
        ]
        return {"error": error_msg, "messages": new_messages}

# ---------- 3. run_sql (keep original) -----------------------------------
async def run_sql_node(state: AnalystState):
    try:
        if state.get("error"):
            logger.warning(f"Skipping SQL execution due to previous error: {state['error']}")
            return {"error": state["error"]}
        
        sql = state.get("sql")
        if not sql:
            if state.get("messages"):
                for msg in reversed(state["messages"]):
                    msg_content = ""
                    if isinstance(msg, AIMessage):
                        msg_content = msg.content
                    elif isinstance(msg, dict) and 'content' in msg:
                        msg_content = msg['content']
                    
                    if "Generated SQL query:" in msg_content:
                        import re
                        sql_match = re.search(r'```sql\n(.*?)\n```', msg_content, re.DOTALL)
                        if sql_match:
                            sql = sql_match.group(1).strip()
                            logger.info(f"Extracted SQL from messages: {sql}")
                            break
            
            if not sql:
                error_msg = "No SQL query found in state or messages"
                logger.failure(error_msg)
                return {"error": error_msg}
            
        logger.info(f"Executing SQL query: {sql}")
        
        result = await asyncio.to_thread(query_tool.invoke, sql)
        
        logger.debug(f"Raw SQL result: {result}")
        
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if isinstance(data, list):
                    logger.success(f"SQL executed successfully, returned {len(data)} rows")
                    new_messages = [
                        AIMessage(content=f"SQL executed successfully. Retrieved {len(data)} rows of data.")
                    ]
                    return {"data": data, "messages": new_messages, "sql": sql}
                else:
                    processed_data = [data] if isinstance(data, dict) else [{"result": str(data)}]
                    logger.success("SQL executed successfully, returned single result")
                    new_messages = [
                        AIMessage(content="SQL executed successfully. Retrieved single result.")
                    ]
                    return {"data": processed_data, "messages": new_messages, "sql": sql}
            except json.JSONDecodeError:
                if result.strip():
                    lines = result.strip().split('\n')
                    if len(lines) > 1:
                        headers = [h.strip() for h in lines[0].split('|') if h.strip()]
                        data = []
                        for line in lines[1:]:
                            if '|' in line:
                                values = [v.strip() for v in line.split('|') if v.strip()]
                                if len(values) == len(headers):
                                    row = dict(zip(headers, values))
                                    data.append(row)
                        if data:
                            logger.success(f"SQL executed successfully, parsed {len(data)} rows from text result")
                            new_messages = [
                                AIMessage(content=f"SQL executed successfully. Parsed {len(data)} rows from result.")
                            ]
                            return {"data": data, "messages": new_messages, "sql": sql}
                    
                    logger.success("SQL executed successfully, returned text result")
                    new_messages = [
                        AIMessage(content="SQL executed successfully. Retrieved text result.")
                    ]
                    return {"data": [{"result": result}], "messages": new_messages, "sql": sql}
                else:
                    logger.info("SQL executed successfully but returned no data")
                    new_messages = [
                        AIMessage(content="SQL executed successfully but returned no data.")
                    ]
                    return {"data": [], "messages": new_messages, "sql": sql}
        else:
            logger.success("SQL executed successfully, returned direct result")
            new_messages = [
                AIMessage(content="SQL executed successfully. Retrieved direct result.")
            ]
            return {"data": [{"result": str(result)}], "messages": new_messages, "sql": sql}
        
    except Exception as e:
        logger.failure(f"Error executing SQL: {str(e)}")
        error_msg = f"Error executing SQL: {str(e)}"
        new_messages = [
            AIMessage(content=f"Error executing SQL: {error_msg}")
        ]
        return {"error": error_msg, "messages": new_messages}

# ---------- 4. answer (updated to handle insufficient data) --------------
def format_data_as_markdown_table(data: List[Dict[str, Any]]) -> str:
    """Convert list of dictionaries to markdown table format"""
    if not data:
        return "No data found."
    
    headers = list(data[0].keys())
    
    header_row = "| " + " | ".join(str(h) for h in headers) + " |"
    separator_row = "| " + " | ".join("---" for _ in headers) + " |"
    
    data_rows = []
    for row in data:
        row_values = [str(row.get(h, "")) for h in headers]
        data_rows.append("| " + " | ".join(row_values) + " |")
    
    return "\n".join([header_row, separator_row] + data_rows)

def format_data_as_text(data: List[Dict[str, Any]]) -> str:
    """Convert list of dictionaries to readable text format"""
    if not data:
        return "No data found."
    
    if len(data) == 1:
        row = data[0]
        lines = [f"{key}: {value}" for key, value in row.items()]
        return "\n".join(lines)
    
    headers = list(data[0].keys())
    
    col_widths = {}
    for header in headers:
        col_widths[header] = max(len(str(header)), 
                               max(len(str(row.get(header, ""))) for row in data))
    
    lines = []
    
    header_line = " | ".join(str(h).ljust(col_widths[h]) for h in headers)
    lines.append(header_line)
    lines.append("-" * len(header_line))
    
    for row in data:
        data_line = " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers)
        lines.append(data_line)
    
    return "\n".join(lines)

answer_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     """You are a senior data analyst. Analyze the query results thoroughly and provide a comprehensive, insightful response.

CRITICAL INSTRUCTIONS:
1. ALWAYS structure your response with:
   - Executive Summary: 1-2 sentence overview of key findings
   - Detailed Analysis: Breakdown of the data with specific numbers and trends
   - Key Insights: Actionable business insights and recommendations
   - Data Summary: Tabular overview when appropriate

2. If the data contains numerical information that can be tabulated, present it in markdown table format
3. Highlight unusual patterns, outliers, or significant trends
4. Provide specific, data-driven recommendations
5. Include relevant metrics and percentages where applicable
6. Use precise numbers from the data to support your analysis

Example format for tabular data:
## Executive Summary
Brief overview of main findings.

## Detailed Analysis
Breakdown of the data with specific observations.

## Key Insights
- Insight 1 with data support
- Insight 2 with recommendation

## Data Summary
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Value 4  | Value 5  | Value 6  |"""),
    ("human", 
     """Original question: {question}
     Analytical task: {task}
     SQL query: {sql}
     Results: {data}
     
     Provide a comprehensive analysis of these results.""")
])

async def answer_node(state: AnalystState):
    try:
        if state.get("error"):
            logger.warning(f"Providing error response due to previous error: {state['error']}")
            error_response = f"Sorry, I encountered an error: {state['error']}"
            error_report = f"## Error\n{state['error']}"
            
            new_messages = [
                AIMessage(content=error_response)
            ]
            
            return {
                "answer": error_response,
                "report": error_report,
                "messages": new_messages
            }
        
        data = state.get("data", [])
        data_quality = state.get("data_quality_score", 0.0)
        
        # Check if we should request feedback for insufficient data
        if not data or data_quality < 0.3:
            insufficient_msg = f"""I found limited data for your analysis.

**Your question:** {state.get('question', 'N/A')}
**Analysis attempted:** {state.get('task', 'N/A')}
**Data found:** {len(data)} records

This might be because:
- The requested data doesn't exist in the database
- The question needs more specific parameters
- Different terminology might be needed

Would you like to:
1. Rephrase your question with more specific details
2. Try a different analytical approach
3. Explore what data is available in this area

Please let me know how you'd like to proceed."""
            
            state["messages"].append(AIMessage(content=insufficient_msg))
            state["waiting_for_feedback"] = True
            return state
        
        logger.info("Generating detailed analysis with insights")
        
        question = state.get("question", "Unknown question")
        sql = state.get("sql", "Unknown SQL")
        task = state.get("task", "Unknown task")
        
        data_str = format_data_as_text(data)
        prompt_msgs = answer_prompt.format_messages(
            question=question, 
            task=task,
            sql=sql, 
            data=data_str
        )
        summary = await llm_light.ainvoke(prompt_msgs)

        if hasattr(summary, 'content'):
            summary_content = summary.content.strip()
        elif isinstance(summary, dict) and 'content' in summary:
            summary_content = summary['content'].strip()
        else:
            summary_content = str(summary).strip()

        data_md = format_data_as_markdown_table(data)
        
        stats_section = ""
        if data and isinstance(data[0], dict):
            numerical_columns = []
            for key, value in data[0].items():
                if isinstance(value, (int, float)):
                    numerical_columns.append(key)
            
            if numerical_columns:
                stats_section = "\n## Basic Statistics\n"
                for col in numerical_columns:
                    values = [row[col] for row in data if row[col] is not None and isinstance(row[col], (int, float))]
                    if values:
                        stats_section += f"- **{col}**: Avg: {sum(values)/len(values):.2f}, Min: {min(values)}, Max: {max(values)}, Count: {len(values)}\n"
        
        report_md = (
            f"# Analytical Report\n\n"
            f"## Original Question\n{question}\n\n"
            f"## Analytical Task\n{task}\n\n"
            f"## SQL Query\n```sql\n{sql}\n```\n\n"
            f"## Results Overview\nRetrieved {len(data)} records\n\n"
            f"## Detailed Data\n{data_md}\n"
            f"{stats_section}\n"
            f"## Analysis\n{summary_content}"
        )
        
        logger.success("Comprehensive analysis completed successfully")
        
        new_messages = [
            AIMessage(content=f"Comprehensive Analysis:\n{summary_content}")
        ]
        
        return {
            "answer": summary_content, 
            "report": report_md,
            "messages": new_messages
        }
        
    except Exception as e:
        logger.failure(f"Error in analysis: {str(e)}")
        error_msg = f"Error in analysis: {str(e)}"
        
        new_messages = [
            AIMessage(content=error_msg)
        ]
        
        return {
            "answer": error_msg,
            "report": f"## Error\n{error_msg}",
            "messages": new_messages
        }

# ========== ROUTING FUNCTIONS ==========

def route_after_clarity_assessment(state: AnalystState) -> Literal["request_clarification", "rewrite"]:
    """Route based on question clarity."""
    if state.get("needs_clarification", True) and state["feedback_cycles"] == 0:
        return "request_clarification"
    else:
        return "rewrite"

def route_after_feedback(state: AnalystState) -> Literal["assess_question_clarity", "answer"]:
    """Route after processing feedback."""
    if not state.get("waiting_for_feedback"):
        if state["feedback_cycles"] > 0:
            return "assess_question_clarity"  # Re-assess with new info
        else:
            return "answer"  # Continue to answer
    else:
        return "answer"  # Safety net

def route_after_data_quality(state: AnalystState) -> Literal["answer", "request_clarification"]:
    """Route based on data quality."""
    quality_score = state.get("data_quality_score", 0.0)
    if quality_score < 0.3 and state["feedback_cycles"] < MAX_FEEDBACK_CYCLES:
        return "request_clarification"
    else:
        return "answer"

# ========== BUILD WORKFLOW ==========

workflow = StateGraph(AnalystState)

# Add all nodes
workflow.add_node("process_input", process_input)
workflow.add_node("assess_question_clarity", assess_question_clarity)
workflow.add_node("request_clarification", request_clarification)
workflow.add_node("process_feedback", process_feedback)
workflow.add_node("rewrite", rewrite_node)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("run_sql", run_sql_node)
workflow.add_node("assess_data_quality", assess_data_quality)
workflow.add_node("answer", answer_node)

# Define flow
workflow.set_entry_point("process_input")

# Main flow
workflow.add_edge("process_input", "assess_question_clarity")

# Conditional routing after clarity assessment
workflow.add_conditional_edges(
    "assess_question_clarity",
    route_after_clarity_assessment,
    {
        "request_clarification": "request_clarification",
        "rewrite": "rewrite"
    }
)

# Feedback loop
workflow.add_edge("request_clarification", "process_feedback")
workflow.add_conditional_edges(
    "process_feedback",
    route_after_feedback,
    {
        "assess_question_clarity": "assess_question_clarity",
        "answer": "answer"
    }
)

# Analysis flow
workflow.add_edge("rewrite", "generate_sql")
workflow.add_edge("generate_sql", "run_sql") 
workflow.add_edge("run_sql", "assess_data_quality")

# Quality-based routing
workflow.add_conditional_edges(
    "assess_data_quality",
    route_after_data_quality,
    {
        "request_clarification": "request_clarification",
        "answer": "answer"
    }
)

workflow.add_edge("answer", END)

# Compile with interrupt capability for user feedback
app = workflow.compile(interrupt_after=["request_clarification"])

# Alternative function for API usage
async def analyze_question(question: str, initial_messages: List[BaseMessage] = None):
    """Entry point for API usage - more flexible input handling"""
    logger.info(f"API: Starting analysis for question: {question}")
    
    if initial_messages is None:
        initial_messages = [HumanMessage(content=question)]
    
    has_question = any(isinstance(msg, HumanMessage) and question in msg.content for msg in initial_messages)
    if not has_question:
        initial_messages.insert(0, HumanMessage(content=question))
    
    initial_state = {
        "question": question,
        "messages": initial_messages,
        "feedback_cycles": 0,
        "waiting_for_feedback": False,
        "task": "",
        "sql": "",
        "data": [],
        "answer": "",
        "report": "",
        "error": "",
        "question_clarity_score": 0.0,
        "question_clarity_issues": [],
        "data_quality_score": 0.0,
        "needs_clarification": False
    }
    
    logger.info(f"API: Processing with {len(initial_messages)} initial messages")
    
    result = await app.ainvoke(initial_state)
    
    logger.info("API: Analysis completed")
    return result

async def main():
    question = "tell me the situation of my current inventory?"
    
    logger.info(f"Starting analysis for question: {question}")
    
    initial_state = {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "feedback_cycles": 0,
        "waiting_for_feedback": False,
        "task": "",
        "sql": "",
        "data": [],
        "answer": "",
        "report": "",
        "error": "",
        "question_clarity_score": 0.0,
        "question_clarity_issues": [],
        "data_quality_score": 0.0,
        "needs_clarification": False
    }
    
    logger.info(f"Initial state keys: {list(initial_state.keys())}")
    logger.info(f"Initial messages: {[type(msg).__name__ + ': ' + msg.content for msg in initial_state['messages']]}")
    
    result = await app.ainvoke(initial_state)
    
    logger.info("Analysis completed")
    
    print("=== ANSWER ===")
    print(result.get("answer", "No answer generated"))
    print("\n=== FULL REPORT ===")
    print(result.get("report", "No report generated"))
    print("\n=== MESSAGE HISTORY ===")
    messages = result.get("messages", [])
    for i, msg in enumerate(messages):
        msg_type = "Human" if isinstance(msg, HumanMessage) else "AI"
        print(f"{i+1}. {msg_type}: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())