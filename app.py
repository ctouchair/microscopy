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
from gpiozero import PWMLED
from PIL import Image
from flask_socketio import SocketIO, send
import json


app = Flask(__name__)
socketio = SocketIO(app)
pic_size = (int(3200), int(2400))  # 设置图像大小, width*height
video_size = (int(1200), int(900))  # 设置视频大小, width*height
cam0 = VideoCamera(Picamera2(), video_size)
motor0 = motor()
# 控制录像状态
is_recording = False
video_writer = None
is_veiwing = True # 控制摄像头是否在运行
led = PWMLED(18)
move_task = False

# 存储照片和录像的目录
SAVE_DIR = '/static'
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

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
    max_sharpness = 0
    while is_veiwing := True:
        frame, rgb = cam0.get_frame()
        frame_sharpness = len(frame)
        if queues_dict['rgb'].empty():queues_dict['rgb'].put(rgb)
        if queues_dict['frame_len'].empty():queues_dict['frame_len'].put(frame_sharpness)
        if frame_sharpness >= max_sharpness:
            max_sharpness = frame_sharpness
            motor0.z_focus = motor0.z_pos
            motor0.focus_vol = motor0.measure_voltage('Z')
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        pbar.update(1)  # 更新进度条


# 录制视频
def record_video():
    global is_recording, video_writer, current_video_filename
    cam0.size = video_size
    rgb = queues_dict['rgb'].get()
    time.sleep(0.1)  # 等待队列中的数据稳定
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    current_video_filename = os.path.join(SAVE_DIR, f'{timestamp}.avi')
    video_writer = cv2.VideoWriter(current_video_filename, fourcc, 20, video_size, isColor=True)
    i = 0
    while is_recording:
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
        return settings
    except FileNotFoundError:
        print("Settings file not found. Using default settings.")
        return {}  # 如果文件不存在，返回空字典或默认设置

@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings = load_settings()
    return jsonify(settings)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    global is_veiwing
    is_veiwing = True  # 开始视频流
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/capture')
def capture():
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
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({"error": "Failed to save image"}), 500


@app.route('/start_recording')
def start_recording():
    global is_recording
    if not is_recording:
        is_recording = True
        threading.Thread(target=record_video).start()
        return jsonify({"message": "Recording started"})
    return jsonify({"message": "Recording already in progress"})


@app.route('/stop_recording')
def stop_recording():
    global is_recording, video_writer, current_video_filename
    if is_recording:
        is_recording = False
        if os.path.exists(current_video_filename):
            size = os.path.getsize(current_video_filename) # 文件路径及文件名
            print(current_video_filename, size)
            return send_file(current_video_filename, as_attachment=True)
        else:
            return jsonify({"error": "No video file found"}), 404
    else:
        return jsonify({"message": "Recording is not in progress"}), 400
        

# 发送命令接口（例如用户输入）
@app.route('/send_command', methods=['POST'])
def send_command():
    command = request.json.get('command')
    # 处理命令，这里可以是一些树莓派操作
    return jsonify({"message": f"Command received: {command}"})


@app.route('/set_exposure', methods=['POST'])
def set_exposure():
    """设置曝光时间"""
    exposure_time = int(request.json['value'])*1000
    cam0.exposure_time = exposure_time
    cam0.set_exposure()
    return jsonify({"status": "exposure set"})


@app.route('/set_gain', methods=['POST'])
def set_gain():
    """设置增益系数"""
    gain = float(request.json['value'])
    cam0.analogue_gain = gain
    cam0.set_gain()
    return jsonify({"status": "gain set"})


@app.route('/set_x_pos', methods=['POST'])
def set_x_pos():
    """x方向位置"""
    xpos = float(request.json['value'])  #每移动1mm，相当于电机转1024步
    motor0.direction = 'X'
    if motor0.status:
        motor0.status = False
        time.sleep(0.01)
        xdelta_step = 1024*xpos - motor0.x_pos
        motor0.status = True
        motor0.move(xdelta_step)
        print(motor0.x_pos, 1024*xpos)
    else:
        motor0.status = True
        xdelta_step = 1024*xpos - motor0.x_pos
        motor0.move(xdelta_step)
        print(motor0.x_pos, 1024*xpos)
    return jsonify({"status": "x position set"})


