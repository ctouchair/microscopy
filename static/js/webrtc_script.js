// SocketIO connection
const socket = io();

// WebRTC variables
let pc = null;
let localVideo = null;
let remoteVideo = null;
let isWebRTCConnected = false;

// Cam1 WebRTC variables
let pcCam1 = null;
let remoteVideoCam1 = null;
let isWebRTCCam1Connected = false;

// Recording state
let isRecording = false;
let isRecordingCam1 = false;
let userModifyingPosition = false;
let logCollapsed = false;
const maxLogMessages = 100;

// Initialize WebRTC
function initWebRTC() {
    localVideo = document.getElementById('webrtcVideo');
    remoteVideo = document.getElementById('webrtcVideo');  // 主摄像头视频元素
    remoteVideoCam1 = document.getElementById('webrtcVideoCam1');  // 辅助摄像头视频元素
}

// Start WebRTC connection
async function startWebRTC() {
    try {
        addLogMessage('正在建立WebRTC连接...', 'info');
        
        // Create RTCPeerConnection with optimized configuration for LAN
        pc = new RTCPeerConnection({
            iceServers: [
                // 局域网直连，移除STUN服务器以减少连接时间
            ],
            iceCandidatePoolSize: 0,  // 局域网不需要预收集ICE候选
            // 添加局域网优化配置
            bundlePolicy: 'max-bundle',
            rtcpMuxPolicy: 'require',
            iceTransportPolicy: 'all'
        });

        // Handle incoming video stream with optimization
        pc.ontrack = (event) => {
            console.log('Received remote stream');
            if (event.streams && event.streams[0]) {
                remoteVideo.srcObject = event.streams[0];
                // 优化视频播放参数
                remoteVideo.playsInline = true;
                remoteVideo.muted = true;
                remoteVideo.autoplay = true;
                // 减少播放延迟
                if (remoteVideo.setLatency) {
                    remoteVideo.setLatency(0.1); // 100ms延迟
                }
                addLogMessage('WebRTC视频流已连接', 'success');
                updateConnectionStatus('已连接');
            }
        };

        // Handle ICE candidates
        pc.onicecandidate = (event) => {
            if (event.candidate) {
                console.log('ICE candidate:', event.candidate);
            }
        };

        // Handle connection state changes
        pc.onconnectionstatechange = () => {
            console.log('Connection state:', pc.connectionState);
            updateConnectionStatus(pc.connectionState);
            
            if (pc.connectionState === 'connected') {
                addLogMessage('WebRTC连接建立成功', 'success');
                isWebRTCConnected = true;
                startVideoStats();
            } else if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
                addLogMessage('WebRTC连接失败或断开', 'error');
                isWebRTCConnected = false;
                stopVideoStats();
                // 自动重连
                setTimeout(() => {
                    if (!isWebRTCConnected) {
                        addLogMessage('尝试重新连接WebRTC...', 'info');
                        startWebRTC();
                    }
                }, 3000);
            }
        };

        // Create offer with optimized settings for high frame rate
        const offer = await pc.createOffer({
            offerToReceiveVideo: true,
            offerToReceiveAudio: false,
            // 局域网高质量视频配置
            voiceActivityDetection: false,
            iceRestart: false
        });
        
        await pc.setLocalDescription(offer);

        // Send offer to server
        const response = await fetch('/offer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sdp: pc.localDescription.sdp,
                type: pc.localDescription.type
            })
        });

        const answer = await response.json();
        
        // Set remote description
        await pc.setRemoteDescription(new RTCSessionDescription({
            sdp: answer.sdp,
            type: answer.type
        }));

        addLogMessage('WebRTC Offer/Answer交换完成', 'info');

    } catch (error) {
        console.error('WebRTC connection failed:', error);
        addLogMessage(`WebRTC连接失败: ${error.message}`, 'error');
        updateConnectionStatus('连接失败');
    }
}

// Stop WebRTC connection
async function stopWebRTC() {
    try {
        if (pc) {
            pc.close();
            pc = null;
        }
        
        if (remoteVideo) {
            remoteVideo.srcObject = null;
        }
        
        isWebRTCConnected = false;
        updateConnectionStatus('已断开');
        stopVideoStats();
        addLogMessage('WebRTC连接已关闭', 'info');
        
    } catch (error) {
        console.error('Error stopping WebRTC:', error);
        addLogMessage(`停止WebRTC时出错: ${error.message}`, 'error');
    }
}

