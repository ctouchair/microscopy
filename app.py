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
import io
from utils import stitch_images, focus_stack, count_cells


class ConfigManager:
    """配置管理类，用于管理所有配置参数"""
    def __init__(self):
        self.z_level = 5  # 景深堆叠Z Level参数
        self.z_step_size = 2  # Z轴步进控制步长（微米），默认2μm
        self.x_step_size = 50  # X轴步进控制步长（微米），默认50μm
        self.y_step_size = 50  # Y轴步进控制步长（微米），默认50μm
        self.show_xyz = False  # 控制XYZ估算位置曲线的显示
        self.recording_interval = 0  # 拍摄间隔时间（秒）
        self.is_recording = False
        self.is_recording_cam1 = False
        self.is_veiwing = True
        self.move_task = False
        
        # 辅助摄像头录制相关
        self.video_writer = None
        self.video_writer_cam1 = None
        self.current_video_filename_cam1 = None
        self.cam1_previous_frame = None
        self.cam1_motion_detected = False
        self.cam1_last_motion_time = 0
        self.cam1_motion_threshold = 0.5
        self.cam1_motion_cooldown = 2.0
        
        # 定期清理缓存文件
        self.cleanup_interval = 3600  # 每小时清理一次（秒）
    
    def load_settings(self):
        """加载设置文件"""
        try:
            with open('/home/admin/Documents/microscopy/settings.json', 'r') as f:
                settings = json.load(f)
                cam0.exposure_time = int(settings['exposure_value']*1000)
                cam0.analogue_gain = settings['gain_value']
                cam0.r_gain = settings['r_value']
                cam0.b_gain = settings['b_value']
                motor0.led_cycle0 = int(settings.get('led_value_0', 10))
                motor0.set_led_power0()
                motor0.led_cycle1 = int(settings.get('led_value_1', 10))
                motor0.set_led_power1()
                # 读取校准的步数值，如果不存在则使用默认值1500
                cam0.pixel_size = settings.get('pixel_size', 0.09)
                print(f"Loaded pixel_size: {cam0.pixel_size}")
                # 读取显微镜倍率，如果不存在则使用默认值40
                cam0.mag_scale = settings.get('magnification', 40)
                print(f"Loaded magnification: {cam0.mag_scale}")
                # 读取景深堆叠Z Level参数，如果不存在则使用默认值5
                self.z_level = settings.get('z_level', 5)
                print(f"Loaded z_level: {self.z_level}")
                # 读取Z轴步进控制步长，如果不存在则使用默认值2
                self.z_step_size = settings.get('z_step_size', 2)
                print(f"Loaded z_step_size: {self.z_step_size}")
                # 读取X轴步进控制步长，如果不存在则使用默认值50
                self.x_step_size = settings.get('x_step_size', 50)
                print(f"Loaded x_step_size: {self.x_step_size}")
                # 读取Y轴步进控制步长，如果不存在则使用默认值50
                self.y_step_size = settings.get('y_step_size', 50)
                print(f"Loaded y_step_size: {self.y_step_size}")
            return settings
        except FileNotFoundError:
            print("Settings file not found. Using default settings.")
            return {}  # 如果文件不存在，返回空字典或默认设置
    
    def save_settings(self):
        """保存设置到文件"""
        try:
            settings = {
                'exposure_value': cam0.exposure_time/1000,
                'gain_value': cam0.analogue_gain,
                'led_value_0': motor0.led_cycle0,
                'led_value_1': motor0.led_cycle1,
                'r_value': cam0.r_gain,
                'b_value': cam0.b_gain,
                'xy_steps_per_mm': motor0.xy_steps_per_mm,
                'z_steps_per_mm': motor0.z_steps_per_mm,
                'magnification': cam0.mag_scale,  # 保存显微镜倍率
                'z_level': self.z_level,  # 保存景深堆叠Z Level参数
                'z_step_size': self.z_step_size,  # 保存Z轴步进控制步长
                'x_step_size': self.x_step_size,  # 保存X轴步进控制步长
                'y_step_size': self.y_step_size,  # 保存Y轴步进控制步长
            }
            with open('/home/admin/Documents/microscopy/settings.json', 'w') as f:
                json.dump(settings, f)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False


# 创建全局配置管理器实例
config = ConfigManager()

imx477_dict = {
    "preview_size": (1014, 760),  # 预览分辨率
    "video_size": (2028, 1520),   # 视频分辨率
    "image_size": (4056, 3040),    # 图片分辨率
    "frame_rate": 20  # 视频帧率
}
imx219_dict = {
    "preview_size": (820, 616),  # 预览分辨率
    "video_size": (1640, 1232),   # 视频分辨率
    "image_size": (3280, 2464),    # 图片分辨率
    "frame_rate": 10  # 视频帧率
}


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 日志发送函数
def send_log_message(message, log_type='info'):
    """发送日志消息到前端"""
    try:
        socketio.emit('log_message', {'message': message, 'type': log_type})
    except Exception as e:
        print(f"Failed to send log message: {e}")

cam0 = VideoCamera(Picamera2(1), preview_size=imx477_dict["preview_size"], video_size=imx477_dict["video_size"], image_size=imx477_dict["image_size"], framerate=imx477_dict["frame_rate"])
cam1 = VideoCamera(Picamera2(0), preview_size=imx219_dict["preview_size"], video_size=imx219_dict["video_size"], image_size=imx219_dict["image_size"], framerate=imx219_dict["frame_rate"])
cam1.apply_perspective = False


motor0 = motor()

# 存储照片和录像的目录
SAVE_DIR = '/home/admin/Documents/microscopy/static'
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)


queues_dict = {
    'rgb': multiprocessing.Queue(),
    'frame_len': multiprocessing.Queue(),
    'cam1_rgb': multiprocessing.Queue(),
}


# 开启摄像头预览及队列
def generate_frames():
    """
    不采用全速写入的方式，微观领域帧率不是关键因素
    """
    cam0.__stop__()
    time.sleep(0.5)
    cam0.preview_config()
    time.sleep(0.5)
    # pbar = tqdm(total=0, dynamic_ncols=True)
    max_sharpness, z_pos_array, sharp_array = 0, [], []
    motor0.focus_get = False
    frame_counter = 0  # 添加帧计数器用于帧率控制
    while config.is_veiwing:
        frame, rgb = cam0.get_frame(awb=True, crap=False)  #rgb图片是用于视频写入保存，为视频分辨率
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
        
        # Send frame via SocketIO for real-time streaming (帧率减半)
        if frame_counter % 2 == 0:  # 只推送偶数帧，实现帧率减半
            try:
                # Convert frame to base64 for SocketIO transmission
                frame_base64 = base64.b64encode(frame).decode('utf-8')
                socketio.emit('video_frame', {'frame': frame_base64})
            except Exception as e:
                print(f"Error sending frame: {e}")
        
        frame_counter += 1
            
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        # pbar.update(1)  # 更新进度条


# 开启cam1摄像头预览
def generate_frames_cam1():
    """
    cam1的视频流生成函数
    """
    cam1.__stop__()
    time.sleep(0.5)
    cam1.exposure_time = 20000
    cam1.preview_config()
    time.sleep(0.5)
    # pbar = tqdm(total=0, dynamic_ncols=True)
    frame_counter_cam1 = 0  # 添加帧计数器用于帧率控制
    while config.is_veiwing:
        frame, rgb = cam1.get_frame(awb=False, flip=True, to_bgr=True, crap=False)
        if queues_dict['cam1_rgb'].empty():queues_dict['cam1_rgb'].put(rgb)
        # Send frame via SocketIO for real-time streaming (帧率减半)
        if frame_counter_cam1 % 2 == 0:  # 只推送偶数帧，实现帧率减半
            try:
                # Convert frame to base64 for SocketIO transmission
                frame_base64 = base64.b64encode(frame).decode('utf-8')
                socketio.emit('video_frame_cam1', {'frame': frame_base64})
            except Exception as e:
                print(f"Error sending cam1 frame: {e}")
        
        frame_counter_cam1 += 1
            
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        # pbar.update(1)  # 更新进度条


# 录制视频
def record_video():
    rgb = queues_dict['rgb'].get()
    time.sleep(0.1)  # 等待队列中的数据稳定
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    current_video_filename = os.path.join(SAVE_DIR, f'{timestamp}.avi')
    config.video_writer = cv2.VideoWriter(current_video_filename, fourcc, imx477_dict["frame_rate"], cam0.video_size, isColor=True)
    i, max_frame = 0, 20000
    while config.is_recording or not queues_dict['rgb'].empty():
        rgb = queues_dict['rgb'].get()
        bgr = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB, rgb)  # 写入图象时，会替换通道

        if i < max_frame:
            if config.recording_interval > 0 :
                time.sleep(config.recording_interval)
            config.video_writer.write(bgr)
        else:
            config.is_recording = False
        i += 1
    config.video_writer.release()


