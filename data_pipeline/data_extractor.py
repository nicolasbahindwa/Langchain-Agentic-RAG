import os
import glob
import re
from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

# Import your logger module
from utils.logger import setup_logging, get_enhanced_logger

# Core markitdown dependency
try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

class FileType(Enum):
    """Supported file types."""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    PPTX = "pptx"
    PPT = "ppt"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    HTML = "html"
    HTM = "htm"
    TXT = "txt"
    MD = "md"
    RTF = "rtf"
    ODT = "odt"
    ODS = "ods"
    ODP = "odp"
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    TIF = "tif"
    BMP = "bmp"
    GIF = "gif"
    WEBP = "webp"

@dataclass
class ConversionResult:
    """Result of document conversion."""
    success: bool
    content: str
    source_file: str
    file_type: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None

class TextFormatter:
    """Handles text formatting and markdown enhancement."""
    
    @staticmethod
    def enhance_markdown(text: str) -> str:
        """Enhance markdown formatting with better structure."""
        if not text.strip():
            return ""
        
        lines = text.split('\n')
        enhanced = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if not stripped:
                enhanced.append('')
                continue
            
            # Detect and format titles/headers
            title_level = TextFormatter._detect_title_level(stripped, i, lines)
            
            if title_level > 0:
                enhanced.append(f"{'#' * title_level} {stripped}")
            else:
                # Clean up line spacing and formatting
                enhanced.append(re.sub(r'\s+', ' ', stripped))
        
        # Add proper spacing after headers
        final = []
        for i, line in enumerate(enhanced):
            final.append(line)
            if (line.startswith('#') and i < len(enhanced) - 1 and 
                enhanced[i+1] and not enhanced[i+1].startswith('#')):
                final.append('')
        
        return '\n'.join(final)
    
    @staticmethod
    def _detect_title_level(text: str, line_index: int, all_lines: List[str]) -> int:
        """Detect if text is a title and return appropriate level."""
        # Already a markdown header
        if text.startswith('#'):
            return 0
        
        # All caps titles (level 1)
        if (text.isupper() and 
            5 < len(text) < 100 and
            2 <= len(text.split()) <= 12 and
            not any(punct in text for punct in [',', ';', '.']) and
            not re.search(r'\d{4}|n°|N°|art\.|Art\.|O\.L\.|du\s+\d', text)):
            return 1
        
        # Article/Chapter/Section headers (level 2)
        if re.match(r'^\s*(Article\s+\d+|ARTICLE\s+\d+|Chapitre\s+\d+|CHAPITRE\s+\d+|Section\s+\d+|SECTION\s+\d+)\s*[:.]?\s*$', text):
            return 2
        
        # Numbered items (level 3)
        if (re.match(r'^\s*([1-9]\d*\.|\b[IVXLCDM]+\.\s*|\b[A-Z]\.\s*)$', text) and len(text) < 20):
            return 3
        
        # Standalone short lines that look like titles (level 2)
        if (len(text) < 50 and len(text.split()) <= 6 and
            line_index > 0 and line_index < len(all_lines) - 2 and
            not all_lines[line_index-1].strip() and not all_lines[line_index+1].strip() and
            not any(punct in text for punct in ['.', ',', ';']) and
            text[0].isupper() and not re.search(r'\d+', text)):
            return 2
        
        return 0
    
    @staticmethod
    def clean_extracted_text(text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Multiple newlines to double
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
        
        # Fix common extraction issues
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Add space between camelCase
        text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)  # Add space after punctuation
        
        return text.strip()

