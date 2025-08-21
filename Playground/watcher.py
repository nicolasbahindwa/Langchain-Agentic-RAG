import time

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import os




class MyEventHandler(FileSystemEventHandler):
    
    def on_any_event(self, event:FileSystemEvent) -> None:
        print(event)
        
    

folder_to_watch = r"documents/raw_data"

event_handler = MyEventHandler()
observer = Observer()
observer.schedule(event_handler, folder_to_watch, recursive=False)
observer.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
finally:
    observer.start()
    observer.join()