"""Output processors for exporting pipeline results."""

from pydantic import Field
from .base import Processor
import numpy as np


class StarCatalogExport(Processor):
    """Export detected stars and measurements to structured catalog format.

    This processor combines source positions with optional PSF measurements
    into a structured catalog that can be exported to CSV or JSON format.
    The catalog is suitable for:
    - Feeding to plate solving algorithms
    - Quality analysis and filtering
    - Long-term tracking and comparison

    The catalog is stored in the data dict and can be saved to disk
    by the PipelineManager.

    Attributes:
        format: Output format ('csv' or 'json')
        include_psf: Whether to include PSF measurements in catalog
    """

    format: str = Field(
        default="csv", pattern="^(csv|json)$", description="Output format (csv or json)"
    )
    include_psf: bool = Field(default=True, description="Include PSF measurements in catalog")

    def __call__(self, image: np.ndarray, data: dict):
        """Export star catalog from pipeline data.

        Args:
            image: Input image (passed through unchanged)
            data: Pipeline data dict (must contain 'sources')

        Returns:
            Tuple of (image, data) where data is updated with:
                - star_catalog: List of dicts containing star information

        Raises:
            ValueError: If 'sources' not found in data
        """
        if "sources" not in data:
            raise ValueError("No sources to export - run SourceDetect first")

        # Build catalog from sources
        catalog = []
        sources = data["sources"]

        # Create PSF lookup dict for faster matching
        psf_lookup = {}
        if self.include_psf and "psf_metrics" in data:
            for metric in data["psf_metrics"]:
                # Use (x, y) as key with small tolerance for floating point
                key = (round(metric["x"], 1), round(metric["y"], 1))
                psf_lookup[key] = metric

        # Build catalog entries
        for i, (x, y) in enumerate(sources):
            entry = {"id": i, "x": float(x), "y": float(y)}

            # Add PSF metrics if available
            if self.include_psf:
                key = (round(x, 1), round(y, 1))
                if key in psf_lookup:
                    metric = psf_lookup[key]
                    entry["fwhm"] = metric.get("fwhm")
                    entry["fwhm_x"] = metric.get("fwhm_x")
                    entry["fwhm_y"] = metric.get("fwhm_y")
                    entry["eccentricity"] = metric.get("eccentricity")
                    entry["amplitude"] = metric.get("amplitude")
                    entry["background"] = metric.get("background")

            catalog.append(entry)

        # Store catalog in data dict
        data["star_catalog"] = catalog
        data["catalog_format"] = self.format

        return image, data
