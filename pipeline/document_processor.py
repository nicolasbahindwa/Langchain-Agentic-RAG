# document_processor.py
"""
Document processing module for loading and chunking documents
"""
import os
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader, 
    PyPDFLoader, 
    CSVLoader,
    UnstructuredWordDocumentLoader,
    JSONLoader
)

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles document loading, processing, and chunking"""
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 supported_extensions: Optional[List[str]] = None):
        """
        Initialize document processor
        
        Args:
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            supported_extensions: List of supported file extensions
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        
        # Default supported extensions and their loaders
        self.supported_extensions = supported_extensions or [
            '.txt', '.pdf', '.csv', '.docx', '.doc', '.json'
        ]
        
        self.loaders = {
            '.txt': TextLoader,
            '.pdf': PyPDFLoader,
            '.csv': CSVLoader,
            '.docx': UnstructuredWordDocumentLoader,
            '.doc': UnstructuredWordDocumentLoader,
            '.json': self._create_json_loader,
        }
    
    def _create_json_loader(self, file_path: str):
        """Create JSON loader with default settings"""
        return JSONLoader(file_path, jq_schema='.', text_content=False)
    
    def is_supported_file(self, file_path: str) -> bool:
        """Check if file extension is supported"""
        file_extension = Path(file_path).suffix.lower()
        return file_extension in self.supported_extensions
    
    def get_file_hash(self, file_path: str) -> str:
        """Generate hash of file content for duplicate detection"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.error(f"Error generating hash for {file_path}: {str(e)}")
            return ""
    
    def load_document(self, file_path: str) -> List[Document]:
        """
        Load document based on file extension
        
        Args:
            file_path: Path to the document file
            
        Returns:
            List of Document objects
        """
        if not os.path.exists(file_path):
            logger.warning(f"File does not exist: {file_path}")
            return []
        
        if not self.is_supported_file(file_path):
            logger.warning(f"Unsupported file type: {Path(file_path).suffix}")
            return []
        
        file_extension = Path(file_path).suffix.lower()
        
        try:
            # Get appropriate loader
            loader_factory = self.loaders[file_extension]
            
            # Create loader instance
            if file_extension == '.json':
                loader = loader_factory(file_path)
            else:
                loader = loader_factory(file_path)
            
            # Load documents
            documents = loader.load()
            
            # Add metadata to all documents
            file_hash = self.get_file_hash(file_path)
            file_stats = os.stat(file_path)
            
            for doc in documents:
                doc.metadata.update({
                    'source': file_path,
                    'file_name': Path(file_path).name,
                    'file_extension': file_extension,
                    'file_hash': file_hash,
                    'processed_at': datetime.now().isoformat(),
                    'file_size': file_stats.st_size,
                    'file_modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                })
            
            logger.info(f"Loaded {len(documents)} documents from {file_path}")
            return documents
            
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {str(e)}")
            return []
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """
        Split documents into chunks
        
        Args:
            documents: List of documents to chunk
            
        Returns:
            List of chunked documents
        """
        if not documents:
            return []
        
        try:
            chunks = self.text_splitter.split_documents(documents)
            
            # Add chunk metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    'chunk_id': i,
                    'chunk_size': len(chunk.page_content),
                    'chunked_at': datetime.now().isoformat()
                })
            
            logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking documents: {str(e)}")
            return []
    
    def process_file(self, file_path: str) -> List[Document]:
        """
        Complete processing pipeline for a single file
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            List of processed document chunks
        """
        logger.info(f"Processing file: {file_path}")
        
        # Load documents
        documents = self.load_document(file_path)
        if not documents:
            return []
        
        # Chunk documents
        chunks = self.chunk_documents(documents)
        
        logger.info(f"Successfully processed {file_path} into {len(chunks)} chunks")
        return chunks
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get file metadata without loading content"""
        if not os.path.exists(file_path):
            return {}
        
        file_stats = os.stat(file_path)
        return {
            'source': file_path,
            'file_name': Path(file_path).name,
            'file_extension': Path(file_path).suffix.lower(),
            'file_hash': self.get_file_hash(file_path),
            'file_size': file_stats.st_size,
            'file_modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            'is_supported': self.is_supported_file(file_path)
        }