from ..hardware.camera import Camera
import time
import signal


class Capture:
    def __init__(self, camera: Camera):
        self.camera: Camera = camera
        self.interrupt = False

    def end(self, *args):
        self.interrupt = True
        print(" Exiting after exposure complete ", end="", flush=True)

    def run(self, exposure_duration, download_period_s=None):
        count = 1
        self.camera.set_bulb(exposure_duration)

        last_download_time = 0
        self.interrupt = False
        signal.signal(signal.SIGINT, self.end)
        while not self.interrupt:
            # print current time
            print(f"{time.asctime()} > ", end="", flush=True)

            # set download if triggered
            if download_period_s is not None:
                now = time.time()
                if now - last_download_time > download_period_s:
                    self.camera.download = True
                    last_download_time = now

            # take exposure
            print(f"Exposure {count}...", end="", flush=True)
            name = self.camera.capture()
            print(f"Complete! {name}{' Downloaded' if self.camera.download else ''}")

            # remove download
            self.camera.download = False

            count += 1
        signal.signal(signal.SIGINT, signal.SIG_IGN)
