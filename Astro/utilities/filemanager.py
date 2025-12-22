from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
from astropy.table import QTable, Column
from astropy.time import Time


class FileManager:
    def __init__(self, extension: str, watch_path: str = '.'):
        self.extension = extension
        self.watch_path = watch_path
        self.files: list[str] = [
            f for f in os.listdir(watch_path) if f.endswith(extension)
        ]
        self.files.sort()
        print(self.files)

        self.observer = Observer()
        self.observer.schedule(FileHandler(self), path=watch_path, recursive=False)
        self.observer.start()

        self.data = QTable()
        self.data["Image"] = Column([], dtype=str)
        self.data["Time"] = Column([], dtype=Time)

    def refresh(self):
        """Manually refresh the file list from disk."""
        self.files = [
            f for f in os.listdir(self.watch_path) if f.endswith(self.extension)
        ]
        self.files.sort()

    def get_latest(self):
        # Refresh the file list to catch any missed events
        self.refresh()

        if not self.files:
            return None
        self.files.sort()
        return self.files[-1]


class FileHandler(FileSystemEventHandler):
    def __init__(self, manager: FileManager):
        super().__init__()
        self.manager = manager

    def on_created(self, event):
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)
        if filename.endswith(self.manager.extension):
            self.manager.files.append(filename)
            self.manager.files.sort()
            print(self.manager.files)
