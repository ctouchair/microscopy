// SocketIO connection
const socket = io();

let isRecording = false;
let isRecordingCam1 = false;
let userModifyingPosition = false; // 跟踪用户是否正在修改位置
let logCollapsed = false; // 跟踪日志窗口是否收起
const maxLogMessages = 100; // 最大日志消息数量

// SocketIO event listeners
socket.on('connect', function() {
    console.log('Connected to server');
    addLogMessage('已连接到服务器', 'success');
    // Request initial settings
    socket.emit('get_settings');
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
    addLogMessage('与服务器连接断开', 'error');
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

// Video streaming for cam1
socket.on('video_frame_cam1', function(data) {
    const canvas = document.getElementById('videoCanvasCam1');
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
        addLogMessage(`拍照成功: ${data.filename}`, 'success');
    } else {
        console.error('Capture failed:', data.error);
        alert('拍照失败: ' + data.error);
        addLogMessage(`拍照失败: ${data.error}`, 'error');
    }
});

// Recording status
socket.on('recording_status', function(data) {
    console.log('Recording status:', data.message);
    addLogMessage(data.message, 'info');
    if (data.recording) {
        const intervalValue = document.getElementById('delay').value;
        if (intervalValue > 0) {
            document.getElementById('recordBtn').innerHTML = `<i class="fas fa-video"></i><br>显微录制中 (间隔${intervalValue}s)`;
        } else {
            document.getElementById('recordBtn').innerHTML = '<i class="fas fa-video"></i><br>显微录制中（点击停止）';
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
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
            // 通知后端删除本地视频文件
            socket.emit('delete_video', { filename: data.filename });
        }, 1000); // 1秒后删除链接并通知后端
    } else {
        console.error('Recording failed:', data.error);
        alert('录制失败: ' + data.error);
    }
    // Reset recording button
    document.getElementById('recordBtn').innerHTML = '<i class="fas fa-video"></i><br>显微录制';
    document.getElementById('recordBtn').classList.remove('recording');
    isRecording = false;
});

// Cam1 recording status
socket.on('recording_cam1_status', function(data) {
    if (data.recording) {
        addLogMessage(data.message, 'info');
    }
});

// Cam1 recording response
socket.on('recording_cam1_response', function(data) {
    if (data.success) {
        // Create download link for recorded video
        const link = document.createElement('a');
        link.href = 'data:video/avi;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
            // 通知后端删除本地视频文件
            socket.emit('delete_video', { filename: data.filename });
        }, 1000); // 1秒后删除链接并通知后端
        addLogMessage(`辅助摄像头录制成功: ${data.filename}`, 'success');
    } else {
        console.error('Cam1 recording failed:', data.error);
        alert('辅助摄像头录制失败: ' + data.error);
        addLogMessage(`辅助摄像头录制失败: ${data.error}`, 'error');
    }
    // Reset cam1 recording button
    document.getElementById('recordCam1Btn').innerHTML = '<i class="fas fa-video"></i><br>辅助录制';
    document.getElementById('recordCam1Btn').classList.remove('recording');
    isRecordingCam1 = false;
});

// Motion detection status
socket.on('motion_status', function(data) {
    if (data.motion_detected) {
        addLogMessage(`辅助摄像头检测到运动: ${data.ratio}%`, 'info');
    }
});

// Stitch status updates
socket.on('stitch_status', function(data) {
    if (data.status === 'started') {
        document.getElementById('stitch_images').innerHTML = '<i class="fas fa-puzzle-piece"></i><br>拼接中...';
        document.getElementById('stitch_images').disabled = true;
        addLogMessage(data.message, 'info');
        alert(data.message);
    }
});

// Stitch progress updates
socket.on('stitch_progress', function(data) {
    const progressText = `<i class="fas fa-puzzle-piece"></i><br>${data.current}/${data.total}`;
    document.getElementById('stitch_images').innerHTML = progressText;
    addLogMessage(data.message, 'info');
});

