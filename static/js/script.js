
let isRecording = false;

// 切换录制状态
function toggleRecording() {
    if (isRecording) {
        fetch('/stop_recording').then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = 'video.avi';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
            });
        document.getElementById('recordBtn').innerText = '开始录制';
        document.getElementById('recordBtn').classList.remove('recording');
    } else {
        fetch('/start_recording');
        document.getElementById('recordBtn').innerText = '停止录制';
        document.getElementById('recordBtn').classList.add('recording');
    }
    isRecording = !isRecording;
}

// 截图并保存到浏览器
function captureScreenshot() {
    fetch('/capture').then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'photo.jpg'; // 文件名为screenshot.jpg
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        });
}

function fast_forcus() {
    fetch(`/fast_focus`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => console.log('Backend updated:', data.message))
        .catch(error => console.error('Error updating backend:', error));
}

function save_config() {
    fetch(`/save_config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => console.log('Backend updated:', data.message))
        .catch(error => console.error('Error updating backend:', error));
}


const x_pos_Slider = document.getElementById('x_pos');
const y_pos_Slider = document.getElementById('y_pos');
const z_pos_Slider = document.getElementById('z_pos');

const exposureSlider = document.getElementById('exposure');
const gainSlider = document.getElementById('gain');
const ledSlider = document.getElementById('led');

const rSlider = document.getElementById('r_bal');
const bSlider = document.getElementById('b_bal');


const x_pos_Value = document.getElementById('x_value');
const y_pos_Value = document.getElementById('y_value');
const z_pos_Value = document.getElementById('z_value');

const exposureValue = document.getElementById('exposure_value');
const gainValue = document.getElementById('gain_value');
const ledValue = document.getElementById('led_value');

const rValue = document.getElementById('r_value');
const bValue = document.getElementById('b_value');

// 函数：更新滑块当前值并发送到后端
function updateValueAndSend(slider, valueElement, endpoint, unit) {
    label = endpoint;
    // 如果label为'exposure'，改为"曝光时间"
    if (endpoint === 'exposure') {
        label = '曝光时间';
    }
    if (endpoint === 'gain') {
        label = 'ISO增益';
    }
    if (endpoint === 'led') {
        label = 'LED亮度';
    }
    if (endpoint === 'x_pos') {
        label = 'X位置';
    }
        if (endpoint === 'y_pos') {
        label = 'Y位置';
    }
        if (endpoint === 'z_pos') {
        label = 'Z位置';
    }
        if (endpoint === 'r_bal') {
        label = '白平衡红色增益';
    }
        if (endpoint === 'b_bal') {
        label = '白平衡蓝色增益';
    }

    // 更新页面显示值
    valueElement.textContent = `${label}：${slider.value}${unit}`;  // 添加单位

    // 立即发送请求到后端，周期0.2秒
    setTimeout(() => {
        fetch(`set_${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ value: slider.value })
        })
        .then(response => response.json())
        .then(data => console.log('Backend updated:', data.message))
        .catch(error => console.error('Error updating backend:', error));
    }, 200); // 每0.2秒更新一次
}


x_pos_Slider.addEventListener('input', () => updateValueAndSend(x_pos_Slider, x_pos_Value, 'x_pos', ' mm'));
y_pos_Slider.addEventListener('input', () => updateValueAndSend(y_pos_Slider, y_pos_Value, 'y_pos', ' mm'));
z_pos_Slider.addEventListener('input', () => updateValueAndSend(z_pos_Slider, z_pos_Value, 'z_pos', ' mm'));


// 曝光时间滑块更新
exposureSlider.addEventListener('input', () => updateValueAndSend(exposureSlider, exposureValue, 'exposure', ' ms'));

// ISO增益滑块更新
gainSlider.addEventListener('input', () => updateValueAndSend(gainSlider, gainValue, 'gain', ''));

// LED亮度滑块更新
ledSlider.addEventListener('input', () => updateValueAndSend(ledSlider, ledValue, 'led', ''));

// 白平衡增益滑块更新
rSlider.addEventListener('input', () => updateValueAndSend(rSlider, rValue, 'r_bal', ''));
bSlider.addEventListener('input', () => updateValueAndSend(bSlider, bValue, 'b_bal', ''));



window.onbeforeunload = function() {
  // 发送请求给后端，通知它停止相关的功能
  fetch('/close', { method: 'POST' });
};


async function fetchSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        
        // 使用获取的设置值初始化表单字段
        document.getElementById('exposure').value = settings.exposure_value;
        document.getElementById('exposure_value').textContent = `曝光时间：${settings.exposure_value} ms`;
        
        document.getElementById('gain').value = settings.gain_value;
        document.getElementById('gain_value').textContent = `ISO增益：${settings.gain_value}`;

        document.getElementById('led').value = settings.led_value;
        document.getElementById('led_value').textContent = `LED亮度：${settings.led_value}`;
        
        document.getElementById('r_bal').value = settings.r_value;
        document.getElementById('r_value').textContent = `白平衡红色增益：${settings.r_value}`;

        document.getElementById('b_bal').value = settings.b_value;
        document.getElementById('b_value').textContent = `白平衡蓝色增益：${settings.b_value}`;

    } catch (error) {
        console.error('Error fetching settings:', error);
    }
}

// 页面加载时初始化设置
window.onload = function () {
    fetchSettings();
};



// // 创建 EventSource 连接
// const eventSource = new EventSource('/events');

// // 监听状态更新事件
// eventSource.onmessage = function(event) {
//     const data = JSON.parse(event.data);  // 解析从服务器接收到的 JSON 数据
//     console.log('Received status:', data.status);
//     updateIndicatorColor('indicator', data.status);
// };


// // 更新指示灯颜色
// function updateIndicatorColor(indicatorId, status) {
//     const indicator = document.getElementById(indicatorId);
//     if (status) {
//         indicator.style.backgroundColor = "red";
//     } else {
//         indicator.style.backgroundColor = "green";
//     }
// }
