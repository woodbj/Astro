import subprocess
import os
import re
import shlex
import cv2
import numpy as np
import threading
import queue
from typing import Optional, Callable


class CameraStream:
    """Handles gphoto2 camera live view stream capture."""

    def __init__(self, max_queue_size: int = 2):
        """
        Initialize camera stream handler.

        Args:
            max_queue_size: Maximum number of frames to queue (older frames dropped)
        """
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.running = False
        self.process = None
        self.stream_thread = None
        self.frame_callbacks = []
        self.latest_frame = None
        self.frame_lock = threading.Lock()

    def add_frame_callback(self, callback: Callable):
        """
        Add a callback function to be called when new frame arrives.

        Args:
            callback: Function that takes a frame (numpy array) as argument
        """
        self.frame_callbacks.append(callback)

    def start(self) -> bool:
        """
        Start the camera stream.

        Returns:
            True if started successfully, False otherwise
        """
        if self.running:
            print("Stream already running")
            return True

        print("Starting camera stream...")

        # Start gphoto2 process
        try:
            self.process = subprocess.Popen(
                ['gphoto2', '--capture-movie', '--stdout'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=10**8
            )
        except FileNotFoundError:
            print("Error: gphoto2 not found. Please install gphoto2.")
            return False
        except Exception as e:
            print(f"Error starting gphoto2: {e}")
            return False

        # Start stream reading thread
        self.running = True
        self.stream_thread = threading.Thread(target=self._read_mjpeg_stream, daemon=True)
        self.stream_thread.start()

        print("Camera stream started")
        return True

    def stop(self):
        """Stop the camera stream and clean up resources."""
        if not self.running:
            return

        print("Stopping camera stream...")
        self.running = False

        # Wait for thread to finish
        if self.stream_thread:
            self.stream_thread.join(timeout=2)

        # Terminate gphoto2 process
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
                print("gphoto2 process terminated successfully")
            except subprocess.TimeoutExpired:
                print("gphoto2 not responding, force killing...")
                self.process.kill()
                self.process.wait()
                print("gphoto2 process killed")

        # Release camera
        try:
            subprocess.run(
                ['gphoto2', '--set-config', 'eosremoterelease=Release Full'],
                timeout=5,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL
            )
            print("Camera released")
        except:
            pass

        print("Camera stream stopped")

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
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def _read_mjpeg_stream(self):
        """Read MJPEG stream from gphoto2 in background thread."""
        bytes_data = b''

        while self.running:
            try:
                chunk = self.process.stdout.read(4096)
                if not chunk:
                    break

                bytes_data += chunk

                # Find JPEG boundaries
                a = bytes_data.find(b'\xff\xd8')  # JPEG start marker
                b = bytes_data.find(b'\xff\xd9')  # JPEG end marker

                if a != -1 and b != -1:
                    jpg = bytes_data[a:b+2]
                    bytes_data = bytes_data[b+2:]

                    # Decode JPEG frame
                    frame = cv2.imdecode(
                        np.frombuffer(jpg, dtype=np.uint8),
                        cv2.IMREAD_COLOR
                    )

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

                        # Call registered callbacks
                        for callback in self.frame_callbacks:
                            try:
                                callback(frame.copy())
                            except Exception as e:
                                print(f"Frame callback error: {e}")

            except Exception as e:
                if self.running:  # Only print if we're supposed to be running
                    print(f"Stream reading error: {e}")
                break

    def is_running(self) -> bool:
        """Check if stream is currently running."""
        return self.running

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


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
