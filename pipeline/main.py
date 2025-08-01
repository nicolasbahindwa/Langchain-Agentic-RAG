# main.py
"""
Main entry point for the watchdog data extraction pipeline
"""
import argparse
import os
import sys
from typing import List

from pipeline_orchestrator import DataExtractionPipeline, PipelineConfig


def main():
    """Main function with CLI interface"""
    parser = argparse.ArgumentParser(
        description="Watchdog Data Extraction Pipeline with LangChain and Qdrant"
    )
    
    # Basic arguments
    parser.add_argument(
        'watch_paths',
        nargs='+',
        help='Paths to monitor for file changes'
    )
    
    # Vector store configuration
    parser.add_argument(
        '--collection-name',
        default='document_store',
        help='Qdrant collection name (default: document_store)'
    )
    
    parser.add_argument(
        '--embeddings-model',
        default='text-embedding-ada-002',
        help='OpenAI embeddings model (default: text-embedding-ada-002)'
    )
    
    parser.add_argument(
        '--qdrant-location',
        default=':memory:',
        help='Qdrant location - :memory: for in-memory or URL for remote (default: :memory:)'
    )
    
    # Document processing
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=1000,
        help='Document chunk size (default: 1000)'
    )
    
    parser.add_argument(
        '--chunk-overlap',
        type=int,
        default=200,
        help='Chunk overlap size (default: 200)'
    )
    
    # File monitoring
    parser.add_argument(
        '--debounce-seconds',
        type=int,
        default=2,
        help='File change debounce period in seconds (default: 2)'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not monitor subdirectories recursively'
    )
    
    parser.add_argument(
        '--no-existing',
        action='store_true',
        help='Do not process existing files on startup'
    )
    
    parser.add_argument(
        '--no-self-query',
        action='store_true',
        help='Disable self-query retriever'
    )
    
    # Logging
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--log-file',
        help='Log file path (default: console only)'
    )
    
    # Interactive mode
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive mode for testing queries'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    PipelineConfig.setup_logging(args.log_level, args.log_file)
    
    # Check OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("Error: OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    
    # Initialize pipeline
    pipeline = DataExtractionPipeline(
        watch_paths=args.watch_paths,
        collection_name=args.collection_name,
        embeddings_model=args.embeddings_model,
        qdrant_location=args.qdrant_location,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        debounce_seconds=args.debounce_seconds,
        recursive=not args.no_recursive,
        enable_self_query=not args.no_self_query
    )
    
    if args.interactive:
        run_interactive_mode(pipeline, not args.no_existing)
    else:
        # Run in monitoring mode
        pipeline.run_forever(process_existing=not args.no_existing)


def run_interactive_mode(pipeline: DataExtractionPipeline, process_existing: bool = True):
    """Run pipeline in interactive mode for testing"""
    import time
    
    print("Starting interactive mode...")
    print("Processing files and starting monitoring in background...")
    
    # Start monitoring in background
    pipeline.start_monitoring(process_existing=process_existing)
    
    print("\nInteractive mode ready!")
    print("Commands:")
    print("  search <query>          - Search documents")
    print("  query <natural_query>   - Natural language query with filtering")
    print("  stats                   - Show pipeline statistics")
    print("  health                  - Show health status")
    print("  help                    - Show this help")
    print("  quit                    - Exit")
    print()
    
    try:
        while True:
            # Process pending file events
            pipeline.file_monitor.process_pending_events()
            
            try:
                command = input("pipeline> ").strip()
            except EOFError:
                break
            
            if not command:
                continue
            
            parts = command.split(' ', 1)
            cmd = parts[0].lower()
            
            if cmd == 'quit' or cmd == 'exit':
                break
            elif cmd == 'help':
                show_help()
            elif cmd == 'stats':
                show_stats(pipeline)
            elif cmd == 'health':
                show_health(pipeline)
            elif cmd == 'search':
                if len(parts) > 1:
                    search_documents(pipeline, parts[1])
                else:
                    print("Usage: search <query>")
            elif cmd == 'query':
                if len(parts) > 1:
                    natural_language_query(pipeline, parts[1])
                else:
                    print("Usage: query <natural_language_query>")
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
    
    except KeyboardInterrupt:
        print("\nReceived interrupt signal")
    finally:
        print("Stopping pipeline...")
        pipeline.stop_monitoring()


def show_help():
    """Show interactive mode help"""
    print("\nAvailable commands:")
    print("  search <query>          - Semantic search in documents")
    print("  query <natural_query>   - Natural language query (e.g., 'documents about AI from 2023')")
    print("  stats                   - Show pipeline statistics")
    print("  health                  - Show pipeline health status")
    print("  help                    - Show this help")
    print("  quit                    - Exit interactive mode")
    print()


def show_stats(pipeline: DataExtractionPipeline):
    """Show pipeline statistics"""
    stats = pipeline.get_pipeline_stats()
    
    print("\n=== Pipeline Statistics ===")
    print(f"Files processed: {stats['pipeline']['files_processed']}")
    print(f"Documents added: {stats['pipeline']['documents_added']}")
    print(f"Processing errors: {stats['pipeline']['processing_errors']}")
    
    if stats['pipeline']['last_error']:
        print(f"Last error: {stats['pipeline']['last_error']}")
    
    print(f"\nMonitoring: {stats['file_monitor']['is_monitoring']}")
    print(f"Watch paths: {', '.join(stats['file_monitor']['watch_paths'])}")
    print(f"Pending events: {stats['file_monitor']['pending_events']}")
    
    print(f"\nVector store initialized: {stats['vector_store']['is_initialized']}")
    print(f"Collection: {stats['vector_store']['collection_name']}")
    print(f"Embeddings model: {stats['vector_store']['embeddings_model']}")
    print()


