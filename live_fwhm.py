#!/usr/bin/env python3
"""
Live FWHM measurement tool for astrophotography focusing.
Processes gphoto2 camera live view stream and measures star FWHM in real-time.
"""

import cv2
import numpy as np
import subprocess
import sys
from scipy.optimize import curve_fit
from scipy.ndimage import center_of_mass
import threading
import queue

class LiveFWHMMeasurement:
    def __init__(self):
        self.star_pos = None  # (x, y) position of selected star
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = False
        self.process = None
        self.fwhm_history = []
        self.max_history = 50
        self.box_size = 40  # Size of box around star for FWHM calculation
        self.frame_width = None  # Width of the camera frame (for mouse callback bounds checking)

    def gaussian_2d(self, coords, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
        """2D Gaussian function for fitting."""
        x, y = coords
        xo = float(xo)
        yo = float(yo)
        a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
        b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
        c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
        g = offset + amplitude*np.exp( - (a*((x-xo)**2) + 2*b*(x-xo)*(y-yo) + c*((y-yo)**2)))
        return g.ravel()

    def calculate_fwhm(self, frame, x, y):
        """
        Calculate FWHM of a star at position (x, y) using Gaussian fitting.
        Returns FWHM value or None if calculation fails.
        """
        try:
            # Extract region around star
            half_box = self.box_size // 2
            x_min = max(0, x - half_box)
            x_max = min(frame.shape[1], x + half_box)
            y_min = max(0, y - half_box)
            y_max = min(frame.shape[0], y + half_box)

            region = frame[y_min:y_max, x_min:x_max].astype(float)

            if region.size == 0:
                return None

            # Create coordinate arrays
            h, w = region.shape
            y_coords, x_coords = np.mgrid[0:h, 0:w]

            # Initial guess for Gaussian parameters
            background = np.percentile(region, 10)
            amplitude = region.max() - background

            # Find approximate center using center of mass
            threshold_region = region - background
            threshold_region[threshold_region < 0] = 0
            cy, cx = center_of_mass(threshold_region)

            if np.isnan(cx) or np.isnan(cy):
                return None

            initial_guess = (
                amplitude,  # amplitude
                cx,         # x center
                cy,         # y center
                3.0,        # sigma_x
                3.0,        # sigma_y
                0.0,        # theta (rotation)
                background  # offset
            )

            # Fit 2D Gaussian
            popt, _ = curve_fit(
                self.gaussian_2d,
                (x_coords, y_coords),
                region.ravel(),
                p0=initial_guess,
                maxfev=1000
            )

            # Extract sigma values and calculate FWHM
            sigma_x = abs(popt[3])
            sigma_y = abs(popt[4])

            # FWHM = 2.355 * sigma (for Gaussian)
            fwhm_x = 2.355 * sigma_x
            fwhm_y = 2.355 * sigma_y
            fwhm_avg = (fwhm_x + fwhm_y) / 2.0

            return fwhm_avg

        except Exception as e:
            print(f"FWHM calculation error: {e}")
            return None

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks to select star position."""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Only accept clicks within the camera view (left side of display)
            if self.frame_width is not None and x < self.frame_width:
                self.star_pos = (x, y)
                self.fwhm_history = []  # Reset history when new star selected
                print(f"Star selected at ({x}, {y})")
            elif self.frame_width is not None:
                print("Click on the camera view (left side) to select a star")

    def read_mjpeg_stream(self):
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
                        # Add to queue (drop old frames if queue is full)
                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        self.frame_queue.put(frame)

            except Exception as e:
                print(f"Stream reading error: {e}")
                break

    def draw_overlay(self, frame, fwhm=None, star_view=None):
        """Draw FWHM measurements and star selection box on frame, with side panel."""
        # Create main display frame
        main_frame = frame.copy()

        # Draw selected star position on main frame
        if self.star_pos:
            x, y = self.star_pos
            half_box = self.box_size // 2

            # Draw box around star
            cv2.rectangle(
                main_frame,
                (x - half_box, y - half_box),
                (x + half_box, y + half_box),
                (0, 0, 255),
                2
            )

            # Draw crosshair
            cv2.line(main_frame, (x - 10, y), (x + 10, y), (0, 0, 255), 1)
            cv2.line(main_frame, (x, y - 10), (x, y + 10), (0, 0, 255), 1)

        # Draw FWHM value on main frame
        if fwhm is not None:
            text = f"FWHM: {fwhm:.2f} px"
            cv2.putText(
                main_frame,
                text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                2
            )

        # Draw instructions on main frame
        instructions = "Click on a star to measure FWHM | Press 'q' to quit"
        cv2.putText(
            main_frame,
            instructions,
            (10, main_frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

        # Create side panel with star view and graph
        panel_width = 400
        panel_height = main_frame.shape[0]
        side_panel = np.full((panel_height, panel_width, 3), 20, dtype=np.uint8)

        # Calculate evenly spaced sections for the three components
        top_margin = 30
        bottom_margin = 30
        spacing = 30  # Space between components

        # Component heights
        star_view_height = star_view.shape[0] if star_view is not None else 320
        hist_height = 120
        graph_height = 150

        # Calculate total height needed
        total_content_height = star_view_height + hist_height + graph_height + (2 * spacing)

        # Calculate available space
        available_height = panel_height - top_margin - bottom_margin

        # If content doesn't fit, reduce spacing proportionally
        if total_content_height > available_height:
            # Calculate reduced spacing to fit everything
            total_component_height = star_view_height + hist_height + graph_height
            remaining_space = available_height - total_component_height
            spacing = max(10, remaining_space // 2)  # At least 10px spacing

        # Calculate starting Y position
        total_height_with_spacing = star_view_height + hist_height + graph_height + (2 * spacing)
        start_y = top_margin + max(0, (available_height - total_height_with_spacing) // 2)

        # Position each component
        star_y = start_y
        hist_y = star_y + star_view_height + spacing
        graph_y = hist_y + hist_height + spacing

        # Add star viewer
        if star_view is not None:
            h, w = star_view.shape[:2]
            x_offset = (panel_width - w) // 2  # Center horizontally

            if star_y + h < panel_height:
                side_panel[star_y:star_y+h, x_offset:x_offset+w] = star_view

                # Add label
                cv2.putText(
                    side_panel,
                    "Star View",
                    (10, star_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )

        # Add histogram
        if self.star_pos is not None and star_view is not None:
            hist_width = panel_width - 40
            hist_x = 20

            # Get histogram from the star region
            x, y = self.star_pos
            zoom_size = 80
            half_size = zoom_size // 2
            x_min = max(0, x - half_size)
            x_max = min(frame.shape[1], x + half_size)
            y_min = max(0, y - half_size)
            y_max = min(frame.shape[0], y + half_size)

            star_region = frame[y_min:y_max, x_min:x_max]
            if star_region.size > 0:
                self.draw_histogram_to_panel(side_panel, star_region, hist_x, hist_y, hist_width, hist_height)

        # Add FWHM graph
        if fwhm is not None and len(self.fwhm_history) > 1:
            graph_width = panel_width - 40
            graph_x = 20

            self.draw_fwhm_graph_to_panel(side_panel, graph_x, graph_y, graph_width, graph_height)

        # Combine main frame and side panel
        display_frame = np.hstack([main_frame, side_panel])

        return display_frame

    def draw_histogram_to_panel(self, frame, star_region, hist_x, hist_y, hist_width, hist_height):
        """Draw histogram of the selected star region."""
        # Background for histogram
        cv2.rectangle(
            frame,
            (hist_x, hist_y),
            (hist_x + hist_width, hist_y + hist_height),
            (20, 20, 20),
            -1
        )
        cv2.rectangle(
            frame,
            (hist_x, hist_y),
            (hist_x + hist_width, hist_y + hist_height),
            (100, 100, 100),
            1
        )

        # Add title
        cv2.putText(
            frame,
            "Brightness Histogram",
            (hist_x + 5, hist_y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

        # Calculate histogram for each channel
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]  # BGR

        # Convert to grayscale for combined histogram
        gray_region = cv2.cvtColor(star_region, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray_region], [0], None, [256], [0, 256])

        # Normalize histogram to fit in display area
        hist_normalized = hist / hist.max() * (hist_height - 10) if hist.max() > 0 else hist

        # Draw histogram bars
        bar_width = hist_width / 256.0
        for i in range(256):
            bar_height = int(hist_normalized[i])
            if bar_height > 0:
                # Color gradient from black to white
                color_val = i
                color = (color_val, color_val, color_val)

                cv2.rectangle(
                    frame,
                    (int(hist_x + i * bar_width), hist_y + hist_height - bar_height - 5),
                    (int(hist_x + (i + 1) * bar_width), hist_y + hist_height - 5),
                    color,
                    -1
                )

        # Draw mean and peak markers
        mean_val = int(gray_region.mean())
        peak_val = int(np.argmax(hist))

        # Mean line (green)
        mean_x = int(hist_x + mean_val * bar_width)
        cv2.line(frame, (mean_x, hist_y + 5), (mean_x, hist_y + hist_height - 5), (0, 255, 0), 2)

        # Peak line (red)
        peak_x = int(hist_x + peak_val * bar_width)
        cv2.line(frame, (peak_x, hist_y + 5), (peak_x, hist_y + hist_height - 5), (0, 0, 255), 2)

        # Labels
        cv2.putText(
            frame,
            f"Mean: {mean_val}",
            (hist_x + 5, hist_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 255, 0),
            1
        )
        cv2.putText(
            frame,
            f"Peak: {peak_val}",
            (hist_x + 5, hist_y + 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 0, 255),
            1
        )

    def draw_fwhm_graph_to_panel(self, frame, graph_x, graph_y, graph_width, graph_height):
        """Draw FWHM history graph at specified position."""
        if not self.fwhm_history:
            return

        # Background for graph
        cv2.rectangle(
            frame,
            (graph_x, graph_y),
            (graph_x + graph_width, graph_y + graph_height),
            (20, 20, 20),
            -1
        )
        cv2.rectangle(
            frame,
            (graph_x, graph_y),
            (graph_x + graph_width, graph_y + graph_height),
            (100, 100, 100),
            1
        )

        # Add title
        cv2.putText(
            frame,
            "FWHM History",
            (graph_x + 5, graph_y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

        # Normalize FWHM values for graphing
        values = np.array(self.fwhm_history)
        min_val = values.min()
        max_val = values.max()

        if max_val - min_val > 0.01:  # Avoid division by zero
            normalized = (values - min_val) / (max_val - min_val)
        else:
            normalized = np.ones_like(values) * 0.5

        # Draw graph line
        points = []
        for i, val in enumerate(normalized):
            x = graph_x + int((i / len(values)) * graph_width)
            y = graph_y + graph_height - int(val * graph_height)
            points.append((x, y))

        for i in range(len(points) - 1):
            cv2.line(frame, points[i], points[i+1], (0, 0, 255), 2)

        # Draw min/max labels (lower FWHM is better, so highlight min)
        cv2.putText(
            frame,
            f"Worst: {max_val:.2f}",
            (graph_x + 5, graph_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1
        )
        cv2.putText(
            frame,
            f"Best: {min_val:.2f}",
            (graph_x + 5, graph_y + graph_height - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (0, 255, 0),
            1
        )

        # Current value
        if len(self.fwhm_history) > 0:
            cv2.putText(
                frame,
                f"Current: {self.fwhm_history[-1]:.2f}",
                (graph_x + 5, graph_y + 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 255),
                1
            )

    def get_star_view(self, frame, gray_frame, fwhm):
        """
        Extract and display a zoomed-in view of the selected star.
        Returns an image suitable for display.
        """
        if not self.star_pos:
            return None

        x, y = self.star_pos
        zoom_size = 80  # Larger region for better view
        half_size = zoom_size // 2

        # Extract region
        x_min = max(0, x - half_size)
        x_max = min(frame.shape[1], x + half_size)
        y_min = max(0, y - half_size)
        y_max = min(frame.shape[0], y + half_size)

        region = frame[y_min:y_max, x_min:x_max].copy()

        if region.size == 0:
            return None

        # Scale up for better visibility (4x zoom)
        scale_factor = 4
        zoomed = cv2.resize(
            region,
            None,
            fx=scale_factor,
            fy=scale_factor,
            interpolation=cv2.INTER_NEAREST
        )

        # Draw crosshair at center
        center_x = zoomed.shape[1] // 2
        center_y = zoomed.shape[0] // 2
        cv2.line(zoomed, (center_x - 20, center_y), (center_x + 20, center_y), (0, 0, 255), 1)
        cv2.line(zoomed, (center_x, center_y - 20), (center_x, center_y + 20), (0, 0, 255), 1)

        # Draw measurement box (scaled)
        box_half = (self.box_size // 2) * scale_factor
        cv2.rectangle(
            zoomed,
            (center_x - box_half, center_y - box_half),
            (center_x + box_half, center_y + box_half),
            (0, 0, 255),
            1
        )

        # Add FWHM text
        if fwhm is not None:
            cv2.putText(
                zoomed,
                f"FWHM: {fwhm:.2f} px",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2
            )

        return zoomed

    def run(self):
        """Main loop for live FWHM measurement."""
        print("Starting live FWHM measurement...")
        print("Click on a star to start measuring FWHM")
        print("Press 'q' to quit")

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
            return
        except Exception as e:
            print(f"Error starting gphoto2: {e}")
            return

        # Start stream reading thread
        self.running = True
        stream_thread = threading.Thread(target=self.read_mjpeg_stream, daemon=True)
        stream_thread.start()

        # Create window and set mouse callback (WINDOW_NORMAL allows resizing/maximizing)
        cv2.namedWindow('Live FWHM Measurement', cv2.WINDOW_NORMAL)
        cv2.setMouseCallback('Live FWHM Measurement', self.mouse_callback)

        try:
            while self.running:
                # Get latest frame
                try:
                    frame = self.frame_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Store frame width for mouse callback bounds checking
                if self.frame_width is None:
                    self.frame_width = frame.shape[1]

                # Convert to grayscale for FWHM calculation
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Calculate FWHM if star is selected
                fwhm = None
                star_view = None
                if self.star_pos:
                    x, y = self.star_pos
                    fwhm = self.calculate_fwhm(gray_frame, x, y)

                    if fwhm is not None:
                        self.fwhm_history.append(fwhm)
                        if len(self.fwhm_history) > self.max_history:
                            self.fwhm_history.pop(0)

                    # Get zoomed star view
                    star_view = self.get_star_view(frame, gray_frame, fwhm)

                # Draw overlay and display
                display_frame = self.draw_overlay(frame, fwhm, star_view)

                # Pad the display to fill window with dark background (20, 20, 20)
                try:
                    window_rect = cv2.getWindowImageRect('Live FWHM Measurement')
                    window_w, window_h = window_rect[2], window_rect[3]

                    if window_w > 0 and window_h > 0:
                        frame_h, frame_w = display_frame.shape[:2]

                        # If window is larger than frame, create padded frame with dark background
                        if window_w > frame_w or window_h > frame_h:
                            # Create dark background canvas
                            padded = np.full((window_h, window_w, 3), 20, dtype=np.uint8)

                            # Calculate position to center the display
                            y_offset = max(0, (window_h - frame_h) // 2)
                            x_offset = max(0, (window_w - frame_w) // 2)

                            # Place display in center
                            padded[y_offset:y_offset+frame_h, x_offset:x_offset+frame_w] = display_frame
                            display_frame = padded
                except:
                    pass  # If we can't get window size, just use original

                cv2.imshow('Live FWHM Measurement', display_frame)

                # Check for quit (key press or window close)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break

                # Check if window was closed
                if cv2.getWindowProperty('Live FWHM Measurement', cv2.WND_PROP_VISIBLE) < 1:
                    print("\nWindow closed")
                    break

        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        print("Cleaning up...")
        self.running = False

        if self.process:
            print("Terminating gphoto2 process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
                print("gphoto2 process terminated successfully")
            except subprocess.TimeoutExpired:
                print("gphoto2 not responding, force killing...")
                self.process.kill()
                self.process.wait()  # Wait for kill to complete
                print("gphoto2 process killed")

        cv2.destroyAllWindows()

        # Release camera
        print("Releasing camera...")
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

        print("Cleanup complete")

if __name__ == '__main__':
    measurement = LiveFWHMMeasurement()
    measurement.run()