// Update connection status display
function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connectionStatus');
    const statusMap = {
        'new': '新建连接',
        'connecting': '连接中',
        'connected': '已连接',
        'disconnected': '已断开',
        'failed': '连接失败',
        'closed': '已关闭'
    };
    
    statusElement.textContent = statusMap[status] || status;
    statusElement.className = `connection-status ${status}`;
}

// Video statistics monitoring
let statsInterval = null;

function startVideoStats() {
    if (statsInterval) clearInterval(statsInterval);
    
    let lastBytesReceived = 0;
    let lastTimestamp = Date.now();
    
    statsInterval = setInterval(async () => {
        if (pc && pc.connectionState === 'connected') {
            try {
                const stats = await pc.getStats();
                let videoStats = '';
                let detailedStats = {
                    fps: 0,
                    bitrate: 0,
                    resolution: '',
                    packetsLost: 0,
                    jitter: 0,
                    rtt: 0
                };
                
                stats.forEach(report => {
                    if (report.type === 'inbound-rtp' && report.mediaType === 'video') {
                        // 帧率统计
                        const fps = report.framesPerSecond || 0;
                        detailedStats.fps = fps;
                        
                        // 带宽计算（更精确的方法）
                        const currentTime = Date.now();
                        const timeDiff = (currentTime - lastTimestamp) / 1000;
                        if (timeDiff >= 1 && lastBytesReceived > 0) {
                            const bytesDiff = (report.bytesReceived || 0) - lastBytesReceived;
                            detailedStats.bitrate = Math.round((bytesDiff * 8) / (timeDiff * 1000)); // kbps
                            lastBytesReceived = report.bytesReceived || 0;
                            lastTimestamp = currentTime;
                        } else if (lastBytesReceived === 0) {
                            lastBytesReceived = report.bytesReceived || 0;
                            lastTimestamp = currentTime;
                        }
                        
                        // 分辨率信息
                        if (report.frameWidth && report.frameHeight) {
                            detailedStats.resolution = `${report.frameWidth}x${report.frameHeight}`;
                        }
                        
                        // 丢包统计
                        detailedStats.packetsLost = report.packetsLost || 0;
                        
                        // 抖动统计
                        detailedStats.jitter = report.jitter ? (report.jitter * 1000).toFixed(1) : 0;
                        
                        // 构建显示字符串
                        videoStats = `${fps.toFixed(1)} fps`;
                        if (detailedStats.bitrate > 0) {
                            videoStats += `, ${detailedStats.bitrate} kbps`;
                        }
                        if (detailedStats.resolution) {
                            videoStats += `, ${detailedStats.resolution}`;
                        }
                        if (detailedStats.packetsLost > 0) {
                            videoStats += `, 丢包: ${detailedStats.packetsLost}`;
                        }
                        if (detailedStats.jitter > 0) {
                            videoStats += `, 抖动: ${detailedStats.jitter}ms`;
                        }
                    }
                    
                    // RTT统计（往返时间）
                    if (report.type === 'candidate-pair' && report.state === 'succeeded') {
                        if (report.currentRoundTripTime) {
                            detailedStats.rtt = (report.currentRoundTripTime * 1000).toFixed(0);
                            if (!videoStats.includes('RTT')) {
                                videoStats += `, RTT: ${detailedStats.rtt}ms`;
                            }
                        }
                    }
                });
                
                document.getElementById('videoStats').textContent = videoStats;
                
                // 如果帧率低于预期，显示警告
                if (detailedStats.fps > 0 && detailedStats.fps < 25) {
                    document.getElementById('videoStats').style.color = 'orange';
                } else if (detailedStats.fps >= 25) {
                    document.getElementById('videoStats').style.color = 'green';
                } else {
                    document.getElementById('videoStats').style.color = 'white';
                }
                
            } catch (error) {
                console.error('Error getting stats:', error);
            }
        }
    }, 1000);
}

function stopVideoStats() {
    if (statsInterval) {
        clearInterval(statsInterval);
        statsInterval = null;
    }
    document.getElementById('videoStats').textContent = '';
}

