"""
Infrared camera configuration settings
"""

# 红外热像仪配置 (Optris PI450i LT Connect SDK)
# 基于成功的测试程序配置
INFRARED_CONFIG = {
    "device_model": "PI450i LT",        # 设备型号 (已验证: PI400/450 #19012006)
    "sdk_type": "Connect SDK",          # 使用Connect SDK（已验证成功）
    #"sdk_path": "e:\\硬件开发\\VB02+logi摄像头头数据采集\\OPT-PIX-Connect-Rel.-3.24.3127.0\\OPT PIX Connect Rel. 3.24.3127.0\\SDK\\Connect SDK\\Lib\\v120",
    "sdk_path": "D:\College\Python_project\\4Project\slm\\OPT-PIX-Connect-Rel.-3.24.3127.0\\OPT PIX Connect Rel. 3.24.3127.0\\SDK\\Connect SDK\\Lib\\v120",
    "dll_arch": "x64",                  # DLL架构 (x64/Win32)
    "dll_name": "ImagerIPC2x64.dll",    # Connect SDK DLL名称
    "enabled": False,                   # 暂时禁用红外热像仪（用于测试）
    "fov": "18°x14°",                  # 视场角
    "temperature_range": (-20, 100),   # 温度测量范围 (°C) - 根据实际测试调整
    "emissivity": 1.0,                 # 发射率设置 (根据PIX Connect界面)
    "framerate": 25.0,                 # 帧率 (调整到25 FPS，避免连接不稳定)
    "device_index": 0,                 # IPC设备索引
    "data_mode": "Temps",              # 数据模式: 温度值（已在PIX Connect中设置）
    "temperature_offset": 0.0,         # 全局温度补偿偏移量 (°C) - 用于矫正热场绝对温度
    "gui_update_rate": 50,             # GUI更新率 (ms) - 调整到50ms，提高稳定性
    "data_timeout": 100,               # 数据获取超时 (ms) - 恢复到100ms，确保连接稳定
    "fast_mode": False,                # 禁用快速模式，确保稳定性
    "skip_frames": 1,                  # 适度跳帧 (跳1帧)，平衡性能和稳定性
    # 温度梯度补偿配置 (针对倾斜安装角度)
    "gradient_compensation": {
        "enabled": False,              # 默认关闭梯度补偿
        "vertical_gradient": -0.15,    # 垂直温度梯度 (°C/像素) - 负值表示上热下冷
        "horizontal_gradient": 0.0,    # 水平温度梯度 (°C/像素)
        "reference_point": "center",   # 参考点位置 ("center", "top", "bottom")
        "compensation_strength": 1.0,  # 补偿强度 (0.0-2.0, 1.0为完全补偿)
        "auto_calibration": {
            "enabled": False,          # 禁用自动校准 - 改为纯手动调整
            "sample_frames": 10,       # 校准用的采样帧数
            "min_temp_range": 2.0,     # 最小温度范围要求 (°C)
            "edge_exclusion": 0.1      # 边缘排除比例 (避免边缘效应)
        }
    }
}