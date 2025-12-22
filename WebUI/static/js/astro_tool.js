// Global state
let selectedStar = null;
let fwhmHistory = [];
let cameraRunning = false;
let chartCanvas = null;
let chartCtx = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    chartCanvas = document.getElementById('fwhmChart');
    chartCtx = chartCanvas.getContext('2d');

    // Set canvas size
    resizeChart();
    window.addEventListener('resize', resizeChart);

    // Setup event listeners
    document.getElementById('videoFrame').addEventListener('click', handleVideoClick);
    document.getElementById('startBtn').addEventListener('click', startCamera);
    document.getElementById('stopBtn').addEventListener('click', stopCamera);
    document.getElementById('resetBtn').addEventListener('click', resetMeasurement);

    // Setup tab switching
    initializeTabs();
    initializeVideoTabs();

    // Start polling for FWHM data
    setInterval(updateFwhmData, 100);

    // Check camera status
    checkCameraStatus();
});

function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function initializeVideoTabs() {
    const videoTabButtons = document.querySelectorAll('.video-tab-button');

    videoTabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-video-tab');
            switchVideoTab(tabName);
        });
    });
}

function switchVideoTab(tabName) {
    // Hide all video tab contents
    const videoTabContents = document.querySelectorAll('.video-tab-content');
    videoTabContents.forEach(content => {
        content.classList.remove('active');
    });

    // Remove active class from all video tab buttons
    const videoTabButtons = document.querySelectorAll('.video-tab-button');
    videoTabButtons.forEach(button => {
        button.classList.remove('active');
    });

    // Show selected video tab content
    const selectedTab = document.getElementById(tabName);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Activate selected button
    const selectedButton = document.querySelector(`[data-video-tab="${tabName}"]`);
    if (selectedButton) {
        selectedButton.classList.add('active');
    }
}

function switchTab(tabName) {
    // Hide all tab contents
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(content => {
        content.classList.remove('active');
    });

    // Remove active class from all buttons
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.classList.remove('active');
    });

    // Show selected tab content
    const selectedTab = document.getElementById(tabName);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Activate selected button
    const selectedButton = document.querySelector(`[data-tab="${tabName}"]`);
    if (selectedButton) {
        selectedButton.classList.add('active');
    }

    // Resize chart if switching to history tab
    if (tabName === 'history') {
        setTimeout(resizeChart, 100);
    }
}

function resizeChart() {
    const container = chartCanvas.parentElement;
    chartCanvas.width = container.clientWidth - 2;
    chartCanvas.height = 200;
    drawChart();
}

function handleVideoClick(event) {
    const rect = event.target.getBoundingClientRect();
    const x = Math.round((event.clientX - rect.left) * (event.target.naturalWidth / rect.width));
    const y = Math.round((event.clientY - rect.top) * (event.target.naturalHeight / rect.height));

    selectStar(x, y);
}

async function selectStar(x, y) {
    try {
        const response = await fetch('/api/select_star', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ x, y }),
        });

        if (response.ok) {
            selectedStar = { x, y };
            document.getElementById('starInfo').style.display = 'block';
            document.getElementById('starPos').textContent = `(${x}, ${y})`;
            fwhmHistory = [];
            drawChart();
        }
    } catch (error) {
        console.error('Error selecting star:', error);
    }
}

async function startCamera() {
    try {
        const response = await fetch('/api/camera/start', {
            method: 'POST',
        });

        if (response.ok) {
            cameraRunning = true;
            updateCameraUI();
        } else {
            alert('Failed to start camera. Make sure gphoto2 is installed and camera is connected.');
        }
    } catch (error) {
        console.error('Error starting camera:', error);
        alert('Error starting camera');
    }
}

async function stopCamera() {
    try {
        const response = await fetch('/api/camera/stop', {
            method: 'POST',
        });

        if (response.ok) {
            cameraRunning = false;
            updateCameraUI();
            resetMeasurement();
        }
    } catch (error) {
        console.error('Error stopping camera:', error);
    }
}

