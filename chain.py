from datetime import datetime
from typing import List, Dict, TypedDict, Annotated
from core.llm_manager import LLMManager, LLMResponse
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
import operator

class GraphState(TypedDict):
    """
    Represents the state of our graph.
    
    Attributes:
        messages: Complete conversation history
        original_question: User's raw input question
        rewritten_question: Enhanced/rewritten version of the question
        context: Retrieved documents from vector store
        answer: Final response to user
    """
    messages : Annotated[List[BaseMessage], operator.add]
    original_question:str
    rewritten_question:str
    context: List[str] 
    answer:str
    
class RAGGraph:
    def __init__(self, vector_store_path:str='vector_store_data'):
        """
        Initialize the RAG graph with dependencies
        
        Args:
            vector_store_path: Path to pre-built vector store
        """
        self.llm_manager = LLMManager()
        self.vector_store = self._load_vector_store(vector_store_path)
        self.graph = self._build_graph()
    
    def _load_vector_store(self, path:str):
        """Load the pre-built vector store"""
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        return FAISS.load_local(
            path,
            embeddings,
            allow_dangerous_deserialization=True
        )
    
    def rewrite_question_node(self, state:GraphState) -> Dict[str, str]:
        """Node to rewrite user question for better retrieval"""
        conversation_history = "\n".join(f"{msg.type}: {msg.content}" for msg in state["messages"] if isinstance(msg, (HumanMessage, AIMessage)))
        
        rewrite_prompt = f"""
            You are a query optimization assistant. Rewrite the user's question to make it 
            more effective for document retrieval while preserving the original intent.
            
            Consider the conversation history:
            {conversation_history}
            
            Original Question: {state['original_question']}
            
            Rewritten Question:
        """
        
        try:
            response: LLMResponse = self.llm_manager.generate(
                prompt=rewrite_prompt,
                system="You specialize in optimizing queries for information retrieval systems.",
                temperature=0.3,
                max_tokens=100
            )
            return {"rewritten_question": response.content.strip()}
        except Exception as e:
            print(f"Question rewrite failed: {e}")
             
            return {"rewritten_question": state["original_question"]}
    
    def _retrieve_context_node(self, state:GraphState)-> Dict[str, List[str]]:
        """Node to retrieve relevant context using rewritten question"""
        try:
            docs = self.vector_store.similarity_search(
                state['rewritten_question'],
                k=4
            )
            context = [doc.page_content for doc in docs]
            return {"context": context}
        except Exception as e:
            print(f"Retrieval failed: {e}")
            return {"context": []}
    def _generate_answer_node(self, state:GraphState)-> Dict[str, str]:
        """Node to generate final answer using context and conversation history"""
        if state["context"]:
            context_str = "\n\n".join(state["context"])
            rag_prompt = f"""
                Use the following context to answer the question. If you don't know the answer, 
                say you don't know. Keep answers concise (2-3 sentences max).
                
                Context:
                {context_str}
                
                Question: {state['original_question']}
                
                Answer:
            """
        else:
            rag_prompt = f"""
                Answer the following question based on your general knowledge:
                
                Question: {state['original_question']}
                
                Answer:
            """
            
        try:
            response: LLMResponse = self.llm_manager.generate(
                prompt=rag_prompt,
                temperature=0.7,
                max_tokens=300
            )
            
            return {
                "answer": response.content,
                "messages": [AIMessage(content=response.content)]
            }
        except Exception as e:
            error_msg =  f"⚠️ Answer generation failed: {str(e)}"
            return {
                "answer": error_msg,
                "messages": [AIMessage(content=error_msg)]
            }
            
    
    def _build_graph(self):
        """Construct the LangGraph application"""
        workflow = StateGraph(GraphState)
        
        # add notes
        workflow.add_node("rewrite_question", self.rewrite_question_node)
        workflow.add_node("retrieve_context", self._retrieve_context_node)
        workflow.add_node("generate_answer", self._generate_answer_node)
        
        # define edges

        workflow.set_entry_point("rewrite_question")
        workflow.add_edge("rewrite_question", "retrieve_context")
        workflow.add_edge("retrieve_context", "generate_answer")
        workflow.add_edge("generate_answer", END)

        return workflow.compile()
    
    def chat(self, question:str, history:List[BaseMessage]=None)-> AIMessage:
        """
        Execute the RAG graph for a question
        
        Args:
            question: User's question
            history: Conversation history (list of messages)
            
        Returns:
            AI response message
        """
        # initialize state
        history = history or []
        initial_state = {
            "messages": history + [HumanMessage(content=question)],
            "original_question": question,
            "rewritten_question": "",
            "context": [],
            "answer": ""
        }
        
        # execute graph
        final_state = self.graph.invoke(initial_state)
        
        # return the AI response
        return final_state["messages"][-1]
    
    def start_chat_interface(self):
        """Start interactive chat session using the graph"""
        print("\n" + "="*50)
        print("RAG Graph Chat Interface")
        print("Type your message or 'exit' to quit")
        print("="*50 + "\n")
        
        conversation_history = []
        
        while True:
            try:
                # Get user input
                user_input = input("You: ")
                
                # Exit condition
                if user_input.lower() in ['exit', 'quit']:
                    print("\nChat session ended.")
                    break
                
                # Process through graph
                ai_response = self.chat(user_input, conversation_history)
                
                # Update history
                conversation_history.extend([
                    HumanMessage(content=user_input),
                    ai_response
                ])
                
                # Display response
                print(f"\nAssistant: {ai_response.content}\n")
                
            except KeyboardInterrupt:
                print("\n\nChat session interrupted.")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
