from typing import List, Dict
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from core.llm_manager import LLMManager, LLMResponse, LLMProvider, LLMError
from utils.logger import setup_logging

class SimpleRAG:
    """Agentic RAG system with Hugging Face embeddings - Fixed LLMManager integration"""
    
    def __init__(self, llm_manager: LLMManager):
        self.llm_manager = llm_manager
        self.logger = setup_logging("SimpleRAG")
        self.vector_store = None
        self.retriever = None
        
        # Initialize text splitter and embeddings
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # Use Hugging Face embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        
        self.logger.info("RAG system initialized with Hugging Face embeddings")

    def load_documents(self, documents: List[Document]):
        """Load and index documents for retrieval"""
        if not documents:
            self.logger.warning("No documents provided for indexing")
            return
            
        self.logger.info(f"Processing {len(documents)} documents...")
        
        # Split documents into chunks
        chunks = self.text_splitter.split_documents(documents)
        self.logger.info(f"Split into {len(chunks)} text chunks")
        
        # Create vector store
        self.vector_store = FAISS.from_documents(chunks, self.embeddings)
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
        self.logger.info("Document indexing complete")

    def retrieve_context(self, query: str) -> str:
        """Retrieve relevant context for a query"""
        if not self.retriever:
            self.logger.error("Retriever not initialized - load documents first")
            return ""
            
        docs = self.retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        self.logger.debug(f"Retrieved {len(docs)} context documents")
        return context

    def generate_response(self, query: str, chat_history: List[Dict[str, str]] = None) -> LLMResponse:
        """Generate response using RAG pattern - Fixed system message handling"""
        # Retrieve relevant context
        context = self.retrieve_context(query)
        
        # Build system prompt with instructions
        system_prompt = (
            "You are a helpful assistant. Use the provided context to answer questions. "
            "If the context doesn't contain the answer, say you don't know. "
            "When possible, include citations from the context.\n\n"
            f"Context:\n{context}"
        )
        
        # Prepare message history - include system prompt as first message
        messages = [{"role": "system", "content": system_prompt}]
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": query})
        
        # Generate response using LLM Manager
        try:
            response = self.llm_manager.chat(
                messages=messages,
                temperature=0.3,  # Lower temp for factual accuracy
                provider=LLMProvider.OLLAMA  # Prefer local model
            )
            return response
        except LLMError as e:
            self.logger.error(f"RAG generation failed: {e}")
            return LLMResponse(
                content="I encountered an error processing your request",
                provider="system",
                model="error"
            )

    def save_index(self, path: str):
        """Save the vector index to disk"""
        if self.vector_store:
            self.vector_store.save_local(path)
            self.logger.info(f"Saved vector index to {path}")
        else:
            self.logger.warning("No vector store to save")

    def load_index(self, path: str):
        """Load vector index from disk"""
        try:
            self.vector_store = FAISS.load_local(path, self.embeddings)
            self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
            self.logger.info(f"Loaded vector index from {path}")
        except Exception as e:
            self.logger.error(f"Failed to load index: {e}")

# Example usage
if __name__ == "__main__":
    # Initialize components
    manager = LLMManager()
    rag = SimpleRAG(manager)
    
    # Option 1: Load from documents
    documents = [
        Document(page_content="LangChain is a framework for developing LLM applications."),
        Document(page_content="RAG stands for Retrieval-Augmented Generation."),
        Document(page_content="Hugging Face provides state-of-the-art NLP models.")
    ]
    rag.load_documents(documents)
    
    # Chat loop
    chat_history = []
    print("RAG System (Fixed) - Type 'exit' to quit\n")
    
    while True:
        query = input("You: ")
        if query.lower() in ['exit', 'quit']:
            break
            
        # Generate response
        response = rag.generate_response(query, chat_history)
        
        # Update chat history (don't include system prompt in history)
        chat_history.append({"role": "user", "content": query})
        chat_history.append({"role": "assistant", "content": response.content})
        
        print(f"\nAssistant ({response.provider}): {response.content}\n")
    
    # Save index for future use
    rag.save_index("my_vector_index")