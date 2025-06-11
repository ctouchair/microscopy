import cv2
from PIL import Image
import io
from picamera2 import Picamera2

class VideoCamera(object):
    def __init__(self, pi_camera: Picamera2, size=(1200, 800)):
        self.src_width, self.src_height = 3200, 2400
        self.size = size
        self.picam2 = pi_camera
        self.picam2.framerate = 20  # 每秒30帧
        self.exposure_time = 1000
        self.analogue_gain = 1.0

    def __stop__(self):
        self.picam2.stop()
    
    def camera_config(self):
        self.picam2.configure(self.picam2.create_preview_configuration(main={"format": 'YUV420', "size": (self.src_width, self.src_height)}, queue=False))
        self.picam2.start()
        with self.picam2.controls as controls:
            controls.ExposureTime = self.exposure_time
            controls.AnalogueGain = self.analogue_gain


    def get_frame(self):
        yuv420 = self.picam2.capture_array()
        rgb = cv2.cvtColor(yuv420, cv2.COLOR_YUV420p2RGB)  #转换耗时30 ms
        if rgb.shape[0] > self.size[0]:
            rgb = cv2.resize(rgb, self.size, interpolation=cv2.INTER_LINEAR)  #resize， binning
        else:
            pass
        #PIL编码
        pil_image = Image.fromarray(rgb)
        # 使用Pillow进行编码
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='jpeg')
        return img_byte_arr.getvalue(), rgb
    
