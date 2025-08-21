
from typing_extensions import TypedDict
import random
from typing import Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, AnyMessage
from langgraph.graph.message import add_messages
from langgraph.graph import MessagesState
from pprint import pprint
from core.llm_manager import LLMManager, LLMProvider
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import NodeInterrupt
 


# class MessageState(MessagesState):
#     messages:Annotated[list[AnyMessage], add_messages]




manager = LLMManager()

llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=256
     
)

def multiply(a:int, b:int)-> int:
    """ Multiply a and b.
    
    Args:
        a: first int
        b: second int
    """
    return a * b

def add(a:int, b:int)-> int:
    """ Add a and b
    
    Args:
        a: first int
        b: second int
    """
    return a + b

def divide(a:int, b:int)-> float:
    """Devide a and b
    
    Args: 
        a: first int
        b: second int
    """
    return a / b


tools = [add, multiply, divide]





llm_with_tools = llm.bind_tools(tools=tools)

sys_msg = SystemMessage(content="You are a helpful assistant taked with performing arithmetics on a set of inputs.")

# nodes
def assistant (state:MessagesState):
    return {"messages": [llm_with_tools.invoke([sys_msg] + state["messages"])]}

memory = MemorySaver()
builder = StateGraph(MessagesState)

builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "assistant")
builder.add_conditional_edges(
    "assistant",
    tools_condition,
    {"tools": "tools", "__end__": END}
)
builder.add_edge("tools", "assistant")

# react graph
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)


 
initial_input = {"messages": "Multiply 4 and 9"}

thread = {"configurable": {"thread_id": "1"}}

for event in graph.stream(initial_input, thread, stream_mode="values"):
    print("===================================================")
    pprint(event)
 
 
snapshot = graph.get_state({"configurable": {"thread_id": "1"}})
pprint(snapshot)
print("*" * 50)

all_states = [s for s in graph.get_state_history(thread)]

print(all_states)
print(len(all_states))
print(all_states[0])


replay = all_states[-2]

print("---------------------- replay -------------------------------")
print(replay.values)
print(replay.next)
print(replay.config)
print(replay)

for event in graph.stream(None, replay.config, stream_mode="values"):
    print(event["messages"][-1])
    
    
    
    
to_fork = all_states[-2]
to_fork.values["messages"]

print(to_fork.config)

fork_config = graph.update_state(
    to_fork.config,
    {"messages": [HumanMessage(content="multiply 5 and 3", id=to_fork.values["messages"][0].id)]},
)

print("#" * 5)

print(to_fork)