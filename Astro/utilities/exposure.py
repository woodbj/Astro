import exiftool
import json
import rawpy
import numpy as np
import os
from astropy.io import fits
from astropy.wcs import WCS
import subprocess
from photutils.aperture import CircularAperture
import matplotlib.pyplot as plt
from skimage.feature import blob_doh
from astropy.time import Time
from datetime import datetime
from astropy.coordinates import SkyCoord
import cv2


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
        self.image: np.ndarray = None
        self.star_xy = None
        self.wcs = None
        self.fwhm = None
        self.ra = None
        self.dec = None
        self.radius = None
        self.import_data()

        time = self.data["time_iso"]
        time = datetime.fromisoformat(time)
        self.time = Time(time)

    def load_image(self):
        with rawpy.imread(f"{self.image_path}") as raw:
            self.image = raw.postprocess()
        return self.image

    def get_bytes(self):
        if self.image is None:
            self.load_image()

        ret, buffer = cv2.imencode(".jpg", self.image)
        frame_bytes = buffer.tobytes()
        return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"

    def load_image_shape(self):
        if "image_shape" not in self.data:
            shape = self.load_image().shape
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

        # Get time
        time: str = self.data["exif"]["QuickTime:CreateDate"]
        time = time.replace(":", "-", 2)
        time = time.replace(" ", "T")
        self.data["time_iso"] = time
        self.time = time

    def export_data(self):
        with open(f"{self.path}.json", "w") as f:
            json.dump(self.data, f, indent=4)

    def import_data(self):
        self.get_metadata()
        self.export_data()

    def make_xyls(self):
        # Create FITS table
        col1 = fits.Column(name="X", format="D", array=self.sources[:, 0])
        col2 = fits.Column(name="Y", format="D", array=self.sources[:, 1])
        col3 = fits.Column(name="FWHM", format="E", array=self.fwhm)
        hdu = fits.BinTableHDU.from_columns([col1, col2, col3])

        # Add required headers
        hdu.header["IMAGEW"] = int(self.image.shape[1])
        hdu.header["IMAGEH"] = int(self.image.shape[0])
        hdu.writeto(f"{self.path}.xyls", overwrite=True)

    def radec_radius(self):
        height, width = self.image.shape[:2]
        centre = tuple(
            x.item() for x in self.wcs.pixel_to_world_values(width // 2 - 1, height // 2 - 1)
        )
        corner = tuple(x.item() for x in self.wcs.pixel_to_world_values(0, 0))

        centre_sc = SkyCoord(*centre, unit="deg")
        corner_sc = SkyCoord(*corner, unit="deg")
        radius = 2 * centre_sc.separation(corner_sc).degree
        self.ra = centre[0]
        self.dec = centre[1]
        self.radius = radius

        return (centre[0], centre[1], radius)

    def radec(self):
        height, width = self.image.shape[:2]
        return self.wcs.pixel_to_world(width // 2 - 1, height // 2 - 1)

    def load_all(self):
        self.load_image()
        self.load_xyls()
        self.load_wcs()

    def load_wcs(self):
        try:
            self.wcs = WCS(fits.getheader(f"{self.path}.wcs"))
        except Exception:
            return None
        return None

    def load_xyls(self):
        try:
            xyls = fits.getdata(f"{self.path}.xyls")
            self.sources = np.array((xyls["X"], xyls["Y"])).T
            self.fwhm = np.array((xyls["FWHM"])).T
        except Exception:
            return None
        return None

    def plate_solve(self, ra=None, dec=None, radius=None):
        # perform plate solve
        command = ["solve-field", f"{self.path}.xyls", "--overwrite", "--wcs", f"{self.path}.wcs"]
        if ra is not None:
            command += ["--ra", f"{ra:.6f}"]
        if dec is not None:
            command += ["--dec", f"{dec:.6f}"]
        if radius is not None:
            command += ["--radius", f"{radius:.2f}"]
        command += ["--no-plots"]
        command += ["--no-remove-lines"]
        command += ["--corr", "none"]
        command += ["--match", "none"]
        command += ["--rdls", "none"]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(result.stdout)
            print(" ".join(command))
            return None

        self.load_wcs()
        self.radec_radius()
        return self.wcs

    def blobs(self, **kwargs):
        # pull target image
        target_channel = kwargs.get("target_channel", "green")
        match target_channel:
            case "red":
                target = self.image[:, :, 0]
            case "green":
                target = self.image[:, :, 1]
            case "blue":
                target = self.image[:, :, 2]
            case "mean":
                target = self.image.mean(axis=2)

        kwargs.setdefault("min_sigma", 10)

        blobs = blob_doh(target, **kwargs)
        self.fwhm = blobs[:, 2]
        self.sources = blobs[:, [1, 0]]
        self.make_xyls()
        return blobs

    def plot_star_centroids(self, **kwargs):
        if self.sources is None:
            print("No sources")
            return

        positions = self.sources

        apertures = [CircularAperture([pos], r=fwhm) for pos, fwhm in zip(positions, self.fwhm)]

        plt.title(f"Sources: {len(self.sources)}")
        plt.imshow(self.image)
        for aperture in apertures:
            aperture.plot(color="red", lw=1.5, alpha=0.5)
        plt.show()
