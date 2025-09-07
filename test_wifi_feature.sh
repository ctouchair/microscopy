#!/bin/bash

# WiFi功能测试脚本

echo "=== 显微镜控制系统 WiFi功能测试 ==="
echo ""

# 测试1: 检查WiFi接口
echo "1. 检查WiFi接口状态..."
if sudo iwconfig wlan0 2>/dev/null | grep -q "IEEE 802.11"; then
    echo "✅ WiFi接口 wlan0 可用"
else
    echo "❌ WiFi接口 wlan0 不可用"
    exit 1
fi

# 测试2: 检查当前WiFi连接
echo ""
echo "2. 检查当前WiFi连接..."
CURRENT_SSID=$(sudo iwconfig wlan0 2>/dev/null | grep "ESSID:" | sed 's/.*ESSID:"\([^"]*\)".*/\1/')
if [ -n "$CURRENT_SSID" ] && [ "$CURRENT_SSID" != "off/any" ]; then
    echo "✅ 当前连接到: $CURRENT_SSID"
else
    echo "⚠️  当前未连接到WiFi网络"
fi

# 测试3: 检查IP地址
echo ""
echo "3. 检查网络IP地址..."
IP_ADDRESS=$(hostname -I | awk '{print $1}')
if [ -n "$IP_ADDRESS" ]; then
    echo "✅ IP地址: $IP_ADDRESS"
else
    echo "❌ 无IP地址"
fi

# 测试4: 测试WiFi扫描
echo ""
echo "4. 测试WiFi网络扫描..."
SCAN_RESULT=$(sudo iwlist wlan0 scan 2>/dev/null | grep "ESSID:" | wc -l)
if [ "$SCAN_RESULT" -gt 0 ]; then
    echo "✅ 扫描到 $SCAN_RESULT 个WiFi网络"
    echo "   前5个网络:"
    sudo iwlist wlan0 scan 2>/dev/null | grep "ESSID:" | head -5 | sed 's/.*ESSID:"\([^"]*\)".*/   - \1/'
else
    echo "❌ WiFi扫描失败或无可用网络"
fi

# 测试5: 检查网络连通性
echo ""
echo "5. 测试网络连通性..."
if sudo ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    echo "✅ 网络连通正常"
else
    echo "❌ 网络连通失败"
fi

# 测试6: 检查sudo权限
echo ""
echo "6. 检查sudo权限..."
PERMISSIONS_OK=true

# 检查各种WiFi命令的权限
commands=(
    "/usr/sbin/iwconfig"
    "/usr/sbin/iwlist wlan0 scan"
    "/usr/bin/killall wpa_supplicant"
    "/usr/bin/ping -c 1 8.8.8.8"
)

for cmd in "${commands[@]}"; do
    if sudo -n $cmd >/dev/null 2>&1; then
        echo "✅ sudo $cmd - 权限正常"
    else
        echo "❌ sudo $cmd - 权限不足"
        PERMISSIONS_OK=false
    fi
done

# 测试7: 检查服务状态
echo ""
echo "7. 检查显微镜服务状态..."
if systemctl is-active --quiet microscope.service; then
    echo "✅ 显微镜服务正在运行"
    
    # 检查服务端口
    if netstat -tlnp 2>/dev/null | grep -q ":5000.*LISTEN"; then
        echo "✅ Web服务端口5000正在监听"
        echo "   访问地址: http://$IP_ADDRESS:5000"
    else
        echo "❌ Web服务端口5000未监听"
    fi
else
    echo "❌ 显微镜服务未运行"
fi

echo ""
echo "=== 测试完成 ==="

if [ "$PERMISSIONS_OK" = true ]; then
    echo "✅ WiFi功能测试通过！"
    echo ""
    echo "使用说明:"
    echo "1. 在浏览器中访问 http://$IP_ADDRESS:5000"
    echo "2. 点击 'WiFi设置' 按钮"
    echo "3. 扫描并连接到新的WiFi网络"
else
    echo "❌ WiFi功能测试未完全通过"
    echo "请检查sudo权限配置"
fi 