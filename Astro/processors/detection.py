"""Source detection processors for identifying stars in images."""

from pydantic import Field
from .base import Processor
from ..core.data import Exposure, Star
import numpy as np
from skimage.feature import blob_doh
from astropy.stats import gaussian_sigma_to_fwhm


class SourceDetect(Processor):
    min_sigma: int = Field(
        default=10, ge=1, le=100, description="Minimum standard deviation for Gaussian kernel"
    )
    max_sigma: int = Field(
        default=30, ge=1, le=200, description="Maximum standard deviation for Gaussian kernel"
    )
    num_sigma: int = Field(
        default=10, ge=1, le=100, description="Number of intermediate sigma values"
    )
    threshold: float = Field(
        default=0.01, ge=0.001, le=1.0, description="Absolute detection threshold"
    )
    overlap: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Overlap threshold for eliminating smaller blobs"
    )
    log_scale: bool = Field(
        default=False, description="If True, interpolate sigma values in log space"
    )

    def __call__(self, exposure: Exposure) -> Exposure:
        # Run blob detection with all blob_doh parameters
        blobs = blob_doh(
            exposure.image,
            min_sigma=self.min_sigma,
            max_sigma=self.max_sigma,
            num_sigma=self.num_sigma,
            threshold=self.threshold,
            overlap=self.overlap,
            log_scale=self.log_scale,
        )

        stars: list[Star] = []
        for array in blobs:
            x = array[1]
            y = array[0]
            fwhm = array[2] * gaussian_sigma_to_fwhm
            star = Star(x=x, y=y, fwhm_x=fwhm, fwhm_y=fwhm, roundness=1.0)
            stars.append(star)

        unique, counts = np.unique(blobs[:, 2], return_counts=True)
        unique = unique * gaussian_sigma_to_fwhm

        exposure.stars = stars

        self.log["stars"] = len(blobs)
        self.log["fwhm"] = unique.tolist()
        self.log["fwhm_count"] = counts.tolist()
        self.log["avg_fwhm"] = np.mean(unique)

        return exposure
