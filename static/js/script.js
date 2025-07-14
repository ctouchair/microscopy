// SocketIO connection
const socket = io();

let isRecording = false;

// SocketIO event listeners
socket.on('connect', function() {
    console.log('Connected to server');
    // Request initial settings
    socket.emit('get_settings');
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
});

// Video streaming
socket.on('video_frame', function(data) {
    const canvas = document.getElementById('videoCanvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    img.onload = function() {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    };
    
    img.src = 'data:image/jpeg;base64,' + data.frame;
});

// Settings update
socket.on('settings_update', function(settings) {
    console.log('Received settings_update:', settings);
    if (settings.exposure_value !== undefined) {
        document.getElementById('exposure').value = settings.exposure_value;
        document.getElementById('exposure_value').textContent = `曝光时间：${settings.exposure_value} ms`;
    }
    if (settings.gain_value !== undefined) {
        document.getElementById('gain').value = settings.gain_value;
        document.getElementById('gain_value').textContent = `ISO增益：${settings.gain_value}`;
    }
    if (settings.led_value !== undefined) {
        document.getElementById('led').value = settings.led_value;
        document.getElementById('led_value').textContent = `LED亮度：${settings.led_value}`;
    }
    if (settings.r_value !== undefined) {
        document.getElementById('r_bal').value = settings.r_value;
        document.getElementById('r_value').textContent = `白平衡红色增益：${settings.r_value}`;
    }
    if (settings.b_value !== undefined) {
        document.getElementById('b_bal').value = settings.b_value;
        document.getElementById('b_value').textContent = `白平衡蓝色增益：${settings.b_value}`;
    }
    if (settings.x_pos !== undefined) {
        document.getElementById('x_pos').value = settings.x_pos;
        document.getElementById('x_value').textContent = `X目标位置：${settings.x_pos} mm`;
        document.getElementById('x_current').textContent = `当前位置：${settings.x_pos} mm`;
    }
    if (settings.y_pos !== undefined) {
        document.getElementById('y_pos').value = settings.y_pos;
        document.getElementById('y_value').textContent = `Y目标位置：${settings.y_pos} mm`;
        document.getElementById('y_current').textContent = `当前位置：${settings.y_pos} mm`;
    }
    if (settings.z_pos !== undefined) {
        document.getElementById('z_pos').value = settings.z_pos;
        document.getElementById('z_value').textContent = `Z目标位置：${settings.z_pos} mm`;
        document.getElementById('z_current').textContent = `当前位置：${settings.z_pos} mm`;
    }
});

// Capture response
socket.on('capture_response', function(data) {
    if (data.success) {
        // Create download link for captured image
        const link = document.createElement('a');
        link.href = 'data:image/jpeg;base64,' + data.data;
        link.download = data.filename;
        link.click();
    } else {
        console.error('Capture failed:', data.error);
        alert('拍照失败: ' + data.error);
    }
});

// Recording status
socket.on('recording_status', function(data) {
    console.log('Recording status:', data.message);
    if (data.recording) {
        const intervalValue = document.getElementById('delay').value;
        if (intervalValue > 0) {
            document.getElementById('recordBtn').innerText = `录制中 (间隔${intervalValue}s)`;
        } else {
            document.getElementById('recordBtn').innerText = '录制中（点击停止）';
        }
        document.getElementById('recordBtn').classList.add('recording');
    }
});

// Recording response
socket.on('recording_response', function(data) {
    if (data.success) {
        // Create download link for recorded video
        const link = document.createElement('a');
        link.href = 'data:video/avi;base64,' + data.data;
        link.download = data.filename;
        link.click();
    } else {
        console.error('Recording failed:', data.error);
        alert('录制失败: ' + data.error);
    }
    
    // Reset recording button
    document.getElementById('recordBtn').innerText = '开始录制';
    document.getElementById('recordBtn').classList.remove('recording');
    isRecording = false;
});

// Move status
socket.on('move_status', function(data) {
    console.log('Move status:', data.message);
});

// Focus complete
socket.on('focus_complete', function(data) {
    if (data.status === 'success') {
        console.log('Focus completed at position:', data.position);
        alert(`对焦完成，位置: ${data.position.toFixed(3)} mm`);
    } else {
        console.error('Focus failed:', data.message);
        alert('对焦失败: ' + data.message);
    }
});

// Configuration saved
socket.on('config_saved', function(data) {
    if (data.status === 'success') {
        console.log('Configuration saved');
        alert('设置已保存');
    } else {
        console.error('Save failed:', data.message);
        alert('保存失败: ' + data.message);
    }
});

// System closed
socket.on('closed', function(data) {
    console.log('System closed:', data.message);
});

// Motor position updates
socket.on('motor_positions', function(data) {
    document.getElementById('x_current').textContent = `当前位置：${data.x_pos} mm`;
    document.getElementById('y_current').textContent = `当前位置：${data.y_pos} mm`;
    document.getElementById('z_current').textContent = `当前位置：${data.z_pos} mm`;
    const indicator = document.getElementById('indicator');
    if (data.motor_status) {
        indicator.classList.add('moving');
    } else {
        indicator.classList.remove('moving');
    }
    // document.getElementById('x_volt').textContent = `电压：${data.x_vol.toFixed(3)} V`;
    // document.getElementById('y_volt').textContent = `电压：${data.y_vol.toFixed(3)} V`;
    // document.getElementById('z_volt').textContent = `电压：${data.z_vol.toFixed(3)} V`;

    // --- Chart update logic ---
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    timeLabels.push(timeStr);
    xPosData.push(data.x_pos);
    yPosData.push(data.y_pos);
    zPosData.push(data.z_pos);
    xVolData.push(data.x_vol);
    yVolData.push(data.y_vol);
    zVolData.push(data.z_vol);
    // Keep only last maxDataPoints
    const maxDataPoints = 100;
    if (timeLabels.length > maxDataPoints) {
        timeLabels.shift();
        xPosData.shift();
        yPosData.shift();
        zPosData.shift();
        xVolData.shift();
        yVolData.shift();
        zVolData.shift();
    }
    mainChart.update();
});

// Control function responses
socket.on('exposure_set', function(data) {
    if (data.status === 'error') {
        console.error('Exposure set failed:', data.message);
    }
});

socket.on('gain_set', function(data) {
    if (data.status === 'error') {
        console.error('Gain set failed:', data.message);
    }
});

socket.on('x_pos_set', function(data) {
    if (data.status === 'error') {
        console.error('X position set failed:', data.message);
    }
});

socket.on('y_pos_set', function(data) {
    if (data.status === 'error') {
        console.error('Y position set failed:', data.message);
    }
});

socket.on('z_pos_set', function(data) {
    if (data.status === 'error') {
        console.error('Z position set failed:', data.message);
    }
});

socket.on('led_set', function(data) {
    if (data.status === 'error') {
        console.error('LED set failed:', data.message);
    }
});

socket.on('r_bal_set', function(data) {
    if (data.status === 'error') {
        console.error('R balance set failed:', data.message);
    }
});

socket.on('b_bal_set', function(data) {
    if (data.status === 'error') {
        console.error('B balance set failed:', data.message);
    }
});

socket.on('recording_delay_set', function(data) {
    if (data.status === 'error') {
        console.error('Recording delay set failed:', data.message);
    }
});

// Control functions
function toggleRecording() {
    if (isRecording) {
        socket.emit('stop_recording');
    } else {
        // Get current interval value from slider
        const intervalValue = document.getElementById('delay').value;
        socket.emit('start_recording', { interval: parseFloat(intervalValue) });
        isRecording = true;
    }
}

function captureScreenshot() {
    socket.emit('capture');
}

function fast_forcus() {
    socket.emit('fast_focus');
}

function save_config() {
    socket.emit('save_config');
}

function stop_move() {
    socket.emit('stop_move');
}

// Get DOM elements
const x_pos_Slider = document.getElementById('x_pos');
const y_pos_Slider = document.getElementById('y_pos');
const z_pos_Slider = document.getElementById('z_pos');

const exposureSlider = document.getElementById('exposure');
const gainSlider = document.getElementById('gain');
const ledSlider = document.getElementById('led');

const rSlider = document.getElementById('r_bal');
const bSlider = document.getElementById('b_bal');

const delaySlider = document.getElementById('delay');

const x_pos_Value = document.getElementById('x_value');
const y_pos_Value = document.getElementById('y_value');
const z_pos_Value = document.getElementById('z_value');

const exposureValue = document.getElementById('exposure_value');
const gainValue = document.getElementById('gain_value');
const ledValue = document.getElementById('led_value');

const rValue = document.getElementById('r_value');
const bValue = document.getElementById('b_value');

const delayValue = document.getElementById('delay_value');

// Function to update slider value and send via SocketIO
function updateValueAndSend(slider, valueElement, eventName, unit) {
    let label = eventName;
    
    // Map event names to Chinese labels
    const labelMap = {
        'set_exposure': '曝光时间',
        'set_gain': 'ISO增益',
        'set_led': 'LED亮度',
        'set_x_pos': 'X目标位置',
        'set_y_pos': 'Y目标位置',
        'set_z_pos': 'Z目标位置',
        'set_r_bal': '白平衡红色增益',
        'set_b_bal': '白平衡蓝色增益',
        'set_recording_delay': '间隔录制'
    };
    
    label = labelMap[eventName] || eventName;

    // Update display value
    valueElement.textContent = `${label}：${slider.value}${unit}`;

    // Send via SocketIO with debouncing
    clearTimeout(slider.timeoutId);
    slider.timeoutId = setTimeout(() => {
        socket.emit(eventName, { value: slider.value });
    }, 200); // 200ms debounce
}

// Add event listeners for sliders
x_pos_Slider.addEventListener('input', () => updateValueAndSend(x_pos_Slider, x_pos_Value, 'set_x_pos', ' mm'));
y_pos_Slider.addEventListener('input', () => updateValueAndSend(y_pos_Slider, y_pos_Value, 'set_y_pos', ' mm'));
z_pos_Slider.addEventListener('input', () => updateValueAndSend(z_pos_Slider, z_pos_Value, 'set_z_pos', ' mm'));

exposureSlider.addEventListener('input', () => updateValueAndSend(exposureSlider, exposureValue, 'set_exposure', ' ms'));
gainSlider.addEventListener('input', () => updateValueAndSend(gainSlider, gainValue, 'set_gain', ''));
ledSlider.addEventListener('input', () => updateValueAndSend(ledSlider, ledValue, 'set_led', ''));

rSlider.addEventListener('input', () => updateValueAndSend(rSlider, rValue, 'set_r_bal', ''));
bSlider.addEventListener('input', () => updateValueAndSend(bSlider, bValue, 'set_b_bal', ''));

delaySlider.addEventListener('input', () => updateValueAndSend(delaySlider, delayValue, 'set_recording_delay', ' 秒'));

// Handle page unload
window.onbeforeunload = function() {
    socket.emit('close');
};

// Add click handler to indicator
document.addEventListener('DOMContentLoaded', function() {
    const indicator = document.getElementById('indicator');
    if (indicator) {
        indicator.addEventListener('click', function() {
            stop_move();
        });
    }
});

// --- Chart.js setup for dual y-axes ---
const ctx = document.getElementById('mainChart').getContext('2d');
const maxDataPoints = 100;
let timeLabels = [];
let xPosData = [], yPosData = [], zPosData = [];
let xVolData = [], yVolData = [], zVolData = [];

const mainChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: timeLabels,
        datasets: [
            // X
            { label: 'X位置 (mm)', data: xPosData, borderColor: 'red', fill: false, yAxisID: 'y' },
            { label: 'X电压 (V)', data: xVolData, borderColor: 'rgba(255,0,0,0.5)', borderDash: [6,4], fill: false, yAxisID: 'y1' },
            // Y
            { label: 'Y位置 (mm)', data: yPosData, borderColor: 'green', fill: false, yAxisID: 'y' },
            { label: 'Y电压 (V)', data: yVolData, borderColor: 'rgba(0,128,0,0.5)', borderDash: [6,4], fill: false, yAxisID: 'y1' },
            // Z
            { label: 'Z位置 (mm)', data: zPosData, borderColor: 'blue', fill: false, yAxisID: 'y' },
            { label: 'Z电压 (V)', data: zVolData, borderColor: 'rgba(0,0,255,0.5)', borderDash: [6,4], fill: false, yAxisID: 'y1' }
        ]
    },
    options: {
        responsive: false,
        animation: false,
        scales: {
            x: { title: { display: true, text: '时间' } },
            y: {
                type: 'linear',
                position: 'left',
                title: { display: true, text: '位置 (mm)' }
            },
            y1: {
                type: 'linear',
                position: 'right',
                title: { display: true, text: '电压 (V)' },
                grid: { drawOnChartArea: false }
            }
        }
    }
});

// Map: axis -> [position dataset index, voltage dataset index]
const axisDatasetMap = {
    X: [0, 1],
    Y: [2, 3],
    Z: [4, 5]
};

function setAxisVisibility(axis, visible) {
    axisDatasetMap[axis].forEach(idx => {
        mainChart.getDatasetMeta(idx).hidden = !visible;
    });
    mainChart.update();
}

document.getElementById('showX').addEventListener('change', function() {
    setAxisVisibility('X', this.checked);
});
document.getElementById('showY').addEventListener('change', function() {
    setAxisVisibility('Y', this.checked);
});
document.getElementById('showZ').addEventListener('change', function() {
    setAxisVisibility('Z', this.checked);
});
