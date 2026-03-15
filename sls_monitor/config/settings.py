"""
SLS监控系统全局配置
"""

import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 保存路径配置
SAVE_DIR = {
    "images": os.path.join(BASE_DIR, "data", "images"),
    "thermal": os.path.join(BASE_DIR, "data", "thermal"),
    "logs": os.path.join(BASE_DIR, "data", "logs")
}

# 设备配置
DEVICES = {
    "camera": {
        "enabled": True,
        "type": "webcam",  # webcam 或 usb_camera
        "index": 0,        # 摄像头索引
        "resolution": (1280, 720)
    },
    
    "vibration": {
        "enabled": True,
        "port": "COM4",    # 串口号
        "baudrate": 115200,
        "timeout": 1
    }
}

# 系统设置
SYSTEM = {
    "debug": True,          # 调试模式
    "simulation": True,     # 模拟模式（用于测试）
    "save_images": True,   # 是否保存图像
    "log_level": "INFO"    # 日志级别
}