def record_video_cam1():
    """辅助摄像头动态录制函数"""
    # 初始化视频写入器
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    config.current_video_filename_cam1 = os.path.join(SAVE_DIR, f'cam1_{timestamp}.avi')
    config.video_writer_cam1 = cv2.VideoWriter(config.current_video_filename_cam1, fourcc, 10, cam1.video_size, isColor=True)
    
    send_log_message('辅助摄像头录制已开始', 'info')
    # 只选择图像视野中心1/4区域进行运动检测
    width, height =  cam1.video_size
    center_x = width // 2
    center_y = height // 2
    roi_width = width // 4
    roi_height = height // 4
    
    # 计算ROI区域的边界
    roi_x1 = center_x - roi_width // 2
    roi_y1 = center_y - roi_height // 2
    roi_x2 = center_x + roi_width // 2
    roi_y2 = center_y + roi_height // 2
    while config.is_recording_cam1 or not queues_dict['cam1_rgb'].empty():
        try:
            # 获取当前帧
            rgb = queues_dict['cam1_rgb'].get()
            
            # 转换为灰度图进行运动检测
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            # 运动检测
            if config.cam1_previous_frame is not None:
                
                # 提取当前帧的中心1/4区域
                current_roi = gray[roi_y1:roi_y2, roi_x1:roi_x2]
                
                # 提取前一帧的中心1/4区域
                prev_roi = config.cam1_previous_frame[roi_y1:roi_y2, roi_x1:roi_x2]
                
                # 计算帧差
                frame_delta = cv2.absdiff(prev_roi, current_roi)
                thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
                
                # 计算运动区域（只计算ROI区域）
                motion_pixels = cv2.countNonZero(thresh)
                total_pixels = thresh.shape[0] * thresh.shape[1]
                motion_ratio = motion_pixels / total_pixels * 100
                
                current_time = time.time()
                # 检测到运动
                if motion_ratio > config.cam1_motion_threshold:
                    config.cam1_motion_detected = True
                    config.cam1_last_motion_time = current_time
                    # 以10fps录制
                    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                    config.video_writer_cam1.write(bgr)
                    time.sleep(0.1)  # 100ms间隔，10fps
                    # 发送运动检测状态
                    socketio.emit('motion_status', {'motion_detected': True, 'ratio': round(motion_ratio, 2)})
                else:
                    # 检查是否在冷却期内
                    if current_time - config.cam1_last_motion_time < config.cam1_motion_cooldown:
                        # 冷却期内继续以10fps录制
                        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                        config.video_writer_cam1.write(bgr)
                        time.sleep(0.1)
                    else:
                        # 冷却期后以1fps录制
                        if config.cam1_motion_detected:
                            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                            config.video_writer_cam1.write(bgr)
                            time.sleep(1.0)  # 1秒间隔，1fps
                            config.cam1_motion_detected = False
                        else:
                            # 没有运动时也以1fps录制
                            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                            config.video_writer_cam1.write(bgr)
                            time.sleep(1.0)
            else:
                # 第一帧，直接写入
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                config.video_writer_cam1.write(bgr)
                time.sleep(0.1)
            
            # 更新前一帧
            config.cam1_previous_frame = gray.copy()
            
        except Exception as e:
            print(f"Cam1 recording error: {e}")
            time.sleep(0.1)
    
    # 录制结束，释放资源
    if config.video_writer_cam1 is not None:
        config.video_writer_cam1.release()
        config.video_writer_cam1 = None
    
    send_log_message('辅助摄像头录制已停止', 'info')




def arctan_func(x, A, B, C, D):
    return A * np.arctan(B*(x-C)) + D

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    send_log_message('客户端已连接', 'success')
    # Load motor positions and send initial settings to client
    # motor_positions = load_motor_positions()
    settings = config.load_settings()
    x_vol = motor0.measure_voltage('X')
    y_vol = motor0.measure_voltage('Y')
    z_vol = motor0.measure_voltage('Z')
    with open('/home/admin/Documents/microscopy/params.json', 'r', encoding='utf-8') as f:
        data_params = json.load(f)
        f.close()
    params_x = data_params['X']
    params_y = data_params['Y']
    params_z = data_params['Z'] 
    motor0.x_pos = int(arctan_func(x_vol, params_x[0], params_x[1], params_x[2], params_x[3])*motor0.xy_steps_per_mm)
    motor0.y_pos = int(arctan_func(y_vol, params_y[0], params_y[1], params_y[2], params_y[3])*motor0.xy_steps_per_mm)
    motor0.z_pos = int(arctan_func(z_vol, params_z[0], params_z[1], params_z[2], params_z[3])*motor0.z_steps_per_mm)
    print(x_vol, motor0.x_pos)
    # Combine settings with motor positions
    initial_data = {
        **settings,
        'x_pos': round(motor0.x_pos / motor0.xy_steps_per_mm, 2),  # Convert steps to mm
        'y_pos': round(motor0.y_pos / motor0.xy_steps_per_mm, 2),
        'z_pos': round(motor0.z_pos / motor0.z_steps_per_mm, 2),
        'show_xyz': config.show_xyz,  # 添加show_xyz变量到初始数据中
        'magnification': cam0.mag_scale,  # 添加显微镜倍率到初始数据中
        'z_level': config.z_level  # 添加景深堆叠Z Level参数到初始数据中
    }
    emit('settings_update', initial_data)
    
    # 检查并发送WiFi权限状态
    wifi_permissions_ok = check_wifi_permissions()
    emit('wifi_permissions_status', {
        'has_permissions': wifi_permissions_ok,
        'message': 'WiFi权限已配置' if wifi_permissions_ok else 'WiFi权限未配置，请运行 sudo bash setup_wifi_permissions.sh'
    })


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    send_log_message('客户端已断开连接', 'warning')
    """断开连接时，停止所有功能"""
    config.is_veiwing = False
    config.is_recording = False
    config.is_recording_cam1 = False
    if config.video_writer is not None:
        config.video_writer.release()
    if config.video_writer_cam1 is not None:
        config.video_writer_cam1.release()
    cam0.__stop__() # 停止摄像头
    cam1.__stop__() # 停止cam1摄像头
    motor0.status = False
    motor0.led_cycle0 = 0
    motor0.set_led_power0()
    motor0.led_cycle1 = 0
    motor0.set_led_power1()
    emit('closed', {'status': 'success', 'message': 'System closed'})


@socketio.on('get_settings')
def handle_get_settings():
    settings = config.load_settings()
    emit('settings_update', settings)


@socketio.on('check_wifi_permissions')
def handle_check_wifi_permissions():
    """检查WiFi权限状态"""
    try:
        has_permissions = check_wifi_permissions()
        emit('wifi_permissions_status', {
            'has_permissions': has_permissions,
            'message': 'WiFi权限已配置' if has_permissions else 'WiFi权限未配置，请运行 sudo bash setup_wifi_permissions.sh'
        })
    except Exception as e:
        print(f"Error checking WiFi permissions: {e}")
        emit('wifi_permissions_status', {
            'has_permissions': False,
            'message': f'检查权限时出错: {str(e)}'
        })


@socketio.on('setup_wifi_permissions')
def handle_setup_wifi_permissions():
    """手动触发WiFi权限配置"""
    try:
        send_log_message('开始配置WiFi权限...', 'info')
        emit('wifi_permissions_setup', {
            'status': 'starting',
            'message': '正在配置WiFi权限...'
        })
        
        success = setup_wifi_permissions()
        
        if success:
            emit('wifi_permissions_setup', {
                'status': 'success',
                'message': 'WiFi权限配置成功'
            })
            emit('wifi_permissions_status', {
                'has_permissions': True,
                'message': 'WiFi权限已配置'
            })
        else:
            emit('wifi_permissions_setup', {
                'status': 'error',
                'message': 'WiFi权限配置失败，请手动运行 sudo bash setup_wifi_permissions.sh'
            })
            
    except Exception as e:
        print(f"Error setting up WiFi permissions: {e}")
        send_log_message(f'配置WiFi权限时出错: {str(e)}', 'error')
        emit('wifi_permissions_setup', {
            'status': 'error',
            'message': f'配置权限时出错: {str(e)}'
        })


@socketio.on('capture')
def handle_capture():
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    rgb = cam0.capture_config()
    rgb[:,:,0] = rgb[:,:,0] * cam0.r_gain  # 调整红色
    rgb[:,:,2] = rgb[:,:,2] * cam0.b_gain  # 调整绿色
    pil_image = Image.fromarray(rgb) #PIL编码
    # 使用Pillow进行编码
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format='jpeg')
    file_data = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
    emit('capture_response', {
        'success': True,
        'filename': f'{timestamp}.jpeg',
        'data': file_data
    })

    cam0.preview_config()


