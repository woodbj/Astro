import subprocess
import os
import re
import shlex
import time
import signal
from dataclasses import dataclass, asdict
import threading
import cv2
import numpy as np
import queue
from typing import Optional


class Camera:
    def __init__(self):
        self.config = dict()
        self.stream: subprocess = None
        self.lock: threading.Lock = threading.Lock()

    def command(self, command: str) -> str:
        command = ["gphoto2"] + shlex.split(command)
        result = subprocess.run(command, capture_output=True, text=True, preexec_fn=os.setpgrp)
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
        result = self.command(f"--get-config={setting}").split("\n")

        for line in result:
            if len(line) == 0:
                continue
            line = line.split()
            if line[0] == "Current:":
                return line[1]

        return None

    def options(self, setting):
        result = self.command(f"--get-config={setting}").split("\n")
        options = []
        for line in result:
            if line.startswith("Choice:"):
                option = line.split(":")[1]
                option = option.strip()
                idx = option.find(" ")
                option = option[idx:].strip()
                options.append(option)

        return options

    def list(self, setting):
        result = self.command(f"--get-config={setting}").split("\n")
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

    def capture(self, pc=True, camera=True):
        if pc:
            command = "--capture-image-and-download"
        else:
            command = "--capture-image"

        if camera:
            command = f"{command} --keep"
        else:
            command = f"{command} --no-keep"

        result = self.command(command)
        print(command)
        print(result)
        return re.search(r"(\w+\.CR3)", result).group(1)

    def bulb_capture(self, bulb_duration, pc=True, camera=True):
        command = "--set-config shutterspeed=bulb"
        if camera:
            command += " --keep"
        command += " --set-config eosremoterelease=Immediate"
        command += f" --wait-event={bulb_duration}s"
        command += ' --set-config eosremoterelease="Release Full"'
        command += " --wait-event-and-download=2s" if pc else " --wait-event=2s"

        result = self.command(command)
        return re.search(r"(\w+\.CR3)", result).group(1)

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
            ["gphoto2", "--capture-movie", "--stdout"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**8,
        )
        time.sleep(0.5)
        stdout = stream.stdout.peek(1024)
        if b"debug" in stdout:
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


class CameraStream:
    """Handles gphoto2 camera live view stream capture."""

    MIN_JPEG_SIZE = 100  # Minimum bytes for valid JPEG header

    def __init__(self, process, max_queue_size=2, jpeg_quality=85):
        """
        Initialize camera stream handler.

        Args:
            process: The subprocess running gphoto2 capture
            max_queue_size: Maximum number of frames to queue (older frames dropped)
            jpeg_quality: JPEG encoding quality for generate() method (0-100)
        """
        self.process = process
        self.jpeg_quality = jpeg_quality
        self.frame_queue = queue.Queue(max_queue_size)
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self._running = False

        self.stream_thread = threading.Thread(target=self._read_mjpeg_stream, daemon=True)

    def start(self):
        """Start the stream processing thread."""
        with self.state_lock:
            if self._running:
                return
            self._running = True
        self.stream_thread.start()

    def stop(self):
        """Stop the stream processing thread gracefully."""
        with self.state_lock:
            self._running = False
        if self.stream_thread.is_alive():
            self.stream_thread.join(timeout=5.0)

    @property
    def running(self):
        """Thread-safe access to running state."""
        with self.state_lock:
            return self._running

    def generate(self):
        """Generator function for video streaming."""
        while self.process is not None:
            frame = self.get_frame()
            if frame is None:
                continue

            # Encode frame as JPEG
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            if not ret:
                continue

            frame_bytes = buffer.tobytes()

            # Yield frame in multipart format
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

    def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Get the next frame from the queue.

        Args:
            timeout: Maximum time to wait for a frame

        Returns:
            Frame as numpy array or None if timeout
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Get the most recent frame without blocking.

        Returns:
            Latest frame as numpy array or None if no frame available
        """
        if not self.running:
            return None
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def _read_mjpeg_stream(self):
        """Read MJPEG stream from gphoto2 in background thread."""
        bytes_data = b""

        while self.running:
            try:
                chunk = self.process.stdout.read(4096)
                if not chunk:
                    break

                bytes_data += chunk

                # Find JPEG boundaries
                a = bytes_data.find(b"\xff\xd8")  # JPEG start marker
                b = bytes_data.find(b"\xff\xd9")  # JPEG end marker

                if a != -1 and b != -1 and b > a:
                    jpg = bytes_data[a : b + 2]  # noqa: E203
                    bytes_data = bytes_data[b + 2 :]  # noqa: E203

                    # Validate JPEG has minimum size
                    if len(jpg) < self.MIN_JPEG_SIZE:
                        continue

                    # Decode JPEG frame
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

                    if frame is not None:
                        # Store latest frame
                        with self.frame_lock:
                            self.latest_frame = frame

                        # Add to queue (drop old frames if queue is full)
                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        self.frame_queue.put(frame)

            except Exception as e:
                with self.state_lock:
                    still_running = self._running
                if still_running:
                    print(f"Stream reading error ({type(e).__name__}): {e}")
                break


@dataclass
class CameraController:
    download: bool = False
    keep: bool = True
    modes: tuple[str] = tuple(("Capture", "Stream", "Schedule"))
    mode: str = "Capture"
    bulb_time: int = 30
    download_interval: int = 0
    active: bool = False

    def __post_init__(self):
        self.lock = threading.Lock()
        self.process = None

    def init(self, camera: Camera):
        self.camera_stream: CameraStream = None
        self.camera: Camera = camera
        self.stream_ps = None

    def get_config(self):
        if self.active:
            camera = self.camera.config
        else:
            camera = self.camera.get_config()

        controller = asdict(self)
        return {"camera": camera, "controller": controller}

    def live(self):
        self.stream_ps = self.camera.start_stream()
        self.camera_stream = CameraStream(self.stream_ps)
        self.camera_stream.start()

        while not self.interrupt:
            time.sleep(0.5)

        self.camera.end_stream()
        self.camera_stream.stop()
        self.camera_stream = None
        self.stream_ps = None

    def capture(self):
        self.camera.capture(pc=self.download, camera=self.keep)
        self.active = False

    def schedule(self):

        # Admin
        last_download_time = 0
        download = False

        # Loop until interrupted
        while not self.interrupt:
            # set download if triggered
            if self.download_interval is not None:
                now = time.time()
                if now - last_download_time > self.download_interval:
                    download = True
                    last_download_time = now

            # take exposure
            self.camera.bulb_capture(self.bulb_time, pc=download, camera=self.keep)

            download = False

    def run(self):
        if self.process is None:
            match self.mode:
                case "Capture":
                    function = self.capture
                case "Stream":
                    function = self.live
                case "Schedule":
                    function = self.schedule

            self.interrupt = False
            self.process: threading.Thread = threading.Thread(target=function, daemon=True)
            self.process.start()
            self.active = True
        else:
            self.interrupt = True
            self.process.join()
            self.process = None
            self.active = False

        return True
