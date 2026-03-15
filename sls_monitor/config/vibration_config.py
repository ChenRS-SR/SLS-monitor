"""
Vibration sensor configuration settings
"""

# 振动传感器配置
VIBRATION_CONFIG = {
    "device_model": "WTVB02-485",  # 设备型号
    "com_port": "COM13",        # 振动监测设备串口号
    "baudrate": 9600,          # 波特率
    "address": 0x50,           # 设备地址
    "timeout": 1.0             # 超时时间(秒)
}

# Register address mapping
REGISTER_MAP = {
    "save_restart": 0x00,      # Save/Restart/Restore
    "baud_rate": 0x04,        # Serial port baud rate
    "device_address": 0x1A,    # Device address
    
    # Vibration velocity
    "velocity_x": 0x3A,
    "velocity_y": 0x3B,
    "velocity_z": 0x3C,
    
    # Vibration angle
    "angle_x": 0x3D,
    "angle_y": 0x3E,
    "angle_z": 0x3F,
    
    # Temperature
    "temperature": 0x40,
    
    # Vibration displacement
    "displacement_x": 0x41,
    "displacement_y": 0x42,
    "displacement_z": 0x43,
    
    # Vibration frequency
    "frequency_x": 0x44,
    "frequency_y": 0x45,
    "frequency_z": 0x46,
    
    # Configuration
    "cutoff_freq_1": 0x63,
    "cutoff_freq_2": 0x64,
    "detection_period": 0x65
}

# 振动检测配置（类似于原始代码中的POWDER_DETECTION_CONFIG）
VIBRATION_DETECTION_CONFIG = {
    # 基本检测参数
    "motion_threshold": 0.05,       # 振动触发阈值
    "debounce_time": 0.5,          # 防抖时间(秒)
    "noise_filter_enabled": True,   # 启用噪声过滤
    "min_signal_strength": 0.001,   # 最小信号强度
    "max_detection_rate": 10,       # 最大检测频率(Hz)
    
    # 日志和调试
    "verbose_logging": True,        # 详细日志输出
    "debug_mode": False,           # 调试模式
    "log_detection_stats": True,   # 记录检测统计
    
    # 高级配置
    "smart_detection_enabled": False,  # 智能检测模式
    "auto_calibration": True,      # 自动校准
    "state_reset_delay": 0.05,     # 状态重置延迟（秒）
    
    # 算法配置
    "default_algorithm": "composite",  # 默认检测算法
    "algorithm_switching": False,   # 允许动态切换算法
}

# 振动级别定义
VIBRATION_LEVELS = {
    "low": {
        "threshold": 0.01,
        "color": "green",
        "description": "轻微振动"
    },
    "medium": {
        "threshold": 0.05,
        "color": "orange", 
        "description": "中等振动"
    },
    "high": {
        "threshold": 0.1,
        "color": "red",
        "description": "强烈振动"
    },
    "critical": {
        "threshold": 0.2,
        "color": "purple",
        "description": "危险振动"
    }
}

# 日志级别配置
LOG_LEVELS = {
    "DEBUG": {"color": "gray", "priority": 1},
    "INFO": {"color": "black", "priority": 2},
    "WARNING": {"color": "orange", "priority": 3},
    "ERROR": {"color": "red", "priority": 4},
    "CRITICAL": {"color": "purple", "priority": 5}
}