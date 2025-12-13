import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import numpy as np
from rpi_hardware_pwm import HardwarePWM


def setup(IN1, IN2, IN3, IN4):
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location
    GPIO.setup(IN1, GPIO.OUT)      # Set pin's mode is output
    GPIO.setup(IN2, GPIO.OUT)
    GPIO.setup(IN3, GPIO.OUT)
    GPIO.setup(IN4, GPIO.OUT)

    
def direction(pos='X'):
    if pos == 'X':
        IN1 = 7    # pin32
        IN2 = 13
        IN3 = 15
        IN4 = 16
    elif pos == 'Y':
        IN1 = 18    # pin32
        IN2 = 22
        IN3 = 29
        IN4 = 31
    elif pos == 'Z':
        IN1 = 36    # pin32
        IN2 = 37
        IN3 = 38
        IN4 = 40
    else:
        IN1, IN2, IN3, IN4 = None, None, None, None
    return IN1, IN2, IN3, IN4


def setStep(IN1, IN2, IN3, IN4, w1, w2, w3, w4):
    GPIO.output(IN1, w1)
    GPIO.output(IN2, w2)
    GPIO.output(IN3, w3)
    GPIO.output(IN4, w4)


def gpio_setup():
    for pos in ["X", "Y", "Z"]:
        IN1, IN2, IN3, IN4 = direction(pos)
        setup(IN1, IN2, IN3, IN4)

