// Global state
let streamRunning = false;
let scheduleRunning = false;
let captureRefreshInterval = null;

async function chooseFolder() {
    try {
        const dirHandle = await window.showDirectoryPicker();
        console.log(dirHandle);
    } catch (err) {
        console.error(err);
    }
}

async function loadTab() {
    const managerId = document.querySelector("#managers .nav-link.active").id
    const response = await fetch('/api/get_state', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({"manager": managerId})
    })
    const result = await response.json()
    const data = result['data']

    for (const id in data) {
        const element = document.getElementById(id)
        if (element !== null) {
            const configData = data[id]

            // Check if this is a dropdown with options
            if (configData.options && Array.isArray(configData.options)) {
                // Convert to format expected by populateDropdown
                const dropdownData = {
                    Choices: configData.options,
                    Current: configData.value
                }
                populateDropdown(element, dropdownData)
            } else if (configData.value !== undefined) {
                // Handle checkboxes
                if (element.type === 'checkbox') {
                    element.checked = configData.value
                } else {
                    // Simple value assignment for other input types
                    element.value = configData.value
                }
            }
        }
    }
}

async function updateSetting(event) {
    const managerId = document.querySelector("#managers .nav-link.active").id
    const elementId = event.target.id
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value

    try {
        const response = await fetch('/api/set_state', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                manager: managerId,
                setting: elementId,
                value: value
            })
        })

        const result = await response.json()

        if (!result.success) {
            console.error('Failed to update setting:', result.error)
            alert('Failed to update setting')
        }
    } catch (error) {
        console.error('Error updating setting:', error)
        alert('Error updating setting')
    }
}

async function getLiveStatus() {
    const response = await fetch('/api/camera/status', {
        method: 'POST',
    });
    const data = await response.json();
    if (data.success && data.data && data.data.stream) {
        streamRunning = true;
        // Update UI to reflect running state
        const btn = document.getElementById('live_running');
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

async function capture() {
    try {
        const response = await fetch('/api/camera/capture', {
            method: 'POST',
        });

        if (response.ok) {
            streamRunning = true;
            console.log('Capture started successfully');
            return true;
        } else {
            const data = await response.json();
            alert('Failed to capture:', data.error);
            console.error('Failed to capture:', data.error);
            return false;
        }
    } catch (error) {
        console.error(error);
        alert(error);
        return false;
    }
}

// Live streaming
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
    const btn = document.getElementById('live_running');
    const active = btn.dataset.active === 'true';
    const feed = document.getElementById('feed');

    if (!active) {
        // Start the stream
        const success = await startStream();
        if (success) {
            btn.innerText = 'Stop Live';
            btn.dataset.active = 'true';
            feed.src = '/video_feed';
        }
    } else {
        // Stop the stream
        const success = await stopStream();
        if (success) {
            btn.innerText = 'Start Live';
            btn.dataset.active = 'false';
            feed.src = '/image_feed';
        }
    }
}

// Schedule Capture
async function startSchedule() {
    try {
        const response = await fetch('/api/camera/start_schedule', {
            method: 'POST',
        });

        if (response.ok) {
            scheduleRunning = true;
            console.log('Schedule started successfully');
            return true;
        } else {
            const data = await response.json();
            console.error('Failed to start schedule:', data.error);
            alert('Failed to start camera. Make sure camera is connected.');
            return false;
        }
    } catch (error) {
        console.error('Error starting schedule:', error);
        alert('Error starting camera');
        return false;
    }
}

async function stopSchedule() {
    try {
        const response = await fetch('/api/camera/stop_schedule', {
            method: 'POST',
        });

        if (response.ok) {
            scheduleRunning = false;
            console.log('Schedule stopped successfully');
            return true;
        } else {
            console.error('Failed to stop schedule');
            return false;
        }
    } catch (error) {
        console.error('Error stopping schedule:', error);
        return false;
    }
}

async function toggleSchedule() {
    const btn = document.getElementById('schedule_run');
    const active = btn.dataset.active === 'true';
    const feed = document.getElementById('feed');

    if (!active) {
        // Start the stream
        const success = await startSchedule();
        if (success) {
            btn.innerText = 'Stop Schedule';
            btn.dataset.active = 'true';
            feed.src = '/image_feed';
        }
    } else {
        // Stop the stream
        const success = await stopSchedule();
        if (success) {
            btn.innerText = 'Start Schedule';
            btn.dataset.active = 'false';
        }
    }
}

function populateDropdown(dropdown, configData) {
    // Clear existing options
    dropdown.innerHTML = '';

    // Add options from Choices array
    configData.Choices.forEach(choice => {
        const option = document.createElement('option');
        option.value = choice;
        option.textContent = choice;

        // Mark current value as selected
        if (choice === configData.Current) {
            option.selected = true;
        }

        dropdown.appendChild(option);
    });
}

async function applyCameraSetting(setting, value) {
    try {
        const response = await fetch('/api/camera/set_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                setting: setting,
                value: value
            })
        });

        if (response.ok) {
            console.log(`Set ${setting} to ${value}`);
        } else {
            const data = await response.json();
            console.error('Failed to set camera setting:', data.error);
            alert('Failed to update camera setting');
        }
    } catch (error) {
        console.error('Error setting camera config:', error);
        alert('Error updating camera setting');
    }
}

// Initialize feed when page loads
window.addEventListener('DOMContentLoaded', function() {
    loadTab()
    getLiveStatus()

    // Force feed refresh with timestamp to avoid caching
    const feed = document.getElementById('feed');
    if (feed && feed.src.includes('/image_feed')) {
        feed.src = '/image_feed?' + new Date().getTime();
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (captureRefreshInterval) {
        clearInterval(captureRefreshInterval);
    }
});
