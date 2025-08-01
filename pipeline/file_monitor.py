# file_monitor.py
"""
File monitoring module using watchdog
"""
import os
import time
import logging
from pathlib import Path
from typing import Callable, Dict, Set, Optional
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent

logger = logging.getLogger(__name__)


class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events with debouncing"""
    
    def __init__(self, 
                 on_file_created: Optional[Callable[[str], None]] = None,
                 on_file_modified: Optional[Callable[[str], None]] = None,
                 on_file_deleted: Optional[Callable[[str], None]] = None,
                 debounce_seconds: int = 2,
                 supported_extensions: Optional[Set[str]] = None):
        """
        Initialize file change handler
        
        Args:
            on_file_created: Callback for file creation events
            on_file_modified: Callback for file modification events
            on_file_deleted: Callback for file deletion events
            debounce_seconds: Seconds to wait before processing file changes
            supported_extensions: Set of supported file extensions
        """
        super().__init__()
        
        self.on_file_created = on_file_created or (lambda x: None)
        self.on_file_modified = on_file_modified or (lambda x: None)
        self.on_file_deleted = on_file_deleted or (lambda x: None)
        
        self.debounce_seconds = debounce_seconds
        self.supported_extensions = supported_extensions or {
            '.txt', '.pdf', '.csv', '.docx', '.doc', '.json'
        }
        
        # Debouncing: track pending file operations
        self.pending_creates: Dict[str, float] = {}
        self.pending_modifies: Dict[str, float] = {}
        self.pending_deletes: Dict[str, float] = {}
        
        # Track processed files to avoid duplicate events
        self.recently_processed: Dict[str, float] = {}
        self.recent_window = 1.0  # seconds
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file extension is supported"""
        return Path(file_path).suffix.lower() in self.supported_extensions
    
    def _should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed (exists, is file, supported extension)"""
        if not os.path.exists(file_path):
            return False
        
        if not os.path.isfile(file_path):
            return False
        
        if not self._is_supported_file(file_path):
            logger.debug(f"Unsupported file type: {file_path}")
            return False
        
        # Check if recently processed (avoid duplicate events)
        current_time = time.time()
        if file_path in self.recently_processed:
            if current_time - self.recently_processed[file_path] < self.recent_window:
                logger.debug(f"Recently processed, skipping: {file_path}")
                return False
        
        return True
    
    def _mark_as_processed(self, file_path: str):
        """Mark file as recently processed"""
        self.recently_processed[file_path] = time.time()
        
        # Clean up old entries
        current_time = time.time()
        expired_files = [
            fp for fp, timestamp in self.recently_processed.items()
            if current_time - timestamp > self.recent_window * 2
        ]
        for fp in expired_files:
            del self.recently_processed[fp]
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if self._should_process_file(file_path):
            self.pending_creates[file_path] = time.time()
            logger.debug(f"File created (pending): {file_path}")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if self._should_process_file(file_path):
            self.pending_modifies[file_path] = time.time()
            logger.debug(f"File modified (pending): {file_path}")
    
    def on_deleted(self, event):
        """Handle file deletion events"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        # For deleted files, we can't check if they should be processed
        # but we can check the extension
        if self._is_supported_file(file_path):
            self.pending_deletes[file_path] = time.time()
            logger.debug(f"File deleted (pending): {file_path}")
    
    def process_pending_events(self):
        """Process pending file events after debounce period"""
        current_time = time.time()
        
        # Process pending creates
        ready_creates = [
            file_path for file_path, timestamp in self.pending_creates.items()
            if current_time - timestamp >= self.debounce_seconds
        ]
        
        for file_path in ready_creates:
            del self.pending_creates[file_path]
            if self._should_process_file(file_path):
                try:
                    logger.info(f"Processing file creation: {file_path}")
                    self.on_file_created(file_path)
                    self._mark_as_processed(file_path)
                except Exception as e:
                    logger.error(f"Error processing file creation {file_path}: {str(e)}")
        
        # Process pending modifies
        ready_modifies = [
            file_path for file_path, timestamp in self.pending_modifies.items()
            if current_time - timestamp >= self.debounce_seconds
        ]
        
        for file_path in ready_modifies:
            del self.pending_modifies[file_path]
            if self._should_process_file(file_path):
                try:
                    logger.info(f"Processing file modification: {file_path}")
                    self.on_file_modified(file_path)
                    self._mark_as_processed(file_path)
                except Exception as e:
                    logger.error(f"Error processing file modification {file_path}: {str(e)}")
        
        # Process pending deletes
        ready_deletes = [
            file_path for file_path, timestamp in self.pending_deletes.items()
            if current_time - timestamp >= self.debounce_seconds
        ]
        
        for file_path in ready_deletes:
            del self.pending_deletes[file_path]
            try:
                logger.info(f"Processing file deletion: {file_path}")
                self.on_file_deleted(file_path)
            except Exception as e:
                logger.error(f"Error processing file deletion {file_path}: {str(e)}")
    
    def get_pending_count(self) -> Dict[str, int]:
        """Get count of pending operations"""
        return {
            'creates': len(self.pending_creates),
            'modifies': len(self.pending_modifies),
            'deletes': len(self.pending_deletes)
        }


