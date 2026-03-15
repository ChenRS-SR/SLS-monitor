"""
SLS系统调试配置
控制各种调试输出和日志级别
"""

# 控制台输出配置
CONSOLE_OUTPUT = {
    "enable_vibration_debug": False,    # 关闭振动传感器调试输出
    "enable_thermal_debug": False,      # 关闭热成像调试输出
    "enable_camera_debug": False,       # 关闭摄像头调试输出
    "enable_ui_debug": False,          # 关闭UI调试输出
    "enable_emoji_output": True,       # 保留表情符号输出
}

# 日志级别配置
LOG_LEVELS = {
    "VibrationDevice": "WARNING",       # 振动传感器日志级别
    "IR8062Device": "WARNING",          # 热成像设备日志级别  
    "CameraDevice": "WARNING",          # 摄像头设备日志级别
    "MainWindow": "INFO",               # 主窗口日志级别
    "System": "INFO",                   # 系统日志级别
}

# 自动启动配置
AUTO_START = {
    "thermal_panel": True,              # 自动启动热成像面板
    "vibration_panel": True,            # 自动启动振动面板
    "camera_panels": False,             # 不自动启动摄像头面板
}