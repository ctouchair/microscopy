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

        self.channel_Z = AnalogIn(self.ads, ADS.P0, ADS.P3)#
        self.channel_Y = AnalogIn(self.ads, ADS.P1, ADS.P3)#
        self.channel_X = AnalogIn(self.ads, ADS.P2, ADS.P3)#, ADS.P3
        self.channel_R = AnalogIn(self.ads, ADS.P3)
       
        self.status = False
        self.x_pos = 0  #记录运动步数
        self.y_pos = 0  
        self.z_pos = 0
        self.focus = False
        self.focus_pos = 0
        self.focus_get = False
        self.steps_per_mm = 1450

        self.led_cycle0, self.led_cycle1 = 0, 0
        self.pwm0 = HardwarePWM(pwm_channel=0, hz=100, chip=0)  # 0通道对应12，1--13，2--18，3--19
        self.pwm0.start(self.led_cycle0) # full duty cycle
        self.pwm1 = HardwarePWM(pwm_channel=1, hz=100, chip=0)  # 0通道对应12，1--13，2--18，3--19
        self.pwm1.start(self.led_cycle1) # full duty cycle


    def move(self, step=0):
        IN1, IN2, IN3, IN4 = direction(pos=self.direction)
        self.forward(IN1, IN2, IN3, IN4, 0.002, int(step))

    
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
            if steps > 0:
                for i in range(0, steps):
                    if not self.status:
                        setStep(IN1, IN2, IN3, IN4, 0, 0, 0, 0)
                        break
                    else:
                        setStep(IN1, IN2, IN3, IN4, 1, 0, 0, 1)
                        time.sleep(delay)
                        setStep(IN1, IN2, IN3, IN4, 0, 0, 1, 1)
                        time.sleep(delay)
                        setStep(IN1, IN2, IN3, IN4, 0, 1, 1, 0)
                        time.sleep(delay)
                        setStep(IN1, IN2, IN3, IN4, 1, 1, 0, 0)
                        time.sleep(delay)
                        setStep(IN1, IN2, IN3, IN4, 0, 0, 0, 0)
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
                        setStep(IN1, IN2, IN3, IN4, 1, 0, 0, 1)
                        time.sleep(delay)
                        setStep(IN1, IN2, IN3, IN4, 1, 1, 0, 0)
                        time.sleep(delay)
                        setStep(IN1, IN2, IN3, IN4, 0, 1, 1, 0)
                        time.sleep(delay)
                        setStep(IN1, IN2, IN3, IN4, 0, 0, 1, 1)
                        time.sleep(delay)
                        if self.direction == 'X':
                            self.x_pos -= 1
                        elif self.direction == 'Y':
                            self.y_pos -= 1
                        elif self.direction == 'Z':
                            self.z_pos -= 1
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

# motor_move = motor()
# motor_move.direction = 'Z'
# i = 0
# # led_power = [1, 0.3, 0.5, 0.7, 0.8, 0.9]

# while True:
#     # motor_move.status = True
#     # motor_move.move(-300)
#     x_vol = motor_move.measure_voltage('X')
#     y_vol = motor_move.measure_voltage('Y')
#     z_vol = motor_move.measure_voltage('Z')
#     r_vol = motor_move.measure_voltage('R')
#     print(x_vol, y_vol, z_vol, r_vol)
#     # motor_move.status = True
#     # motor_move.move(300)
#     # print(x_vol, y_vol, z_vol, r_vol)
#     # motor_move.led_cycle1 = led_power[-int(i%len(led_power))]
#     # motor_move.set_led1_power()
#     time.sleep(0.5)
#     i += 1


# step = 128
# motor_move.status = True
# motor_move.move(step)
# time.sleep(0.01)
# data = []
# vol = 1.7
# while 1<vol<1.8:
#     motor_move.status = True
#     motor_move.move(step)
#     time.sleep(0.01)
#     vol = motor_move.measure_voltage('Z')
#     data.append([motor_move.z_pos, vol])
#     print(vol, motor_move.z_pos)
# np.savetxt('data.txt',data)
