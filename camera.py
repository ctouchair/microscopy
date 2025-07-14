import cv2
from PIL import Image
import io
from picamera2 import Picamera2
import numpy as np

class VideoCamera(object):
    def __init__(self, pi_camera: Picamera2, size=(1600, 1200)):
        self.src_width, self.src_height = 3200, 2400
        self.size = size
        self.picam2 = pi_camera
        self.picam2.framerate = 30  # 每秒30帧
        self.exposure_time = 10000
        self.analogue_gain = 1
        self.r_gain = 0.674
        self.b_gain = 0.576


    def __stop__(self):
        self.picam2.stop()
    
    def camera_config(self):
        self.picam2.configure(self.picam2.create_preview_configuration(main={"format": 'YUV420', "size": (self.src_width, self.src_height)}, queue=False))
        self.picam2.start()
        self.set_exposure()
        self.set_gain()
    

    def set_exposure(self):
        """
        设置曝光时间和模拟增益
        :param exposure_time: 曝光时间，单位微秒
        """
        with self.picam2.controls as controls:
            controls.ExposureTime = self.exposure_time
    

    def set_gain(self):
        """
        :param analogue_gain: 模拟增益(0--1)
        """
        with self.picam2.controls as controls:
            controls.AnalogueGain = self.analogue_gain


    def get_frame(self):
        yuv420 = self.picam2.capture_array()
        rgb = cv2.cvtColor(yuv420, cv2.COLOR_YUV420p2BGR)  #转换耗时30 ms
        if rgb.shape[0] > self.size[0]:
            rgb = cv2.resize(rgb, self.size, interpolation=cv2.INTER_LINEAR)  #resize， binning
        else:
            pass
        rgb[:,:,0] = rgb[:,:,0] * self.r_gain  # 调整红色
        rgb[:,:,2] = rgb[:,:,2] * self.b_gain  # 调整绿色
        rgb = np.clip(rgb.astype(np.uint8), 0, 255)
        #PIL编码
        pil_image = Image.fromarray(rgb)
        # 使用Pillow进行编码
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='jpeg')
        return img_byte_arr.getvalue(), rgb

