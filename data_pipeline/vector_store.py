import os
import re
import json
import pickle
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import numpy as np
from collections import defaultdict

# Modern LangChain imports (updated)
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Evaluation imports
from sklearn.metrics.pairwise import cosine_similarity
import logging

@dataclass
class VectorStoreConfig:
    """Configuration for vector store processing"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: str = "cpu"
    max_retries: int = 3
    batch_size: int = 32
    similarity_threshold: float = 0.7
    max_chunks_per_doc: int = 100

@dataclass
class ChunkMetadata:
    """Structured metadata for chunks"""
    source: str
    section_title: str
    chunk_index: int
    section_type: str
    chunk_size: int
    overlap_with_previous: bool
    created_at: str
    splitting_strategy: str

class EvaluationMetrics:
    """Metrics for evaluating vector store performance"""
    
    @staticmethod
    def calculate_retrieval_metrics(relevant_docs: List[str], retrieved_docs: List[str]) -> Dict[str, float]:
        """Calculate precision, recall, and F1 for retrieval"""
        relevant_set = set(relevant_docs)
        retrieved_set = set(retrieved_docs)
        
        if not retrieved_set:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        
        intersection = relevant_set.intersection(retrieved_set)
        
        precision = len(intersection) / len(retrieved_set) if retrieved_set else 0.0
        recall = len(intersection) / len(relevant_set) if relevant_set else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {"precision": precision, "recall": recall, "f1": f1}
    
    @staticmethod
    def calculate_diversity_score(embeddings: np.ndarray) -> float:
        """Calculate diversity of retrieved results"""
        if len(embeddings) < 2:
            return 0.0
        
        similarities = cosine_similarity(embeddings)
        # Average pairwise similarity (lower = more diverse)
        avg_similarity = np.mean(similarities[np.triu_indices(len(similarities), k=1)])
        return 1.0 - avg_similarity

class SmartTextSplitter:
    """Enhanced text splitter with better error handling and configuration"""
    
    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Enhanced title patterns with confidence scores
        self.title_patterns = [
            (r'^#{1,6}\s+(.+)$', 0.9),  # Markdown headers
            (r'^([A-Z][A-Z\s]{5,50})$', 0.8),  # ALL CAPS titles
            (r'^(\d+\.\s+.+)$', 0.7),  # Numbered sections
            (r'^([IVX]+\.\s+.+)$', 0.7),  # Roman numerals
            (r'^(Chapter\s+\d+.*)$', 0.8),  # Chapter titles
            (r'^(Section\s+\d+.*)$', 0.8),  # Section titles
            (r'^(.{5,50}:)$', 0.6),  # Colon-ended titles
            (r'^(Article\s+\d+)$', 0.8),  # Article numbers
            (r'^(Part\s+[IVX]+)$', 0.8),  # Part numbers
        ]
    
    def split_by_sections(self, text: str, source: str) -> List[Document]:
        """Split text by sections with enhanced metadata"""
        try:
            sections = self._extract_sections(text)
            documents = []
            
            for section in sections:
                if len(section['content']) > self.config.chunk_size:
                    # Split large sections further
                    sub_chunks = self._split_large_section(section['content'])
                    for i, chunk in enumerate(sub_chunks):
                        metadata = ChunkMetadata(
                            source=source,
                            section_title=section['title'],
                            chunk_index=i,
                            section_type=section['metadata']['section_type'],
                            chunk_size=len(chunk),
                            overlap_with_previous=i > 0,
                            created_at=datetime.now().isoformat(),
                            splitting_strategy="sections_with_subsplits"
                        )
                        doc = Document(
                            page_content=chunk,
                            metadata=asdict(metadata)
                        )
                        documents.append(doc)
                else:
                    metadata = ChunkMetadata(
                        source=source,
                        section_title=section['title'],
                        chunk_index=0,
                        section_type=section['metadata']['section_type'],
                        chunk_size=len(section['content']),
                        overlap_with_previous=False,
                        created_at=datetime.now().isoformat(),
                        splitting_strategy="sections"
                    )
                    doc = Document(
                        page_content=section['content'],
                        metadata=asdict(metadata)
                    )
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error splitting text by sections: {e}")
            return self._fallback_split(text, source)
    
    def _extract_sections(self, text: str) -> List[Dict]:
        """Extract sections with confidence scoring"""
        sections = []
        current_section = []
        current_title = "Introduction"
        current_confidence = 0.5
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_section:
                    current_section.append('')
                continue
            
            # Check if this line is a title with confidence
            is_title, confidence = self._is_title_with_confidence(line)
            
            if is_title and confidence > 0.6:  # Confidence threshold
                # Save previous section if it has content
                if current_section and any(s.strip() for s in current_section):
                    section_text = '\n'.join(current_section).strip()
                    sections.append({
                        'title': current_title,
                        'content': section_text,
                        'metadata': {
                            'section_type': 'content',
                            'title_confidence': current_confidence
                        }
                    })
                
                # Start new section
                current_title = line
                current_confidence = confidence
                current_section = []
            else:
                current_section.append(line)
        
        # Add the last section
        if current_section and any(s.strip() for s in current_section):
            section_text = '\n'.join(current_section).strip()
            sections.append({
                'title': current_title,
                'content': section_text,
                'metadata': {
                    'section_type': 'content',
                    'title_confidence': current_confidence
                }
            })
        
        return sections
    
    def _is_title_with_confidence(self, text: str) -> Tuple[bool, float]:
        """Check if text is a title with confidence score"""
        for pattern, confidence in self.title_patterns:
            if re.match(pattern, text, re.MULTILINE):
                return True, confidence
        return False, 0.0
    
    def _split_large_section(self, content: str) -> List[str]:
        """Split large sections with proper overlap"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        return text_splitter.split_text(content)
    
    def _fallback_split(self, text: str, source: str) -> List[Document]:
        """Fallback splitting method"""
        self.logger.warning(f"Using fallback splitting for {source}")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap
        )
        return text_splitter.create_documents([text], [{'source': source, 'splitting_strategy': 'fallback'}])

