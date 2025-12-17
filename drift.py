import os
import threading
import time
import signal
import json
import matplotlib.pyplot as plt
from photutils.aperture import CircularAperture

from Astro import Exposure, DriftAlign

lat = -34.898558500345416
long = 138.5800482838913


def analyse(todo: list[str], exposures: list[Exposure], drift_data: dict, lock, shutdown_event):
    ra = None
    dec = None
    radius = None
    da = DriftAlign(lat, long)
    while not shutdown_event.is_set():
        if len(todo) == 0:
            time.sleep(1)
            continue

        with lock:
            if len(todo) == 0:  # Double check after acquiring lock
                continue
            image = todo.pop(0)

        e = Exposure(image)
        e.load_all()
        print(f"{image} Finding Stars")
        e.blobs()
        print(f"{image} Found {len(e.sources)} stars")

        if ra is None:
            try:
                ra, dec, radius = e.radec_radius()
            except Exception:
                ...
        print(f"{image} Plate solving near {ra} {dec}")
        e.plate_solve(ra, dec, radius)
        ra, dec, radius = e.radec_radius()

        with lock:
            if len(exposures) == 0:
                exposures.append(e)
                print(f"{image} processed (first image)")
                continue
            last = exposures[-1]
            current = e
            exposures.append(e)
            print(f"{image} processed")

        alt, az = da.get_error(last, current)
        print(f"alt:\t{alt},\taz:\t{az}")

        # Store drift data and export to file
        with lock:
            drift_data['alt'].append(float(alt.value))
            drift_data['az'].append(float(az.value))
            drift_data['times'].append(current.time.iso)

            # Export data for live plotting
            with open('drift_data.json', 'w') as f:
                export_data = {
                    'alt': drift_data['alt'],
                    'az': drift_data['az'],
                    'times': drift_data['times'],
                    'latest_image': e.image_path if e.image is not None else None,
                }

                # Export sources as x and y arrays
                if hasattr(e, 'sources') and e.sources is not None:
                    export_data['latest_sources_x'] = e.sources[:, 0].tolist()
                    export_data['latest_sources_y'] = e.sources[:, 1].tolist()
                    export_data['latest_fwhm'] = e.fwhm.tolist()
                else:
                    export_data['latest_sources_x'] = None
                    export_data['latest_sources_y'] = None
                    export_data['latest_fwhm'] = None

                json.dump(export_data, f)


def monitor(todo: list[str], lock, shutdown_event):
    seen_files = set()
    while not shutdown_event.is_set():
        current_files = sorted([im for im in os.listdir() if ".CR3" in im])
        new = set(current_files) - seen_files
        new = sorted(list(new))
        if len(new) > 0:
            with lock:
                print(f"{' '.join(new)} Added")
                todo.extend(new)
            seen_files.update(new)

        time.sleep(1)


def run_visualization(exposures: list[Exposure], drift_data: dict, lock, shutdown_event):
    """Run live visualization in main thread (matplotlib requirement)"""
    plt.ion()
    fig, (ax_img, ax_drift) = plt.subplots(1, 2, figsize=(16, 6))

    try:
        while not shutdown_event.is_set():
            with lock:
                if len(exposures) == 0:
                    time.sleep(1)
                    continue

                # Get the most recent exposure
                latest = exposures[-1]

                # Copy drift data
                alt_errors = drift_data.get('alt', []).copy()
                az_errors = drift_data.get('az', []).copy()
                times = drift_data.get('times', []).copy()

            # Clear previous plots
            ax_img.clear()
            ax_drift.clear()

            # Plot 1: Image with star apertures
            if latest.image is not None and latest.sources is not None:
                ax_img.imshow(latest.image)

                # Draw apertures around stars
                for pos, fwhm in zip(latest.sources, latest.fwhm):
                    aperture = CircularAperture([pos], r=fwhm)
                    aperture.plot(ax=ax_img, color='red', lw=1.5, alpha=0.5)

                ax_img.set_title(f"Latest Image - {len(latest.sources)} stars detected")
                ax_img.axis('off')

            # Plot 2: Drift errors over time
            if len(alt_errors) > 0:
                ax_drift.plot(times, alt_errors, 'b-o', label='Altitude drift', markersize=4)
                ax_drift.plot(times, az_errors, 'r-o', label='Azimuth drift', markersize=4)
                ax_drift.axhline(y=30, color='orange', linestyle='--', alpha=0.5, label='Good (30 arcsec/min)')
                ax_drift.axhline(y=15, color='green', linestyle='--', alpha=0.5, label='Excellent (15 arcsec/min)')
                ax_drift.axhline(y=-30, color='orange', linestyle='--', alpha=0.5)
                ax_drift.axhline(y=-15, color='green', linestyle='--', alpha=0.5)
                ax_drift.set_xlabel('Image Number')
                ax_drift.set_ylabel('Drift (arcsec/min)')
                ax_drift.set_title('Polar Alignment Drift')
                ax_drift.legend()
                ax_drift.grid(True, alpha=0.3)
            else:
                ax_drift.text(0.5, 0.5, 'Waiting for drift data...',
                             ha='center', va='center', transform=ax_drift.transAxes)
                ax_drift.set_title('Polar Alignment Drift')

            plt.tight_layout()
            plt.pause(0.1)
            time.sleep(2)  # Update every 2 seconds

    except KeyboardInterrupt:
        pass
    finally:
        plt.close(fig)


# has the list of images needing to be analysed
lock = threading.Lock()
todo = sorted([im for im in os.listdir() if ".CR3" in im])

# has the analysed images
exposures = []

# drift error data for plotting - load existing data if available
drift_data = {'alt': [], 'az': [], 'times': []}
try:
    with open('drift_data.json', 'r') as f:
        existing_data = json.load(f)
        drift_data['alt'] = existing_data.get('alt', [])
        drift_data['az'] = existing_data.get('az', [])
        drift_data['times'] = existing_data.get('times', [])
        print(f"Loaded {len(drift_data['alt'])} existing drift data points")
except (FileNotFoundError, json.JSONDecodeError):
    print("No existing drift data found, starting fresh")

# Flag to signal shutdown
shutdown_event = threading.Event()

# Create threads
analyser = threading.Thread(target=analyse, args=(todo, exposures, drift_data, lock, shutdown_event))
monitoriser = threading.Thread(target=monitor, args=(todo, lock, shutdown_event))


def signal_handler(sig, frame):
    print("\nShutting down gracefully...")
    shutdown_event.set()


# Register signal handler
signal.signal(signal.SIGINT, signal_handler)

# Start threads
analyser.start()
monitoriser.start()

print("Drift alignment monitoring started. Press Ctrl+C to stop.")

# Run visualization in main thread (comment out to run without GUI)
# run_visualization(exposures, drift_data, lock, shutdown_event)

# If not running visualization, keep main thread alive
try:
    while not shutdown_event.is_set():
        time.sleep(1)
except KeyboardInterrupt:
    signal_handler(signal.SIGINT, None)

# Wait for threads to finish
analyser.join(timeout=5)
monitoriser.join(timeout=5)
print("Shutdown complete.")
