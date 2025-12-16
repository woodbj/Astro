import subprocess
import os
import re
import shlex


class Camera:
    def __init__(self):
        self.bulb_time = 30
        self.bulb_mode = self.get("shutterspeed") == "bulb"
        self.download = True

    def command(self, command: str) -> str:
        command = ["gphoto2"] + shlex.split(command)
        result = subprocess.run(command,
                                capture_output=True,
                                text=True,
                                preexec_fn=os.setpgrp)
        return result.stdout

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

    def set_bulb(self, duration):
        self.set("shutterspeed", "bulb")
        self.bulb_time = duration
        self.bulb_mode = True

    def list_config_options(self):
        result = self.command("--list-config")
        heading = None
        for line in result.split('\n'):
            if len(line) == 0:
                continue

            line = line.split('/')
            if line[2] != heading:
                heading = line[2]
                print(heading)
            print('-', line[3])

    def capture(self):
        if self.bulb_mode and isinstance(self.bulb_time, int):
            command = "--set-config shutterspeed=bulb"
            command += " --keep"
            command += " --set-config eosremoterelease=Immediate"
            command += f" --wait-event={self.bulb_time}s"
            command += " --set-config eosremoterelease=\"Release Full\""
            command += " --wait-event-and-download=2s" if self.download else " --wait-event=2s"
        else:
            if self.download:
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
