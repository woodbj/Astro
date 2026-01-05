from astropy.io import fits
from astropy.wcs import WCS
import subprocess
from .base import Processor
from ..core import Exposure
from pydantic import Field


class PlateSolve(Processor):
    ra: float | None = Field(default=None)
    dec: float | None = Field(default=None)

    def load_wcs(self, exposure: Exposure) -> WCS:
        try:
            wcs = WCS(fits.getheader(exposure.path.with_suffix(".wcs")))
            return wcs
        except Exception:
            raise Exception("Could not load .wcs file")

    def make_xyls(self, exposure: Exposure):
        # Create FITS table with sources stored as (X, Y)
        stars = exposure.stars
        if stars is None:
            raise Exception("Exposure has no stars with which to make .xyls file")
        x = [s.x for s in stars]
        y = [s.y for s in stars]
        col1 = fits.Column(name="X", format="D", array=x)
        col2 = fits.Column(name="Y", format="D", array=y)
        hdu = fits.BinTableHDU.from_columns([col1, col2])

        # Add required headers
        if exposure.width is None or exposure.height is None:
            raise Exception("Exposure width or height not specified")
        hdu.header["IMAGEW"] = int(exposure.width)
        hdu.header["IMAGEH"] = int(exposure.height)
        hdu.writeto(f"{exposure.path.with_suffix(".xyls")}", overwrite=True)

    def update_exposure(self, exposure: Exposure):
        hdul = fits.open(exposure.path.with_suffix(".wcs"))
        exposure.ra = hdul[0].header["CRVAL1"]
        exposure.dec = hdul[0].header["CRVAL2"]
        self.ra = exposure.ra
        self.dec = exposure.dec
        pass

    def solve_field(self, exposure: Exposure, ra=None, dec=None, flags=None):
        command = ["solve-field", f"{exposure.path.with_suffix(".xyls")}"]
        command += ["--wcs", f"{exposure.path.with_suffix(".wcs")}"]
        command += ["--overwrite"]
        command += ["--crpix-center"]

        if ra is not None:
            command += ["--ra", f"{ra:.6f}"]
            command += ["--radius", "10"]
        if dec is not None:
            command += ["--dec", f"{dec:.6f}"]

        if flags is not None:
            command += flags

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            print("Command:", " ".join(command))
            return None

    def __call__(self, exposure: Exposure):
        # perform plate solve
        self.make_xyls(exposure)
        self.solve_field(exposure, ra=self.ra, dec=self.dec)
        self.update_exposure(exposure)

        return exposure
