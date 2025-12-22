import cv2
import numpy as np
from scipy.optimize import curve_fit
from scipy.ndimage import center_of_mass
from typing import Optional, Tuple


def gaussian_2d(coords, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
    """
    2D Gaussian function for fitting star profiles.

    Args:
        coords: Tuple of (x, y) coordinate arrays
        amplitude: Peak amplitude of the Gaussian
        xo: X-coordinate of the center
        yo: Y-coordinate of the center
        sigma_x: Standard deviation in x direction
        sigma_y: Standard deviation in y direction
        theta: Rotation angle
        offset: Background offset

    Returns:
        Flattened array of Gaussian values
    """
    x, y = coords
    xo = float(xo)
    yo = float(yo)
    a = (np.cos(theta) ** 2) / (2 * sigma_x**2) + (np.sin(theta) ** 2) / (2 * sigma_y**2)
    b = -(np.sin(2 * theta)) / (4 * sigma_x**2) + (np.sin(2 * theta)) / (4 * sigma_y**2)
    c = (np.sin(theta) ** 2) / (2 * sigma_x**2) + (np.cos(theta) ** 2) / (2 * sigma_y**2)
    g = offset + amplitude * np.exp(
        -(a * ((x - xo) ** 2) + 2 * b * (x - xo) * (y - yo) + c * ((y - yo) ** 2))
    )
    return g.ravel()


def calculate_fwhm(frame: np.ndarray, x: int, y: int, box_size: int = 40) -> Optional[float]:
    """
    Calculate FWHM of a star at position (x, y) using 2D Gaussian fitting.

    Args:
        frame: Input image (grayscale or color)
        x: X-coordinate of the star center
        y: Y-coordinate of the star center
        box_size: Size of the box around the star for fitting

    Returns:
        Average FWHM value in pixels, or None if calculation fails
    """
    try:
        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Extract region around star
        half_box = box_size // 2
        x_min = max(0, x - half_box)
        x_max = min(frame.shape[1], x + half_box)
        y_min = max(0, y - half_box)
        y_max = min(frame.shape[0], y + half_box)

        region = frame[y_min:y_max, x_min:x_max].astype(float)

        if region.size == 0:
            return None

        # Create coordinate arrays
        h, w = region.shape
        y_coords, x_coords = np.mgrid[0:h, 0:w]

        # Initial guess for Gaussian parameters
        background = np.percentile(region, 10)
        amplitude = region.max() - background

        # Find approximate center using center of mass
        threshold_region = region - background
        threshold_region[threshold_region < 0] = 0
        cy, cx = center_of_mass(threshold_region)

        if np.isnan(cx) or np.isnan(cy):
            return None

        initial_guess = (
            amplitude,  # amplitude
            cx,  # x center
            cy,  # y center
            3.0,  # sigma_x
            3.0,  # sigma_y
            0.0,  # theta (rotation)
            background,  # offset
        )

        # Fit 2D Gaussian
        popt, _ = curve_fit(
            gaussian_2d, (x_coords, y_coords), region.ravel(), p0=initial_guess, maxfev=1000
        )

        # Extract sigma values and calculate FWHM
        sigma_x = abs(popt[3])
        sigma_y = abs(popt[4])

        # FWHM = 2.355 * sigma (for Gaussian)
        fwhm_x = 2.355 * sigma_x
        fwhm_y = 2.355 * sigma_y
        fwhm_avg = (fwhm_x + fwhm_y) / 2.0

        return fwhm_avg

    except Exception as e:
        # Silently return None on error - caller can decide how to handle
        return None


def draw_star_overlay(
    frame: np.ndarray,
    x: int,
    y: int,
    fwhm: Optional[float] = None,
    box_size: int = 40,
    color: Tuple[int, int, int] = (0, 0, 255),
) -> np.ndarray:
    """
    Draw overlay markers on a frame showing the selected star and FWHM measurement.

    Args:
        frame: Input image
        x: X-coordinate of the star center
        y: Y-coordinate of the star center
        fwhm: FWHM value to display (optional)
        box_size: Size of the measurement box
        color: BGR color for the overlay

    Returns:
        Frame with overlay drawn
    """
    display_frame = frame.copy()
    half_box = box_size // 2

    # Draw box around star
    cv2.rectangle(
        display_frame, (x - half_box, y - half_box), (x + half_box, y + half_box), color, 2
    )

    # Draw crosshair
    cv2.line(display_frame, (x - 10, y), (x + 10, y), color, 1)
    cv2.line(display_frame, (x, y - 10), (x, y + 10), color, 1)

    # Draw FWHM value if provided
    if fwhm is not None:
        text = f"FWHM: {fwhm:.2f} px"
        cv2.putText(display_frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    return display_frame


def get_star_region(
    frame: np.ndarray, x: int, y: int, region_size: int = 80, scale_factor: int = 4
) -> Optional[np.ndarray]:
    """
    Extract and scale up a region around a star for detailed viewing.

    Args:
        frame: Input image
        x: X-coordinate of the star center
        y: Y-coordinate of the star center
        region_size: Size of the region to extract
        scale_factor: Factor to scale up the region

    Returns:
        Scaled region image, or None if extraction fails
    """
    half_size = region_size // 2

    # Extract region
    x_min = max(0, x - half_size)
    x_max = min(frame.shape[1], x + half_size)
    y_min = max(0, y - half_size)
    y_max = min(frame.shape[0], y + half_size)

    region = frame[y_min:y_max, x_min:x_max].copy()

    if region.size == 0:
        return None

    # Scale up for better visibility
    zoomed = cv2.resize(
        region, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_NEAREST
    )

    return zoomed


class FWHMTracker:
    """
    Track FWHM measurements over time and compute statistics.
    """

    def __init__(self, max_history: int = 50):
        """
        Initialize FWHM tracker.

        Args:
            max_history: Maximum number of measurements to keep in history
        """
        self.max_history = max_history
        self.history = []

    def add_measurement(self, fwhm: float):
        """Add a new FWHM measurement to the history."""
        if fwhm is not None:
            self.history.append(fwhm)
            if len(self.history) > self.max_history:
                self.history.pop(0)

    def get_history(self) -> list:
        """Get the full measurement history."""
        return self.history.copy()

    def get_current(self) -> Optional[float]:
        """Get the most recent measurement."""
        return self.history[-1] if self.history else None

    def get_best(self) -> Optional[float]:
        """Get the best (minimum) FWHM value."""
        return min(self.history) if self.history else None

    def get_worst(self) -> Optional[float]:
        """Get the worst (maximum) FWHM value."""
        return max(self.history) if self.history else None

    def get_mean(self) -> Optional[float]:
        """Get the mean FWHM value."""
        return np.mean(self.history) if self.history else None

    def get_std(self) -> Optional[float]:
        """Get the standard deviation of FWHM values."""
        return np.std(self.history) if self.history else None

    def get_count(self) -> int:
        """Get the number of measurements."""
        return len(self.history)

    def reset(self):
        """Clear all measurements."""
        self.history = []

    def get_statistics(self) -> dict:
        """
        Get comprehensive statistics about the measurements.

        Returns:
            Dictionary with current, best, worst, mean, std, and count
        """
        return {
            "current": self.get_current(),
            "best": self.get_best(),
            "worst": self.get_worst(),
            "mean": self.get_mean(),
            "std": self.get_std(),
            "count": self.get_count(),
        }
