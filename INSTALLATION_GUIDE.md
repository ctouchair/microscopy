# 显微镜控制系统安装指南

## 系统要求

### 硬件要求
- **树莓派5** (推荐4GB或8GB内存版本)
- **MicroSD卡** (至少32GB，Class 10或更高速度)
- **摄像头模块** (兼容IMX477和IMX219传感器)
- **GPIO硬件** (电机控制器、传感器等)

### 操作系统
- **Raspberry Pi OS** (基于Debian 12 Bookworm)
- **Python 3.11** (系统预装)

## 安装步骤

### 1. 系统准备

```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y

# 安装系统依赖
sudo apt install -y python3-pip python3-venv python3-dev
sudo apt install -y libatlas-base-dev libhdf5-dev libhdf5-serial-dev
sudo apt install -y libjasper-dev libqtgui4 libqt4-test
sudo apt install -y libavcodec-dev libavformat-dev libswscale-dev
sudo apt install -y wireless-tools wpasupplicant dhcpcd5
```

### 2. 创建虚拟环境

```bash
# 进入项目目录
cd /home/admin/Documents

# 创建Python虚拟环境
python3 -m venv micro_env

# 激活虚拟环境
source micro_env/bin/activate
```

### 3. 安装Python依赖

#### 方法1: 使用requirements.txt (推荐)

```bash
# 确保在虚拟环境中
source /home/admin/Documents/micro_env/bin/activate

# 安装所有依赖
pip install -r /home/admin/Documents/project/requirements.txt
```

#### 方法2: 手动安装主要包

```bash
# Web框架
pip install Flask==2.2.2 Flask-SocketIO==5.5.1

# 图像处理
pip install Pillow==9.4.0 numpy==1.24.2

# 树莓派摄像头
pip install picamera2==0.3.27

# 硬件控制
pip install RPi.GPIO==0.7.1
pip install adafruit-circuitpython-ads1x15==2.4.4
pip install adafruit-blinka==8.66.0
pip install rpi-hardware-pwm==0.3.0

# 科学计算
pip install scipy==1.10.1

# 其他工具
pip install tqdm==4.64.1 requests==2.28.1
```

### 4. OpenCV安装

OpenCV在树莓派上需要特殊处理：

#### 方法1: 使用预编译包 (推荐)

```bash
# 安装系统预编译的OpenCV
sudo apt install -y python3-opencv

# 或者使用pip安装（可能需要很长时间编译）
pip install opencv-python==4.8.1.78
```

#### 方法2: 使用系统包

```bash
# 安装系统OpenCV包
sudo apt install -y python3-opencv
sudo apt install -y libopencv-dev python3-opencv
```

### 5. 硬件权限配置

```bash
# 添加用户到必要的组
sudo usermod -a -G gpio,spi,i2c,video admin

# 启用SPI和I2C接口
sudo raspi-config
# 选择 Interfacing Options -> SPI -> Enable
# 选择 Interfacing Options -> I2C -> Enable
# 选择 Interfacing Options -> Camera -> Enable
```

### 6. WiFi功能权限设置

```bash
# 运行WiFi权限设置脚本
cd /home/admin/Documents/project
sudo bash setup_wifi_permissions.sh
```

### 7. 设置自启动服务

```bash
# 安装自启动服务
cd /home/admin/Documents/project
sudo bash install_autostart.sh
```

## 验证安装

### 1. 测试Python依赖

```bash
# 激活虚拟环境
source /home/admin/Documents/micro_env/bin/activate

# 测试主要模块导入
python3 -c "
import flask
import cv2
import numpy as np
import RPi.GPIO as GPIO
from picamera2 import Picamera2
print('所有主要模块导入成功！')
"
```

### 2. 测试硬件功能

```bash
# 测试摄像头
python3 -c "
from picamera2 import Picamera2
picam2 = Picamera2()
print('摄像头初始化成功')
picam2.close()
"

# 测试GPIO
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BOARD)
print('GPIO初始化成功')
GPIO.cleanup()
"
```

### 3. 测试系统服务

```bash
# 运行完整测试
bash /home/admin/Documents/project/test_autostart.sh

# 测试WiFi功能
bash /home/admin/Documents/project/test_wifi_feature.sh
```

### 4. 手动启动测试

```bash
# 激活虚拟环境
source /home/admin/Documents/micro_env/bin/activate

# 手动运行应用
cd /home/admin/Documents/project
python3 app.py
```

访问 `http://[树莓派IP]:5000` 查看界面。

## 故障排除

### 常见问题

#### 1. OpenCV安装失败

```bash
# 增加swap空间
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# 修改 CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# 重新安装
pip install opencv-python
```

#### 2. 摄像头权限问题

```bash
# 检查摄像头设备
ls -l /dev/video*

# 添加用户到video组
sudo usermod -a -G video admin

# 重启系统
sudo reboot
```

#### 3. GPIO权限问题

```bash
# 检查GPIO权限
ls -l /dev/gpiomem

# 添加用户到gpio组
sudo usermod -a -G gpio admin
```

#### 4. 服务启动失败

```bash
# 查看服务日志
sudo journalctl -u microscope.service -f

# 检查Python路径
which python3
/home/admin/Documents/micro_env/bin/python --version
```

### 性能优化

#### 1. 内存优化

```bash
# 增加GPU内存分配
sudo raspi-config
# Advanced Options -> Memory Split -> 128
```

#### 2. 系统优化

```bash
# 禁用不必要的服务
sudo systemctl disable bluetooth
sudo systemctl disable hciuart

# 启用性能模式
echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

## 备份和恢复

### 创建系统备份

```bash
# 备份项目文件
tar -czf microscope_backup_$(date +%Y%m%d).tar.gz /home/admin/Documents/project/

# 备份虚拟环境
tar -czf venv_backup_$(date +%Y%m%d).tar.gz /home/admin/Documents/micro_env/
```

### 恢复系统

```bash
# 恢复项目文件
tar -xzf microscope_backup_YYYYMMDD.tar.gz -C /

# 恢复虚拟环境
tar -xzf venv_backup_YYYYMMDD.tar.gz -C /

# 重新设置权限
sudo bash /home/admin/Documents/project/setup_wifi_permissions.sh
sudo bash /home/admin/Documents/project/install_autostart.sh
```

## 更新和维护

### 更新系统

```bash
# 停止服务
sudo systemctl stop microscope.service

# 更新代码
cd /home/admin/Documents/project
git pull  # 如果使用git

# 更新依赖
source /home/admin/Documents/micro_env/bin/activate
pip install -r requirements.txt --upgrade

# 重启服务
sudo systemctl start microscope.service
```

### 日志管理

```bash
# 查看应用日志
sudo journalctl -u microscope.service --since today

# 清理旧日志
sudo journalctl --vacuum-time=7d
```

## 技术支持

如遇到问题，请检查：

1. **系统日志**: `sudo journalctl -u microscope.service -f`
2. **硬件连接**: 确保所有硬件正确连接
3. **权限设置**: 运行测试脚本验证权限
4. **网络配置**: 确保WiFi和网络设置正确

完成安装后，系统将在开机时自动启动，可通过Web界面访问所有功能。 