// Start Cam1 WebRTC connection
async function startWebRTCCam1() {
    try {
        addLogMessage('正在建立辅助摄像头WebRTC连接...', 'info');
        
        // Create RTCPeerConnection for cam1 with optimized configuration
        pcCam1 = new RTCPeerConnection({
            iceServers: [
                // 局域网直连，移除STUN服务器
            ],
            iceCandidatePoolSize: 0,
            // 局域网优化配置
            bundlePolicy: 'max-bundle',
            rtcpMuxPolicy: 'require',
            iceTransportPolicy: 'all'
        });

        // Handle incoming video stream with optimization
        pcCam1.ontrack = (event) => {
            console.log('Received cam1 remote stream');
            if (event.streams && event.streams[0]) {
                remoteVideoCam1.srcObject = event.streams[0];
                // 优化视频播放参数
                remoteVideoCam1.playsInline = true;
                remoteVideoCam1.muted = true;
                remoteVideoCam1.autoplay = true;
                // 减少播放延迟
                if (remoteVideoCam1.setLatency) {
                    remoteVideoCam1.setLatency(0.1);
                }
                addLogMessage('辅助摄像头WebRTC视频流已连接', 'success');
                updateConnectionStatusCam1('已连接');
            }
        };

        // Handle ICE candidates
        pcCam1.onicecandidate = (event) => {
            if (event.candidate) {
                console.log('Cam1 ICE candidate:', event.candidate);
            }
        };

        // Handle connection state changes
        pcCam1.onconnectionstatechange = () => {
            console.log('Cam1 Connection state:', pcCam1.connectionState);
            updateConnectionStatusCam1(pcCam1.connectionState);
            
            if (pcCam1.connectionState === 'connected') {
                addLogMessage('辅助摄像头WebRTC连接建立成功', 'success');
                isWebRTCCam1Connected = true;
                startVideoStatsCam1();
            } else if (pcCam1.connectionState === 'failed' || pcCam1.connectionState === 'disconnected') {
                addLogMessage('辅助摄像头WebRTC连接失败或断开', 'error');
                isWebRTCCam1Connected = false;
                stopVideoStatsCam1();
                // 自动重连
                setTimeout(() => {
                    if (!isWebRTCCam1Connected) {
                        addLogMessage('尝试重新连接辅助摄像头WebRTC...', 'info');
                        startWebRTCCam1();
                    }
                }, 3000);
            }
        };

        // Create offer with optimized settings
        const offer = await pcCam1.createOffer({
            offerToReceiveVideo: true,
            offerToReceiveAudio: false,
            // 局域网高质量视频配置
            voiceActivityDetection: false,
            iceRestart: false
        });
        
        await pcCam1.setLocalDescription(offer);

        // Send offer to server for cam1
        const response = await fetch('/offer_cam1', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sdp: pcCam1.localDescription.sdp,
                type: pcCam1.localDescription.type
            })
        });

        const answer = await response.json();
        
        // Set remote description
        await pcCam1.setRemoteDescription(new RTCSessionDescription({
            sdp: answer.sdp,
            type: answer.type
        }));

        addLogMessage('辅助摄像头WebRTC Offer/Answer交换完成', 'info');

    } catch (error) {
        console.error('Cam1 WebRTC connection failed:', error);
        addLogMessage(`辅助摄像头WebRTC连接失败: ${error.message}`, 'error');
        updateConnectionStatusCam1('连接失败');
    }
}

// Stop Cam1 WebRTC connection
async function stopWebRTCCam1() {
    try {
        if (pcCam1) {
            pcCam1.close();
            pcCam1 = null;
        }
        
        if (remoteVideoCam1) {
            remoteVideoCam1.srcObject = null;
        }
        
        isWebRTCCam1Connected = false;
        updateConnectionStatusCam1('已断开');
        stopVideoStatsCam1();
        addLogMessage('辅助摄像头WebRTC连接已关闭', 'info');
        
    } catch (error) {
        console.error('Error stopping cam1 WebRTC:', error);
        addLogMessage(`停止辅助摄像头WebRTC时出错: ${error.message}`, 'error');
    }
}

// Update cam1 connection status display
function updateConnectionStatusCam1(status) {
    const statusElement = document.getElementById('connectionStatusCam1');
    const statusMap = {
        'new': '新建连接',
        'connecting': '连接中',
        'connected': '已连接',
        'disconnected': '已断开',
        'failed': '连接失败',
        'closed': '已关闭'
    };
    
    statusElement.textContent = statusMap[status] || status;
    statusElement.className = `connection-status ${status}`;
}

// Cam1 Video statistics monitoring
let statsIntervalCam1 = null;

