from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from pprint import pprint
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, RemoveMessage
from langgraph.graph import MessagesState
from core.llm_manager import LLMManager, LLMProvider
from langgraph.checkpoint.memory import MemorySaver

 

manager = LLMManager()
llm = manager.get_chat_model(
    provider = LLMProvider.ANTHROPIC,
    temperature=0.7,
    model="claude-3-haiku-20240307",
    max_tokens=256

)



class State(MessagesState):
    summary:str
    
def call_model(state:State):
    summary = state.get('summary', "")
    
    if summary:
        system_message = f"summary of conversation earlier {summary}"
        
        messages = [SystemMessage(content=system_message)] + state["messages"]
    else:
        messages = state["messages"]
    
    response = llm.invoke(messages)
    
    return {"messages": response}


def summarize_conversation(state: State):
    
    summary =state.get("summary", "")
    
    if summary:
        
        summary_message= (
            f"this is summary of the conversation to date: {summary}\n\n"
            "Extend the summary taking into account the new messages above:"
        )
    
    else:
        summary_message = "Create a summary of the conversation above:"
    
    messages = state["messages"] + [HumanMessage(content=summary_message)]
    
    response = llm.invoke(messages)
    
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    
    return {"summary": response.content, "messages": delete_messages}


def should_continue(state: State):
    messages = state["messages"]
    
    if len(messages) > 6:
        return "summarize_conversation"
    

    return END


workflow = StateGraph(MessagesState)

workflow.add_node("conversation", call_model)
workflow.add_node("summarize_conversation", summarize_conversation)

workflow.add_edge(START, "conversation")
workflow.add_conditional_edges("conversation", should_continue, {
        "summarize_conversation": "summarize_conversation",
        END: END
    })
workflow.add_edge("summarize_conversation", "conversation")

memory = MemorySaver()

# graph = workflow.compile(checkpointer=memory)
graph = workflow.compile()
 
 