# from .orchestrator import DataExtractionPipeline
# from utils.logger import setup_logging, get_enhanced_logger

# if __name__ == "__main__":
#     # Setup logging first
#     setup_logging("file_monitor_pipeline")
    
#     # Get enhanced logger for main script
#     logger = get_enhanced_logger("main")
    
#     logger.success("=== FILE MONITORING PIPELINE ===")
#     logger.performance("Initializing pipeline...")
    
#     # Initialize with watch paths
#     pipeline = DataExtractionPipeline(watch_paths=["./documents"])
    
#     # Start monitoring
#     try:
#         pipeline.run_forever()
#     except Exception as e:
#         logger.failure(f"Critical error: {str(e)}")
#         raise
#     finally:
#         logger.success("Pipeline shutdown complete")

"""
Enhanced run script for the complete data extraction pipeline
Demonstrates file monitoring, processing, vector storage, and querying
"""
import asyncio
import threading
import time
from .orchestrator import DataExtractionPipeline
from utils.logger import setup_logging, get_enhanced_logger

def interactive_query_loop(pipeline: DataExtractionPipeline):
    """Interactive query loop running in a separate thread"""
    logger = get_enhanced_logger("query_interface")
    
    # Wait a bit for initial processing to complete
    time.sleep(5)
    
    logger.success("=== INTERACTIVE QUERY INTERFACE ===")
    logger.info("You can now query your documents!")
    logger.info("Type 'quit' to exit, 'stats' for pipeline statistics")
    logger.info("Example queries:")
    logger.info("  - 'machine learning algorithms'")
    logger.info("  - 'project timeline'")
    logger.info("  - 'financial data'")
    print()
    
    while True:
        try:
            # Get user input
            query = input("Enter your query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                logger.info("Exiting query interface...")
                break
            
            if query.lower() == 'stats':
                stats = pipeline.get_pipeline_stats()
                logger.success("=== PIPELINE STATISTICS ===")
                for key, value in stats.items():
                    logger.info(f"{key}: {value}")
                print()
                continue
            
            if not query:
                continue
            
            # Query the pipeline
            logger.info(f"Searching for: '{query}'")
            results = pipeline.query_documents(query, k=3)
            
            if results:
                logger.success(f"Found {len(results)} relevant documents:")
                print()
                
                for i, doc in enumerate(results, 1):
                    print(f"--- Result {i} ---")
                    print(f"File: {doc.metadata.get('file_name', 'Unknown')}")
                    print(f"Source: {doc.metadata.get('source', 'Unknown')}")
                    print(f"Content Preview: {doc.page_content[:200]}...")
                    if len(doc.page_content) > 200:
                        print("[Content truncated...]")
                    print()
            else:
                logger.warning("No relevant documents found")
                print()
        
        except KeyboardInterrupt:
            logger.info("Query interface interrupted")
            break
        except Exception as e:
            logger.error(f"Query error: {str(e)}")

def demonstrate_pipeline_features(pipeline: DataExtractionPipeline):
    """Demonstrate key pipeline features"""
    logger = get_enhanced_logger("demo")
    
    logger.success("=== PIPELINE FEATURE DEMONSTRATION ===")
    
    # Show initial stats
    time.sleep(2)  # Wait for initial processing
    stats = pipeline.get_pipeline_stats()
    logger.info("Initial pipeline statistics:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")
    
    # Example queries with different filters
    sample_queries = [
        ("recent documents", {"must": [{"key": "file_extension", "match": {"value": ".pdf"}}]}),
        ("text files content", {"must": [{"key": "file_extension", "match": {"value": ".txt"}}]}),
        ("all documents", None)
    ]
    
    logger.info("Running sample queries...")
    for query, filters in sample_queries:
        logger.info(f"Query: '{query}' with filters: {filters}")
        results = pipeline.query_documents(query, k=2, filters=filters)
        logger.success(f"Found {len(results)} results")
        print()

if __name__ == "__main__":
    # Setup logging first
    setup_logging("file_monitor_pipeline")
    
    # Get enhanced logger for main script
    logger = get_enhanced_logger("main")
    
    logger.success("=== COMPLETE FILE MONITORING & PROCESSING PIPELINE ===")
    logger.performance("Initializing integrated pipeline...")
    
    # Configuration
    config = {
        "watch_paths": ["./documents", "./data"],  # Multiple watch directories
        "chunk_size": 800,  # Smaller chunks for better granularity
        "chunk_overlap": 100,
        "embedding_model": "text-embedding-3-small",
        "collection_name": "document_knowledge_base",
        "persist_dir": "./vector_storage"
    }
    
    logger.info("Pipeline configuration:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    
    # Initialize pipeline with configuration
    try:
        pipeline = DataExtractionPipeline(**config)
        logger.success("Pipeline initialization complete!")
        
        # Start feature demonstration in background
        demo_thread = threading.Thread(
            target=demonstrate_pipeline_features, 
            args=(pipeline,),
            daemon=True
        )
        demo_thread.start()
        
        # Start interactive query interface in background
        query_thread = threading.Thread(
            target=interactive_query_loop, 
            args=(pipeline,),
            daemon=True
        )
        query_thread.start()
        
        # Start main monitoring loop
        logger.success("Starting main pipeline...")
        logger.info("The pipeline will:")
        logger.info("  • Monitor directories for file changes")
        logger.info("  • Process new/modified documents automatically")
        logger.info("  • Maintain vector store with embeddings")
        logger.info("  • Provide interactive query interface")
        logger.info("  • Clean up deleted documents")
        
        pipeline.run_forever()
        
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
    except Exception as e:
        logger.failure(f"Critical pipeline error: {str(e)}")
        raise
    finally:
        logger.success("Pipeline shutdown complete")
        logger.info("Thank you for using the document processing pipeline!")