from typing_extensions import TypedDict
import random
from typing import Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, AnyMessage
from langgraph.graph.message import add_messages
from langgraph.graph import MessagesState
from pprint import pprint
from core.llm_manager import LLMManager, LLMProvider



class MessageState(MessagesState):
    messages:Annotated[list[AnyMessage], add_messages]




manager = LLMManager()

llm = manager.get_chat_model(
    provider = LLMProvider.ANTHROPIC,
    temperature=0.7,
    model="claude-3-haiku-20240307",
    max_tokens=256

)

 
def multiplication(a: int, b:int)->int:

    return a * b


llm_with_tools = llm.bind_tools([multiplication])

tool_call = llm_with_tools.invoke([HumanMessage(content=f"what is 10 multiply by 5", name="user")])

pprint(tool_call.tool_calls)


initial_messages = [AIMessage(content="hello, how are you felling", name="AI"),
                    HumanMessage(content="I'm looking for information about the dr congo", name="John deo")]

print(initial_messages)
new_message = AIMessage(content="surre, i can help you, what do you want to know", name="AI")

add_messages(initial_messages, new_message)




def tool_calling_llm(state: MessagesState):
    return{"messages": [llm_with_tools.invoke(state["messages"])]}

builder = StateGraph(MessagesState)

builder.add_node("tool_calling_llm", tool_calling_llm)
builder.add_edge(START, "tool_calling_llm")
builder.add_edge("tool_calling_llm", END)

graph = builder.compile()


messages = graph.invoke({"messages": HumanMessage(content="Multiply 2 and 3")})
for m in messages['messages']:
    m.pretty_print()

