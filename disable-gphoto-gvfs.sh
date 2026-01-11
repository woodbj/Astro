#!/bin/bash
# Disable gvfs-gphoto2 processes to prevent interference with gphoto2 camera access
# Run this script before using gphoto2 with your camera

echo "Removing execute permissions from gvfs-gphoto2 processes..."

sudo chmod -x /usr/libexec/gvfs-gphoto2-volume-monitor
sudo chmod -x /usr/libexec/gvfsd-gphoto2

echo "Done! gvfs-gphoto2 processes disabled."
echo "Your camera should now work with gphoto2."
echo ""
echo "Note: This will cause systemd service failures for gvfs-gphoto2-volume-monitor"
echo "which may slow down your file manager. Run enable-gphoto-gvfs.sh when done."
