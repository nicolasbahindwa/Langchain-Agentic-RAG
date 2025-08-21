from typing_extensions import TypedDict
import random
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pprint import pprint
from core.llm_manager import LLMManager, LLMProvider



class State(TypedDict):
    graph_state:str



def node_1(state):
    print("__Node 1__")
    return {"graph_state": state['graph_state'] + "I am"}

def node_2(state):
    print("__Node 2__")
    return {"graph_state": state["graph_state"]+ "happy"}

def node_3(state):
    print("__Node 3__")
    return {"graph_state": state["graph_state"] + "sad"}



def decine_mood(state)-> Literal["node_2", "node_3"]:
    user_input = state["graph_state"]

    if random.random() < 0.5:
        return "node_2"
    else:
        return "node_3"
    

builder = StateGraph(State)

builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_node("node_3", node_3)

builder.add_edge(START, "node_1")
builder.add_conditional_edges("node_1", decine_mood)
builder.add_edge("node_2", END)
builder.add_edge("node_3", END)


graph = builder.compile()



if __name__ == "__main__":
    graph.invoke({"graph_state": "hi, this is lance"})

    messages = [AIMessage(content=f"what are you up to today", name="AI")]
    messages.extend([HumanMessage(content=f"I'M Cool, ", name='User')])
    messages.extend([AIMessage(content=f"Great, what would you like to learn about", name="AI")])
    messages.extend([HumanMessage(content=f"I want to learn about the best place to travel", name="User")])

    for m in messages:
        m.pretty_print()



    manager = LLMManager()

    llm = manager.get_chat_model(
        provider = LLMProvider.ANTHROPIC,
        temperature=0.7,
        model="claude-3-haiku-20240307",
        max_tokens=256

    )

    result = llm.invoke(messages)
    type(result)


    


