from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from pprint import pprint
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, RemoveMessage
from langgraph.graph import MessagesState
from core.llm_manager import LLMManager, LLMProvider
from langgraph.checkpoint.memory import MemorySaver
from pprint import pprint
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import asyncio
import aiosqlite
import os

 
os.makedirs("state_db", exist_ok=True)
db_path = "state_db/example.db"
 
# memory = SqliteSaver(conn)
# memory = AsyncSqliteSaver(conn)

manager = LLMManager()
llm = manager.get_chat_model(
    provider = LLMProvider.ANTHROPIC,
    temperature=0.7,
    model="claude-3-haiku-20240307",
    max_tokens=256

)

class State(MessagesState):
    summary: str = ""  # Provide default value

def call_model(state: State):
    summary = state.get('summary', "")
    
    print(f"DEBUG call_model: summary={summary}, messages_count={len(state['messages'])}")
    
    if summary:
        system_message = f"Summary of conversation earlier: {summary}"
        messages = [SystemMessage(content=system_message)] + state["messages"]
    else:
        messages = state["messages"]
    
    response = llm.invoke(messages)
    
    return {"messages": [response]}  # Return as list

def summarize_conversation(state: State):
    summary = state.get("summary", "")
    messages_count = len(state["messages"])
    
    print(f"DEBUG summarize: current_summary={summary}, messages_count={messages_count}")
    
    if summary:
        summary_message = (
            f"This is summary of the conversation to date: {summary}\n\n"
            "Extend the summary taking into account the new messages above:"
        )
    else:
        summary_message = "Create a summary of the conversation above:"
    
    messages = state["messages"] + [HumanMessage(content=summary_message)]
    response = llm.invoke(messages)
    
    # Keep last 2 messages, remove the rest
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    
    print(f"DEBUG summarize: new_summary={response.content[:50]}...")
    
    return {"summary": response.content, "messages": delete_messages}

def should_continue(state: State):
    messages = state["messages"]
    count = len(messages)
    
    print(f"DEBUG should_continue: message_count={count}")
    
    if count > 6:
        return "summarize_conversation"
    return "end"

# Use the correct State type
workflow = StateGraph(State)

workflow.add_node("conversation", call_model)
workflow.add_node("summarize_conversation", summarize_conversation)

workflow.add_edge(START, "conversation")
workflow.add_conditional_edges("conversation", should_continue, {
    "summarize_conversation": "summarize_conversation",
    "end": END
})
workflow.add_edge("summarize_conversation", END)


# graph = workflow.compile(checkpointer=memory)


# config = {"configurable": {"thread_id": "1"}}

 
# for chunk in graph.stream({"messages": [HumanMessage(content="hello, i'm jonh doe")]}, config, stream_mode="updates"):
#     pprint(chunk['conversation']['messages'])




# config = {"configurable": {"thread_id": "3"}}

# input_message = HumanMessage(content="Tell me about zaire country in one sentence")
# async for event in graph.astream_events({"messages":[input_message]}, config, version="v2"):
#     print(f"Node: {event['metadata'].get('langgraph_node', '')}, Type: {event['event']}. Name:{event['name']}")

async def run_async_stream():
    async with aiosqlite.connect(db_path) as conn:
        memory = AsyncSqliteSaver(conn)
        
        # Compile graph with async checkpointer
        graph = workflow.compile(checkpointer=memory)
        
        node_to_stream = 'conversation'
        config = {"configurable": {"thread_id": "4"}}
        input_message = HumanMessage(content="i'm nicolas and i come from zaire")
        async for event in graph.astream_events(
            {"messages":[input_message]}, 
            config, 
            version="v2"
        ):
            # print(f"Node: {event['metadata'].get('langgraph_node', '')}, Type: {event['event']}. Name:{event['name']}")
            
            
            if event['event'] == "on_chat_model_stream" and event["metadata"].get("langgraph_node", "") == node_to_stream:
                print(event["data"])
                
        
        # async for event in graph.astream_events({"messages":[input_message]}, config, version="v2"):
        #     if event["event"] == "on_chat_model_stream" and event["metadata"].get("langgraph_node", "") == node_to_stream:
        #         data = event["data"]
        #         print(data["chunk"].content, end="|")
        
        # thread = await client.threads.create()
        # input_message = HumanMessage(content="Multiply 2 to 3")
        
        # async for event in client.runs.stream(thread["thread_id"], assistant_id = "agent", input={"messages": [input_message]}, stream_mode="messages"):
        #     print(event.event)

# Run the async function
asyncio.run(run_async_stream())

 