import exiftool
import json
import rawpy
import numpy as np
import os
from astropy.io import fits
from astropy.wcs import WCS
import subprocess
from astropy.stats import sigma_clipped_stats
from astropy.nddata import block_reduce
from photutils.detection import DAOStarFinder
from photutils.aperture import CircularAperture
import matplotlib.pyplot as plt


class Exposure:
    def __init__(self, path: str) -> None:
        # Convert to absolute path to handle relative paths correctly
        abs_path = os.path.abspath(path)
        self.stub = os.path.basename(abs_path).split(".")[0]
        self.img_ext = os.path.basename(abs_path).split(".")[1]
        self.directory = os.path.dirname(abs_path)
        self.path = f"{self.directory}/{self.stub}"
        self.image_path = f"{self.path}.{self.img_ext}"
        self.data = dict()
        self.import_data()
        self.image: np.ndarray = None
        self.star_xy = None
        self.time = None
        self.fwhm = 15
        self.threshold_factor = 3
        self.sources = None
        self.wcs = None

    def get_image(self):
        if self.image is None:
            with rawpy.imread(f"{self.image_path}") as raw:
                self.image = raw.postprocess()
        return self.image

    def get_image_shape(self):
        if "image_shape" not in self.data:
            shape = self.get_image().shape
            self.data["image_shape"] = shape
            self.export_data()

        return self.data["image_shape"]

    def get_metadata(self) -> None:
        with exiftool.ExifToolHelper() as et:
            self.data["exif"] = et.get_metadata(self.image_path)[0]

        # Get pixel size
        res = self.data["exif"]["EXIF:FocalPlaneXResolution"]
        scale = 25400 if self.data["exif"]["EXIF:FocalPlaneResolutionUnit"] == 2 else 10000
        pixel_size = scale / res
        self.data["pixel_size"] = pixel_size

        # Get focal length
        focal_length = self.data["exif"]["MakerNotes:FocalLength"]
        self.data["focal_length"] = focal_length

        # Get pixel scale
        pixel_scale = (pixel_size / focal_length) * 206.265
        self.data["arcsec_per_pixel"] = pixel_scale

        # Get time
        time: str = self.data["exif"]["QuickTime:CreateDate"]
        time = time.replace(":", "-", 2)
        time = time.replace(' ', "T")
        self.data["time_iso"] = time
        self.time = time

    def export_data(self):
        with open(f"{self.path}.json", "w") as f:
            json.dump(self.data, f, indent=4)

    def import_data(self):
        self.get_metadata()
        self.export_data()

    def get_xyls(self, max_stars=20):
        # load image if not already
        if self.image is None:
            self.get_image()

        # sources
        self.get_sources()
        sources = self.sources
        if len(sources) > max_stars:
            sources.sort("flux")
            sources = sources[-max_stars:]

        x = sources["xcentroid"]
        y = sources["ycentroid"]

        # Create FITS table
        col1 = fits.Column(name="X", format="D", array=x)
        col2 = fits.Column(name="Y", format="D", array=y)
        hdu = fits.BinTableHDU.from_columns([col1, col2])

        # Add required headers
        hdu.header["IMAGEW"] = int(self.image.shape[1])
        hdu.header["IMAGEH"] = int(self.image.shape[0])
        hdu.writeto(f"{self.path}.xyls", overwrite=True)

    def get_wcs(self, overwrite=False, max_stars=20):
        if self.wcs is None:
            self.plate_solve(overwrite, max_stars)
        return self.wcs

    def plate_solve(self, overwrite=False, max_stars=20):
        if os.path.exists(f"{self.path}.wcs") and not overwrite:
            self.wcs = WCS(fits.getheader(f"{self.path}.wcs"))
            return self.wcs

        self.get_xyls(max_stars=max_stars)

        # perform plate solve
        subprocess.run(
            ["solve-field", f"{self.path}.xyls", "--overwrite", "--wcs", f"{self.path}.wcs"],
            capture_output=True,
            text=True,
        )

        # get wcs transform
        self.wcs = WCS(fits.getheader(f"{self.path}.wcs"))

    def get_sources(self):
        # process image
        image = self.get_image()
        if len(image.shape) == 3:
            target = image.mean(axis=2)
        mean, median, std = sigma_clipped_stats(target, sigma_lower=3.0, sigma_upper=3.0)
        target = target - median

        # reduce image for faster detection
        block_size = 4
        target_reduced = block_reduce(target, block_size=block_size, func=np.mean)

        # detect stars
        daofind = DAOStarFinder(fwhm=self.fwhm, threshold=self.threshold_factor * std)
        self.sources = daofind(target_reduced)

        # upscale points
        self.sources["xcentroid"] = self.sources["xcentroid"] * block_size
        self.sources["ycentroid"] = self.sources["ycentroid"] * block_size

    def plot_star_centroids(self):
        if self.sources is None:
            self.sources = self.get_sources()

        sources = self.sources
        image = self.get_image()

        positions = np.transpose((sources["xcentroid"], sources["ycentroid"]))
        apertures = CircularAperture(positions, r=2 * self.fwhm)
        if len(image.shape) == 3:
            plt.imshow(image.mean(axis=2), cmap="Greys")
        else:
            plt.imshow(image, cmap="Greys")

        apertures.plot(color="blue", lw=1.5, alpha=0.5)
        plt.show()
