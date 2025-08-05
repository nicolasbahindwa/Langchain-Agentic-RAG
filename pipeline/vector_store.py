 
# from typing import List, Dict, Any, Optional, Tuple
# from langchain_core.documents import Document
# from langchain_qdrant import Qdrant
# from langchain_huggingface import HuggingFaceEmbeddings
# from qdrant_client import QdrantClient
# from qdrant_client.http import models
# from qdrant_client.http.exceptions import UnexpectedResponse
# import os
# import hashlib
# from utils.logger import get_enhanced_logger

# logger = get_enhanced_logger("VectorStoreManager")

# class VectorStoreManager:
#     """Manages Qdrant vector store operations with local persistence"""
    
#     def __init__(self, 
#                  embedding_model: str = "BAAI/bge-small-en-v1.5",
#                  collection_name: str = "document_chunks",
#                  persist_dir: str = "./qdrant_storage"):
#         """
#         Initialize Qdrant vector store manager with HuggingFace embeddings
        
#         Args:
#             embedding_model: Valid HuggingFace embedding model
#             collection_name: Qdrant collection name
#             persist_dir: Directory for local Qdrant storage
#         """
#         self.embedding_model_name = embedding_model
#         self.collection_name = collection_name
#         self.persist_dir = persist_dir
        
#         # Ensure storage directory exists
#         os.makedirs(persist_dir, exist_ok=True)
        
#         logger.info(f"Loading HuggingFace embedding model: {embedding_model}")
        
#         try:
#             self.embedding_model = HuggingFaceEmbeddings(
#                 model_name=embedding_model,
#                 model_kwargs={'device': 'cpu'},
#                 encode_kwargs={'normalize_embeddings': True}
#             )
#         except Exception as e:
#             logger.failure(f"Model load failed: {str(e)}. Using fallback model.")
#             self.embedding_model = HuggingFaceEmbeddings(
#                 model_name="BAAI/bge-small-en-v1.5",
#                 model_kwargs={'device': 'cpu'},
#                 encode_kwargs={'normalize_embeddings': True}
#             )
#             self.embedding_model_name = "BAAI/bge-small-en-v1.5"
        
#         # Get actual embedding dimension
#         self.embedding_dim = self._get_embedding_dimension()
#         logger.info(f"Embedding dimension: {self.embedding_dim}")
        
#         # Initialize Qdrant client and vector store
#         self.client = QdrantClient(path=persist_dir)
#         self.vector_store = self._initialize_vector_store()
    
#     def _get_embedding_dimension(self) -> int:
#         """Get actual embedding dimension by testing the model"""
#         try:
#             test_embedding = self.embedding_model.embed_query("test")
#             actual_dim = len(test_embedding)
#             logger.info(f"Actual embedding dimension: {actual_dim}")
#             return actual_dim
#         except Exception as e:
#             logger.failure(f"Failed to get embedding dimension: {e}")
#             # Fallback to known dimensions
#             dimension_map = {
#                 "BAAI/bge-small-en-v1.5": 384,
#                 "sentence-transformers/all-MiniLM-L6-v2": 384,
#                 "BAAI/bge-base-en-v1.5": 768,
#                 "BAAI/bge-large-en-v1.5": 1024,
#             }
#             return dimension_map.get(self.embedding_model_name, 384)
    
#     def _initialize_vector_store(self) -> Qdrant:
#         """Initialize Qdrant vector store with dimension validation"""
#         try:
#             # Check if collection exists
#             collection_info = self.client.get_collection(self.collection_name)
#             existing_dim = collection_info.config.params.vectors.size
            
#             if existing_dim != self.embedding_dim:
#                 logger.warning(f"Dimension mismatch: Collection has {existing_dim}, model has {self.embedding_dim}")
#                 logger.warning("Recreating collection with correct dimensions...")
                
#                 # Delete and recreate collection with correct dimensions
#                 self.client.delete_collection(self.collection_name)
#                 self._create_collection()
#                 logger.info(f"Recreated collection with dimension {self.embedding_dim}")
#             else:
#                 logger.info(f"Using existing collection: {self.collection_name}")
                
#         except UnexpectedResponse as e:
#             if "doesn't exist" in str(e).lower() or e.status_code == 404:
#                 logger.info(f"Collection {self.collection_name} doesn't exist, creating new one")
#                 self._create_collection()
#             else:
#                 logger.failure(f"Unexpected error checking collection: {e}")
#                 raise
#         except Exception as e:
#             logger.failure(f"Error initializing collection: {e}")
#             self._create_collection()

#         return Qdrant(
#             client=self.client,
#             collection_name=self.collection_name,
#             embeddings=self.embedding_model
#         )
    
#     def _create_collection(self):
#         """Create a new collection with the correct vector dimensions"""
#         self.client.create_collection(
#             collection_name=self.collection_name,
#             vectors_config=models.VectorParams(
#                 size=self.embedding_dim,
#                 distance=models.Distance.COSINE
#             )
#         )
#         logger.info(f"Created collection '{self.collection_name}' with dimension {self.embedding_dim}")
    
#     def add_documents(self, chunks: List[Document]) -> None:
#         """
#         Add processed document chunks to Qdrant vector store with error handling
        
#         Args:
#             chunks: List of chunked Document objects
#         """
#         if not chunks:
#             logger.warning("No chunks provided for vector store")
#             return
        
