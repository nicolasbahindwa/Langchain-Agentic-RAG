 
from typing_extensions import TypedDict
import random
from typing import Literal, Annotated, List
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
from pydantic import BaseModel, Field
from langgraph.types import Send

 


search_manager = SearchManager()
manager = LLMManager()

llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=256
     
)
 

class Analyst(BaseModel):
    affiliation: str = Field(
        description="Primary affiliation of the analyst."
    )
    name: str = Field(
        description="Name of the analyst"
    )
    role: str = Field(
        description="Role if the analyst in the context of the topic"
    )
    
    description: str = Field(
        description="Role of the analyst focus, concerns, and motives"
    )
    
    @property
    def persona(self)->str:
        return f"Name: {self.name} \nRole: {self.role}\nAffilation: {self.affiliation}\nDescription:{self.description}\n"
        
    
    
    

class Perspectives(BaseModel):
    analysts: List[Analyst] = Field(
            description="Comprehension list of analysts with their roles and affiliations."
        )

class GenerateAnalystsState(TypedDict):
    topic: str
    max_analysts: int
    human_analyst_feedback: str
    analysts: List[Analyst]



analyst_instructions = """You are tasked with creating a set of AI analyst personas. Follow these instructions carefully:

1. First, review the research topic:
{topic}
        
2. Examine any editorial feedback that has been optionally provided to guide creation of the analysts: 
        
{human_analyst_feedback}
    
3. Determine the most interesting themes based upon documents and / or feedback above.
                    
4. Pick the top {max_analysts} themes.

5. Assign one analyst to each theme."""


# nodes

def create_analysts(state:GenerateAnalystsState):
    """ Create analysts """
    topic = state['topic']
    max_analysts = state["max_analysts"]
    human_analyst_feedback= state.get("human_analyst_feedback")
    
    # efforce structured output
    structured_llm = llm.with_structured_output(Perspectives)
    
    # system message
    system_message = analyst_instructions.format(topic=topic, 
                                                 human_analyst_feedback=human_analyst_feedback,
                                                 max_analysts=max_analysts)
    
    # generate question
    analysts = structured_llm.invoke([SystemMessage(content=system_message)] + [HumanMessage(content="Generate the set analysts. ")])
    
    # write the list of analysis to state
    return {"analysts": analysts.analysts}


def human_feedback(state: GenerateAnalystsState):
    """ No-op node that should be interrupted on """
    pass


def should_continue(state: GenerateAnalystsState):
    """ Return the next node to execute """
    human_analyst_feedback=state.get("human_analyst_feedback", None)
    if human_analyst_feedback:
        return "create_analysts"
    
    # otherwise
    END


# Add nodes and edges 
builder = StateGraph(GenerateAnalystsState)
builder.add_node("create_analysts", create_analysts)
builder.add_node("human_feedback", human_feedback)
builder.add_edge(START, "create_analysts")
builder.add_edge("create_analysts", "human_feedback")
builder.add_conditional_edges("human_feedback", should_continue, ["create_analysts", END])

# Compile
memory = MemorySaver()
graph = builder.compile(interrupt_before=['human_feedback'], checkpointer=memory)