function startVideoStatsCam1() {
    if (statsIntervalCam1) clearInterval(statsIntervalCam1);
    
    let lastBytesReceivedCam1 = 0;
    let lastTimestampCam1 = Date.now();
    
    statsIntervalCam1 = setInterval(async () => {
        if (pcCam1 && pcCam1.connectionState === 'connected') {
            try {
                const stats = await pcCam1.getStats();
                let videoStats = '';
                let detailedStats = {
                    fps: 0,
                    bitrate: 0,
                    resolution: '',
                    packetsLost: 0,
                    jitter: 0,
                    rtt: 0
                };
                
                stats.forEach(report => {
                    if (report.type === 'inbound-rtp' && report.mediaType === 'video') {
                        // 帧率统计
                        const fps = report.framesPerSecond || 0;
                        detailedStats.fps = fps;
                        
                        // 带宽计算
                        const currentTime = Date.now();
                        const timeDiff = (currentTime - lastTimestampCam1) / 1000;
                        if (timeDiff >= 1 && lastBytesReceivedCam1 > 0) {
                            const bytesDiff = (report.bytesReceived || 0) - lastBytesReceivedCam1;
                            detailedStats.bitrate = Math.round((bytesDiff * 8) / (timeDiff * 1000));
                            lastBytesReceivedCam1 = report.bytesReceived || 0;
                            lastTimestampCam1 = currentTime;
                        } else if (lastBytesReceivedCam1 === 0) {
                            lastBytesReceivedCam1 = report.bytesReceived || 0;
                            lastTimestampCam1 = currentTime;
                        }
                        
                        // 分辨率信息
                        if (report.frameWidth && report.frameHeight) {
                            detailedStats.resolution = `${report.frameWidth}x${report.frameHeight}`;
                        }
                        
                        // 丢包和抖动统计
                        detailedStats.packetsLost = report.packetsLost || 0;
                        detailedStats.jitter = report.jitter ? (report.jitter * 1000).toFixed(1) : 0;
                        
                        // 构建显示字符串
                        videoStats = `${fps.toFixed(1)} fps`;
                        if (detailedStats.bitrate > 0) {
                            videoStats += `, ${detailedStats.bitrate} kbps`;
                        }
                        if (detailedStats.resolution) {
                            videoStats += `, ${detailedStats.resolution}`;
                        }
                        if (detailedStats.packetsLost > 0) {
                            videoStats += `, 丢包: ${detailedStats.packetsLost}`;
                        }
                        if (detailedStats.jitter > 0) {
                            videoStats += `, 抖动: ${detailedStats.jitter}ms`;
                        }
                    }
                    
                    // RTT统计
                    if (report.type === 'candidate-pair' && report.state === 'succeeded') {
                        if (report.currentRoundTripTime) {
                            detailedStats.rtt = (report.currentRoundTripTime * 1000).toFixed(0);
                            if (!videoStats.includes('RTT')) {
                                videoStats += `, RTT: ${detailedStats.rtt}ms`;
                            }
                        }
                    }
                });
                
                document.getElementById('videoStatsCam1').textContent = videoStats;
                
                // 帧率颜色指示（辅助摄像头目标25fps）
                if (detailedStats.fps > 0 && detailedStats.fps < 20) {
                    document.getElementById('videoStatsCam1').style.color = 'orange';
                } else if (detailedStats.fps >= 20) {
                    document.getElementById('videoStatsCam1').style.color = 'green';
                } else {
                    document.getElementById('videoStatsCam1').style.color = 'white';
                }
                
            } catch (error) {
                console.error('Error getting cam1 stats:', error);
            }
        }
    }, 1000);
}

function stopVideoStatsCam1() {
    if (statsIntervalCam1) {
        clearInterval(statsIntervalCam1);
        statsIntervalCam1 = null;
    }
    document.getElementById('videoStatsCam1').textContent = '';
}

