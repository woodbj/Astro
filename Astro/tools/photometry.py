from ..core.exposure import Exposure
import numpy as np
from skimage.feature import blob_doh
from astropy.io import fits
from dataclasses import dataclass


@dataclass
class SourceDetector:
    min_sigma: float = 10
    target_channel: str = "green"

    def __call__(self, exposure: Exposure, **kwargs) -> np.ndarray:
        image = exposure.get_image()

        target_channel = self.target_channel
        match target_channel:
            case "red":
                target = image[:, :, 0]
            case "green":
                target = image[:, :, 1]
            case "blue":
                target = image[:, :, 2]
            case "mean":
                target = image.mean(axis=2)

        kwargs.setdefault("min_sigma", self.min_sigma)

        # blob_doh returns (row, col, sigma), convert to (X, Y) for clarity
        blobs = blob_doh(target, **kwargs)
        # Sort by sigma (brightest/most prominent first) for astrometry.net
        blobs = blobs[np.argsort(blobs[:, 2])]
        sources_xy = blobs[:, [1, 0]]
        exposure.sources = sources_xy
        self.make_xyls(exposure)
        return sources_xy

    def make_xyls(self, exposure: Exposure) -> None:
        # Create FITS table with sources stored as (X, Y)
        col1 = fits.Column(name="X", format="D", array=exposure.sources[:, 0])
        col2 = fits.Column(name="Y", format="D", array=exposure.sources[:, 1])
        hdu = fits.BinTableHDU.from_columns([col1, col2])

        # Add required headers
        hdu.header["IMAGEW"] = int(exposure.shape[1])
        hdu.header["IMAGEH"] = int(exposure.shape[0])
        hdu.writeto(f"{exposure.path.with_suffix(".xyls")}", overwrite=True)
