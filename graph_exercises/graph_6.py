from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from pprint import pprint
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import MessagesState
from core.llm_manager import LLMManager, LLMProvider

messages = [AIMessage(content=f"So you said you were researching about congo", name="bot")]
messages.append(HumanMessage(content=f"Yes, tell me about the country in question"))

manager = LLMManager()


llm = manager.get_chat_model(
    provider = LLMProvider.ANTHROPIC,
    temperature=0.7,
    model="claude-3-haiku-20240307",
    max_tokens=256

)



for m in messages:
    m.pretty_print()

def chat_model_node(state: MessagesState):
    return {"messages": llm.invoke(state["messages"][-1])}

builder = StateGraph(MessagesState)

builder.add_node("chat_model_node", chat_model_node)
builder.add_edge(START, "chat_model_node")
builder.add_edge("chat_model_node", END)

graph = builder.compile()



 