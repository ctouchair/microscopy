import cv2
from PIL import Image
import io
from picamera2 import Picamera2
import numpy as np
import time
from utils import load_fused_perspective_transform


class VideoCamera(object):
    def __init__(self, pi_camera: Picamera2, preview_size=(1014, 760), video_size=(2028, 1520), image_size=(4056, 3040), framerate=20):
        self.preview_size = preview_size
        self.video_size = video_size
        self.image_size = image_size
        self.picam2 = pi_camera
        self.exposure_time = 10000
        self.analogue_gain = 1
        self.r_gain, self.b_gain = 1, 1
        self.framerate = framerate
        self.pixel_size = 0.09 #um
        self.cam1_params, self.cam1_output_size = load_fused_perspective_transform('/home/admin/Documents/microscopy/fused_perspective_transform_params.json')
        self.apply_perspective = False
        self.mag_scale = 40


    def __stop__(self):
        self.picam2.stop()
    
    def preview_config(self):
        """
        预览模式设置，采集像素为2028*1520，这样才能看到全画幅以及高帧率
        """
        self.picam2.stop()
        preview_config = self.picam2.create_preview_configuration(
            main={"format": 'RGB888', "size": self.video_size},
            queue=False,
            buffer_count=3,
            controls={
                    "FrameDurationLimits": (int(1e6/self.framerate), int(1e6/self.framerate)),
                    "NoiseReductionMode": 2,          # 去噪
                    "AwbMode": 0, 
                    "ExposureTime": self.exposure_time,            # 可选：手动曝光（微秒）
                    "AnalogueGain": self.analogue_gain              # 可选：手动增益
                }
        )
        self.picam2.configure(preview_config)
        self.set_exposure()
        self.set_gain()
        self.set_framerate()
        time.sleep(0.5) #等待配置生效
        self.picam2.start()


    def capture_config(self):
        """
        拍照模式，全像素拍照
        """
        self.picam2.stop()
        capture_config = self.picam2.create_still_configuration(
            main={"format": 'RGB888', "size": self.image_size},  # 高分辨率图像（根据你的传感器调整）
            controls={"NoiseReductionMode": 2,  "AwbMode": 0}  # 启用降噪和白平衡等处理
            )
        self.picam2.configure(capture_config)
        self.picam2.start()
        rgb = self.picam2.capture_array()
        if self.apply_perspective:
            rgb = cv2.warpPerspective(rgb, self.cam1_params, self.cam1_output_size)
            rgb = rgb[1000:, 800:2700]
        return rgb


    def __start__(self):
        self.picam2.start()

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


    def set_framerate(self):
        """
        设置帧率，帧间隔为1e6/framerate
        """
        frame_duration = int(1e6/self.framerate)
        with self.picam2.controls as controls:
            controls.FrameDurationLimits = (frame_duration, frame_duration)  # 固定为self.framerate


    def get_frame(self, awb=True, flip=False, to_bgr=False, ):
        """
        用于产生视频预览和保存的图像
        """
        rgb = self.picam2.capture_array()

        if awb:
            rgb[:,:,0] = rgb[:,:,0] * self.r_gain  # 调整红色
            rgb[:,:,2] = rgb[:,:,2] * self.b_gain  # 调整绿色
        if flip:
            rgb = cv2.flip(rgb, 1)  # 0，上下翻转，1，水平翻转，-1，对角翻转
        if to_bgr:
            rgb = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB, rgb)  # 写入图象时，会替换通道
        #TO-DO提升性能，输入为低分辨率，同时输出低分辨率
        if self.apply_perspective:
            rgb = cv2.resize(rgb, self.image_size, interpolation=cv2.INTER_LINEAR)  #resize， binning
            rgb = cv2.warpPerspective(rgb, self.cam1_params, self.cam1_output_size)
            rgb = rgb[1000:, 800:2700]
            rgb_preview = cv2.resize(rgb, self.preview_size, interpolation=cv2.INTER_LINEAR)  #resize， binning
            rgb = cv2.resize(rgb, self.video_size, interpolation=cv2.INTER_LINEAR)  #resize， binning
            # TO-DO视频录制失败
        else:
            if rgb.shape[0] > self.preview_size[0]:  #默认是video_size采集图像
                rgb_preview = cv2.resize(rgb, self.preview_size, interpolation=cv2.INTER_LINEAR)  #resize， binning
            else:
                rgb_preview = rgb

        #PIL编码
        pil_image = Image.fromarray(rgb_preview)
        # 使用Pillow进行编码
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='jpeg')
        return img_byte_arr.getvalue(), rgb
    

    # def get_frame(self):
    #     data = io.BytesIO()
    #     picam2.capture_file(data, format='jpeg')
    #     return img_byte_arr.getvalue()