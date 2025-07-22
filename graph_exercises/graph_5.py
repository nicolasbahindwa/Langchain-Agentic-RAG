from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class InputState(TypedDict):
    question: str

class OutputState(TypedDict):
    answer: str

class OverallState(TypedDict):
    question:str
    answer:str
    notes:str

def think_node(state: InputState):
    return {"answer": "bye", "notes": "...hi is name john does"}


def answer_node(state: OverallState)-> OutputState:
    return {"answer": "bye john doe"}
    
    
 

graph = StateGraph(OverallState, input=InputState, output=OutputState)

graph.add_node("answer_node", answer_node)
graph.add_node("think_node", think_node)

graph.add_edge(START, "think_node")
graph.add_edge("think_node", "answer_node")
graph.add_edge("answer_node", END)


graph = graph.compile()

