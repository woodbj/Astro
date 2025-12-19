#!/usr/bin/env python3
"""
Camera stream handler for gphoto2 live view.
Manages MJPEG stream capture in a background thread.
"""

import cv2
import numpy as np
import subprocess
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
