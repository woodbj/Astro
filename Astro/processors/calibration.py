"""Calibration and pre-processing processors."""

from pydantic import Field
from typing import Literal
from .base import Processor
from ..core.data import Exposure
import numpy as np
from astropy.stats import sigma_clipped_stats


class Flatten(Processor):
    """Extract a single color channel from RGB image.

    Converts a 3-channel RGB image to a single-channel grayscale image
    by selecting one color channel. This is often the first step in
    astrophotography processing pipelines.

    For color cameras, the green channel typically has the best SNR.
    For monochrome cameras, this processor passes through unchanged.

    Attributes:
        channel: Color channel to extract ('Red', 'Green', or 'Blue')
    """

    channel: Literal["Red", "Green", "Blue"] = Field(
        default="Green", description="Color channel to extract"
    )

    def __call__(self, exposure: Exposure) -> Exposure:
        """Extract color channel from image.

        Args:
            image: Input image (RGB or grayscale)
            data: Pipeline data dictionary

        Returns:
            Tuple of (flattened_image, data)
        """
        if not isinstance(exposure.image, np.ndarray):
            raise Exception("Exposure has no image loaded")

        image: np.ndarray = exposure.image

        # If already 2D (grayscale), return as-is
        if image.ndim == 2:
            self.log["channel"] = "already greyscale"
            return exposure

        # Map channel name to index
        channel_map = {"Red": 0, "Green": 1, "Blue": 2}

        channel = channel_map[self.channel]
        self.log["channel"] = channel
        exposure.image = image[:, :, channel]
        return exposure


class BackgroundSubtract(Processor):
    """Remove background sky signal using sigma-clipped statistics.

    Uses astropy's sigma_clipped_stats to robustly estimate the
    background level and subtract it from the image. This is essential
    for accurate photometry and source detection.

    The sigma-clipping algorithm iteratively removes outliers (stars)
    to get a clean estimate of the sky background level.

    Attributes:
        sigma: Number of standard deviations for sigma clipping
        n_sigma: Number of iterations (0 = auto-determine)
    """

    sigma: float = Field(default=3.0, ge=0, lt=10, description="Sigma threshold for clipping")

    def __call__(self, exposure: Exposure) -> Exposure:
        """Subtract background from image.

        Args:
            image: Input image
            data: Pipeline data dictionary

        Returns:
            Tuple of (background_subtracted_image, data) where data
            is updated with background statistics
        """
        # Calculate robust background statistics
        image: np.ndarray = exposure.image
        mean, median, std = sigma_clipped_stats(image, sigma=self.sigma)

        # Subtract median background
        image = image - median

        # Store statistics in data
        self.log["mean"] = float(mean)
        self.log["median"] = float(median)
        self.log["std"] = float(std)
        exposure.mean = mean
        exposure.median = median
        exposure.std = std

        return exposure
