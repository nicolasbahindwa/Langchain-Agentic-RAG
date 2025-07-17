# from datetime import datetime
# from typing import List, Dict, TypedDict, Annotated
# from core.llm_manager import LLMManager, LLMResponse
# from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
# from langgraph.graph import StateGraph, END
# import operator

# class GraphState(TypedDict):
#     """
#     Represents the state of our graph.
    
#     Attributes:
#         messages: Complete conversation history
#         original_question: User's raw input question
#         rewritten_question: Enhanced/rewritten version of the question
#         context: Retrieved documents from vector store
#         answer: Final response to user
#     """
#     messages : Annotated[List[BaseMessage], operator.add]
#     original_question:str
#     rewritten_question:str
#     context: List[str] 
#     answer:str
    
# class RAGGraph:
#     def __init__(self, vector_store_path:str='vector_store_data'):
#         """
#         Initialize the RAG graph with dependencies
        
#         Args:
#             vector_store_path: Path to pre-built vector store
#         """
#         self.llm_manager = LLMManager()
#         self.vector_store = self._load_vector_store(vector_store_path)
#         self.graph = self._build_graph()
    
#     def _load_vector_store(self, path:str):
#         """Load the pre-built vector store"""
#         from langchain_community.vectorstores import FAISS
#         from langchain_huggingface import HuggingFaceEmbeddings
        
#         embeddings = HuggingFaceEmbeddings(
#             model_name="sentence-transformers/all-MiniLM-L6-v2"
#         )
#         return FAISS.load_local(
#             path,
#             embeddings,
#             allow_dangerous_deserialization=True
#         )
    
#     def rewrite_question_node(self, state:GraphState) -> Dict[str, str]:
#         """Node to rewrite user question for better retrieval"""
#         conversation_history = "\n".join(f"{msg.type}: {msg.content}" for msg in state["messages"] if isinstance(msg, (HumanMessage, AIMessage)))
        
#         rewrite_prompt = f"""
#             You are a query optimization assistant. Rewrite the user's question to make it 
#             more effective for document retrieval while preserving the original intent.
            
#             Consider the conversation history:
#             {conversation_history}
            
#             Original Question: {state['original_question']}
            
#             Rewritten Question:
#         """
        
#         try:
#             response: LLMResponse = self.llm_manager.generate(
#                 prompt=rewrite_prompt,
#                 system="You specialize in optimizing queries for information retrieval systems.",
#                 temperature=0.3,
#                 max_tokens=100
#             )
#             return {"rewritten_question": response.content.strip()}
#         except Exception as e:
#             print(f"Question rewrite failed: {e}")
             
#             return {"rewritten_question": state["original_question"]}
    
#     def _retrieve_context_node(self, state:GraphState)-> Dict[str, List[str]]:
#         """Node to retrieve relevant context using rewritten question"""
#         try:
#             docs = self.vector_store.similarity_search(
#                 state['rewritten_question'],
#                 k=4
#             )
#             context = [doc.page_content for doc in docs]
#             return {"context": context}
#         except Exception as e:
#             print(f"Retrieval failed: {e}")
#             return {"context": []}
#     def _generate_answer_node(self, state:GraphState)-> Dict[str, str]:
#         """Node to generate final answer using context and conversation history"""
#         if state["context"]:
#             context_str = "\n\n".join(state["context"])
#             rag_prompt = f"""
#                 Use the following context to answer the question. If you don't know the answer, 
#                 say you don't know. Keep answers concise (2-3 sentences max).
                
#                 Context:
#                 {context_str}
                
#                 Question: {state['original_question']}
                
#                 Answer:
#             """
#         else:
#             rag_prompt = f"""
#                 Answer the following question based on your general knowledge:
                
#                 Question: {state['original_question']}
                
#                 Answer:
#             """
            
#         try:
#             response: LLMResponse = self.llm_manager.generate(
#                 prompt=rag_prompt,
#                 temperature=0.7,
#                 max_tokens=300
#             )
            
#             return {
#                 "answer": response.content,
#                 "messages": [AIMessage(content=response.content)]
#             }
#         except Exception as e:
#             error_msg =  f"⚠️ Answer generation failed: {str(e)}"
#             return {
#                 "answer": error_msg,
#                 "messages": [AIMessage(content=error_msg)]
#             }
            
    
#     def _build_graph(self):
#         """Construct the LangGraph application"""
#         workflow = StateGraph(GraphState)
        
