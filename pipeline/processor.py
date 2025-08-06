import os
import re
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime

from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader, 
    PyPDFLoader, 
    CSVLoader,
    UnstructuredWordDocumentLoader,
    JSONLoader,
    UnstructuredFileLoader
)
from utils.logger import get_enhanced_logger

logger = get_enhanced_logger("DocumentProcessor")

class StructureAwareChunker:
    """Advanced chunking with structure awareness and fallback strategies"""
    
    def __init__(self, 
                 max_chunk_size: int = 1000,
                 min_chunk_size: int = 100,
                 chunk_overlap: int = 200,
                 preserve_headings: bool = True):
        """
        Initialize structure-aware chunker
        
        Args:
            max_chunk_size: Maximum characters per chunk
            min_chunk_size: Minimum characters per chunk
            chunk_overlap: Overlap between chunks for context preservation
            preserve_headings: Whether to include heading context in chunks
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.chunk_overlap = chunk_overlap
        self.preserve_headings = preserve_headings
        
        # Fallback splitter for long sections
        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Heading patterns for different document types
        self.heading_patterns = [
            # Markdown headings
            r'^#{1,6}\s+(.+)$',
            # HTML headings
            r'<h[1-6][^>]*>(.+?)</h[1-6]>',
            # Underlined headings
            r'^(.+)\n[=\-~]{3,}$',
            # ALL CAPS headings (with some constraints)
            r'^[A-Z][A-Z\s]{10,50}$',
            # Numbered sections
            r'^\d+\.?\s+[A-Z].{5,50}$',
            # Roman numerals
            r'^[IVX]+\.\s+[A-Z].{5,50}$',
        ]
        
        # Compile regex patterns
        self.compiled_patterns = [re.compile(pattern, re.MULTILINE | re.IGNORECASE) 
                                for pattern in self.heading_patterns]
    
    def _detect_headings(self, text: str) -> List[Tuple[int, str, str]]:
        """
        Detect headings in text using multiple strategies
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of tuples: (position, heading_text, heading_level)
        """
        headings = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check markdown headings first (most reliable)
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                heading_text = line.lstrip('#').strip()
                if heading_text:
                    position = text.find(line)
                    headings.append((position, heading_text, f"h{level}"))
                    continue
            
            # Check for underlined headings
            if i < len(lines) - 1:
                next_line = lines[i + 1].strip()
                if next_line and all(c in '=-~' for c in next_line) and len(next_line) >= 3:
                    level = 1 if '=' in next_line else 2
                    position = text.find(line)
                    headings.append((position, line, f"h{level}"))
                    continue
            
            # Check other patterns
            for pattern in self.compiled_patterns[2:]:  # Skip markdown and HTML (handled above)
                match = pattern.match(line)
                if match:
                    heading_text = match.group(1) if match.groups() else line
                    position = text.find(line)
                    # Heuristic for heading level based on content
                    level = self._infer_heading_level(line)
                    headings.append((position, heading_text.strip(), f"h{level}"))
                    break
        
        # Sort by position and deduplicate
        headings = sorted(list(set(headings)), key=lambda x: x[0])
        return headings
    
    def _infer_heading_level(self, heading_text: str) -> int:
        """Infer heading level based on text characteristics"""
        if len(heading_text) < 20 and heading_text.isupper():
            return 1  # Major heading
        elif heading_text.startswith(('1.', 'I.', 'A.')):
            return 2  # Primary section
        elif any(heading_text.startswith(prefix) for prefix in ['a.', 'i.', '•']):
            return 3  # Subsection
        else:
            return 2  # Default to secondary heading
    
    def _create_structured_chunks(self, text: str, headings: List[Tuple[int, str, str]]) -> List[Dict[str, Any]]:
        """
        Create chunks based on document structure
        
        Args:
            text: Full document text
            headings: List of detected headings with positions
            
        Returns:
            List of chunk dictionaries with content and metadata
        """
        if not headings:
            return self._fallback_chunk(text, "No structure detected")
        
        chunks = []
        heading_stack = []  # Stack to track heading hierarchy
        
        for i, (pos, heading_text, level) in enumerate(headings):
            # Determine section start and end
            start_pos = pos
            end_pos = headings[i + 1][0] if i + 1 < len(headings) else len(text)
            
            # Extract section content
            section_content = text[start_pos:end_pos].strip()
            
            # Update heading stack for context
            level_num = int(level[1])
            heading_stack = [h for h in heading_stack if h[1] < level_num]
            heading_stack.append((heading_text, level_num))
            
            # Create heading context
            heading_context = " > ".join([h[0] for h in heading_stack]) if self.preserve_headings else ""
            
            # Check if section is too long
            if len(section_content) <= self.max_chunk_size:
                # Section fits in one chunk
                chunks.append({
                    'content': section_content,
                    'heading_context': heading_context,
                    'structure_type': 'section',
                    'heading_level': level,
                    'size': len(section_content)
                })
            else:
                # Section too long - apply fallback chunking
                sub_chunks = self._fallback_chunk(section_content, f"Long section: {heading_text}")
                for j, sub_chunk in enumerate(sub_chunks):
                    sub_chunk['heading_context'] = heading_context
                    sub_chunk['structure_type'] = 'subsection'
                    sub_chunk['heading_level'] = f"{level}_part_{j+1}"
                    chunks.append(sub_chunk)
        
        return chunks
    
    def _fallback_chunk(self, text: str, reason: str = "Fallback chunking") -> List[Dict[str, Any]]:
        """
        Apply fallback fixed-size chunking
        
        Args:
            text: Text to chunk
            reason: Reason for fallback chunking
            
        Returns:
            List of chunk dictionaries
        """
        try:
            # Use the fallback splitter
            temp_doc = Document(page_content=text)
            split_docs = self.fallback_splitter.split_documents([temp_doc])
            
            chunks = []
            for i, doc in enumerate(split_docs):
                chunks.append({
                    'content': doc.page_content,
                    'heading_context': '',
                    'structure_type': 'fixed_size',
                    'heading_level': f"chunk_{i+1}",
                    'size': len(doc.page_content),
                    'fallback_reason': reason
                })
            
            return chunks
            
        except Exception as e:
            logger.warning(f"Fallback chunking failed: {e}")
            # Ultimate fallback - simple splitting
            words = text.split()
            chunks = []
            for i in range(0, len(words), self.max_chunk_size // 5):  # Rough word estimate
                chunk_words = words[i:i + self.max_chunk_size // 5]
                chunk_text = ' '.join(chunk_words)
                chunks.append({
                    'content': chunk_text,
                    'heading_context': '',
                    'structure_type': 'simple',
                    'heading_level': f"simple_{i//100 + 1}",
                    'size': len(chunk_text),
                    'fallback_reason': 'Ultimate fallback'
                })
            
            return chunks
    
    def chunk_text(self, text: str, source_metadata: Dict[str, Any] = None) -> List[Document]:
        """
        Main chunking method with structure awareness
        
        Args:
            text: Input text to chunk
            source_metadata: Metadata from source document
            
        Returns:
            List of Document objects with enhanced chunking
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            logger.warning("Text too short for chunking")
            return []
        
        try:
            # Detect document structure
            headings = self._detect_headings(text)
            logger.debug(f"Detected {len(headings)} headings in document")
            
            # Create structured chunks
            chunk_data = self._create_structured_chunks(text, headings)
            
            # Convert to Document objects
            documents = []
            for i, chunk_info in enumerate(chunk_data):
                # Create enhanced metadata
                metadata = {
                    'chunk_id': f"{source_metadata.get('file_hash', 'unknown')}_{i}",
                    'chunk_index': i,
                    'chunk_size': chunk_info['size'],
                    'heading_context': chunk_info['heading_context'],
                    'structure_type': chunk_info['structure_type'],
                    'heading_level': chunk_info['heading_level'],
                    'chunked_at': datetime.now().isoformat(),
                }
                
                # Add fallback reason if applicable
                if 'fallback_reason' in chunk_info:
                    metadata['fallback_reason'] = chunk_info['fallback_reason']
                
                # Merge with source metadata
                if source_metadata:
                    metadata.update(source_metadata)
                
                # Create document
                doc = Document(
                    page_content=chunk_info['content'],
                    metadata=metadata
                )
                documents.append(doc)
            
            logger.info(f"Created {len(documents)} structure-aware chunks")
            return documents
            
        except Exception as e:
            logger.failure(f"Structure-aware chunking failed: {e}")
            # Final fallback to simple chunking
            return self._simple_chunk_fallback(text, source_metadata)
    
    def _simple_chunk_fallback(self, text: str, source_metadata: Dict[str, Any] = None) -> List[Document]:
        """Emergency fallback to simple chunking"""
        try:
            temp_doc = Document(page_content=text, metadata=source_metadata or {})
            chunks = self.fallback_splitter.split_documents([temp_doc])
            
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    'chunk_id': f"{source_metadata.get('file_hash', 'unknown')}_{i}",
                    'chunk_index': i,
                    'chunk_size': len(chunk.page_content),
                    'structure_type': 'emergency_fallback',
                    'chunked_at': datetime.now().isoformat(),
                })
            
            logger.warning(f"Used emergency fallback chunking: {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.failure(f"Even emergency fallback failed: {e}")
            return []


class DocumentProcessor:
    """Enhanced document processor with structure-aware chunking"""
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 supported_extensions: Optional[List[str]] = None,
                 max_file_size: int = 100 * 1024 * 1024,
                 enable_structure_aware: bool = True):
        """
        Initialize enhanced document processor with structure-aware chunking
        
        Args:
            chunk_size: Maximum character length of text chunks
            chunk_overlap: Overlap between chunks for context preservation
            supported_extensions: File types to process
            max_file_size: Maximum file size in bytes (default 100MB)
            enable_structure_aware: Enable structure-aware chunking
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_file_size = max_file_size
        self.enable_structure_aware = enable_structure_aware
        
        # Initialize chunking strategy
        if enable_structure_aware:
            self.chunker = StructureAwareChunker(
                max_chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                preserve_headings=True
            )
            logger.info("✅ Structure-aware chunking enabled")
        else:
            # Fallback to traditional chunking
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            logger.info("ℹ️ Using traditional fixed-size chunking")
        
        # File type handling
        self.supported_extensions = supported_extensions or [
            '.txt', '.pdf', '.csv', '.docx', '.doc', '.json', 
            '.pptx', '.html', '.md', '.rtf', '.odt'
        ]
        
        # Document loader registry
        self.loaders = {
            '.txt': self._load_text_file,
            '.md': self._load_text_file,
            '.pdf': self._load_pdf_file,
            '.csv': self._load_csv_file,
            '.docx': self._load_word_file,
            '.doc': self._load_word_file,
            '.json': self._load_json_file,
            '.pptx': self._load_unstructured_file,
            '.html': self._load_unstructured_file,
            '.rtf': self._load_unstructured_file,
            '.odt': self._load_unstructured_file,
        }
    
    def _safe_file_access_check(self, file_path: Path) -> bool:
        """Comprehensive file access validation"""
        try:
            if not file_path.exists():
                logger.warning(f"File does not exist: {file_path}")
                return False
            
            if not file_path.is_file():
                logger.warning(f"Path is not a file: {file_path}")
                return False
            
            if not os.access(file_path, os.R_OK):
                logger.failure(f"❌ No read permission for: {file_path}")
                return False
            
            file_size = file_path.stat().st_size
            if file_size == 0:
                logger.warning(f"File is empty: {file_path}")
                return False
            
            if file_size > self.max_file_size:
                logger.warning(f"File too large ({file_size / 1024 / 1024:.1f}MB): {file_path}")
                return False
            
            return True
            
        except PermissionError:
            logger.failure(f"❌ Permission denied accessing: {file_path}")
            return False
        except Exception as e:
            logger.failure(f"❌ Error checking file access for {file_path}: {e}")
            return False
    
    def get_file_hash(self, file_path: Union[str, Path]) -> str:
        """Generate file hash with multiple fallback strategies"""
        path = Path(file_path)
        
        try:
            with open(path, 'rb') as f:
                content = f.read()
                content_hash = hashlib.md5(content).hexdigest()
            logger.debug(f"Generated content hash for: {path.name}")
            return content_hash
            
        except PermissionError:
            logger.warning(f"⚠️ Permission denied for content hash: {path}")
            
        except Exception as e:
            logger.warning(f"⚠️ Content hash failed for {path}: {e}")
        
        try:
            stat = path.stat()
            metadata_str = f"{path.name}_{stat.st_size}_{stat.st_mtime}_{stat.st_ctime}"
            metadata_hash = hashlib.md5(metadata_str.encode()).hexdigest()
            logger.info(f"Generated metadata hash for: {path.name}")
            return metadata_hash
            
        except Exception as e:
            logger.warning(f"⚠️ Metadata hash failed for {path}: {e}")
        
        try:
            path_hash = hashlib.md5(str(path).encode()).hexdigest()
            logger.warning(f"Using path-based hash for: {path.name}")
            return path_hash
            
        except Exception as e:
            logger.failure(f"❌ All hash strategies failed for {path}: {e}")
            return "unknown_hash"
    
    # [Previous loader methods remain the same - _load_text_file, _load_pdf_file, etc.]
    def _load_text_file(self, file_path: Path) -> List[Document]:
        """Load text files with encoding detection"""
        encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'iso-8859-1', 'ascii', 'latin1']
        
        for encoding in encodings:
            try:
                loader = TextLoader(str(file_path), encoding=encoding)
                documents = loader.load()
                
                if documents and documents[0].page_content.strip():
                    logger.debug(f"Loaded text file with {encoding} encoding")
                    return documents
                    
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Text loader failed with {encoding}: {e}")
                continue
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            if content.strip():
                doc = Document(page_content=content)
                logger.info(f"Loaded text file with error replacement")
                return [doc]
        except Exception as e:
            logger.failure(f"❌ All text loading strategies failed: {e}")
        
        return []
    
    def _load_pdf_file(self, file_path: Path) -> List[Document]:
        """Load PDF files with error handling"""
        try:
            loader = PyPDFLoader(str(file_path))
            documents = loader.load()
            
            valid_docs = []
            for doc in documents:
                content = doc.page_content.strip()
                if content and len(content) > 10:
                    doc.page_content = content
                    valid_docs.append(doc)
            
            if valid_docs:
                logger.debug(f"Loaded {len(valid_docs)} valid PDF pages")
                return valid_docs
            else:
                logger.warning(f"No valid content found in PDF: {file_path}")
                
        except Exception as e:
            logger.failure(f"❌ PDF loading failed: {e}")
        
        return []
    
    def _load_csv_file(self, file_path: Path) -> List[Document]:
        """Load CSV files with error handling"""
        try:
            loader = CSVLoader(str(file_path))
            documents = loader.load()
            
            if documents:
                logger.debug(f"Loaded CSV with {len(documents)} rows")
                return documents
                
        except Exception as e:
            logger.failure(f"❌ CSV loading failed: {e}")
        
        return []
    
    def _load_word_file(self, file_path: Path) -> List[Document]:
        """Load Word documents with error handling"""
        try:
            loader = UnstructuredWordDocumentLoader(str(file_path))
            documents = loader.load()
            
            valid_docs = []
            for doc in documents:
                content = doc.page_content.strip()
                if content and len(content) > 10:
                    valid_docs.append(doc)
            
            if valid_docs:
                logger.debug(f"Loaded Word document with {len(valid_docs)} sections")
                return valid_docs
                
        except Exception as e:
            logger.failure(f"❌ Word document loading failed: {e}")
        
        return []
    
    def _load_json_file(self, file_path: Path) -> List[Document]:
        """Load JSON files with error handling"""
        try:
            loader = JSONLoader(
                file_path=str(file_path),
                jq_schema='.',
                text_content=False
            )
            documents = loader.load()
            
            if documents:
                logger.debug(f"Loaded JSON document")
                return documents
                
        except Exception as e:
            logger.failure(f"❌ JSON loading failed: {e}")
        
        return []
    
    def _load_unstructured_file(self, file_path: Path) -> List[Document]:
        """Load files using unstructured loader"""
        try:
            loader = UnstructuredFileLoader(str(file_path))
            documents = loader.load()
            
            if documents:
                logger.debug(f"Loaded unstructured document")
                return documents
                
        except Exception as e:
            logger.failure(f"❌ Unstructured loading failed: {e}")
        
        return []
    
    def is_supported_file(self, file_path: Union[str, Path]) -> bool:
        """Check if file extension is supported"""
        file_extension = Path(file_path).suffix.lower()
        return file_extension in self.supported_extensions
    
    def load_document(self, file_path: Union[str, Path]) -> List[Document]:
        """Load document with comprehensive error handling and validation"""
        path = Path(file_path)
        
        if not self._safe_file_access_check(path):
            return []
        
        if not self.is_supported_file(path):
            logger.warning(f"Unsupported file type: {path.suffix}")
            return []
        
        try:
            loader_func = self.loaders.get(path.suffix.lower())
            if not loader_func:
                logger.failure(f"❌ No loader registered for {path.suffix}")
                return []
            
            logger.info(f"ℹ️ Loading document: {path.name}")
            documents = loader_func(path)
            
            if not documents:
                logger.warning(f"⚠️ No content extracted from: {path.name}")
                return []
            
            # Enhance metadata
            file_hash = self.get_file_hash(path)
            file_stats = path.stat()
            base_metadata = {
                'source': str(path),
                'file_name': path.name,
                'file_extension': path.suffix.lower(),
                'file_hash': file_hash,
                'processed_at': datetime.now().isoformat(),
                'file_size': file_stats.st_size,
                'file_modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            }
            
            for doc in documents:
                if not hasattr(doc, 'metadata') or doc.metadata is None:
                    doc.metadata = {}
                doc.metadata.update(base_metadata)
            
            logger.info(f"✅ Loaded {len(documents)} documents from {path.name}")
            return documents
            
        except Exception as e:
            logger.failure(f"❌ Document loading failed: {path.name} - Error loading {path}")
            return []
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """
        Split documents into chunks using structure-aware or traditional methods
        
        Args:
            documents: List of loaded documents
            
        Returns:
            List of chunked documents with enhanced metadata
        """
        if not documents:
            logger.warning("⚠️ No documents provided for chunking")
            return []
        
        try:
            valid_docs = []
            for doc in documents:
                if hasattr(doc, 'page_content') and doc.page_content:
                    content = doc.page_content.strip()
                    if len(content) >= 10:
                        valid_docs.append(doc)
            
            if not valid_docs:
                logger.warning("⚠️ No valid documents found for chunking")
                return []
            
            all_chunks = []
            
            for doc in valid_docs:
                if self.enable_structure_aware:
                    # Use structure-aware chunking
                    chunks = self.chunker.chunk_text(doc.page_content, doc.metadata)
                else:
                    # Use traditional chunking
                    chunks = self.text_splitter.split_documents([doc])
                    
                    # Add traditional metadata
                    for i, chunk in enumerate(chunks):
                        if not hasattr(chunk, 'metadata') or chunk.metadata is None:
                            chunk.metadata = {}
                        
                        file_hash = chunk.metadata.get('file_hash', 'unknown')
                        chunk.metadata.update({
                            'chunk_id': f"{file_hash}_{i}",
                            'chunk_index': i,
                            'chunk_size': len(chunk.page_content),
                            'structure_type': 'traditional',
                            'chunked_at': datetime.now().isoformat(),
                        })
                
                all_chunks.extend(chunks)
            
            logger.info(f"ℹ️ Split {len(valid_docs)} docs into {len(all_chunks)} chunks")
            return all_chunks
            
        except Exception as e:
            logger.failure(f"❌ Chunking failed: {str(e)}")
            return []
    
    def process_file(self, file_path: Union[str, Path]) -> List[Document]:
        """Complete processing pipeline for a single file"""
        logger.info(f"ℹ️ Processing file: {file_path}")
        
        documents = self.load_document(file_path)
        if not documents:
            logger.warning(f"⚠️ No documents loaded from: {file_path}")
            return []
        
        chunks = self.chunk_documents(documents)
        if not chunks:
            logger.warning(f"⚠️ No chunks generated for: {file_path}")
            return []
        
        # Log chunking statistics
        structure_types = {}
        for chunk in chunks:
            struct_type = chunk.metadata.get('structure_type', 'unknown')
            structure_types[struct_type] = structure_types.get(struct_type, 0) + 1
        
        logger.info(f"✅ Successfully processed {len(chunks)} chunks from: {file_path}")
        logger.info(f"📊 Chunk types: {dict(structure_types)}")
        return chunks
    
    def get_chunking_stats(self, chunks: List[Document]) -> Dict[str, Any]:
        """Get detailed statistics about chunking results"""
        if not chunks:
            return {}
        
        sizes = [chunk.metadata.get('chunk_size', len(chunk.page_content)) for chunk in chunks]
        structure_types = {}
        heading_levels = {}
        
        for chunk in chunks:
            # Structure type distribution
            struct_type = chunk.metadata.get('structure_type', 'unknown')
            structure_types[struct_type] = structure_types.get(struct_type, 0) + 1
            
            # Heading level distribution
            heading_level = chunk.metadata.get('heading_level', 'none')
            heading_levels[heading_level] = heading_levels.get(heading_level, 0) + 1
        
        return {
            'total_chunks': len(chunks),
            'average_chunk_size': sum(sizes) / len(sizes),
            'min_chunk_size': min(sizes),
            'max_chunk_size': max(sizes),
            'structure_type_distribution': structure_types,
            'heading_level_distribution': heading_levels,
            'chunks_with_headings': sum(1 for chunk in chunks 
                                      if chunk.metadata.get('heading_context', ''))
        }
    
    def process_directory(self, dir_path: Union[str, Path], recursive: bool = True) -> List[Document]:
        """Process all supported files in a directory with enhanced statistics"""
        path = Path(dir_path)
        if not path.is_dir():
            logger.failure(f"❌ Invalid directory: {dir_path}")
            return []
        
        logger.info(f"ℹ️ Processing directory: {dir_path}")
        all_chunks = []
        processed_files = 0
        failed_files = 0
        
        file_iterator = path.rglob('*') if recursive else path.iterdir()
        
        for file_path in file_iterator:
            if file_path.is_file() and self.is_supported_file(file_path):
                try:
                    chunks = self.process_file(file_path)
                    if chunks:
                        all_chunks.extend(chunks)
                        processed_files += 1
                    else:
                        failed_files += 1
                except Exception as e:
                    logger.failure(f"❌ Failed to process {file_path}: {e}")
                    failed_files += 1
        
        # Log comprehensive statistics
        stats = self.get_chunking_stats(all_chunks)
        logger.info(f"✅ Directory processing complete:")
        logger.info(f"   📁 Files processed: {processed_files}")
        logger.info(f"   ❌ Files failed: {failed_files}")
        logger.info(f"   📄 Total chunks: {stats.get('total_chunks', 0)}")
        logger.info(f"   📊 Average chunk size: {stats.get('average_chunk_size', 0):.0f} chars")
        logger.info(f"   🏗️ Structure types: {stats.get('structure_type_distribution', {})}")
        
        return all_chunks