
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
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.document_loaders import WikipediaLoader


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

class State(TypedDict):
    question: str
    answer: str
    context: Annotated[list, operator.add]


# def search_web(state):
#     """Retrieve docs from web search"""
#     tavily_search = search_manager.get_web_search(max_results=3)
#     search_docs = tavily_search.invoke(state["question"])
    
#     formatted_search_docs = "\n\n ---\n\n".join(
#         [
#             f'<Document href="{doc["url"]}">\n{doc["content"]}\n</Document>'
#             for doc in search_docs
#         ]
#     )
#     return {"context": [formatted_search_docs]}
def search_web(state):
    """Retrieve docs from web search"""
    tavily_search = search_manager.get_web_search(max_results=3)
    search_docs = tavily_search.invoke(state["question"])
    
    # Fixed: Handle different possible formats of search results
    formatted_search_docs = []
    
    if isinstance(search_docs, list):
        for doc in search_docs:
            if isinstance(doc, dict):
                # Try different possible keys
                content = (doc.get("content") or 
                          doc.get("snippet") or 
                          doc.get("text") or 
                          doc.get("body") or 
                          str(doc))
                formatted_search_docs.append(content)
            elif isinstance(doc, str):
                formatted_search_docs.append(doc)
            else:
                formatted_search_docs.append(str(doc))
    else:
        # Handle case where search_docs is not a list
        formatted_search_docs.append(str(search_docs))
    
    final_formatted_docs = "\n\n ---\n\n".join(formatted_search_docs)
    return {"context": [final_formatted_docs]}

def search_wikipedia(state):
    """Retrieve docs from wikipedia"""
    
    wikipedia_loader = search_manager.get_wikipedia_loader(query=state["question"], load_max_docs=2)
    search_docs = wikipedia_loader.load()
    formatted_search_docs = "\n\n ---\n\n".join([
        f' <Document source="{doc.metadata["source"]}" page="{doc.metadata.get("page", "")}">\n{doc.page_content}\n</Document>'
        for doc in search_docs
    ])
    
    return {"context": [formatted_search_docs]}


def generate_answer(state):
    """Node to answer a question"""
    
    # get state
    context = state["context"]
    question = state["question"]
    
    # tempplate
    answer_template = """Answer the question {question} using this context: {context} """
    answer_instructions = answer_template.format(question=question, context=context)
    
    
    # answer
    answer = llm.invoke([SystemMessage(content=answer_instructions)] + [HumanMessage(content=f"answer the question.")])
    
    return {"answer": answer}

builder = StateGraph(State)

builder.add_node("search_web", search_web)
builder.add_node("search_wikipedia", search_wikipedia)
builder.add_node("generate_answer", generate_answer)

# flow
builder.add_edge(START, "search_wikipedia")
builder.add_edge(START, "search_web")
builder.add_edge("search_wikipedia", "generate_answer")
builder.add_edge("search_web", "generate_answer")
builder.add_edge("generate_answer", END)

graph = builder.compile()

result = graph.invoke({"question": "what is was the result of japanese election 2025 july"})
answer = result["answer"].content

print(answer)