#         # add notes
#         workflow.add_node("rewrite_question", self.rewrite_question_node)
#         workflow.add_node("retrieve_context", self._retrieve_context_node)
#         workflow.add_node("generate_answer", self._generate_answer_node)
        
#         # define edges

#         workflow.set_entry_point("rewrite_question")
#         workflow.add_edge("rewrite_question", "retrieve_context")
#         workflow.add_edge("retrieve_context", "generate_answer")
#         workflow.add_edge("generate_answer", END)

#         return workflow.compile()
    
#     def chat(self, question:str, history:List[BaseMessage]=None)-> AIMessage:
#         """
#         Execute the RAG graph for a question
        
#         Args:
#             question: User's question
#             history: Conversation history (list of messages)
            
#         Returns:
#             AI response message
#         """
#         # initialize state
#         history = history or []
#         initial_state = {
#             "messages": history + [HumanMessage(content=question)],
#             "original_question": question,
#             "rewritten_question": "",
#             "context": [],
#             "answer": ""
#         }
        
#         # execute graph
#         final_state = self.graph.invoke(initial_state)
        
#         # return the AI response
#         return final_state["messages"][-1]
    
#     def start_chat_interface(self):
#         """Start interactive chat session using the graph"""
#         print("\n" + "="*50)
#         print("RAG Graph Chat Interface")
#         print("Type your message or 'exit' to quit")
#         print("="*50 + "\n")
        
#         conversation_history = []
        
#         while True:
#             try:
#                 # Get user input
#                 user_input = input("You: ")
                
#                 # Exit condition
#                 if user_input.lower() in ['exit', 'quit']:
#                     print("\nChat session ended.")
#                     break
                
#                 # Process through graph
#                 ai_response = self.chat(user_input, conversation_history)
                
#                 # Update history
#                 conversation_history.extend([
#                     HumanMessage(content=user_input),
#                     ai_response
#                 ])
                
#                 # Display response
#                 print(f"\nAssistant: {ai_response.content}\n")
                
#             except KeyboardInterrupt:
#                 print("\n\nChat session interrupted.")
#                 break
#             except Exception as e:
#                 print(f"Unexpected error: {e}")
# # class LanChainChat:
# #     def __init__(self, system_prompt:str= 'You are a helpful assustant, respond concisely.'):
# #         """
# #         Initialize the chat interface with LLM Manager
# #         """
# #         self.llm_manager = LLMManager()
# #         self.messages : List[Dict[str, str]] = [
# #             {"role": "system", "content": system_prompt}
# #         ]
# #         self.conversation_history = []
        
# #     def add_message(self, role:str, content:str):
# #         """
# #         Add a message to the conversation
# #         """
# #         self.messages.append({"role":role, "content": content})
# #         self.conversation_history.append({
# #             "timestamp": datetime.now().isoformat(),
# #             "role": role,
# #             "content":content
# #         })
    
#     # def generate_response(self, user_input:str) -> str:
#     #     """
#     #     Generate LLM response for user input handles context management and response formatting
#     #     """
#     #     try:
#     #         # Add user message to history
#     #         self.add_message("user", user_input)
            
#     #         # Generate response using LLM Manager
#     #         response: LLMResponse = self.llm_manager.chat(
#     #             messages=self.messages,
#     #             temperature=0.7,
#     #             max_tokens=500
#     #         )
            
#     #         # add assistant response to history
#     #         self.add_message("assistant", response.content)
#     #         return response.content
#     #     except Exception as e:
#     #         error_msg = f"⚠️ Error generating response: {str(e)}"
#     #         self.add_message("system", error_msg)
#     #         return error_msg
       
            
#     # def get_formatted_history(self)-> str:
#     #     """Get formatted conversation history"""
#     #     history_str = "conversation history"
#     #     for msg in self.conversation_history:
#     #         prefix = "🧠: " if msg["role"] == "assistant" else "👤: "
#     #         history_str += f"{prefix}{msg['content']}\n"
#     #     return history_str
    
