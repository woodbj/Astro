"""Image processing pipeline processors for astrophotography.

This module contains specialized processors for extracting star data from
astrophotography images. Processors are organized by function:

- calibration: Flatten, background subtraction
- detection: Source detection and filtering
- measurement: PSF measurement, centroid refinement, photometry
- enhancement: Downsampling, normalization, stretching
- output: Data export and visualization

Each processor inherits from the base Processor class and implements
the __call__(image, data) method.
"""

from .calibration import Flatten, BackgroundSubtract
from .detection import SourceDetect
from .astrometry import PlateSolve
from .measurement import PSFMeasure
from .enhancement import Downsample, Normalize
from .output import StarCatalogExport
from .metadata import MetaData, LoadImage

__all__ = [
    "Flatten",
    "BackgroundSubtract",
    "SourceDetect",
    "PSFMeasure",
    "Downsample",
    "Normalize",
    "StarCatalogExport",
    "MetaData",
    "LoadImage",
    "PlateSolve"
]
