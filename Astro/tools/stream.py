from ..hardware.camera import Camera
import cv2
import numpy as np
import threading
import queue
from typing import Optional
from abc import ABC, abstractmethod


# class Stream(ABC):
#     @abstractmethod
#     def __init__(self):
#         super().__init__()
#         self.running = True

#     @abstractmethod
#     def get_bytes(self):
#         pass

#     def generate(self):
#         """Generator function for video streaming."""
#         while self.running:
#             frame = self.get_bytes()
#             if frame is None:
#                 continue

#             # Encode frame as JPEG
#             ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
#             if not ret:
#                 continue

#             frame_bytes = buffer.tobytes()

#             # Yield frame in multipart format
#             yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")


class CameraStream:
    """Handles gphoto2 camera live view stream capture."""

    def __init__(self, process):
        """
        Initialize camera stream handler.

        Args:
            max_queue_size: Maximum number of frames to queue (older frames dropped)
        """
        super().__init__()
        self.frame_queue = queue.Queue(2)
        self.running = False
        self.process = process
        self.stream_thread = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.state_lock = threading.Lock()

    def generate(self):
        """Generator function for video streaming."""
        while self.running:
            frame = self.get_bytes()
            if frame is None:
                continue

            # Encode frame as JPEG
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue

            frame_bytes = buffer.tobytes()

            # Yield frame in multipart format
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

    def get_bytes(self) -> Optional[np.ndarray]:
        """
        Get the next frame from the queue.

        Args:
            timeout: Maximum time to wait for a frame

        Returns:
            Frame as numpy array or None if timeout
        """
        try:
            return self.frame_queue.get(timeout=1.0)
        except queue.Empty:
            return None

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
                    jpg = bytes_data[a : b + 2]
                    bytes_data = bytes_data[b + 2 :]

                    # Validate JPEG has minimum size
                    if len(jpg) < 100:
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
                if self.running:  # Only print if we're supposed to be running
                    print(f"Stream reading error: {e}")
                break
