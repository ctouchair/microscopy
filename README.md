# 显微镜控制系统

一个基于树莓派5的智能显微镜控制系统，提供Web界面操作、实时图像处理、精密运动控制和WiFi管理等功能。

![系统状态](https://img.shields.io/badge/状态-运行中-brightgreen)
![Python版本](https://img.shields.io/badge/Python-3.11-blue)
![平台](https://img.shields.io/badge/平台-树莓派5-red)
![许可证](https://img.shields.io/badge/许可证-MIT-green)

## 📋 目录

- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [硬件要求](#硬件要求)
- [快速开始](#快速开始)
- [安装指南](#安装指南)
- [使用说明](#使用说明)
- [API文档](#api文档)
- [故障排除](#故障排除)
- [贡献指南](#贡献指南)
- [更新日志](#更新日志)
- [许可证](#许可证)

## ✨ 功能特性

### 🔬 显微镜控制
- **双摄像头支持**: 主摄像头(IMX477)和辅助摄像头(IMX219)
- **精密运动控制**: 三轴(X/Y/Z)步进电机控制，精度达微米级
- **自动对焦**: 基于图像清晰度的智能对焦算法
- **LED照明控制**: 可调节LED亮度，优化成像效果

### 📸 图像处理
- **实时预览**: 高帧率实时图像预览
- **高分辨率拍照**: 支持4K分辨率图像捕获
- **视频录制**: 支持高清视频录制和间隔拍摄
- **图像拼接**: 400%画幅拼接功能，扩大视野范围
- **景深堆叠**: 多层图像合成，获得更大景深
- **细胞计数**: 自动细胞识别和计数功能

### 🌐 网络功能
- **Web界面**: 现代化响应式Web控制界面
- **实时通信**: 基于WebSocket的实时数据传输
- **WiFi管理**: 内置WiFi扫描、连接和管理功能
- **远程访问**: 支持局域网和互联网远程访问

### ⚙️ 系统功能
- **自启动服务**: 开机自动启动，无需手动干预
- **配置管理**: 参数保存和恢复功能
- **系统校准**: 自动像素尺寸校准
- **日志记录**: 完整的操作日志和错误追踪
- **运动检测**: 辅助摄像头运动检测录制

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Web浏览器客户端                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  控制界面   │ │  实时预览   │ │  WiFi设置   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/WebSocket
┌─────────────────────────▼───────────────────────────────────┐
│                  Flask Web服务器                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  REST API   │ │  SocketIO   │ │  静态文件   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────┬───────────────────────────────────┘
                          │ Python调用
┌─────────────────────────▼───────────────────────────────────┐
│                    核心控制模块                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  摄像头控制 │ │  电机控制   │ │  图像处理   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────┬───────────────────────────────────┘
                          │ 硬件接口
┌─────────────────────────▼───────────────────────────────────┐
│                      硬件层                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  摄像头模块 │ │  步进电机   │ │  传感器     │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 💻 硬件要求

### 必需硬件
- **树莓派5** (推荐4GB或8GB内存版本)
- **MicroSD卡** (至少32GB，Class 10或更高)
- **摄像头模块**:
  - 主摄像头: IMX477 (12MP, 支持4K)
  - 辅助摄像头: IMX219 (8MP)
- **步进电机系统**:
  - 3轴步进电机 (X/Y/Z轴)
  - 电机驱动板
  - Hall传感器 (位置反馈)
- **LED照明系统**
- **电源**: 5V/3A USB-C电源适配器

### 可选硬件
- **散热系统**: 主动散热风扇
- **外壳**: 保护性外壳
- **显示屏**: 用于本地操作

## 🚀 快速开始

### 一键安装 (推荐)

```bash
# 克隆项目 (如果使用git)
git clone <repository-url>
cd microscope-control-system

# 或者直接在现有项目目录中运行
cd /home/admin/Documents/project

# 运行一键安装脚本
bash install_dependencies.sh

# 设置WiFi权限
sudo bash setup_wifi_permissions.sh

# 安装自启动服务
sudo bash install_autostart.sh

# 重启系统
sudo reboot
```

### 手动安装

详细的手动安装步骤请参考 [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)

## 📖 安装指南

### 系统要求
- **操作系统**: Raspberry Pi OS (基于Debian 12 Bookworm)
- **Python版本**: 3.11+
- **内存**: 至少4GB RAM
- **存储**: 至少16GB可用空间

### 依赖包安装

```bash
# 激活虚拟环境
source /home/admin/Documents/micro_env/bin/activate

# 安装Python依赖
pip install -r requirements.txt
```

主要依赖包：
- **Web框架**: Flask 2.2.2, Flask-SocketIO 5.5.1
- **图像处理**: OpenCV, Pillow 9.4.0, NumPy 1.24.2
- **硬件控制**: RPi.GPIO, Adafruit库, picamera2
- **科学计算**: SciPy 1.10.1

完整依赖列表请查看 [requirements.txt](requirements.txt)

## 📱 使用说明

### 访问系统

1. **本地有线网络访问**: `http://192.168.1.92:5000`
2. **本地无线网络访问**: `http://[树莓派IP]:5000`
3. **WiFi IP**: 通过WiFi设置界面查看当前IP

### 主要功能

#### 🔬 显微镜操作
1. **拍照**: 点击拍照按钮，支持高分辨率图像捕获
2. **录像**: 支持连续录制和间隔录制
3. **实时预览**: 双摄像头实时图像显示

#### 🎯 运动控制
1. **手动控制**: 使用滑块精确控制X/Y/Z轴位置
2. **自动对焦**: 一键自动对焦到最清晰位置
3. **位置保存**: 保存和恢复常用位置

#### 🖼️ 图像处理
1. **图像拼接**: 自动拍摄9张图片并拼接成大视野图像
2. **景深堆叠**: 拍摄多层图像并合成高景深图片
3. **细胞计数**: 自动识别和计数细胞

#### 📶 WiFi管理
1. **网络扫描**: 扫描附近可用WiFi网络
2. **网络连接**: 连接到新的WiFi网络
3. **状态查看**: 查看当前连接状态和IP地址

### 界面说明

```
┌─────────────────────────────────────────────────────────────┐
│  🔬 显微镜控制系统                    📶 WiFi: HomeCherry    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │   主摄像头预览   │  │  辅助摄像头预览  │                 │
│  │                │  │                │                 │
│  │    实时图像     │  │    监控视图     │                 │
│  └─────────────────┘  └─────────────────┘                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┤
│  │  📷 拍照  🎥 录制  📡 WiFi  🔧 设置  📊 图表            │
│  └─────────────────────────────────────────────────────────┤
│                                                             │
│  位置控制:                                                   │
│  X: ████████░░ 5.23mm    Y: ██████░░░░ 3.45mm             │
│  Z: ███████░░░ 2.18mm    🎯 自动对焦                       │
│                                                             │
│  相机设置:                                                   │
│  曝光: ██████░░░░ 20ms   增益: ███░░░░░░░ 1.5x             │
│  LED:  ████████░░ 80%    白平衡: R:0.67 B:0.58            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 📡 API文档

### WebSocket事件

#### 客户端发送事件
```javascript
// 拍照
socket.emit('capture');

// 开始录制
socket.emit('start_recording', {interval: 0});

// 移动到位置
socket.emit('set_x_pos', {value: 5.0});

// WiFi扫描
socket.emit('scan_wifi');
```

#### 服务器发送事件
```javascript
// 拍照结果
socket.on('capture_response', function(data) {
    // data: {success: true, filename: 'xxx.jpg', data: 'base64...'}
});

// 运动位置更新
socket.on('motor_positions', function(data) {
    // data: {x_pos: 5.0, y_pos: 3.0, z_pos: 2.0}
});

// WiFi扫描结果
socket.on('wifi_scan_result', function(data) {
    // data: {success: true, networks: [...]}
});
```

### REST API

```bash
# 获取设置
GET /api/settings

# 视频流
GET /video_feed        # 主摄像头
GET /video_feed_cam1   # 辅助摄像头
```

## 🔧 配置文件

### settings.json
```json
{
    "exposure_value": 20,
    "gain_value": 1.5,
    "led_value": 80,
    "r_value": 0.67,
    "b_value": 0.58,
    "pixel_size": 0.09
}
```

### params.json
```json
{
    "X": [A, B, C, D],  // X轴校准参数
    "Y": [A, B, C, D],  // Y轴校准参数
    "Z": [A, B, C, D]   // Z轴校准参数
}
```

## 🛠️ 故障排除

### 常见问题

#### 1. 服务无法启动
```bash
# 检查服务状态
sudo systemctl status microscope.service

# 查看错误日志
sudo journalctl -u microscope.service -f
```

#### 2. 摄像头无法访问
```bash
# 检查摄像头设备
ls -l /dev/video*

# 测试摄像头
libcamera-hello --list-cameras
```

#### 3. WiFi功能异常
```bash
# 测试WiFi扫描
sudo iwlist wlan0 scan

# 检查权限配置
sudo cat /etc/sudoers.d/microscope-wifi
```

#### 4. 运动控制问题
```bash
# 检查GPIO权限
ls -l /dev/gpiomem

# 测试GPIO
python3 -c "import RPi.GPIO as GPIO; print('GPIO OK')"
```

### 性能优化

1. **内存优化**:
   ```bash
   # 增加GPU内存
   sudo raspi-config
   # Advanced Options -> Memory Split -> 128
   ```

2. **CPU性能**:
   ```bash
   # 启用性能模式
   echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
   ```

## 📁 项目结构

```
project/
├── app.py                      # 主应用程序
├── camera.py                   # 摄像头控制模块
├── motor.py                    # 电机控制模块
├── utils.py                    # 图像处理工具
├── hall_calibrate.py          # 传感器校准
├── requirements.txt           # Python依赖
├── settings.json              # 系统配置
├── params.json               # 校准参数
├── microscope.service        # 系统服务文件
├── install_autostart.sh      # 自启动安装脚本
├── install_dependencies.sh   # 依赖安装脚本
├── setup_wifi_permissions.sh # WiFi权限设置
├── test_autostart.sh         # 自启动测试
├── test_wifi_feature.sh      # WiFi功能测试
├── templates/                # Web模板
│   └── index.html
├── static/                   # 静态资源
│   ├── css/
│   ├── js/
│   └── images/
└── docs/                     # 文档
    ├── README.md
    ├── INSTALLATION_GUIDE.md
    ├── WIFI_FEATURE_README.md
    └── WIFI_SETUP_COMPLETE.md
```

## 🧪 测试

### 运行测试
```bash
# 系统功能测试
bash test_autostart.sh

# WiFi功能测试
bash test_wifi_feature.sh

# 手动测试
source /home/admin/Documents/micro_env/bin/activate
python3 -m pytest tests/  # 如果有测试文件
```

## 📈 监控和日志

### 系统监控
```bash
# 查看系统状态
htop

# 监控温度
vcgencmd measure_temp

# 查看内存使用
free -h
```

### 日志管理
```bash
# 查看应用日志
sudo journalctl -u microscope.service --since today

# 清理旧日志
sudo journalctl --vacuum-time=7d
```

## 🔄 更新和维护

### 系统更新
```bash
# 停止服务
sudo systemctl stop microscope.service

# 更新代码
git pull  # 如果使用git

# 更新依赖
source /home/admin/Documents/micro_env/bin/activate
pip install -r requirements.txt --upgrade

# 重启服务
sudo systemctl start microscope.service
```

### 备份
```bash
# 备份项目文件
tar -czf microscope_backup_$(date +%Y%m%d).tar.gz /home/admin/Documents/project/

# 备份虚拟环境
tar -czf venv_backup_$(date +%Y%m%d).tar.gz /home/admin/Documents/micro_env/
```

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范
- 使用Python PEP 8编码规范
- 添加适当的注释和文档
- 确保测试通过
- 更新相关文档

## 📝 更新日志

### v2.0.0 (2025-09-07)
- ✨ 新增WiFi管理功能
- 🔧 修复WiFi IP地址显示问题
- 📦 完善依赖包管理
- 📚 更新文档和安装指南

### v1.5.0 (2025-08-xx)
- ✨ 添加自启动服务功能
- 🔧 优化系统稳定性
- 📈 改进性能监控

### v1.0.0 (2025-xx-xx)
- 🎉 初始版本发布
- ✨ 基础显微镜控制功能
- 📸 图像处理和录制功能
- 🌐 Web界面

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持和联系

- **问题报告**: [Issues](https://github.com/your-repo/issues)
- **功能请求**: [Feature Requests](https://github.com/your-repo/issues)
- **文档**: [Wiki](https://github.com/your-repo/wiki)

## 🙏 致谢

感谢以下开源项目的支持：
- [Flask](https://flask.palletsprojects.com/) - Web框架
- [OpenCV](https://opencv.org/) - 计算机视觉库
- [Picamera2](https://github.com/raspberrypi/picamera2) - 树莓派摄像头库
- [Adafruit](https://github.com/adafruit) - 硬件控制库

---

<div align="center">
  <strong>🔬 让科学研究更简单 | Making Scientific Research Easier 🔬</strong>
</div> 