def show_health(pipeline: DataExtractionPipeline):
    """Show pipeline health status"""
    health = pipeline.health_check()
    
    print(f"\n=== Health Status: {health['status'].upper()} ===")
    
    if health['issues']:
        print("Issues:")
        for issue in health['issues']:
            print(f"  - {issue}")
    else:
        print("No issues detected")
    print()


def search_documents(pipeline: DataExtractionPipeline, query: str):
    """Perform document search"""
    print(f"\nSearching for: '{query}'")
    
    results = pipeline.search_documents(query, k=3, with_scores=True)
    
    if not results:
        print("No results found.")
        return
    
    print(f"\nFound {len(results)} results:")
    print("-" * 50)
    
    for i, (doc, score) in enumerate(results, 1):
        print(f"Result {i} (score: {score:.3f}):")
        print(f"Source: {doc.metadata.get('source', 'Unknown')}")
        print(f"Content: {doc.page_content[:200]}...")
        print("-" * 50)


def natural_language_query(pipeline: DataExtractionPipeline, query: str):
    """Perform natural language query"""
    if not pipeline.self_query_manager:
        print("Self-query retriever is not enabled. Use --no-self-query to disable this feature.")
        return
    
    print(f"\nNatural language query: '{query}'")
    
    try:
        results = pipeline.self_query(query)
        
        if not results:
            print("No results found.")
            return
        
        print(f"\nFound {len(results)} results:")
        print("-" * 50)
        
        for i, doc in enumerate(results, 1):
            print(f"Result {i}:")
            print(f"Source: {doc.metadata.get('source', 'Unknown')}")
            print(f"File: {doc.metadata.get('file_name', 'Unknown')}")
            print(f"Content: {doc.page_content[:200]}...")
            print("-" * 50)
    
    except Exception as e:
        print(f"Error performing natural language query: {str(e)}")


if __name__ == "__main__":
    main()


# example_usage.py
"""
Example usage of the data extraction pipeline
"""
import os
import time
from pipeline_orchestrator import DataExtractionPipeline


def basic_usage_example():
    """Basic usage example"""
    # Set up environment
    os.environ["OPENAI_API_KEY"] = "your-openai-api-key-here"
    
    # Create pipeline
    pipeline = DataExtractionPipeline(
        watch_paths=["./documents"],
        collection_name="my_documents",
        embeddings_model="text-embedding-ada-002",
        qdrant_location=":memory:",  # In-memory storage
        chunk_size=500,
        chunk_overlap=50,
        debounce_seconds=1,
        recursive=True
    )
    
    # Process existing files
    pipeline.process_existing_files()
    
    # Start monitoring
    pipeline.start_monitoring(process_existing=False)
    
    # Let it run for a while
    try:
        while True:
            time.sleep(1)
            pipeline.file_monitor.process_pending_events()
            
            # Example: search every 30 seconds
            if int(time.time()) % 30 == 0:
                results = pipeline.search_documents("example query", k=2)
                print(f"Found {len(results)} results")
                
    except KeyboardInterrupt:
        pipeline.stop_monitoring()


def advanced_usage_example():
    """Advanced usage with custom configuration"""
    
    # Custom supported extensions
    supported_extensions = {'.txt', '.pdf', '.md', '.json'}
    
    pipeline = DataExtractionPipeline(
        watch_paths=["./docs", "./reports"],
        collection_name="advanced_docs",
        embeddings_model="text-embedding-ada-002",
        qdrant_location=":memory:",
        chunk_size=1500,
        chunk_overlap=300,
        debounce_seconds=3,
        recursive=True,
        supported_extensions=supported_extensions,
        enable_self_query=True
    )
    
    # Add custom metadata fields for better querying
    pipeline.add_custom_metadata_field(
        name="department",
        description="The department that created the document",
        field_type="string"
    )
    
    # Process and monitor
    pipeline.run_forever(process_existing=True)


def query_examples():
    """Examples of different query types"""
    pipeline = DataExtractionPipeline(
        watch_paths=["./documents"],
        collection_name="query_examples"
    )
    
    # Process some files first
    pipeline.process_existing_files()
    
    # Basic semantic search
    results = pipeline.search_documents("machine learning algorithms", k=5)
    print(f"Semantic search found {len(results)} results")
    
    # Search with metadata filter
    results = pipeline.search_documents(
        "data analysis",
        k=3,
        filter_dict={"file_extension": "pdf"}
    )
    print(f"Filtered search found {len(results)} results")
    
    # Natural language query (if self-query is enabled)
    if pipeline.self_query_manager:
        results = pipeline.self_query("Find PDF documents about data science from this year")
        print(f"Natural language query found {len(results)} results")
    
    # Get pipeline statistics
    stats = pipeline.get_pipeline_stats()
    print("Pipeline stats:", stats)


if __name__ == "__main__":
    # Run the basic example
    basic_usage_example()