class DocumentProcessor:
    """Main document processing class using markitdown."""
    
    def __init__(self, 
                 output_dir: Optional[str] = None,
                 ocr_language: str = 'eng',
                 app_name: str = "DocumentProcessor"):
        """
        Initialize the document processor.
        
        Args:
            output_dir: Directory to save converted files
            ocr_language: Language for OCR processing
            app_name: Application name for logging
        """
        if not MARKITDOWN_AVAILABLE:
            raise RuntimeError("markitdown not available. Install with: pip install markitdown[all]")
        
        # Initialize logging
        setup_logging(app_name)
        self.logger = get_enhanced_logger(app_name)
        
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "converted_docs"
        self.ocr_language = ocr_language
        
        # Initialize components
        self.markitdown = MarkItDown()
        self.text_formatter = TextFormatter()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported extensions
        self.supported_extensions = {
            '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.csv',
            '.html', '.htm', '.txt', '.md', '.rtf', '.odt', '.ods', '.odp',
            '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'
        }
        
        self.logger.info(f"Initialized with output directory: {self.output_dir}")
    
    def _extract_content_from_result(self, result) -> str:
        """Extract content from MarkItDown result."""
        if hasattr(result, 'text_content'):
            return result.text_content or ""
        elif hasattr(result, 'content'):
            return result.content or ""
        elif hasattr(result, 'text'):
            return result.text or ""
        return str(result) if result else ""
    
    def convert_single_file(self, file_path: Union[str, Path]) -> ConversionResult:
        """Convert a single file to markdown using markitdown."""
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        start_time = datetime.now()
        
        self.logger.debug(f"Starting conversion of {file_path.name}")
        
        try:
            # Check if file type is supported
            if ext not in self.supported_extensions:
                error_msg = f"Unsupported file type: {ext}"
                self.logger.warning(error_msg)
                return ConversionResult(
                    success=False,
                    content="",
                    source_file=str(file_path),
                    file_type=ext,
                    error=error_msg
                )
            
            # Prepare OCR options if applicable
            ocr_options = {}
            if ext in {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}:
                ocr_options = {'lang': self.ocr_language}
                self.logger.debug(f"Using OCR with language: {self.ocr_language}")
            
            # Convert using markitdown
            result = self.markitdown.convert(str(file_path), **ocr_options)
            raw_content = self._extract_content_from_result(result)
            cleaned_content = self.text_formatter.clean_extracted_text(raw_content)
            
            if not cleaned_content.strip():
                error_msg = "No content extracted"
                self.logger.warning(f"No content extracted from {file_path.name}")
                return ConversionResult(
                    success=False,
                    content="",
                    source_file=str(file_path),
                    file_type=ext,
                    error=error_msg
                )
            
            # Enhance markdown structure
            formatted_content = self.text_formatter.enhance_markdown(cleaned_content)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            self.logger.performance(f"Converted {file_path.name} in {processing_time:.2f}s")
            
            return ConversionResult(
                success=True,
                content=formatted_content,
                source_file=str(file_path),
                file_type=ext,
                processing_time=processing_time,
                metadata={"extraction_method": "markitdown"}
            )
        
        except Exception as e:
            error_msg = f"Error converting {file_path.name}: {str(e)}"
            self.logger.failure(error_msg)
            return ConversionResult(
                success=False,
                content="",
                source_file=str(file_path),
                file_type=ext,
                error=str(e)
            )
    
    def convert_directory(self, 
                         directory_path: Union[str, Path],
                         recursive: bool = True,
                         file_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convert all supported documents in a directory.
        
        Args:
            directory_path: Path to directory containing documents
            recursive: Whether to search subdirectories
            file_patterns: Optional list of file patterns to match
        
        Returns:
            Dictionary with conversion results and statistics
        """
        directory_path = Path(directory_path)
        
        if not directory_path.exists():
            error_msg = f"Directory does not exist: {directory_path}"
            self.logger.failure(error_msg)
            raise ValueError(error_msg)
        
        if not directory_path.is_dir():
            error_msg = f"Path is not a directory: {directory_path}"
            self.logger.failure(error_msg)
            raise ValueError(error_msg)
        
        # Find files to process
        files_to_process = self._find_files(directory_path, recursive, file_patterns)
        
        if not files_to_process:
            self.logger.warning(f"No supported documents found in {directory_path}")
            return {
                "summary": {
                    "total_files": 0,
                    "successful": 0,
                    "failed": 0,
                    "output_files": []
                },
                "results": []
            }
        
        self.logger.info(f"Found {len(files_to_process)} document(s) to convert")
        
        # Process files
        results = []
        successful_conversions = []
        
        for file_path in files_to_process:
            self.logger.info(f"Converting: {file_path.name}")
            
            conversion_result = self.convert_single_file(file_path)
            results.append(conversion_result)
            
            if conversion_result.success:
                # Save converted content
                output_file = self._generate_output_filename(file_path)
                
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(conversion_result.content)
                    
                    successful_conversions.append(str(output_file))
                    self.logger.success(f"Saved: {output_file.name}")
                except Exception as e:
                    error_msg = f"Failed to save {output_file.name}: {e}"
                    self.logger.failure(error_msg)
                    conversion_result.success = False
                    conversion_result.error = f"Save failed: {e}"
            else:
                self.logger.failure(f"Failed: {conversion_result.error}")
        
        # Generate summary
        successful_count = sum(1 for r in results if r.success)
        failed_count = len(results) - successful_count
        
        summary = {
            "total_files": len(files_to_process),
            "successful": successful_count,
            "failed": failed_count,
            "output_files": successful_conversions,
            "output_directory": str(self.output_dir)
        }
        
        self.logger.success(f"Conversion complete: {successful_count}/{len(files_to_process)} files successful")
        
        return {
            "summary": summary,
            "results": results
        }
    
    def _find_files(self, directory: Path, recursive: bool, patterns: Optional[List[str]]) -> List[Path]:
        """Find files to process in directory."""
        files = []
        
        if patterns:
            # Use custom patterns
            for pattern in patterns:
                if recursive:
                    files.extend(directory.rglob(pattern))
                else:
                    files.extend(directory.glob(pattern))
        else:
            # Use supported extensions
            for ext in self.supported_extensions:
                pattern = f"*{ext}"
                if recursive:
                    files.extend(directory.rglob(pattern))
                else:
                    files.extend(directory.glob(pattern))
        
        # Remove duplicates and sort
        return sorted(list(set(files)))
    
    def _generate_output_filename(self, input_file: Path) -> Path:
        """Generate output filename avoiding conflicts."""
        output_file = self.output_dir / f"{input_file.stem}.md"
        
        # Handle filename conflicts
        counter = 1
        while output_file.exists():
            output_file = self.output_dir / f"{input_file.stem}_{counter}.md"
            counter += 1
        
        return output_file
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        return sorted(list(self.supported_extensions))
    
    def get_conversion_stats(self, results: List[ConversionResult]) -> Dict[str, Any]:
        """Generate detailed statistics from conversion results."""
        stats = {
            "total_files": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "by_file_type": {},
            "by_extraction_method": {},
            "average_processing_time": 0,
            "errors": []
        }
        
        processing_times = []
        
        for result in results:
            # File type statistics
            file_type = result.file_type
            if file_type not in stats["by_file_type"]:
                stats["by_file_type"][file_type] = {"total": 0, "successful": 0, "failed": 0}
            
            stats["by_file_type"][file_type]["total"] += 1
            if result.success:
                stats["by_file_type"][file_type]["successful"] += 1
            else:
                stats["by_file_type"][file_type]["failed"] += 1
                stats["errors"].append({"file": result.source_file, "error": result.error})
            
            # Extraction method statistics
            if result.success and result.metadata:
                method = result.metadata.get("extraction_method", "unknown")
                if method not in stats["by_extraction_method"]:
                    stats["by_extraction_method"][method] = 0
                stats["by_extraction_method"][method] += 1
            
            # Processing time statistics
            if result.processing_time:
                processing_times.append(result.processing_time)
        
        if processing_times:
            stats["average_processing_time"] = sum(processing_times) / len(processing_times)
        
        return stats

