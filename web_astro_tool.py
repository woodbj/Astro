#!/usr/bin/env python3
"""
Launcher for web-based Live FWHM measurement tool.
Can run as web server or interactive shell.
"""

import argparse
from WebGUI import run_server


def interactive_shell(port=5000):
    """Start an interactive Python shell with camera objects available and web server in background."""
    import threading
    import logging
    from Astro.hardware import Camera
    from Astro.services import CameraStream, FileStream
    from Astro.utilities import FileManager
    from Astro.managers import CameraManager, SessionManager
    from Astro.utilities.exposure import Exposure
    from Astro.utilities.analysis import calculate_fwhm, FWHMTracker
    from Astro.utilities.drift_align import DriftAlign

    # Initialize shared objects
    camera = Camera()
    camera_stream = CameraStream(camera)
    camera_manager = CameraManager(camera_stream)
    files = FileManager(".CR3")
    file_stream = FileStream(files)
    session = SessionManager()

    # Inject objects into server module so they're shared
    import WebGUI.server as server_module
    server_module.camera = camera
    server_module.camera_stream = camera_stream
    server_module.camera_manager = camera_manager
    server_module.files = files
    server_module.file_stream = file_stream
    server_module.session = session

    # Start web server in background thread
    def run_server_background():
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)  # Suppress Flask logs in shell
        server_module.run_server(host='0.0.0.0', port=port, debug=False)

    server_thread = threading.Thread(target=run_server_background, daemon=True)
    server_thread.start()
    print(f"\n[Web server started on http://localhost:{port}]\n")

    # Prepare namespace
    namespace = {
        'camera_manager': camera_manager,
        'session': session,
        'camera': camera,
        'camera_stream': camera_stream,
        'file_stream': file_stream,
        'files': files,
        'Exposure': Exposure,
        'calculate_fwhm': calculate_fwhm,
        'FWHMTracker': FWHMTracker,
        'DriftAlign': DriftAlign,
    }

    banner = f"""
=== Astro Camera Interactive Shell ===

Web UI: http://localhost:{port}

Available objects:
  camera_manager  - Main camera control interface
  session         - Session/location manager
  camera          - Direct hardware access
  camera_stream   - Live view stream
  files           - File manager (.CR3 watcher)

Utility classes:
  Exposure        - Load and analyze images
  calculate_fwhm  - Calculate star FWHM
  FWHMTracker     - Track FWHM over time
  DriftAlign      - Polar alignment drift analysis

Quick examples:
  camera_manager.capture()           # Take a photo
  camera_manager.set('iso', '1600')  # Change ISO
  camera_manager.dictionary()        # Show settings
  camera_manager.start_schedule()    # Start scheduled captures

  exp = Exposure(files.get_latest()) # Load latest image
  exp.blobs()                        # Detect stars
"""

    # Try IPython first (nicer interface), fall back to basic REPL
    try:
        from IPython import embed
        embed(banner1=banner, user_ns=namespace)
    except ImportError:
        import code
        code.interact(banner=banner, local=namespace)


def main():
    parser = argparse.ArgumentParser(
        description='Astro Camera Control - Web Server or Interactive Shell'
    )
    parser.add_argument(
        '-s', '--shell',
        action='store_true',
        help='Start interactive Python shell instead of web server'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Web server host (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Web server port (default: 5000)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        default=True,
        help='Enable debug mode (default: True)'
    )

    args = parser.parse_args()

    if args.shell:
        interactive_shell(port=args.port)
    else:
        run_server(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
