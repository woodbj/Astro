#!/usr/bin/env python3
"""
Web server for Live FWHM measurement tool.
Provides a browser interface for viewing camera stream and measuring star FWHM.
"""

import os

from flask import Flask, Response, render_template, jsonify, request
from Astro.hardware import Camera
from Astro.services import CameraStream, FileStream
from Astro.utilities import FileManager
from Astro.managers import CameraManager, SessionManager


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
camera_manager: CameraManager = CameraManager(camera_stream)
files = FileManager(".CR3")
file_stream = FileStream(files)
session = SessionManager()


@app.route("/")
def index():
    """Main page."""
    return render_template("index.html")


@app.route("/api/session/cwd", methods=["POST"])
def change_cwd():
    global session
    try:
        result = session.set_cwd()
    except:
        ...

@app.route("/api/get_state", methods=["POST"])
def get_state():
    print(request.json)
    manager = request.json['manager']
    data = None
    if manager == "camera_manager":
        data = camera_manager.dictionary()
    elif manager == "session_manager":
        data = session.dictionary()

    return jsonify({"success": True, "data": data})


@app.route("/api/set_state", methods=["POST"])
def set_state():
    try:
        data = request.get_json()
        manager = data.get("manager")
        setting = data.get("setting")
        value = data.get("value")

        if not manager or not setting or value is None:
            return jsonify({"success": False, "error": "Missing manager, setting, or value"}), 400

        if manager == "camera_manager":
            selected_manager = camera_manager
        elif manager == "session_manager":
            selected_manager = session
        else:
            return jsonify({"success": False, "error": "Unknown manager"}), 400

        result = selected_manager.set(setting, value)
        print(manager, setting, "=", selected_manager.get(setting))
        return jsonify({"success": True, "data": result})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/video_feed")
def video_feed():
    """Video streaming route."""
    return Response(camera_stream.generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/image_feed")
def image_feed():
    """Continuously stream the latest captured image."""
    return Response(file_stream.generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/camera/start", methods=["POST"])
def start_camera():
    """Start the camera stream."""
    global camera_manager

    try:
        result = camera_manager.start_live()
        return jsonify({"success": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/stop", methods=["POST"])
def stop_camera():
    """Stop the camera stream."""
    global camera_manager

    try:
        result = camera_manager.stop_live()
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/capture", methods=["POST"])
def capture():
    global camera_manager

    try:
        result = camera_manager.capture()
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/camera/start_schedule", methods=["POST"])
def start_schedule():
    """Start the camera stream."""
    global camera_manager

    try:
        result = camera_manager.start_schedule()
        return jsonify({"success": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/stop_schedule", methods=["POST"])
def stop_schedule():
    """Stop the camera stream."""
    global camera_manager

    try:
        result = camera_manager.stop_schedule()
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/get_config", methods=["POST"])
def get_config():
    global camera_manager
    try:
        result = camera_manager.dictionary()
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

        print(setting)
        print(type(value))
        result = camera_manager.set(setting, value)
        print(result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/status", methods=["POST"])
def get_status():
    if camera_manager.live_running:
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
        print("Debug mode enabled")

    # use_reloader=False prevents OpenMP fork warning
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=True)


if __name__ == "__main__":
    run_server()
