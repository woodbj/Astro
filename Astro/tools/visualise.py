import matplotlib.pyplot as plt
from ..core import Exposure
from photutils.aperture import CircularAperture


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
    fig, ax = plt.subplots(figsize=(12, 10))

    # Display image
    image = exposure.get_image()
    ax.imshow(image, origin='lower', cmap='gray')

    # Plot sources with apertures if available
    if exposure.sources is not None:
        # Create circular apertures at source positions
        # exposure.sources should be in (X, Y) format
        apertures = CircularAperture(exposure.sources, r=aperture_radius)

        # Plot apertures
        apertures.plot(color='red', lw=1.5, alpha=0.8, ax=ax)

    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(f'Exposure: {exposure.path.name}')

    plt.tight_layout()
    plt.show()

    return fig, ax
