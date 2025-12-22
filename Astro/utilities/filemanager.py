from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
from astropy.table import QTable, Column
from astropy.time import Time


class FileManager:
    def __init__(self, extension: str):
        self.extension = extension
        self.files: list[str] = [
            f for f in os.listdir() if f.endswith(extension)
        ]
        self.files.sort()

        self.observer = Observer()
        self.observer.schedule(FileHandler(self), path='.', recursive=False)
        self.observer.start()

        self.data = QTable()
        self.data["Image"] = Column([], dtype=str)
        self.data["Time"] = Column([], dtype=Time)

    def get_latest(self):
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
