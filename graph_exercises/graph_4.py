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



# class MessageState(MessagesState):
#     messages:Annotated[list[AnyMessage], add_messages]




manager = LLMManager()

 

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


llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=256
     
)


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
    {"tools": "tools", "end": END}
)
builder.add_edge("tools", "assistant")

# react graph
graph = builder.compile()



react_graph_memory = builder.compile(checkpointer=memory,
                                      interrupt_before=["tools"],
                                        interrupt_after=["tools"])


 