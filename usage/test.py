#!/usr/bin/env python3
"""
Debug RAG system for French legal documents
"""

import subprocess
from enhanced_rag_graph import RAGGraph
from collections import Counter
from pathlib import Path

def check_ollama_models():
    """Check available Ollama models"""
    print("🔍 CHECKING OLLAMA MODELS")
    print("=" * 30)
    
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            print("Available models:")
            print(result.stdout)
            
            # Check if llama3.2 is available
            if 'llama3.2' in result.stdout:
                print("✅ llama3.2 found")
                return True
            else:
                print("❌ llama3.2 NOT found")
                print("Install with: ollama pull llama3.2")
                return False
        else:
            print("❌ Ollama not running or accessible")
            return False
    except FileNotFoundError:
        print("❌ Ollama not installed")
        return False

def analyze_vector_distribution(rag_app):
    """Analyze how vectors are distributed across documents"""
    print("\n🔍 ANALYZING VECTOR DISTRIBUTION")
    print("=" * 35)
    
    # Get a large sample to see distribution
    results = rag_app.enhanced_vector_store.enhanced_search("article", k=50)
    
    if not results:
        print("❌ No results found")
        return
    
    source_counts = Counter()
    section_counts = Counter()
    chunk_sizes = []
    
    for doc, score in results:
        source = doc.metadata.get('source', 'Unknown')
        section = doc.metadata.get('section_title', 'Unknown')
        
        source_counts[source] += 1
        section_counts[section] += 1
        chunk_sizes.append(len(doc.page_content))
    
    print(f"📊 Analyzed {len(results)} chunks:")
    print(f"   Unique sources: {len(source_counts)}")
    print(f"   Average chunk size: {sum(chunk_sizes)/len(chunk_sizes):.0f} chars")
    
    print(f"\n📚 Distribution by source:")
    for source, count in source_counts.most_common():
        percentage = (count / len(results)) * 100
        print(f"   {source}: {count} chunks ({percentage:.1f}%)")
    
    # Check if one document dominates
    top_source_count = source_counts.most_common(1)[0][1]
    if top_source_count > len(results) * 0.7:
        print(f"\n⚠️  WARNING: One document dominates ({top_source_count}/{len(results)} chunks)")
        print("   This suggests chunking issues")

def test_french_legal_queries(rag_app):
    """Test specific French legal queries"""
    print("\n🔍 TESTING FRENCH LEGAL QUERIES")
    print("=" * 32)
    
    test_queries = [
        "droit de manifester",
        "liberté d'expression", 
        "droits fondamentaux",
        "constitution article",
        "libertés publiques",
        "manifestation pacifique"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        results = rag_app.enhanced_vector_store.enhanced_search(query, k=3)
        
        if results:
            print(f"   Found {len(results)} results")
            best_result = results[0]
            doc, score = best_result
            source = doc.metadata.get('source', 'Unknown')
            section = doc.metadata.get('section_title', 'Unknown')
            content_preview = doc.page_content[:100].replace('\n', ' ')
            
            print(f"   Best match: {source}")
            print(f"   Section: {section}")
            print(f"   Score: {score:.3f}")
            print(f"   Preview: {content_preview}...")
        else:
            print("   ❌ No results found")

def check_constitution_content(rag_app):
    """Specifically check constitution content for rights"""
    print("\n🔍 CHECKING CONSTITUTION CONTENT")
    print("=" * 33)
    
    # Search for constitution-specific terms
    constitution_queries = [
        "constitution",
        "droits",
        "libertés", 
        "citoyen",
        "article"
    ]
    
    constitution_chunks = set()
    
    for query in constitution_queries:
        results = rag_app.enhanced_vector_store.enhanced_search(query, k=10)
        for doc, score in results:
            source = doc.metadata.get('source', 'Unknown')
            if 'Constitution' in source:
                constitution_chunks.add(doc.page_content[:200])
    
    print(f"📄 Found {len(constitution_chunks)} unique constitution chunks")
    
    if constitution_chunks:
        print("\n📋 Sample constitution content:")
        for i, chunk in enumerate(list(constitution_chunks)[:3]):
            print(f"   {i+1}. {chunk.replace('\n', ' ')}...")
    else:
        print("❌ No constitution content found in searches")

def suggest_improvements(rag_app):
    """Suggest specific improvements"""
    print("\n💡 SUGGESTED IMPROVEMENTS")
    print("=" * 26)
    
    stats = rag_app.get_vector_store_stats()
    total_vectors = stats.get('total_vectors', 0)
    
    print("1. 🔧 LLM Setup:")
    print("   - Install: ollama pull llama3.2")
    print("   - Or use: ollama pull llama3.1")
    print("   - Verify: ollama list")
    
    print("\n2. 📝 Improve Chunking for Legal Text:")
    print("   - Use smaller chunks (500-800 chars)")
    print("   - More overlap (100-200 chars)")
    print("   - Legal-specific splitting")
    
    print("\n3. 🌍 French Language Optimization:")
    print("   - Use multilingual embedding model")
    print("   - Lower similarity threshold (0.4-0.6)")
    print("   - Test with French legal terms")
    
    print("\n4. 🔍 Retrieval Improvements:")
    print("   - Increase retrieval_k (6-10)")
    print("   - Enable metadata filtering")
    print("   - Add legal-specific preprocessing")
    
    if total_vectors > 500:
        print(f"\n5. 📊 Vector Store ({total_vectors} vectors):")
        print("   - Seems reasonable size")
        print("   - Check distribution balance")
    else:
        print(f"\n5. 📊 Vector Store ({total_vectors} vectors):")
        print("   - Might be too few chunks")
        print("   - Consider smaller chunk size")

def main():
    """Run comprehensive RAG debugging"""
    print("🔍 RAG SYSTEM DEBUGGING FOR FRENCH LEGAL DOCUMENTS")
    print("=" * 55)
    
    # Check Ollama
    ollama_ok = check_ollama_models()
    
    try:
        # Initialize RAG
        rag_app = RAGGraph(use_config=True)
        
        # Run diagnostics
        analyze_vector_distribution(rag_app)
        test_french_legal_queries(rag_app)
        check_constitution_content(rag_app)
        suggest_improvements(rag_app)
        
        # Overall assessment
        print(f"\n🎯 OVERALL ASSESSMENT")
        print("=" * 20)
        
        if not ollama_ok:
            print("❌ CRITICAL: Fix Ollama model issue first")
        else:
            print("✅ LLM should work once model is available")
            
        print("🔧 Recommended actions:")
        print("1. Fix Ollama model (critical)")
        print("2. Rebuild with smaller chunks")
        print("3. Use French-optimized embeddings")
        print("4. Test with more specific queries")
        
    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()