"""
Powder detection configuration settings
"""

# 集成所有影响检测灵敏度的参数，便于调整和调试
POWDER_DETECTION_CONFIG = {
    # 核心振动阈值
    "motion_threshold": 0.05,          # 主振动触发阈值（降低到0.05进行调试）
    "motion_threshold_factor": 0.1,    # 静止判断阈值系数（主阈值的30%）
    
    # 时间控制参数
    "debounce_time": 1,              # 防抖时间（秒），避免重复触发（增加到1.5s）
    "first_motion_min_duration": 2.0,  # 第一次振动最小持续时间（秒）
    "between_motions_min_wait": 0.8,   # 两次振动之间最小等待时间（秒）
    "between_motions_timeout": 15.0,   # 等待第二次振动超时时间（秒）- 增加到15秒
    "second_motion_settle_time": 0.5,  # 第二次振动停止后等待稳定时间（秒）
    
    # 连续性检查参数
    "required_consecutive_low": 20,     # 需要连续低于阈值的次数（增加到40次）
    "consecutive_check_time": 2.0,     # 连续性检查时间阈值（增加到2秒）
    
    # 第一次振动后拍照参数（简化逻辑）
    "first_motion_settle_time": 0.3,   # 第一次振动停止后的平息等待时间（秒）
    
    # 额外保护参数
    "noise_filter_enabled": True,      # 启用噪声过滤
    "max_detection_rate": 0.1,         # 最大检测频率（次/秒），防止过度检测
    "stability_check_enabled": True,   # 启用稳定性检查
    "min_signal_strength": 0.05,       # 最小信号强度阈值
    "smart_detection_enabled": False,  # 智能检测模式（已禁用，使用简单第一次振动检测）
    
    # 调试和监控
    "verbose_logging": True,           # 详细日志输出
    "detection_stats_enabled": True,  # 启用检测统计
    
    # 系统性能参数
    "main_loop_delay": 0.02,          # 主循环延迟（秒）
    "pause_delay": 0.1,               # 暂停时延迟（秒）
    "state_reset_delay": 0.05,        # 状态重置延迟（秒）
    
    # 图像稳定参数
    "after_stabilization_time": 0.3,  # after图像稳定等待时间（秒）
}