// Stitch images response
socket.on('stitch_response', function(data) {
    if (data.success) {
        // Create download link for stitched image
        const link = document.createElement('a');
        link.href = 'data:image/jpeg;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
        }, 1000);
        alert('图像拼接完成！');
    } else {
        console.error('Stitch failed:', data.error);
        alert('图像拼接失败: ' + data.error);
    }
    
    // Reset button state
    document.getElementById('stitch_images').innerHTML = '<i class="fas fa-puzzle-piece"></i><br>400%拼接';
    document.getElementById('stitch_images').disabled = false;
});

// Focus stack status updates
socket.on('focus_stack_status', function(data) {
    if (data.status === 'started') {
        document.getElementById('focus_stack').innerHTML = '<i class="fas fa-layer-group"></i><br>堆叠中...';
        document.getElementById('focus_stack').disabled = true;
        addLogMessage(data.message, 'info');
        alert(data.message);
    }
});

// Focus stack progress updates
socket.on('focus_stack_progress', function(data) {
    document.getElementById('focus_stack').innerHTML = `<i class="fas fa-layer-group"></i><br>堆叠中 ${data.current}/${data.total}`;
    addLogMessage(`景深堆叠进度: ${data.current}/${data.total}`, 'debug');
});

// Focus stack response
socket.on('focus_stack_response', function(data) {
    if (data.success) {
        // Create download link for focus stacked image
        const link = document.createElement('a');
        link.href = 'data:image/jpeg;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
        }, 1000);
        alert('景深堆叠完成！');
    } else {
        console.error('Focus stack failed:', data.error);
        alert('景深堆叠失败: ' + data.error);
    }
    
    // Reset button state
    document.getElementById('focus_stack').innerHTML = '<i class="fas fa-layer-group"></i><br>景深堆叠';
    document.getElementById('focus_stack').disabled = false;
});

// Calibration status updates
socket.on('calibration_status', function(data) {
    if (data.status === 'started') {
        document.getElementById('calibrate').innerHTML = '<i class="fas fa-ruler"></i><br>校准中...';
        document.getElementById('calibrate').disabled = true;
        alert(data.message);
    }
});

// Calibration response
socket.on('calibration_response', function(data) {
    if (data.success) {
        alert(`系统校准完成！\n像素尺寸: ${data.pixel_size.toFixed(4)} μm/pixel`);
    } else {
        console.error('Calibration failed:', data.error);
        alert('系统校准失败: ' + data.error);
    }
    
    // Reset button state
    document.getElementById('calibrate').innerHTML = '<i class="fas fa-ruler"></i><br>系统校准';
    document.getElementById('calibrate').disabled = false;
});

// Cell count status updates
socket.on('cell_count_status', function(data) {
    if (data.status === 'started') {
        document.getElementById('cell_count').innerHTML = '<i class="fas fa-microscope"></i><br>计数中...';
        document.getElementById('cell_count').disabled = true;
        addLogMessage(data.message, 'info');
        alert(data.message);
    }
});

// Cell count response
socket.on('cell_count_response', function(data) {
    if (data.success) {
        // Create download link for annotated image
        const link = document.createElement('a');
        link.href = 'data:image/jpeg;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
        }, 1000);
        alert(`细胞计数完成！\n检测到 ${data.cell_count} 个细胞\n平均直径: ${data.avg_diameter.toFixed(2)} μm`);
    } else {
        console.error('Cell count failed:', data.error);
        alert('细胞计数失败: ' + data.error);
    }
    
    // Reset button state
    document.getElementById('cell_count').innerHTML = '<i class="fas fa-microscope"></i><br>细胞计数';
    document.getElementById('cell_count').disabled = false;
});

// Auto brightness status updates
socket.on('auto_brightness_status', function(data) {
    if (data.status === 'started') {
        addLogMessage(data.message, 'info');
    }
});

