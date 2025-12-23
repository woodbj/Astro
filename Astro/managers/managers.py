from dataclasses import dataclass, asdict
from ..services.capture import CameraStream
import threading
import time
import json
import os


class DataManager:
    def get(self, attribute):
        try:
            method = getattr(self, f"get_{attribute}")
            return method()
        except Exception:
            return self.__getattribute__(attribute)

    def set(self, attribute, value):
        try:
            method = getattr(self, f"set_{attribute}")
            current_value = self.get(attribute)
            if current_value is not None:
                value = type(current_value)(value)
            self.dump()
            return method(value)
        except AttributeError:
            current_value = self.__getattribute__(attribute)
            if current_value is not None:
                value = type(current_value)(value)
            self.dump()
            return self.__setattr__(attribute, value)
        except Exception:
            return None

    def dump(self):
        try:
            export = dict()
            data = asdict(self)
            for id in data:
                if data[id] is None:
                    continue
                export[id] = data[id]

            with open(f"{type(self).__name__}.json", "w") as f:
                json.dump(export, f)
        except Exception:
            # Silently fail during interpreter shutdown when builtins are unavailable
            pass

    def load(self):
        try:
            with open(f"{type(self).__name__}.json", "r") as f:
                data = json.load(f)

            for id in data:
                self.set(id, data[id])
        except Exception:
            raise Exception("Couldn't load dump")

    def options(self, attribute):
        try:
            method = getattr(self, f"options_{attribute}")
            return method()
        except AttributeError:
            return None
        except Exception:
            return None

    def dictionary(self):
        state = asdict(self)
        out = dict()
        for attribute in state:
            value = self.get(attribute)
            value_type = type(value).__name__
            options = self.options(attribute)
            out[attribute] = {"value": value, "type": value_type, "options": options}
        return out

    def print(self):
        state = self.dictionary()
        for attribute in state:
            print(attribute, state[attribute])

    def __del__(self):
        self.dump()


@dataclass
class CameraManager(DataManager):
    iso: str = None
    shutter: str = None
    aperture: str = None
    bulb_duration: int = 30
    download_interval: int = 0
    download_camera: bool = True
    download_pc: bool = True

    def __init__(self, stream: CameraStream):
        self.stream: CameraStream = stream
        self.camera = stream.camera
        self.live_running: bool = False
        self.schedule_running: bool = False
        self.schedule_thread: threading.Thread = None
        self.interrupt_thread: bool = False
        self.load()

    def get_iso(self):
        self.iso = self.camera.get("iso")
        return self.iso

    def set_iso(self, value):
        return self.camera.set("iso", value)

    def options_iso(self):
        return self.camera.options("iso")

    def get_shutter(self):
        self.shutter = self.camera.get("shutterspeed")
        return self.shutter

    def set_shutter(self, value):
        return self.camera.set("shutterspeed", value)

    def options_shutter(self):
        return self.camera.options("shutterspeed")

    def get_aperture(self):
        self.aperture = self.camera.get("aperture")
        return self.aperture

    def set_aperture(self, value):
        return self.camera.set("aperture", value)

    def options_aperture(self):
        return self.camera.options("aperture")

    def checks(self):
        if self.live_running is True:
            raise Exception("Live stream already running")

        if self.schedule_running is True:
            raise Exception("Stop schedule first")

        return True

    def capture(self):
        self.checks()
        return self.camera.capture()

    def start_live(self):
        self.checks()
        self.live_running = True
        return self.stream.start()

    def stop_live(self):
        if self.live_running is True:
            self.live_running = False
            return self.stream.stop()

        else:
            raise Exception("Live stream not running")

    def start_schedule(self):
        if not self.schedule_running:
            try:
                self.schedule_thread = threading.Thread(target=self.run_schedule, daemon=True)
                self.schedule_thread.start()
                self.schedule_running = True
            except Exception:
                raise Exception("Could not start schedule thread")

    def stop_schedule(self):
        if self.schedule_running:
            self.interrupt_thread = True
            self.schedule_thread.join()
            self.schedule_running = False
        else:
            raise Exception("Can't stop schedule that isn't already running")

    def run_schedule(self):
        # Setup camera
        self.set("shutter", "bulb")
        print(self.get_shutter(), self.bulb_duration)

        # Admin
        last_download_time = 0
        self.interrupt_thread = False
        download = False

        # Loop until interrupted
        while not self.interrupt_thread:
            # set download if triggered
            if self.download_interval is not None:
                now = time.time()
                if now - last_download_time > self.download_interval:
                    download = True
                    last_download_time = now

            # take exposure
            self.camera.bulb_capture(self.bulb_duration, pc=download)

            # remove download
            download = False


@dataclass
class SessionManager(DataManager):
    cwd: str = os.getcwd()
    lat: float = None
    lon: float = None
    ra: float = None
    dec: float = None

    def __init__(self):
        self.load()

    def set_cwd(self, path: str):
        path = os.path.abspath(path)
        print("settinng cwd to:", path)
        if os.path.isdir(path):
            self.cwd = path
            os.chdir(self.cwd)
            print(f"cwd: {self.cwd}")
        else:
            raise Exception("Invalid CWD")
