import logging
from typing import List
from monitor import FileMonitor

class DataExtractionPipeline:
    """Simplified pipeline focusing only on file monitoring"""
    
    def __init__(self, watch_paths: List[str]):
        self.watch_paths = watch_paths
        
        # Initialize file monitor with print handlers
        self.file_monitor = FileMonitor(
            watch_paths=watch_paths,
            on_file_created=self._handle_file_created,
            on_file_modified=self._handle_file_modified,
            on_file_deleted=self._handle_file_deleted
        )
    
    # File event handlers with prints
    def _handle_file_created(self, file_path: str):
        print(f"🚀 [ORCHESTRATOR] NEW FILE DETECTED: {file_path}")
    
    def _handle_file_modified(self, file_path: str):
        print(f"🔄 [ORCHESTRATOR] FILE MODIFIED: {file_path}")
    
    def _handle_file_deleted(self, file_path: str):
        print(f"❌ [ORCHESTRATOR] FILE DELETED: {file_path}")
    
    def start_monitoring(self):
        print("🟢 [ORCHESTRATOR] STARTING FILE MONITORING")
        self.file_monitor.start_monitoring()
    
    def stop_monitoring(self):
        print("🔴 [ORCHESTRATOR] STOPPING FILE MONITORING")
        self.file_monitor.stop_monitoring()
    
    def run_forever(self):
        """Main execution loop"""
        try:
            self.start_monitoring()
            print("👀 [ORCHESTRATOR] Monitoring files... (Press Ctrl+C to stop)")
            self.file_monitor.run_forever()
        except KeyboardInterrupt:
            print("\n⌨️ [ORCHESTRATOR] Keyboard interrupt received")
        finally:
            self.stop_monitoring()