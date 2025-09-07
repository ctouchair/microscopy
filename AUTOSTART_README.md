# 显微镜控制系统自启动配置

本文档说明如何在树莓派5系统中设置显微镜控制系统的开机自启动。

## 文件说明

- `microscope.service` - systemd服务配置文件
- `install_autostart.sh` - 安装自启动服务的脚本
- `uninstall_autostart.sh` - 卸载自启动服务的脚本

## 安装自启动服务

1. 进入项目目录：
```bash
cd /home/admin/Documents/project
```

2. 运行安装脚本（需要sudo权限）：
```bash
sudo bash install_autostart.sh
```

3. 安装完成后，系统会自动：
   - 创建systemd服务
   - 启用开机自启动
   - 立即启动服务

## 服务管理命令

### 查看服务状态
```bash
sudo systemctl status microscope.service
```

### 启动服务
```bash
sudo systemctl start microscope.service
```

### 停止服务
```bash
sudo systemctl stop microscope.service
```

### 重启服务
```bash
sudo systemctl restart microscope.service
```

### 查看服务日志
```bash
sudo journalctl -u microscope.service -f
```

### 禁用自启动（但不删除服务）
```bash
sudo systemctl disable microscope.service
```

### 启用自启动
```bash
sudo systemctl enable microscope.service
```

## 卸载自启动服务

如果需要完全移除自启动服务：

```bash
sudo bash uninstall_autostart.sh
```

## 服务配置说明

服务配置的关键特性：

- **自动重启**: 如果程序崩溃，系统会自动重启服务
- **延迟启动**: 开机后等待10秒再启动，确保系统完全就绪
- **网络依赖**: 等待网络服务启动后再运行
- **日志记录**: 所有输出都记录到系统日志中
- **用户权限**: 以admin用户身份运行，确保权限正确

## 访问应用

服务启动后，可通过以下地址访问：
- 本地访问: http://localhost:5000
- 网络访问: http://[树莓派IP]:5000

## 故障排除

### 检查服务是否运行
```bash
sudo systemctl is-active microscope.service
```

### 查看详细错误信息
```bash
sudo journalctl -u microscope.service --no-pager
```

### 查看最近的日志
```bash
sudo journalctl -u microscope.service -n 50
```

### 重新安装服务
如果遇到问题，可以先卸载再重新安装：
```bash
sudo bash uninstall_autostart.sh
sudo bash install_autostart.sh
```

## 注意事项

1. 确保虚拟环境路径正确：`/home/admin/Documents/micro_env/`
2. 确保项目路径正确：`/home/admin/Documents/project/`
3. 确保admin用户有相应的硬件访问权限（GPIO、摄像头等）
4. 如果修改了项目路径，需要更新`microscope.service`文件中的路径
5. 系统重启后服务会自动启动，无需手动干预 