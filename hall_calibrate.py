from motor import motor
import time
import numpy as np
from scipy.optimize import curve_fit
import json
import os
"""
X轴 Hall 传感器标定,电压范围1.3~2V
Y轴 Hall 传感器标定,电压范围1.3~2V
Z轴 Hall 传感器标定,电压范围1~1.8V
在边缘区域会有大幅畸变，导致校准不准确，应该去除边缘区域
电机运动的系数为1450steps/mm
"""


def arctan_func(x, A, B, C, D):
    return A * np.arctan(B*(x-C)) + D


class hall_calibrate:
    def __init__(self):
        self.motor_move = motor()
        self.step = 128
        self.step_ratio = 1450
        self.direction = 'X'
        self.json_file = 'params.json'
        self.load_json()
    
    def load_json(self):
        if os.path.exists(self.json_file):
            with open(self.json_file, 'r', encoding='utf-8') as f:
                self.data_params = json.load(f)
        else:  #如果文件不存在，则创建一个空字典
            self.data_params = {}


    def move_to_end(self, bool_end=False):
        self.data = []
        self.motor_move.status = True
        self.motor_move.direction = self.direction
        self.motor_move.move(self.step)
        time.sleep(0.01)
        vol = self.motor_move.measure_voltage(self.direction)
        i = 0
        if self.direction == 'X':
            self.step = np.sign(vol - 1.60001)*abs(self.step)*(-1 if bool_end is True else 1 )
            self.motor_move.x_pos = 0
        elif self.direction == 'Y':
            self.step = np.sign(vol - 1.60001)*abs(self.step)*(-1 if bool_end is True else 1)
            self.motor_move.y_pos = 0
        elif self.direction == 'Z':
            self.step = int(np.sign(vol - 1.40001)*abs(self.step)/2)*(-1 if bool_end is True else 1)  #Z轴范围小一点，因此步长除以2
            self.motor_move.z_pos = 0
        print(vol, self.step, self.direction)
        while True:
            if bool_end is True:
                if i >2:
                    if abs(self.data[i-1][0] - self.data[i-3][0]) <= 0.004:
                        break
            else:
                if i > 10:
                    if abs(self.data[i-1][0] - self.data[i-3][0]) <= 0.004:
                        break
            self.motor_move.status = True
            self.motor_move.move(self.step)
            time.sleep(0.01)
            vol = self.motor_move.measure_voltage(self.direction)
            if self.direction == 'X':
                self.data.append([vol, self.motor_move.x_pos,  self.motor_move.x_pos/self.step_ratio])
                print(vol, self.motor_move.x_pos, self.motor_move.x_pos/self.step_ratio)
            elif self.direction == 'Y':
                self.data.append([vol, self.motor_move.y_pos, self.motor_move.y_pos/self.step_ratio])
                print(vol, self.motor_move.y_pos, self.motor_move.y_pos/self.step_ratio)
            elif self.direction == 'Z':
                self.data.append([vol, self.motor_move.z_pos, self.motor_move.z_pos/self.step_ratio])
                print(vol, self.motor_move.z_pos, self.motor_move.z_pos/self.step_ratio)
            i += 1
        np.savetxt('data.txt',self.data)
    
    def fit_data(self):
        x, y = np.array(self.data)[:, 0], np.array(self.data)[:, 2]
        if x[-1] > 1.5:
            x = x[5:-20]
            y = y[5:-20]-np.min(y)
        else:
            x = x[20:-5]
            y = y[20:-5]-np.min(y)
        p0 = [np.ptp(y)/2, 3, 1.5, 0]  # initial guess
        params, covariance = curve_fit(arctan_func, x, y, p0=p0, maxfev=20000)
        print(params, np.mean(abs(arctan_func(x, *params)-y))*1000)
        self.data_params[self.direction] = params.tolist()
        with open(self.json_file, 'w') as f:
            json.dump(self.data_params, f, ensure_ascii=False, indent=4)
    
    def back_to_origin(self):
        self.motor_move.move(0)
        vol = self.motor_move.measure_voltage(self.direction)
        if self.direction == 'X' or self.direction == 'Y':
            orign_vol = self.data_params[self.direction][2]
        else:
            orign_vol = 1.6
        if vol > orign_vol:
            step = abs(self.step)
        else:
            step = -abs(self.step)
        while abs(vol-orign_vol) > 0.05:
            self.motor_move.status = True
            self.motor_move.move(step)
            time.sleep(0.01)
            vol = self.motor_move.measure_voltage(self.direction)
            print(vol)


if __name__ == '__main__':
    hall_calibrate = hall_calibrate()
    hall_calibrate.direction = 'Y'
    hall_calibrate.move_to_end(bool_end=True) #先移动到边缘位置
    hall_calibrate.move_to_end(bool_end=False) #再移动完整行程
    hall_calibrate.fit_data()
    hall_calibrate.back_to_origin()