# class LanChainChat:
#     def __init__(self, system_prompt:str= 'You are a helpful assustant, respond concisely.'):
#         """
#         Initialize the chat interface with LLM Manager
#         """
#         self.llm_manager = LLMManager()
#         self.messages : List[Dict[str, str]] = [
#             {"role": "system", "content": system_prompt}
#         ]
#         self.conversation_history = []
        
#     def add_message(self, role:str, content:str):
#         """
#         Add a message to the conversation
#         """
#         self.messages.append({"role":role, "content": content})
#         self.conversation_history.append({
#             "timestamp": datetime.now().isoformat(),
#             "role": role,
#             "content":content
#         })
    
    # def generate_response(self, user_input:str) -> str:
    #     """
    #     Generate LLM response for user input handles context management and response formatting
    #     """
    #     try:
    #         # Add user message to history
    #         self.add_message("user", user_input)
            
    #         # Generate response using LLM Manager
    #         response: LLMResponse = self.llm_manager.chat(
    #             messages=self.messages,
    #             temperature=0.7,
    #             max_tokens=500
    #         )
            
    #         # add assistant response to history
    #         self.add_message("assistant", response.content)
    #         return response.content
    #     except Exception as e:
    #         error_msg = f"⚠️ Error generating response: {str(e)}"
    #         self.add_message("system", error_msg)
    #         return error_msg
       
            
    # def get_formatted_history(self)-> str:
    #     """Get formatted conversation history"""
    #     history_str = "conversation history"
    #     for msg in self.conversation_history:
    #         prefix = "🧠: " if msg["role"] == "assistant" else "👤: "
    #         history_str += f"{prefix}{msg['content']}\n"
    #     return history_str
    
    # def start_chat(self):
    #     """start interactive chat session"""
    #     print("\n" + "="*5)
    #     print("LangChain chat interface")
    #     print("Type your message or 'exit' to quit")
    #     print("="*50 + "\n")
        
    #     while True:
    #         try:
    #             # get user input
    #             user_input = input("You: ")
                
    #             # exit condition
    #             if user_input.lower() in ['exit', 'quit']:
    #                 print("\nChat session ended.")
    #                 break
                
    #             response = self.generate_response(user_input)
    #             print(f"\n assistant: {response}")
            
    #         except KeyboardInterrupt as e:
    #             print(f"cat session interupted {e}")
    #         except Exception as e:
    #             print(f"unexpected error: {e} ")
                
    
    
# example usage

if __name__ == '__main__':
    # custom_prompt = (
    #     "You are an expert technical assistant. "
    #     "Provide accurate, concise answers to technical questions. "
    #     "If unsure, say you don't know."
    # )
    # chat = LanChainChat(system_prompt=custom_prompt)
    # chat.start_chat()
    # print("\n :" + chat.get_formatted_history())
    
    rag_app = RAGGraph(vector_store_path="./data_pipeline/vector_store_data")
    
    rag_app.start_chat_interface()

