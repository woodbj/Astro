from ..hardware.camera import Camera
import time
import signal


class Capture:
    def __init__(self, camera: Camera):
        self.camera: Camera = camera
        self.interrupt = False

    def end(self, *args):
        self.interrupt = True

    def run(self, exposure_duration, download_period_s=None):
        # Setup camera
        self.camera.set_bulb(exposure_duration)

        # Admin
        last_download_time = 0
        self.interrupt = False
        signal.signal(signal.SIGINT, self.end)

        # Loop until interrupted
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
            self.camera.capture()

            # remove download
            self.camera.download = False
        
        # Remove interrupt handler
        signal.signal(signal.SIGINT, signal.SIG_IGN)