// SocketIO event listeners
socket.on('connect', function() {
    console.log('Connected to server');
    addLogMessage('已连接到服务器', 'success');
    socket.emit('get_settings');
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
    addLogMessage('与服务器连接断开', 'error');
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
        document.getElementById('r_bal_value').textContent = `白平衡红色增益：${settings.r_value}`;
    }
    if (settings.b_value !== undefined) {
        document.getElementById('b_bal').value = settings.b_value;
        document.getElementById('b_bal_value').textContent = `白平衡蓝色增益：${settings.b_value}`;
    }
    if (settings.x_pos !== undefined) {
        document.getElementById('x_pos').value = settings.x_pos;
        document.getElementById('x_pos_value').textContent = `X目标位置：${settings.x_pos.toFixed(2)} mm`;
        document.getElementById('x_current').textContent = `当前位置：${settings.x_pos.toFixed(3)} mm`;
    }
    if (settings.y_pos !== undefined) {
        document.getElementById('y_pos').value = settings.y_pos;
        document.getElementById('y_pos_value').textContent = `Y目标位置：${settings.y_pos.toFixed(2)} mm`;
        document.getElementById('y_current').textContent = `当前位置：${settings.y_pos.toFixed(3)} mm`;
    }
    if (settings.z_pos !== undefined) {
        document.getElementById('z_pos').value = settings.z_pos;
        document.getElementById('z_pos_value').textContent = `Z目标位置：${settings.z_pos.toFixed(3)} mm`;
        document.getElementById('z_current').textContent = `当前位置：${settings.z_pos.toFixed(3)} mm`;
    }
});

// Capture response
socket.on('capture_response', function(data) {
    if (data.success) {
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
        const link = document.createElement('a');
        link.href = 'data:video/avi;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
            socket.emit('delete_video', { filename: data.filename });
        }, 1000);
        addLogMessage(`显微录制成功: ${data.filename}`, 'success');
    } else {
        console.error('Recording failed:', data.error);
        alert('录制失败: ' + data.error);
        addLogMessage(`录制失败: ${data.error}`, 'error');
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
        const link = document.createElement('a');
        link.href = 'data:video/avi;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
            socket.emit('delete_video', { filename: data.filename });
        }, 1000);
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

// Stitch status updates
socket.on('stitch_status', function(data) {
    if (data.status === 'started') {
        document.getElementById('stitch_images').innerHTML = '<i class="fas fa-puzzle-piece"></i><br>拼接中...';
        document.getElementById('stitch_images').disabled = true;
        addLogMessage(data.message, 'info');
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
        const link = document.createElement('a');
        link.href = 'data:image/jpeg;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
        }, 1000);
        addLogMessage('图像拼接完成！', 'success');
    } else {
        console.error('Stitch failed:', data.error);
        addLogMessage('图像拼接失败: ' + data.error, 'error');
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
        const link = document.createElement('a');
        link.href = 'data:image/jpeg;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
        }, 1000);
        addLogMessage('景深堆叠完成！', 'success');
    } else {
        console.error('Focus stack failed:', data.error);
        addLogMessage('景深堆叠失败: ' + data.error, 'error');
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
        addLogMessage(data.message, 'info');
    }
});

// Calibration response
socket.on('calibration_response', function(data) {
    if (data.success) {
        addLogMessage(`系统校准完成 - 像素尺寸: ${data.pixel_size.toFixed(4)} μm/pixel`, 'success');
    } else {
        console.error('Calibration failed:', data.error);
        addLogMessage('系统校准失败: ' + data.error, 'error');
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
    }
});

// Cell count response
socket.on('cell_count_response', function(data) {
    if (data.success) {
        const link = document.createElement('a');
        link.href = 'data:image/jpeg;base64,' + data.data;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
        }, 1000);
        addLogMessage(`细胞计数完成 - 检测到 ${data.cell_count} 个细胞，平均直径: ${data.avg_diameter.toFixed(2)} μm`, 'success');
    } else {
        console.error('Cell count failed:', data.error);
        addLogMessage('细胞计数失败: ' + data.error, 'error');
    }
    
    // Reset button state
    document.getElementById('cell_count').innerHTML = '<i class="fas fa-microscope"></i><br>细胞计数';
    document.getElementById('cell_count').disabled = false;
});

// Focus complete
socket.on('focus_complete', function(data) {
    if (data.status === 'success') {
        addLogMessage(`对焦完成 - 位置: ${data.position.toFixed(3)} mm`, 'success');
    } else {
        addLogMessage(`对焦失败: ${data.message}`, 'error');
    }
});

// Config saved
socket.on('config_saved', function(data) {
    if (data.status === 'success') {
        addLogMessage('配置保存成功', 'success');
    } else {
        addLogMessage(`配置保存失败: ${data.message}`, 'error');
    }
});

