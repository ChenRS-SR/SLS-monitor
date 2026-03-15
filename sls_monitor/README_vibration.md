# 振动检测系统使用指南

## 概述
这个振动检测系统基于你提供的 `check_vibration_trigger` 函数，已经集成到我们的SLS监控项目中，可以检测振动信号并在界面上显示相关信息和日志。

## 主要功能

### 1. 振动检测
- **实时振动监测**: 持续检测振动传感器数据
- **智能阈值触发**: 可配置的振动阈值，超过时触发警报
- **多种检测算法**: 支持7种不同的振动检测算法
- **防抖处理**: 避免频繁误触发
- **噪声过滤**: 过滤低强度噪声信号

### 2. 界面显示
- **实时状态显示**: 显示当前振动强度和状态
- **颜色编码**: 根据振动级别显示不同颜色
- **系统日志**: 在界面上显示详细的振动检测日志
- **配置界面**: 可以实时调整检测参数

### 3. 日志记录
- **多级别日志**: DEBUG、INFO、WARNING、ERROR、CRITICAL
- **时间戳**: 每条日志都包含准确的时间戳
- **振动事件记录**: 详细记录每次振动触发事件
- **界面和终端双输出**: 同时在界面和终端显示日志

## 快速开始

### 1. 基本使用
```python
from devices.vibration import VibrationDevice

# 创建振动设备实例
vibration_device = VibrationDevice()

# 连接设备
if vibration_device.connect():
    print("设备连接成功")
    
    # 检测振动
    triggered, magnitude = vibration_device.check_vibration_trigger()
    
    if triggered:
        print(f"检测到振动！强度: {magnitude:.3f}")
    
    # 断开连接
    vibration_device.disconnect()
```

### 2. 在界面中集成
```python
import tkinter as tk
from devices.vibration import VibrationDevice

class YourApp:
    def __init__(self):
        self.vibration_device = VibrationDevice()
        
        # 注册日志回调，在界面上显示日志
        self.vibration_device.add_log_callback(self.show_log_in_ui)
    
    def show_log_in_ui(self, message, level="INFO"):
        # 在界面的日志区域显示消息
        self.log_text.insert(tk.END, f"[{level}] {message}\\n")
    
    def start_monitoring(self):
        # 启动监测线程
        threading.Thread(target=self.monitoring_loop, daemon=True).start()
    
    def monitoring_loop(self):
        while True:
            triggered, magnitude = self.vibration_device.check_vibration_trigger()
            if triggered:
                # 处理振动触发事件
                self.handle_vibration_event(magnitude)
            time.sleep(0.1)
```

### 3. 配置检测参数
```python
# 更新检测配置
new_config = {
    "motion_threshold": 0.08,      # 提高触发阈值
    "debounce_time": 1.0,          # 增加防抖时间
    "verbose_logging": True        # 启用详细日志
}

vibration_device.update_detection_config(new_config)
```

## 配置说明

### 振动检测配置 (VIBRATION_DETECTION_CONFIG)
- `motion_threshold`: 振动触发阈值 (默认: 0.05)
- `debounce_time`: 防抖时间，秒 (默认: 0.5)
- `noise_filter_enabled`: 是否启用噪声过滤 (默认: True)
- `min_signal_strength`: 最小信号强度 (默认: 0.001)
- `max_detection_rate`: 最大检测频率，Hz (默认: 10)
- `verbose_logging`: 是否输出详细日志 (默认: True)

### 振动级别定义 (VIBRATION_LEVELS)
- **轻微振动** (low): < 0.01, 绿色
- **中等振动** (medium): 0.01 - 0.05, 橙色
- **强烈振动** (high): 0.05 - 0.1, 红色
- **危险振动** (critical): > 0.1, 紫色

## 示例程序

### 1. 完整的GUI示例
运行 `examples/vibration_monitor_example.py` 查看完整的图形界面示例。

### 2. 集成指南
查看 `examples/integration_guide.py` 了解如何将振动检测集成到现有项目中。

## API 参考

### VibrationDevice 主要方法

#### `check_vibration_trigger()`
检查振动信号是否超过阈值
- **返回**: `(triggered: bool, magnitude: float)`
- **说明**: 这是核心检测方法，等同于你提供的原始函数

#### `add_log_callback(callback)`
添加日志回调函数
- **参数**: `callback(message, level)` - 日志回调函数
- **说明**: 用于在界面上显示日志

#### `update_detection_config(config)`
更新检测配置
- **参数**: `config: dict` - 新的配置参数
- **返回**: `bool` - 是否更新成功

#### `get_vibration_status()`
获取当前振动状态
- **返回**: `dict` - 包含振动强度、级别、数据等信息

#### `get_vibration_level(magnitude=None)`
获取振动级别描述
- **参数**: `magnitude: float` - 振动强度（可选）
- **返回**: `dict` - 包含级别名称、颜色、描述等

## 调试模式

当设备未连接时，系统会自动进入调试模式：
- 返回随机的低强度振动值
- 每10秒模拟一次振动触发事件
- 用于测试界面和逻辑功能

## 错误处理

系统包含完善的错误处理机制：
- 自动重试连接
- 错误计数和限流输出
- 异常情况下的安全降级
- 详细的错误日志记录

## 注意事项

1. **线程安全**: 界面更新必须在主线程中进行，使用 `root.after()` 方法
2. **资源管理**: 程序结束时记得调用 `disconnect()` 释放资源
3. **配置持久化**: 可以将配置保存到文件中实现持久化
4. **性能优化**: 可以根据需要调整检测频率和缓冲区大小

## 故障排除

### 常见问题
1. **设备连接失败**: 检查串口号、波特率、设备地址配置
2. **检测不敏感**: 降低 `motion_threshold` 值
3. **误触发过多**: 增加 `debounce_time` 或启用噪声过滤
4. **界面卡顿**: 降低检测频率或优化日志输出

### 日志级别说明
- **DEBUG**: 详细的调试信息
- **INFO**: 一般信息，如状态变化
- **WARNING**: 警告信息，如振动触发
- **ERROR**: 错误信息，如连接失败
- **CRITICAL**: 严重错误，如系统异常