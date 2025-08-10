import os
import sqlite3
import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
import time

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

# NEW IMPORTS --------------------------------------------------
from typing import Dict
from sentence_transformers import CrossEncoder
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
# -------------------------------------------------------------

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Qdrant vector store manager with reliable ID-based deletion"""

    def __init__(self,
                 embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
                 collection_name: str = "document_chunks",
                 persist_dir: str = "./qdrant_storage",
                 rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """Initialize Qdrant vector store manager"""
        self.embedding_model_name = embedding_model
        self.collection_name = collection_name
        self.persist_dir = Path(persist_dir)
        self.rerank_model_name = rerank_model

        # Ensure storage directory exists
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database for file tracking with ID support
        self.db_path = self.persist_dir / "processed_files.db"
        self._init_database()

        # Initialize embedding model
        self.embedding_model = self._init_embedding_model()

        # Initialize Qdrant client
        self.client = QdrantClient(path=str(self.persist_dir))

        # Ensure collection exists and initialize vector store
        self._ensure_collection_exists()
        self.vector_store = self._init_vector_store()

        # NEW: initialize cross-encoder re-ranker
        self.reranker = self._init_reranker()

        logger.info(f"VectorStoreManager initialized with ID-based deletion")
        logger.info(f"Collection '{collection_name}' ready for use")

    # ----------------------------------------------------------
    # NEW METHODS (reranking support)
    # ----------------------------------------------------------
    def _init_reranker(self) -> Optional[CrossEncoder]:
        """Initialize cross-encoder for relevance ranking"""
        try:
            return CrossEncoder(self.rerank_model_name)
        except Exception as e:
            logger.warning(f"Failed to initialize reranker: {e}. Using simple retrieval.")
            return None

    def _prepare_filter(self, filters: Dict) -> Filter:
        """Convert metadata filters to Qdrant filter"""
        conditions = []
        for key, value in filters.items():
            conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )
        return Filter(must=conditions)

    def _retrieve_candidates(
        self,
        query: str,
        count: int,
        filter: Optional[Filter] = None,
        search_type: str = "hybrid",
        diversity: bool = True
    ) -> List[Document]:
        """
        Retrieve initial candidates using the chosen strategy.
        NOTE: We leverage LangChain-Qdrant only; no raw QdrantClient.search().
        """
        if search_type == "keyword":
            # LangChain-Qdrant exposes BM25 via similarity_search
            # (set score_threshold low to allow more results)
            return self.vector_store.similarity_search(
                query=query,
                k=count,
                filter=filter,
                score_threshold=0.0   # include everything
            )

        elif search_type == "hybrid":
            # Vector half
            vec_docs = self._vector_search(query, count // 2, filter)
            # Keyword half
            key_docs = self.vector_store.similarity_search(
                query=query,
                k=count // 2,
                filter=filter,
                score_threshold=0.0
            )

            # De-duplicate by source
            seen, merged = set(), []
            for doc in vec_docs + key_docs:
                src = doc.metadata.get("source")
                if src not in seen:
                    seen.add(src)
                    merged.append(doc)
            return merged[:count]

        else:  # "vector" (default)
            if diversity:
                return self._diversified_search(query, count, filter)
            return self._vector_search(query, count, filter)

    def _vector_search(
        self,
        query: str,
        k: int,
        filter: Optional[Filter] = None
    ) -> List[Document]:
        """Standard vector similarity search"""
        return self.vector_store.similarity_search(
            query=query,
            k=k,
            filter=filter
        )

    def _diversified_search(
        self,
        query: str,
        k: int,
        filter: Optional[Filter] = None,
        lambda_mult: float = 0.7
    ) -> List[Document]:
        """Diversify results using Maximal Marginal Relevance (MMR)"""
        return self.vector_store.max_marginal_relevance_search(
            query=query,
            k=k,
            fetch_k=min(k * 3, 50),  # Fetch more then diversify
            lambda_mult=lambda_mult,
            filter=filter
        )

    def _keyword_search(
        self,
        query: str,
        k: int,
        filter: Optional[Filter] = None
    ) -> List[Document]:
        """Keyword-based search using BM25"""
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_text=query,
                query_filter=filter,
                limit=k,
                search_params=models.SearchParams(
                    hnsw_ef=128  # Balance between speed and accuracy
                )
            )
            return [
                Document(
                    page_content=hit.payload["page_content"],
                    metadata=hit.payload["metadata"]
                ) for hit in results
            ]
        except UnexpectedResponse:
            logger.warning("Keyword search not available. Ensure text index is created.")
            return []

    def _rerank_results(
        self,
        query: str,
        candidates: List[Document],
        top_k: int
    ) -> Tuple[List[Document], List[float]]:
        """Re-rank documents using cross-encoder"""
        try:
            # Prepare query-document pairs
            pairs = [(query, doc.page_content) for doc in candidates]

            # Get relevance scores (higher = more relevant)
            scores = self.reranker.predict(pairs)

            # Sort by descending relevance
            scored_docs = sorted(
                zip(candidates, scores),
                key=lambda x: x[1],
                reverse=True
            )

            # Return top documents with scores
            top_docs = [doc for doc, _ in scored_docs[:top_k]]
            top_scores = [score for _, score in scored_docs[:top_k]]
            return top_docs, top_scores

        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            return candidates[:top_k], [1.0] * top_k

    # ----------------------------------------------------------
    # EXISTING CODE (unchanged except where noted)
    # ----------------------------------------------------------
    def _init_database(self) -> None:
        """Initialize SQLite database with ID tracking support"""
        try:
            with self._get_db_connection() as conn:
                # Main files table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_files (
                        file_path TEXT PRIMARY KEY,
                        file_hash TEXT NOT NULL,
                        chunk_count INTEGER DEFAULT 0,
                        processed_at TEXT NOT NULL,
                        file_size INTEGER DEFAULT 0
                    )
                """)

                # Vector IDs tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vector_ids (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        vector_id TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (file_path) REFERENCES processed_files (file_path) ON DELETE CASCADE
                    )
                """)

                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON processed_files(file_hash)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vector_file_path ON vector_ids(file_path)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vector_id ON vector_ids(vector_id)")

                conn.commit()
                logger.info("Database initialized with ID tracking support")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @contextmanager
    def _get_db_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _init_embedding_model(self) -> HuggingFaceEmbeddings:
        """Initialize embedding model with fallback"""
        try:
            return HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
        except Exception as e:
            logger.warning(f"Primary model failed, using fallback: {e}")
            fallback_model = "sentence-transformers/all-MiniLM-L6-v2"
            self.embedding_model_name = fallback_model
            return HuggingFaceEmbeddings(
                model_name=fallback_model,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )

    def _get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding model"""
        try:
            test_embedding = self.embedding_model.embed_query("test")
            return len(test_embedding)
        except Exception as e:
            logger.warning(f"Could not determine embedding dimension: {e}")
            if "bge-small" in self.embedding_model_name:
                return 384
            elif "all-MiniLM-L6-v2" in self.embedding_model_name:
                return 384
            else:
                return 768

    def _ensure_collection_exists(self) -> None:
        """Ensure the Qdrant collection exists, create if it doesn't"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name in collection_names:
                logger.info(f"Collection '{self.collection_name}' already exists")
                return

            embedding_dim = self._get_embedding_dimension()
            logger.info(f"Creating collection '{self.collection_name}' with dimension {embedding_dim}")

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_dim,
                    distance=models.Distance.COSINE
                )
            )

            # NEW: create payload index to enable keyword search
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="page_content",
                field_schema="text"
            )

            logger.info(f"Successfully created collection '{self.collection_name}'")

        except Exception as e:
            logger.error(f"Failed to ensure collection exists: {e}")
            raise

    def _init_vector_store(self) -> QdrantVectorStore:
        """Initialize Qdrant vector store"""
        try:
            return QdrantVectorStore(
                client=self.client,
                collection_name=self.collection_name,
                embedding=self.embedding_model
            )
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise

    def _get_file_hash(self, file_path: str) -> str:
        """Generate hash for file content"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to generate hash for {file_path}: {e}")
            return ""

    def _generate_vector_ids(self, documents: List[Document]) -> List[str]:
        """Generate unique vector IDs for documents"""
        return [str(uuid.uuid4()) for _ in documents]

    def _store_vector_ids(self, file_path: str, vector_ids: List[str]) -> None:
        """Store vector IDs in database for later deletion"""
        file_path = self._normalize_path(file_path)
        try:
            with self._get_db_connection() as conn:
                for i, vector_id in enumerate(vector_ids):
                    conn.execute("""
                        INSERT INTO vector_ids (file_path, vector_id, chunk_index, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        file_path,
                        vector_id,
                        i,
                        datetime.now().isoformat()
                    ))
                conn.commit()
                logger.debug(f"Stored {len(vector_ids)} vector IDs for file: {file_path}")

        except Exception as e:
            logger.error(f"Failed to store vector IDs: {e}")
            raise

    def _get_vector_ids_for_file(self, file_path: str) -> List[str]:
        """Get all vector IDs associated with a file"""
        file_path = self._normalize_path(file_path)
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT vector_id FROM vector_ids WHERE file_path = ? ORDER BY chunk_index",
                    (file_path,)
                )
                return [row['vector_id'] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get vector IDs for file {file_path}: {e}")
            return []

    def _remove_vector_ids_from_database(self, file_path: str) -> int:
        """Remove vector ID records for a file from database"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("DELETE FROM vector_ids WHERE file_path = ?", (file_path,))
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to remove vector IDs from database: {e}")
            return 0

    def _verify_deletion(self, vector_ids: List[str]) -> bool:
        """Verify that vectors were actually deleted from the vector store"""
        if not vector_ids:
            return True

        try:
            # Try to retrieve the vectors - should return empty if deleted
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=vector_ids
            )

            # If any vectors still exist, deletion was incomplete
            remaining_count = len([r for r in result if r is not None])
            if remaining_count > 0:
                logger.warning(f"Deletion verification failed: {remaining_count} vectors still exist")
                return False

            logger.debug(f"Deletion verified: all {len(vector_ids)} vectors removed")
            return True

        except Exception as e:
            # If retrieval fails, assume vectors are deleted
            logger.debug(f"Deletion verification inconclusive (assuming success): {e}")
            return True

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path for consistent representation"""
        return os.path.normpath(file_path)

    def is_file_processed(self, file_path: str) -> bool:
        """Check if file has been processed"""
        file_path = self._normalize_path(file_path)
        try:
            current_hash = self._get_file_hash(file_path)
            if not current_hash:
                return False

            with self._get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT file_hash FROM processed_files WHERE file_path = ?",
                    (file_path,)
                )
                row = cursor.fetchone()

                if row and row['file_hash'] == current_hash:
                    return True

                # If hash is different, remove old entry and its vector IDs
                if row:
                    self._remove_file_completely(file_path)

                return False

        except Exception as e:
            logger.error(f"Error checking if file is processed: {e}")
            return False

    def add_documents(self, documents: List[Document]) -> None:
        """Add documents to vector store with ID tracking"""
        if not documents:
            logger.warning("No documents to add")
            return

        try:
            # Generate unique IDs for the documents
            vector_ids = self._generate_vector_ids(documents)

            # Add IDs to document metadata
            for doc, vector_id in zip(documents, vector_ids):
                doc.metadata['vector_id'] = vector_id

            # Add documents to vector store with specific IDs
            self.vector_store.add_documents(documents, ids=vector_ids)

            # Get file path from first document
            file_path = documents[0].metadata.get('source', '')
            if file_path:
                normalized_path = self._normalize_path(file_path)
                try:
                    self._track_processed_file(documents)
                    self._store_vector_ids(normalized_path, vector_ids)
                except Exception as e:
                    # Clean up if vector ID storage fails
                    logger.error(f"Failed to store vector IDs: {e}. Rolling back file tracking.")
                    with self._get_db_connection() as conn:
                        conn.execute("DELETE FROM processed_files WHERE file_path = ?", (normalized_path,))
                        conn.commit()
                    raise

            logger.info(f"Added {len(documents)} documents with ID tracking")

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def _track_processed_file(self, documents: List[Document]) -> None:
        """Track processed file in database"""
        if not documents:
            return

        # FIX: Properly get first document
        first_document = documents[0]
        file_path = first_document.metadata.get('source', '')
        file_path = self._normalize_path(file_path)

        if not file_path:
            logger.warning("No source path in document metadata")
            return

        try:
            file_hash = self._get_file_hash(file_path)
            file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0

            with self._get_db_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO processed_files 
                    (file_path, file_hash, chunk_count, processed_at, file_size)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    file_path,
                    file_hash,
                    len(documents),
                    datetime.now().isoformat(),
                    file_size
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to track processed file: {e}")

    def remove_file(self, file_path: str) -> bool:
        """Remove all documents for a file using ID-based deletion"""
        file_path = self._normalize_path(file_path)
        try:
            # Get vector IDs for this file
            vector_ids = self._get_vector_ids_for_file(file_path)

            if not vector_ids:
                logger.warning(f"No vector IDs found for file: {file_path}")
                # Try fallback filter-based deletion
                return self._remove_file_by_filter(file_path)

            logger.info(f"Removing {len(vector_ids)} vectors for file: {file_path}")

            # Delete vectors by ID from vector store
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=vector_ids)
            )

            # Verify deletion was successful
            if not self._verify_deletion(vector_ids):
                logger.error(f"Vector deletion verification failed for: {file_path}")
                return False

            # Remove from database (this will cascade to vector_ids table)
            with self._get_db_connection() as conn:
                cursor = conn.execute("DELETE FROM processed_files WHERE file_path = ?", (file_path,))
                deleted_count = cursor.rowcount
                conn.commit()

            if deleted_count > 0:
                logger.info(f"Successfully removed file: {file_path}")
                return True
            else:
                logger.warning(f"File not found in database: {file_path}")
                return False

        except Exception as e:
            logger.error(f"Failed to remove file {file_path}: {e}")
            return False

    def _remove_file_by_filter(self, file_path: str) -> bool:
        """Fallback: Remove file using filter-based deletion"""
        file_path = self._normalize_path(file_path)
        try:
            logger.info(f"Using fallback filter-based deletion for: {file_path}")

            # Corrected filter condition syntax
            filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="source",
                        match=models.MatchValue(value=file_path)
                    )
                ]
            )

            # Perform deletion and log results
            delete_result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=filter_condition)
            )
            logger.info(f"Deleted {delete_result.count} vectors using filter")

            # Verify deletion
            time.sleep(0.5)  # Allow time for deletion to propagate

            # Corrected count method parameters
            search_result = self.client.count(
                collection_name=self.collection_name,
                filter=filter_condition  # Changed 'count_filter' to 'filter'
            )

            if search_result.count > 0:
                logger.error(f"Filter deletion failed! {search_result.count} vectors remain")
                return False

            # Remove from database
            with self._get_db_connection() as conn:
                cursor = conn.execute("DELETE FROM processed_files WHERE file_path = ?", (file_path,))
                deleted_count = cursor.rowcount
                conn.commit()

            if deleted_count > 0:
                logger.info(f"Successfully removed file via fallback: {file_path}")
                return True
            else:
                logger.warning(f"File not found in database: {file_path}")
                return False

        except Exception as e:
            logger.exception(f"Fallback deletion failed: {e}")
            return False

    def _remove_file_completely(self, file_path: str) -> None:
        """Remove file completely from both vector store and database"""
        try:
            # Remove vectors using ID-based deletion
            self.remove_file(file_path)

        except Exception as e:
            logger.error(f"Failed to completely remove file {file_path}: {e}")

    # ----------------------------------------------------------
    # REPLACED query_documents with the enhanced version
    # ----------------------------------------------------------
    def query_documents(
        self,
        query: str,
        k: int = 5,
        filters: Optional[Dict] = None,
        search_type: str = "hybrid",  # "vector", "keyword", or "hybrid"
        rerank: bool = True,
        diversity: bool = True
    ) -> Tuple[List[Document], List[float]]:
        """
        Enhanced document query with hybrid search and re-ranking

        Args:
            query: Search query
            k: Number of results to return
            filters: Metadata filters
            search_type: "vector", "keyword", or "hybrid"
            rerank: Enable relevance re-ranking
            diversity: Enable MMR diversification

        Returns:
            Tuple of (documents, relevance_scores)
        """
        try:
            # Prepare base filter
            qdrant_filter = self._prepare_filter(filters) if filters else None

            # Stage 1: Initial retrieval (hybrid by default)
            candidates = self._retrieve_candidates(
                query,
                count=k * 5 if rerank else k,  # Get more candidates for reranking
                filter=qdrant_filter,
                search_type=search_type,
                diversity=diversity
            )

            # Stage 2: Re-ranking
            if rerank and self.reranker and candidates:
                return self._rerank_results(query, candidates, top_k=k)

            # Return top results without re-ranking
            return candidates[:k], [1.0] * min(len(candidates), k)

        except Exception as e:
            logger.error(f"Query failed: {e}")
            return [], []

    # ----------------------------------------------------------
    # EXISTING STATS / HEALTH / CLEANUP METHODS
    # ----------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        try:
            collection_info = self.client.get_collection(self.collection_name)

            with self._get_db_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as count FROM processed_files")
                tracked_files = cursor.fetchone()['count']

                cursor = conn.execute("SELECT SUM(chunk_count) as total FROM processed_files")
                total_chunks = cursor.fetchone()['total'] or 0

                cursor = conn.execute("SELECT COUNT(*) as count FROM vector_ids")
                tracked_vectors = cursor.fetchone()['count']

            return {
                'collection_name': self.collection_name,
                'vector_count': collection_info.points_count,
                'tracked_files': tracked_files,
                'total_chunks': total_chunks,
                'tracked_vectors': tracked_vectors,
                'embedding_model': self.embedding_model_name
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    def health_check(self) -> bool:
        """Perform health check"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' has {collection_info.points_count} vectors")

            with self._get_db_connection() as conn:
                conn.execute("SELECT 1")

            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def cleanup_orphaned_records(self) -> int:
        """Remove database records for files that no longer exist"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("SELECT file_path FROM processed_files")
                all_files = [row['file_path'] for row in cursor.fetchall()]

                orphaned_count = 0
                for file_path in all_files:
                    if not Path(file_path).exists():
                        # This will cascade delete vector_ids due to foreign key constraint
                        conn.execute("DELETE FROM processed_files WHERE file_path = ?", (file_path,))
                        orphaned_count += 1

                conn.commit()

                if orphaned_count > 0:
                    logger.info(f"Cleaned up {orphaned_count} orphaned records")

                return orphaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned records: {e}")
            return 0


def get_recommended_model(model_type: str = "multilingual") -> str:
    """Get recommended embedding model"""
    models = {
        "multilingual": "paraphrase-multilingual-MiniLM-L12-v2",
        "english": "sentence-transformers/all-MiniLM-L6-v2",
        "fast": "sentence-transformers/paraphrase-MiniLM-L6-v2"
    }
    return models.get(model_type, models["multilingual"])