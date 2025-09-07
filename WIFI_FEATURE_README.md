# 显微镜控制系统 - WiFi设置功能

## 功能概述

WiFi设置功能允许用户通过Web界面直接管理树莓派的WiFi连接，包括：

- 查看当前WiFi连接状态
- 扫描可用的WiFi网络
- 连接到新的WiFi网络
- 查看网络信息（IP地址、信号强度等）

## 使用方法

### 1. 打开WiFi设置

在显微镜控制系统的主界面中，点击 **"WiFi设置"** 按钮（带有WiFi图标）。

### 2. 查看当前连接状态

WiFi设置窗口会显示：
- **网络名称 (SSID)**: 当前连接的WiFi网络名称
- **IP地址**: 当前获取的IP地址
- **信号强度**: 当前连接的信号强度百分比

### 3. 扫描WiFi网络

- 点击 **"扫描"** 按钮来搜索附近的WiFi网络
- 扫描结果会按信号强度排序显示
- 每个网络显示：
  - 网络名称 (SSID)
  - 安全类型 (WPA2/WPA/WEP/开放网络)
  - 信号强度
  - 频道信息

### 4. 连接到WiFi网络

#### 连接加密网络：
1. 在扫描结果中点击要连接的网络
2. 在弹出的连接窗口中输入WiFi密码
3. 点击 **"连接"** 按钮
4. 系统会尝试连接并显示连接状态

#### 连接开放网络：
1. 直接点击开放网络即可自动连接
2. 无需输入密码

### 5. 连接状态反馈

- **连接成功**: 显示绿色成功消息，自动关闭连接窗口
- **连接失败**: 显示红色错误消息，可以重新尝试
- **连接中**: 显示蓝色进度消息

## 技术特性

### 前端功能
- 现代化的模态框界面设计
- 实时的WiFi状态更新
- 响应式设计，支持移动设备
- 密码显示/隐藏切换
- 加载动画和状态指示器

### 后端功能
- 使用 `iwconfig` 获取当前WiFi状态
- 使用 `iwlist` 扫描可用网络
- 使用 `wpa_supplicant` 管理WiFi连接
- 自动配置网络参数
- 连接验证和错误处理

### 安全特性
- 密码安全传输
- 临时配置文件自动清理
- 连接验证机制
- 错误处理和超时保护

## 系统要求

### 必需的系统工具
```bash
# 检查系统工具是否可用
which iwconfig    # 无线网络配置工具
which iwlist      # 无线网络扫描工具
which wpa_supplicant  # WPA/WPA2连接工具
which dhclient   # DHCP客户端
```

### 权限要求
WiFi管理需要sudo权限，确保运行应用的用户有以下权限：
```bash
# 在 /etc/sudoers 中添加（使用 sudo visudo 编辑）
admin ALL=(ALL) NOPASSWD: /sbin/iwlist
admin ALL=(ALL) NOPASSWD: /usr/bin/killall wpa_supplicant
admin ALL=(ALL) NOPASSWD: /sbin/wpa_supplicant
admin ALL=(ALL) NOPASSWD: /sbin/dhclient
admin ALL=(ALL) NOPASSWD: /bin/cp * /etc/wpa_supplicant/wpa_supplicant.conf
```

## 故障排除

### 常见问题

#### 1. 扫描失败
**问题**: WiFi扫描返回错误或无结果
**解决方案**:
```bash
# 检查WiFi接口状态
sudo iwconfig
# 启用WiFi接口
sudo ip link set wlan0 up
# 手动扫描测试
sudo iwlist wlan0 scan
```

#### 2. 连接失败
**问题**: 输入正确密码但连接失败
**解决方案**:
```bash
# 检查wpa_supplicant进程
sudo killall wpa_supplicant
# 重启网络服务
sudo systemctl restart networking
# 检查网络接口
sudo ip addr show wlan0
```

#### 3. 权限错误
**问题**: 执行WiFi命令时权限不足
**解决方案**:
```bash
# 检查sudo权限
sudo -l
# 添加必要的sudo规则（见上面的权限要求）
sudo visudo
```

#### 4. 服务日志检查
```bash
# 查看应用日志
sudo journalctl -u microscope.service -f
# 查看系统网络日志
sudo journalctl -u networking.service -f
```

### 调试模式

如果需要调试WiFi功能，可以在Python代码中启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 配置文件

### wpa_supplicant配置
WiFi连接成功后，配置会保存到：
- `/etc/wpa_supplicant/wpa_supplicant.conf`

### 网络接口配置
确保 `/etc/dhcpcd.conf` 或网络配置正确设置了DHCP。

## 注意事项

1. **网络切换**: 连接新网络时会断开当前连接
2. **密码安全**: 密码会保存在系统配置文件中
3. **重启持久**: 连接配置会在系统重启后保持
4. **信号强度**: 显示的信号强度为估算值，可能与实际有差异
5. **连接超时**: 连接操作有30秒超时限制

## 更新日志

- **v1.0**: 初始版本，支持基本的WiFi扫描和连接功能
- 支持WPA/WPA2/WEP/开放网络
- 现代化的Web界面
- 实时状态更新
- 错误处理和用户反馈 