@socketio.on('capture_cam1')
def handle_capture_cam1():
    try:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        # 使用cam1进行拍照，与cam0类似的流程
        rgb = cam1.capture_config()
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        # 转换为PIL图像并编码
        pil_image = Image.fromarray(bgr)
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='jpeg')
        file_data = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        
        emit('capture_cam1_response', {
            'success': True,
            'filename': f'cam1_{timestamp}.jpeg',
            'data': file_data
        })
        
        send_log_message(f'辅助摄像头拍照成功: cam1_{timestamp}.jpeg', 'success')
        
    except Exception as e:
        print(f"Cam1 capture error: {e}")
        send_log_message(f'辅助摄像头拍照失败: {str(e)}', 'error')
        emit('capture_cam1_response', {
            'success': False,
            'error': str(e)
        })
    finally:
        # 恢复cam1的预览模式
        cam1.exposure_time = 20000
        cam1.preview_config()
    


@socketio.on('start_recording')
def handle_start_recording(data=None):
    if not config.is_recording:
        # 检查辅助摄像头是否正在录制
        if config.is_recording_cam1:
            emit('recording_status', {'recording': False, 'message': '辅助摄像头正在录制中，请先停止辅助摄像头录制', 'error': True})
            return
        
        # Get the current recording interval from frontend if provided
        if data and 'interval' in data:
            config.recording_interval = float(data['interval'])
        
        config.is_recording = True
        threading.Thread(target=record_video).start()
        
        # 如果设置了间隔录制，显示间隔信息
        if config.recording_interval > 0:
            interval_info = f"Recording started with interval frames every {config.recording_interval} seconds"
        else:
            interval_info = "Recording started"
            
        emit('recording_status', {'recording': True, 'message': interval_info, 'interval': config.recording_interval})
    else:
        emit('recording_status', {'recording': True, 'message': 'Recording already in progress'})


@socketio.on('stop_recording')
def handle_stop_recording():
    if config.is_recording:
        config.is_recording = False
        # 需要从record_video函数中获取文件名，这里暂时使用一个通用的方法
        # 在实际应用中，可能需要将文件名也存储在config中
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        current_video_filename = os.path.join(SAVE_DIR, f'{timestamp}.avi')
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
        cam0.preview_size = imx477_dict["preview_size"]
    else:
        emit('recording_response', {'success': False, 'error': 'Recording is not in progress'})


@socketio.on('start_recording_cam1')
def handle_start_recording_cam1():
    if not config.is_recording_cam1:
        # 检查主摄像头是否正在录制
        if config.is_recording:
            emit('recording_cam1_status', {'recording': False, 'message': '主摄像头正在录制中，请先停止主摄像头录制', 'error': True})
            return
        
        config.is_recording_cam1 = True
        threading.Thread(target=record_video_cam1).start()
        emit('recording_cam1_status', {'recording': True, 'message': '辅助摄像头录制已开始'})
    else:
        emit('recording_cam1_status', {'recording': True, 'message': '辅助摄像头录制已在进行中'})


@socketio.on('stop_recording_cam1')
def handle_stop_recording_cam1():
    if config.is_recording_cam1:
        config.is_recording_cam1 = False
        time.sleep(0.5)  # 等待录制线程结束
        
        if os.path.exists(config.current_video_filename_cam1):
            size = os.path.getsize(config.current_video_filename_cam1)
            print(f"Cam1 video: {config.current_video_filename_cam1}, size: {size}")
            # Send file as base64
            with open(config.current_video_filename_cam1, 'rb') as f:
                file_data = base64.b64encode(f.read()).decode('utf-8')
            emit('recording_cam1_response', {
                'success': True,
                'filename': os.path.basename(config.current_video_filename_cam1),
                'data': file_data
            })
        else:
            emit('recording_cam1_response', {'success': False, 'error': 'No cam1 video file found'})
    else:
        emit('recording_cam1_response', {'success': False, 'error': 'Cam1 recording is not in progress'})


@socketio.on('stitch_images')
def handle_stitch_images():
    try:
        # 发送开始拼接的状态
        emit('stitch_status', {'status': 'started', 'message': '开始图像拼接...'})
        
        # 实现400%画幅拼接（2x2网格）
        # 拍摄4张图片，每张图片移动一定距离
        images = []
        
        # 保存当前位置
        original_x = motor0.x_pos
        original_y = motor0.y_pos
        mag_scale = 20/cam0.mag_scale
        # 计算移动步长（根据图像分辨率和视野计算）
        # 假设图像视野为0.4mm x 0.3mm，需要50%重叠区域
        # 每张图片移动0.2mm，确保有足够重叠
        step_x_size = int(motor0.xy_steps_per_mm * 0.28*mag_scale)  # 0.32mm步长，确保30%重叠
        step_y_size = int(motor0.xy_steps_per_mm * 0.21*mag_scale)  # 0.24mm步长，确保30%重叠
        # 拍摄3x3网格的图片，从左上角开始
        # 贪吃蛇形状运动：左上→右上→右中→右下→中下→中中→中上→左中→左上
        # 每张图片移动步长，确保有足够重叠区域进行拼接
        positions = [
            (-step_x_size, -step_y_size),     # 左上
            (step_x_size, 0),     # 中上
            (step_x_size, 0),      # 右上
            (0, step_y_size),      # 右中
            (-step_x_size, 0),     # 中中
            (-step_x_size, 0),      # 左中
            (0, step_y_size),     # 左下
            (step_x_size, 0),     # 中下
            (step_x_size, 0),      # 右下
        ]
        
        for i, (dx, dy) in enumerate(positions):
            send_log_message(f'拍摄第 {i+1}/9 张拼接图片', 'info')
            # 移动到指定位置
            if dx != 0:
                motor0.direction = 'X'
                motor0.status = True
                motor0.move(dx)
                time.sleep(0.1)  # 等待移动完成，确保稳定
            
            if dy != 0:
                motor0.direction = 'Y'
                motor0.status = True
                motor0.move(dy)
                time.sleep(0.1)  # 等待移动完成，确保稳定
            
            # 拍摄图片
            rgb = cam0.capture_config()
            rgb[:,:,0] = rgb[:,:,0] * cam0.r_gain
            rgb[:,:,2] = rgb[:,:,2] * cam0.b_gain

            images.append(rgb)
            
        # 恢复预览模式
        cam0.preview_config()
        
        # 恢复原始位置
        motor0.direction = 'X'
        motor0.status = True
        motor0.move(original_x - motor0.x_pos)
        time.sleep(0.1)
        
        motor0.direction = 'Y'
        motor0.status = True
        motor0.move(original_y - motor0.y_pos)
        time.sleep(0.1)
        
        # 拼接图像
        send_log_message('正在处理图像拼接...', 'info')
        stitched_image = stitch_images(images, positions)
        
        if stitched_image is not None:
            stitched_image = cv2.cvtColor(stitched_image, cv2.COLOR_BGR2RGB)
            
            # 裁剪黑边
            # stitched_image = crop_center_expanding_rect(stitched_image)
            
            # 生成拼接后的图像文件名（不保存到本地）
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            stitched_filename = f'stitched_{timestamp}.jpeg'
            
            # 直接将拼接图像转换为base64，不保存到本地
            # 使用cv2.imencode将图像编码为内存中的字节流
            _, buffer = cv2.imencode('.jpeg', stitched_image)
            file_data = base64.b64encode(buffer).decode('utf-8')
            
            emit('stitch_response', {
                'success': True,
                'filename': stitched_filename,
                'data': file_data
            })
        else:
            emit('stitch_response', {
                'success': False,
                'error': 'Image stitching failed'
            })
            
    except Exception as e:
        print(f"Stitch error: {e}")
        emit('stitch_response', {
            'success': False,
                'error': str(e)
        })


@socketio.on('focus_stack')
def handle_focus_stack():
    try:
        # 发送开始景深堆叠的状态
        emit('focus_stack_status', {'status': 'started', 'message': '开始景深堆叠...'})
        
        # 拍摄不同Z轴位置的5张照片
        images = []
        
        # 保存当前Z位置
        original_z = motor0.z_pos
        # 计算Z轴移动步长（每张图片间隔0.02mm，总共覆盖0.08mm景深）
        step_z_size = int(config.z_level*2)  # 使用config.z_level参数
        z_positions = [-3*step_z_size, -2*step_z_size, -step_z_size, 0, step_z_size, 2*step_z_size, 3*step_z_size]  # 7个位置
        
        for i, dz in enumerate(z_positions):
            send_log_message(f'拍摄第 {i+1}/{len(z_positions)} 张景深图片', 'info')
            # 移动到指定Z位置
            if dz != 0:
                motor0.direction = 'Z'
                motor0.status = True
                target_z = original_z + dz
                motor0.move(target_z - motor0.z_pos)
                time.sleep(0.2)  # 等待移动完成，确保稳定
            
            # 拍摄图片
            rgb = cam0.capture_config()
            rgb[:,:,0] = rgb[:,:,0] * cam0.r_gain
            rgb[:,:,2] = rgb[:,:,2] * cam0.b_gain
            # 恢复预览模式
            
            # 转换为BGR格式（OpenCV格式）
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            images.append(bgr)
            
            # 发送进度更新
            emit('focus_stack_progress', {'current': i+1, 'total': len(z_positions)})
        cam0.preview_config()
        
        # 恢复原始Z位置
        motor0.direction = 'Z'
        motor0.status = True
        motor0.move(original_z - motor0.z_pos)
        time.sleep(0.2)
        
        # 景深堆叠处理
        send_log_message('正在处理景深堆叠...', 'info')
        stacked_image, depthmap_image = focus_stack(images)

        if stacked_image is not None:
            # 生成景深堆叠后的图像文件名
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            stacked_filename = f'focus_stacked_{timestamp}.jpeg'
            
            # 直接将堆叠图像转换为base64，不保存到本地
            _, buffer = cv2.imencode('.jpeg', stacked_image)
            file_data = base64.b64encode(buffer).decode('utf-8')
            
            emit('focus_stack_response', {
                'success': True,
                'filename': stacked_filename,
                'data': file_data
            })
        else:
            emit('focus_stack_response', {
                'success': False,
                'error': 'Focus stacking failed'
            })
            
    except Exception as e:
        print(f"Focus stack error: {e}")
        emit('focus_stack_response', {
            'success': False,
            'error': str(e)
        })
    finally:
        cam0.preview_config()




