#!/usr/bin/env python3
"""
Quick check of your vector store content
Run this to immediately see what documents are loaded
"""

from chain import RAGGraph
from pathlib import Path
from collections import Counter

def quick_check():
    """Quick diagnostic of vector store content"""
    print("🔍 QUICK VECTOR STORE CHECK")
    print("=" * 30)
    
    try:
        # Initialize RAG app
        rag_app = RAGGraph(use_config=True)
        
        # 1. Check basic stats
        stats = rag_app.get_vector_store_stats()
        print(f"📊 Total vectors: {stats.get('total_vectors', 'Unknown')}")
        
        # 2. Check source files
        docs_path = Path(rag_app.documents_path)
        md_files = list(docs_path.rglob('*.md')) if docs_path.exists() else []
        print(f"📁 Source .md files: {len(md_files)}")
        
        if md_files:
            print("   Files found:")
            for file in md_files:
                print(f"   - {file.name}")
        
        # 3. Test retrieval to see what sources are actually loaded
        print(f"\n🔍 Testing retrieval...")
        
        # Try a broad search to get various results
        results = rag_app.enhanced_vector_store.enhanced_search("article", k=10)
        
        if not results:
            print("❌ No results found!")
            return
        
        # Count sources
        source_counts = Counter()
        unique_sources = set()
        
        for doc, score in results:
            source = doc.metadata.get('source', 'Unknown')
            source_counts[source] += 1
            unique_sources.add(source)
        
        print(f"📚 Unique sources in vector store: {len(unique_sources)}")
        print("   Sources found:")
        for source in sorted(unique_sources):
            count = source_counts[source]
            print(f"   - {source} ({count} chunks)")
        
        # Sample content from each source
        print(f"\n📄 Sample content from each source:")
        seen_sources = set()
        for doc, score in results:
            source = doc.metadata.get('source', 'Unknown')
            if source not in seen_sources:
                seen_sources.add(source)
                content_preview = doc.page_content[:150].replace('\n', ' ')
                print(f"\n   {source}:")
                print(f"   {content_preview}...")
        
        # Diagnosis
        print(f"\n🎯 DIAGNOSIS:")
        if len(unique_sources) <= 1:
            print("❌ ISSUE: Only one document source found!")
            print("   Possible causes:")
            if len(md_files) <= 1:
                print("   - Not enough source files (.md)")
                print("   - Solution: Convert more documents to markdown")
            else:
                print("   - Vector store creation issue")
                print("   - Solution: Rebuild vector store")
        else:
            print(f"✅ GOOD: {len(unique_sources)} document sources loaded")
            print("   Issue might be with specific queries or retrieval parameters")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    quick_check()