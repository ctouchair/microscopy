#!/bin/bash

# 显微镜控制系统自启动安装脚本
# 适用于树莓派5系统

echo "=== 显微镜控制系统自启动安装脚本 ==="
echo "正在安装自启动服务..."

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo "错误: 请使用sudo运行此脚本"
    echo "使用方法: sudo bash install_autostart.sh"
    exit 1
fi

# 定义路径
SERVICE_FILE="/etc/systemd/system/microscope.service"
PROJECT_DIR="/home/admin/Documents/project"

# 检查项目目录是否存在
if [ ! -d "$PROJECT_DIR" ]; then
    echo "错误: 项目目录 $PROJECT_DIR 不存在"
    exit 1
fi

# 检查app.py是否存在
if [ ! -f "$PROJECT_DIR/app.py" ]; then
    echo "错误: app.py 文件不存在于 $PROJECT_DIR"
    exit 1
fi

# 检查虚拟环境是否存在
if [ ! -f "/home/admin/Documents/micro_env/bin/python" ]; then
    echo "错误: Python虚拟环境不存在于 /home/admin/Documents/micro_env/"
    exit 1
fi

echo "1. 复制服务文件到系统目录..."
cp "$PROJECT_DIR/microscope.service" "$SERVICE_FILE"

echo "2. 设置服务文件权限..."
chmod 644 "$SERVICE_FILE"

echo "3. 重新加载systemd配置..."
systemctl daemon-reload

echo "4. 启用自启动服务..."
systemctl enable microscope.service

echo "5. 启动服务..."
systemctl start microscope.service

echo "6. 检查服务状态..."
sleep 2
if systemctl is-active --quiet microscope.service; then
    echo "✅ 服务已成功启动"
else
    echo "⚠️  服务启动可能有问题，请检查状态:"
    systemctl status microscope.service
fi

echo ""
echo "=== 安装完成 ==="
echo "服务管理命令:"
echo "  查看状态: sudo systemctl status microscope.service"
echo "  启动服务: sudo systemctl start microscope.service"
echo "  停止服务: sudo systemctl stop microscope.service"
echo "  重启服务: sudo systemctl restart microscope.service"
echo "  查看日志: sudo journalctl -u microscope.service -f"
echo "  禁用自启: sudo systemctl disable microscope.service"
echo ""
echo "系统将在下次重启后自动启动显微镜控制系统"
echo "服务将运行在 http://0.0.0.0:5000" 