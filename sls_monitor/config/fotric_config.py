"""
FOTRIC 628ch红外热成像仪配置模块
基于FOTRIC SDK的网络红外热成像仪配置
"""

# FOTRIC 628ch设备基础配置
FOTRIC_CONFIG = {
    "enabled": True,                    # 是否启用设备
    "device_model": "628ch",            # 设备型号
    
    # 网络通信设置
    "network": {
        "ip_address": "192.168.1.100",  # 设备IP地址
        "command_port": 10080,           # 命令端口
        "stream_port": 10081,            # 数据流端口
        "username": "admin",             # 用户名
        "password": "123456",            # 密码
        "connection_timeout": 5.0,       # 连接超时（秒）
        "auto_discover": True,           # 是否自动发现设备
        "retry_attempts": 3,             # 连接重试次数
        "retry_delay": 2.0               # 重试间隔（秒）
    },
    
    # 热成像传感器参数
    "sensor": {
        "width": 640,                    # 图像宽度
        "height": 480,                   # 图像高度（修正为标准分辨率）
        "pixel_format": "raw16",         # 像素格式
        "frame_rate": 25,                # 帧率
        "temperature_range": {
            "min": -20.0,                # 测温范围最小值（°C）
            "max": 650.0                 # 测温范围最大值（°C）（628ch高温型）
        }
    },
    
    # 温度计算参数
    "temperature": {
        "emissivity": 0.95,              # 发射率
        "reflected_temperature": 20.0,   # 反射温度（°C）
        "atmospheric_temperature": 20.0, # 大气温度（°C）
        "distance": 1.0,                 # 距离（米）
        "relative_humidity": 50.0,       # 相对湿度（%）
        "external_optics_transmission": 1.0,  # 外部光学透射率
        "external_optics_temperature": 20.0,  # 外部光学温度（°C）
        "use_lut": True,                 # 是否使用查找表
        "lut_size": 65536               # 查找表大小
    },
    
    # 实时显示设置
    "display": {
        "enabled": True,
        "width": 640,                   # 显示宽度
        "height": 480,                  # 显示高度
        "colormap": "jet",              # 伪彩色映射
        "update_interval": 40,          # 更新间隔（ms）约25fps
        "auto_range": True,             # 自动温度范围
        "range_padding": 2.0            # 温度范围扩展（°C）
    },
    
    # 数据存储与记录
    "recording": {
        "enabled": True,
        "raw_data": True,               # 保存原始数据
        "temperature_data": True,       # 保存温度数据
        "image_format": "png",          # 图像格式
        "data_formats": ["npy", "npz", "csv"],  # 数据格式
        "compression": True,            # 是否压缩
        "metadata": True                # 是否保存元数据
    },
    
    # 模拟模式（用于开发调试）
    "simulation": {
        "enabled": False,               # 是否启用模拟模式
        "pattern": "gradient",          # 模拟图案：gradient/random/hotspots
        "base_temperature": 25.0,       # 基础温度（°C）
        "temperature_variation": 10.0,  # 温度变化范围（°C）
        "noise_level": 0.2,            # 噪声水平
        "hotspot_count": 3,            # 热点数量
        "update_rate": 25              # 更新频率（fps）
    },
    
    # FOTRIC SDK库配置
    "sdk": {
        "dll_path": "StreamSDK.dll",    # StreamSDK DLL路径
        "rest_dll_path": "restc.dll",   # REST API DLL路径
        "radiation_dll_path": "Radiation.dll",  # 温度计算DLL路径
        "detect_dll_path": "DetectSDK.dll",     # 设备发现DLL路径
        "thread_pool_size": 4,          # 线程池大小
        "buffer_size": 1024000,         # 缓冲区大小
        "max_packet_size": 65536        # 最大包大小
    },
    
    # 开发调试选项
    "debug": {
        "verbose": True,                # 详细输出
        "log_level": "INFO",           # 日志级别
        "save_debug_images": False,     # 保存调试图像
        "performance_stats": True,      # 性能统计
        "connection_monitor": True      # 连接监控
    },
    
    # 高级功能设置
    "advanced": {
        "stream_buffer_count": 10,      # 流缓冲区数量
        "processing_threads": 2,        # 处理线程数
        "temperature_filter": "none",   # 温度滤波：none/gaussian/median
        "error_recovery": True,         # 错误恢复
        "auto_reconnect": True,         # 自动重连
        "reconnect_interval": 5.0       # 重连间隔（秒）
    }
}

# 网络设备发现配置
DEVICE_DISCOVERY = {
    "enabled": True,
    "timeout": 10.0,                   # 发现超时（秒）
    "interface": "",                   # 网络接口（空为自动）
    "broadcast_interval": 2.0,         # 广播间隔（秒）
    "max_devices": 10                  # 最大设备数
}

# FOTRIC 设备错误码定义
ERROR_CODES = {
    "FOTRIC_OK": 0,
    "FOTRIC_CONNECT_FAILED": 1001,
    "FOTRIC_LOGIN_FAILED": 1002,
    "FOTRIC_STREAM_FAILED": 1003,
    "FOTRIC_TIMEOUT": 1004,
    "FOTRIC_SDK_ERROR": 1005,
    "FOTRIC_DEVICE_NOT_FOUND": 1006,
    "FOTRIC_INVALID_PARAM": 1007,
    "FOTRIC_MEMORY_ERROR": 1008
}

# REST API URL路径定义
API_URLS = {
    "admin_info": "/admin/info",
    "admin_boot_id": "/admin/boot-id",
    "admin_reboot": "/admin/reboot",
    "sensor_dimension": "/sensor/dimension",
    "sensor_lut": "/sensor/lut",
    "sensor_luts": "/sensor/luts",
    "sensor_lut_table": "/sensor/luts/{0}?list",
    "sensor_t_range": "/sensor/t-range",
    "stream_video_raw": "/stream/video/raw",
    "stream_video_pri": "/stream/video/pri", 
    "stream_video_sub": "/stream/video/sub",
    "isp_instrument_jconfig": "/isp/instrument/jconfig",
    "isp_temperature": "/isp/t?x={0}&y={1}",
    "isp_snapshot": "/isp/snapshot",
    "capture": "/capture/{0}",
    "capture_modes": "/capture/modes"
}
