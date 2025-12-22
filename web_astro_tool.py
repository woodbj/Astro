#!/usr/bin/env python3
"""
Launcher for web-based Live FWHM measurement tool.
"""

from WebGUI import run_server

if __name__ == '__main__':
    run_server(host='0.0.0.0', port=5000, debug=True)
