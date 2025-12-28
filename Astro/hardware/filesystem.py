import os
import threading
import time


class FileWatcher:
    def __init__(self, extension: str):
        self.extension = extension
        self.watch_thread = threading.Thread(target=self.watch, daemon=True)
        self.watch_thread.start()

        self.files = []
        self.lock = threading.Lock()

    def watch(self):
        while True:
            all_files: str = os.listdir(os.getcwd())
            files = [
                f for f in all_files if f.endswith(self.extension)
            ]
            files.sort()
            with self.lock:
                self.files = files

            time.sleep(0.5)

    def get_files(self):
        with self.lock:
            return list(self.files)
