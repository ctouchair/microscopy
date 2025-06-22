import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import numpy as np


def setup(IN1, IN2, IN3, IN4):
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location
    GPIO.setup(IN1, GPIO.OUT)      # Set pin's mode is output
    GPIO.setup(IN2, GPIO.OUT)
    GPIO.setup(IN3, GPIO.OUT)
    GPIO.setup(IN4, GPIO.OUT)

def direction(pos='X'):
    if pos == 'Z':
        IN1 = 32    # pin32
        IN2 = 36
        IN3 = 38
        IN4 = 40
    elif pos == 'X':
        IN1 = 11    # pin32
        IN2 = 13
        IN3 = 15
        IN4 = 19
    elif pos == 'Y':
        IN1 = 31    # pin32
        IN2 = 33
        IN3 = 35
        IN4 = 37
    else:
        print('Error Direction, Back to Y')
        IN1, IN2, IN3, IN4 = 7, 11, 13, 15
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
        self.ads = ADS.ADS1115(self.i2c)
        # Select Analog Input Channel (A0)

        self.channel_Y = AnalogIn(self.ads, ADS.P3)
        self.channel_Z = AnalogIn(self.ads, ADS.P1)
        self.channel_X = AnalogIn(self.ads, ADS.P0)
        self.status = True
        self.x_pos = 0  #记录运动步数
        self.y_pos = 0
        self.z_pos = 0
        self.z_focus = 0
        self.focus_sharpness = 0
        self.focus_vol = 0


    def move(self, step=0):
        IN1, IN2, IN3, IN4 = direction(pos=self.direction)
        self.forward(IN1, IN2, IN3, IN4, 0.002, int(step))

    
    def measure_voltage(self, pos_direct): #切换方向时第二次测量才准，需要先读取一次
        self.move(1)  # 测量前需要先移动1步，不知道为啥
        if pos_direct == 'X':
            voltage = round(self.channel_X.voltage, 4)
        elif pos_direct == 'Y':
            voltage = round(self.channel_Y.voltage, 4)
        elif pos_direct == 'Z':
            voltage = round(self.channel_Z.voltage, 4)
        return voltage
    
    def forward(self, IN1, IN2, IN3, IN4, delay, steps):  #启动频率550Hz，因此最小delay 2ms
        if steps > 0:
            for i in range(0, steps):
                if not self.status:
                    break
                else:
                    setStep(IN1, IN2, IN3, IN4, 1, 0, 0, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 1, 0, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 0, 1, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 0, 0, 1)
                    time.sleep(delay)
                    if self.direction == 'X':
                        self.x_pos += 1
                    elif self.direction == 'Y':
                        self.y_pos += 1
                    elif self.direction == 'Z':
                        self.z_pos += 1
        else:
            for i in range(0, abs(steps)):
                if not self.status:
                    break
                else:
                    setStep(IN1, IN2, IN3, IN4, 0, 0, 0, 1)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 0, 1, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 0, 1, 0, 0)
                    time.sleep(delay)
                    setStep(IN1, IN2, IN3, IN4, 1, 0, 0, 0)
                    time.sleep(delay)
                    if self.direction == 'X':
                        self.x_pos -= 1
                    elif self.direction == 'Y':
                        self.y_pos -= 1
                    elif self.direction == 'Z':
                        self.z_pos -= 1
        self.status = False



# motor_move = motor()
# while True:
#     print(motor_move.measure_voltage('Z'))
#     time.sleep(0.5)
# motor_move.direction = 'Z'
# motor_move.status = True
# motor_move.move(500)

# end_voltage = 1.7
# step = 256
# data = []
# x_end = [1.24, 2.06]
# y_end = [1.33, 2.12]
# z_end = [1.11, 1.97]
# step_cnt = 0
# if motor_move.direction == 'X':
#     end = x_end
# elif motor_move.direction == 'Y':
#     end = y_end
# elif motor_move.direction == 'Z':
#     end = z_end
# while end_voltage < end[1] and end_voltage > end[0]:
#     start_voltage = motor_move.measure_voltage()
#     motor_move.move(step)
#     step_cnt += step
#     end_voltage = motor_move.measure_voltage()
#     delta_voltage = end_voltage - start_voltage
#     if delta_voltage == 0:
#         continue
#     else:
#         step_ratio = int(step/(end_voltage - start_voltage))
#         time.sleep(0.1)
#         data.append([step_ratio, end_voltage, step_cnt])
#         print(f'{step_ratio}, {end_voltage}, {step_cnt}')
# np.savetxt('data.txt',data)
