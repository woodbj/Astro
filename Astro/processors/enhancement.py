"""Image enhancement processors for pre-processing and optimization."""

from pydantic import Field
from .base import Processor
import numpy as np
from skimage.transform import downscale_local_mean


class Downsample(Processor):
    """Downsample image by binning pixels for faster processing.

    Binning is a common technique in astrophotography to reduce noise and
    processing time. A 2x2 bin combines 4 pixels into 1, reducing image
    dimensions by half and improving SNR.

    This processor is particularly useful before computationally expensive
    operations like source detection on large images.

    Attributes:
        factor: Downsampling factor (2 = half size, 4 = quarter size, etc.)
        preserve_dtype: Whether to preserve the original data type
    """

    factor: int = Field(
        default=2, ge=1, le=8, description="Downsampling factor (2=half, 4=quarter, etc)"
    )
    preserve_dtype: bool = Field(default=True, description="Preserve original data type")

    def __call__(self, image: np.ndarray, data: dict):
        """Downsample the image by binning.

        Args:
            image: Input image (grayscale or RGB)
            data: Pipeline data dictionary

        Returns:
            Tuple of (downsampled_image, data) where data is updated with:
                - original_shape: Original image dimensions
                - downsample_factor: Factor used for downsampling
        """
        if self.factor == 1:
            # No downsampling needed
            return image, data

        original_dtype = image.dtype
        original_shape = image.shape

        # Determine downsampling factors for each dimension
        if image.ndim == 3:
            # RGB image: downsample spatial dimensions only
            factors = (self.factor, self.factor, 1)
        else:
            # Grayscale image
            factors = (self.factor, self.factor)

        # Perform downsampling using local mean
        downsampled = downscale_local_mean(image, factors)

        # Preserve dtype if requested
        if self.preserve_dtype:
            if np.issubdtype(original_dtype, np.integer):
                downsampled = np.round(downsampled).astype(original_dtype)
            else:
                downsampled = downsampled.astype(original_dtype)

        # Store metadata (convert numpy shape tuples to lists)
        data["original_shape"] = list(original_shape)
        data["downsample_factor"] = self.factor
        data["downsampled_shape"] = list(downsampled.shape)

        return downsampled, data


class Normalize(Processor):
    """Normalize image values to a standard range.

    Normalization is useful for:
    - Preparing images for consistent processing
    - Bringing out faint details
    - Standardizing data for algorithms that expect specific ranges

    Attributes:
        method: Normalization method ('minmax', 'percentile', 'zscore')
        output_range: Target output range as (min, max) tuple
        lower_percentile: Lower percentile for percentile method
        upper_percentile: Upper percentile for percentile method
    """

    method: str = Field(default="minmax", description="Normalization method")
    output_min: float = Field(default=0.0, description="Minimum output value")
    output_max: float = Field(default=255.0, description="Maximum output value")
    lower_percentile: float = Field(
        default=1.0, ge=0, le=50, description="Lower percentile for clipping"
    )
    upper_percentile: float = Field(
        default=99.0, ge=50, le=100, description="Upper percentile for clipping"
    )

    def __call__(self, image: np.ndarray, data: dict):
        """Normalize image values.

        Args:
            image: Input image
            data: Pipeline data dictionary

        Returns:
            Tuple of (normalized_image, data)
        """
        if self.method == "minmax":
            # Simple min-max normalization
            img_min = image.min()
            img_max = image.max()

        elif self.method == "percentile":
            # Percentile-based normalization (robust to outliers)
            img_min = np.percentile(image, self.lower_percentile)
            img_max = np.percentile(image, self.upper_percentile)

        else:
            raise ValueError(f"Unknown normalization method: {self.method}")

        # Avoid division by zero
        if img_max == img_min:
            normalized = np.full_like(image, self.output_min, dtype=float)
        else:
            # Normalize to [0, 1]
            normalized = (image - img_min) / (img_max - img_min)
            # Scale to output range
            normalized = normalized * (self.output_max - self.output_min) + self.output_min

        # Store statistics
        data["normalize_method"] = self.method
        data["normalize_input_min"] = float(img_min)
        data["normalize_input_max"] = float(img_max)

        return normalized, data
