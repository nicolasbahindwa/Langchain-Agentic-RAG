from orchestrator import DataExtractionPipeline

if __name__ == "__main__":
    print("=== FILE MONITORING PIPELINE ===")
    print("Initializing pipeline...")
    
    # Initialize with watch paths
    pipeline = DataExtractionPipeline(watch_paths=["./documents"])
    
    # Start monitoring
    try:
        pipeline.run_forever()
    except Exception as e:
        print(f"💥 Critical error: {str(e)}")
    finally:
        print("✅ Pipeline shutdown complete")