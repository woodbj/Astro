#!/usr/bin/env python3
"""
Live drift alignment plotter
Reads drift_data.json and displays live visualization
Run this separately from drift.py
"""

import json
import os
import matplotlib
matplotlib.use('TkAgg')  # Use TkAgg backend for animation
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from photutils.aperture import CircularAperture
import numpy as np
import rawpy


# Track last data count to detect new data
last_data_count = [0]  # Use list to allow modification in nested function


def load_data():
    """Load drift data from JSON file"""
    try:
        with open('drift_data.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def update_plot(frame):
    """Update function called by animation"""
    data = load_data()

    if data is None:
        return

    # Check if new data has been added
    current_count = len(data.get('alt', []))
    if current_count > last_data_count[0]:
        # New data detected
        alt_errors = data.get('alt', [])
        az_errors = data.get('az', [])
        times_iso = data.get('times', [])

        # Print the new data point
        print(f"\nNew drift data point #{current_count}:")
        print(f"  Time: {times_iso[-1] if times_iso else 'N/A'}")
        print(f"  Altitude drift: {alt_errors[-1]:.2f} arcsec/min")
        print(f"  Azimuth drift: {az_errors[-1]:.2f} arcsec/min")

        last_data_count[0] = current_count

    # Clear previous plots
    ax_img.clear()
    ax_drift.clear()

    # Plot 1: Image with star apertures
    latest_image = data.get('latest_image')
    sources_x = data.get('latest_sources_x')
    sources_y = data.get('latest_sources_y')
    latest_fwhm = data.get('latest_fwhm')

    if latest_image and sources_x and sources_y and latest_fwhm and os.path.exists(latest_image):
        try:
            # Load the image
            with rawpy.imread(latest_image) as raw:
                img = raw.postprocess()

            ax_img.imshow(img)

            # Draw apertures around stars
            fwhm = np.array(latest_fwhm)

            for x, y, r in zip(sources_x, sources_y, fwhm):
                aperture = CircularAperture([(x, y)], r=r)
                aperture.plot(ax=ax_img, color='red', lw=1.5, alpha=0.5)

            ax_img.set_title(f"Latest Image - {len(sources_x)} stars detected")
            ax_img.axis('off')
        except Exception as e:
            ax_img.text(0.5, 0.5, f'Error loading image:\n{str(e)}',
                        ha='center', va='center',
                        transform=ax_img.transAxes)
            ax_img.set_title('Latest Image')
    else:
        ax_img.text(0.5, 0.5, 'Waiting for image data...',
                    ha='center', va='center',
                    transform=ax_img.transAxes)
        ax_img.set_title('Latest Image')

    # Plot 2: Drift errors over time
    alt_errors = data.get('alt', [])
    az_errors = data.get('az', [])
    times_iso = data.get('times', [])

    if len(alt_errors) > 0:
        # Convert ISO times to HH:MM format
        from datetime import datetime
        time_labels = []
        for t in times_iso:
            try:
                dt = datetime.fromisoformat(t)
                time_labels.append(dt.strftime('%H:%M'))
            except (ValueError, AttributeError):
                time_labels.append('')

        x_indices = list(range(len(alt_errors)))

        ax_drift.plot(x_indices, alt_errors, 'b-o',
                      label='Altitude drift', markersize=4)
        ax_drift.plot(x_indices, az_errors, 'r-o',
                      label='Azimuth drift', markersize=4)
        ax_drift.axhline(y=30, color='orange', linestyle='--',
                         alpha=0.5, label='Good (30 arcsec/min)')
        ax_drift.axhline(y=15, color='green', linestyle='--',
                         alpha=0.5, label='Excellent (15 arcsec/min)')
        ax_drift.axhline(y=-30, color='orange', linestyle='--', alpha=0.5)
        ax_drift.axhline(y=-15, color='green', linestyle='--', alpha=0.5)

        # Set x-axis to show times
        ax_drift.set_xticks(x_indices)
        ax_drift.set_xticklabels(time_labels, rotation=45, ha='right')

        ax_drift.set_xlabel('Time (HH:MM)')
        ax_drift.set_ylabel('Drift (arcsec/min)')
        ax_drift.set_title('Polar Alignment Drift')
        ax_drift.legend()
        ax_drift.grid(True, alpha=0.3)
    else:
        ax_drift.text(0.5, 0.5, 'Waiting for drift data...',
                      ha='center', va='center',
                      transform=ax_drift.transAxes)
        ax_drift.set_title('Polar Alignment Drift')

    try:
        plt.tight_layout()
    except Exception as e:
        print(f"Layout error: {e}")


# Create figure
fig, (ax_img, ax_drift) = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle('Live Drift Alignment Monitor', fontsize=14)

print("Live drift plotter started. Close the window to exit.")

# Create animation that updates every 2 seconds
ani = FuncAnimation(fig, update_plot, interval=2000, cache_frame_data=False)

# Show plot - this will block until window is closed
plt.show()
