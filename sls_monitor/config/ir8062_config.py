"""
IR8062红外传感器配置模块
"""

# 串口设置
IR8062_CONFIG = {
    "enabled": True,              # 是否启用传感器
    "port": "COM16",              # 串口号（Thermal USB Camera 连接后可能不同，如 COM7）
    "baudrate": 1500000,         # 波特率（若厂商示例不同请调整）
    "auto_baud": True,            # 启动时尝试多波特率探测（若无数据可保持True以防配置错误）
    "baud_candidates": [1500000, 921600, 115200],  # 探测候选顺序
    "toggle_lines": True,         # 打开后连接时尝试 DTR/RTS 翻转以激活输出
    "query_fallback_threshold": 40, # 连续空读达到阈值发送一次查询指令
    "timeout": 1,                # 读取超时（秒）

    # 传感器参数
    "resolution": {
        "width": 80,             # 图像宽度
        "height": 62             # 图像高度
    },
    "frame_size": 9938,          # 完整帧大小（字节）（2字节*80*62=9920 + 可能18字节头）
    "frame_header": [0x5A, 0x5A],# 帧头标识（需与实际协议核实）
    "header_size": 18,           # 估计的帧头长度（如果厂商协议不同请调整）

    # 温度设置（初始显示范围，可启用自动范围）
    "temperature_range": {
        "min": 20.0,
        "max": 40.0
    },
    "auto_range": {
        "enabled": True,        # 根据帧数据自动平滑调整显示范围
        "alpha": 0.1,           # 指数平滑系数
        "padding": 2.0          # 上下各扩展摄氏度
    },
    "emissivity": 1.0,

    # 显示设置
    "display": {
        "enabled": True,
        "width": 400,
        "height": 310,
        "colormap": "jet",
        "update_interval": 33   # ms （模拟模式用作帧间隔）
    },

    # 数据记录
    "save_data": {
        "enabled": True,
        "format": "csv",
        "interval": 1.0
    },

    # 模拟模式（旧字段兼容）
    "mock_mode": {
        "enabled": False,
        "base_temp": 30.0,
        "noise_level": 0.5,
        "hot_spot_temp": 40.0
    },

    # 新的 simulation 字段（供驱动内部优先使用）
    "simulation": {
        "pattern": "gradient",   # gradient | random
        "noise_level": 0.5,
        "update_interval": 0.05   # 秒
    },

    # 调试选项（开发期使用，生产可关闭）
    "debug": {
        "verbose": True,         # 输出等待/缓冲状态
        "hex_head": True,        # 首次打印前32字节HEX
        "stats": True,           # 周期打印帧统计
        "stats_interval": 20,    # 间隔帧数
        "max_buffer": 120000     # 缓冲区最大字节
    },

    # 启动增强参数
    "raw_probe_seconds": 2.0,             # 上电后先抓取原始字节探测时间(秒)
    # 可自定义引导序列: 字符串列表: query:N / delay:MS / auto
    # 例如 ["query:5", "delay:200", "auto"] 表示先查询5次, 延迟200ms, 再切自动模式
    "bootstrap_sequence": ["query:5", "delay:200", "auto"]
}