#         try:
#             # Validate chunks have content
#             valid_chunks = [chunk for chunk in chunks if chunk.page_content.strip()]
#             if len(valid_chunks) != len(chunks):
#                 logger.warning(f"Filtered out {len(chunks) - len(valid_chunks)} empty chunks")
            
#             if not valid_chunks:
#                 logger.warning("No valid chunks to add")
#                 return
            
#             # Add documents to Qdrant with automatic embedding
#             self.vector_store.add_documents(valid_chunks)
#             logger.info(f"✅ Successfully added {len(valid_chunks)} chunks to Qdrant store")
            
#         except Exception as e:
#             logger.failure(f"❌ Qdrant update failed: {str(e)}")
#             # If dimension error, try to recreate collection
#             if "broadcast" in str(e) or "dimension" in str(e).lower():
#                 logger.warning("Attempting to fix dimension mismatch...")
#                 try:
#                     self.client.delete_collection(self.collection_name)
#                     self.vector_store = self._initialize_vector_store()
#                     self.vector_store.add_documents(valid_chunks)
#                     logger.info("✅ Successfully added chunks after collection recreation")
#                 except Exception as retry_error:
#                     logger.failure(f"❌ Failed even after recreation: {retry_error}")
    
#     def delete_documents(self, filter_conditions: Dict[str, Any]) -> None:
#         """
#         Remove documents from vector store using Qdrant filters with safety checks
        
#         Args:
#             filter_conditions: Qdrant filter expression
#         """
#         try:
#             # Check if collection has any points before deletion
#             collection_info = self.client.get_collection(self.collection_name)
#             if collection_info.points_count == 0:
#                 logger.info("Collection is empty, no documents to delete")
#                 return
            
#             # Build filter object
#             qdrant_filter = models.Filter(**filter_conditions)
            
#             # Delete points matching the filter
#             result = self.client.delete(
#                 collection_name=self.collection_name,
#                 points_selector=models.FilterSelector(filter=qdrant_filter)
#             )
            
#             logger.info(f"✅ Removed documents from vector store (operation_id: {result.operation_id})")
            
#         except Exception as e:
#             logger.failure(f"❌ Qdrant deletion failed: {str(e)}")
    
#     def query_documents(self, 
#                        query: str, 
#                        k: int = 5, 
#                        filters: Optional[Dict[str, Any]] = None) -> List[Document]:
#         """
#         Perform similarity search with error handling
#         """
#         try:
#             # Check if collection has documents
#             collection_info = self.client.get_collection(self.collection_name)
#             if collection_info.points_count == 0:
#                 logger.warning("Collection is empty, no documents to search")
#                 return []
            
#             logger.info(f"Querying vector store with: '{query}' (k={k})")
#             results = self.vector_store.similarity_search(
#                 query=query,
#                 k=k,
#                 filter=filters
#             )
#             logger.info(f"✅ Found {len(results)} matching documents")
#             return results
#         except Exception as e:
#             logger.failure(f"❌ Qdrant query failed: {str(e)}")
#             return []
    
#     def query_documents_with_scores(self, 
#                                   query: str, 
#                                   k: int = 5, 
#                                   filters: Optional[Dict[str, Any]] = None) -> List[Tuple[Document, float]]:
#         """
#         Perform similarity search with similarity scores
#         """
#         try:
#             collection_info = self.client.get_collection(self.collection_name)
#             if collection_info.points_count == 0:
#                 logger.warning("Collection is empty, no documents to search")
#                 return []
                
#             logger.info(f"Querying vector store with scores: '{query}' (k={k})")
#             results = self.vector_store.similarity_search_with_score(
#                 query=query,
#                 k=k,
#                 filter=filters
#             )
#             logger.info(f"✅ Found {len(results)} matching documents with scores")
#             return results
#         except Exception as e:
#             logger.failure(f"❌ Qdrant query with scores failed: {str(e)}")
#             return []
    
#     def get_collection_info(self) -> Dict[str, Any]:
#         """Get statistics about the Qdrant collection with error handling"""
#         try:
#             info = self.client.get_collection(self.collection_name)
#             collection_stats = {
#                 "vectors_count": info.vectors_count,
#                 "points_count": info.points_count,
#                 "embedding_dimension": self.embedding_dim,
#                 "embedding_model": self.embedding_model_name,
#                 "collection_status": info.status,
#                 "config": {
#                     "vector_size": info.config.params.vectors.size,
#                     "distance": info.config.params.vectors.distance,
#                     "shard_number": info.config.params.shard_number,
#                     "replication_factor": info.config.params.replication_factor,
#                 }
#             }
#             logger.info(f"Collection stats: {collection_stats['points_count']} documents")
#             return collection_stats
#         except Exception as e:
#             logger.failure(f"❌ Collection info failed: {str(e)}")
#             return {}
    
#     def reset_collection(self) -> None:
#         """Reset collection safely - delete and recreate"""
#         try:
#             logger.warning(f"Resetting collection: {self.collection_name}")
            
#             # Delete collection if it exists
#             try:
#                 self.client.delete_collection(self.collection_name)
#                 logger.info(f"Deleted existing collection: {self.collection_name}")
#             except:
#                 logger.info("Collection didn't exist or was already deleted")
            
#             # Recreate the collection and vector store
#             self.vector_store = self._initialize_vector_store()
#             logger.info(f"✅ Successfully reset collection: {self.collection_name}")
            
