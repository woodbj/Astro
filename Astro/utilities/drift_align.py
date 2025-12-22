from astropy.coordinates import AltAz, EarthLocation
import astropy.units as u
from .exposure import Exposure


class DriftAlign:
    def __init__(self, lat, lon):
        self.lat = lat * u.deg
        self.lon = lon * u.deg
        pass

    def get_error(self, image1: Exposure, image2: Exposure):
        # Good drift alignment: ≤ 30 arcsec/min.
        # Excellent alignment: ≤ 10–15 arcsec/min.

        # -----------------------------
        # 1. Observer location
        # -----------------------------

        location = EarthLocation(lat=self.lat, lon=self.lon)

        # -----------------------------
        # 2. Load exposure coordinates
        # -----------------------------

        # RA/Dec of image centers
        radec1 = image1.radec()  # RA/Dec of 1st image centre
        radec2 = image2.radec()  # RA/Dec of 2nd image centre

        # -----------------------------
        # 3. Convert to Alt/Az
        # -----------------------------
        # Get times
        dt = (image2.time - image1.time).to(u.min)

        # Get reference frames for the two times
        frame1 = AltAz(obstime=image1.time, location=location)
        frame2 = AltAz(obstime=image2.time, location=location)

        # Convert RA/Dec coordinates to Alt/Az
        altaz1 = radec1.transform_to(frame1)  # exposure 1 actual Alt/Az
        altaz2_exp = radec1.transform_to(frame2)  # exposure 2 Alt/Az if perfectly aligned
        altaz2_act = radec2.transform_to(frame2)  # exposure 2 actual Alt/Az

        # -----------------------------
        # 4. Compute drift (observed)
        # -----------------------------
        # Ideal change in Alt/Az
        delta_alt_exp = (altaz2_exp.alt - altaz1.alt).wrap_at(180 * u.deg)
        delta_az_exp = (altaz2_exp.az - altaz1.az).wrap_at(180 * u.deg)

        # Actual change in Alt/Az
        delta_alt_act = (altaz2_act.alt - altaz1.alt).wrap_at(180 * u.deg)
        delta_az_act = (altaz2_act.az - altaz1.az).wrap_at(180 * u.deg)

        # Alt/Az drift
        drift_alt = (delta_alt_exp - delta_alt_act).to(u.arcsec) / dt
        drift_az = (delta_az_exp - delta_az_act).to(u.arcsec) / dt

        return drift_alt, drift_az