@app.route('/set_y_pos', methods=['POST'])
def set_y_pos():
    """y方向位置"""
    ypos = float(request.json['value'])  #每移动1mm，相当于电机转1024步
    motor0.direction = 'Y'
    if motor0.status:
        motor0.status = False
        time.sleep(0.01)
        ydelta_step = 1024*ypos - motor0.y_pos
        motor0.status = True
        motor0.move(ydelta_step)
        print(motor0.y_pos, 1024*ypos)
    else:
        motor0.status = True
        ydelta_step = 1024*ypos - motor0.y_pos
        motor0.move(ydelta_step)
        print(motor0.y_pos, 1024*ypos)
    return jsonify({"status": "y position set"})


@app.route('/set_z_pos', methods=['POST'])
def set_z_pos():
    """z方向位置"""
    zpos = float(request.json['value'])  #每移动1mm，相当于电机转1024步
    motor0.direction = 'Z'
    if motor0.status:
        motor0.status = False
        time.sleep(0.01)
        zdelta_step = 1024*zpos - motor0.z_pos
        motor0.status = True
        motor0.move(zdelta_step)
        # print(motor0.measure_voltage('Z'))

    else:
        motor0.status = True
        zdelta_step = 1024*zpos - motor0.z_pos
        motor0.move(zdelta_step)
        # print(motor0.measure_voltage('Z'))
    
    return jsonify({"status": "z position set"})


@app.route('/fast_focus', methods=['POST'])
def fast_focus():
    """快速对焦"""
    print(motor0.measure_voltage('Z'))
    motor0.direction = 'Z'
    # 先扫描400步，看方向
    motor0.status = True
    _ = queues_dict['frame_len'].get()
    test_sharpness1  = queues_dict['frame_len'].get()
    motor0.move(400)
    _ = queues_dict['frame_len'].get()
    test_sharpness2  = queues_dict['frame_len'].get()
    phi = 0.618
    tolerance, iterations = 1, 0
    if test_sharpness1 >= test_sharpness2:
        # 在当前位置的往小了走
        if motor0.focus_sharpness > test_sharpness1*1.2 and motor0.z_focus < motor0.z_pos:
            # 说明motor0.z_focus值可信
            z_max, z_min = motor0.z_focus+500,  motor0.z_focus-500  #搜索范围正负2 mm
        else:
            z_max, z_min = motor0.z_pos+100, motor0.z_pos-2000  #搜索范围正负2 mm
        # 初始搜索区间和焦距
        while (z_max - z_min) > tolerance and iterations < 100:
            print(motor0.measure_voltage(pos_direct='Z'))
            z1 = z_max - (z_max - z_min)*phi
            z2 = z_min + (z_max - z_min)*phi
            zdelta_step = z2 - motor0.z_pos
            motor0.status = True
            motor0.move(zdelta_step)
            _ = queues_dict['frame_len'].get()
            sharpness2  = queues_dict['frame_len'].get()
            zdelta_step = z1 - motor0.z_pos
            motor0.status = True
            motor0.move(zdelta_step)
            _ = queues_dict['frame_len'].get()
            sharpness1  = queues_dict['frame_len'].get()
            # 根据清晰度动态调整步长和搜索范围
            if sharpness1 > sharpness2: #更新右端点
                # phi = (phi + 0.5)/2
                if z_max - z_min < tolerance:
                    z_min = z1
                else:
                    z_max = z2
            else: #更新左端点
                # phi = (phi + 1)/2
                z_min = z1
            print(sharpness1, sharpness2, z_max, z_min, motor0.focus_sharpness, motor0.z_focus, motor0.focus_vol)
    else: # 在当前位置的往大了走
        if  motor0.focus_sharpness > test_sharpness2*1.2 and motor0.z_focus > motor0.z_pos-400:
            # 说明motor0.z_focus值可信
            z_max, z_min = motor0.z_focus+500, motor0.z_pos-500  #搜索范围正负2 mm
        else:
            z_max, z_min = motor0.z_pos+2000, motor0.z_pos-500  #搜索范围正负2 mm
        # 初始搜索区间和焦距
        print(z_max,z_min)
        while (z_max - z_min) > tolerance and iterations < 100:
            print(motor0.measure_voltage('Z'))
            iterations += 1
            z1 = z_max - (z_max - z_min)*phi
            z2 = z_min + (z_max - z_min)*phi
            zdelta_step = z1 - motor0.z_pos
            motor0.status = True
            motor0.move(zdelta_step)
            _ = queues_dict['frame_len'].get()
            sharpness1  = queues_dict['frame_len'].get()
            zdelta_step = z2 - motor0.z_pos
            motor0.status = True
            motor0.move(zdelta_step)
            _ = queues_dict['frame_len'].get()
            sharpness2  = queues_dict['frame_len'].get()
            # 根据清晰度动态调整步长和搜索范围
            if sharpness1 > sharpness2: #更新右端点
                # phi = (phi + 0.5)/2
                # 如果清晰度差异较大，缩小步长和搜索区间
                tolerance /= 2
                if z_max - z_min < tolerance:
                    z_min = z1
                else:
                    z_max = z2
            else: #更新左端点
                # phi = (phi + 1)/2
                # 如果清晰度差异较小，扩大步长和搜索区间
                tolerance *= 1.5
                z_min = z1
            print(sharpness1, sharpness2, z_max, z_min, motor0.focus_sharpness, motor0.z_focus, motor0.focus_vol)
    best_z = (z_min + z_max) / 2
    zdelta_step = best_z - motor0.z_pos
    motor0.status = True
    motor0.move(zdelta_step)
    print(best_z/1024)

    return jsonify({"status": "fast focus set"})



