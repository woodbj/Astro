"""PSF measurement processors for star characterization."""

from pydantic import Field
from .base import Processor
import numpy as np
from scipy.optimize import curve_fit
from scipy.ndimage import center_of_mass


class PSFMeasure(Processor):
    """Measure PSF (Point Spread Function) metrics for detected sources.

    This processor fits a 2D Gaussian function to each detected star and
    extracts key metrics including FWHM (Full Width at Half Maximum),
    eccentricity, and amplitude. These measurements are critical for:
    - Focus quality assessment
    - Seeing conditions monitoring
    - Star quality filtering for plate solving

    The processor expects 'sources' to already exist in the data dict
    (populated by SourceDetect processor).

    Attributes:
        box_size: Size of the box (in pixels) to extract around each star
                 for PSF fitting. Should be large enough to capture the
                 entire star profile (typically 4-6x FWHM).
        max_sources: Maximum number of sources to measure. Processing is
                    limited to the brightest sources for performance.
    """

    box_size: int = Field(
        default=40, ge=10, le=200, description="PSF extraction box size in pixels"
    )
    max_sources: int = Field(default=100, ge=1, le=1000, description="Maximum sources to measure")

    def __call__(self, image: np.ndarray, data: dict):
        """Measure PSF metrics for detected sources.

        Args:
            image: Input image (grayscale or RGB)
            data: Pipeline data dict (must contain 'sources')

        Returns:
            Tuple of (image, data) where data is updated with:
                - psf_metrics: List of dicts with FWHM measurements
                - median_fwhm: Median FWHM across all measured stars
                - mean_fwhm: Mean FWHM across all measured stars

        Raises:
            ValueError: If 'sources' not found in data (run SourceDetect first)
        """
        if "sources" not in data:
            raise ValueError("No sources found - run SourceDetect first")

        # Work with grayscale image
        if image.ndim == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image

        # Limit to max_sources (already sorted by prominence from SourceDetect)
        sources = data["sources"][: self.max_sources]
        psf_metrics = []

        # Measure PSF for each source
        for x, y in sources:
            result = self._calculate_fwhm(gray, int(x), int(y))
            if result is not None:
                result["x"] = float(x)
                result["y"] = float(y)
                psf_metrics.append(result)

        # Store results
        data["psf_metrics"] = psf_metrics

        if len(psf_metrics) > 0:
            fwhm_values = [m["fwhm"] for m in psf_metrics]
            data["median_fwhm"] = float(np.median(fwhm_values))
            data["mean_fwhm"] = float(np.mean(fwhm_values))
        else:
            data["median_fwhm"] = None
            data["mean_fwhm"] = None

        return image, data

    def _gaussian_2d(self, coords, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
        """2D elliptical Gaussian function for PSF fitting.

        This is the model function used to fit the star profile. It supports
        rotation and independent X/Y widths to handle elliptical PSFs.

        Args:
            coords: Tuple of (x, y) coordinate grids
            amplitude: Peak amplitude above background
            xo, yo: Center coordinates
            sigma_x, sigma_y: Standard deviations in X and Y directions
            theta: Rotation angle in radians
            offset: Background offset level

        Returns:
            Flattened array of Gaussian values
        """
        x, y = coords
        xo = float(xo)
        yo = float(yo)

        # Rotation matrix elements
        a = (np.cos(theta) ** 2) / (2 * sigma_x**2) + (np.sin(theta) ** 2) / (2 * sigma_y**2)
        b = -(np.sin(2 * theta)) / (4 * sigma_x**2) + (np.sin(2 * theta)) / (4 * sigma_y**2)
        c = (np.sin(theta) ** 2) / (2 * sigma_x**2) + (np.cos(theta) ** 2) / (2 * sigma_y**2)

        # 2D Gaussian formula
        g = offset + amplitude * np.exp(
            -(a * ((x - xo) ** 2) + 2 * b * (x - xo) * (y - yo) + c * ((y - yo) ** 2))
        )

        return g.ravel()

    def _calculate_fwhm(self, image, x, y):
        """Calculate FWHM for a star at given position.

        Extracts a small region around the star, fits a 2D Gaussian, and
        computes FWHM and other PSF metrics.

        This method is extracted and adapted from testing/analyze_image.py
        lines 78-136.

        Args:
            image: Grayscale image array
            x, y: Star center position in pixels

        Returns:
            Dict with keys: fwhm, fwhm_x, fwhm_y, eccentricity, amplitude,
            background. Returns None if fitting fails.
        """
        try:
            # Extract region around star
            half_box = self.box_size // 2
            x_min = max(0, x - half_box)
            x_max = min(image.shape[1], x + half_box)
            y_min = max(0, y - half_box)
            y_max = min(image.shape[0], y + half_box)

            region = image[y_min:y_max, x_min:x_max].astype(float)

            if region.size == 0:
                return None

            h, w = region.shape
            y_coords, x_coords = np.mgrid[0:h, 0:w]

            # Estimate background and amplitude
            background = np.percentile(region, 10)
            amplitude = region.max() - background

            # Find approximate center using center of mass
            threshold_region = region - background
            threshold_region[threshold_region < 0] = 0
            cy, cx = center_of_mass(threshold_region)

            if np.isnan(cx) or np.isnan(cy):
                return None

            # Initial guess: (amplitude, xo, yo, sigma_x, sigma_y, theta, offset)
            initial_guess = (amplitude, cx, cy, 3.0, 3.0, 0.0, background)

            # Fit 2D Gaussian
            popt, _ = curve_fit(
                self._gaussian_2d,
                (x_coords, y_coords),
                region.ravel(),
                p0=initial_guess,
                maxfev=1000,
            )

            # Extract fitted parameters
            sigma_x = abs(popt[3])
            sigma_y = abs(popt[4])

            # Convert sigma to FWHM: FWHM = 2.355 * sigma (for Gaussian)
            fwhm_x = 2.355 * sigma_x
            fwhm_y = 2.355 * sigma_y
            fwhm_avg = (fwhm_x + fwhm_y) / 2.0

            # Calculate eccentricity (measure of elongation)
            eccentricity = abs(sigma_x - sigma_y) / max(sigma_x, sigma_y)

            return {
                "fwhm": fwhm_avg,
                "fwhm_x": fwhm_x,
                "fwhm_y": fwhm_y,
                "eccentricity": eccentricity,
                "amplitude": amplitude,
                "background": background,
            }

        except Exception as e:
            raise Exception(f"{e}: PSFMeasure._calculate_fwhm() failed")

    def save_visualization(self, image: np.ndarray, data: dict, output_path):
        """Save visualization with measurement apertures drawn around stars.

        Overrides base implementation to draw apertures around measured stars,
        color-coded by FWHM quality.
        """
        from PIL import Image, ImageDraw
        import numpy as np

        # Normalize image for display (same as base class)
        if image.dtype in [np.uint16, np.int16]:
            vis_image = (image.astype(float) / 65535.0 * 255).astype(np.uint8)
        elif image.dtype in [np.float32, np.float64]:
            img_min, img_max = image.min(), image.max()
            if img_max > img_min:
                vis_image = ((image - img_min) / (img_max - img_min) * 255).astype(np.uint8)
            else:
                vis_image = np.zeros_like(image, dtype=np.uint8)
        else:
            vis_image = image.astype(np.uint8)

        # Convert to RGB if grayscale so we can draw colored apertures
        if vis_image.ndim == 2:
            vis_image = np.stack([vis_image, vis_image, vis_image], axis=2)

        # Convert to PIL for drawing
        pil_image = Image.fromarray(vis_image)
        draw = ImageDraw.Draw(pil_image)

        # Draw apertures around measured stars
        if "psf_metrics" in data:
            psf_metrics = data["psf_metrics"]
            median_fwhm = data.get("median_fwhm", 3.0)

            for metric in psf_metrics:
                x = metric["x"]
                y = metric["y"]
                fwhm = metric["fwhm"]

                # Aperture size based on FWHM
                radius = int(fwhm * 2)

                # Color-code by FWHM quality
                # Green = good focus (near median)
                # Yellow = acceptable (within 20% of median)
                # Red = poor focus (>20% from median)
                deviation = abs(fwhm - median_fwhm) / median_fwhm
                if deviation < 0.1:
                    color = (0, 255, 0)  # Green - excellent
                elif deviation < 0.2:
                    color = (255, 255, 0)  # Yellow - acceptable
                else:
                    color = (255, 0, 0)  # Red - poor

                # Draw aperture circle
                draw.ellipse(
                    [x - radius, y - radius, x + radius, y + radius], outline=color, width=2
                )

                # Draw small crosshair at center
                crosshair_size = 3
                draw.line([x - crosshair_size, y, x + crosshair_size, y], fill=color, width=1)
                draw.line([x, y - crosshair_size, x, y + crosshair_size], fill=color, width=1)

        # Save as JPG
        pil_image.save(str(output_path.with_suffix(".jpg")), quality=95)
