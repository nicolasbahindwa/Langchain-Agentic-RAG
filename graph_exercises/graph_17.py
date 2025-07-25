 
from typing_extensions import TypedDict
import random
from typing import Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, AnyMessage
from langgraph.graph.message import add_messages
from langgraph.graph import MessagesState
from pprint import pprint
from core.llm_manager import LLMManager, LLMProvider
from core.search_manager import SearchManager
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import NodeInterrupt
import operator
from pydantic import BaseModel
from langgraph.types import Send


# class MessageState(MessagesState):
#     messages:Annotated[list[AnyMessage], add_messages]



search_manager = SearchManager()
manager = LLMManager()

llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=256
     
)
 

subject_promt = """Generate a comma separated list of between 2 and 5 examples related to : {topic}."""
joke_prompt = """Generate a joke about {subject}"""
best_joke_prompt = """Bellow are bunch of jokes about {topic}. select the best one! return the ID of the best, starting 0 as the ID for the first joke. Jokes: \n\n  {jokes}"""


class Subjects(BaseModel):
    subjects: list[str]
    

class BestJoke(BaseModel):
    id:int

class OverallState(TypedDict):
    topic:str
    subjects: list
    jokes:Annotated[list, operator.add]
    best_selected_joke:str


def generate_topics(state: OverallState):
    prompt = subject_promt.format(topic=state["topic"])
    response = llm.with_structured_output(Subjects).invoke(prompt)
    return{"subjects": response.subjects}


def continue_to_jokes(state: OverallState):
    return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]



class Joke_state(TypedDict):
    subject: str

class Joke(BaseModel):
    joke:str

def generate_joke(state:OverallState):
    prompt = joke_prompt.format(subject=state["subject"])
    response = llm.with_structured_output(Joke).invoke(prompt)
    return {"jokes": [response.joke]}


def best_joke(state:OverallState):
    jokes = "\n\n".join(state["jokes"])
    prompt = best_joke_prompt.format(topic=state["topic"], jokes=jokes)
    response = llm.with_structured_output(BestJoke).invoke(prompt)
    return {"best_selected_joke": state["jokes"][response.id]}


graph = StateGraph(OverallState)

graph.add_node("generate_topics", generate_topics)
graph.add_node("generate_joke", generate_joke)
graph.add_node("best_joke", best_joke)

graph.add_edge(START, "generate_topics")
graph.add_conditional_edges("generate_topics", continue_to_jokes, ["generate_joke"])
graph.add_edge("generate_joke", "best_joke")
graph.add_edge("best_joke", END)


graph = graph.compile()

for s in graph.stream({"topic": "dog"}):
    print(s)