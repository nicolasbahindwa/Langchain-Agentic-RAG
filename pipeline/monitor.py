import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable, Optional

class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events"""
    
    def __init__(self, 
                 on_file_created: Optional[Callable[[str], None]] = None,
                 on_file_modified: Optional[Callable[[str], None]] = None,
                 on_file_deleted: Optional[Callable[[str], None]] = None):
        
        self.on_file_created = on_file_created or (lambda x: None)
        self.on_file_modified = on_file_modified or (lambda x: None)
        self.on_file_deleted = on_file_deleted or (lambda x: None)
    
    # Core event handlers
    def on_created(self, event):
        if not event.is_directory:
            print(f"👶 [MONITOR] Raw create event: {event.src_path}")
            self.on_file_created(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            print(f"📝 [MONITOR] Raw modify event: {event.src_path}")
            self.on_file_modified(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            print(f"💀 [MONITOR] Raw delete event: {event.src_path}")
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
        
        # Create event handler
        self.event_handler = FileChangeHandler(
            on_file_created=on_file_created,
            on_file_modified=on_file_modified,
            on_file_deleted=on_file_deleted
        )
        
        # Setup observers
        for path in watch_paths:
            self.observer.schedule(self.event_handler, path, recursive=True)
        
        self.is_monitoring = False
    
    def start_monitoring(self):
        """Start file monitoring"""
        if not self.is_monitoring:
            self.observer.start()
            self.is_monitoring = True
            print("🔍 [MONITOR] Watching paths: " + ", ".join(self.watch_paths))
    
    def stop_monitoring(self):
        """Stop file monitoring"""
        if self.is_monitoring:
            self.observer.stop()
            self.observer.join()
            self.is_monitoring = False
            print("👋 [MONITOR] Stopped all observers")
    
    def run_forever(self):
        """Run monitoring indefinitely"""
        try:
            while self.observer.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n⚠️ [MONITOR] Keyboard interrupt in monitor loop")