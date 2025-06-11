from flask import Flask, render_template, Response, jsonify, send_file, request, send_from_directory
from tqdm import tqdm
import time
import os
from picamera2 import Picamera2
from camera import VideoCamera
import multiprocessing
import cv2
import threading


app = Flask(__name__)

pic_size = (int(2000), int(1500))  # 设置图像大小, width*height
video_size = (int(1200), int(800))  # 设置视频大小, width*height
cam0 = VideoCamera(Picamera2(), video_size)
# 控制录像状态
is_recording = False
video_writer = None


# 存储照片和录像的目录
SAVE_DIR = '/static'
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

queues_dict = {
    'frame': multiprocessing.Queue(),
    'focus_image': multiprocessing.Queue(),
}


# 开启摄像头
def generate_frames():
    cam0.__stop__()
    time.sleep(1)
    cam0.camera_config()
    time.sleep(1)
    pbar = tqdm(total=0, dynamic_ncols=True)
    while True:
        frame, rgb = cam0.get_frame()
        if queues_dict['frame'].empty():queues_dict['frame'].put(rgb)
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        pbar.update(1)  # 更新进度条


# 录制视频
def record_video():
    global is_recording, video_writer, current_video_filename
    cam0.size = video_size
    rgb = queues_dict['frame'].get()
    time.sleep(0.1)  # 等待队列中的数据稳定
    fourcc = cv2.VideoWriter_fourcc(*'XVID')  # 使用mp4v编码
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    current_video_filename = os.path.join(SAVE_DIR, f'{timestamp}.avi')
    video_writer = cv2.VideoWriter(current_video_filename, fourcc, 20, video_size, isColor=True)
    i = 0
    while is_recording:
        rgb = queues_dict['frame'].get()
        if rgb is not None and i < 20*1000:
            video_writer.write(rgb)
        else:
            is_recording = False
        i += 1
    video_writer.release()


@app.route('/')
def index():
    return render_template('index_app.html')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/take_picture')
def take_picture():
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    file_path = os.path.join(SAVE_DIR, f'{timestamp}.jpeg')
    cam0.size = pic_size
    rgb = queues_dict['frame'].get()  # 确保队列中有数据
    time.sleep(0.1)  #释放掉旧的图片
    rgb = queues_dict['frame'].get()  # 确保队列中有最新数据
    cv2.imwrite(file_path, rgb)  # 保存图像文件
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
            # return jsonify({"message": f"Recording stopped{size}", "video_file": current_video_filename})
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
