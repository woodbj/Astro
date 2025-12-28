import exiftool

# import json
import rawpy
import numpy as np
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from dataclasses import dataclass, field  # , asdict, field
from datetime import datetime
from astropy.io import fits
from pathlib import Path
import os
import json


@dataclass
class Exposure:
    id: str
    path: Path = None
    time: datetime = None
    radec: SkyCoord = None
    exif: dict = None
    data: dict = field(default_factory=dict)
    sources: Path = None
    wcs: WCS = None
    shape: tuple[int] = None

    def __post_init__(self):
        self.path = Path(os.path.abspath(self.id))
        if self.path.is_file():
            # self.load_metadata()
            ...
        else:
            raise Exception("Could not resolve path")

    def get_wcs(self) -> WCS:
        path = self.path.with_suffix(".wcs")
        try:
            self.wcs: WCS = WCS(fits.getheader(path))
            crpix = tuple(s/2 for s in self.shape[::-1])
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
