from ..core import ExposureLibrary, Observer, Exposure
import numpy as np
from astropy.coordinates import SkyCoord, AltAz, EarthLocation, CartesianRepresentation
from astropy.time import Time


class Drift:
    def __init__(self, source: ExposureLibrary, observer: Observer):
        self.source = source
        self.observer = observer

    def __call__(self):
        exposures = self.source.get_ordered_list("time")
        return self.drift_error(exposures)

    def plane_error(self, exposures: list[Exposure]):
        if len(exposures) < 3:
            return None, None
        altaz = self.alt_az(exposures)
        samples = np.array([o.cartesian.xyz.value for o in altaz])
        A = np.ones((len(altaz), 4))
        A[:, :3] = samples
        U, S, Vh = np.linalg.svd(A)
        x = Vh[-1][:3]
        location = EarthLocation(lat=self.observer.latitude, lon=self.observer.longitude)
        alignment = AltAz(CartesianRepresentation(x), location=location)
        alt_err = alignment.alt.value - abs(self.observer.latitude)
        az_diff = alignment.az.value - 180
        az_err = (az_diff + 180) % 360 - 180
        # if not len(residuals > 0):
        #     residuals = None
        # else:
        #     residuals = residuals[0]
        return alt_err, az_err

    def drift_error(self, exposures: list[Exposure]):
        ra = []
        dec = []
        dra = []
        ddec = []
        h = []
        alt = []
        for i in range(1, len(exposures)):
            ra.append((exposures[i].ra + exposures[i - 1].ra) / 2)
            dec.append((exposures[i].dec + exposures[i - 1].dec) / 2)
            dra.append((exposures[i].ra - exposures[i - 1].ra))
            ddec.append((exposures[i].dec - exposures[i - 1].dec))
            dt = Time(exposures[i].time) - Time(exposures[i - 1].time)
            time = Time(exposures[i - 1].time) + dt
            h.append(time.sidereal_time("mean", self.observer.longitude).rad)
            loc = EarthLocation(lat=self.observer.latitude, lon=self.observer.longitude)
            radec = SkyCoord(ra=ra[-1], dec=[-1], unit="deg", frame="icrs")
            altaz = radec.transform_to(AltAz(location=loc, obstime=time))
            alt.append(altaz.alt.rad.item())

        ra = np.array(np.deg2rad(ra))
        dec = np.array(np.deg2rad(dec))
        dra = np.array(np.deg2rad(dra))
        ddec = np.array(np.deg2rad(ddec))
        alt = np.array(np.deg2rad(alt))
        h = np.array(h)

        cos_dec = np.cos(dec)
        cos_alt = np.cos(alt)
        cos_h = np.cos(h)
        sin_h = np.sin(h)

        alt_err = ddec * cos_h - dra * cos_dec
        az_err = (dra * cos_dec * cos_h + ddec * sin_h) / cos_alt

        alt_err = np.rad2deg(alt_err)
        az_err = np.rad2deg(az_err)

        return alt_err, az_err

    def alt_az(self, exposures: list[Exposure]):
        # if only a single exposure is passed, make it a list
        if isinstance(exposures, Exposure):
            exposures = list(exposures)

        altazs: list[AltAz] = []
        lat = self.observer.latitude
        lon = self.observer.longitude
        location = EarthLocation(lat=lat, lon=lon)
        for e in exposures:
            radec = SkyCoord(ra=e.ra, dec=e.dec, unit="deg", frame="icrs")
            altaz = radec.transform_to(AltAz(location=location, obstime=e.time))
            altazs.append(altaz)
            e.alt = altaz.alt.value
            e.az = altaz.az.value

        return altazs
