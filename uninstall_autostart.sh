#!/bin/bash

# 显微镜控制系统自启动卸载脚本
# 适用于树莓派5系统

echo "=== 显微镜控制系统自启动卸载脚本 ==="
echo "正在卸载自启动服务..."

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo "错误: 请使用sudo运行此脚本"
    echo "使用方法: sudo bash uninstall_autostart.sh"
    exit 1
fi

# 定义路径
SERVICE_FILE="/etc/systemd/system/microscope.service"

echo "1. 停止服务..."
systemctl stop microscope.service

echo "2. 禁用自启动..."
systemctl disable microscope.service

echo "3. 删除服务文件..."
if [ -f "$SERVICE_FILE" ]; then
    rm "$SERVICE_FILE"
    echo "服务文件已删除"
else
    echo "服务文件不存在，跳过删除"
fi

echo "4. 重新加载systemd配置..."
systemctl daemon-reload

echo "5. 重置失败状态..."
systemctl reset-failed

echo ""
echo "=== 卸载完成 ==="
echo "显微镜控制系统自启动服务已完全移除"
echo "如需重新安装，请运行: sudo bash install_autostart.sh" 