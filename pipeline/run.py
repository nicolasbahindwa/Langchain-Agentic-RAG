"""
Simplified usage example for the refactored DataExtractionPipeline
"""
import logging
import threading
import time
import signal
import sys
from pathlib import Path

# Import the refactored classes
from pipeline.orchestrator import DataExtractionPipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineManager:
    """Simple manager for the pipeline with clean shutdown"""
    
    def __init__(self, pipeline: DataExtractionPipeline):
        self.pipeline = pipeline
        self.running = True
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """Setup graceful shutdown on SIGINT"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Shutdown signal received, stopping pipeline...")
        self.running = False
    
    def run(self):
        """Run the pipeline with monitoring"""
        try:
            # Start file monitoring
            self.pipeline.start_monitoring()
            logger.info("Pipeline started successfully")
            
            # Keep running until shutdown
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        finally:
            self.pipeline.stop_monitoring()
            logger.info("Pipeline stopped")


def interactive_query_loop(pipeline: DataExtractionPipeline):
    """Interactive query interface"""
    logger.info("Starting interactive query interface...")
    
    # Wait for initial processing
    time.sleep(3)
    
    print("\n=== INTERACTIVE QUERY INTERFACE ===")
    print("You can now query your documents!")
    print("Commands:")
    print("  'quit' or 'exit' - Exit the interface")
    print("  'stats' - Show pipeline statistics")
    print("  'health' - Check pipeline health")
    print("\nExample queries:")
    print("  - 'machine learning algorithms'")
    print("  - 'project timeline'")
    print("  - 'financial data'")
    print()
    
    while True:
        try:
            query = input("Enter your query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                logger.info("Exiting query interface...")
                break
            
            if query.lower() == 'stats':
                show_pipeline_stats(pipeline)
                continue
            
            if query.lower() == 'health':
                health_status = pipeline.health_check()
                print(f"Pipeline health: {'OK' if health_status else 'ERROR'}")
                continue
            
            if not query:
                continue
            
            # Query the vector store
            logger.info(f"Searching for: '{query}'")
            results = pipeline.vector_store.query_documents(query, k=3)
            
            if results:
                print(f"\nFound {len(results)} relevant documents:")
                print("-" * 50)
                
                for i, doc in enumerate(results, 1):
                    print(f"\nResult {i}:")
                    print(f"File: {doc.metadata.get('source', 'Unknown')}")
                    
                    # Show content preview
                    content = doc.page_content.strip()
                    if len(content) > 200:
                        print(f"Content: {content[:200]}...")
                    else:
                        print(f"Content: {content}")
                    
                    print("-" * 30)
            else:
                print("No relevant documents found")
            
            print()
        
        except KeyboardInterrupt:
            logger.info("Query interface interrupted")
            break
        except Exception as e:
            logger.error(f"Query error: {e}")


def show_pipeline_stats(pipeline: DataExtractionPipeline):
    """Display pipeline statistics"""
    try:
        stats = pipeline.get_stats()
        
        print("\n=== PIPELINE STATISTICS ===")
        print(f"Watch paths: {', '.join(stats.get('watch_paths', []))}")
        
        vector_stats = stats.get('vector_store_stats', {})
        print(f"Collection: {vector_stats.get('collection_name', 'Unknown')}")
        print(f"Vector count: {vector_stats.get('vector_count', 0)}")
        print(f"Tracked files: {vector_stats.get('tracked_files', 0)}")
        print(f"Total chunks: {vector_stats.get('total_chunks', 0)}")
        print(f"Embedding model: {vector_stats.get('embedding_model', 'Unknown')}")
        print()
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")


def demonstrate_pipeline_features(pipeline: DataExtractionPipeline):
    """Demonstrate key pipeline features"""
    logger.info("Demonstrating pipeline features...")
    
    # Wait for initial processing
    time.sleep(2)
    
    # Show initial stats
    show_pipeline_stats(pipeline)
    
    # Run sample queries
    sample_queries = [
        "document content",
        "file information",
        "data processing"
    ]
    
    logger.info("Running sample queries...")
    for query in sample_queries:
        logger.info(f"Sample query: '{query}'")
        try:
            results = pipeline.vector_store.query_documents(query, k=2)
            logger.info(f"Found {len(results)} results")
        except Exception as e:
            logger.error(f"Query failed: {e}")
    
    print()


def create_watch_directories(watch_paths):
    """Create watch directories if they don't exist"""
    for path_str in watch_paths:
        path = Path(path_str)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path}")
            
            # Create a sample file
            sample_file = path / "sample.txt"
            if not sample_file.exists():
                sample_file.write_text(
                    "This is a sample document for testing the pipeline.\n"
                    "It contains some text that can be searched and indexed.\n"
                    "You can add more documents to this directory for processing."
                )
                logger.info(f"Created sample file: {sample_file}")


def main():
    """Main function to run the pipeline"""
    logger.info("=== SIMPLIFIED DOCUMENT PROCESSING PIPELINE ===")
    
    # Configuration
    config = {
        "watch_paths": ["./documents", "./data"],
        "chunk_size": 800,
        "chunk_overlap": 100,
        "embedding_model": "BAAI/bge-small-en-v1.5",  # Use HuggingFace model
        "collection_name": "document_knowledge_base",
        "persist_dir": "./vector_storage"
    }
    
    logger.info("Configuration:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    
    # Create watch directories if needed
    create_watch_directories(config["watch_paths"])
    
    try:
        # Initialize pipeline
        logger.info("Initializing pipeline...")
        pipeline = DataExtractionPipeline(**config)
        logger.info("Pipeline initialization complete!")
        
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
        
        # Create and run pipeline manager
        manager = PipelineManager(pipeline)
        
        logger.info("Starting pipeline monitoring...")
        logger.info("The pipeline will:")
        logger.info("  • Monitor directories for file changes")
        logger.info("  • Process new/modified documents automatically")
        logger.info("  • Maintain vector store with embeddings")
        logger.info("  • Provide interactive query interface")
        logger.info("Press Ctrl+C to stop")
        
        manager.run()
        
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise
    finally:
        logger.info("Pipeline shutdown complete")


if __name__ == "__main__":
    main()

