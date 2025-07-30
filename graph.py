 
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
from langchain_core.messages import get_buffer_string
from IPython.display import Markdown

 


search_manager = SearchManager()
manager = LLMManager()

llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=1500
)

llm_light = manager.get_chat_model(
    provider=LLMProvider.OLLAMA
)



class  RagState(TypedDict):
    messages: str
    question: str
    original_question:str
    answer: str
    context: List[str]
    ranked_context: List[str]
    answer: str
    process_cycle_count:int
    user_feedback: str
    feedback_cycle_count: int
    
    




def question_rewrite(state:RagState)->RagState:
    """ rewrite the question"""
    question = state["question"]
    feedback = state.get("user_feedback", "")
    original_question = state.get("original_question", "")
    
    rewrite_prompt = f"""
        Rewrite the following question to make it more effective for document search.
        Maintain the original language and preserve all key terms.

        Conversation history:
        {question}

        Original question: {state.get("original_question", "")}

        Rewritten question (concise):
    """
    
    if feedback and feedback.lower() != "none":
        question = f"{question}\n Clarification and Additional requested by user: {feedback}"
    
    messages = [SystemMessage(content=rewrite_prompt), 
                HumanMessage(content=f"original question: {original_question} \n current {question}")]
       
    
    enhanced_question = llm_light.invoke(messages).content.strip()
    state["question"] = enhanced_question
   
    
    return state


def retrieve_context(state:RagState)->RagState:
    """retrieve the context to asnwer the question"""
    question = state["question"]
    feedback = state.get("user_feedback", "")
    
    if feedback:
        # retrieve more additional context
        pass
    else:
        pass
    
    # retrieve context
    retrieve_context = ["contextq1", "contact 2", "context 3"]
    state["context"] = retrieve_context
    return state


def context_ranking(state:RagState)->RagState:
    """ Rank the best context that contains the relavant information to answer the question"""
    context = state["context"]
    question = state["question"]
    feedback = state.get("user_feedback", "")
    
    if feedback:
        # consider user feedback in ranking
        pass
    
    ranked_context = context
    state["ranked_context"] = ranked_context
    
    return state

def collect_user_feedback(state:RagState)-> RagState:
    """ Asking for humman feedback before proceeding"""
    question = state["original_question"]
    context_summary = state["ranked_context"][:2]
    
 
    print(f"Question: {question}")
    print(f"Context found: {context_summary}")
    print("Please provide feedback or type 'none' to proceed...")
 
    state["user_feedback"] = "none"   
    return state

def process_feedback(state:RagState)->RagState:
    """ Process the user feedback and determine next steps"""
    feedback = state.get("user_feedback", "").strip().lower()
    
    cycle_count = state.get("feedback_cycle_count", 0)
    
    if feedback and feedback != "none":
        state["feedback_cycle_count"] = cycle_count + 1
    
    return state

def answer_generation(state:RagState)->RagState:
    """ answer the question"""
    question = state["question"]
    context = state["context"]
    feedback = state.get("user_feedback", "")
    
    if feedback:
        # incorporate user feedback 
        pass
    
    
    answer = "generated answer"
    
    state["answer"] = answer
    return state

def has_meaningful_feedback(state:RagState) -> Literal["process_feedback", "generate_answer"]:
    """check if usere provided meaningful feedback"""
    feedback = state.get("user_feedback", "").strip().lower()
    cycle_count = state.get("feedback_cycle_count", 0)
    
    if feedback and feedback != "none" and cycle_count < 3:
        return "process_feedback"
    else:
        return "generate_answer"
        

def should_retrieve_mode_context(state:RagState)-> Literal["retrieve_more", "generate_answer"]:
    """deternmine if we should continue execution"""
    feedback = state.get("process_feedback", "").strip().lower()
    cycle_count = state.get("feedback_cycle_count", 0)
    
    if feedback and feedback != "none" and cycle_count < 3:
        return "retrieve_more"
    else:
        return "generate_answer"






graph = StateGraph(RagState)

graph.add_node("question_rewrite", question_rewrite)
graph.add_node("retrieve_context", retrieve_context)
graph.add_node("context_ranking", context_ranking)
graph.add_node("collect_user_feedback", collect_user_feedback)
graph.add_node("process_feedback", process_feedback)
graph.add_node("answer_generation", answer_generation)


graph.add_edge(START, "question_rewrite")
graph.add_edge("question_rewrite", "retrieve_context")
graph.add_edge("retrieve_context", "context_ranking") 
graph.add_edge("context_ranking", "collect_user_feedback")

graph.add_conditional_edges(
    "collect_user_feedback",
        has_meaningful_feedback,
        {
            "process_feedback": "process_feedback",
            "generate_answer": "answer_generation"
        }
    )

graph.add_conditional_edges(
    "process_feedback",
    should_retrieve_mode_context,
    {
        "retrieve_more": "question_rewrite",
        "generate_answer": "answer_generation"
    }
)
graph.add_edge("answer_generation", END)


app = graph.compile()

