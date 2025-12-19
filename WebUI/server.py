#!/usr/bin/env python3
"""
Web server for Live FWHM measurement tool.
Provides a browser interface for viewing camera stream and measuring star FWHM.
"""

import cv2
import numpy as np
import os
from flask import Flask, Response, render_template, jsonify, request, send_file
import threading
from io import BytesIO

from Astro.hardware import CameraStream
from Astro.utilities import calculate_fwhm, draw_star_overlay, FWHMTracker

try:
    import rawpy
    import imageio
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False
    print("Warning: rawpy not installed. CR3 preview not available.")

# Get the directory where this file is located
WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Flask app with template and static folders in WebUI package
app = Flask(__name__,
            template_folder=os.path.join(WEBUI_DIR, 'templates'),
            static_folder=os.path.join(WEBUI_DIR, 'static'))

# Global state
camera_stream = None
measurement_state = {
    'star_pos': None,  # (x, y) position of selected star
    'fwhm_tracker': FWHMTracker(max_history=50),
    'box_size': 40,
    'latest_frame': None,
    'frame_width': None,
    'frame_height': None,
}
state_lock = threading.Lock()


def process_frame(frame):
    """Process a frame for FWHM measurement and update state."""
    with state_lock:
        measurement_state['latest_frame'] = frame.copy()

        if measurement_state['frame_width'] is None:
            measurement_state['frame_width'] = frame.shape[1]
            measurement_state['frame_height'] = frame.shape[0]

        star_pos = measurement_state['star_pos']

        if star_pos:
            x, y = star_pos
            fwhm = calculate_fwhm(frame, x, y, measurement_state['box_size'])

            if fwhm is not None:
                measurement_state['fwhm_tracker'].add_measurement(fwhm)


def generate_frames():
    """Generator function for video streaming."""
    global camera_stream

    while True:
        if camera_stream is None or not camera_stream.is_running():
            # Send a placeholder frame
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "Camera not connected", (150, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            ret, buffer = cv2.imencode('.jpg', blank)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            continue

        frame = camera_stream.get_frame(timeout=1.0)
        if frame is None:
            continue

        # Process frame for FWHM measurement
        process_frame(frame)

        # Draw overlay
        with state_lock:
            star_pos = measurement_state['star_pos']
            current_fwhm = measurement_state['fwhm_tracker'].get_current()

            if star_pos:
                display_frame = draw_star_overlay(
                    frame,
                    star_pos[0],
                    star_pos[1],
                    current_fwhm,
                    measurement_state['box_size']
                )
            else:
                display_frame = frame

        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        # Yield frame in multipart format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/')
def index():
    """Main page."""
    return render_template('astro_tool.html')


@app.route('/video_feed')
def video_feed():
    """Video streaming route."""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/select_star', methods=['POST'])
def select_star():
    """API endpoint to select a star for FWHM measurement."""
    data = request.json
    x = data.get('x')
    y = data.get('y')

    if x is None or y is None:
        return jsonify({'error': 'Missing coordinates'}), 400

    with state_lock:
        measurement_state['star_pos'] = (int(x), int(y))
        measurement_state['fwhm_tracker'].reset()

    return jsonify({'success': True, 'x': x, 'y': y})


@app.route('/api/fwhm_data')
def fwhm_data():
    """API endpoint to get current FWHM data."""
    with state_lock:
        stats = measurement_state['fwhm_tracker'].get_statistics()
        data = {
            'current_fwhm': stats['current'],
            'fwhm_history': measurement_state['fwhm_tracker'].get_history(),
            'star_pos': measurement_state['star_pos'],
            'frame_width': measurement_state['frame_width'],
            'frame_height': measurement_state['frame_height'],
        }

    return jsonify(data)


@app.route('/api/camera/start', methods=['POST'])
def start_camera():
    """Start the camera stream."""
    global camera_stream

    if camera_stream is not None and camera_stream.is_running():
        return jsonify({'error': 'Camera already running'}), 400

    camera_stream = CameraStream(max_queue_size=2)
    if camera_stream.start():
        return jsonify({'success': True})
    else:
        camera_stream = None
        return jsonify({'error': 'Failed to start camera'}), 500


@app.route('/api/camera/stop', methods=['POST'])
def stop_camera():
    """Stop the camera stream."""
    global camera_stream

    if camera_stream is None:
        return jsonify({'error': 'Camera not running'}), 400

    camera_stream.stop()
    camera_stream = None

    # Reset measurement state
    with state_lock:
        measurement_state['star_pos'] = None
        measurement_state['fwhm_tracker'].reset()
        measurement_state['latest_frame'] = None

    return jsonify({'success': True})


@app.route('/api/camera/status')
def camera_status():
    """Get camera status."""
    global camera_stream

    is_running = camera_stream is not None and camera_stream.is_running()
    return jsonify({'running': is_running})


@app.route('/api/preview_raw/<path:filename>')
def preview_raw(filename):
    """
    Preview a CR3/RAW file by extracting embedded JPEG or processing.

    Args:
        filename: Path to the raw file
    """
    if not HAS_RAWPY:
        return jsonify({'error': 'rawpy not installed'}), 500

    try:
        # Open the raw file
        with rawpy.imread(filename) as raw:
            # Extract embedded JPEG preview (fast)
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    # Return the embedded JPEG directly
                    return Response(thumb.data, mimetype='image/jpeg')
            except:
                pass

            # If no preview, process the raw data (slower but better quality)
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=True,  # Faster processing
                no_auto_bright=False,
                output_bps=8
            )

            # Convert to JPEG
            img_io = BytesIO()
            imageio.imwrite(img_io, rgb, format='JPEG', quality=85)
            img_io.seek(0)

            return send_file(img_io, mimetype='image/jpeg')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/list_captures')
def list_captures():
    """List captured images in a directory."""
    # You can customize this path
    capture_dir = os.path.join(os.path.dirname(WEBUI_DIR), 'captures')

    if not os.path.exists(capture_dir):
        return jsonify({'images': []})

    images = []
    for filename in os.listdir(capture_dir):
        if filename.lower().endswith(('.cr3', '.cr2', '.nef', '.arw', '.jpg', '.jpeg', '.png')):
            images.append({
                'filename': filename,
                'path': os.path.join(capture_dir, filename)
            })

    return jsonify({'images': images})


def cleanup():
    """Clean up resources on shutdown."""
    global camera_stream
    if camera_stream is not None:
        camera_stream.stop()


def run_server(host='0.0.0.0', port=5000, debug=True):
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


if __name__ == '__main__':
    run_server()
