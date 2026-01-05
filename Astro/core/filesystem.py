import os
import threading
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Callable
import numpy as np
import rawpy
import exiftool
import json


@dataclass(frozen=True)
class Watch:
    """Configuration for watching a directory for new files with a specific extension.

    Attributes:
        path: Directory path to monitor for new files.
        ext: File extension to filter for (e.g., '.fits', '.jpg').
        callback: Function to call when new files are detected.
                  Receives a list of new file paths as argument.

    Raises:
        Exception: If the path doesn't exist or is not a directory.
    """
    path: Path
    ext: str
    callback: Callable[[list[Path]], None]

    def __post_init__(self) -> None:
        """Validate the watch configuration after initialization."""
        if not self.path.absolute().exists():
            raise Exception("Path does not exist")

        if not self.path.is_dir():
            raise Exception("Path should not be a file")


class FileSystem:
    """Manages filesystem operations and file watching for astrophotography data.

    Monitors directories for new files matching specific extensions and triggers
    callbacks when new files are detected. Runs watching in a background thread.

    Attributes:
        home: Absolute path to the home/working directory.
        lock: Thread lock for synchronizing filesystem operations.
        watchlist: List of active Watch configurations.
        files: Mapping of Watch objects to their tracked file lists.
        watching: Flag indicating if the watch thread is running.
    """

    def __init__(self, home: Path | None = None) -> None:
        """Initialize the filesystem manager.

        Args:
            home: Path to set as the home/working directory.
        """
        if home is None:
            home = Path(os.getcwd())
        self.home: Path = home.absolute()
        os.chdir(self.home)
        self.lock: threading.Lock = threading.Lock()
        self.watchlist: list[Watch] = []
        self.files: dict[Watch, list[Path]] = dict()
        self.watching: bool = False
        self.interval: float = 0.5

    def cwd(self, home: Path) -> None:
        """Change the current working directory.

        Args:
            home: Path to set as the new working directory.

        Raises:
            Exception: If changing directory fails.
        """
        try:
            os.chdir(home.absolute())
            self.home = Path(os.getcwd())
        except Exception as e:
            raise Exception(f"{e}: os.chdir({home}) failed")

    def start_watch(self) -> None:
        """Start the file watching thread.

        Creates and starts a daemon thread that monitors directories
        for new files based on configured Watch objects.
        """
        self.watching = True
        self.watch_thread = threading.Thread(target=self.watch, daemon=True)
        self.watch_thread.start()

    def stop_watch(self) -> None:
        """Stop the file watching thread.

        Signals the watch thread to stop and waits for it to complete.
        Does nothing if watching is not currently active.
        """
        if self.watching is False:
            return
        self.watching = False
        self.watch_thread.join()

    def add_watch(self, watch: Watch) -> None:
        """Add a new directory watch configuration.

        Temporarily stops the watch thread, adds the new watch to the list,
        and restarts watching.

        Args:
            watch: Watch configuration to add to the monitoring list.
        """
        self.stop_watch()
        self.watchlist.append(watch)
        self.files[watch] = []
        self.start_watch()

    def watch(self) -> None:
        """Main watch loop executed in background thread.

        Continuously monitors all configured directories for files
        matching the specified extensions. When new files are detected,
        triggers the associated callbacks.

        Raises:
            Exception: If a watched path doesn't exist during monitoring.
        """
        while self.watching:
            for w in self.watchlist:
                # build absolute path of watch
                if w.path.is_absolute():
                    path = w.path
                else:
                    path = self.home / w.path

                # check path exists
                if not path.exists():
                    raise Exception(f"Path {path} does not exist")

                # populate file list
                files = [(path / Path(f)).absolute() for f in os.listdir(path)]
                files = list(f for f in files if f.suffix == w.ext)
                files.sort()

                # callback only if there are new files
                if len(files) > 0:
                    w.callback(files)

            time.sleep(self.interval)


class ImageIO:
    output_bps = 8
    gamma = (1.0, 1.0)
    exp_shift = 0.0

    @classmethod
    def get_raw(cls, path: Path) -> np.ndarray:
        with rawpy.imread(str(path)) as raw:
            image: np.ndarray = raw.postprocess(
                output_bps=cls.output_bps, gamma=cls.gamma, exp_shift=cls.exp_shift
            )
            return image

    @classmethod
    def get_metadata(cls, path: Path) -> dict:
        with exiftool.ExifToolHelper() as et:
            exif = et.get_metadata(str(path))[0]

        with open(path.with_suffix(".json").with_stem(f"{path.stem}_exif"), "w") as f:
            json.dump(exif, f, indent=2)

        return exif