// White balance responses
socket.on('r_bal_set', function(data) {
    if (data.status === 'success') {
        addLogMessage(`红色增益设置成功: ${data.value}`, 'debug');
    } else {
        addLogMessage(`红色增益设置失败: ${data.message}`, 'error');
    }
});

socket.on('b_bal_set', function(data) {
    if (data.status === 'success') {
        addLogMessage(`蓝色增益设置成功: ${data.value}`, 'debug');
    } else {
        addLogMessage(`蓝色增益设置失败: ${data.message}`, 'error');
    }
});

// Recording delay response
socket.on('recording_delay_set', function(data) {
    if (data.status === 'success') {
        addLogMessage(`录制间隔设置成功: ${data.value}秒`, 'debug');
    } else {
        addLogMessage(`录制间隔设置失败: ${data.message}`, 'error');
    }
});

// Move status (for stop move functionality)
socket.on('move_status', function(data) {
    if (data.status === false) {
        addLogMessage(data.message, 'info');
        // 更新indicator状态
        const indicator = document.getElementById('indicator');
        const indicatorText = document.getElementById('indicator-text');
        const indicatorIcon = document.getElementById('indicator-icon');
        
        if (indicator) {
            indicator.classList.remove('moving');
            indicatorText.textContent = '静止';
            indicatorIcon.className = 'fas fa-stop-circle';
            indicator.title = '电机已停止运动';
        }
    }
});

// Motor position updates
let motorStoppedTime = null;
let positionUpdateTimer = null;

socket.on('motor_positions', function(data) {
    // 始终更新当前位置显示
    document.getElementById('x_current').textContent = `当前位置：${data.x_pos} mm`;
    document.getElementById('y_current').textContent = `当前位置：${data.y_pos} mm`;
    document.getElementById('z_current').textContent = `当前位置：${data.z_pos} mm`;
    
    // Update indicator
    const indicator = document.getElementById('indicator');
    const indicatorText = document.getElementById('indicator-text');
    const indicatorIcon = document.getElementById('indicator-icon');
    
    if (data.motor_status) {
        // 电机运动中 - 目标位置保持在滑块设置的位置
        indicator.classList.add('moving');
        indicatorText.textContent = '停止运动';
        indicatorIcon.className = 'fas fa-hand-paper';
        indicator.title = '点击立即停止电机运动';
        
        // 清除静止计时器
        if (positionUpdateTimer) {
            clearTimeout(positionUpdateTimer);
            positionUpdateTimer = null;
        }
        motorStoppedTime = null;
    } else {
        // 电机静止
        indicator.classList.remove('moving');
        indicatorText.textContent = '静止';
        indicatorIcon.className = 'fas fa-stop-circle';
        indicator.title = '电机当前处于静止状态';
        
        // 记录停止时间
        if (motorStoppedTime === null) {
            motorStoppedTime = Date.now();
            
            // 设置1秒延时更新目标位置到当前位置
            if (positionUpdateTimer) {
                clearTimeout(positionUpdateTimer);
            }
            
            positionUpdateTimer = setTimeout(() => {
                // 1秒后且用户没有在修改位置时，将目标位置更新为当前位置
                if (!userModifyingPosition) {
                    document.getElementById('x_pos').value = data.x_pos;
                    document.getElementById('y_pos').value = data.y_pos;
                    document.getElementById('z_pos').value = data.z_pos;
                    
                    document.getElementById('x_pos_value').textContent = `X目标位置：${data.x_pos} mm`;
                    document.getElementById('y_pos_value').textContent = `Y目标位置：${data.y_pos} mm`;
                    document.getElementById('z_pos_value').textContent = `Z目标位置：${data.z_pos} mm`;
                }
                positionUpdateTimer = null;
            }, 1000);
        }
    }
    
    // 更新图表数据
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
        
        // 保持最多100个数据点
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
        document.getElementById('x_pos_value').textContent = `X目标位置：${data.x_target} mm`;
        document.getElementById('y_pos_value').textContent = `Y目标位置：${data.y_target} mm`;
        document.getElementById('z_pos_value').textContent = `Z目标位置：${data.z_target} mm`;
        
        // 同时更新滑块的值
        document.getElementById('x_pos').value = data.x_target;
        document.getElementById('y_pos').value = data.y_target;
        document.getElementById('z_pos').value = data.z_target;
    }
});

// Control functions
function captureScreenshot() {
    socket.emit('capture');
}

function toggleRecording() {
    if (isRecording) {
        socket.emit('stop_recording');
    } else {
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

function fast_forcus() {
    socket.emit('fast_focus');
    addLogMessage('开始快速对焦...', 'info');
}

function save_config() {
    socket.emit('save_config');
    addLogMessage('保存配置...', 'info');
}

function stitch_images() {
    socket.emit('stitch_images');
    addLogMessage('开始图像拼接...', 'info');
}

function focusStack() {
    socket.emit('focus_stack');
    addLogMessage('开始景深堆叠...', 'info');
}

function calibrateSystem() {
    socket.emit('calibrate_system');
    addLogMessage('开始系统校准...', 'info');
}

function cellCount() {
    socket.emit('cell_count');
    addLogMessage('开始细胞计数...', 'info');
}

// Log management functions
function addLogMessage(message, type = 'info') {
    const logContent = document.getElementById('logContent');
    const timestamp = new Date().toLocaleTimeString();
    
    const logMessage = document.createElement('div');
    logMessage.className = `log-message ${type}`;
    logMessage.innerHTML = `<span class="log-timestamp">[${timestamp}]</span>${message}`;
    
    logContent.appendChild(logMessage);
    
    const messages = logContent.querySelectorAll('.log-message');
    if (messages.length > maxLogMessages) {
        logContent.removeChild(messages[0]);
    }
    
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

// Slider control functions
function updateValueAndSend(slider, valueElement, eventName, unit) {
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
    
    const label = labelMap[eventName] || eventName;
    valueElement.textContent = `${label}：${slider.value} ${unit}`;
    
    socket.emit(eventName, { value: slider.value });
}

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    initWebRTC();
    
    // Setup sliders
    const sliders = [
        { id: 'exposure', event: 'set_exposure', unit: 'ms' },
        { id: 'gain', event: 'set_gain', unit: '' },
        { id: 'led', event: 'set_led', unit: '' },
        { id: 'x_pos', event: 'set_x_pos', unit: 'mm' },
        { id: 'y_pos', event: 'set_y_pos', unit: 'mm' },
        { id: 'z_pos', event: 'set_z_pos', unit: 'mm' },
        { id: 'r_bal', event: 'set_r_bal', unit: '' },
        { id: 'b_bal', event: 'set_b_bal', unit: '' },
        { id: 'delay', event: 'set_recording_delay', unit: '秒' }
    ];
    
    sliders.forEach(slider => {
        const element = document.getElementById(slider.id);
        const valueElement = document.getElementById(slider.id + '_value');
        
        if (element && valueElement) {
            element.addEventListener('input', function() {
                userModifyingPosition = (slider.event.includes('pos'));
                updateValueAndSend(element, valueElement, slider.event, slider.unit);
                
                // 如果是位置滑块，清除自动更新计时器
                if (slider.event.includes('pos') && positionUpdateTimer) {
                    clearTimeout(positionUpdateTimer);
                    positionUpdateTimer = null;
                }
            });
            
            element.addEventListener('change', function() {
                // 延长用户修改标志，确保在用户操作后有足够时间完成
                if (slider.event.includes('pos')) {
                    setTimeout(() => { userModifyingPosition = false; }, 500);
                } else {
                    setTimeout(() => { userModifyingPosition = false; }, 100);
                }
            });
        }
    });
    
    // Add click handler to indicator for stopping motor movement
    const indicator = document.getElementById('indicator');
    if (indicator) {
        // 初始化title
        indicator.title = '电机当前处于静止状态';
        
        indicator.addEventListener('click', function() {
            // 点击indicator时停止电机运动
            if (indicator.classList.contains('moving')) {
                socket.emit('stop_move');
                addLogMessage('用户手动停止电机运动', 'info');
            }
        });
    }
    
    // Initialize chart controls
    const showX = document.getElementById('showX');
    const showY = document.getElementById('showY');
    const showZ = document.getElementById('showZ');
    
    if (showX && showY && showZ) {
        showX.addEventListener('change', function() {
            setAxisVisibility('X', this.checked);
        });
        showY.addEventListener('change', function() {
            setAxisVisibility('Y', this.checked);
        });
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
    
    // Auto-start WebRTC connections
    setTimeout(() => {
        addLogMessage('自动启动WebRTC连接...', 'info');
        startWebRTC();
        // 延迟启动辅助摄像头，避免同时连接冲突
        setTimeout(() => {
            startWebRTCCam1();
        }, 2000);
    }, 1000);
}); 