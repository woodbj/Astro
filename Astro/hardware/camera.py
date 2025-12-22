import subprocess
import os
import re
import shlex
import time
import signal


class Camera:
    def __init__(self):
        self.config = dict()
        self.stream = None

    def command(self, command: str) -> str:
        command = ["gphoto2"] + shlex.split(command)
        result = subprocess.run(command,
                                capture_output=True,
                                text=True,
                                preexec_fn=os.setpgrp)
        if result.returncode == 0:
            return result.stdout
        else:
            raise Exception("Could not connect to camera")

    def is_on(self):
        try:
            self.command("--summary")
            return True
        except Exception:
            return False

    def set(self, setting, value):
        result = self.command(f"--set-config {setting}={value}")
        if setting == "shutterspeed":  # update bulb mode
            self.bulb_mode = value == "bulb"
        return result

    def get(self, setting):
        result = self.command(f"--get-config={setting}").split('\n')

        for line in result:
            if len(line) == 0:
                continue
            line = line.split()
            if line[0] == "Current:":
                return line[1]

        return None

    def list(self, setting):
        result = self.command(f"--get-config={setting}").split('\n')
        for line in result:
            line = line.split(" ")
            if line[0] == "Choice:":
                print(f"{int(line[1])}:\t{' '.join(line[2:])}")
            elif line[0] == "Current:":
                print(f"{' '.join(line)}")

    def sync_time(self):
        self.command("--set-config datetimeutc=now")

    def get_config(self):
        result = self.command("--list-all-config")
        entries = result.split("END")
        config = dict()
        for entry in entries:
            lines = entry.split("\n")
            title = ""
            current = ""
            choices = []
            for line in lines:
                if len(line) == 0:
                    continue

                if line.startswith("/"):
                    title = line.split("/")[-1]

                else:
                    line = line.split(":")
                    if line[0] == "Current":
                        current = line[1].strip()
                    elif line[0] == "Choice":
                        choice = line[1].strip()
                        i = choice.find(" ")
                        choice = choice[i:].split()
                        choice = " ".join(choice)
                        choices.append(choice)
            if title == "":
                continue

            config[title] = {"Current": current, "Choices": choices}
        self.config = config

        return self.config

    def capture(self, download=True):
        # if self.bulb_mode and isinstance(self.bulb_time, int):
        #     command = "--set-config shutterspeed=bulb"
        #     command += " --keep"
        #     command += " --set-config eosremoterelease=Immediate"
        #     command += f" --wait-event={self.bulb_time}s"
        #     command += " --set-config eosremoterelease=\"Release Full\""
        #     command += " --wait-event-and-download=2s" if self.download else " --wait-event=2s"
        # else:
        if download:
            command = "--capture-image-and-download --keep"
        else:
            command = "--capture-image --keep"

        result = self.command(command)
        return re.search(r'(\w+\.CR3)', result).group(1)

    def download_latest(self):
        # Get list of files
        result = subprocess.run(["gphoto2", "--list-files"], capture_output=True, text=True)

        # Parse the output to find the last file number
        lines = result.stdout.strip().split("\n")
        last_file = None
        for line in lines:
            if line.startswith("#"):
                last_file = line

        # Download the latest image
        success = False
        if last_file:
            file = last_file.split()[0].replace("#", "")
            result = subprocess.run(
                ["gphoto2", "--get-file", file], input="n\nn\n", capture_output=True, text=True
            )
            success = result.stdout.strip().split()[0] == "Saving"

        # Success is false if it already exists on the pc
        return success

    def start_stream(self):
        # Check if stream exists and is still running
        if self.stream is not None:
            return self.stream

        # Start new stream process
        stream = subprocess.Popen(
                ['gphoto2', '--capture-movie', '--stdout'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
        time.sleep(0.5)
        stdout = stream.stdout.peek(1024)
        if b'debug' in stdout:
            stream.kill()
            self.stream = None
            raise Exception("Turn on camera")
        self.stream = stream
        return self.stream

    def end_stream(self):
        if self.stream is None:
            return True

        # Send SIGINT for graceful shutdown
        self.stream.send_signal(signal.SIGINT)

        try:
            # Wait up to 2 seconds for graceful exit
            self.stream.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # If still running after timeout, force kill
            self.stream.kill()
            self.stream.wait()

        self.stream = None

        # Give camera a moment to reset
        time.sleep(0.5)

        try:
            self.command("--set-config eosremoterelease=4")
            return True
        except Exception as e:
            print(f"Warning: Could not reset camera release mode: {e}")
            return False


class CameraSchedule:
    def __init__(self, camera: Camera):
        self.camera: Camera = camera
        self.interrupt = False
        camera.schedule = self

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
