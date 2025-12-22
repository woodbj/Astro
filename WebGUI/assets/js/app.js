// Global state
let streamRunning = false;
let captureRefreshInterval = null;

async function startup() {
    const response = await fetch('/api/camera/status', {
        method: 'POST',
    });
    const data = await response.json();
    if (data.success && data.data && data.data.stream) {
        streamRunning = true;
        // Update UI to reflect running state
        const btn = document.getElementById('live-start-stop');
        if (btn) {
            btn.innerText = 'Stop Live';
            btn.classList.remove('btn-success');
            btn.classList.add('btn-danger');
            btn.dataset.active = 'true';
            const feed = document.getElementById('feed');
            if (feed) {
                feed.src = '/video_feed';
            }
        }
    }
}

// Camera control functions
async function startStream() {
    try {
        const response = await fetch('/api/camera/start', {
            method: 'POST',
        });

        if (response.ok) {
            streamRunning = true;
            console.log('Camera started successfully');
            return true;
        } else {
            const data = await response.json();
            console.error('Failed to start camera:', data.error);
            alert('Failed to start camera. Make sure camera is connected.');
            return false;
        }
    } catch (error) {
        console.error('Error starting camera:', error);
        alert('Error starting camera');
        return false;
    }
}

async function stopStream() {
    try {
        const response = await fetch('/api/camera/stop', {
            method: 'POST',
        });

        if (response.ok) {
            streamRunning = false;
            console.log('Camera stopped successfully');
            return true;
        } else {
            console.error('Failed to stop camera');
            return false;
        }
    } catch (error) {
        console.error('Error stopping camera:', error);
        return false;
    }
}

async function toggleStream() {
    const btn = document.getElementById('live-start-stop');
    const active = btn.dataset.active === 'true';
    const feed = document.getElementById('feed');

    if (!active) {
        // Start the stream
        const success = await startStream();
        if (success) {
            btn.innerText = 'Stop Live';
            btn.classList.remove('btn-success');
            btn.classList.add('btn-danger');
            btn.dataset.active = 'true';
            feed.src = '/video_feed';
        }
    } else {
        // Stop the stream
        const success = await stopStream();
        if (success) {
            btn.innerText = 'Start Live';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-success');
            btn.dataset.active = 'false';
            feed.src = '/image_feed';
        }
    }
}

async function loadCameraTab() {
    const response = await fetch('/api/camera/get_config', {
        method: 'POST',
    });
    if (response.ok) {
        const data = await response.json();
        console.log(data);
        // TODO: Populate camera config UI with data
    } else {
        console.error('Failed to load camera config');
    }
}

// Initialize feed when page loads
window.addEventListener('DOMContentLoaded', function() {
    startup();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (captureRefreshInterval) {
        clearInterval(captureRefreshInterval);
    }
});
