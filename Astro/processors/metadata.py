from .base import Processor
from ..core.data import Exposure
from ..core.filesystem import ImageIO
import exiftool
from datetime import datetime


class MetaData(Processor):
    def __call__(self, exposure: Exposure) -> Exposure:
        with exiftool.ExifToolHelper() as et:
            exif = et.get_metadata(str(exposure.path.absolute()))[0]

        # Get exif data
        time: str = exif["QuickTime:CreateDate"]
        time = time.replace(":", "-", 2)
        time = time.replace(" ", "T")

        # save to camera
        exposure.time = datetime.fromisoformat(time)
        exposure.iso = exif["EXIF:ISO"]
        exposure.aperture = exif["Composite:Aperture"]
        exposure.shutter = exif["Composite:ShutterSpeed"]

        # save to log
        self.log["iso"] = exposure.iso
        self.log["aperture"] = exposure.aperture
        self.log["shutter"] = exposure.shutter
        self.log["time"] = exposure.time

        return exposure


class LoadImage(Processor):
    def __call__(self, exposure: Exposure) -> Exposure:
        exposure.image = ImageIO.get_raw(exposure.path)
        exposure.height = exposure.image.shape[0]
        exposure.width = exposure.image.shape[1]
        self.log["image"] = f"{exposure.image.shape}"
        return exposure