// Auto brightness progress updates
socket.on('auto_brightness_progress', function(data) {
    document.getElementById('autoBrightnessBtn').innerHTML = `<i class="fas fa-lightbulb"></i><br>调节中 ${data.current}/${data.total}`;
    addLogMessage(`自动亮度调节进度: LED=${data.led_value}, 清晰度=${data.sharpness}`, 'debug');
});

// Auto brightness response
socket.on('auto_brightness_response', function(data) {
    if (data.success) {
        // Update LED slider to reflect the optimal value
        document.getElementById('led').value = data.optimal_led;
        document.getElementById('led_value').textContent = `LED亮度：${data.optimal_led}`;
        addLogMessage(`自动亮度调节完成！最佳LED亮度: ${data.optimal_led}, 最大清晰度: ${data.max_sharpness}`, 'success');
        alert(`自动亮度调节完成！\n最佳LED亮度: ${data.optimal_led}\n最大清晰度: ${data.max_sharpness}`);
    } else {
        console.error('Auto brightness failed:', data.error);
        addLogMessage(`自动亮度调节失败: ${data.error}`, 'error');
        alert('自动亮度调节失败: ' + data.error);
    }
    
    // Reset button state
    document.getElementById('autoBrightnessBtn').innerHTML = '<i class="fas fa-lightbulb"></i><br>自动亮度';
    document.getElementById('autoBrightnessBtn').disabled = false;
});

// 监听视频删除结果
socket.on('delete_video_response', function(data) {
    if (data.success) {
        console.log('本地视频已删除');
    } else {
        console.warn('删除视频失败:', data.error);
    }
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
    addLogMessage('系统已关闭', 'warning');
});

// 后端日志消息
socket.on('log_message', function(data) {
    addLogMessage(data.message, data.type || 'info');
});

// Motor position updates
socket.on('motor_positions', function(data) {
    document.getElementById('x_current').textContent = `当前位置：${data.x_pos} mm`;
    document.getElementById('y_current').textContent = `当前位置：${data.y_pos} mm`;
    document.getElementById('z_current').textContent = `当前位置：${data.z_pos} mm`;
    const indicator = document.getElementById('indicator');
    const indicatorText = document.getElementById('indicator-text');
    if (data.motor_status) {
        indicator.classList.add('moving');
        indicatorText.textContent = '停止运动';
    } else {
        indicator.classList.remove('moving');
        indicatorText.textContent = '静止';
    }
    // document.getElementById('x_volt').textContent = `电压：${data.x_vol.toFixed(3)} V`;
    // document.getElementById('y_volt').textContent = `电压：${data.y_vol.toFixed(3)} V`;
    // document.getElementById('z_volt').textContent = `电压：${data.z_vol.toFixed(3)} V`;

    // --- Chart update logic ---
    if (window.mainChart && window.timeLabels && window.xPosData && window.yPosData && window.zPosData && window.xVolData && window.yVolData && window.zVolData) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString();
        window.timeLabels.push(timeStr);
        window.xPosData.push(data.x_pos);
        window.yPosData.push(data.y_pos);
        window.zPosData.push(data.z_pos);
        window.xVolData.push(data.x_vol);
        window.yVolData.push(data.y_vol);
        window.zVolData.push(data.z_vol);
        // Keep only last maxDataPoints
        const maxDataPoints = 100;
        if (window.timeLabels.length > maxDataPoints) {
            window.timeLabels.shift();
            window.xPosData.shift();
            window.yPosData.shift();
            window.zPosData.shift();
            window.xVolData.shift();
            window.yVolData.shift();
            window.zVolData.shift();
        }
        window.mainChart.update();
    }
});

