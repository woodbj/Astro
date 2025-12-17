from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time


class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            # Your script logic here


class Tracking:
    def __init__(self):
        self.observer = Observer()
        self.observer.schedule(FileHandler(), path='.', recursive=False)
        self.observer.start()

    def run(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()
