# #!/usr/bin/env python3
# """
# Interactive CLI for the RAG graph with human-in-the-loop support.
# """

# import os
# import sys
# from typing import Dict, Any

# from graph import app 




# # ------------------------------------------------------------------
# # Pretty printer
# # ------------------------------------------------------------------
# def print_step(name: str, data: Dict[str, Any]) -> None:
#     print(f"\n● {name}")
#     if "ai_feedback_request" in data:
#         print("💬", data["ai_feedback_request"])
#     elif "final_answer" in data:
#         print("\n" + "="*60)
#         print(data["final_answer"])
#         print("="*60)
#     elif "current_question" in data:
#         print("📝 Reframed question →", data["current_question"])
#     elif "retrieved_docs" in data:
#         print("📚 Retrieved", len(data["retrieved_docs"]), "document(s)")
#     elif "error" in data:
#         print("❌", data["error"])

# # ------------------------------------------------------------------
# # Main loop
# # ------------------------------------------------------------------
# def main() -> None:
#     thread = {"configurable": {"thread_id": "cli_demo"}}
#     state = {
#         "original_question": input("Ask me anything: ").strip(),
#         "human_feedback": None,
#         "feedback_cycles": 0
#     }

#     while True:
#         # Stream every update
#         for step_name, payload in app.stream(state, thread, stream_mode="updates"):
#             print_step(step_name, payload)

#         # Check if we are paused waiting for human input
#         snapshot = app.get_state(thread)
#         if snapshot.next and "request_human_feedback" in snapshot.next:
#             feedback = input("\n👉 Your feedback (empty = continue as-is): ").strip()
#             state = snapshot.values
#             state["human_feedback"] = feedback or None
#             continue   # continue the loop – graph will resume

#         # No more steps -> we are done
#         if not snapshot.next:
#             break

#     print("\n✅ Done.")

# if __name__ == "__main__":
#     try:
#         main()
#     except KeyboardInterrupt:
#         print("\nInterrupted by user.")

from core.search_manager import ResultCleaner, create_search_manager


if __name__ == "__main__":
    print("=== TESTING SEARCH MANAGER ===")
    
    # Initialize search manager
    search_manager = create_search_manager()
    
    # Test single provider searches
    query = "japan economy current state"
    print(f"\n🔍 Testing query: '{query}'")
    
    # Test each provider individually
    for provider in search_manager.get_available_providers():
        print(f"\n--- Testing {provider.upper()} ---")
        results = search_manager.search(query, provider=provider, max_results=2)
        
        print(f"Status: {results.get('status', 'unknown')}")
        print(f"Results Count: {results.get('count', 0)}")
        
        if results.get('status') == 'error':
            print(f"❌ Error: {results.get('error', 'Unknown error')}")
        elif results.get('status') == 'success' and results.get('search_results'):
            print("✅ Success! Sample results:")
            for i, search_result in enumerate(results['search_results'][:1], 1):  # Show only first result
                print(f"  {i}. {search_result.title}")
                print(f"     URL: {search_result.url}")
                print(f"     Preview: {search_result.snippet[:100]}...")
        else:
            print("⚠️  No results found")
    
    # Test multi-provider search if at least one provider works
    working_providers = []
    for provider in search_manager.get_available_providers():
        test_result = search_manager.search("test", provider=provider, max_results=1)
        if test_result.get('status') == 'success':
            working_providers.append(provider)
    
    if len(working_providers) > 1:
        print(f"\n{'='*60}")
        print("🔄 MULTI-PROVIDER SEARCH TEST")
        print(f"{'='*60}")
        
        multi_results = search_manager.multi_search(query, providers=working_providers[:2])  # Test with 2 providers
        
        if multi_results.get('status') == 'success' and multi_results.get('search_results'):
            # Clean and filter results
            cleaner = ResultCleaner()
            clean_results = cleaner.deduplicate_results(multi_results['search_results'])
            quality_results = cleaner.filter_by_quality(clean_results, min_content_length=50)
            sorted_results = cleaner.sort_by_relevance(quality_results)
            
            print(f"✅ Multi-search successful!")
            print(f"   Original results: {multi_results.get('total_count', 0)}")
            print(f"   After cleaning: {len(sorted_results)}")
            
            if sorted_results:
                print("   Top result:")
                top_result = sorted_results[0]
                print(f"   - {top_result.title}")
                print(f"   - Source: {top_result.source}")
                print(f"   - Preview: {top_result.snippet[:150]}...")
        else:
            print("❌ Multi-search failed:")
            if 'results_by_provider' in multi_results:
                for provider, result in multi_results['results_by_provider'].items():
                    if result.get('status') == 'error':
                        print(f"   {provider}: {result.get('error', 'Unknown error')}")
    else:
        print(f"\n⚠️  Only {len(working_providers)} provider(s) working, skipping multi-search test")
    
    print(f"\n{'='*60}")
    print("📊 SEARCH MANAGER SUMMARY")
    print(f"{'='*60}")
    print(f"Available providers: {search_manager.get_available_providers()}")
    print(f"Working providers: {working_providers}")
    print("Search manager ready for production use!")
    print(f"{'='*60}")