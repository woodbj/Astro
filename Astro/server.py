#!/usr/bin/env python3
"""
Web server for Live FWHM measurement tool.
Provides a browser interface for viewing camera stream and measuring star FWHM.
"""

import os
import argparse
from dataclasses import asdict
import json
import time

from flask import Flask, Response, jsonify, request
from flask_socketio import SocketIO
from Astro.hardware import Camera, CameraController, CameraStream
from Astro.terminal import InteractiveConsole
from Astro.core import Observer, Exposure, FileSystem
from Astro.tools import get_processors, build_pipeline, export_jpeg
from Astro.tools.base import DataEncoder

# Get the directory where this file is located
WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Flask app with template and static folders in WebGUI package
app = Flask(
    __name__,
    template_folder=WEBUI_DIR,
    static_folder=os.path.join(WEBUI_DIR, "assets"),
)

# Configure Flask to use custom JSON encoder for numpy arrays
# For Flask 2.2+, use the json provider interface
from flask.json.provider import DefaultJSONProvider
import numpy as np
from pathlib import Path


class NumpyJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


app.json = NumpyJSONProvider(app)

# Fallback for older Flask versions
try:
    app.json_encoder = DataEncoder
except AttributeError:
    pass

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
camera = Camera()
camera_controller = CameraController()
camera_controller.init(camera)
camera_stream = CameraStream(camera_controller.stream_ps)

observer = Observer()

file_system = FileSystem(Path(os.getcwd()))

# Initialize auto-processing components
from Astro.core import FileSystem, Watch, ExposureLibrary
from pathlib import Path

filesystem = None
library = ExposureLibrary()
auto_processing_enabled = False
auto_processing_pipeline_id = None


def auto_process_callback(files: set[Path]):
    """Process new files with configured pipeline."""
    global auto_processing_pipeline_id

    if not auto_processing_pipeline_id:
        print("Auto-processing: No pipeline configured")
        return

    library.put_files(files)

    try:
        # Load the configured pipeline
        pipeline = pipeline_manager.load(auto_processing_pipeline_id)

        for file in files:
            try:
                print(f"Auto-processing: {file.name}")

                # Load exposure and get image
                exposure = Exposure(str(file))
                image = exposure.get_image()

                # Run pipeline
                result_image, result_data = pipeline.run(image)

                # Save results
                result_id = pipeline_manager.save_results(
                    str(file), auto_processing_pipeline_id, result_image, result_data
                )

                print(f"Auto-processing complete: {result_id}")
                print(f"  - Sources: {result_data.get('num_sources', 0)}")
                if "median_fwhm" in result_data:
                    print(f"  - FWHM: {result_data['median_fwhm']:.2f} px")

            except Exception as e:
                print(f"Auto-processing failed for {file.name}: {e}")

    except Exception as e:
        print(f"Auto-processing error: {e}")


# Initialize interactive console with access to camera objects
console = InteractiveConsole(
    locals={
        "camera": camera,
        "camera_controller": camera_controller,
        "app": app,
        "observer": observer,
        "pipeline_manager": pipeline_manager,
        "library": library,
        "filesystem": filesystem,
    }
)


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# SESSION / OBSERVER ROUTES
# ============================================================================


@app.route("/api/session/config", methods=["POST", "GET"])
def session():
    """Get or update observer session configuration."""
    if request.method == "GET":
        data = asdict(observer)
    elif request.method == "POST":
        data = request.json
        for key, value in data.items():
            observer.__setattr__(key, value)

    return jsonify({"success": True, "data": data})


# ============================================================================
# CAMERA ROUTES
# ============================================================================


@app.route("/api/camera/config", methods=["GET", "POST"])
def camera_config():
    """Get or update camera configuration."""
    if request.method == "GET":
        data = camera_controller.get_config()
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
    """Start camera capture."""
    result = camera_controller.run()
    return jsonify({"success": result})


# ============================================================================
# TERMINAL / CONSOLE ROUTES
# ============================================================================


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


# ============================================================================
# PIPELINE ROUTES
# ============================================================================


@app.route("/api/pipeline/processors", methods=["GET"])
def get_pipeline_processors():
    """Return JSON schemas for all available processors."""
    try:
        schemas = get_processors()
        return jsonify({"success": True, "data": schemas})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pipeline/build", methods=["POST"])