#     # def start_chat(self):
#     #     """start interactive chat session"""
#     #     print("\n" + "="*5)
#     #     print("LangChain chat interface")
#     #     print("Type your message or 'exit' to quit")
#     #     print("="*50 + "\n")
        
#     #     while True:
#     #         try:
#     #             # get user input
#     #             user_input = input("You: ")
                
#     #             # exit condition
#     #             if user_input.lower() in ['exit', 'quit']:
#     #                 print("\nChat session ended.")
#     #                 break
                
#     #             response = self.generate_response(user_input)
#     #             print(f"\n assistant: {response}")
            
#     #         except KeyboardInterrupt as e:
#     #             print(f"cat session interupted {e}")
#     #         except Exception as e:
#     #             print(f"unexpected error: {e} ")
                
    
    
# # example usage

# if __name__ == '__main__':
#     # custom_prompt = (
#     #     "You are an expert technical assistant. "
#     #     "Provide accurate, concise answers to technical questions. "
#     #     "If unsure, say you don't know."
#     # )
#     # chat = LanChainChat(system_prompt=custom_prompt)
#     # chat.start_chat()
#     # print("\n :" + chat.get_formatted_history())
    
#     rag_app = RAGGraph(vector_store_path="./data_pipeline/vector_store_data")
    
#     rag_app.start_chat_interface()

import os
import logging
from datetime import datetime
from typing import List, Dict, TypedDict, Annotated, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from core.llm_manager import LLMManager, LLMResponse
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import operator

class GraphState(TypedDict):
    """State of the RAG graph"""
    messages: Annotated[List[BaseMessage], operator.add]
    original_question: str
    rewritten_question: str
    context: List[str] 
    answer: str