#         except Exception as e:
#             logger.failure(f"❌ Failed to reset collection: {str(e)}")
    
#     def health_check(self) -> bool:
#         """Perform a health check on the vector store"""
#         try:
#             # Test embedding generation
#             test_embedding = self.embedding_model.embed_query("health check test")
#             if len(test_embedding) != self.embedding_dim:
#                 logger.failure(f"Embedding dimension mismatch: expected {self.embedding_dim}, got {len(test_embedding)}")
#                 return False
            
#             # Test collection access
#             collection_info = self.client.get_collection(self.collection_name)
#             if collection_info.config.params.vectors.size != self.embedding_dim:
#                 logger.failure(f"Collection dimension mismatch: expected {self.embedding_dim}, got {collection_info.config.params.vectors.size}")
#                 return False
            
#             logger.info("✅ Vector store health check passed")
#             return True
            
#         except Exception as e:
#             logger.failure(f"❌ Health check failed: {str(e)}")
#             return False


# def create_safe_file_hash(file_path: str) -> Optional[str]:
#     """Create file hash with permission error handling"""
#     try:
#         with open(file_path, 'rb') as f:
#             file_hash = hashlib.md5(f.read()).hexdigest()
#         return file_hash
#     except PermissionError:
#         logger.failure(f"Permission denied accessing file: {file_path}")
#         # Use file stats as fallback
#         try:
#             stat = os.stat(file_path)
#             fallback_hash = hashlib.md5(f"{file_path}{stat.st_size}{stat.st_mtime}".encode()).hexdigest()
#             logger.info(f"Using fallback hash for: {file_path}")
#             return fallback_hash
#         except Exception as e:
#             logger.failure(f"Failed to create fallback hash: {e}")
#             return None
#     except Exception as e:
#         logger.failure(f"Failed to hash file {file_path}: {e}")
#         return None


# def get_recommended_model(use_case: str = "general") -> str:
#     """Get recommended embedding model based on use case"""
#     recommendations = {
#         "fast": "sentence-transformers/all-MiniLM-L6-v2",      # 384d, fastest
#         "general": "BAAI/bge-small-en-v1.5",                   # 384d, good balance
#         "quality": "BAAI/bge-base-en-v1.5",                    # 768d, better quality
#         "best": "BAAI/bge-large-en-v1.5",                      # 1024d, best quality
#         "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 384d
#     }
#     return recommendations.get(use_case, "BAAI/bge-small-en-v1.5")


from typing import List, Dict, Any, Optional, Tuple, Set
from langchain_core.documents import Document
from langchain_qdrant import Qdrant
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
import os
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager
from utils.logger import get_enhanced_logger

logger = get_enhanced_logger("VectorStoreManager")

