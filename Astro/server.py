#!/usr/bin/env python3
"""
Web server for Live FWHM measurement tool.
Provides a browser interface for viewing camera stream and measuring star FWHM.
"""

import os
import argparse
from dataclasses import asdict

from flask import Flask, Response, jsonify, request
from flask_socketio import SocketIO
from Astro.hardware import Camera, CameraController, CameraStream
from Astro.terminal import InteractiveConsole
from Astro.core import Observer

# Get the directory where this file is located
WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Flask app with template and static folders in WebGUI package
app = Flask(
    __name__,
    template_folder=WEBUI_DIR,
    static_folder=os.path.join(WEBUI_DIR, "assets"),
)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
camera = Camera()
camera_controller = CameraController()
camera_controller.init(camera)
camera_stream = CameraStream(camera_controller.stream_ps)

observer = Observer()

# Initialize interactive console with access to camera objects
console = InteractiveConsole(
    locals={"camera": camera, "camera_controller": camera_controller, "app": app}
)


@app.route("/api/session/config", methods=["POST", "GET"])
def session():
    if request.method == "GET":
        data = asdict(observer)
        # print(data)
    elif request.method == "POST":
        data = request.json
        for key, value in data.items():
            observer.__setattr__(key, value)

    return jsonify({"success": True, "data": data})


@app.route("/api/terminal/execute", methods=["POST"])
def execute_terminal_code():
    """Execute Python code in the server's namespace with access to live objects."""
    try:
        data = request.get_json()
        code = data.get("code", "")

        if not code.strip():
            return jsonify({"success": False, "error": "No code provided"}), 400

        # Execute code using the interactive console
        result = console.execute(code)

        return jsonify(
            {
                "success": True,
                "output": result.get("output", ""),
                "error": result.get("error"),
                "incomplete": result.get("incomplete", False),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/terminal/namespace", methods=["GET"])
def get_terminal_namespace():
    """Get the current namespace variables."""
    try:
        namespace = console.get_locals()
        # Convert to serializable format
        namespace_info = {}
        for name, obj in namespace.items():
            if not name.startswith("_"):
                namespace_info[name] = {
                    "type": type(obj).__name__,
                    "repr": repr(obj)[:100],  # Limit length
                }

        return jsonify({"success": True, "namespace": namespace_info})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/terminal/reset", methods=["POST"])
def reset_terminal():
    """Reset the terminal console."""
    try:
        console.reset()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/image/<filename>")
def api_image(filename): ...


@app.route("/api/camera/config", methods=["GET", "POST"])
def camera_config():
    if request.method == "GET":
        data = camera_controller.get_config()
        # print(data['controller'])
        return jsonify({"success": True, "data": data})

    elif request.method == "POST":
        print("Delta:", request.json)
        for k, v in request.json["camera"].items():
            camera.set(k, v)

        for k, v in request.json["controller"].items():
            camera_controller.__setattr__(k, v)
        return jsonify({"success": True})


@app.route("/api/camera/run", methods=["POST"])
def run_camera():
    result = camera_controller.run()
    return jsonify({"success": result})


@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"success": False, "error": str(e)}), 500


# @app.route("/api/session/cwd", methods=["POST"])
# def change_cwd():
#     global session
#     try:
#         result = session.set_cwd()
#     except:
#         ...


# @app.route("/api/get_state", methods=["POST"])
# def get_state():
#     print(request.json)
#     manager = request.json["manager"]
#     data = None
#     if manager == "camera_manager":
#         data = camera_manager.dictionary()
#     elif manager == "session_manager":
#         data = session.dictionary()

#     return jsonify({"success": True, "data": data})


# @app.route("/api/set_state", methods=["POST"])
# def set_state():
#     try:
#         data = request.get_json()
#         manager = data.get("manager")
#         setting = data.get("setting")
#         value = data.get("value")

#         if not manager or not setting or value is None:
#             return jsonify({"success": False, "error": "Missing manager, setting, or value"}), 400

#         if manager == "camera_manager":
#             selected_manager = camera_manager
#         elif manager == "session_manager":
#             selected_manager = session
#         else:
#             return jsonify({"success": False, "error": "Unknown manager"}), 400

#         result = selected_manager.set(setting, value)
#         print(manager, setting, "=", selected_manager.get(setting))
#         return jsonify({"success": True, "data": result})

#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500


@app.route("/video_feed")
def video_feed():
    """Video streaming route."""
    if camera_controller.camera_stream is not None:
        return Response(
            camera_controller.camera_stream.generate(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )
    else:
        raise Exception("Camera stream not active")


# @app.route("/image_feed")
# def image_feed():
#     """Continuously stream the latest captured image."""
#     return Response(file_stream.generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


# @app.route("/api/camera/start", methods=["POST"])
# def start_camera():
#     """Start the camera stream."""
#     global camera_manager

#     try:
#         result = camera_manager.start_live()
#         return jsonify({"success": result})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500


# @app.route("/api/camera/stop", methods=["POST"])
# def stop_camera():
#     """Stop the camera stream."""
#     global camera_manager

#     try:
#         result = camera_manager.stop_live()
#         return jsonify({"success": True, "data": result})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500


# @app.route("/api/camera/capture", methods=["POST"])
# def capture():
#     global camera_manager

#     try:
#         result = camera_manager.capture()
#         return jsonify({"success": True, "data": result})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500


# @app.route("/api/camera/start_schedule", methods=["POST"])
# def start_schedule():
#     """Start the camera stream."""
#     global camera_manager

#     try:
#         result = camera_manager.start_schedule()
#         return jsonify({"success": result})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500


# @app.route("/api/camera/stop_schedule", methods=["POST"])
# def stop_schedule():
#     """Stop the camera stream."""
#     global camera_manager

#     try:
#         result = camera_manager.stop_schedule()
#         return jsonify({"success": True, "data": result})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500


# @app.route("/api/camera/get_config", methods=["POST"])
# def get_config():
#     global camera_manager
#     try:
#         result = camera_manager.dictionary()
#         return jsonify({"success": True, "data": result})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500


# @app.route("/api/camera/set_config", methods=["POST"])
# def set_config():
#     try:
#         data = request.get_json()
#         setting = data.get("setting")
#         value = data.get("value")

#         if not setting or value is None:
#             return jsonify({"success": False, "error": "Missing setting or value"}), 400

#         print(setting)
#         print(type(value))
#         result = camera_manager.set(setting, value)
#         print(result)
#         return jsonify({"success": True, "data": result})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500


# @app.route("/api/camera/status", methods=["POST"])
# def get_status():
#     if camera_manager.live_running:
#         return jsonify({"success": True, "data": {"stream": True}})
#     return jsonify({"success": True, "data": {"stream": False}})


def cleanup():
    """Clean up resources on shutdown."""
    pass


def run_server(host="0.0.0.0", port=5000):
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

    # use_reloader=False prevents OpenMP fork warning
    app.run(host=host, port=port, debug=True, threaded=True, use_reloader=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    run_server(**vars(parser.parse_args()))