class EnhancedVectorStore:
    """Enhanced vector store with evaluation and monitoring"""
    
    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.embeddings = self._initialize_embeddings()
        self.vector_store = None
        self.metadata_store = {}
        self.evaluation_metrics = EvaluationMetrics()
        
    def _initialize_embeddings(self) -> HuggingFaceEmbeddings:
        """Initialize embeddings with error handling"""
        try:
            return HuggingFaceEmbeddings(
                model_name=self.config.embedding_model,
                model_kwargs={
                    'device': self.config.device,
                    'trust_remote_code': True
                },
                encode_kwargs={'batch_size': self.config.batch_size}
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize embeddings: {e}")
            # Fallback to basic model
            return HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
    
    def process_documents(self, documents: List[Document]) -> FAISS:
        """Process documents with batching and error handling"""
        try:
            # Validate documents
            valid_docs = [doc for doc in documents if doc.page_content.strip()]
            if not valid_docs:
                raise ValueError("No valid documents to process")
            
            # Limit chunks per document
            if len(valid_docs) > self.config.max_chunks_per_doc:
                self.logger.warning(f"Limiting to {self.config.max_chunks_per_doc} chunks")
                valid_docs = valid_docs[:self.config.max_chunks_per_doc]
            
            # Process in batches
            self.vector_store = FAISS.from_documents(valid_docs, self.embeddings)
            
            # Store metadata
            self.metadata_store = {
                'total_documents': len(valid_docs),
                'processing_time': datetime.now().isoformat(),
                'config': asdict(self.config)
            }
            
            self.logger.info(f"Successfully processed {len(valid_docs)} documents")
            return self.vector_store
            
        except Exception as e:
            self.logger.error(f"Error processing documents: {e}")
            raise
    
    def enhanced_search(self, query: str, k: int = 5, 
                       filter_metadata: Optional[Dict] = None,
                       similarity_threshold: Optional[float] = None) -> List[Tuple[Document, float]]:
        """Enhanced search with filtering and thresholding"""
        if not self.vector_store:
            raise ValueError("Vector store not initialized")
        
        try:
            # Get similarity search results
            results = self.vector_store.similarity_search_with_score(query, k=k*2)  # Get more for filtering
            
            # Apply similarity threshold
            threshold = similarity_threshold or self.config.similarity_threshold
            results = [(doc, score) for doc, score in results if score >= threshold]
            
            # Filter by metadata if provided
            if filter_metadata:
                filtered_results = []
                for doc, score in results:
                    if self._matches_metadata_filter(doc.metadata, filter_metadata):
                        filtered_results.append((doc, score))
                results = filtered_results
            
            # Return top k results
            return results[:k]
            
        except Exception as e:
            self.logger.error(f"Error during search: {e}")
            return []
    
    def _matches_metadata_filter(self, doc_metadata: Dict, filter_metadata: Dict) -> bool:
        """Check if document metadata matches filter"""
        for key, value in filter_metadata.items():
            if key not in doc_metadata:
                return False
            
            doc_value = doc_metadata[key]
            if isinstance(value, list):
                if doc_value not in value:
                    return False
            elif isinstance(value, str) and isinstance(doc_value, str):
                if value.lower() not in doc_value.lower():
                    return False
            elif doc_value != value:
                return False
        
        return True
    
    def evaluate_retrieval(self, test_queries: List[Dict]) -> Dict[str, float]:
        """Evaluate retrieval performance"""
        if not test_queries:
            return {}
        
        all_metrics = []
        
        for query_data in test_queries:
            query = query_data['query']
            relevant_docs = query_data.get('relevant_docs', [])
            
            # Perform search
            results = self.enhanced_search(query, k=10)
            retrieved_docs = [doc.metadata.get('source', '') for doc, _ in results]
            
            # Calculate metrics
            metrics = self.evaluation_metrics.calculate_retrieval_metrics(
                relevant_docs, retrieved_docs
            )
            all_metrics.append(metrics)
        
        # Average metrics
        avg_metrics = {}
        for metric in ['precision', 'recall', 'f1']:
            avg_metrics[f'avg_{metric}'] = np.mean([m[metric] for m in all_metrics])
        
        return avg_metrics
    
    def get_store_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics about the vector store"""
        if not self.vector_store:
            return {}
        
        stats = {
            'total_vectors': self.vector_store.index.ntotal,
            'embedding_dimension': self.vector_store.index.d,
            'metadata_store': self.metadata_store,
            'config': asdict(self.config)
        }
        
        return stats
    
    def save_store(self, path: str, include_metadata: bool = True):
        """Save vector store with metadata"""
        if not self.vector_store:
            raise ValueError("No vector store to save")
        
        try:
            # Save FAISS index
            self.vector_store.save_local(path)
            
            # Save metadata if requested
            if include_metadata:
                metadata_path = Path(path) / "metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(self.metadata_store, f, indent=2)
            
            self.logger.info(f"Vector store saved to {path}")
            
        except Exception as e:
            self.logger.error(f"Error saving vector store: {e}")
            raise
    
    @classmethod
    def load_store(cls, path: str, config: VectorStoreConfig) -> 'EnhancedVectorStore':
        """Load vector store with metadata"""
        instance = cls(config)
        
        try:
            # Load FAISS index
            instance.vector_store = FAISS.load_local(
                path, 
                instance.embeddings,
                allow_dangerous_deserialization=True
            )
            
            # Load metadata if available
            metadata_path = Path(path) / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    instance.metadata_store = json.load(f)
            
            instance.logger.info(f"Vector store loaded from {path}")
            return instance
            
        except Exception as e:
            instance.logger.error(f"Error loading vector store: {e}")
            raise