class motor():
    def __init__(self):
        gpio_setup()
        self.direction = 'X'
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.ads = ADS.ADS1115(self.i2c, address=0x49)

        self.channel_Z = AnalogIn(self.ads, ADS.P0)# , ADS.P3
        self.channel_Y = AnalogIn(self.ads, ADS.P1)# , ADS.P3
        self.channel_X = AnalogIn(self.ads, ADS.P2)#, ADS.P3
        self.channel_R = AnalogIn(self.ads, ADS.P3)
       
        self.status = False
        self.x_pos = 0  #记录运动步数
        self.y_pos = 0  
        self.z_pos = 0
        self.focus = False
        self.focus_pos = 0
        self.focus_get = False
        
        # 默认步数参数
        self.xy_steps_per_mm = 1450/1.5
        self.z_steps_per_mm = 1450
        
        # 从settings.json读取步数参数
        self.load_steps_per_mm()
        
        # 默认step_sign值
        self.step_sign_x, self.step_sign_y, self.step_sign_z = -1, -1, 1
        
        # 从params.json读取step_sign参数
        self.load_step_signs()

        self.led_cycle0, self.led_cycle1 = 0, 0
        self.pwm0 = HardwarePWM(pwm_channel=0, hz=100, chip=0)  # 0通道对应12，1--13，2--18，3--19
        self.pwm0.start(self.led_cycle0) # full duty cycle
        self.pwm1 = HardwarePWM(pwm_channel=1, hz=100, chip=0)  # 0通道对应12，1--13，2--18，3--19
        self.pwm1.start(self.led_cycle1) # full duty cycle

    def load_steps_per_mm(self):
        """从settings.json文件中读取步数参数"""
        import json
        import os
        
        settings_file = '/home/admin/Documents/microscopy/settings.json'
        
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # 读取xy_steps_per_mm参数
                if 'xy_steps_per_mm' in settings:
                    self.xy_steps_per_mm = settings['xy_steps_per_mm']
                    print(f"Loaded xy_steps_per_mm: {self.xy_steps_per_mm}")
                else:
                    print("No xy_steps_per_mm found in settings.json, using default value")
                
                # 读取z_steps_per_mm参数
                if 'z_steps_per_mm' in settings:
                    self.z_steps_per_mm = settings['z_steps_per_mm']
                    print(f"Loaded z_steps_per_mm: {self.z_steps_per_mm}")
                else:
                    print("No z_steps_per_mm found in settings.json, using default value")
            else:
                print(f"settings.json not found at {settings_file}, using default steps_per_mm values")
                
        except Exception as e:
            print(f"Error loading steps_per_mm from settings.json: {e}")
            print("Using default steps_per_mm values")

    def load_step_signs(self):
        """从params.json文件中读取step_sign参数"""
        import json
        import os
        
        params_file = '/home/admin/Documents/microscopy/params.json'
        
        try:
            if os.path.exists(params_file):
                with open(params_file, 'r', encoding='utf-8') as f:
                    data_params = json.load(f)
                
                # 读取step_signs参数
                if 'step_signs' in data_params:
                    step_signs = data_params['step_signs']
                    
                    if 'X' in step_signs:
                        self.step_sign_x = step_signs['X']
                        print(f"Loaded step_sign_x: {self.step_sign_x}")
                    
                    if 'Y' in step_signs:
                        self.step_sign_y = step_signs['Y']
                        print(f"Loaded step_sign_y: {self.step_sign_y}")
                    
                    if 'Z' in step_signs:
                        self.step_sign_z = step_signs['Z']
                        print(f"Loaded step_sign_z: {self.step_sign_z}")
                else:
                    print("No step_signs found in params.json, using default values")
            else:
                print(f"params.json not found at {params_file}, using default step_sign values")
                
        except Exception as e:
            print(f"Error loading step_signs from params.json: {e}")
            print("Using default step_sign values")

    def move(self, step=0):
        IN1, IN2, IN3, IN4 = direction(pos=self.direction)
        self.forward(IN1, IN2, IN3, IN4, 0.002, int(step))

    def move_to_target(self, target_pose=0, delay=0.002):
        IN1, IN2, IN3, IN4 = direction(pos=self.direction)
        if IN1 is not None:
            if self.direction == 'X':
                step_sign = self.step_sign_x
                real_pos = self.x_pos
            elif self.direction == 'Y':
                step_sign = self.step_sign_y
                real_pos = self.y_pos
            elif self.direction == 'Z':
                step_sign = self.step_sign_z
                real_pos = self.z_pos
            steps = target_pose - real_pos
            while abs(steps) > 1:
                if not self.status:
                    break
                elif steps*step_sign > 0:
                    setStep(IN1, IN2, IN3, IN4, 1, 0, 0, 1)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 0, 1, 1)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 1, 1, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 1, 1, 0, 0)
                    time.sleep(delay)
                elif steps*step_sign < 0:
                    setStep(IN1, IN2, IN3, IN4, 1, 0, 0, 1)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 1, 1, 0, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 1, 1, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 0, 1, 1)
                    time.sleep(delay)
                if self.direction == 'X':
                    self.x_pos += np.sign(steps)
                    real_pos = self.x_pos
                elif self.direction == 'Y':
                    self.y_pos += np.sign(steps)
                    real_pos = self.y_pos
                elif self.direction == 'Z':
                    self.z_pos += np.sign(steps)
                    real_pos = self.z_pos
                steps = target_pose - real_pos
            setStep(IN1, IN2, IN3, IN4, 0, 0, 0, 0)
            self.status = False
        else:
            print('GPIO IN Error !!')


    
    def measure_voltage(self, pos_direct): #切换方向时第二次测量才准，需要先读取一次
        if pos_direct == 'X':
            voltage = round(self.channel_X.voltage, 4)
        elif pos_direct == 'Y':
            voltage = round(self.channel_Y.voltage, 4)
        elif pos_direct == 'Z':
            voltage = round(self.channel_Z.voltage, 4)
        else:
            voltage = round(self.channel_R.voltage, 4)
        return voltage
    

    def forward(self, IN1, IN2, IN3, IN4, delay, steps):  #启动频率550Hz，因此最小delay 2ms
        if IN1 is not None:
            if self.direction == 'X':
                step_sign = self.step_sign_x
            elif self.direction == 'Y':
                step_sign = self.step_sign_y
            elif self.direction == 'Z':
                step_sign = self.step_sign_z
            for i in range(0, abs(steps)):
                if not self.status:
                    break
                elif steps*step_sign > 0:
                    setStep(IN1, IN2, IN3, IN4, 1, 0, 0, 1)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 0, 1, 1)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 1, 1, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 1, 1, 0, 0)
                    time.sleep(delay)
                elif steps*step_sign < 0:
                    setStep(IN1, IN2, IN3, IN4, 1, 0, 0, 1)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 1, 1, 0, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 1, 1, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 0, 1, 1)
                    time.sleep(delay)
                if self.direction == 'X':
                    self.x_pos += np.sign(steps)
                elif self.direction == 'Y':
                    self.y_pos += np.sign(steps)
                elif self.direction == 'Z':
                    self.z_pos += np.sign(steps)
            setStep(IN1, IN2, IN3, IN4, 0, 0, 0, 0)
            self.status = False
        else:
            print('GPIO IN Error !!')


    def set_led_power0(self):
        self.pwm0.change_duty_cycle(self.led_cycle0)
        self.pwm0.change_frequency(25_000)

    def set_led_power1(self):
        self.pwm1.change_duty_cycle(self.led_cycle1)
        self.pwm1.change_frequency(25_000)


if __name__ == '__main__':
    motor_move = motor()
    motor_move.direction = 'Z'
    i = 0

    while True:
        x_vol = motor_move.measure_voltage('X')
        y_vol = motor_move.measure_voltage('Y')
        z_vol = motor_move.measure_voltage('Z')
        r_vol = motor_move.measure_voltage('R')
        print(x_vol, y_vol, z_vol, r_vol)
        time.sleep(0.5)
        i += 1
