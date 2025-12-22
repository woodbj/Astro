#!/usr/bin/env python3
"""
Web server for Live FWHM measurement tool.
Provides a browser interface for viewing camera stream and measuring star FWHM.
"""

import os
from flask import Flask, Response, render_template, jsonify, request
from Astro.hardware import Camera
from Astro.services import CameraStream
from Astro.utilities import FileManager


# Get the directory where this file is located
WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Flask app with template and static folders in WebGUI package
app = Flask(
    __name__,
    template_folder=WEBUI_DIR,
    static_folder=os.path.join(WEBUI_DIR, "assets"),
)

# Global state
camera = Camera()
camera_stream: CameraStream = CameraStream(camera)
files = FileManager(".CR3")


@app.route("/")
def index():
    """Main page."""
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    """Video streaming route."""
    return Response(camera_stream.get(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/image_feed")
def image_feed():
    """Continuously stream the latest captured image."""
    import time
    import cv2
    import numpy as np
    import rawpy

    def generate():
        last_file = None
        cached_bytes = None
        while True:
            try:
                file = files.get_latest()

                if file is None:
                    # No files available - send placeholder
                    blank = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(
                        blank,
                        "No Captures Available",
                        (150, 240),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (255, 255, 255),
                        2,
                    )
                    ret, buffer = cv2.imencode(".jpg", blank)
                    frame_bytes = buffer.tobytes()
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
                # Only send if file changed
                elif file != last_file:
                    print(f"Loading new file: {file}")

                    # Check for cached JPEG preview
                    file_stub = os.path.splitext(file)[0]
                    jpeg_cache_path = f"{file_stub}_preview.jpg"

                    if os.path.exists(jpeg_cache_path):
                        # Load cached preview
                        with open(jpeg_cache_path, 'rb') as f:
                            frame_bytes = f.read()
                    else:
                        # Generate preview from RAW
                        with rawpy.imread(file) as raw:
                            image = raw.postprocess()

                        # Resize for faster loading (max 1920px wide)
                        height, width = image.shape[:2]
                        if width > 1920:
                            scale = 1920 / width
                            new_width = 1920
                            new_height = int(height * scale)
                            image_resized = cv2.resize(image, (new_width, new_height))
                        else:
                            image_resized = image

                        # Convert RGB to BGR for OpenCV
                        image_bgr = cv2.cvtColor(image_resized, cv2.COLOR_RGB2BGR)
                        ret, buffer = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if not ret:
                            raise Exception("Failed to encode image as JPEG")
                        frame_bytes = buffer.tobytes()

                        # Cache to disk
                        with open(jpeg_cache_path, 'wb') as f:
                            f.write(frame_bytes)

                    cached_bytes = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    yield cached_bytes
                    last_file = file
                    print(f"Successfully loaded: {file}")
                # Send cached bytes if same file
                elif cached_bytes is not None:
                    yield cached_bytes
            except Exception as e:
                print(f"Error in image_feed: {e}")
                import traceback
                traceback.print_exc()

            time.sleep(1)  # Check for new images every second

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/camera/start", methods=["POST"])
def start_camera():
    """Start the camera stream."""
    global camera_stream

    try:
        result = camera_stream.start()
        if result is True:
            return jsonify({"success": True})
        else:
            return jsonify(
                {"success": False, "error": "Camera not detected. Please check connection."}
            ), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/stop", methods=["POST"])
def stop_camera():
    """Stop the camera stream."""
    global camera_stream

    if camera_stream is None:
        return jsonify({"error": "Camera not running"}), 400

    camera_stream.stop()

    return jsonify({"success": True})


@app.route("/api/camera/capture", methods=["POST"])
def capture():
    try:
        result = camera.capture()
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/get_config", methods=["POST"])
def get_config():
    try:
        result = camera.get_config()
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/set_config", methods=["POST"])
def set_config():
    try:
        data = request.get_json()
        setting = data.get("setting")
        value = data.get("value")

        if not setting or value is None:
            return jsonify({"success": False, "error": "Missing setting or value"}), 400

        result = camera.set(setting, value)
        print(result)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/status", methods=["POST"])
def get_status():
    if camera_stream and camera_stream.running:
        return jsonify({"success": True, "data": {"stream": True}})
    return jsonify({"success": True, "data": {"stream": False}})


def cleanup():
    """Clean up resources on shutdown."""
    pass


def run_server(host="0.0.0.0", port=5000, debug=True):
    """
    Run the web server.

    Args:
        host: Host address to bind to
        port: Port number to listen on
        debug: Enable Flask debug mode
    """
    import atexit

    atexit.register(cleanup)

    print("Starting web-based FWHM measurement tool...")
    print(f"Open http://localhost:{port} in your browser")
    if debug:
        print("Debug mode enabled - server will auto-reload on file changes")

    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run_server()