class DiagnosticRAGGraph:
    """Enhanced RAG Graph with debugging capabilities"""
    
    def __init__(self, vector_store_path: str = 'vector_store_data'):
        """Initialize with debugging"""
        self.vector_store_path = vector_store_path
        self.llm_manager = LLMManager()
        self.vector_store = None
        self.embeddings = None
        
        # Load vector store with diagnostics
        self._load_vector_store_with_diagnostics()
        self.graph = self._build_graph()
    
    def _load_vector_store_with_diagnostics(self):
        """Load vector store with comprehensive diagnostics"""
        try:
            # Check if vector store path exists
            if not os.path.exists(self.vector_store_path):
                logger.error(f"Vector store path does not exist: {self.vector_store_path}")
                raise FileNotFoundError(f"Vector store not found at {self.vector_store_path}")
            
            # Initialize embeddings
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
            
            # Load vector store
            self.vector_store = FAISS.load_local(
                self.vector_store_path,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            
            # Diagnostic information
            logger.info(f"✅ Vector store loaded successfully from: {self.vector_store_path}")
            logger.info(f"📊 Vector store contains {self.vector_store.index.ntotal} documents")
            logger.info(f"🔢 Embedding dimension: {self.vector_store.index.d}")
            
            # Test retrieval with sample query
            self._test_retrieval()
            
        except Exception as e:
            logger.error(f"❌ Failed to load vector store: {str(e)}")
            raise
    
    def _test_retrieval(self):
        """Test retrieval to ensure vector store is working"""
        try:
            # Test with a simple query
            test_results = self.vector_store.similarity_search("constitution", k=3)
            logger.info(f"🔍 Test retrieval returned {len(test_results)} documents")
            
            # Show sample content
            for i, doc in enumerate(test_results[:2]):
                content_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                logger.info(f"📄 Document {i+1}: {content_preview}")
                logger.info(f"📋 Metadata: {doc.metadata}")
                
        except Exception as e:
            logger.error(f"❌ Test retrieval failed: {str(e)}")
    
    def enhanced_similarity_search(self, query: str, k: int = 4) -> List[str]:
        """Enhanced similarity search with debugging"""
        try:
            logger.info(f"🔍 Searching for: '{query}'")
            
            # Try different search strategies
            docs = self.vector_store.similarity_search(query, k=k)
            
            if not docs:
                logger.warning(f"⚠️ No documents found for query: '{query}'")
                
                # Try broader search
                broader_query = " ".join(query.split()[:2])  # Use first 2 words
                docs = self.vector_store.similarity_search(broader_query, k=k)
                logger.info(f"🔍 Broader search with '{broader_query}' returned {len(docs)} documents")
            
            context = []
            for i, doc in enumerate(docs):
                logger.info(f"📄 Retrieved doc {i+1}: {doc.page_content[:100]}...")
                context.append(doc.page_content)
            
            return context
            
        except Exception as e:
            logger.error(f"❌ Similarity search failed: {str(e)}")
            return []
    
    def rewrite_question_node(self, state: GraphState) -> Dict[str, str]:
        """Enhanced question rewriting with fallback"""
        try:
            conversation_history = "\n".join(
                f"{msg.type}: {msg.content}" 
                for msg in state["messages"] 
                if isinstance(msg, (HumanMessage, AIMessage))
            )
            
            rewrite_prompt = f"""
            Rewrite this question to be more effective for document search.
            Keep the same language and preserve key terms.
            
            Conversation history:
            {conversation_history}
            
            Original question: {state['original_question']}
            
            Rewritten question (keep it concise):
            """
            
            response: LLMResponse = self.llm_manager.generate(
                prompt=rewrite_prompt,
                system="You optimize search queries while preserving meaning and language.",
                temperature=0.3,
                max_tokens=100
            )
            
            rewritten = response.content.strip()
            logger.info(f"🔄 Question rewritten: '{state['original_question']}' → '{rewritten}'")
            return {"rewritten_question": rewritten}
            
        except Exception as e:
            logger.error(f"❌ Question rewrite failed: {str(e)}")
            # Use original question as fallback
            return {"rewritten_question": state["original_question"]}
    
    def _retrieve_context_node(self, state: GraphState) -> Dict[str, List[str]]:
        """Enhanced context retrieval"""
        try:
            # First try with rewritten question
            context = self.enhanced_similarity_search(state['rewritten_question'], k=4)
            
            # If no results, try original question
            if not context:
                logger.info("🔄 Trying original question...")
                context = self.enhanced_similarity_search(state['original_question'], k=4)
            
            # If still no results, try keyword extraction
            if not context:
                logger.info("🔄 Trying keyword extraction...")
                keywords = self._extract_keywords(state['original_question'])
                for keyword in keywords:
                    context = self.enhanced_similarity_search(keyword, k=2)
                    if context:
                        break
            
            logger.info(f"📊 Retrieved {len(context)} context pieces")
            return {"context": context}
            
        except Exception as e:
            logger.error(f"❌ Context retrieval failed: {str(e)}")
            return {"context": []}
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract key terms from question"""
        import re
        
        # Remove common words and extract meaningful terms
        stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'est', 'que', 'quel', 'quelle'}
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords[:3]  # Return top 3 keywords
    
    def _generate_answer_node(self, state: GraphState) -> Dict[str, str]:
        """Enhanced answer generation with better fallbacks"""
        try:
            if state["context"]:
                context_str = "\n\n".join(state["context"])
                
                # Check if context seems relevant
                relevance_score = self._check_context_relevance(state['original_question'], context_str)
                logger.info(f"📊 Context relevance score: {relevance_score:.2f}")
                
                if relevance_score > 0.3:  # Threshold for relevance
                    rag_prompt = f"""
                    Based on the following context, answer the user's question in the same language as the question.
                    If the context doesn't contain enough information, say so clearly.
                    
                    Context:
                    {context_str}
                    
                    Question: {state['original_question']}
                    
                    Answer:
                    """
                else:
                    rag_prompt = f"""
                    The retrieved context does not seem directly relevant to the question.
                    
                    Question: {state['original_question']}
                    
                    Please respond that you don't have enough relevant information to answer this question.
                    Answer in the same language as the question.
                    """
            else:
                rag_prompt = f"""
                No relevant context was found in the knowledge base.
                
                Question: {state['original_question']}
                
                Please respond that you don't have information to answer this question.
                Answer in the same language as the question.
                """
            
            response: LLMResponse = self.llm_manager.generate(
                prompt=rag_prompt,
                system="You are a helpful assistant that answers based on provided context.",
                temperature=0.7,
                max_tokens=300
            )
            
            logger.info(f"✅ Generated answer: {response.content[:100]}...")
            
            return {
                "answer": response.content,
                "messages": [AIMessage(content=response.content)]
            }
            
        except Exception as e:
            error_msg = f"❌ Answer generation failed: {str(e)}"
            logger.error(error_msg)
            fallback_msg = "Je ne peux pas répondre à cette question en ce moment en raison d'un problème technique."
            
            return {
                "answer": fallback_msg,
                "messages": [AIMessage(content=fallback_msg)]
            }
    
    def _check_context_relevance(self, question: str, context: str) -> float:
        """Simple relevance check based on keyword overlap"""
        question_words = set(question.lower().split())
        context_words = set(context.lower().split())
        
        if not question_words:
            return 0.0
        
        overlap = len(question_words.intersection(context_words))
        return overlap / len(question_words)
    
    def _build_graph(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("rewrite_question", self.rewrite_question_node)
        workflow.add_node("retrieve_context", self._retrieve_context_node)
        workflow.add_node("generate_answer", self._generate_answer_node)
        
        # Define edges
        workflow.set_entry_point("rewrite_question")
        workflow.add_edge("rewrite_question", "retrieve_context")
        workflow.add_edge("retrieve_context", "generate_answer")
        workflow.add_edge("generate_answer", END)

        return workflow.compile()
    
    def chat(self, question: str, history: List[BaseMessage] = None) -> AIMessage:
        """Execute the RAG graph with debugging"""
        logger.info(f"🎯 Processing question: '{question}'")
        
        history = history or []
        initial_state = {
            "messages": history + [HumanMessage(content=question)],
            "original_question": question,
            "rewritten_question": "",
            "context": [],
            "answer": ""
        }
        
        # Execute graph
        final_state = self.graph.invoke(initial_state)
        
        return final_state["messages"][-1]
    
    def diagnose_system(self):
        """Run system diagnostics"""
        logger.info("🔧 Running system diagnostics...")
        
        # Check vector store
        logger.info(f"📁 Vector store path: {self.vector_store_path}")
        logger.info(f"📊 Vector store loaded: {self.vector_store is not None}")
        
        if self.vector_store:
            logger.info(f"📄 Number of documents: {self.vector_store.index.ntotal}")
            
            # Test with sample queries
            test_queries = [
                "constitution",
                "article", 
                "congo",
                "république démocratique"
            ]
            
            for query in test_queries:
                results = self.vector_store.similarity_search(query, k=2)
                logger.info(f"🔍 Query '{query}': {len(results)} results")
        
        # Check LLM
        try:
            test_response = self.llm_manager.generate(
                prompt="Test prompt",
                system="You are a test assistant.",
                temperature=0.5,
                max_tokens=10
            )
            logger.info("✅ LLM is working")
        except Exception as e:
            logger.error(f"❌ LLM test failed: {str(e)}")
    
    def start_chat_interface(self):
        """Start enhanced chat interface"""
        print("\n" + "="*50)
        print("🔧 DIAGNOSTIC RAG CHAT INTERFACE")
        print("Type your message or 'exit' to quit")
        print("Type 'diagnose' to run system diagnostics")
        print("="*50 + "\n")
        
        # Run initial diagnostics
        self.diagnose_system()
        
        conversation_history = []
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("\nChat session ended.")
                    break
                
                if user_input.lower() == 'diagnose':
                    self.diagnose_system()
                    continue
                
                if not user_input:
                    continue
                
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
                logger.error(f"❌ Unexpected error: {str(e)}")
                print(f"\n❌ Error: {str(e)}\n")

# Example usage
if __name__ == '__main__':
    # Update the path to match your vector store location
    vector_store_path = "./data_pipeline/vector_store_data"  # Adjust this path
    
    # Alternative paths to try
    alternative_paths = [
        "./vector_store_data",
        "vector_store_data",
        "./data_pipeline/vector_store_data"
    ]
    
    # Find the correct path
    actual_path = None
    for path in alternative_paths:
        if os.path.exists(path):
            actual_path = path
            break
    
    if actual_path:
        print(f"✅ Found vector store at: {actual_path}")
        rag_app = DiagnosticRAGGraph(vector_store_path=actual_path)
        rag_app.start_chat_interface()
    else:
        print("❌ Vector store not found. Please check the path.")
        print("Available paths to check:")
        for path in alternative_paths:
            print(f"  - {path}")