async function checkCameraStatus() {
    try {
        const response = await fetch('/api/camera/status');
        const data = await response.json();
        cameraRunning = data.running;
        updateCameraUI();
    } catch (error) {
        console.error('Error checking camera status:', error);
    }
}

function updateCameraUI() {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');

    if (cameraRunning) {
        statusDot.classList.add('connected');
        statusDot.classList.remove('disconnected');
        statusText.textContent = 'Connected';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        statusDot.classList.remove('connected');
        statusDot.classList.add('disconnected');
        statusText.textContent = 'Disconnected';
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

function resetMeasurement() {
    selectedStar = null;
    fwhmHistory = [];
    document.getElementById('fwhmValue').textContent = '--';
    document.getElementById('currentFwhm').textContent = '--';
    document.getElementById('bestFwhm').textContent = '--';
    document.getElementById('worstFwhm').textContent = '--';
    document.getElementById('sampleCount').textContent = '0';
    document.getElementById('starInfo').style.display = 'none';
    drawChart();
}

async function updateFwhmData() {
    if (!cameraRunning) return;

    try {
        const response = await fetch('/api/fwhm_data');
        const data = await response.json();

        if (data.current_fwhm !== null) {
            const fwhm = data.current_fwhm;
            document.getElementById('fwhmValue').textContent = fwhm.toFixed(2) + ' px';
            document.getElementById('currentFwhm').textContent = fwhm.toFixed(2);
        }

        if (data.fwhm_history && data.fwhm_history.length > 0) {
            fwhmHistory = data.fwhm_history;

            const best = Math.min(...fwhmHistory);
            const worst = Math.max(...fwhmHistory);

            document.getElementById('bestFwhm').textContent = best.toFixed(2);
            document.getElementById('worstFwhm').textContent = worst.toFixed(2);
            document.getElementById('sampleCount').textContent = fwhmHistory.length;

            drawChart();
        }
    } catch (error) {
        console.error('Error updating FWHM data:', error);
    }
}

function drawChart() {
    if (!chartCtx) return;

    const width = chartCanvas.width;
    const height = chartCanvas.height;

    // Clear canvas
    chartCtx.fillStyle = '#0a0a0a';
    chartCtx.fillRect(0, 0, width, height);

    if (fwhmHistory.length < 2) {
        chartCtx.fillStyle = '#666';
        chartCtx.font = '14px sans-serif';
        chartCtx.textAlign = 'center';
        chartCtx.fillText('No data yet', width / 2, height / 2);
        return;
    }

    // Draw grid
    chartCtx.strokeStyle = '#222';
    chartCtx.lineWidth = 1;
    for (let i = 1; i < 5; i++) {
        const y = (height / 5) * i;
        chartCtx.beginPath();
        chartCtx.moveTo(0, y);
        chartCtx.lineTo(width, y);
        chartCtx.stroke();
    }

    // Calculate scales
    const minFwhm = Math.min(...fwhmHistory);
    const maxFwhm = Math.max(...fwhmHistory);
    const range = maxFwhm - minFwhm;
    const padding = range * 0.1;

    // Draw FWHM line
    chartCtx.strokeStyle = '#4a9eff';
    chartCtx.lineWidth = 2;
    chartCtx.beginPath();

    fwhmHistory.forEach((fwhm, index) => {
        const x = (index / (fwhmHistory.length - 1)) * width;
        const normalizedFwhm = (fwhm - minFwhm + padding) / (range + 2 * padding);
        const y = height - (normalizedFwhm * (height - 20)) - 10;

        if (index === 0) {
            chartCtx.moveTo(x, y);
        } else {
            chartCtx.lineTo(x, y);
        }
    });

    chartCtx.stroke();

    // Draw labels
    chartCtx.fillStyle = '#4ade80';
    chartCtx.font = '12px sans-serif';
    chartCtx.textAlign = 'left';
    chartCtx.fillText(`Best: ${minFwhm.toFixed(2)}`, 5, height - 5);

    chartCtx.fillStyle = '#ff4a4a';
    chartCtx.textAlign = 'right';
    chartCtx.fillText(`Worst: ${maxFwhm.toFixed(2)}`, width - 5, 15);
}
