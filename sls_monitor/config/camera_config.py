"""
Camera configuration settings
"""

# 摄像头配置
CAMERA_CONFIG = {
    "main_camera_index": 0,    # 主摄像头索引
    "main_camera_enabled": True,  # 是否启用主摄像头
    "secondary_camera_index": 2,  # 副摄像头索引（根据扫描结果更新）
    "secondary_camera_enabled": True,  # 是否启用副摄像头
    "fps": 30                  # 帧率
}

# 统一图像尺寸配置
IMAGE_CONFIG = {
    "display_width": 360,      # 优化显示宽度，节省空间
    "display_height": 220,     # 优化显示高度，节省空间
    "save_width": 2592,        # 提升保存宽度到2592（更高清晰度）
    "save_height": 1944,       # 提升保存高度到1944（更高清晰度）
    "keep_aspect_ratio": True, # 保持宽高比
    "camera_fps": 20,          # 降低相机帧率到20fps减少卡顿
    "thermal_fps": 20,          # 热像仪更新率20fps
    "ui_update_interval": 60,   # UI更新间隔60ms (20fps)
    
    # 保存时的显示控制
    "save_with_temperature": True,  # 保存时是否添加温度信息
    "save_with_colorbar": True      # 保存时是否添加色带
}

# 摄像头错误计数器
MAX_CAMERA_ERRORS = 10  # 最大连续错误次数
MAX_RECONNECT_ATTEMPTS = 3  # 最大重连尝试次数