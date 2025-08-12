from data_pipeline.data_extractor import DocumentProcessor
from datetime import datetime
import os
from pathlib import Path
def main():
    """Example usage of the DocumentProcessor."""
    
    # Configuration
    try:
        from core.config import config
        input_dir = config.data_processing.raw_data_folder_path
        output_dir = os.path.join(config.data_processing.markdown_data_folder_path, 
                                 datetime.now().strftime("%Y-%m-%d"))
    except ImportError:
        # Fallback for standalone usage
        input_dir = "./documents"
        output_dir = f"./converted_docs_{datetime.now().strftime('%Y%m%d')}"
    
    # Initialize processor
    processor = DocumentProcessor(
        output_dir=output_dir,
        ocr_language='eng',
        app_name="DocumentProcessor"
    )
    
    # Print supported file types
    print("Supported file extensions:")
    for ext in processor.get_supported_extensions():
        print(f"  {ext}")
    
    # Convert documents
    print(f"\nProcessing documents from: {input_dir}")
    results = processor.convert_directory(input_dir)
    
    # Print summary
    summary = results["summary"]
    print(f"\n=== Conversion Summary ===")
    print(f"Total files: {summary['total_files']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Output directory: {summary['output_directory']}")
    
    # Print detailed statistics
    stats = processor.get_conversion_stats(results["results"])
    print(f"\n=== Detailed Statistics ===")
    print(f"Average processing time: {stats['average_processing_time']:.2f} seconds")
    
    print("\nBy file type:")
    for file_type, counts in stats["by_file_type"].items():
        print(f"  {file_type}: {counts['successful']}/{counts['total']} successful")
    
    print("\nBy extraction method:")
    for method, count in stats["by_extraction_method"].items():
        print(f"  {method}: {count} files")
    
    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats["errors"][:5]:  # Show first 5 errors
            print(f"  {Path(error['file']).name}: {error['error']}")

if __name__ == "__main__":
    main()