class DatabaseDeduplicationTracker:
    """SQLite-based file deduplication tracker with robust error handling"""
    
    def __init__(self, db_path: str = "./qdrant_storage/processed_files.db"):
        """
        Initialize SQLite database for tracking processed files
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_database()
        logger.info(f"📊 Database deduplication tracker initialized: {db_path}")
    
    def _init_database(self):
        """Initialize database schema with proper constraints and indexes"""
        try:
            with self._get_connection() as conn:
                # Create main table for processed files
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_files (
                        file_hash TEXT PRIMARY KEY,
                        file_path TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        file_extension TEXT,
                        chunk_count INTEGER DEFAULT 0,
                        processed_at TEXT NOT NULL,
                        file_size INTEGER DEFAULT 0,
                        file_modified TEXT,
                        embedding_model TEXT,
                        chunk_strategy TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index for faster lookups
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_name 
                    ON processed_files(file_name)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processed_at 
                    ON processed_files(processed_at)
                """)
                
                # Create table for tracking file chunks (optional detailed tracking)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS file_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_hash TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        chunk_id TEXT,
                        chunk_size INTEGER,
                        structure_type TEXT,
                        heading_context TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (file_hash) REFERENCES processed_files (file_hash) ON DELETE CASCADE,
                        UNIQUE(file_hash, chunk_index)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_chunks_hash 
                    ON file_chunks(file_hash)
                """)
                
                # Database version/metadata table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS db_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Set database version
                conn.execute("""
                    INSERT OR REPLACE INTO db_metadata (key, value, updated_at) 
                    VALUES ('db_version', '1.0', ?)
                """, (datetime.now().isoformat(),))
                
                conn.commit()
                logger.info("✅ Database schema initialized successfully")
                
        except Exception as e:
            logger.failure(f"❌ Failed to initialize database: {e}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
            conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.failure(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def is_file_processed(self, file_hash: str) -> bool:
        """
        Check if a file has already been processed
        
        Args:
            file_hash: MD5 hash of the file
            
        Returns:
            True if file was already processed, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM processed_files WHERE file_hash = ?",
                    (file_hash,)
                )
                result = cursor.fetchone()
                return result['count'] > 0
                
        except Exception as e:
            logger.failure(f"Error checking if file is processed: {e}")
            return False
    
    def get_file_info(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a processed file
        
        Args:
            file_hash: MD5 hash of the file
            
        Returns:
            Dictionary with file information or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM processed_files WHERE file_hash = ?
                """, (file_hash,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.failure(f"Error getting file info: {e}")
            return None
    
    def add_processed_file(self, file_hash: str, file_info: Dict[str, Any], chunks_info: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Add a file to the processed files database with duplicate protection
        """
        try:
            with self._get_connection() as conn:
                # Insert main file record
                conn.execute("""
                    INSERT OR REPLACE INTO processed_files 
                    (file_hash, file_path, file_name, file_extension, chunk_count, 
                    processed_at, file_size, file_modified, embedding_model, chunk_strategy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_hash,
                    file_info.get('file_path', 'unknown'),
                    file_info.get('file_name', 'unknown'),
                    file_info.get('file_extension', ''),
                    file_info.get('chunk_count', 0),
                    file_info.get('processed_at', datetime.now().isoformat()),
                    file_info.get('file_size', 0),
                    file_info.get('file_modified', None),
                    file_info.get('embedding_model', ''),
                    file_info.get('chunk_strategy', 'unknown')
                ))
                
                # Insert chunk details if provided
                if chunks_info:
                    # Use set to track seen chunk indices
                    seen_indices = set()
                    duplicate_count = 0
                    
                    for chunk_info in chunks_info:
                        chunk_index = chunk_info.get('chunk_index', 0)
                        
                        # Skip duplicate indices in same batch
                        if chunk_index in seen_indices:
                            duplicate_count += 1
                            continue
                        
                        seen_indices.add(chunk_index)
                        
                        # Insert with conflict resolution
                        conn.execute("""
                            INSERT INTO file_chunks 
                            (file_hash, chunk_index, chunk_id, chunk_size, structure_type, heading_context)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(file_hash, chunk_index) DO UPDATE SET
                                chunk_id = excluded.chunk_id,
                                chunk_size = excluded.chunk_size,
                                structure_type = excluded.structure_type,
                                heading_context = excluded.heading_context
                        """, (
                            file_hash,
                            chunk_index,
                            chunk_info.get('chunk_id', ''),
                            chunk_info.get('chunk_size', 0),
                            chunk_info.get('structure_type', ''),
                            chunk_info.get('heading_context', '')
                        ))
                    
                    if duplicate_count > 0:
                        logger.warning(f"⚠️ Skipped {duplicate_count} duplicate chunk indices for file {file_hash}")
                    
                conn.commit()
                logger.debug(f"✅ Added processed file to database: {file_info.get('file_name', 'unknown')}")
                return True
                
        except Exception as e:
            logger.failure(f"❌ Error adding processed file to database: {e}")
            return False
        
    def remove_processed_file(self, file_hash: str) -> bool:
        """
        Remove a file from the processed files database
        
        Args:
            file_hash: Hash of the file to remove
            
        Returns:
            True if file was removed, False if not found or error
        """
        try:
            with self._get_connection() as conn:
                # Check if file exists
                cursor = conn.execute(
                    "SELECT file_name FROM processed_files WHERE file_hash = ?",
                    (file_hash,)
                )
                row = cursor.fetchone()
                
                if row:
                    file_name = row['file_name']
                    
                    # Delete from main table (chunks will be deleted via CASCADE)
                    conn.execute("DELETE FROM processed_files WHERE file_hash = ?", (file_hash,))
                    conn.commit()
                    
                    logger.info(f"🗑️ Removed from database: {file_name}")
                    return True
                else:
                    logger.warning(f"File hash not found in database: {file_hash}")
                    return False
                    
        except Exception as e:
            logger.failure(f"❌ Error removing processed file: {e}")
            return False
    
    def get_all_processed_files(self) -> List[Dict[str, Any]]:
        """Get list of all processed files"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM processed_files 
                    ORDER BY processed_at DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.failure(f"Error getting all processed files: {e}")
            return []
    
    def get_processed_files_count(self) -> int:
        """Get count of processed files"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as count FROM processed_files")
                return cursor.fetchone()['count']
                
        except Exception as e:
            logger.failure(f"Error getting processed files count: {e}")
            return 0
    
    def get_files_by_extension(self, extension: str) -> List[Dict[str, Any]]:
        """Get processed files by extension"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM processed_files 
                    WHERE file_extension = ? 
                    ORDER BY processed_at DESC
                """, (extension,))
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.failure(f"Error getting files by extension: {e}")
            return []
    
    def cleanup_old_entries(self, days_old: int = 30) -> int:
        """
        Remove entries older than specified days (use with caution)
        
        Args:
            days_old: Remove entries older than this many days
            
        Returns:
            Number of entries removed
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cutoff_str = cutoff_date.isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM processed_files WHERE processed_at < ?",
                    (cutoff_str,)
                )
                count_to_delete = cursor.fetchone()['count']
                
                if count_to_delete > 0:
                    conn.execute(
                        "DELETE FROM processed_files WHERE processed_at < ?",
                        (cutoff_str,)
                    )
                    conn.commit()
                    
                    logger.warning(f"⚠️ Cleaned up {count_to_delete} old entries (older than {days_old} days)")
                    return count_to_delete
                else:
                    logger.info("No old entries to clean up")
                    return 0
                    
        except Exception as e:
            logger.failure(f"Error during cleanup: {e}")
            return 0
    
    def reset_database(self) -> bool:
        """Reset the entire database (use with extreme caution!)"""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM file_chunks")
                conn.execute("DELETE FROM processed_files")
                conn.commit()
                
                logger.warning("⚠️ Database reset - all tracking data cleared")
                return True
                
        except Exception as e:
            logger.failure(f"❌ Error resetting database: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics"""
        try:
            with self._get_connection() as conn:
                # File counts
                cursor = conn.execute("SELECT COUNT(*) as total FROM processed_files")
                total_files = cursor.fetchone()['total']
                
                cursor = conn.execute("SELECT SUM(chunk_count) as total FROM processed_files")
                total_chunks = cursor.fetchone()['total'] or 0
                
                cursor = conn.execute("SELECT SUM(file_size) as total FROM processed_files")
                total_size = cursor.fetchone()['total'] or 0
                
                # Extension breakdown
                cursor = conn.execute("""
                    SELECT file_extension, COUNT(*) as count 
                    FROM processed_files 
                    GROUP BY file_extension 
                    ORDER BY count DESC
                """)
                extensions = {row['file_extension']: row['count'] for row in cursor.fetchall()}
                
                # Recent activity
                cursor = conn.execute("""
                    SELECT COUNT(*) as count 
                    FROM processed_files 
                    WHERE processed_at >= datetime('now', '-7 days')
                """)
                recent_files = cursor.fetchone()['count']
                
                return {
                    'total_files': total_files,
                    'total_chunks': total_chunks,
                    'total_size_bytes': total_size,
                    'total_size_mb': round(total_size / (1024 * 1024), 2),
                    'extensions_breakdown': extensions,
                    'files_last_7_days': recent_files,
                    'database_path': str(self.db_path),
                    'database_size_mb': round(self.db_path.stat().st_size / (1024 * 1024), 2) if self.db_path.exists() else 0
                }
                
        except Exception as e:
            logger.failure(f"Error getting database stats: {e}")
            return {}


class VectorStoreManager:
    """Enhanced Qdrant vector store manager with SQLite-based deduplication"""
    
    def __init__(self, 
                 embedding_model: str = "BAAI/bge-small-en-v1.5",
                 collection_name: str = "document_chunks",
                 persist_dir: str = "./qdrant_storage",
                 enable_deduplication: bool = True):
        """
        Initialize Qdrant vector store manager with SQLite deduplication
        
        Args:
            embedding_model: Valid HuggingFace embedding model
            collection_name: Qdrant collection name
            persist_dir: Directory for local Qdrant storage
            enable_deduplication: Enable SQLite-based file hash tracking
        """
        self.embedding_model_name = embedding_model
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self.enable_deduplication = enable_deduplication
        
        # Ensure storage directory exists
        os.makedirs(persist_dir, exist_ok=True)
        
        # Initialize SQLite deduplication tracker
        if enable_deduplication:
            db_path = os.path.join(persist_dir, "processed_files.db")
            self.dedup_tracker = DatabaseDeduplicationTracker(db_path)
            logger.info(f"✅ SQLite deduplication enabled")
        else:
            self.dedup_tracker = None
            logger.info("ℹ️ Deduplication disabled")
        
        logger.info(f"Loading HuggingFace embedding model: {embedding_model}")
        
        try:
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=embedding_model,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
        except Exception as e:
            logger.failure(f"Model load failed: {str(e)}. Using fallback model.")
            self.embedding_model = HuggingFaceEmbeddings(
                model_name="BAAI/bge-small-en-v1.5",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            self.embedding_model_name = "BAAI/bge-small-en-v1.5"
        
        # Get actual embedding dimension
        self.embedding_dim = self._get_embedding_dimension()
        logger.info(f"Embedding dimension: {self.embedding_dim}")
        
        # Initialize Qdrant client and vector store
        self.client = QdrantClient(path=persist_dir)
        self.vector_store = self._initialize_vector_store()
        
        if enable_deduplication:
            stats = self.dedup_tracker.get_database_stats()
            logger.info(f"📊 Tracking {stats.get('total_files', 0)} processed files in database")
    
    def is_file_already_processed(self, file_hash: str, file_path: str = None) -> bool:
        """
        Check if a file has already been processed using SQLite database
        
        Args:
            file_hash: MD5 hash of the file
            file_path: Optional file path for logging
            
        Returns:
            True if file was already processed, False otherwise
        """
        if not self.enable_deduplication or not self.dedup_tracker:
            return False
        
        if self.dedup_tracker.is_file_processed(file_hash):
            file_info = self.dedup_tracker.get_file_info(file_hash)
            if file_info:
                logger.info(f"📋 File already processed: {file_path or 'unknown'}")
                logger.info(f"   Original: {file_info.get('file_path', 'unknown')}")
                logger.info(f"   Processed: {file_info.get('processed_at', 'unknown')}")
                logger.info(f"   Chunks: {file_info.get('chunk_count', 0)}")
            return True
        
        return False
    
    def mark_file_as_processed(self, file_hash: str, file_info: Dict[str, Any], 
                              chunks: Optional[List[Document]] = None) -> None:
        """
        Mark a file as processed in the SQLite database
        
        Args:
            file_hash: MD5 hash of the file
            file_info: Dictionary with file information
            chunks: Optional list of processed chunks for detailed tracking
        """
        if not self.enable_deduplication or not self.dedup_tracker:
            return
        
        # Prepare file info for database
        db_file_info = {
            'file_path': file_info.get('file_path', file_info.get('source', 'unknown')),
            'file_name': file_info.get('file_name', 'unknown'),
            'file_extension': file_info.get('file_extension', ''),
            'chunk_count': file_info.get('chunk_count', 0),
            'processed_at': datetime.now().isoformat(),
            'file_size': file_info.get('file_size', 0),
            'file_modified': file_info.get('file_modified', None),
            'embedding_model': self.embedding_model_name,
            'chunk_strategy': file_info.get('chunk_strategy', 'unknown')
        }
        
        # Prepare chunks info for detailed tracking
        chunks_info = []
        if chunks:
            for chunk in chunks:
                chunk_info = {
                    'chunk_index': chunk.metadata.get('chunk_index', 0),
                    'chunk_id': chunk.metadata.get('chunk_id', ''),
                    'chunk_size': chunk.metadata.get('chunk_size', len(chunk.page_content)),
                    'structure_type': chunk.metadata.get('structure_type', ''),
                    'heading_context': chunk.metadata.get('heading_context', '')
                }
                chunks_info.append(chunk_info)
        
        # Add to database
        success = self.dedup_tracker.add_processed_file(file_hash, db_file_info, chunks_info)
        if success:
            logger.debug(f"📝 Marked file as processed in database: {db_file_info.get('file_name', 'unknown')}")
        else:
            logger.warning(f"⚠️ Failed to mark file as processed: {db_file_info.get('file_name', 'unknown')}")
    
    def filter_new_documents(self, chunks: List[Document]) -> List[Document]:
        """
        Filter out chunks from already processed files using SQLite database
        
        Args:
            chunks: List of document chunks
            
        Returns:
            List of chunks from new files only
        """
        if not self.enable_deduplication or not self.dedup_tracker or not chunks:
            return chunks
        
        new_chunks = []
        processed_hashes = set()
        
        for chunk in chunks:
            file_hash = chunk.metadata.get('file_hash')
            if not file_hash:
                logger.warning("Chunk missing file_hash in metadata, adding anyway")
                new_chunks.append(chunk)
                continue
            
            if not self.dedup_tracker.is_file_processed(file_hash):
                new_chunks.append(chunk)
            else:
                processed_hashes.add(file_hash)
        
        if processed_hashes:
            unique_files = len(processed_hashes)
            logger.info(f"🚫 Skipped {len(chunks) - len(new_chunks)} chunks from {unique_files} already processed files")
        
        return new_chunks
    
    def add_documents(self, chunks: List[Document], force_add: bool = False) -> None:
        """
        Add processed document chunks to Qdrant vector store with SQLite deduplication
        
        Args:
            chunks: List of chunked Document objects
            force_add: If True, bypass deduplication checks
        """
        if not chunks:
            logger.warning("No chunks provided for vector store")
            return
        
        try:
            # Filter out already processed files unless forced
            original_chunks = chunks.copy()
            if not force_add:
                original_count = len(chunks)
                chunks = self.filter_new_documents(chunks)
                
                if len(chunks) == 0:
                    logger.info("🚫 All documents already processed, nothing to add")
                    return
                elif len(chunks) < original_count:
                    logger.info(f"📊 Processing {len(chunks)} new chunks (filtered {original_count - len(chunks)})")
            
            # Validate chunks have content
            valid_chunks = [chunk for chunk in chunks if chunk.page_content.strip()]
            if len(valid_chunks) != len(chunks):
                logger.warning(f"Filtered out {len(chunks) - len(valid_chunks)} empty chunks")
            
            if not valid_chunks:
                logger.warning("No valid chunks to add")
                return
            
            # Add documents to Qdrant with automatic embedding
            self.vector_store.add_documents(valid_chunks)
            logger.info(f"✅ Successfully added {len(valid_chunks)} chunks to Qdrant store")
            
            # Update SQLite database registry
            if self.enable_deduplication and not force_add:
                self._update_database_from_chunks(valid_chunks)
            
        except Exception as e:
            logger.failure(f"❌ Qdrant update failed: {str(e)}")
            # If dimension error, try to recreate collection
            if "broadcast" in str(e) or "dimension" in str(e).lower():
                logger.warning("Attempting to fix dimension mismatch...")
                try:
                    self.client.delete_collection(self.collection_name)
                    self.vector_store = self._initialize_vector_store()
                    self.vector_store.add_documents(valid_chunks)
                    logger.info("✅ Successfully added chunks after collection recreation")
                    
                    # Update database after successful retry
                    if self.enable_deduplication and not force_add:
                        self._update_database_from_chunks(valid_chunks)
                        
                except Exception as retry_error:
                    logger.failure(f"❌ Failed even after recreation: {retry_error}")
    
    def _update_database_from_chunks(self, chunks: List[Document]) -> None:
        """Update the SQLite database based on successfully added chunks"""
        if not self.dedup_tracker:
            return
        
        file_info_by_hash = {}
        chunks_by_hash = {}
        
        # Group chunks by file hash
        for chunk in chunks:
            file_hash = chunk.metadata.get('file_hash')
            if not file_hash:
                continue
            
            if file_hash not in file_info_by_hash:
                file_info_by_hash[file_hash] = {
                    'file_path': chunk.metadata.get('source', 'unknown'),
                    'file_name': chunk.metadata.get('file_name', 'unknown'),
                    'file_extension': chunk.metadata.get('file_extension', ''),
                    'file_size': chunk.metadata.get('file_size', 0),
                    'file_modified': chunk.metadata.get('file_modified', None),
                    'chunk_count': 0,
                    'chunk_strategy': chunk.metadata.get('structure_type', 'unknown')
                }
                chunks_by_hash[file_hash] = []
            
            file_info_by_hash[file_hash]['chunk_count'] += 1
            chunks_by_hash[file_hash].append(chunk)
        
        # Mark each file as processed in database
        for file_hash, file_info in file_info_by_hash.items():
            file_chunks = chunks_by_hash.get(file_hash, [])
            self.mark_file_as_processed(file_hash, file_info, file_chunks)
        
        logger.info(f"📝 Updated database with {len(file_info_by_hash)} new files")
    
    def remove_file_from_database(self, file_hash: str) -> bool:
        """
        Remove a file from the SQLite database
        
        Args:
            file_hash: Hash of the file to remove
            
        Returns:
            True if file was removed, False if not found
        """
        if not self.enable_deduplication or not self.dedup_tracker:
            return False
        
        return self.dedup_tracker.remove_processed_file(file_hash)
    
    def delete_documents(self, filter_conditions: Dict[str, Any], update_database: bool = True) -> None:
        """
        Remove documents from vector store and optionally update SQLite database
        
        Args:
            filter_conditions: Qdrant filter expression
            update_database: Whether to remove files from processed database
        """
        try:
            # Check if collection has any points before deletion
            collection_info = self.client.get_collection(self.collection_name)
            if collection_info.points_count == 0:
                logger.info("Collection is empty, no documents to delete")
                return
            
            # If updating database, get file hashes to remove first
            file_hashes_to_remove = set()
            if update_database and self.enable_deduplication and self.dedup_tracker:
                try:
                    qdrant_filter = models.Filter(**filter_conditions)
                    search_result = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=qdrant_filter,
                        limit=1000,  # Adjust as needed
                        with_payload=True
                    )
                    
                    for point in search_result[0]:
                        if point.payload and 'file_hash' in point.payload:
                            file_hashes_to_remove.add(point.payload['file_hash'])
                            
                except Exception as e:
                    logger.warning(f"Failed to get file hashes for database update: {e}")
            
            # Build filter object and delete from Qdrant
            qdrant_filter = models.Filter(**filter_conditions)
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=qdrant_filter)
            )
            
            logger.info(f"✅ Removed documents from vector store (operation_id: {result.operation_id})")
            
            # Update SQLite database
            if update_database and self.enable_deduplication and self.dedup_tracker and file_hashes_to_remove:
                removed_count = 0
                for file_hash in file_hashes_to_remove:
                    if self.dedup_tracker.remove_processed_file(file_hash):
                        removed_count += 1
                logger.info(f"📝 Updated database - removed {removed_count} files")
            
        except Exception as e:
            logger.failure(f"❌ Qdrant deletion failed: {str(e)}")
    
    def get_processed_files_info(self) -> Dict[str, Any]:
        """Get comprehensive information about processed files from SQLite database"""
        if not self.enable_deduplication or not self.dedup_tracker:
            return {"deduplication_enabled": False}
        
        stats = self.dedup_tracker.get_database_stats()
        return {
            "deduplication_enabled": True,
            "database_stats": stats,
            "recent_files": self.dedup_tracker.get_all_processed_files()[:10]  # Last 10 files
        }
    
    def reset_processed_files_database(self) -> None:
        """Reset the SQLite database (use with caution!)"""
        if not self.enable_deduplication or not self.dedup_tracker:
            logger.warning("Deduplication not enabled")
            return
        
        if self.dedup_tracker.reset_database():
            logger.warning("⚠️ Reset processed files database - all files will be considered new")
        else:
            logger.failure("❌ Failed to reset database")
    
    # [Include all other existing methods from original VectorStoreManager]
    def _get_embedding_dimension(self) -> int:
        """Get actual embedding dimension by testing the model"""
        try:
            test_embedding = self.embedding_model.embed_query("test")
            actual_dim = len(test_embedding)
            logger.info(f"Actual embedding dimension: {actual_dim}")
            return actual_dim
        except Exception as e:
            logger.failure(f"Failed to get embedding dimension: {e}")
            # Fallback to known dimensions
            dimension_map = {
                "BAAI/bge-small-en-v1.5": 384,
                "sentence-transformers/all-MiniLM-L6-v2": 384,
                "BAAI/bge-base-en-v1.5": 768,
                "BAAI/bge-large-en-v1.5": 1024,
            }
            return dimension_map.get(self.embedding_model_name, 384)
    
    def _initialize_vector_store(self) -> Qdrant:
        """Initialize Qdrant vector store with dimension validation"""
        try:
            # Check if collection exists
            collection_info = self.client.get_collection(self.collection_name)
            existing_dim = collection_info.config.params.vectors.size
            
            if existing_dim != self.embedding_dim:
                logger.warning(f"Dimension mismatch: Collection has {existing_dim}, model has {self.embedding_dim}")
                logger.warning("Recreating collection with correct dimensions...")
                
                # Delete and recreate collection with correct dimensions
                self.client.delete_collection(self.collection_name)
                self._create_collection()
                logger.info(f"Recreated collection with dimension {self.embedding_dim}")
            else:
                logger.info(f"Using existing collection: {self.collection_name}")
                
        except UnexpectedResponse as e:
            if "doesn't exist" in str(e).lower() or e.status_code == 404:
                logger.info(f"Collection {self.collection_name} doesn't exist, creating new one")
                self._create_collection()
            else:
                logger.failure(f"Unexpected error checking collection: {e}")
                raise
        except Exception as e:
            logger.failure(f"Error initializing collection: {e}")
            self._create_collection()

        return Qdrant(
            client=self.client,
            collection_name=self.collection_name,
            embeddings=self.embedding_model
        )
    
    def _create_collection(self):
        """Create a new collection with the correct vector dimensions"""
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.embedding_dim,
                distance=models.Distance.COSINE
            )
        )
        logger.info(f"Created collection '{self.collection_name}' with dimension {self.embedding_dim}")
    
    def query_documents(self, 
                       query: str, 
                       k: int = 5, 
                       filters: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Perform similarity search with error handling"""
        try:
            # Check if collection has documents
            collection_info = self.client.get_collection(self.collection_name)
            if collection_info.points_count == 0:
                logger.warning("Collection is empty, no documents to search")
                return []
            
            logger.info(f"Querying vector store with: '{query}' (k={k})")
            results = self.vector_store.similarity_search(
                query=query,
                k=k,
                filter=filters
            )
            logger.info(f"✅ Found {len(results)} matching documents")
            return results
        except Exception as e:
            logger.failure(f"❌ Qdrant query failed: {str(e)}")
            return []
    
    def query_documents_with_scores(self, 
                                  query: str, 
                                  k: int = 5, 
                                  filters: Optional[Dict[str, Any]] = None) -> List[Tuple[Document, float]]:
        """Perform similarity search with similarity scores"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            if collection_info.points_count == 0:
                logger.warning("Collection is empty, no documents to search")
                return []
                
            logger.info(f"Querying vector store with scores: '{query}' (k={k})")
            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=k,
                filter=filters
            )
            logger.info(f"✅ Found {len(results)} matching documents with scores")
            return results
        except Exception as e:
            logger.failure(f"❌ Qdrant query with scores failed: {str(e)}")
            return []
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get statistics about the Qdrant collection with error handling"""
        try:
            info = self.client.get_collection(self.collection_name)
            collection_stats = {
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "embedding_dimension": self.embedding_dim,
                "embedding_model": self.embedding_model_name,
                "collection_status": info.status,
                "config": {
                    "vector_size": info.config.params.vectors.size,
                    "distance": info.config.params.vectors.distance,
                    "shard_number": info.config.params.shard_number,
                    "replication_factor": info.config.params.replication_factor,
                },
                "deduplication_info": self.get_processed_files_info()
            }
            logger.info(f"Collection stats: {collection_stats['points_count']} documents")
            return collection_stats
        except Exception as e:
            logger.failure(f"❌ Collection info failed: {str(e)}")
            return {}
    
    def reset_collection(self) -> None:
        """Reset collection safely - delete and recreate"""
        try:
            logger.warning(f"Resetting collection: {self.collection_name}")
            
            # Delete collection if it exists
            try:
                self.client.delete_collection(self.collection_name)
                logger.info(f"Deleted existing collection: {self.collection_name}")
            except:
                logger.info("Collection didn't exist or was already deleted")
            
            # Recreate the collection and vector store
            self.vector_store = self._initialize_vector_store()
            logger.info(f"✅ Successfully reset collection: {self.collection_name}")
            
        except Exception as e:
            logger.failure(f"❌ Failed to reset collection: {str(e)}")
    
    def health_check(self) -> bool:
        """Perform a health check on the vector store and database"""
        try:
            # Test embedding generation
            test_embedding = self.embedding_model.embed_query("health check test")
            if len(test_embedding) != self.embedding_dim:
                logger.failure(f"Embedding dimension mismatch: expected {self.embedding_dim}, got {len(test_embedding)}")
                return False
            
            # Test collection access
            collection_info = self.client.get_collection(self.collection_name)
            if collection_info.config.params.vectors.size != self.embedding_dim:
                logger.failure(f"Collection dimension mismatch: expected {self.embedding_dim}, got {collection_info.config.params.vectors.size}")
                return False
            
            # Test database access if deduplication is enabled
            if self.enable_deduplication and self.dedup_tracker:
                stats = self.dedup_tracker.get_database_stats()
                if not isinstance(stats, dict):
                    logger.failure("Database health check failed")
                    return False
            
            logger.info("✅ Vector store and database health check passed")
            return True
            
        except Exception as e:
            logger.failure(f"❌ Health check failed: {str(e)}")
            return False


# Utility functions for file hashing
def create_safe_file_hash(file_path: str) -> Optional[str]:
    """Create file hash with permission error handling"""
    try:
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash
    except PermissionError:
        logger.failure(f"Permission denied accessing file: {file_path}")
        # Use file stats as fallback
        try:
            stat = os.stat(file_path)
            fallback_hash = hashlib.md5(f"{file_path}{stat.st_size}{stat.st_mtime}".encode()).hexdigest()
            logger.info(f"Using fallback hash for: {file_path}")
            return fallback_hash
        except Exception as e:
            logger.failure(f"Failed to create fallback hash: {e}")
            return None
    except Exception as e:
        logger.failure(f"Failed to hash file {file_path}: {e}")
        return None


def get_recommended_model(use_case: str = "general") -> str:
    """Get recommended embedding model based on use case"""
    recommendations = {
        "fast": "sentence-transformers/all-MiniLM-L6-v2",      # 384d, fastest
        "general": "BAAI/bge-small-en-v1.5",                   # 384d, good balance
        "quality": "BAAI/bge-base-en-v1.5",                    # 768d, better quality
        "best": "BAAI/bge-large-en-v1.5",                      # 1024d, best quality
        "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 384d
    }
    return recommendations.get(use_case, "BAAI/bge-small-en-v1.5")