# pipeline_orchestrator.py
"""
Main pipeline orchestrator that coordinates all components
"""
import logging
import os
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from document_processor import DocumentProcessor
from vector_store import VectorStoreManager, SelfQueryRetrieverManager
from file_monitor import FileMonitor

logger = logging.getLogger(__name__)


class DataExtractionPipeline:
    """Main data extraction pipeline that coordinates all components"""
    
    def __init__(self,
                 watch_paths: List[str],
                 collection_name: str = "document_store",
                 embeddings_model: str = "text-embedding-ada-002",
                 qdrant_location: str = ":memory:",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 debounce_seconds: int = 2,
                 recursive: bool = True,
                 supported_extensions: Optional[Set[str]] = None,
                 enable_self_query: bool = True,
                 **qdrant_kwargs):
        """
        Initialize the data extraction pipeline
        
        Args:
            watch_paths: List of directories to monitor
            collection_name: Qdrant collection name
            embeddings_model: OpenAI embeddings model
            qdrant_location: Qdrant location (:memory: or URL)
            chunk_size: Document chunk size
            chunk_overlap: Chunk overlap size
            debounce_seconds: File change debounce period
            recursive: Monitor subdirectories
            supported_extensions: Supported file extensions
            enable_self_query: Enable self-query retriever
            **qdrant_kwargs: Additional Qdrant parameters
        """
        self.watch_paths = watch_paths
        self.enable_self_query = enable_self_query
        
        # Initialize document processor
        self.document_processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            supported_extensions=supported_extensions
        )
        
        # Initialize vector store manager
        self.vector_store_manager = VectorStoreManager(
            collection_name=collection_name,
            embeddings_model=embeddings_model,
            location=qdrant_location,
            **qdrant_kwargs
        )
        
        # Initialize self-query retriever if enabled
        self.self_query_manager = None
        if enable_self_query:
            self.self_query_manager = SelfQueryRetrieverManager(
                vector_store_manager=self.vector_store_manager
            )
        
        # Initialize file monitor
        self.file_monitor = FileMonitor(
            watch_paths=watch_paths,
            on_file_created=self._handle_file_created,
            on_file_modified=self._handle_file_modified,
            on_file_deleted=self._handle_file_deleted,
            recursive=recursive,
            debounce_seconds=debounce_seconds,
            supported_extensions=supported_extensions or self.document_processor.supported_extensions
        )
        
        # Statistics
        self.stats = {
            'files_processed': 0,
            'documents_added': 0,
            'processing_errors': 0,
            'last_error': None
        }
    
    def _handle_file_created(self, file_path: str):
        """Handle file creation event"""
        logger.info(f"File created: {file_path}")
        self._process_file(file_path, event_type='created')
    
    def _handle_file_modified(self, file_path: str):
        """Handle file modification event"""
        logger.info(f"File modified: {file_path}")
        self._process_file(file_path, event_type='modified')
    
    def _handle_file_deleted(self, file_path: str):
        """Handle file deletion event"""
        logger.info(f"File deleted: {file_path}")
        # For now, we don't remove documents from vector store on file deletion
        # This could be implemented by tracking file_hash to document mapping
        logger.info(f"File deletion handled (document remains in vector store): {file_path}")
    
    def _process_file(self, file_path: str, event_type: str = 'unknown'):
        """Process a single file through the pipeline"""
        try:
            logger.info(f"Processing file ({event_type}): {file_path}")
            
            # Process file into document chunks
            chunks = self.document_processor.process_file(file_path)
            
            if not chunks:
                logger.warning(f"No chunks generated from file: {file_path}")
                return
            
            # Add documents to vector store
            success = self.vector_store_manager.add_documents(chunks)
            
            if success:
                self.stats['files_processed'] += 1
                self.stats['documents_added'] += len(chunks)
                logger.info(f"Successfully processed {file_path}: {len(chunks)} chunks added")
            else:
                self.stats['processing_errors'] += 1
                logger.error(f"Failed to add documents from {file_path} to vector store")
                
        except Exception as e:
            error_msg = f"Error processing file {file_path}: {str(e)}"
            logger.error(error_msg)
            self.stats['processing_errors'] += 1
            self.stats['last_error'] = error_msg
    
    def process_existing_files(self):
        """Process all existing files in watch directories"""
        logger.info("Processing existing files...")
        
        existing_files = self.file_monitor.scan_existing_files()
        
        for file_path in existing_files:
            self._process_file(file_path, event_type='existing')
        
        logger.info(f"Finished processing {len(existing_files)} existing files")
    
    def start_monitoring(self, process_existing: bool = True):
        """
        Start the file monitoring and processing pipeline
        
        Args:
            process_existing: Whether to process existing files first
        """
        logger.info("Starting data extraction pipeline...")
        
        # Process existing files if requested
        if process_existing:
            self.process_existing_files()
        
        # Start file monitoring
        self.file_monitor.start_monitoring()
        logger.info("Pipeline started successfully")
    
    def stop_monitoring(self):
        """Stop the file monitoring"""
        self.file_monitor.stop_monitoring()
        logger.info("Pipeline stopped")
    
    def run_forever(self, process_existing: bool = True, process_interval: float = 1.0):
        """
        Run the pipeline indefinitely
        
        Args:
            process_existing: Process existing files on startup
            process_interval: Interval for processing pending events
        """
        try:
            self.start_monitoring(process_existing=process_existing)
            self.file_monitor.run_forever(process_interval=process_interval)
        except Exception as e:
            logger.error(f"Error running pipeline: {str(e)}")
        finally:
            self.stop_monitoring()
    
    def search_documents(self, 
                        query: str, 
                        k: int = 4, 
                        with_scores: bool = False,
                        filter_dict: Optional[Dict] = None):
        """
        Search documents in the vector store
        
        Args:
            query: Search query
            k: Number of results to return
            with_scores: Whether to return similarity scores
            filter_dict: Optional metadata filter
            
        Returns:
            Search results
        """
        if with_scores:
            return self.vector_store_manager.similarity_search_with_score(
                query=query, k=k, filter=filter_dict
            )
        else:
            return self.vector_store_manager.similarity_search(
                query=query, k=k, filter=filter_dict
            )
    
    def self_query(self, query: str):
        """
        Perform self-query retrieval (natural language query with filtering)
        
        Args:
            query: Natural language query
            
        Returns:
            Query results
        """
        if not self.self_query_manager:
            logger.error("Self-query retriever is not enabled")
            return []
        
        return self.self_query_manager.query(query)
    
    def add_custom_metadata_field(self, name: str, description: str, field_type: str):
        """
        Add custom metadata field for self-querying
        
        Args:
            name: Field name
            description: Field description
            field_type: Field type (string, integer, float, etc.)
        """
        if self.self_query_manager:
            self.self_query_manager.add_metadata_field(name, description, field_type)
            logger.info(f"Added custom metadata field: {name}")
        else:
            logger.warning("Self-query retriever is not enabled")
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics"""
        monitor_stats = self.file_monitor.get_stats()
        vector_stats = self.vector_store_manager.get_stats()
        
        return {
            'pipeline': self.stats,
            'file_monitor': monitor_stats,
            'vector_store': vector_stats,
            'document_processor': {
                'chunk_size': self.document_processor.chunk_size,
                'chunk_overlap': self.document_processor.chunk_overlap,
                'supported_extensions': self.document_processor.supported_extensions
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform pipeline health check"""
        health = {
            'status': 'healthy',
            'issues': []
        }
        
        # Check if monitoring is active
        if not self.file_monitor.is_monitoring:
            health['issues'].append('File monitoring is not active')
        
        # Check vector store
        try:
            vector_stats = self.vector_store_manager.get_stats()
            if not vector_stats.get('is_initialized', False):
                health['issues'].append('Vector store is not initialized')
        except Exception as e:
            health['issues'].append(f'Vector store error: {str(e)}')
        
        # Check for recent errors
        if self.stats['processing_errors'] > 0:
            health['issues'].append(f"Processing errors: {self.stats['processing_errors']}")
        
        if health['issues']:
            health['status'] = 'unhealthy'
        
        return health


# Configuration management
class PipelineConfig:
    """Configuration management for the pipeline"""
    
    @staticmethod
    def from_env() -> Dict[str, Any]:
        """Load configuration from environment variables"""
        return {
            'watch_paths': os.getenv('WATCH_PATHS', './documents').split(','),
            'collection_name': os.getenv('COLLECTION_NAME', 'document_store'),
            'embeddings_model': os.getenv('EMBEDDINGS_MODEL', 'text-embedding-ada-002'),
            'qdrant_location': os.getenv('QDRANT_LOCATION', ':memory:'),
            'chunk_size': int(os.getenv('CHUNK_SIZE', '1000')),
            'chunk_overlap': int(os.getenv('CHUNK_OVERLAP', '200')),
            'debounce_seconds': int(os.getenv('DEBOUNCE_SECONDS', '2')),
            'recursive': os.getenv('RECURSIVE', 'true').lower() == 'true',
            'enable_self_query': os.getenv('ENABLE_SELF_QUERY', 'true').lower() == 'true',
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        }
    
    @staticmethod
    def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None):
        """Setup logging configuration"""
        handlers = [logging.StreamHandler()]
        
        if log_file:
            handlers.append(logging.FileHandler(log_file))
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )