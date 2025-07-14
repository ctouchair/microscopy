from flask import Flask, render_template, Response, jsonify, send_file, request, send_from_directory
from tqdm import tqdm
import time
import os
from picamera2 import Picamera2
from camera import VideoCamera
import multiprocessing
import cv2
import threading
from motor import motor
from PIL import Image
from flask_socketio import SocketIO, emit, send
import json
import numpy as np
import base64


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
pic_size = (int(3200), int(2400))  # 设置图像大小, width*height
video_size = (int(1200), int(900))  # 设置视频大小, width*height
cam0 = VideoCamera(Picamera2(), video_size)

motor0 = motor()
# 控制录像状态
is_recording = False
video_writer = None
is_veiwing = True # 控制摄像头是否在运行
move_task = False
recording_interval = 0  # 拍摄间隔时间（秒），0表示不进行间隔拍摄
interval_shooting = False  # 是否启用间隔拍摄

# 存储照片和录像的目录
SAVE_DIR = '/static'
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# 电机位置保存文件
MOTOR_POSITIONS_FILE = './motor_positions.json'

queues_dict = {
    'rgb': multiprocessing.Queue(),
    'frame_len': multiprocessing.Queue(),
}


# 开启摄像头
def generate_frames():
    global is_veiwing
    cam0.__stop__()
    time.sleep(1)
    cam0.camera_config()
    time.sleep(1)
    pbar = tqdm(total=0, dynamic_ncols=True)
    max_sharpness, z_pos_array, sharp_array = 0, [], []
    motor0.focus_get = False
    while is_veiwing := True:
        frame, rgb = cam0.get_frame()
        frame_sharpness = len(frame)
        if queues_dict['rgb'].empty():queues_dict['rgb'].put(rgb)
        if queues_dict['frame_len'].empty():queues_dict['frame_len'].put(frame_sharpness)
        if motor0.focus == True and motor0.direction == 'Z':  #开始对焦流程,直接找峰值，记录z和sharpness数组
            z_pos_array.append(motor0.z_pos)
            sharp_array.append(frame_sharpness)
            if frame_sharpness >= max_sharpness:
                max_sharpness = frame_sharpness
                motor0.focus_pos = motor0.z_pos
            # 峰值不能在边缘，第一次扫描结束
            if max_sharpness > 1.2*np.mean(sharp_array) and (min(z_pos_array)+100 < motor0.focus_pos < max(z_pos_array)-100) and motor0.focus_get == False:
                motor0.status, motor0.focus_get = False, True
                print(motor0.focus_pos, max_sharpness)
            # 第二次回扫，确定最终点,20 FPS有可能错过，主要是硬件光照灯不稳定，可能会有差别,如果判断不到则依赖局部最优
            if abs(frame_sharpness/max_sharpness-1) < 0.02 and motor0.focus_get:
                print('get best focus', frame_sharpness)
                motor0.focus, motor0.status, motor0.focus_get = False, False, False
                motor0.direction = ''  # Use empty string instead of None
        else:  # 退出对焦流程，重置
            max_sharpness, motor0.focus_get = 0, False
            z_pos_array, sharp_array = [], []
        
        # Send frame via SocketIO for real-time streaming
        try:
            # Convert frame to base64 for SocketIO transmission
            frame_base64 = base64.b64encode(frame).decode('utf-8')
            socketio.emit('video_frame', {'frame': frame_base64})
        except Exception as e:
            print(f"Error sending frame: {e}")
            
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        pbar.update(1)  # 更新进度条


# 录制视频
def record_video():
    global is_recording, video_writer, current_video_filename, recording_interval
    cam0.size = video_size
    rgb = queues_dict['rgb'].get()
    time.sleep(0.1)  # 等待队列中的数据稳定
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    current_video_filename = os.path.join(SAVE_DIR, f'{timestamp}.avi')
    video_writer = cv2.VideoWriter(current_video_filename, fourcc, 20, video_size, isColor=True)
    i = 0
    while is_recording:
        if recording_interval > 0:
            time.sleep(recording_interval)
        rgb = queues_dict['rgb'].get()
        if rgb is not None and i < 20*1000:
            bgr = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB, rgb)  # 写入图象时，会替换通道
            video_writer.write(bgr)
        else:
            is_recording = False
        i += 1
    video_writer.release()


def load_settings():
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
            cam0.exposure_time = int(settings['exposure_value']*1000)
            cam0.analogue_gain = settings['gain_value']
            cam0.r_gain = settings['r_value']
            cam0.b_gain = settings['b_value']
            motor0.led_cycle = int(settings['led_value'])
            motor0.set_led_power()
        return settings
    except FileNotFoundError:
        print("Settings file not found. Using default settings.")
        return {}  # 如果文件不存在，返回空字典或默认设置


def arctan_func(x, A, B, C, D):
    return A * np.arctan(B * x + C) + D

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Load motor positions and send initial settings to client
    motor_positions = load_motor_positions()
    settings = load_settings()
    x_vol = motor0.measure_voltage('X')
    motor0.x_pos = int(arctan_func(x_vol, 11.868, 2.776, -4.678, 0.282)*1024)

    # Combine settings with motor positions
    initial_data = {
        **settings,
        'x_pos': round(motor0.x_pos / 1024, 2),  # Convert steps to mm
        'y_pos': round(motor_positions['y_pos'] / 1024, 2),
        'z_pos': round(motor_positions['z_pos'] / 1024, 3)
    }
    emit('settings_update', initial_data)


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    global is_veiwing, is_recording, video_writer
    """断开连接时，停止所有功能"""
    is_veiwing = False
    is_recording = False
    if video_writer is not None:
        video_writer.release()
    cam0.__stop__() # 停止摄像头
    motor0.status = False
    motor0.led_cycle = 0
    emit('closed', {'status': 'success', 'message': 'System closed'})


@socketio.on('get_settings')
def handle_get_settings():
    settings = load_settings()
    emit('settings_update', settings)


@socketio.on('capture')
def handle_capture():
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    file_path = os.path.join(SAVE_DIR, f'{timestamp}.jpeg')
    cam0.size = pic_size
    rgb = queues_dict['rgb'].get()  # 确保队列中有数据
    time.sleep(0.1)  #释放掉旧的图片
    rgb = queues_dict['rgb'].get()  # 确保队列中有最新数据
    bgr = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB, rgb)  # 写入图象时，会替换通道
    cv2.imwrite(file_path, bgr)  # 保存图像文件
    cam0.size = video_size
    if os.path.exists(file_path):
        # Send file as base64
        with open(file_path, 'rb') as f:
            file_data = base64.b64encode(f.read()).decode('utf-8')
        emit('capture_response', {
            'success': True,
            'filename': f'{timestamp}.jpeg',
            'data': file_data
        })
    else:
        emit('capture_response', {'success': False, 'error': 'Failed to save image'})


@socketio.on('start_recording')
def handle_start_recording(data=None):
    global is_recording, recording_interval
    if not is_recording:
        # Get the current recording interval from frontend if provided
        if data and 'interval' in data:
            recording_interval = float(data['interval'])
        
        is_recording = True
        threading.Thread(target=record_video).start()
        
        # 如果设置了间隔录制，显示间隔信息
        if recording_interval > 0:
            interval_info = f"Recording started with interval frames every {recording_interval} seconds"
        else:
            interval_info = "Recording started"
            
        emit('recording_status', {'recording': True, 'message': interval_info, 'interval': recording_interval})
    else:
        emit('recording_status', {'recording': True, 'message': 'Recording already in progress'})


@socketio.on('stop_recording')
def handle_stop_recording():
    global is_recording, video_writer, current_video_filename
    if is_recording:
        is_recording = False
        
        if os.path.exists(current_video_filename):
            size = os.path.getsize(current_video_filename)
            print(current_video_filename, size)
            # Send file as base64
            with open(current_video_filename, 'rb') as f:
                file_data = base64.b64encode(f.read()).decode('utf-8')
            emit('recording_response', {
                'success': True,
                'filename': os.path.basename(current_video_filename),
                'data': file_data
            })
        else:
            emit('recording_response', {'success': False, 'error': 'No video file found'})
    else:
        emit('recording_response', {'success': False, 'error': 'Recording is not in progress'})


@socketio.on('stop_move')
def handle_stop_move():
    motor0.status = False
    motor0.direction = ''  # Use empty string instead of None
    motor0.focus = False
    emit('move_status', {'status': False, 'message': 'Moving stopped'})


@socketio.on('set_exposure')
def handle_set_exposure(data):
    try:
        exposure_time = int(data['value'])*1000
        cam0.exposure_time = exposure_time
        cam0.set_exposure()
        emit('exposure_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('exposure_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_gain')
def handle_set_gain(data):
    try:
        gain = int(float(data['value']))  # Convert to int
        cam0.analogue_gain = gain
        cam0.set_gain()
        emit('gain_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('gain_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_x_pos')
def handle_set_x_pos(data):
    try:
        xpos = float(data['value'])  #每移动1mm，相当于电机转1024步
        motor0.direction = 'X'
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
            xdelta_step = int(1024*xpos - motor0.x_pos)  # Convert to int
            motor0.status = True
            motor0.move(xdelta_step)
        else:
            motor0.status = True
            xdelta_step = int(1024*xpos - motor0.x_pos)  # Convert to int
            motor0.move(xdelta_step)
        emit('x_pos_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('x_pos_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_y_pos')
def handle_set_y_pos(data):
    try:
        ypos = float(data['value'])  #每移动1mm，相当于电机转1024步
        motor0.direction = 'Y'
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
            ydelta_step = int(1024*ypos - motor0.y_pos)  # Convert to int
            motor0.status = True
            motor0.move(ydelta_step)
        else:
            motor0.status = True
            ydelta_step = int(1024*ypos - motor0.y_pos)  # Convert to int
            motor0.move(ydelta_step)
        emit('y_pos_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('y_pos_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_z_pos')
def handle_set_z_pos(data):
    try:
        zpos = float(data['value'])  #每移动1mm，相当于电机转1024步
        motor0.direction, motor0.focus = 'Z', False
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
            zdelta_step = int(1024*zpos - motor0.z_pos)  # Convert to int
            motor0.status = True
            motor0.move(zdelta_step)
        else:
            motor0.status = True
            zdelta_step = int(1024*zpos - motor0.z_pos)  # Convert to int
            motor0.move(zdelta_step)
        emit('z_pos_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('z_pos_set', {'status': 'error', 'message': str(e)})


def focus_init():
    motor0.direction = 'Z'
    motor0.focus = False  # 开始对焦
    # 先扫描400步，看方向
    motor0.status = False
    time.sleep(0.01)


@socketio.on('fast_focus')
def handle_fast_focus():
    try:
        focus_init()
        motor0.focus = True  # 开始对焦， 同步开始记录最优值
        # 先扫描400步，看方向
        motor0.status = True
        _ = queues_dict['frame_len'].get()
        test_sharpness1  = queues_dict['frame_len'].get()
        motor0.move(400)
        _ = queues_dict['frame_len'].get()
        test_sharpness2  = queues_dict['frame_len'].get()
        if test_sharpness1 >= test_sharpness2:
            # 在当前位置的往小了走
            z_max, z_min = motor0.z_pos+100, motor0.z_pos-3000  #搜索范围2 mm
            # 直接平扫
            zdelta_step = z_max - motor0.z_pos
            motor0.status = True
            motor0.move(zdelta_step)
            zdelta_step = z_min - motor0.z_pos
            motor0.status = True
            motor0.move(zdelta_step) # 此时应该能覆盖最佳焦点，扫描结束
            time.sleep(0.01)
            step, iterations, phi, tolerance = 300, 0, 0.618, 1
            z_max, z_min = motor0.z_pos, motor0.z_pos+step
            while motor0.focus_get and iterations < 20 and z_max-z_min < tolerance:
                z1 = int(z_max - (z_max - z_min)*phi)
                z2 = int(z_min + (z_max - z_min)*phi)
                zdelta_step = z2 - motor0.z_pos
                motor0.status = True
                motor0.move(zdelta_step)
                _ = queues_dict['frame_len'].get()
                sharpness2  = queues_dict['frame_len'].get(block=True)
                if motor0.focus_get == True:
                    zdelta_step = z1 - motor0.z_pos
                    motor0.status = True
                    motor0.move(zdelta_step)
                    _ = queues_dict['frame_len'].get()
                    sharpness1  = queues_dict['frame_len'].get(block=True)
                    # 根据清晰度动态调整步长和搜索范围
                    if sharpness1 > sharpness2: #更新右端点
                        z_max = z2
                    else: #更新左端点
                        z_min = z1
                    iterations += 1
                print(z2, sharpness2)

        else: # 在当前位置的往大了走
            z_max, z_min = motor0.z_pos+3000, motor0.z_pos-500  #搜索范围2 mm
            # 直接平扫
            zdelta_step = z_min - motor0.z_pos
            motor0.status = True
            motor0.move(zdelta_step)
            zdelta_step = z_max - motor0.z_pos
            motor0.status = True
            motor0.move(zdelta_step) # 此时应该能覆盖最佳焦点，扫描结束
            time.sleep(0.01)
            step, iterations, phi, tolerance = -300, 0, 0.618, 1
            z_max, z_min = motor0.z_pos, motor0.z_pos+step
            while motor0.focus_get and iterations < 20 and z_max-z_min < tolerance:
                z1 = int(z_max - (z_max - z_min)*phi)
                z2 = int(z_min + (z_max - z_min)*phi)
                zdelta_step = z2 - motor0.z_pos
                motor0.status = True
                motor0.move(zdelta_step)
                _ = queues_dict['frame_len'].get()
                sharpness2  = queues_dict['frame_len'].get(block=True)
                zdelta_step = z1 - motor0.z_pos
                if motor0.focus_get == True:
                    motor0.status = True
                    motor0.move(zdelta_step)
                    _ = queues_dict['frame_len'].get()
                    sharpness1  = queues_dict['frame_len'].get(block=True)
                    # 根据清晰度动态调整步长和搜索范围
                    if sharpness1 > sharpness2: #更新右端点
                        z_max = z2
                    else: #更新左端点
                        z_min = z1
                    iterations += 1
                print(z2, sharpness2)
        motor0.focus, motor0.focus_get = False, False  # 对焦结束
        emit('focus_complete', {'status': 'success', 'position': motor0.z_pos/1024})
    except Exception as e:
        emit('focus_complete', {'status': 'error', 'message': str(e)})


@socketio.on('set_led')
def handle_set_led(data):
    try:
        motor0.led_cycle = int(data['value'])
        motor0.set_led_power()
        emit('led_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        print(f"LED setting error: {e}")
        emit('led_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_r_bal')
def handle_set_r_bal(data):
    try:
        r_value = float(data['value'])
        cam0.r_gain = r_value
        emit('r_bal_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('r_bal_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_b_bal')
def handle_set_b_bal(data):
    try:
        b_value = float(data['value'])
        cam0.b_gain = b_value
        emit('b_bal_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('b_bal_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_recording_delay')
def handle_set_recording_delay(data):
    global recording_interval
    try:
        recording_interval = float(data['value'])
        emit('recording_delay_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('recording_delay_set', {'status': 'error', 'message': str(e)})


@socketio.on('save_config')
def handle_save_config():
    try:
        settings = {
            'exposure_value': cam0.exposure_time/1000,
            'gain_value': cam0.analogue_gain,
            'led_value': motor0.led_cycle,
            'r_value': cam0.r_gain,
            'b_value': cam0.b_gain,
        }
        with open('settings.json', 'w') as f:
            json.dump(settings, f)
        emit('config_saved', {'status': 'success', 'message': 'Configuration saved'})
    except Exception as e:
        emit('config_saved', {'status': 'error', 'message': str(e)})


@socketio.on('close')
def handle_close():
    global is_veiwing, is_recording, video_writer
    """用户关闭网页时，停止所有功能"""
    is_veiwing = False
    is_recording = False
    if video_writer is not None:
        video_writer.release()
    cam0.__stop__() # 停止摄像头
    motor0.status = False
    emit('closed', {'status': 'success', 'message': 'System closed'})


# Keep some REST endpoints for backward compatibility and file serving
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    global is_veiwing
    is_veiwing = True  # 开始视频流
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings = load_settings()
    return jsonify(settings)


# Background thread to send motor position updates
def send_motor_positions():
    """Send motor positions every 200ms"""
    while True:
        try:
            # Convert steps to mm (1024 steps = 1mm)
            x_pos_mm = motor0.x_pos / 1024
            y_pos_mm = motor0.y_pos / 1024
            z_pos_mm = motor0.z_pos / 1024
            
            x_vol = motor0.measure_voltage('X')
            x_vol = round(arctan_func(x_vol, 11.868, 2.776, -4.678, 0.282),4)
            y_vol = motor0.measure_voltage('Y')
            z_vol = motor0.measure_voltage('Z')
            print(x_vol, y_vol, z_vol)

            socketio.emit('motor_positions', {
                'x_pos': round(x_pos_mm, 3),
                'y_pos': round(y_pos_mm, 3),
                'z_pos': round(z_pos_mm, 3),
                'motor_status': motor0.status,  # Add motor status for indicator
                'x_vol': x_vol,
                'y_vol': y_vol,
                'z_vol': z_vol
            })

        except Exception as e:
            print(f"Error sending motor positions: {e}")
        # 保存电机位置
        save_motor_positions()
        if motor0.status: #动态时，实时保存
            time.sleep(0.2)  # 200ms frequency
        else: #静态时，缓慢保存
            time.sleep(1)  # 200ms frequency


def save_motor_positions():
    """保存电机当前位置到JSON文件"""
    try:
        positions = {
            'x_pos': motor0.x_pos,
            'y_pos': motor0.y_pos,
            'z_pos': motor0.z_pos
        }
        with open(MOTOR_POSITIONS_FILE, 'w') as f:
            json.dump(positions, f)
    except Exception as e:
        print(f"Error saving motor positions: {e}")


def load_motor_positions():
    """从JSON文件加载电机位置"""
    try:
        with open(MOTOR_POSITIONS_FILE, 'r') as f:
            positions = json.load(f)
            motor0.x_pos = positions.get('x_pos', 0)
            motor0.y_pos = positions.get('y_pos', 0)
            motor0.z_pos = positions.get('z_pos', 0)
        print(f"Motor positions loaded: X={motor0.x_pos}, Y={motor0.y_pos}, Z={motor0.z_pos}")
        return positions
    except FileNotFoundError:
        print("Motor positions file not found. Using default positions (0,0,0).")
        return {'x_pos': 0, 'y_pos': 0, 'z_pos': 0}
    except Exception as e:
        print(f"Error loading motor positions: {e}")
        return {'x_pos': 0, 'y_pos': 0, 'z_pos': 0}


if __name__ == "__main__":
    # Load motor positions on startup
    load_motor_positions()
    
    # Start motor position update thread
    motor_position_thread = threading.Thread(target=send_motor_positions, daemon=True)
    motor_position_thread.start()
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
