
import logging
import time
from typing import List, Set, Optional
from pathlib import Path
from .monitor import FileMonitor
from .processor import DocumentProcessor
from .vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


class DataExtractionPipeline:
    """Simplified pipeline with reliable ID-based file deletion"""
    
    def __init__(self, 
                 watch_paths: List[str],
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 embedding_model: str = "BAAI/bge-small-en-v1.5",
                 collection_name: str = "document_chunks",
                 persist_dir: str = "./qdrant_storage"):
        """
        Initialize data pipeline with ID-based deletion support
        
        Args:
            watch_paths: Directories to monitor for changes
            chunk_size: Text chunk size for processing
            chunk_overlap: Overlap between chunks
            embedding_model: HuggingFace embedding model
            collection_name: Qdrant collection name
            persist_dir: Vector store persistence directory
        """
        self.watch_paths = [Path(p) for p in watch_paths]
        
        # Initialize components
        self.processor = DocumentProcessor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.vector_store = VectorStoreManager(
            embedding_model=embedding_model,
            collection_name=collection_name,
            persist_dir=persist_dir
        )
        
        # Initialize file monitor
        self.file_monitor = FileMonitor(
            watch_paths=watch_paths,
            on_file_created=self._handle_file_created,
            on_file_modified=self._handle_file_modified,
            on_file_deleted=self._handle_file_deleted
        )
        
        logger.info(f"Pipeline initialized with ID-based deletion for paths: {', '.join(watch_paths)}")
        
        # Process existing files
        self._process_existing_files()
    
    def _process_existing_files(self) -> None:
        """Process all existing supported files in watch directories"""
        logger.info("Processing existing files...")
        
        processed_count = 0
        for watch_path in self.watch_paths:
            if not watch_path.exists():
                logger.warning(f"Watch path does not exist: {watch_path}")
                continue
                
            for file_path in watch_path.rglob('*'):
                if file_path.is_file() and self._should_process_file(file_path):
                    if self._process_file(file_path):
                        processed_count += 1
        
        logger.info(f"Processed {processed_count} existing files")
    
    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed"""
        # Skip metadata files and unsupported files
        if file_path.name == "metadata.json":
            return False
        
        return self.processor.is_supported_file(str(file_path))
    
    def _process_file(self, file_path: Path, force: bool = False) -> bool:
        """
        Process a single file: load, chunk, and add to vector store with ID tracking
        
        Args:
            file_path: Path to file to process
            force: Force processing even if already processed
            
        Returns:
            True if processing successful, False otherwise
        """
        try:
            file_path_str = str(file_path)
            
            # Check if already processed (unless forced)
            if not force and self.vector_store.is_file_processed(file_path_str):
                logger.debug(f"File already processed: {file_path}")
                return False
            
            # Process the file
            logger.info(f"Processing file: {file_path}")
            chunks = self.processor.process_file(file_path_str)
            
            if not chunks:
                logger.warning(f"No chunks generated for: {file_path}")
                return False
            
            # Add to vector store with ID tracking
            self.vector_store.add_documents(chunks)
            logger.info(f"Successfully processed {len(chunks)} chunks from: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return False
    
    def _handle_file_created(self, file_path: str) -> None:
        """Handle new file creation"""
        logger.info(f"New file detected: {file_path}")
        
        file_path_obj = Path(file_path)
        if self._should_process_file(file_path_obj):
            # Small delay to ensure file is fully written
            time.sleep(0.1)
            self._process_file(file_path_obj)
    
    def _handle_file_modified(self, file_path: str) -> None:
        """Handle file modification with reliable ID-based deletion and reprocessing"""
        logger.info(f"File modified: {file_path}")
        
        file_path_obj = Path(file_path)
        if not self._should_process_file(file_path_obj):
            return
        
        try:
            # Remove old version using ID-based deletion
            logger.info(f"Removing old version of modified file: {file_path}")
            removal_success = self.vector_store.remove_file(file_path)
            
            if removal_success:
                logger.info(f"Successfully removed old version: {file_path}")
            else:
                logger.warning(f"Could not remove old version (may not exist): {file_path}")
            
            # Wait a moment for file system operations to complete
            time.sleep(0.1)
            
            # Reprocess the file with new content
            logger.info(f"Reprocessing modified file: {file_path}")
            if self._process_file(file_path_obj, force=True):
                logger.info(f"Successfully reprocessed modified file: {file_path}")
            else:
                logger.error(f"Failed to reprocess modified file: {file_path}")
            
        except Exception as e:
            logger.error(f"Error handling file modification for {file_path}: {e}")
    
    def _handle_file_deleted(self, file_path: str) -> None:
        """Handle file deletion with reliable ID-based removal"""
        logger.info(f"File deleted: {file_path}")
        
        try:
            # Use ID-based deletion for reliable removal
            removal_success = self.vector_store.remove_file(file_path)
            
            if removal_success:
                logger.info(f"Successfully removed all data for deleted file: {file_path}")
            else:
                logger.warning(f"Could not remove data for deleted file (may not exist): {file_path}")
                
        except Exception as e:
            logger.error(f"Error removing deleted file {file_path}: {e}")
    
    def start_monitoring(self) -> None:
        """Start file monitoring"""
        logger.info("Starting file monitoring with ID-based deletion...")
        self.file_monitor.start_monitoring()
    
    def stop_monitoring(self) -> None:
        """Stop file monitoring"""
        logger.info("Stopping file monitoring...")
        self.file_monitor.stop_monitoring()
    
    def process_file_manually(self, file_path: str, force: bool = False) -> bool:
        """Manually process a specific file"""
        return self._process_file(Path(file_path), force=force)
    
    def remove_file_manually(self, file_path: str) -> bool:
        """Manually remove a specific file using ID-based deletion"""
        try:
            return self.vector_store.remove_file(file_path)
        except Exception as e:
            logger.error(f"Failed to manually remove file {file_path}: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get pipeline statistics including ID tracking info"""
        stats = {
            'watch_paths': [str(p) for p in self.watch_paths],
            'vector_store_stats': self.vector_store.get_stats()
        }
        
        # Add ID-based deletion info
        vector_stats = stats['vector_store_stats']
        if 'tracked_vectors' in vector_stats:
            stats['id_based_deletion'] = {
                'enabled': True,
                'tracked_vectors': vector_stats['tracked_vectors'],
                'deletion_method': 'ID-based with filter fallback'
            }
        
        return stats
    
    def health_check(self) -> bool:
        """Perform health check of pipeline components"""
        try:
            # Check vector store (includes ID tracking verification)
            if not self.vector_store.health_check():
                return False
            
            # Check processor
            if not hasattr(self.processor, 'is_supported_file'):
                return False
            
            # Check watch paths exist
            missing_paths = [p for p in self.watch_paths if not p.exists()]
            if missing_paths:
                logger.warning(f"Missing watch paths: {missing_paths}")
            
            # Verify ID tracking is working
            stats = self.vector_store.get_stats()
            if 'tracked_vectors' not in stats:
                logger.warning("ID tracking may not be working properly")
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def cleanup_orphaned_data(self) -> int:
        """Clean up orphaned data from database and vector store"""
        try:
            return self.vector_store.cleanup_orphaned_records()
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned data: {e}")
            return 0

