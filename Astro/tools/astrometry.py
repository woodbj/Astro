import subprocess
from ..core.exposure import Exposure
from astropy.io import fits
from astropy.wcs import WCS


class PlateSolver:
    def load_wcs(self, exposure: Exposure) -> WCS:
        try:
            wcs = WCS(fits.getheader(exposure.path.with_suffix(".wcs")))
            return wcs
        except Exception:
            return None

    def __call__(self, exposure: Exposure, ra=None, dec=None, flags=None):
        # perform plate solve
        command = ["solve-field", f"{exposure.path.with_suffix(".xyls")}", "--overwrite"]
        command += ["--wcs", f"{exposure.path.with_suffix(".wcs")}"]
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

        wcs = exposure.get_wcs()
        return wcs
