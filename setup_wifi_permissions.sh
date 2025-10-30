#!/bin/bash

# WiFi功能权限设置脚本
# 为显微镜控制系统配置必要的sudo权限

echo "=== 显微镜控制系统 WiFi权限设置 ==="
echo ""

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo "错误: 请使用sudo运行此脚本"
    echo "使用方法: sudo bash setup_wifi_permissions.sh"
    exit 1
fi

# 定义用户名
USERNAME="admin"

# 检查用户是否存在
if ! id "$USERNAME" &>/dev/null; then
    echo "错误: 用户 $USERNAME 不存在"
    exit 1
fi

echo "正在为用户 $USERNAME 配置WiFi管理权限..."

# 创建sudoers配置文件
SUDOERS_FILE="/etc/sudoers.d/microscope-wifi"

cat > "$SUDOERS_FILE" << EOF
# 显微镜控制系统WiFi管理权限
# 允许admin用户执行WiFi相关命令而无需密码

# WiFi扫描和状态查询（使用nmcli，与系统WiFi Manager一致）
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/nmcli
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/nmcli device wifi *
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/nmcli connection *
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/nmcli device *

# 传统的iw/iwgetid命令作为备用
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/iw
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/iwgetid
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/iwlist
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/iwconfig

# 网络接口管理
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip link set wlan*
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip addr show wlan*
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip -4 addr show wlan*

# 网络连接测试
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/ping -c 1 *
EOF

# 设置正确的权限
chmod 440 "$SUDOERS_FILE"

# 验证sudoers文件语法
if visudo -c -f "$SUDOERS_FILE"; then
    echo "✅ sudoers配置文件创建成功: $SUDOERS_FILE"
else
    echo "❌ sudoers配置文件语法错误，正在删除..."
    rm "$SUDOERS_FILE"
    exit 1
fi

echo ""
echo "=== 权限设置完成 ==="
echo ""
echo "已配置的权限:"
echo "  - WiFi网络管理 (nmcli - 与系统WiFi Manager一致)"
echo "  - WiFi网络扫描 (nmcli, iwlist, iwconfig)"
echo "  - WiFi连接管理 (nmcli)"
echo "  - 网络接口管理 (ip命令)"
echo "  - 网络连接测试 (ping)"
echo ""
echo "测试WiFi权限:"
echo "  sudo -u $USERNAME sudo nmcli device wifi list"
echo "  sudo -u $USERNAME sudo nmcli device status"
echo ""
echo "如需移除权限，请删除文件: $SUDOERS_FILE" 