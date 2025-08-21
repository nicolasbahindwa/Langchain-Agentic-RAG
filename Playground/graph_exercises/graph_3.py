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



# class MessageState(MessagesState):
#     messages:Annotated[list[AnyMessage], add_messages]




manager = LLMManager()

llm = manager.get_chat_model(
    provider = LLMProvider.ANTHROPIC,
    temperature=0.7,
    model="claude-3-haiku-20240307",
    max_tokens=256

)


def multiply(a:int, b:int)-> int:
    """Multipy a and b
    args:
        a: first int
        b: second int
    """
    return a * b

llm_with_tools = llm.bind_tools([multiply])
  

# node
def tool_calling_llm(state:MessagesState):
    return {"messages":[llm_with_tools.invoke(state["messages"])]}


builder = StateGraph(MessagesState)

builder.add_node("tool_calling_llm", tool_calling_llm)
builder.add_node("tools", ToolNode([multiply]))


builder.add_edge(START, "tool_calling_llm")
builder.add_conditional_edges("tool_calling_llm", tools_condition)
builder.add_edge("tools", END)

graph = builder.compile()




