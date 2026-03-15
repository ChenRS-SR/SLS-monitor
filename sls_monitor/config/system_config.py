"""
系统配置模块
包含全局系统设置和默认参数
"""

import os
import logging

# 目录设置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
IMAGE_DIR = os.path.join(OUTPUT_DIR, 'images')
LOG_DIR = os.path.join(OUTPUT_DIR, 'logs')
DATA_DIR = os.path.join(OUTPUT_DIR, 'data')

# 日志设置
LOG_LEVEL = logging.INFO
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

# 默认工艺参数
DEFAULT_PARAMS = {
    'layer_thickness': 0.1,#分层厚度
    'fill_spacing': 0.1,#填充间距
    'fill_speed': 2000,#填充速度
    'fill_power': 10 #填充功率
}

# 红外摄像头配置
THERMAL_CAMERA_CONFIG = {
    "thermal_camera_type": 1,  # 0: IR8062, 1: Fotric628ch
    "fotric_ip": "192.168.1.100",  # Fotric设备IP地址
    "fotric_port": 10080,  # Fotric设备端口（正确的REST API端口）
    "fotric_username": "admin",
    "fotric_password": "admin",
    "ir8062_port": None,  # IR8062端口，None为自动检测
    "simulation_mode": False,  # 使用真实Fotric设备，不使用模拟数据
    "fotric_high_resolution": True,  # 启用Fotric高分辨率模式(640x480)
    "fotric_update_rate": 15.0,  # Fotric更新频率(Hz)，进一步提高到15Hz
    "fotric_sample_density": 40  # 采样密度（像素间隔），用于性能优化
}

# 默认保存路径配置
DEFAULT_SAVE_PATH_CONFIG = {
    "use_custom_default": 1,  # 0: 使用项目默认路径, 1: 使用自定义路径
    "project_default_path": r"D:\College\Python_project\4Project\SLS\sls_monitor\output",
    "custom_default_path": r"G:\数据\SLS数据"
}

# System settings
SYSTEM_CONFIG = {
    "log_level": "INFO",
    "data_save_path": "data",
    "image_save_path": "images",
    "backup_enabled": True,
    "backup_interval": 3600,  # seconds
    "auto_reconnect": True,
    "debug_mode": False
}