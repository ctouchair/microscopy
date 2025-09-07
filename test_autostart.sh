#!/bin/bash

# 显微镜控制系统自启动测试脚本

echo "=== 显微镜控制系统自启动测试 ==="
echo ""

echo "1. 检查服务状态..."
if sudo systemctl is-active --quiet microscope.service; then
    echo "✅ 服务正在运行"
else
    echo "❌ 服务未运行"
    exit 1
fi

echo ""
echo "2. 检查自启动状态..."
if sudo systemctl is-enabled --quiet microscope.service; then
    echo "✅ 自启动已启用"
else
    echo "❌ 自启动未启用"
    exit 1
fi

echo ""
echo "3. 检查端口监听..."
if netstat -tlnp | grep -q ":5000.*LISTEN"; then
    echo "✅ 端口5000正在监听"
else
    echo "❌ 端口5000未监听"
    exit 1
fi

echo ""
echo "4. 检查进程..."
PID=$(pgrep -f "python.*app.py")
if [ -n "$PID" ]; then
    echo "✅ 应用进程正在运行 (PID: $PID)"
else
    echo "❌ 应用进程未找到"
    exit 1
fi

echo ""
echo "5. 获取网络地址..."
IP=$(hostname -I | awk '{print $1}')
echo "📡 本地访问: http://localhost:5000"
echo "📡 网络访问: http://$IP:5000"

echo ""
echo "6. 检查最近的日志..."
echo "最近5条日志:"
sudo journalctl -u microscope.service -n 5 --no-pager

echo ""
echo "=== 测试完成 ==="
echo "✅ 显微镜控制系统自启动配置正常！"
echo ""
echo "重启测试建议:"
echo "  sudo reboot"
echo "  # 等待系统启动后，运行:"
echo "  bash test_autostart.sh" 