// Target positions update - 更新目标位置标签
socket.on('target_positions_update', function(data) {
    // 只有在用户没有主动修改位置时才更新目标位置
    if (!userModifyingPosition) {
        document.getElementById('x_value').textContent = `X目标位置：${data.x_target} mm`;
        document.getElementById('y_value').textContent = `Y目标位置：${data.y_target} mm`;
        document.getElementById('z_value').textContent = `Z目标位置：${data.z_target} mm`;
        
        // 同时更新滑块的值
        document.getElementById('x_pos').value = data.x_target;
        document.getElementById('y_pos').value = data.y_target;
        document.getElementById('z_pos').value = data.z_target;
    }
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
        // 更新按钮状态
        if (intervalValue > 0) {
            document.getElementById('recordBtn').innerHTML = `<i class="fas fa-video"></i><br>显微录制中 (间隔${intervalValue}s)`;
        } else {
            document.getElementById('recordBtn').innerHTML = '<i class="fas fa-video"></i><br>显微录制中（点击停止）';
        }
        document.getElementById('recordBtn').classList.add('recording');
    }
}

function toggleCam1Recording() {
    if (isRecordingCam1) {
        socket.emit('stop_recording_cam1');
    } else {
        socket.emit('start_recording_cam1');
        isRecordingCam1 = true;
        // 更新按钮状态
        document.getElementById('recordCam1Btn').innerHTML = '<i class="fas fa-video"></i><br>录制中（点击停止）';
        document.getElementById('recordCam1Btn').classList.add('recording');
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

function stitch_images() {
    socket.emit('stitch_images');
}

function focusStack() {
    socket.emit('focus_stack');
}

function calibrateSystem() {
    socket.emit('calibrate_system');
}

function cellCount() {
    socket.emit('cell_count');
}

// Auto brightness function
function autoBrightness() {
    const btn = document.getElementById('autoBrightnessBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><br>自动调节中...';
    
    socket.emit('auto_brightness');
    addLogMessage('开始自动亮度调节...', 'info');
}

// 日志管理函数
function addLogMessage(message, type = 'info') {
    const logContent = document.getElementById('logContent');
    const timestamp = new Date().toLocaleTimeString();
    
    const logMessage = document.createElement('div');
    logMessage.className = `log-message ${type}`;
    logMessage.innerHTML = `<span class="log-timestamp">[${timestamp}]</span>${message}`;
    
    logContent.appendChild(logMessage);
    
    // 限制日志消息数量
    const messages = logContent.querySelectorAll('.log-message');
    if (messages.length > maxLogMessages) {
        logContent.removeChild(messages[0]);
    }
    
    // 自动滚动到底部
    logContent.scrollTop = logContent.scrollHeight;
}

function clearLog() {
    const logContent = document.getElementById('logContent');
    logContent.innerHTML = '<div class="log-message welcome">日志已清空</div>';
}

function toggleLog() {
    const logContent = document.getElementById('logContent');
    const toggleBtn = document.getElementById('toggleLog');
    const toggleIcon = toggleBtn.querySelector('i');
    
    logCollapsed = !logCollapsed;
    
    if (logCollapsed) {
        logContent.classList.add('collapsed');
        toggleIcon.className = 'fas fa-chevron-down';
        toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i> 展开';
    } else {
        logContent.classList.remove('collapsed');
        toggleIcon.className = 'fas fa-chevron-up';
        toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i> 收起';
    }
}

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

    // 如果是位置相关的滑块，设置用户修改标志
    if (eventName.includes('_pos')) {
        userModifyingPosition = true;
        // 在发送完成后重置标志
        clearTimeout(slider.timeoutId);
        slider.timeoutId = setTimeout(() => {
            socket.emit(eventName, { value: slider.value });
            // 延迟重置标志，确保电机开始运动
            setTimeout(() => {
                userModifyingPosition = false;
            }, 1000); // 1秒后重置
        }, 200); // 200ms debounce
    } else {
        // 非位置相关的滑块，正常处理
        clearTimeout(slider.timeoutId);
        slider.timeoutId = setTimeout(() => {
            socket.emit(eventName, { value: slider.value });
        }, 200); // 200ms debounce
    }
}

// Handle page unload
window.onbeforeunload = function() {
    socket.emit('close');
};

// Add click handler to indicator and initialize all DOM elements
document.addEventListener('DOMContentLoaded', function() {
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

    // Add event listeners for sliders
    if (x_pos_Slider && x_pos_Value) {
        x_pos_Slider.addEventListener('input', () => updateValueAndSend(x_pos_Slider, x_pos_Value, 'set_x_pos', ' mm'));
    }
    if (y_pos_Slider && y_pos_Value) {
        y_pos_Slider.addEventListener('input', () => updateValueAndSend(y_pos_Slider, y_pos_Value, 'set_y_pos', ' mm'));
    }
    if (z_pos_Slider && z_pos_Value) {
        z_pos_Slider.addEventListener('input', () => updateValueAndSend(z_pos_Slider, z_pos_Value, 'set_z_pos', ' mm'));
    }

    if (exposureSlider && exposureValue) {
        exposureSlider.addEventListener('input', () => updateValueAndSend(exposureSlider, exposureValue, 'set_exposure', ' ms'));
    }
    if (gainSlider && gainValue) {
        gainSlider.addEventListener('input', () => updateValueAndSend(gainSlider, gainValue, 'set_gain', ''));
    }
    if (ledSlider && ledValue) {
        ledSlider.addEventListener('input', () => updateValueAndSend(ledSlider, ledValue, 'set_led', ''));
    }

    if (rSlider && rValue) {
        rSlider.addEventListener('input', () => updateValueAndSend(rSlider, rValue, 'set_r_bal', ''));
    }
    if (bSlider && bValue) {
        bSlider.addEventListener('input', () => updateValueAndSend(bSlider, bValue, 'set_b_bal', ''));
    }

    if (delaySlider && delayValue) {
        delaySlider.addEventListener('input', () => updateValueAndSend(delaySlider, delayValue, 'set_recording_delay', ' 秒'));
    }

    // Add click handler to indicator - 只用于显示状态，不触发功能
    const indicator = document.getElementById('indicator');
    if (indicator) {
        indicator.addEventListener('click', function() {
            // 点击indicator时停止电机运动
            socket.emit('stop_move');
        });
    }

    // Initialize chart controls
    const showX = document.getElementById('showX');
    const showY = document.getElementById('showY');
    const showZ = document.getElementById('showZ');

    if (showX) {
        showX.addEventListener('change', function() {
            setAxisVisibility('X', this.checked);
        });
    }
    if (showY) {
        showY.addEventListener('change', function() {
            setAxisVisibility('Y', this.checked);
        });
    }
    if (showZ) {
        showZ.addEventListener('change', function() {
            setAxisVisibility('Z', this.checked);
        });
    }

    // Initialize chart
    const ctx = document.getElementById('mainChart');
    if (ctx) {
        const chartCtx = ctx.getContext('2d');
        const maxDataPoints = 100;
        let timeLabels = [];
        let xPosData = [], yPosData = [], zPosData = [];
        let xVolData = [], yVolData = [], zVolData = [];

        const mainChart = new Chart(chartCtx, {
            type: 'line',
            data: {
                labels: timeLabels,
                datasets: [
                    // X
                    { label: 'X位置 (mm)', data: xPosData, borderColor: 'red', fill: false, yAxisID: 'y' },
                    { label: 'X估算 (mm)', data: xVolData, borderColor: 'rgba(255,0,0,0.5)', borderDash: [6,4], fill: false, yAxisID: 'y1' },
                    // Y
                    { label: 'Y位置 (mm)', data: yPosData, borderColor: 'green', fill: false, yAxisID: 'y' },
                    { label: 'Y估算 (mm)', data: yVolData, borderColor: 'rgba(0,128,0,0.5)', borderDash: [6,4], fill: false, yAxisID: 'y1' },
                    // Z
                    { label: 'Z位置 (mm)', data: zPosData, borderColor: 'blue', fill: false, yAxisID: 'y' },
                    { label: 'Z估算 (mm)', data: zVolData, borderColor: 'rgba(0,0,255,0.5)', borderDash: [6,4], fill: false, yAxisID: 'y1' }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
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
                        title: { display: true, text: '估算 (mm)' },
                        grid: { drawOnChartArea: false },
                        min: function(context) {
                            return context.chart.scales.y.min;
                        },
                        max: function(context) {
                            return context.chart.scales.y.max;
                        }
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

        // Make mainChart and setAxisVisibility available globally
        window.mainChart = mainChart;
        window.setAxisVisibility = setAxisVisibility;
        window.timeLabels = timeLabels;
        window.xPosData = xPosData;
        window.yPosData = yPosData;
        window.zPosData = zPosData;
        window.xVolData = xVolData;
        window.yVolData = yVolData;
        window.zVolData = zVolData;
    }
});

// WiFi设置功能
let currentWifiNetworks = [];

function openWifiModal() {
    document.getElementById('wifiModal').style.display = 'block';
    // 自动获取当前WiFi状态和扫描网络
    getCurrentWifiStatus();
    scanWifiNetworks();
}

function closeWifiModal() {
    document.getElementById('wifiModal').style.display = 'none';
}

function openWifiConnectModal(ssid, security) {
    document.getElementById('connectSSID').value = ssid;
    document.getElementById('connectPassword').value = '';
    document.getElementById('connectStatus').style.display = 'none';
    document.getElementById('wifiConnectModal').style.display = 'block';
}

function closeWifiConnectModal() {
    document.getElementById('wifiConnectModal').style.display = 'none';
}

function togglePasswordVisibility() {
    const passwordInput = document.getElementById('connectPassword');
    const toggleBtn = document.querySelector('.password-toggle i');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleBtn.className = 'fas fa-eye-slash';
    } else {
        passwordInput.type = 'password';
        toggleBtn.className = 'fas fa-eye';
    }
}

function getCurrentWifiStatus() {
    addLogMessage('获取当前WiFi状态...', 'info');
    
    socket.emit('get_wifi_status');
}

function scanWifiNetworks() {
    const scanBtn = document.getElementById('scanBtn');
    const wifiList = document.getElementById('wifiList');
    const scanIcon = scanBtn.querySelector('i');
    
    // 禁用扫描按钮并显示加载动画
    scanBtn.disabled = true;
    scanIcon.classList.add('rotating');
    wifiList.innerHTML = '<div class="loading">正在扫描WiFi网络...</div>';
    
    addLogMessage('开始扫描WiFi网络...', 'info');
    
    socket.emit('scan_wifi');
}

function connectToWifi() {
    const ssid = document.getElementById('connectSSID').value;
    const password = document.getElementById('connectPassword').value;
    const connectBtn = document.getElementById('connectBtn');
    const connectStatus = document.getElementById('connectStatus');
    
    if (!ssid) {
        showConnectStatus('请选择要连接的网络', 'error');
        return;
    }
    
    if (!password.trim()) {
        showConnectStatus('请输入WiFi密码', 'error');
        return;
    }
    
    // 禁用连接按钮
    connectBtn.disabled = true;
    connectBtn.innerHTML = '<i class="fas fa-spinner rotating"></i> 连接中...';
    
    showConnectStatus('正在连接到 ' + ssid + '...', 'info');
    addLogMessage(`尝试连接到WiFi网络: ${ssid}`, 'info');
    
    socket.emit('connect_wifi', {
        ssid: ssid,
        password: password
    });
}

function showConnectStatus(message, type) {
    const connectStatus = document.getElementById('connectStatus');
    connectStatus.textContent = message;
    connectStatus.className = `connect-status ${type}`;
    connectStatus.style.display = 'block';
}

function displayWifiNetworks(networks) {
    const wifiList = document.getElementById('wifiList');
    currentWifiNetworks = networks;
    
    if (!networks || networks.length === 0) {
        wifiList.innerHTML = '<div class="loading">未发现WiFi网络</div>';
        return;
    }
    
    let html = '';
    networks.forEach(network => {
        const signalClass = getSignalClass(network.signal);
        const securityIcon = network.security ? '<i class="fas fa-lock security-icon"></i>' : '<i class="fas fa-unlock-alt"></i>';
        
        html += `
            <div class="wifi-item" onclick="selectWifiNetwork('${network.ssid}', '${network.security}')">
                <div class="wifi-info">
                    <div class="wifi-ssid">
                        ${securityIcon}
                        ${network.ssid}
                    </div>
                    <div class="wifi-details">
                        ${network.security || '开放网络'} • 频道 ${network.channel || 'N/A'}
                    </div>
                </div>
                <div class="wifi-signal">
                    <i class="fas fa-wifi signal-strength ${signalClass}"></i>
                    <span class="signal-strength ${signalClass}">${network.signal}%</span>
                </div>
            </div>
        `;
    });
    
    wifiList.innerHTML = html;
}

function selectWifiNetwork(ssid, security) {
    if (security && security !== 'NONE') {
        openWifiConnectModal(ssid, security);
    } else {
        // 开放网络，直接连接
        addLogMessage(`连接到开放网络: ${ssid}`, 'info');
        socket.emit('connect_wifi', {
            ssid: ssid,
            password: ''
        });
    }
}

function getSignalClass(signal) {
    const signalNum = parseInt(signal);
    if (signalNum >= 70) return '';
    if (signalNum >= 40) return 'weak';
    return 'very-weak';
}

function updateWifiStatus(status) {
    document.getElementById('currentSSID').textContent = status.ssid || '未连接';
    document.getElementById('currentIP').textContent = status.ip || '无IP地址';
    document.getElementById('currentSignal').textContent = status.signal ? `${status.signal}%` : '无信号';
}

// WiFi相关Socket.IO事件监听
socket.on('wifi_status', function(data) {
    updateWifiStatus(data);
});

socket.on('wifi_scan_result', function(data) {
    const scanBtn = document.getElementById('scanBtn');
    const scanIcon = scanBtn.querySelector('i');
    
    // 恢复扫描按钮
    scanBtn.disabled = false;
    scanIcon.classList.remove('rotating');
    
    if (data.success) {
        displayWifiNetworks(data.networks);
        addLogMessage(`扫描完成，发现 ${data.networks.length} 个WiFi网络`, 'success');
    } else {
        document.getElementById('wifiList').innerHTML = '<div class="loading">扫描失败：' + (data.error || '未知错误') + '</div>';
        addLogMessage('WiFi扫描失败: ' + (data.error || '未知错误'), 'error');
    }
});

socket.on('wifi_connect_result', function(data) {
    const connectBtn = document.getElementById('connectBtn');
    
    // 恢复连接按钮
    connectBtn.disabled = false;
    connectBtn.innerHTML = '<i class="fas fa-wifi"></i> 连接';
    
    if (data.success) {
        showConnectStatus('连接成功！', 'success');
        addLogMessage(`WiFi连接成功: ${data.ssid}`, 'success');
        
        // 延迟关闭模态框并刷新状态
        setTimeout(() => {
            closeWifiConnectModal();
            getCurrentWifiStatus();
        }, 2000);
    } else {
        showConnectStatus('连接失败：' + (data.error || '未知错误'), 'error');
        addLogMessage(`WiFi连接失败: ${data.error || '未知错误'}`, 'error');
    }
});

// 点击模态框外部关闭
window.onclick = function(event) {
    const wifiModal = document.getElementById('wifiModal');
    const connectModal = document.getElementById('wifiConnectModal');
    
    if (event.target === wifiModal) {
        closeWifiModal();
    }
    if (event.target === connectModal) {
        closeWifiConnectModal();
    }
}
