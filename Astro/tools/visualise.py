import matplotlib.pyplot as plt
from ..core import Exposure
# from photutils.aperture import CircularAperture
import numpy as np
from pathlib import Path


def plot_exposure(exposure: Exposure, aperture_radius=10):
    """
    Plot exposure with detected sources and apertures.

    Parameters:
    -----------
    exposure : Exposure
        The exposure object to plot
    aperture_radius : float, optional
        Radius of apertures in pixels (default: 10)
    """
    if not isinstance(exposure.image, np.ndarray):
        return
    fig, ax = plt.subplots(figsize=(12, 10))

    # Display image
    if exposure.image.ndim == 2:
        plt.imshow(exposure.image, cmap='gray')
    else:
        plt.imshow(exposure.image)

    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(f'Exposure: {exposure.path}')

    plt.show()


def export_jpeg(image: np.ndarray, output_path: Path, sources=None, sigmas=None, zero_clip=False):
    """Save visualization with detected sources marked as circles.

    Overrides base implementation to draw circles around detected sources.
    """
    from PIL import Image, ImageDraw
    import numpy as np

    # clip zeros
    if zero_clip:
        image = np.clip(image, a_min=0, a_max=np.max(image))

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

    # Convert to PIL for drawing
    pil_image = Image.fromarray(vis_image)
    draw = ImageDraw.Draw(pil_image)

    # Draw circles around detected sources
    if sources is not None:
        if sigmas is None:
            sigmas = np.ones_like(sources[:, 0])

        for (x, y), sigma in zip(sources, sigmas):
            # Circle radius based on sigma (approximate star size)
            radius = int(sigma * 2)

            # Draw green circle around each source
            draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius], outline=(0, 255, 0), width=2
            )

    filepath = str(output_path.with_suffix(".jpg"))
    pil_image.save(filepath, quality=95)
    return filepath