class FileMonitor:
    """File system monitor using watchdog"""
    
    def __init__(self, 
                 watch_paths: list[str],
                 on_file_created: Optional[Callable[[str], None]] = None,
                 on_file_modified: Optional[Callable[[str], None]] = None,
                 on_file_deleted: Optional[Callable[[str], None]] = None,
                 recursive: bool = True,
                 debounce_seconds: int = 2,
                 supported_extensions: Optional[Set[str]] = None):
        """
        Initialize file monitor
        
        Args:
            watch_paths: List of paths to monitor
            on_file_created: Callback for file creation
            on_file_modified: Callback for file modification
            on_file_deleted: Callback for file deletion
            recursive: Whether to monitor subdirectories
            debounce_seconds: Debounce period for file events
            supported_extensions: Supported file extensions
        """
        self.watch_paths = [Path(path) for path in watch_paths]
        self.recursive = recursive
        
        # Validate watch paths
        for path in self.watch_paths:
            if not path.exists():
                raise ValueError(f"Watch path does not exist: {path}")
            if not path.is_dir():
                raise ValueError(f"Watch path is not a directory: {path}")
        
        # Initialize event handler
        self.event_handler = FileChangeHandler(
            on_file_created=on_file_created,
            on_file_modified=on_file_modified,
            on_file_deleted=on_file_deleted,
            debounce_seconds=debounce_seconds,
            supported_extensions=supported_extensions
        )
        
        # Initialize observer
        self.observer = Observer()
        self.is_monitoring = False
    
    def start_monitoring(self):
        """Start file monitoring"""
        if self.is_monitoring:
            logger.warning("File monitor is already running")
            return
        
        logger.info(f"Starting file monitor for paths: {[str(p) for p in self.watch_paths]}")
        
        # Schedule monitoring for each path
        for watch_path in self.watch_paths:
            self.observer.schedule(
                self.event_handler,
                str(watch_path),
                recursive=self.recursive
            )
        
        self.observer.start()
        self.is_monitoring = True
        
        logger.info("File monitor started successfully")
    
    def stop_monitoring(self):
        """Stop file monitoring"""
        if not self.is_monitoring:
            logger.warning("File monitor is not running")
            return
        
        logger.info("Stopping file monitor...")
        self.observer.stop()
        self.observer.join()
        self.is_monitoring = False
        logger.info("File monitor stopped")
    
    def process_pending_events(self):
        """Process any pending file events"""
        if self.is_monitoring:
            self.event_handler.process_pending_events()
    
    def run_forever(self, process_interval: float = 1.0):
        """
        Run file monitor indefinitely
        
        Args:
            process_interval: Interval for processing pending events
        """
        try:
            if not self.is_monitoring:
                self.start_monitoring()
            
            logger.info("File monitor running. Press Ctrl+C to stop.")
            
            while True:
                time.sleep(process_interval)
                self.process_pending_events()
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop_monitoring()
    
    def get_stats(self) -> Dict[str, any]:
        """Get monitoring statistics"""
        pending = self.event_handler.get_pending_count()
        
        return {
            'is_monitoring': self.is_monitoring,
            'watch_paths': [str(p) for p in self.watch_paths],
            'recursive': self.recursive,
            'supported_extensions': list(self.event_handler.supported_extensions),
            'pending_events': pending,
            'recently_processed_count': len(self.event_handler.recently_processed)
        }
    
    def scan_existing_files(self) -> list[str]:
        """Scan for existing files in watch paths"""
        existing_files = []
        
        for watch_path in self.watch_paths:
            pattern = "**/*" if self.recursive else "*"
            
            for file_path in watch_path.glob(pattern):
                if file_path.is_file() and self.event_handler._is_supported_file(str(file_path)):
                    existing_files.append(str(file_path))
        
        logger.info(f"Found {len(existing_files)} existing files")
        return existing_files