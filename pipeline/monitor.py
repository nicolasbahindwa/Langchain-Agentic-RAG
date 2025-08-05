import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable, Optional
from utils.logger import get_enhanced_logger, setup_logging

class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events"""
    
    def __init__(self, 
                 on_file_created: Optional[Callable[[str], None]] = None,
                 on_file_modified: Optional[Callable[[str], None]] = None,
                 on_file_deleted: Optional[Callable[[str], None]] = None):
        
        self.on_file_created = on_file_created or (lambda x: None)
        self.on_file_modified = on_file_modified or (lambda x: None)
        self.on_file_deleted = on_file_deleted or (lambda x: None)
        
        # Initialize enhanced logger for this handler
        self.logger = get_enhanced_logger("file_handler")
    
    # Core event handlers
    def on_created(self, event):
        if not event.is_directory:
            self.logger.info(f"Raw create event detected: {event.src_path}")
            self.on_file_created(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            self.logger.info(f"Raw modify event detected: {event.src_path}")
            self.on_file_modified(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.logger.warning(f"Raw delete event detected: {event.src_path}")
            self.on_file_deleted(event.src_path)

class FileMonitor:
    """File system monitor using watchdog"""
    
    def __init__(self, 
                 watch_paths: list,
                 on_file_created: Optional[Callable[[str], None]] = None,
                 on_file_modified: Optional[Callable[[str], None]] = None,
                 on_file_deleted: Optional[Callable[[str], None]] = None):
        
        self.watch_paths = watch_paths
        self.observer = Observer()
        
        # Initialize enhanced logger for monitor
        self.logger = get_enhanced_logger("file_monitor")
        
        # Create event handler
        self.event_handler = FileChangeHandler(
            on_file_created=on_file_created,
            on_file_modified=on_file_modified,
            on_file_deleted=on_file_deleted
        )
        
        # Setup observers
        for path in watch_paths:
            self.observer.schedule(self.event_handler, path, recursive=True)
            self.logger.success(f"Observer scheduled for path: {path}")
        
        self.is_monitoring = False
    
    def start_monitoring(self):
        """Start file monitoring"""
        if not self.is_monitoring:
            try:
                self.observer.start()
                self.is_monitoring = True
                self.logger.success(f"File monitoring started for paths: {', '.join(self.watch_paths)}")
            except Exception as e:
                self.logger.failure(f"Failed to start monitoring: {str(e)}")
                raise
    
    def stop_monitoring(self):
        """Stop file monitoring"""
        if self.is_monitoring:
            try:
                self.observer.stop()
                self.observer.join()
                self.is_monitoring = False
                self.logger.success("File monitoring stopped successfully")
            except Exception as e:
                self.logger.failure(f"Error stopping monitoring: {str(e)}")
    
    def run_forever(self):
        """Run monitoring indefinitely"""
        try:
            self.logger.performance("Starting infinite monitoring loop")
            while self.observer.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.logger.warning("Keyboard interrupt received in monitor loop")
        except Exception as e:
            self.logger.failure(f"Unexpected error in monitoring loop: {str(e)}")
            raise