@app.route('/set_led', methods=['POST'])
def set_led():
    """设置led亮度"""  
    led_value = float(request.json['value'])
    led.value = led_value
    return jsonify({"status": "led set"})


@app.route('/set_r_bal', methods=['POST'])
def set_r_bal():
    """设置白平衡增益R"""  
    r_value = float(request.json['value'])
    cam0.r_gain = r_value
    return jsonify({"status": "r gain set"})

@app.route('/set_b_bal', methods=['POST'])
def set_b_bal():
    """设置白平衡增益B"""  
    b_value = float(request.json['value'])
    cam0.b_gain = b_value
    return jsonify({"status": "b gain set"})


# # REST API 端点，返回当前状态
# @app.route('/get_status', methods=['GET'])
# def get_status():
#     return jsonify({'status': motor0.status})


# # 状态更新的函数
# def generate_status_updates():
#     while True:
#         status = motor0.status
#         yield f"data: {{'status': {status}}}\n\n"
#         time.sleep(1)  # 模拟每 3 秒变化一次状态

# # SSE 路由，用于前端接收状态更新
# @app.route('/events')
# def sse():
#     return Response(generate_status_updates(), content_type='text/event-stream')


@app.route('/save_config', methods=['POST'])
def save_config():
    """保存设置"""  
    settings = {
        'exposure_value': cam0.exposure_time/1000,
        'gain_value': cam0.analogue_gain,
        'led_value': led.value,
        'r_value': cam0.r_gain,
        'b_value': cam0.b_gain,
    }
    with open('settings.json', 'w') as f:
        json.dump(settings, f)
    return jsonify({"status": "config set"})


@app.route('/close', methods=['POST'])
def close():
    global is_veiwing, is_recording, video_writer
    """用户关闭网页时，停止所有功能"""
    is_veiwing = False
    is_recording = False
    if video_writer is not None:
        video_writer.release()
    cam0.__stop__() # 停止摄像头
    motor0.status = False
    return jsonify({"status": "closed"})



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
