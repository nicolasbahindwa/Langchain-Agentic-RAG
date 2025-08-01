# vector_store.py
"""
Vector store module using LangChain's Qdrant integration
"""
import logging
from typing import List, Dict, Any, Optional

from langchain_core.documents import Document
from langchain_community.vectorstores import Qdrant
from langchain_openai import OpenAIEmbeddings
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_openai import OpenAI

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages vector store operations using LangChain's Qdrant integration"""
    
    def __init__(self, 
                 collection_name: str = "document_store",
                 embeddings_model: str = "text-embedding-ada-002",
                 location: str = ":memory:",  # In-memory for now, can be changed to URL later
                 **qdrant_kwargs):
        """
        Initialize vector store manager
        
        Args:
            collection_name: Name of the Qdrant collection
            embeddings_model: OpenAI embeddings model to use
            location: Qdrant location (:memory: for in-memory, URL for remote)
            **qdrant_kwargs: Additional Qdrant configuration
        """
        self.collection_name = collection_name
        self.location = location
        self.qdrant_kwargs = qdrant_kwargs
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(model=embeddings_model)
        
        # Vector store will be initialized when first used
        self.vectorstore: Optional[Qdrant] = None
        
        # Track processed files to avoid duplicates
        self.processed_hashes: set = set()
    
    def _ensure_vectorstore(self) -> Qdrant:
        """Ensure vector store is initialized"""
        if self.vectorstore is None:
            # Create empty vector store first
            self.vectorstore = Qdrant.from_documents(
                documents=[],  # Start with empty documents
                embedding=self.embeddings,
                location=self.location,
                collection_name=self.collection_name,
                **self.qdrant_kwargs
            )
            logger.info(f"Initialized vector store with collection: {self.collection_name}")
        
        return self.vectorstore
    
    def add_documents(self, documents: List[Document]) -> bool:
        """
        Add documents to the vector store
        
        Args:
            documents: List of documents to add
            
        Returns:
            True if successful, False otherwise
        """
        if not documents:
            logger.warning("No documents provided to add")
            return False
        
        try:
            vectorstore = self._ensure_vectorstore()
            
            # Filter out documents we've already processed
            new_documents = []
            for doc in documents:
                file_hash = doc.metadata.get('file_hash', '')
                if file_hash and file_hash not in self.processed_hashes:
                    new_documents.append(doc)
                    self.processed_hashes.add(file_hash)
                elif file_hash:
                    logger.info(f"Skipping duplicate document with hash: {file_hash}")
            
            if not new_documents:
                logger.info("All documents already processed, skipping")
                return True
            
            # Add new documents
            vectorstore.add_documents(new_documents)
            logger.info(f"Added {len(new_documents)} documents to vector store")
            return True
            
        except Exception as e:
            logger.error(f"Error adding documents to vector store: {str(e)}")
            return False
    
    def create_from_documents(self, documents: List[Document]) -> bool:
        """
        Create or recreate vector store from documents
        
        Args:
            documents: List of documents to create store from
            
        Returns:
            True if successful, False otherwise
        """
        if not documents:
            logger.warning("No documents provided to create vector store")
            return False
        
        try:
            self.vectorstore = Qdrant.from_documents(
                documents=documents,
                embedding=self.embeddings,
                location=self.location,
                collection_name=self.collection_name,
                **self.qdrant_kwargs
            )
            
            # Update processed hashes
            self.processed_hashes.clear()
            for doc in documents:
                file_hash = doc.metadata.get('file_hash', '')
                if file_hash:
                    self.processed_hashes.add(file_hash)
            
            logger.info(f"Created vector store with {len(documents)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            return False
    
    def similarity_search(self, 
                         query: str, 
                         k: int = 4, 
                         filter: Optional[Dict] = None) -> List[Document]:
        """
        Perform similarity search
        
        Args:
            query: Search query
            k: Number of documents to return
            filter: Optional metadata filter
            
        Returns:
            List of similar documents
        """
        try:
            vectorstore = self._ensure_vectorstore()
            results = vectorstore.similarity_search(query, k=k, filter=filter)
            logger.info(f"Found {len(results)} results for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error performing similarity search: {str(e)}")
            return []
    
    def similarity_search_with_score(self, 
                                   query: str, 
                                   k: int = 4,
                                   filter: Optional[Dict] = None) -> List[tuple]:
        """
        Perform similarity search with scores
        
        Args:
            query: Search query
            k: Number of documents to return
            filter: Optional metadata filter
            
        Returns:
            List of (document, score) tuples
        """
        try:
            vectorstore = self._ensure_vectorstore()
            results = vectorstore.similarity_search_with_score(query, k=k, filter=filter)
            logger.info(f"Found {len(results)} results with scores for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error performing similarity search with scores: {str(e)}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        try:
            vectorstore = self._ensure_vectorstore()
            
            return {
                'collection_name': self.collection_name,
                'location': self.location,
                'processed_hashes_count': len(self.processed_hashes),
                'embeddings_model': self.embeddings.model,
                'is_initialized': self.vectorstore is not None
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return {}


class SelfQueryRetrieverManager:
    """Manages self-query retriever for advanced querying"""
    
    def __init__(self, 
                 vector_store_manager: VectorStoreManager,
                 llm_temperature: float = 0,
                 enable_limit: bool = True):
        """
        Initialize self-query retriever manager
        
        Args:
            vector_store_manager: Vector store manager instance
            llm_temperature: Temperature for LLM
            enable_limit: Whether to enable limit in queries
        """
        self.vector_store_manager = vector_store_manager
        self.llm = OpenAI(temperature=llm_temperature)
        self.enable_limit = enable_limit
        
        # Default metadata field info for documents
        self.metadata_field_info = [
            AttributeInfo(
                name="source",
                description="The source file path of the document",
                type="string",
            ),
            AttributeInfo(
                name="file_name",
                description="The name of the source file",
                type="string",
            ),
            AttributeInfo(
                name="file_extension",
                description="The file extension (e.g., .pdf, .txt)",
                type="string",
            ),
            AttributeInfo(
                name="file_size",
                description="The size of the file in bytes",
                type="integer",
            ),
            AttributeInfo(
                name="processed_at",
                description="When the document was processed",
                type="string",
            ),
        ]
        
        self.document_content_description = "Document content from various file types including text, PDF, CSV, and Word documents"
        
        self._retriever: Optional[SelfQueryRetriever] = None
    
    def add_metadata_field(self, 
                          name: str, 
                          description: str, 
                          field_type: str):
        """Add a metadata field for querying"""
        self.metadata_field_info.append(
            AttributeInfo(name=name, description=description, type=field_type)
        )
        self._retriever = None  # Reset retriever to pick up new field
    
    def _ensure_retriever(self) -> SelfQueryRetriever:
        """Ensure self-query retriever is initialized"""
        if self._retriever is None:
            vectorstore = self.vector_store_manager._ensure_vectorstore()
            
            self._retriever = SelfQueryRetriever.from_llm(
                llm=self.llm,
                vectorstore=vectorstore,
                document_contents=self.document_content_description,
                metadata_field_info=self.metadata_field_info,
                enable_limit=self.enable_limit,
                verbose=True
            )
            
            logger.info("Initialized self-query retriever")
        
        return self._retriever
    
    def query(self, query: str) -> List[Document]:
        """
        Perform self-query retrieval
        
        Args:
            query: Natural language query
            
        Returns:
            List of relevant documents
        """
        try:
            retriever = self._ensure_retriever()
            results = retriever.invoke(query)
            logger.info(f"Self-query returned {len(results)} results for: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error performing self-query: {str(e)}")
            return []