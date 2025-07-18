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



from datetime import datetime
from typing import List, Dict, TypedDict, Annotated, Optional
from pathlib import Path
import os
from core.llm_manager import LLMManager, LLMResponse
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
import operator
import logging

# Import the enhanced vector store classes
from data_pipeline.vector_store import EnhancedVectorStore, VectorStoreConfig, SmartTextSplitter
from core.config import config  # Import your existing config

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
    messages: Annotated[List[BaseMessage], operator.add]
    original_question: str
    rewritten_question: str
    context: List[str] 
    answer: str

class RAGGraph:
    def __init__(self, use_config: bool = True):
        """
        Initialize the RAG graph with enhanced vector store
        
        Args:
            use_config: Whether to use the global config system
        """
        if use_config:
            # Use global configuration
            self.vector_store_path = config.vector_store.path
            self.documents_path = config.rag.documents_path
            self.rag_config = config.rag
            self.vector_config = config.get_rag_vector_store_config()
        else:
            # Fallback to defaults if config not available
            self.vector_store_path = 'data/vector_store'
            self.documents_path = 'documents'
            self.rag_config = None
            self.vector_config = VectorStoreConfig()
        
        # Initialize components
        self.llm_manager = LLMManager()
        self.logger = logging.getLogger(__name__)
        
        # Initialize or load vector store
        self.enhanced_vector_store = self._initialize_vector_store()
        self.graph = self._build_graph()
    
    def _initialize_vector_store(self) -> EnhancedVectorStore:
        """Initialize or load the enhanced vector store"""
        vector_store_exists = self._check_vector_store_exists()
        
        if vector_store_exists:
            self.logger.info(f"Loading existing vector store from {self.vector_store_path}")
            return self._load_existing_vector_store()
        else:
            self.logger.info(f"Creating new vector store at {self.vector_store_path}")
            return self._create_new_vector_store()
    
    def _check_vector_store_exists(self) -> bool:
        """Check if vector store files exist"""
        store_path = Path(self.vector_store_path)
        
        # Check for FAISS index files
        index_file = store_path / "index.faiss"
        pkl_file = store_path / "index.pkl"
        
        return index_file.exists() and pkl_file.exists()
    
    def _load_existing_vector_store(self) -> EnhancedVectorStore:
        """Load existing vector store using EnhancedVectorStore"""
        try:
            return EnhancedVectorStore.load_store(self.vector_store_path, self.vector_config)
        except Exception as e:
            self.logger.error(f"Failed to load existing vector store: {e}")
            self.logger.info("Attempting to create new vector store...")
            return self._create_new_vector_store()
    
    def _create_new_vector_store(self) -> EnhancedVectorStore:
        """Create new vector store from documents"""
        if not self.documents_path:
            raise ValueError(
                "documents_path must be provided to create a new vector store. "
                "Either provide documents_path or ensure vector store exists at the specified path."
            )
        
        documents_dir = Path(self.documents_path)
        if not documents_dir.exists():
            raise ValueError(f"Documents directory does not exist: {self.documents_path}")
        
        # Load and process documents
        documents = self._load_documents_from_directory(documents_dir)
        
        if not documents:
            raise ValueError(f"No documents found in {self.documents_path}")
        
        # Create enhanced vector store
        enhanced_store = EnhancedVectorStore(self.vector_config)
        
        # Process documents and create vector store
        enhanced_store.process_documents(documents)
        
        # Save the vector store
        os.makedirs(self.vector_store_path, exist_ok=True)
        enhanced_store.save_store(self.vector_store_path, include_metadata=True)
        
        self.logger.info(f"Created and saved new vector store with {len(documents)} documents")
        return enhanced_store
    
    def _load_documents_from_directory(self, documents_dir: Path) -> List[Document]:
        """Load and split markdown documents from directory (converted by DocumentProcessor)"""
        documents = []
        text_splitter = SmartTextSplitter(self.vector_config)
        
        # Only look for markdown files since they're already converted
        md_files = list(documents_dir.rglob('*.md'))
        
        if not md_files:
            self.logger.warning(f"No .md files found in {documents_dir}")
            self.logger.info("Tip: Use DocumentProcessor to convert your documents to markdown first")
            return documents
        
        self.logger.info(f"Found {len(md_files)} markdown file(s) to process")
        
        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if content.strip():
                    # Use smart text splitter
                    file_documents = text_splitter.split_by_sections(
                        content, 
                        source=str(md_file.relative_to(documents_dir))
                    )
                    documents.extend(file_documents)
                    self.logger.info(f"Loaded {len(file_documents)} chunks from {md_file.name}")
                else:
                    self.logger.warning(f"Empty file: {md_file.name}")
            
            except Exception as e:
                self.logger.warning(f"Failed to load {md_file}: {e}")
        
        self.logger.info(f"Total: {len(documents)} document chunks loaded")
        return documents
    
    def rewrite_question_node(self, state: GraphState) -> Dict[str, str]:
        """Node to rewrite user question for better retrieval"""
        conversation_history = "\n".join(
            f"{msg.type}: {msg.content}" 
            for msg in state["messages"] 
            if isinstance(msg, (HumanMessage, AIMessage))
        )
        
        rewrite_prompt = f"""
            You are a query optimization assistant. Rewrite the user's question to make it 
            more effective for document retrieval while preserving the original intent.
            
            Consider the conversation history:
            {conversation_history}
            
            Original Question: {state['original_question']}
            
            Rewritten Question:
        """
        
        try:
            # Get temperature and max_tokens from config
            temperature = self.rag_config.rewrite_temperature if self.rag_config else 0.3
            max_tokens = self.rag_config.rewrite_max_tokens if self.rag_config else 100
            
            response: LLMResponse = self.llm_manager.generate(
                prompt=rewrite_prompt,
                system="You specialize in optimizing queries for information retrieval systems.",
                temperature=temperature,
                max_tokens=max_tokens
            )
            return {"rewritten_question": response.content.strip()}
        except Exception as e:
            self.logger.error(f"Question rewrite failed: {e}")
            return {"rewritten_question": state["original_question"]}
    
    def _retrieve_context_node(self, state: GraphState) -> Dict[str, List[str]]:
        """Node to retrieve relevant context using enhanced vector store"""
        try:
            # Get retrieval parameters from config
            k = self.rag_config.retrieval_k if self.rag_config else 4
            similarity_threshold = self.vector_config.similarity_threshold
            
            # Use enhanced search with configurable parameters
            results = self.enhanced_vector_store.enhanced_search(
                query=state['rewritten_question'],
                k=k,
                similarity_threshold=similarity_threshold
            )
            
            # Extract content and add metadata information
            context = []
            for doc, score in results:
                content = doc.page_content
                source = doc.metadata.get('source', 'Unknown')
                section = doc.metadata.get('section_title', '')
                
                # Add metadata context for better understanding
                context_item = f"[Source: {source}]"
                if section and section != 'Introduction':
                    context_item += f" [Section: {section}]"
                context_item += f"\n{content}"
                
                context.append(context_item)
            
            self.logger.info(f"Retrieved {len(context)} relevant documents")
            return {"context": context}
            
        except Exception as e:
            self.logger.error(f"Retrieval failed: {e}")
            return {"context": []}
    
    def _generate_answer_node(self, state: GraphState) -> Dict[str, str]:
        """Node to generate final answer using context and conversation history"""
        if state["context"]:
            context_str = "\n\n".join(state["context"])
            rag_prompt = f"""
                Use the following context to answer the question. The context includes source 
                information and section titles to help you provide accurate responses.
                
                If you don't know the answer based on the provided context, say you don't know. 
                Keep answers concise but informative (2-4 sentences).
                
                Context:
                {context_str}
                
                Question: {state['original_question']}
                
                Answer:
            """
        else:
            rag_prompt = f"""
                No relevant context was found for this question. Answer based on your 
                general knowledge, but mention that the response is not based on the 
                provided documents.
                
                Question: {state['original_question']}
                
                Answer:
            """
            
        try:
            # Get temperature and max_tokens from config
            temperature = self.rag_config.answer_temperature if self.rag_config else 0.7
            max_tokens = self.rag_config.answer_max_tokens if self.rag_config else 300
            
            response: LLMResponse = self.llm_manager.generate(
                prompt=rag_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                "answer": response.content,
                "messages": [AIMessage(content=response.content)]
            }
        except Exception as e:
            error_msg = f"⚠️ Answer generation failed: {str(e)}"
            return {
                "answer": error_msg,
                "messages": [AIMessage(content=error_msg)]
            }
    
    def _build_graph(self):
        """Construct the LangGraph application"""
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
        """
        Execute the RAG graph for a question
        
        Args:
            question: User's question
            history: Conversation history (list of messages)
            
        Returns:
            AI response message
        """
        # Initialize state
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
        
        # Return the AI response
        return final_state["messages"][-1]
    
    def get_vector_store_stats(self) -> Dict:
        """Get statistics about the vector store"""
        return self.enhanced_vector_store.get_store_statistics()
    
    def start_chat_interface(self):
        """Start interactive chat session using the graph"""
        print("\n" + "="*50)
        print("Enhanced RAG Graph Chat Interface")
        print("Type your message or 'exit' to quit")
        print("Type 'stats' to see vector store statistics")
        print("="*50 + "\n")
        
        # Display vector store info
        stats = self.get_vector_store_stats()
        if stats:
            print(f"Vector Store: {stats.get('total_vectors', 'Unknown')} vectors loaded")
            print(f"Embedding dimension: {stats.get('embedding_dimension', 'Unknown')}")
            print()
        
        conversation_history = []
        
        while True:
            try:
                # Get user input
                user_input = input("You: ")
                
                # Exit condition
                if user_input.lower() in ['exit', 'quit']:
                    print("\nChat session ended.")
                    break
                
                # Show stats
                if user_input.lower() == 'stats':
                    stats = self.get_vector_store_stats()
                    print("\nVector Store Statistics:")
                    for key, value in stats.items():
                        print(f"  {key}: {value}")
                    print()
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
                print(f"Unexpected error: {e}")

# Example usage
if __name__ == '__main__':
    # Initialize RAG app using global config
    # The config system handles all the settings automatically
    rag_app = RAGGraph(use_config=True)
    
    # Start chat interface
    rag_app.start_chat_interface()

