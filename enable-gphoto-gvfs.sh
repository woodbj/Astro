#!/bin/bash
# Re-enable gvfs-gphoto2 processes for normal file manager operation
# Run this script when you're done using gphoto2 with your camera

echo "Restoring execute permissions to gvfs-gphoto2 processes..."

sudo chmod +x /usr/libexec/gvfs-gphoto2-volume-monitor
sudo chmod +x /usr/libexec/gvfsd-gphoto2

echo "Done! gvfs-gphoto2 processes re-enabled."
echo "File manager should now open faster without service failures."
echo ""
echo "Note: gvfs may interfere with gphoto2 camera access."
echo "Run disable-gphoto-gvfs.sh before using gphoto2."
