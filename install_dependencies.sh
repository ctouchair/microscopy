#!/bin/bash

# 显微镜控制系统依赖包安装脚本
# 适用于树莓派5系统

echo "=== 显微镜控制系统依赖安装 ==="
echo ""

# 检查是否为树莓派
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  警告: 此脚本专为树莓派设计"
    read -p "是否继续安装? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 定义路径
PROJECT_DIR="/home/admin/Documents/project"
VENV_DIR="/home/admin/Documents/micro_env"

# 检查项目目录
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ 项目目录不存在: $PROJECT_DIR"
    exit 1
fi

echo "1. 更新系统包..."
sudo apt update

echo ""
echo "2. 安装系统依赖..."
sudo apt install -y python3-pip python3-venv python3-dev
sudo apt install -y libatlas-base-dev libhdf5-dev libhdf5-serial-dev
sudo apt install -y wireless-tools wpasupplicant dhcpcd5

echo ""
echo "3. 安装OpenCV系统包 (推荐方式)..."
sudo apt install -y python3-opencv libopencv-dev

echo ""
echo "4. 检查虚拟环境..."
if [ ! -d "$VENV_DIR" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv "$VENV_DIR"
else
    echo "✅ 虚拟环境已存在"
fi

echo ""
echo "5. 激活虚拟环境并安装Python包..."
source "$VENV_DIR/bin/activate"

# 升级pip
pip install --upgrade pip

# 检查requirements.txt是否存在
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "从requirements.txt安装依赖..."
    pip install -r "$PROJECT_DIR/requirements.txt"
else
    echo "requirements.txt不存在，手动安装主要包..."
    
    # Web框架
    pip install Flask==2.2.2 Flask-SocketIO==5.5.1
    pip install python-socketio==5.13.0 python-engineio==4.12.2
    
    # 图像处理
    pip install Pillow==9.4.0 numpy==1.24.2
    
    # 树莓派摄像头
    pip install picamera2==0.3.27
    
    # 硬件控制
    pip install RPi.GPIO==0.7.1
    pip install adafruit-circuitpython-ads1x15==2.4.4
    pip install adafruit-blinka==8.66.0
    pip install Adafruit-ADS1x15==1.0.2
    pip install rpi-hardware-pwm==0.3.0
    
    # 科学计算
    pip install scipy==1.10.1
    
    # 其他工具
    pip install tqdm==4.64.1 requests==2.28.1 netifaces==0.10.6
    
    # 实时通信支持
    pip install bidict==0.23.1 simple-websocket==1.1.0 wsproto==1.2.0
fi

echo ""
echo "6. 设置用户权限..."
sudo usermod -a -G gpio,spi,i2c,video admin

echo ""
echo "7. 验证安装..."
echo "测试主要模块导入..."

python3 -c "
try:
    import flask
    print('✅ Flask导入成功')
except ImportError as e:
    print('❌ Flask导入失败:', e)

try:
    import numpy as np
    print('✅ NumPy导入成功')
except ImportError as e:
    print('❌ NumPy导入失败:', e)

try:
    import cv2
    print('✅ OpenCV导入成功')
except ImportError as e:
    print('❌ OpenCV导入失败:', e)

try:
    from picamera2 import Picamera2
    print('✅ Picamera2导入成功')
except ImportError as e:
    print('❌ Picamera2导入失败:', e)

try:
    import RPi.GPIO as GPIO
    print('✅ RPi.GPIO导入成功')
except ImportError as e:
    print('❌ RPi.GPIO导入失败:', e)

try:
    from flask_socketio import SocketIO
    print('✅ Flask-SocketIO导入成功')
except ImportError as e:
    print('❌ Flask-SocketIO导入失败:', e)
"

echo ""
echo "8. 检查包依赖..."
pip check

echo ""
echo "=== 安装完成 ==="
echo ""
echo "下一步操作:"
echo "1. 配置WiFi权限: sudo bash $PROJECT_DIR/setup_wifi_permissions.sh"
echo "2. 设置自启动: sudo bash $PROJECT_DIR/install_autostart.sh" 
echo "3. 测试系统: bash $PROJECT_DIR/test_autostart.sh"
echo ""
echo "手动启动应用:"
echo "  source $VENV_DIR/bin/activate"
echo "  cd $PROJECT_DIR"
echo "  python3 app.py"
echo ""

# 显示虚拟环境信息
echo "虚拟环境位置: $VENV_DIR"
echo "激活命令: source $VENV_DIR/bin/activate"

# 检查是否需要重启
echo ""
echo "⚠️  建议重启系统以确保所有权限生效:"
echo "  sudo reboot" 