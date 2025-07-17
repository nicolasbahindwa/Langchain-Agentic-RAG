import os
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import json

class VectorStoreInspector:
    """Inspect and debug vector store contents"""
    
    def __init__(self, vector_store_path: str):
        self.vector_store_path = Path(vector_store_path)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.vector_store = None
        self._load_vector_store()
    
    def _load_vector_store(self):
        """Load the vector store"""
        try:
            if not self.vector_store_path.exists():
                raise FileNotFoundError(f"Vector store path does not exist: {self.vector_store_path}")
            
            self.vector_store = FAISS.load_local(
                str(self.vector_store_path),
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            print(f"✅ Vector store loaded successfully")
            
        except Exception as e:
            print(f"❌ Failed to load vector store: {e}")
            raise
    
    def inspect_basic_info(self):
        """Show basic information about the vector store"""
        print("\n=== BASIC VECTOR STORE INFO ===")
        try:
            total_docs = self.vector_store.index.ntotal
            embedding_dim = self.vector_store.index.d
            
            print(f"📊 Total documents: {total_docs}")
            print(f"🔢 Embedding dimension: {embedding_dim}")
            print(f"📁 Vector store path: {self.vector_store_path}")
            
            # Check if index file exists and its size
            index_file = self.vector_store_path / "index.faiss"
            if index_file.exists():
                size_mb = index_file.stat().st_size / (1024 * 1024)
                print(f"💾 Index file size: {size_mb:.2f} MB")
            
        except Exception as e:
            print(f"❌ Error inspecting basic info: {e}")
    
    def inspect_documents(self, limit: int = 5):
        """Show sample documents from the vector store"""
        print(f"\n=== SAMPLE DOCUMENTS (first {limit}) ===")
        try:
            # Get a sample of documents
            sample_results = self.vector_store.similarity_search("", k=limit)
            
            for i, doc in enumerate(sample_results):
                print(f"\n📄 Document {i+1}:")
                print(f"Content preview: {doc.page_content[:200]}...")
                print(f"Metadata: {doc.metadata}")
                
        except Exception as e:
            print(f"❌ Error inspecting documents: {e}")
    
    def test_search_queries(self, queries: list):
        """Test multiple search queries"""
        print(f"\n=== TESTING SEARCH QUERIES ===")
        
        for query in queries:
            print(f"\n🔍 Query: '{query}'")
            try:
                results = self.vector_store.similarity_search_with_score(query, k=3)
                print(f"📊 Found {len(results)} results")
                
                for i, (doc, score) in enumerate(results):
                    print(f"  Result {i+1}: Score={score:.4f}")
                    print(f"    Preview: {doc.page_content[:100]}...")
                    print(f"    Metadata: {doc.metadata}")
                    print()
                
            except Exception as e:
                print(f"❌ Search failed for '{query}': {e}")
    
    def test_embedding_quality(self):
        """Test if embeddings are working correctly"""
        print(f"\n=== TESTING EMBEDDING QUALITY ===")
        
        test_texts = [
            "machine learning",
            "apprentissage automatique",
            "constitution",
            "république démocratique congo"
        ]
        
        try:
            # Test embedding generation
            embeddings = self.embeddings.embed_documents(test_texts)
            print(f"✅ Successfully generated {len(embeddings)} embeddings")
            print(f"📏 Embedding dimension: {len(embeddings[0])}")
            
            # Test similarity between related concepts
            query_embedding = self.embeddings.embed_query("machine learning")
            
            # Find most similar documents
            results = self.vector_store.similarity_search_with_score("machine learning", k=5)
            print(f"\n🔍 Most similar documents to 'machine learning':")
            for i, (doc, score) in enumerate(results):
                print(f"  {i+1}. Score: {score:.4f} | {doc.page_content[:80]}...")
                
        except Exception as e:
            print(f"❌ Embedding test failed: {e}")
    
    def check_metadata_consistency(self):
        """Check if metadata is consistent across documents"""
        print(f"\n=== CHECKING METADATA CONSISTENCY ===")
        
        try:
            # Get all documents (or a large sample)
            all_docs = self.vector_store.similarity_search("", k=100)
            
            metadata_keys = set()
            sources = set()
            
            for doc in all_docs:
                metadata_keys.update(doc.metadata.keys())
                if 'source' in doc.metadata:
                    sources.add(doc.metadata['source'])
            
            print(f"📋 Metadata keys found: {sorted(metadata_keys)}")
            print(f"📁 Sources found: {sorted(sources)}")
            print(f"📊 Total documents sampled: {len(all_docs)}")
            
        except Exception as e:
            print(f"❌ Metadata check failed: {e}")
    
    def run_full_inspection(self):
        """Run all inspection methods"""
        print("🔍 STARTING FULL VECTOR STORE INSPECTION")
        print("=" * 50)
        
        self.inspect_basic_info()
        self.inspect_documents(limit=3)
        self.check_metadata_consistency()
        self.test_embedding_quality()
        
        # Test with various query types
        test_queries = [
            "constitution",
            "learning",
            "machine learning",
            "république démocratique congo",
            "apprentissage automatique",
            "démocratique",
            "congo",
            "article",
            "loi"
        ]
        
        self.test_search_queries(test_queries)
        
        print("\n" + "=" * 50)
        print("🏁 INSPECTION COMPLETE")

# Usage example
if __name__ == "__main__":
    # Replace with your actual vector store path
    inspector = VectorStoreInspector("./data_pipeline/vector_store_data")
    inspector.run_full_inspection()