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

 
conn = sqlite3.connect(":memory:")
db_path = "state_db/example.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
memory = SqliteSaver(conn)

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


graph = workflow.compile(checkpointer=memory)


config = {"configurable": {"thread_id": "1"}}

# start conversation
# input_message = HumanMessage(content="Hi, my name is john doe")
# output = graph.invoke({"messages": [input_message]}, config)
# for m in output ["messages"][-1:]:
#     print(m)
    

input_message = HumanMessage(content="what is my name")
output = graph.invoke({"messages": [input_message]}, config)
for m in output ["messages"][-1:]:
    print(m)
    

# input_message = HumanMessage(content="I'm form the democratic republic of congo")
# output = graph.invoke({"messages": [input_message]}, config)
# for m in output ["messages"][-1:]:
#     print(m)


input_message = HumanMessage(content="what do you know about my country")
output = graph.invoke({"messages": [input_message]}, config)
for m in output ["messages"][-1:]:
    print(m)






