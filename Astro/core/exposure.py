import exiftool

# import json
import rawpy
import numpy as np
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from dataclasses import dataclass, field, asdict
from datetime import datetime
from astropy.io import fits
from pathlib import Path
import os
import json
from queue import Queue
import threading
import pandas as pd


class DataEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, Exposure):
            return o.id
        if isinstance(o, datetime):
            return str(o)
        return super().default(o)


class Data:
    def to_df(self, key=None, orient="index", dtype=None, columns=None):
        data = self.to_dict(serialise=False)
        if key is not None:
            data = data[key]
        return pd.DataFrame.from_dict(data=data, orient=orient, dtype=dtype, columns=columns)

    def to_dict(self, serialise=True):
        if serialise:
            return json.loads(str(self))
        else:
            return asdict(self)

    def __str__(self):
        return json.dumps(asdict(self), cls=DataEncoder)


@dataclass(unsafe_hash=True)
class Exposure(Data):
    id: str
    path: Path = field(default=None, hash=False, compare=False)
    time: datetime = field(default=None, hash=False, compare=False)
    ra: float = field(default=None, hash=False, compare=False)
    dec: float = field(default=None, hash=False, compare=False)
    alt: float = field(default=None, hash=False, compare=False)
    az: float = field(default=None, hash=False, compare=False)

    def __post_init__(self):
        self.path = Path(os.path.abspath(self.id))
        if not self.path.is_file():
            raise Exception("Path is not a file")

        self.data = dict()
        self.load_metadata()

    def get_wcs(self) -> WCS:
        path = self.path.with_suffix(".wcs")
        try:
            self.wcs: WCS = WCS(fits.getheader(path))
            crpix = tuple(s / 2 for s in self.shape[::-1])
            self.radec = self.wcs.pixel_to_world(*crpix)
            return self.wcs
        except Exception as e:
            raise Exception(f"{e}: Could not load WCS")

    def get_image(self) -> np.ndarray:
        try:
            with rawpy.imread(str(self.path)) as raw:
                image: np.ndarray = raw.postprocess()
            self.shape = image.shape[:2]
            return image

        except Exception as e:
            raise Exception(f"{e}: Could not generate np.ndarray from image")

    def load_metadata(self) -> None:
        try:
            with exiftool.ExifToolHelper() as et:
                self.exif = et.get_metadata(self.id)[0]
        except Exception as e:
            raise Exception(f"{e}: Could not extract exif data")

        with open(self.path.with_suffix(".json"), "w") as f:
            json.dump(self.exif, f, indent=2)

        # Get pixel size
        res = self.exif["EXIF:FocalPlaneXResolution"]
        scale = 25400 if self.exif["EXIF:FocalPlaneResolutionUnit"] == 2 else 10000
        pixel_size = scale / res
        self.data["pixel_size"] = pixel_size

        # Get time
        time: str = self.exif["QuickTime:CreateDate"]
        time = time.replace(":", "-", 2)
        time = time.replace(" ", "T")
        self.data["time_iso"] = time
        self.time = datetime.fromisoformat(time)


@dataclass
class Library(Data):
    exposures: dict[Exposure] = field(default_factory=dict)

    def __post_init__(self):
        self.files: set[Path] = set()
        self.processing_queue: Queue = Queue()
        self.lock = threading.Lock()

    def put_files(self, files: set[Path] | None):
        new_files = files - self.files
        with self.lock:
            self.files.update(files)

            for file in new_files:
                exp = Exposure(file.name)
                self.exposures[exp.id] = exp

    def get_unprocessed(self):
        with self.lock:
            return self.processing_queue