@socketio.on('cell_count')
def handle_cell_count():
    try:
        # 发送开始细胞计数的状态
        emit('cell_count_status', {'status': 'started', 'message': '开始细胞计数...'})
        
        # 拍摄图片进行细胞计数
        print("拍摄细胞计数图片...")
        send_log_message('拍摄细胞计数图片...', 'info')
        rgb = cam0.capture_config()
        rgb[:,:,0] = rgb[:,:,0] * cam0.r_gain
        rgb[:,:,2] = rgb[:,:,2] * cam0.b_gain
        
        # 转换为BGR格式用于OpenCV处理
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        
        # 获取像素尺寸用于计算实际尺寸
        pixel_size = getattr(cam0, 'pixel_size', 0.09)  # 默认值0.09 μm/pixel
        
        print("正在进行细胞计数...")
        send_log_message('正在进行细胞计数...', 'info')
        
        # 进行细胞计数
        annotated_image, cell_count, avg_diameter = count_cells(bgr, pixel_size)
        
        if annotated_image is not None:
            # 生成细胞计数后的图像文件名
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            count_filename = f'cell_count_{timestamp}.jpeg'
            
            # 直接将标注图像转换为base64，不保存到本地
            _, buffer = cv2.imencode('.jpeg', annotated_image)
            file_data = base64.b64encode(buffer).decode('utf-8')
            
            send_log_message(f'细胞计数完成 - 检测到 {cell_count} 个细胞，平均直径: {avg_diameter:.2f} μm', 'success')
            
            emit('cell_count_response', {
                'success': True,
                'filename': count_filename,
                'data': file_data,
                'cell_count': cell_count,
                'avg_diameter': avg_diameter
            })
        else:
            emit('cell_count_response', {
                'success': False,
                'error': 'Cell counting failed'
            })
            
    except Exception as e:
        print(f"Cell count error: {e}")
        send_log_message(f'细胞计数失败: {str(e)}', 'error')
        emit('cell_count_response', {
            'success': False,
            'error': str(e)
        })
    finally:
        cam0.preview_config()


@socketio.on('auto_brightness')
def handle_auto_brightness(data):
    try:
        led_type = data.get('led_type', 0)  # 默认为反射LED (0)
        led_name = '反射' if led_type == 0 else '透射'
        
        # 发送开始自动亮度调节的状态
        emit('auto_brightness_status', {'status': 'started', 'message': f'开始{led_name}自动亮度调节...'})
        send_log_message(f'开始{led_name}自动亮度调节...', 'info')
        
        # 保存原始LED设置
        if led_type == 0:
            original_led = motor0.led_cycle0
            led_values = list(range(max(0, original_led - 10), min(20, original_led + 11)))
        else:
            original_led = motor0.led_cycle1
            led_values = list(range(max(0, original_led - 10), min(50, original_led + 11)))
        
        # 测试不同LED亮度下的清晰度
        
        max_sharpness = 0
        optimal_led = original_led
        sharpness_results = []
        
        for i, led_value in enumerate(led_values):
            # 设置LED亮度
            if led_type == 0:
                motor0.led_cycle0 = led_value
                motor0.set_led_power0()
            else:
                motor0.led_cycle1 = led_value
                motor0.set_led_power1()
            time.sleep(0.1)  # 等待LED稳定
            
            # 清空队列中的旧数据
            while not queues_dict['frame_len'].empty():
                try:
                    queues_dict['frame_len'].get_nowait()
                except:
                    break
            
            # 等待新的帧数据
            time.sleep(0.1)
            
            # 获取当前清晰度
            try:
                frame_sharpness = queues_dict['frame_len'].get(timeout=2.0)
                sharpness_results.append((led_value, frame_sharpness))
                
                # 发送进度更新
                emit('auto_brightness_progress', {
                    'current': i + 1,
                    'total': len(led_values),
                    'led_value': led_value,
                    'sharpness': frame_sharpness,
                    'led_type': led_type
                })
                
                # 更新最优值
                if frame_sharpness > max_sharpness:
                    max_sharpness = frame_sharpness
                    optimal_led = led_value
                
                print(f"{led_name}LED {led_value}: 清晰度 {frame_sharpness}")
                send_log_message(f'{led_name}LED {led_value}: 清晰度 {frame_sharpness}', 'debug')
                
            except Exception as e:
                print(f"获取清晰度数据失败 {led_name}LED {led_value}: {e}")
                sharpness_results.append((led_value, 0))
        
        # 设置为最优LED亮度
        if led_type == 0:
            motor0.led_cycle0 = optimal_led
            motor0.set_led_power0()
        else:
            motor0.led_cycle1 = optimal_led
            motor0.set_led_power1()
        
        print(f"{led_name}自动亮度调节完成 - 最佳LED: {optimal_led}, 最大清晰度: {max_sharpness}")
        send_log_message(f'{led_name}自动亮度调节完成 - 最佳LED: {optimal_led}, 最大清晰度: {max_sharpness}', 'success')
        
        emit('auto_brightness_response', {
            'success': True,
            'optimal_led': optimal_led,
            'max_sharpness': max_sharpness,
            'results': sharpness_results,
            'led_type': led_type
        })
        
    except Exception as e:
        print(f"{led_name}Auto brightness error: {e}")
        send_log_message(f'{led_name}自动亮度调节失败: {str(e)}', 'error')
        
        # 恢复原始LED设置
        if led_type == 0:
            motor0.led_cycle0 = original_led
            motor0.set_led_power0()
        else:
            motor0.led_cycle1 = original_led
            motor0.set_led_power1()
        
        emit('auto_brightness_response', {
            'success': False,
            'error': str(e),
            'led_type': led_type
        })