def build_save_pipeline():
    """Build and save pipeline from schema."""
    try:
        schema = request.json.get("schema")
        name = request.json.get("name")

        pipeline = pipeline_manager.build(schema)
        pipeline_id = pipeline_manager.save(pipeline, name=name)

        return jsonify({"success": True, "pipeline_id": pipeline_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/pipeline/execute", methods=["POST"])
def execute_pipeline_route():
    """Execute pipeline on exposure.

    JSON params:
        pipeline_id: Pipeline to execute
        exposure_id: Image file path
        save_intermediate: Optional, save image at each step (default: False)
    """
    try:
        # Load pipeline
        pipeline = build_pipeline(request.get_json()['pipeline_config'])

        # Load exposure and get image
        exposure_id = request.get_json()['exposure_id']
        exposure = Exposure(exposure_id)
        image = exposure.get_image()

        # Run pipeline with optional intermediate saves
        save_intermediate = request.json.get("save_intermediate", False)
        result_image, result_data = pipeline.run(image, export=save_intermediate)
        output = pipeline.output

        # log saved data
        path = Path("results") / Path(exposure_id).stem / Path(str(int(time.time())))
        path.mkdir(parents=True, exist_ok=True)

        images = []
        for i, entry in enumerate(output):
            filepath = path / Path(f"step_{i}")
            try:
                jpg_file = export_jpeg(image, filepath)
                images.append(jpg_file)
            except Exception as e:
                raise Exception(f"{e}: could not create jpg")

            # Remove image and enter 
            del entry['image']
            try:
                json_file = filepath.with_suffix(".json")
                with open(json_file, "w") as f:
                    json.dump(entry, f, indent=2)
            except Exception as e:
                raise Exception(f"{e}: could not json.dump entry")

        return jsonify({"success": True, "data": images})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pipeline/templates", methods=["GET"])
def get_pipeline_templates():
    """Get predefined pipeline templates."""
    try:
        templates = pipeline_manager.get_templates()
        return jsonify({"success": True, "data": templates})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pipeline/results/<result_id>", methods=["GET"])
def get_pipeline_results(result_id):
    """Retrieve pipeline execution results."""
    try:
        results = pipeline_manager.get_results(result_id)
        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# AUTO-PROCESSING ROUTES
# ============================================================================


@app.route("/api/pipeline/auto/config", methods=["GET", "POST"])
def auto_processing_config():
    """Get or set auto-processing configuration."""
    global auto_processing_enabled, auto_processing_pipeline_id, filesystem

    try:
        if request.method == "GET":
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "enabled": auto_processing_enabled,
                        "pipeline_id": auto_processing_pipeline_id,
                        "watch_path": str(filesystem.home) if filesystem else None,
                        "watch_extension": ".CR3",
                    },
                }
            )

        elif request.method == "POST":
            data = request.json

            if "pipeline_id" in data:
                auto_processing_pipeline_id = data["pipeline_id"]

            if "enabled" in data:
                enabled = data["enabled"]
                watch_path = data.get("watch_path", "./incoming")
                watch_ext = data.get("watch_extension", ".CR3")

                if enabled and not auto_processing_enabled:
                    # Enable auto-processing
                    if not auto_processing_pipeline_id:
                        return jsonify(
                            {
                                "success": False,
                                "error": "No pipeline configured for auto-processing",
                            }
                        ), 400

                    # Initialize filesystem if needed
                    if filesystem is None:
                        filesystem = FileSystem(Path(watch_path).parent)

                    # Create watch
                    watch = Watch(
                        path=Path(watch_path), ext=watch_ext, callback=auto_process_callback
                    )

                    filesystem.add_watch(watch)
                    auto_processing_enabled = True
                    print(f"Auto-processing enabled: {watch_path} ({watch_ext})")

                elif not enabled and auto_processing_enabled:
                    # Disable auto-processing
                    if filesystem:
                        filesystem.stop_watch()
                    auto_processing_enabled = False
                    print("Auto-processing disabled")

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "enabled": auto_processing_enabled,
                        "pipeline_id": auto_processing_pipeline_id,
                    },
                }
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pipeline/auto/status", methods=["GET"])
def auto_processing_status():
    """Get current auto-processing status."""
    try:
        return jsonify(
            {
                "success": True,
                "data": {
                    "enabled": auto_processing_enabled,
                    "pipeline_id": auto_processing_pipeline_id,
                    "processed_count": len(library.exposures),
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# FILESYSTEM ROUTES
# ============================================================================


@app.route("/api/filesystem/scan/<extension>", methods=["GET"])
def scan_filesystem(extension):
    """Scan filesystem for files with specific extension.

    Args:
        extension: File extension to search for (e.g., 'CR3', 'fits', 'jpg')

    Query params:
        path: Base path to scan (default: current directory)
        recursive: Whether to scan recursively (default: true)
    """
    try:
        # Get query parameters
        base_path = request.args.get("path", ".")
        recursive = request.args.get("recursive", "true").lower() == "true"

        # Ensure extension has leading dot
        if not extension.startswith("."):
            extension = f".{extension}"

        images = []
        base_dir = Path(base_path).resolve()  # Get absolute path of search directory

        if recursive:
            # Recursive scan
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    file_path = Path(root) / Path(file)
                    if file_path.suffix.lower() == extension.lower():
                        # Store as dict with both absolute and relative paths
                        try:
                            rel_path = file_path.relative_to(base_dir)
                            images.append(
                                {
                                    "absolute": str(file_path),
                                    "relative": str(rel_path),
                                    "name": file_path.name,
                                }
                            )
                        except ValueError:
                            # If relative path fails, just use absolute
                            images.append(
                                {
                                    "absolute": str(file_path),
                                    "relative": str(file_path),
                                    "name": file_path.name,
                                }
                            )
        else:
            # Single directory scan
            if base_dir.exists() and base_dir.is_dir():
                for file_path in base_dir.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() == extension.lower():
                        images.append(
                            {
                                "absolute": str(file_path),
                                "relative": file_path.name,
                                "name": file_path.name,
                            }
                        )

        return jsonify(
            {
                "success": True,
                "data": {
                    "files": sorted(images, key=lambda x: x["relative"]),
                    "count": len(images),
                    "extension": extension,
                    "base_path": str(Path(base_path).absolute()),
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/filesystem/cwd", methods=["GET", "POST"])
def filesystem_cwd():
    if request.method == "POST":
        path = Path(request.data)
        file_system.cwd(path)
        response = str(file_system.home)
    elif request.method == "GET":
        response = str(file_system.home)

    return jsonify({"success": True, "data": response})


# ============================================================================
# MEDIA ROUTES
# ============================================================================


@app.route("/api/image/<filename>")
def api_image(filename):
    """Serve image files."""
    ...


@app.route("/video_feed")
def video_feed():
    """Video streaming route for camera feed."""
    if camera_controller.camera_stream is not None:
        return Response(
            camera_controller.camera_stream.generate(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )
    else:
        raise Exception("Camera stream not active")


# ============================================================================
# SERVER LIFECYCLE
# ============================================================================


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
