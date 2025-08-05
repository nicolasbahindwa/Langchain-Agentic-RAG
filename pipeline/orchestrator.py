"""
Complete data extraction pipeline orchestrator integrating file monitoring,
document processing, and vector store management
"""
import logging
import json
from typing import List, Set
from pathlib import Path
from .monitor import FileMonitor
from .processor import DocumentProcessor
from .vector_store import VectorStoreManager, get_recommended_model
from utils.logger import get_enhanced_logger

class DataExtractionPipeline:
    """Complete pipeline with file monitoring, processing and vector store integration"""
    
    def __init__(self, 
                 watch_paths: List[str],
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 embedding_model: str = get_recommended_model("multilingual"),
                 collection_name: str = "document_chunks",
                 persist_dir: str = "./qdrant_storage"):
        """
        Initialize complete data pipeline
        
        Args:
            watch_paths: Directories to monitor for changes
            chunk_size: Text chunk size for processing
            chunk_overlap: Overlap between chunks
            embedding_model: OpenAI embedding model
            collection_name: Qdrant collection name
            persist_dir: Vector store persistence directory
        """
        self.watch_paths = watch_paths
        
        # Initialize enhanced logger
        self.logger = get_enhanced_logger("orchestrator")
        
        # Track processed files to avoid duplicates
        self.processed_files: Set[str] = set()
        
        # Initialize document processor
        self.processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        self.logger.success("Document processor initialized")
        
        # Initialize vector store manager
        try:
            self.vector_store = VectorStoreManager(
                embedding_model=embedding_model,
                collection_name=collection_name,
                persist_dir=persist_dir
            )
            self.logger.success("Vector store manager initialized")
        except Exception as e:
            self.logger.failure(f"Vector store initialization failed: {str(e)}")
            raise
        
        # Initialize file monitor with event handlers
        self.file_monitor = FileMonitor(
            watch_paths=watch_paths,
            on_file_created=self._handle_file_created,
            on_file_modified=self._handle_file_modified,
            on_file_deleted=self._handle_file_deleted
        )
        
        self.logger.success(f"Pipeline initialized for paths: {', '.join(watch_paths)}")
        
        # Process existing files on startup
        self._process_existing_files()
    
    def _process_existing_files(self):
        """Process all existing supported files in watch directories"""
        self.logger.info("Processing existing files in watch directories...")
        
        total_processed = 0
        for watch_path in self.watch_paths:
            path = Path(watch_path)
            if not path.exists():
                self.logger.warning(f"Watch path does not exist: {watch_path}")
                continue
                
            for file_path in path.rglob('*'):
                if file_path.is_file() and self.processor.is_supported_file(file_path):
                    # Skip metadata files
                    if file_path.name == "metadata.json":
                        self.logger.info(f"Skipping metadata file: {file_path}")
                        continue
                        
                    if self._process_file(str(file_path)):
                        total_processed += 1
        
        self.logger.success(f"Processed {total_processed} existing files on startup")
    
    def _process_file(self, file_path: str) -> bool:
        """
        Process a single file: load, chunk, and add to vector store
        
        Args:
            file_path: Path to file to process
            
        Returns:
            True if processing successful, False otherwise
        """
        try:
            # Check if file is supported
            if not self.processor.is_supported_file(file_path):
                self.logger.info(f"Skipping unsupported file: {file_path}")
                return False
            
            # Get file hash for deduplication
            file_hash = self.processor.get_file_hash(file_path)
            if file_hash in self.processed_files:
                self.logger.info(f"File already processed: {file_path}")
                return False
            
            # Process the file
            self.logger.info(f"Processing file: {file_path}")
            chunks = self.processor.process_file(file_path)
            
            if not chunks:
                self.logger.warning(f"No chunks generated for: {file_path}")
                return False
            
            # Add to vector store
            self.vector_store.add_documents(chunks)
            
            # Track as processed
            self.processed_files.add(file_hash)
            
            self.logger.success(f"Successfully processed {len(chunks)} chunks from: {file_path}")
            return True
            
        except Exception as e:
            self.logger.failure(f"File processing failed for {file_path}: {str(e)}")
            return False
    
    def _remove_file_from_store(self, file_path: str):
        """
        Remove file's documents from vector store
        
        Args:
            file_path: Path to deleted file
        """
        try:
            # Create filter to remove documents from this file
            filter_conditions = {
                "must": [
                    {
                        "key": "source",
                        "match": {"value": str(file_path)}
                    }
                ]
            }
            
            self.vector_store.delete_documents(filter_conditions)
            self.logger.success(f"Removed documents from vector store for: {file_path}")
            
        except Exception as e:
            self.logger.failure(f"Failed to remove documents for {file_path}: {str(e)}")
    
    # File event handlers
    def _handle_file_created(self, file_path: str):
        """Handle new file creation"""
        self.logger.success(f"NEW FILE DETECTED: {file_path}")
        
        # Skip metadata files
        if Path(file_path).name == "metadata.json":
            self.logger.info(f"Skipping metadata file: {file_path}")
            return
            
        # Process the new file
        if self._process_file(file_path):
            self.logger.performance(f"New file processed and indexed: {file_path}")
        else:
            self.logger.warning(f"Failed to process new file: {file_path}")
    
    def _handle_file_modified(self, file_path: str):
        """Handle file modification"""
        # Skip metadata files
        if Path(file_path).name == "metadata.json":
            return
            
        self.logger.info(f"FILE MODIFIED: {file_path}")
        
        try:
            # Remove old version
            self._remove_file_from_store(file_path)
            
            # Process updated version
            if self._process_file(file_path):
                self.logger.performance(f"Modified file reprocessed: {file_path}")
            else:
                self.logger.warning(f"Failed to reprocess modified file: {file_path}")
                
        except Exception as e:
            self.logger.failure(f"Error handling file modification for {file_path}: {str(e)}")
    
    def _handle_file_deleted(self, file_path: str):
        """Handle file deletion"""
        # Skip metadata files
        if Path(file_path).name == "metadata.json":
            return
            
        self.logger.warning(f"FILE DELETED: {file_path}")
        
        # Remove from vector store
        self._remove_file_from_store(file_path)
        
        self.logger.info(f"Cleanup completed for deleted file: {file_path}")
    
    def get_pipeline_stats(self) -> dict:
        """Get statistics about the pipeline state"""
        try:
            vector_stats = self.vector_store.get_collection_info()
            return {
                "processed_files_count": len(self.processed_files),
                "watch_paths": self.watch_paths,
                "vector_store_stats": vector_stats,
                "is_monitoring": self.file_monitor.is_monitoring
            }
        except Exception as e:
            self.logger.failure(f"Failed to get pipeline stats: {str(e)}")
            return {"error": str(e)}
    
    def query_documents(self, query: str, k: int = 5, filters: dict = None):
        """
        Query the vector store for relevant documents
        
        Args:
            query: Search query
            k: Number of results to return
            filters: Optional Qdrant filters
            
        Returns:
            List of relevant document chunks
        """
        self.logger.info(f"Querying documents with: '{query}' (k={k})")
        
        try:
            results = self.vector_store.query_documents(query=query, k=k, filters=filters)
            self.logger.success(f"Query returned {len(results)} results")
            return results
        except Exception as e:
            self.logger.failure(f"Query failed: {str(e)}")
            return []
    
    def start_monitoring(self):
        """Start file monitoring"""
        self.logger.performance("STARTING FILE MONITORING")
        try:
            self.file_monitor.start_monitoring()
            stats = self.get_pipeline_stats()
            self.logger.info(f"Pipeline stats: {stats}")
        except Exception as e:
            self.logger.failure(f"Failed to start monitoring: {str(e)}")
            raise
    
    def stop_monitoring(self):
        """Stop file monitoring"""
        self.logger.performance("STOPPING FILE MONITORING")
        try:
            self.file_monitor.stop_monitoring()
        except Exception as e:
            self.logger.failure(f"Failed to stop monitoring: {str(e)}")
    
    def run_forever(self):
        """Main execution loop"""
        try:
            self.start_monitoring()
            self.logger.info("Monitoring files... (Press Ctrl+C to stop)")
            self.logger.info("Pipeline is ready for queries and file changes")
            self.file_monitor.run_forever()
        except KeyboardInterrupt:
            self.logger.warning("Keyboard interrupt received")
        except Exception as e:
            self.logger.failure(f"Critical error in pipeline: {str(e)}")
            raise
        finally:
            self.stop_monitoring()
            self.logger.success("Pipeline shutdown complete")