@socketio.on('stop_move')
def handle_stop_move():
    """停止电机运动"""
    try:
        motor0.status = False
        motor0.direction = ''
        motor0.focus = False
        emit('move_status', {'status': False, 'message': 'Moving stopped'})
    except Exception as e:
        print(f"Stop move error: {e}")
        emit('move_status', {'status': False, 'message': str(e)})


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
        xpos = float(data['value'])  #每移动1mm，相当于电机转steps_per_mm步
        motor0.direction = 'X'
        target_xpose = int(motor0.xy_steps_per_mm*xpos)
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
        motor0.status = True
        motor0.move_to_target(target_xpose)
        emit('x_pos_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('x_pos_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_y_pos')
def handle_set_y_pos(data):
    try:
        ypos = float(data['value'])  #每移动1mm，相当于电机转steps_per_mm步
        motor0.direction = 'Y'
        target_ypose = int(motor0.xy_steps_per_mm*ypos)
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
        motor0.status = True
        motor0.move_to_target(target_ypose)
        emit('y_pos_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('y_pos_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_z_pos')
def handle_set_z_pos(data):
    try:
        zpos = float(data['value'])  #每移动1mm，相当于电机转steps_per_mm步
        motor0.direction, motor0.focus = 'Z', False
        target_zpose = int(motor0.z_steps_per_mm*zpos)
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
        motor0.status = True
        motor0.move_to_target(target_zpose)
        emit('z_pos_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('z_pos_set', {'status': 'error', 'message': str(e)})


@socketio.on('move_z')
def handle_move_z(data):
    """处理Z轴步进移动请求"""
    try:
        steps = int(data.get('steps', 1))  # 默认移动1步，可以是-1或1
        motor0.direction = 'Z'
        motor0.focus = False
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
        motor0.status = True
        motor0.move(steps)
        emit('z_move_response', {'status': 'success', 'steps': steps})
    except Exception as e:
        emit('z_move_response', {'status': 'error', 'message': str(e)})


@socketio.on('move_x')
def handle_move_x(data):
    """处理X轴步进移动请求"""
    try:
        step_size_um = float(data.get('step_size_um', 0))  # 步长（微米），可为正数或负数
        if step_size_um == 0:
            raise ValueError('步长不能为0')
        
        # 将微米转换为步数：(步长_um / 1000) * xy_steps_per_mm
        # 保持正负号以确定方向
        step_size_mm = abs(step_size_um) / 1000.0
        steps = int(step_size_mm * motor0.xy_steps_per_mm)
        if steps == 0:
            steps = 1  # 确保至少移动1步
        
        # 根据step_size_um的正负确定方向
        if step_size_um < 0:
            steps = -steps
        
        motor0.direction = 'X'
        motor0.focus = False
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
        motor0.status = True
        motor0.move(steps)
        emit('x_move_response', {'status': 'success', 'steps': steps})
    except Exception as e:
        emit('x_move_response', {'status': 'error', 'message': str(e)})


@socketio.on('move_y')
def handle_move_y(data):
    """处理Y轴步进移动请求"""
    try:
        step_size_um = float(data.get('step_size_um', 0))  # 步长（微米），可为正数或负数
        if step_size_um == 0:
            raise ValueError('步长不能为0')
        
        # 将微米转换为步数：(步长_um / 1000) * xy_steps_per_mm
        # 保持正负号以确定方向
        step_size_mm = abs(step_size_um) / 1000.0
        steps = int(step_size_mm * motor0.xy_steps_per_mm)
        if steps == 0:
            steps = 1  # 确保至少移动1步
        
        # 根据step_size_um的正负确定方向
        if step_size_um < 0:
            steps = -steps
        
        motor0.direction = 'Y'
        motor0.focus = False
        if motor0.status:
            motor0.status = False
            time.sleep(0.01)
        motor0.status = True
        motor0.move(steps)
        emit('y_move_response', {'status': 'success', 'steps': steps})
    except Exception as e:
        emit('y_move_response', {'status': 'error', 'message': str(e)})


def focus_init():
    motor0.direction = 'Z'
    motor0.focus = False  # 开始对焦
    # 先扫描400步，看方向
    motor0.status = False
    time.sleep(0.01)


@socketio.on('fast_focus')
def handle_fast_focus():
    try:
        send_log_message('开始快速对焦...', 'info')
        focus_init()
        motor0.focus = True  # 开始对焦， 同步开始记录最优值
        # 先扫描400步，看方向
        motor0.status = True
        _ = queues_dict['frame_len'].get()
        test_sharpness1  = queues_dict['frame_len'].get()
        motor0.move(200)
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
                # print(z2, sharpness2)

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
                # print(z2, sharpness2)
        motor0.focus, motor0.focus_get = False, False  # 对焦结束
        send_log_message(f'对焦完成 - 位置: {motor0.z_pos/motor0.z_steps_per_mm:.3f} mm', 'success')
        emit('focus_complete', {'status': 'success', 'position': motor0.z_pos/motor0.z_steps_per_mm})
    except Exception as e:
        emit('focus_complete', {'status': 'error', 'message': str(e)})


@socketio.on('set_led_0')
def handle_set_led_0(data):
    try:
        motor0.led_cycle0 = int(data['value'])
        motor0.set_led_power0()
        emit('led_0_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        print(f"LED 0 setting error: {e}")
        emit('led_0_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_led_1')
def handle_set_led_1(data):
    try:
        motor0.led_cycle1 = int(data['value'])
        motor0.set_led_power1()
        emit('led_1_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        print(f"LED 1 setting error: {e}")
        emit('led_1_set', {'status': 'error', 'message': str(e)})


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


@socketio.on('toggle_show_xyz')
def handle_toggle_show_xyz(data):
    """切换XYZ估算位置曲线的显示状态"""
    try:
        config.show_xyz = bool(data.get('show_xyz', False))
        send_log_message(f'位置调试模式已{"开启" if config.show_xyz else "关闭"}', 'info')
        emit('show_xyz_toggled', {'status': 'success', 'show_xyz': config.show_xyz})
    except Exception as e:
        send_log_message(f'切换位置调试模式失败: {str(e)}', 'error')
        emit('show_xyz_toggled', {'status': 'error', 'message': str(e)})


@socketio.on('set_magnification')
def handle_set_magnification(data):
    """设置显微镜倍率"""
    try:
        magnification = int(data.get('magnification', 40))
        # 验证倍率值是否有效
        valid_magnifications = [10, 20, 40, 60, 100]
        if magnification not in valid_magnifications:
            raise ValueError(f"无效的倍率值: {magnification}")
        
        # 更新cam0的mag_scale值
        cam0.mag_scale = magnification
        
        # 只保存倍率参数到settings.json
        try:
            # 先读取现有配置
            try:
                with open('/home/admin/Documents/microscopy/settings.json', 'r') as f:
                    settings = json.load(f)
            except FileNotFoundError:
                settings = {}
            
            # 只更新倍率参数
            settings['magnification'] = cam0.mag_scale
            
            # 保存更新后的配置
            with open('/home/admin/Documents/microscopy/settings.json', 'w') as f:
                json.dump(settings, f)
            print(f"Magnification saved: {magnification}")
        except Exception as save_error:
            print(f"Failed to save magnification: {save_error}")
        
        send_log_message(f'显微镜倍率已设置为: {magnification}倍', 'info')
        emit('magnification_set', {'status': 'success', 'magnification': magnification})
    except Exception as e:
        send_log_message(f'设置显微镜倍率失败: {str(e)}', 'error')
        emit('magnification_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_cam1_mode')
def handle_set_cam1_mode(data):
    try:
        mode = data.get('mode', 'normal')
        apply_perspective = data.get('apply_perspective', False)
        
        # 设置cam1的透视校正参数
        cam1.apply_perspective = apply_perspective
        
        mode_name = '正常模式' if mode == 'normal' else '校正模式'
        send_log_message(f'辅助摄像头模式已切换为: {mode_name}', 'info')
        
        emit('cam1_mode_response', {
            'success': True,
            'mode': mode,
            'apply_perspective': apply_perspective,
            'message': f'模式已切换为: {mode_name}'
        })
    except Exception as e:
        print(f"Cam1 mode setting error: {e}")
        send_log_message(f'辅助摄像头模式切换失败: {str(e)}', 'error')
        emit('cam1_mode_response', {
            'success': False,
            'error': str(e)
        })


@socketio.on('set_recording_delay')
def handle_set_recording_delay(data):
    try:
        config.recording_interval = float(data['value'])
        emit('recording_delay_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('recording_delay_set', {'status': 'error', 'message': str(e)})


@socketio.on('set_z_level')
def handle_set_z_level(data):
    try:
        config.z_level = int(data['value'])
        emit('z_level_set', {'status': 'success', 'value': data['value']})
    except Exception as e:
        emit('z_level_set', {'status': 'error', 'message': str(e)})


@socketio.on('save_config')
def handle_save_config(data=None):
    try:
        # 如果前端发送了步长配置，更新配置
        if data:
            if 'z_step_size' in data:
                config.z_step_size = int(data['z_step_size'])
            if 'x_step_size' in data:
                config.x_step_size = max(50, int(data['x_step_size']))  # 最小值50μm
            if 'y_step_size' in data:
                config.y_step_size = max(50, int(data['y_step_size']))  # 最小值50μm
        
        if config.save_settings():
            emit('config_saved', {'status': 'success', 'message': 'Configuration saved'})
        else:
            emit('config_saved', {'status': 'error', 'message': 'Failed to save configuration'})
    except Exception as e:
        emit('config_saved', {'status': 'error', 'message': str(e)})


@socketio.on('close')
def handle_close():
    """用户关闭网页时，停止所有功能"""
    config.is_veiwing = False
    config.is_recording = False
    config.is_recording_cam1 = False
    if config.video_writer is not None:
        config.video_writer.release()
    if config.video_writer_cam1 is not None:
        config.video_writer_cam1.release()
    cam0.__stop__() # 停止摄像头
    cam1.__stop__() # 停止cam1摄像头
    motor0.status = False
    emit('closed', {'status': 'success', 'message': 'System closed'})


@socketio.on('delete_video')
def handle_delete_video(data):
    try:
        filename = data.get('filename')
        if not filename:
            emit('delete_video_response', {'success': False, 'error': 'No filename provided'})
            return
        file_path = os.path.join(SAVE_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            emit('delete_video_response', {'success': True, 'message': f'{filename} deleted'})
        else:
            emit('delete_video_response', {'success': False, 'error': 'File not found'})
    except Exception as e:
        emit('delete_video_response', {'success': False, 'error': str(e)})


def check_wifi_permissions():
    """检查WiFi管理权限是否已配置"""
    try:
        import subprocess
        # 检查sudoers文件是否存在
        sudoers_file = '/etc/sudoers.d/microscope-wifi'
        if os.path.exists(sudoers_file):
            # 测试是否有nmcli权限
            test_result = subprocess.run(['sudo', '-n', 'nmcli', 'device', 'status'], 
                                        capture_output=True, text=True, timeout=5)
            return test_result.returncode == 0
        return False
    except Exception as e:
        print(f"Error checking WiFi permissions: {e}")
        return False


def setup_wifi_permissions():
    """自动配置WiFi管理权限"""
    try:
        import subprocess
        
        # 获取脚本路径
        script_path = '/home/admin/Documents/microscopy/setup_wifi_permissions.sh'
        
        # 检查脚本是否存在
        if not os.path.exists(script_path):
            print(f"权限设置脚本不存在: {script_path}")
            return False
        
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        
        print("正在自动配置WiFi权限...")
        send_log_message('正在自动配置WiFi权限...', 'info')
        
        # 使用sudo运行脚本（需要用户有sudo权限）
        result = subprocess.run(['sudo', 'bash', script_path], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ WiFi权限配置成功")
            send_log_message('WiFi权限配置成功', 'success')
            
            # 验证配置是否生效
            time.sleep(0.5)  # 等待配置生效
            if check_wifi_permissions():
                return True
            else:
                print("⚠️  权限配置完成，但验证失败，可能需要重新启动服务")
                send_log_message('权限配置完成，但验证失败，可能需要重新启动服务', 'warning')
                return False
        else:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            print(f"❌ WiFi权限配置失败: {error_msg}")
            send_log_message(f'WiFi权限配置失败: {error_msg}', 'error')
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ WiFi权限配置超时")
        send_log_message('WiFi权限配置超时', 'error')
        return False
    except Exception as e:
        print(f"❌ WiFi权限配置出错: {e}")
        send_log_message(f'WiFi权限配置出错: {str(e)}', 'error')
        return False


@socketio.on('get_wifi_status')
def handle_get_wifi_status():
    """获取当前WiFi连接状态 - 使用iw和nmcli，与系统WiFi Manager一致"""
    try:
        import subprocess
        import re
        
        ssid = None
        ip_address = None
        signal = None
        
        # 方法1: 使用iw获取WiFi状态（推荐，最准确）
        try:
            iw_result = subprocess.run(['sudo', 'iw', 'dev', 'wlan0', 'link'], 
                                      capture_output=True, text=True, timeout=5)
            if iw_result.returncode == 0 and 'Connected to' in iw_result.stdout:
                # 获取SSID
                for line in iw_result.stdout.split('\n'):
                    if 'SSID:' in line:
                        ssid = line.split('SSID:')[1].strip()
                    elif 'signal:' in line:
                        signal_match = re.search(r'(-?\d+)\s*dBm', line)
                        if signal_match:
                            signal_dbm = int(signal_match.group(1))
                            # 转换为百分比（-30dBm到-90dBm对应100%到0%）
                            signal = max(0, min(100, int((signal_dbm + 90) * 100 / 60)))
        except Exception as e:
            print(f"Error getting info from iw: {e}")
        
        # 方法2: 从ip命令获取IP地址（不需要sudo）
        try:
            ip_result = subprocess.run(['ip', '-4', 'addr', 'show', 'wlan0'], 
                                     capture_output=True, text=True, timeout=5)
            if ip_result.returncode == 0:
                ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_result.stdout)
                if ip_match:
                    ip_address = ip_match.group(1)
        except Exception as e:
            print(f"Error getting IP: {e}")
        
        # 方法3: 如果还没有获取到SSID，尝试从iwgetid获取
        if not ssid:
            try:
                result = subprocess.run(['sudo', 'iwgetid', '-r'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    ssid = result.stdout.strip()
            except Exception as e:
                print(f"Error getting info from iwgetid: {e}")
        
        emit('wifi_status', {
            'ssid': ssid or None,
            'ip': ip_address or None,
            'signal': signal
        })
        
    except Exception as e:
        print(f"Error getting WiFi status: {e}")
        emit('wifi_status', {
            'ssid': None,
            'ip': None,
            'signal': None
        })


@socketio.on('scan_wifi')
def handle_scan_wifi():
    """扫描可用的WiFi网络 - 使用nmcli，与系统WiFi Manager一致"""
    try:
        import subprocess
        
        send_log_message('开始扫描WiFi网络...', 'info')
        
        # 使用sudo执行nmcli扫描WiFi网络（与系统管理器一致）
        result = subprocess.run(['sudo', 'nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'], 
                              capture_output=True, text=True, timeout=30)
        
        networks = []
        
        if result.returncode == 0:
            seen_ssids = {}  # 用于去重，保留信号最强的
            
            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                
                parts = line.split(':')
                if len(parts) >= 2:
                    ssid = parts[0].strip()
                    signal_str = parts[1].strip() if len(parts) > 1 else '0'
                    security = parts[2].strip() if len(parts) > 2 else '--'
                    
                    if ssid:
                        signal = int(signal_str) if signal_str.isdigit() else 0
                        
                        # 只保留每个SSID信号最强的那个
                        if ssid not in seen_ssids or seen_ssids[ssid]['signal'] < signal:
                            seen_ssids[ssid] = {
                                'ssid': ssid,
                                'signal': signal,
                                'security': 'WPA2' if security else None
                            }
            
            networks = list(seen_ssids.values())
            networks.sort(key=lambda x: x.get('signal', 0), reverse=True)
        else:
            # 如果权限不足，尝试自动配置权限
            error_msg = result.stderr.strip() if result.stderr else 'Permission denied'
            if 'permission' in error_msg.lower() or 'sudo' in error_msg.lower():
                send_log_message('WiFi扫描失败：权限不足，正在尝试自动配置权限...', 'warning')
                
                # 尝试自动配置权限
                if setup_wifi_permissions():
                    # 配置成功后，重新尝试扫描
                    send_log_message('权限配置成功，重新尝试扫描WiFi...', 'info')
                    time.sleep(1)  # 等待配置生效
                    
                    # 重新执行扫描命令
                    retry_result = subprocess.run(['sudo', 'nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'], 
                                                  capture_output=True, text=True, timeout=30)
                    
                    if retry_result.returncode == 0:
                        # 解析网络列表
                        seen_ssids = {}
                        for line in retry_result.stdout.split('\n'):
                            if not line.strip():
                                continue
                            parts = line.split(':')
                            if len(parts) >= 2:
                                ssid = parts[0].strip()
                                signal_str = parts[1].strip() if len(parts) > 1 else '0'
                                security = parts[2].strip() if len(parts) > 2 else '--'
                                if ssid:
                                    signal = int(signal_str) if signal_str.isdigit() else 0
                                    if ssid not in seen_ssids or seen_ssids[ssid]['signal'] < signal:
                                        seen_ssids[ssid] = {
                                            'ssid': ssid,
                                            'signal': signal,
                                            'security': 'WPA2' if security else None
                                        }
                        networks = list(seen_ssids.values())
                        networks.sort(key=lambda x: x.get('signal', 0), reverse=True)
                        send_log_message(f'WiFi扫描完成，发现 {len(networks)} 个网络', 'success')
                        emit('wifi_scan_result', {
                            'success': True,
                            'networks': networks
                        })
                        return
                    else:
                        emit('wifi_scan_result', {
                            'success': False,
                            'error': '权限配置后扫描仍然失败'
                        })
                        return
                else:
                    emit('wifi_scan_result', {
                        'success': False,
                        'error': '权限不足，自动配置失败，请手动运行 sudo bash setup_wifi_permissions.sh'
                    })
                    return
        
        send_log_message(f'WiFi扫描完成，发现 {len(networks)} 个网络', 'success')
        
        emit('wifi_scan_result', {
            'success': True,
            'networks': networks
        })
        
    except subprocess.TimeoutExpired:
        send_log_message('WiFi扫描超时', 'error')
        emit('wifi_scan_result', {
            'success': False,
            'error': 'Scan timeout'
        })
    except Exception as e:
        print(f"Error scanning WiFi: {e}")
        send_log_message(f'WiFi扫描失败: {str(e)}', 'error')
        emit('wifi_scan_result', {
            'success': False,
            'error': str(e)
        })


@socketio.on('connect_wifi')
def handle_connect_wifi(data):
    """连接到WiFi网络 - 使用nmcli，与系统WiFi Manager一致"""
    try:
        ssid = data.get('ssid')
        password = data.get('password', '')
        
        if not ssid:
            emit('wifi_connect_result', {
                'success': False,
                'error': 'SSID is required'
            })
            return
        
        send_log_message(f'尝试连接到WiFi: {ssid}', 'info')
        emit('wifi_connect_result', {
            'success': 'connecting',
            'message': '正在连接...'
        })
        
        import subprocess
        
        try:
            # 使用sudo执行nmcli连接WiFi（推荐方式，与系统管理器一致）
            # nmcli会自动选择最佳信道和处理所有细节
            
            if password:
                # 加密网络连接
                result = subprocess.run([
                    'sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 'password', password
                ], capture_output=True, text=True, timeout=20)
            else:
                # 开放网络连接
                result = subprocess.run([
                    'sudo', 'nmcli', 'device', 'wifi', 'connect', ssid
                ], capture_output=True, text=True, timeout=20)
            
            if result.returncode == 0:
                send_log_message(f'WiFi连接成功: {ssid}', 'success')
                emit('wifi_connect_result', {
                    'success': True,
                    'ssid': ssid
                })
            else:
                # 解析错误信息
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip() if result.stdout else 'Connection failed'
                # 检查是否是权限问题
                if 'permission' in error_msg.lower() or 'sudo' in error_msg.lower() or 'not allowed' in error_msg.lower():
                    send_log_message('WiFi连接失败：权限不足，正在尝试自动配置权限...', 'warning')
                    
                    # 尝试自动配置权限
                    if setup_wifi_permissions():
                        # 配置成功后，重新尝试连接
                        send_log_message('权限配置成功，重新尝试连接WiFi...', 'info')
                        time.sleep(1)  # 等待配置生效
                        
                        # 重新执行连接命令
                        if password:
                            retry_result = subprocess.run([
                                'sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 'password', password
                            ], capture_output=True, text=True, timeout=20)
                        else:
                            retry_result = subprocess.run([
                                'sudo', 'nmcli', 'device', 'wifi', 'connect', ssid
                            ], capture_output=True, text=True, timeout=20)
                        
                        if retry_result.returncode == 0:
                            send_log_message(f'WiFi连接成功: {ssid}', 'success')
                            emit('wifi_connect_result', {
                                'success': True,
                                'ssid': ssid
                            })
                            return
                        else:
                            retry_error = retry_result.stderr.strip() if retry_result.stderr else retry_result.stdout.strip() if retry_result.stdout else 'Connection failed'
                            emit('wifi_connect_result', {
                                'success': False,
                                'error': f'权限配置后连接仍然失败: {retry_error}'
                            })
                            return
                    else:
                        emit('wifi_connect_result', {
                            'success': False,
                            'error': '权限不足，自动配置失败，请手动运行 sudo bash setup_wifi_permissions.sh'
                        })
                        return
                raise Exception(f"WiFi连接失败: {error_msg}")
                
        except subprocess.TimeoutExpired:
            raise Exception("Connection timeout")
        
    except Exception as e:
        print(f"Error connecting to WiFi: {e}")
        send_log_message(f'WiFi连接失败: {str(e)}', 'error')
        emit('wifi_connect_result', {
            'success': False,
            'error': str(e)
        })


@socketio.on('system_update')
def handle_system_update(data):
    """系统更新功能"""
    try:
        github_url = data.get('github_url', 'https://github.com/ctouchair/microscopy.git')
        branch = data.get('branch', 'main')
        
        send_log_message('开始系统更新...', 'info')
        emit('update_status', {'status': 'started', 'message': '正在准备更新...'})
        
        import subprocess
        import tempfile
        import shutil
        import glob
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            send_log_message('正在从GitHub下载最新代码...', 'info')
            emit('update_status', {'status': 'downloading', 'message': '正在下载最新代码...'})
            
            # 克隆仓库到临时目录
            clone_result = subprocess.run([
                'git', 'clone', '--branch', branch, '--depth', '1', 
                github_url, temp_dir + '/repo'
            ], capture_output=True, text=True, timeout=300)
            
            if clone_result.returncode != 0:
                raise Exception(f"Git clone failed: {clone_result.stderr}")
            
            send_log_message('代码下载完成，正在更新文件...', 'info')
            emit('update_status', {'status': 'updating', 'message': '正在更新系统文件...'})
            
            # 重启服务以应用更新
            send_log_message('正在重启显微镜服务以应用更新...', 'info')
            
            # 备份当前配置文件
            backup_files = [
                'settings.json',
                'params.json'
            ]
            
            backup_data = {}
            microscopy_path = '/home/admin/Documents/microscopy'
            
            for file in backup_files:
                file_path = os.path.join(microscopy_path, file)
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        backup_data[file] = f.read()
                    send_log_message(f'已备份配置文件: {file}', 'info')
            
            # 更新代码文件
            repo_path = temp_dir + '/repo'
            
            # 定义需要更新的文件和目录
            update_items = [
                'app.py',
                'camera.py',
                'motor.py',
                'utils.py',
                'hall_calibrate.py',
                'requirements.txt',
                'templates/',
                'static/',
                'microscope.service',
                '*.sh',  # 所有shell脚本
                '*.md'   # 所有文档文件
            ]
            
            updated_count = 0
            
            # 使用rsync进行文件同步，排除配置文件和版本文件
            rsync_result = subprocess.run([
                'rsync', '-av', '--exclude=settings.json', '--exclude=params.json', '--exclude=version.json',
                '--exclude=*.pyc', '--exclude=__pycache__/', '--exclude=.git/',
                repo_path + '/', microscopy_path + '/'
            ], capture_output=True, text=True, timeout=60)
            
            if rsync_result.returncode == 0:
                updated_count = rsync_result.stdout.count('>')
                send_log_message(f'成功更新 {updated_count} 个文件', 'success')
            else:
                send_log_message(f'文件同步警告: {rsync_result.stderr}', 'warning')
            
            # 恢复配置文件
            for file, content in backup_data.items():
                file_path = os.path.join(microscopy_path, file)
                with open(file_path, 'w') as f:
                    f.write(content)
                send_log_message(f'已恢复配置文件: {file}', 'info')
            
            # 设置文件权限
            send_log_message('正在设置文件权限...', 'info')
            chown_result = subprocess.run(['sudo', 'chown', '-R', 'admin:admin', microscopy_path], 
                         capture_output=True, text=True)
            if chown_result.returncode != 0:
                send_log_message(f'设置文件所有者警告: {chown_result.stderr}', 'warning')
            
            # 设置shell脚本执行权限
            for script_file in glob.glob(os.path.join(microscopy_path, '*.sh')):
                chmod_result = subprocess.run(['sudo', 'chmod', '+x', script_file], 
                             capture_output=True, text=True)
                if chmod_result.returncode != 0:
                    send_log_message(f'设置脚本权限警告: {chmod_result.stderr}', 'warning')
            
            # 更新系统服务文件
            service_file = microscopy_path + '/microscope.service'
            if os.path.exists(service_file):
                subprocess.run(['sudo', 'cp', service_file, '/etc/systemd/system/'], 
                             capture_output=True)
                subprocess.run(['sudo', 'systemctl', 'daemon-reload'], 
                             capture_output=True)
                send_log_message('系统服务文件已更新', 'info')
            
            # 保存更新后的版本号到本地文件
            try:
                # 获取最新提交的版本信息
                latest_commit_result = subprocess.run([
                    'git', '-C', repo_path, 'log', '-1', '--format=%H|%s|%ad', '--date=short'
                ], capture_output=True, text=True)
                
                if latest_commit_result.returncode == 0:
                    commit_info = latest_commit_result.stdout.strip().split('|')
                    new_version = {
                        'hash': commit_info[0][:8],
                        'full_hash': commit_info[0],
                        'message': commit_info[1],
                        'date': commit_info[2],
                        'update_time': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # 保存版本信息到本地文件
                    version_file = os.path.join(microscopy_path, 'version.json')
                    with open(version_file, 'w', encoding='utf-8') as f:
                        import json
                        json.dump(new_version, f, ensure_ascii=False, indent=2)
                    
                    send_log_message(f'版本信息已保存: {new_version["hash"]}', 'info')
                else:
                    send_log_message('无法获取更新后的版本信息', 'warning')
            except Exception as version_error:
                send_log_message(f'保存版本信息失败: {str(version_error)}', 'warning')
            
            # 发送重启通知给前端
            send_log_message('系统更新完成，正在重启服务...', 'info')
            emit('update_status', {'status': 'restarting', 'message': '正在重启服务，请稍候...'})
            
            # 延迟发送重启信号，让前端有时间接收消息
            time.sleep(1)
            emit('system_restart_required', {
                'success': True,
                'message': f'系统更新成功，共更新了 {updated_count} 个文件。服务将在5秒后重启，页面将自动刷新。',
                'updated_files': updated_count,
                'restart_delay': 5  # 5秒后重启
            })
            
            # 等待前端接收消息后再重启
            time.sleep(2)
            
            # 重启服务
            send_log_message('正在重启显微镜服务...', 'info')
            restart_result = subprocess.run(['sudo', 'systemctl', 'restart', 'microscope.service'], 
                         capture_output=True, text=True, timeout=15)
            
            if restart_result.returncode != 0:
                send_log_message(f'服务重启失败: {restart_result.stderr}', 'error')
                raise Exception(f"服务重启失败: {restart_result.stderr}")
            
            # 检查服务状态
            time.sleep(2)
            status_result = subprocess.run(['sudo', 'systemctl', 'is-active', 'microscope.service'], 
                                         capture_output=True, text=True)
            
            if status_result.stdout.strip() == 'active':
                send_log_message('系统更新完成，服务已重启', 'success')
                # 这个消息可能不会被发送，因为服务重启了
            else:
                send_log_message(f'服务状态异常: {status_result.stdout.strip()}', 'error')
                # 尝试获取服务日志
                try:
                    journal_result = subprocess.run(['sudo', 'journalctl', '-u', 'microscope.service', '-n', '10', '--no-pager'], 
                                                   capture_output=True, text=True, timeout=5)
                    if journal_result.returncode == 0:
                        send_log_message(f'服务日志: {journal_result.stdout}', 'error')
                except:
                    pass
        
    except subprocess.TimeoutExpired:
        send_log_message('系统更新超时', 'error')
        emit('update_result', {
            'success': False,
            'error': '更新操作超时'
        })
    except Exception as e:
        print(f"System update error: {e}")
        send_log_message(f'系统更新失败: {str(e)}', 'error')
        emit('update_result', {
            'success': False,
            'error': str(e)
        })
        
        # 尝试重启服务
        try:
            send_log_message('尝试重启服务...', 'info')
            restart_result = subprocess.run(['sudo', 'systemctl', 'restart', 'microscope.service'], 
                         capture_output=True, text=True, timeout=10)
            if restart_result.returncode == 0:
                send_log_message('服务已重启', 'success')
            else:
                send_log_message(f'服务重启失败: {restart_result.stderr}', 'error')
        except Exception as restart_error:
            send_log_message(f'服务重启异常: {str(restart_error)}', 'error')


@socketio.on('check_update')
def handle_check_update():
    """检查是否有可用的更新"""
    try:
        send_log_message('正在检查更新...', 'info')
        
        import subprocess
        import tempfile
        
        github_url = 'https://github.com/ctouchair/microscopy.git'
        
        # 获取远程仓库的最新提交信息
        with tempfile.TemporaryDirectory() as temp_dir:
            # 浅克隆仓库获取最新提交信息
            clone_result = subprocess.run([
                'git', 'clone', '--depth', '1', github_url, temp_dir + '/repo'
            ], capture_output=True, text=True, timeout=60)
            
            if clone_result.returncode != 0:
                raise Exception(f"无法访问远程仓库: {clone_result.stderr}")
            
            # 获取最新提交的信息
            commit_result = subprocess.run([
                'git', '-C', temp_dir + '/repo', 'log', '-1', '--format=%H|%s|%ad', '--date=short'
            ], capture_output=True, text=True)
            
            if commit_result.returncode == 0:
                commit_info = commit_result.stdout.strip().split('|')
                latest_commit = {
                    'hash': commit_info[0][:8],
                    'message': commit_info[1],
                    'date': commit_info[2]
                }
                
                # 获取当前本地版本信息（优先从保存的版本文件读取）
                local_version = "未知版本"
                local_version_info = None
                
                try:
                    # 首先尝试从本地版本文件读取
                    version_file = '/home/admin/Documents/microscopy/version.json'
                    if os.path.exists(version_file):
                        with open(version_file, 'r', encoding='utf-8') as f:
                            import json
                            local_version_info = json.load(f)
                            local_version = local_version_info.get('hash', '未知版本')
                            send_log_message(f'从本地文件读取版本: {local_version}', 'info')
                    else:
                        # 如果本地文件不存在，尝试从git获取
                        if os.path.exists('/home/admin/Documents/microscopy/.git'):
                            local_result = subprocess.run([
                                'git', '-C', '/home/admin/Documents/microscopy', 'log', '-1', '--format=%H'
                            ], capture_output=True, text=True)
                            if local_result.returncode == 0:
                                local_version = local_result.stdout.strip()[:8]
                                send_log_message(f'从Git读取版本: {local_version}', 'info')
                except Exception as e:
                    send_log_message(f'读取本地版本信息失败: {str(e)}', 'warning')
                
                has_update = latest_commit['hash'] != local_version
                
                send_log_message(f'检查完成 - 最新版本: {latest_commit["hash"]}', 'success')
                
                emit('update_check_result', {
                    'success': True,
                    'has_update': has_update,
                    'latest_version': latest_commit,
                    'current_version': local_version,
                    'current_version_info': local_version_info
                })
            else:
                raise Exception("无法获取版本信息")
    
    except Exception as e:
        print(f"Check update error: {e}")
        send_log_message(f'检查更新失败: {str(e)}', 'error')
        emit('update_check_result', {
            'success': False,
            'error': str(e)
        })


# Keep some REST endpoints for backward compatibility and file serving
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    config.is_veiwing = True  # 开始视频流
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_feed_cam1')
def video_feed_cam1():
    config.is_veiwing = True  # 开始视频流
    return Response(generate_frames_cam1(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings = config.load_settings()
    return jsonify(settings)


# Background thread to send motor position updates
def send_motor_positions():
    """Send motor positions every 200ms"""
    with open('/home/admin/Documents/microscopy/params.json', 'r', encoding='utf-8') as f:
        data_params = json.load(f)
        f.close()
    params_x = data_params['X']
    params_y = data_params['Y']
    params_z = data_params['Z']
    while True:
        try:
            # Convert steps to mm (steps_per_mm steps = 1mm)
            x_pos_mm = motor0.x_pos / motor0.xy_steps_per_mm
            y_pos_mm = motor0.y_pos / motor0.xy_steps_per_mm
            z_pos_mm = motor0.z_pos / motor0.z_steps_per_mm
            
            x_vol = round(motor0.measure_voltage('X'),4)
            y_vol = round(motor0.measure_voltage('Y'),4)
            z_vol = round(motor0.measure_voltage('Z'),4)

            x_pos_vol_mm = round(arctan_func(x_vol, params_x[0], params_x[1], params_x[2], params_x[3]), 4)
            y_pos_vol_mm = round(arctan_func(y_vol, params_y[0], params_y[1], params_y[2], params_y[3]), 4)
            z_pos_vol_mm = round(arctan_func(z_vol, params_z[0], params_z[1], params_z[2], params_z[3]), 4)
            # print(x_vol, y_vol, z_vol)

            socketio.emit('motor_positions', {
                'x_pos': round(x_pos_mm, 3),
                'y_pos': round(y_pos_mm, 3),
                'z_pos': round(z_pos_mm, 3),
                'motor_status': motor0.status,  # Add motor status for indicator
                'x_vol': x_pos_vol_mm,
                'y_vol': y_pos_vol_mm,
                'z_vol': z_pos_vol_mm
            })
             # 二者定位差距大时，以电压校准为准，因为螺纹会有回程差，只针对运动时的方向，其他方向不控制
            if abs(x_pos_mm - x_pos_vol_mm) > 0.05 and motor0.direction == 'X':
                motor0.x_pos = int(x_pos_vol_mm*motor0.xy_steps_per_mm)
            if abs(y_pos_mm - y_pos_vol_mm) > 0.05 and motor0.direction == 'Y':
                motor0.y_pos = int(y_pos_vol_mm*motor0.xy_steps_per_mm)
            if abs(z_pos_mm - z_pos_vol_mm) > 0.02 and motor0.direction == 'Z':
                motor0.z_pos = int(z_pos_vol_mm*motor0.z_steps_per_mm)

        except Exception as e:
            print(f"Error sending motor positions: {e}")
        if motor0.status: #动态时，实时保存
            time.sleep(0.1)  # 200ms frequency
        else: #静态时，缓慢保存
            time.sleep(1)  # 200ms frequency
            
            socketio.emit('target_positions_update', {
                'x_target': round(x_pos_mm, 3),
                'y_target': round(y_pos_mm, 3),
                'z_target': round(z_pos_mm, 3)
            })



def cleanup_static_files():
    """清理static文件夹下的缓存文件"""
    try:
        static_dir = '/home/admin/Documents/static'
        if os.path.exists(static_dir):
            # 删除.avi文件
            for file in os.listdir(static_dir):
                if file.endswith('.avi'):
                    file_path = os.path.join(static_dir, file)
                    try:
                        os.remove(file_path)
                        print(f"已删除缓存视频文件: {file}")
                    except Exception as e:
                        print(f"删除视频文件失败 {file}: {e}")
            
            # 删除.jpeg文件
            for file in os.listdir(static_dir):
                if file.endswith('.jpeg'):
                    file_path = os.path.join(static_dir, file)
                    try:
                        os.remove(file_path)
                        print(f"已删除缓存图片文件: {file}")
                    except Exception as e:
                        print(f"删除图片文件失败 {file}: {e}")
        
        print("缓存文件清理完成")
    except Exception as e:
        print(f"清理缓存文件时出错: {e}")


if __name__ == "__main__":
    print("Starting Microscope Control System...")
    
    # 启动时清理缓存文件
    cleanup_static_files()
    
    # 检查WiFi权限配置
    print("检查WiFi管理权限...")
    if check_wifi_permissions():
        print("✅ WiFi权限已配置")
    else:
        print("⚠️  WiFi权限未配置，正在尝试自动配置...")
        # 尝试自动配置权限
        if setup_wifi_permissions():
            print("✅ WiFi权限自动配置成功")
        else:
            print("⚠️  WiFi权限自动配置失败，WiFi功能可能无法正常工作")
            print("   请手动运行以下命令配置权限:")
            print("   sudo bash /home/admin/Documents/microscopy/setup_wifi_permissions.sh")
    
    # Start motor position update thread
    motor_position_thread = threading.Thread(target=send_motor_positions, daemon=True)
    motor_position_thread.start()
    
    print("Server starting on http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
