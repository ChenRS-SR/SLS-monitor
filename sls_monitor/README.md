# SLS Monitor

SLS监控系统是一个用于选择性激光烧结(SLS)设备的综合监控解决方案。该系统集成了摄像头监控、红外热像传感器(IR8062)和振动检测功能，用于实时监控SLS制造过程。

## 项目结构

```
sls_monitor/
├── config/                     # 配置文件
│   ├── ir8062_config.py           # IR8062红外热像传感器配置
│   ├── system_config.py           # 系统配置
│   ├── vibration_config.py        # 振动传感器配置
│   └── settings.py                # 通用设置
├── core/                       # 核心功能模块
│   ├── powder_detector.py         # 扑粉检测逻辑
│   ├── image_processor.py          # 图像处理
│   └── data_logger.py             # 数据记录
├── devices/                    # 设备控制
│   ├── camera.py                  # 摄像头控制
│   ├── ir8062.py                  # IR8062红外热像传感器驱动
│   ├── infrared.py                # 通用红外设备控制
│   ├── vibration.py               # 振动传感器控制
│   ├── vibration_optimizer.py     # 振动数据优化
│   └── device_model.py            # 设备模型基类
├── examples/                   # 示例和调试脚本
│   ├── ir8062_debug.py            # IR8062调试脚本
│   ├── inspect_interfaces.py      # 接口检测工具
│   ├── bruteforce_ir8062.py       # IR8062启动探测
│   └── vibration_monitor_example.py # 振动监控示例
├── test_ir8062/               # IR8062测试模块
│   └── test.py                    # IR8062测试脚本
├── tools/                      # 实用工具
│   ├── scan_ir_serial.py          # 串口扫描工具
│   └── probe_uvc.py               # UVC设备探测
├── ui/                        # 用户界面
│   ├── main_window.py             # 主窗口
│   └── [其他UI组件]
├── utils/                     # 工具类
│   ├── error_handler.py           # 错误处理
│   ├── logger.py                  # 日志工具
│   └── [其他工具类]
├── main.py                    # 程序入口
├── run.py                     # 启动脚本
└── requirements.txt           # 项目依赖

```

## 功能特点

1. **多源数据采集**
   - 摄像头实时监控
   - IR8062红外热像传感器温度监测(80×62分辨率)
   - WTVB02-485振动传感器数据采集
   - 支持模拟模式和硬件模式

2. **IR8062红外热像功能**
   - 串口/USB通信支持
   - 实时温度数据解析
   - 自动/查询双模式
   - 自动波特率检测
   - 温度数据可视化(伪彩色映射)
   - 原始数据探测和调试工具

3. **智能扑粉检测**
   - 基于振动阈值的扑粉过程检测
   - 自动图像捕获触发
   - 可配置的检测参数和优化算法
   - 实时振动数据分析

4. **数据可视化与处理**
   - 实时视频显示
   - 热力图显示(支持多种颜色映射)
   - 振动数据实时图表
   - 自动温度范围调整

5. **数据记录与导出**
   - 图像和视频存储
   - 温度数据记录(CSV/NPY格式)
   - 振动数据日志
   - 元数据信息保存
   - 统计数据导出

## 系统要求

- Python 3.7+
- Windows 10/11 (主要测试平台)
- OpenCV 4.5+
- NumPy 1.21+
- PySerial 3.5+

### 支持的硬件

- **红外热像传感器**: IR8062 (80×62分辨率)
  - 串口通信 (USB转串口)
  - 波特率: 115200/921600/1500000
  - 温度分辨率: 0.1°C
- **振动传感器**: WTVB02-485
  - RS485通信接口
  - 可配置采样率和灵敏度
- **摄像头**: USB摄像头 (支持UVC标准)
- **其他**: 支持多种USB-Serial转换器

## 安装步骤

1. 克隆或下载项目：
   ```bash
   git clone [repository_url]
   cd SLS
   ```

2. 创建虚拟环境 (推荐)：
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # 或
   source venv/bin/activate  # Linux/Mac
   ```

3. 安装依赖：
   ```bash
   pip install -r sls_monitor/requirements.txt
   ```

4. 配置设备：
   - 修改 `sls_monitor/config/ir8062_config.py` 设置串口号
   - 修改 `sls_monitor/config/vibration_config.py` 设置振动传感器参数
   - 确保所有设备正确连接

5. 运行程序：
   ```bash
   # 主程序
   python run.py
   
   # 或运行IR8062测试
   python -m sls_monitor.test_ir8062.test --port COM16
   
   # 或运行调试脚本
   python -m sls_monitor.examples.ir8062_debug --port COM16
   ```

## 使用说明

### 1. 基础使用

```bash
# 启动主程序
python run.py

# IR8062测试 (模拟模式)
python -m sls_monitor.test_ir8062.test --simulation --frames 50

# IR8062测试 (硬件模式)
python -m sls_monitor.test_ir8062.test --port COM16
```

### 2. 调试和诊断工具

```bash
# 接口检测 (查看可用串口和摄像头)
python -m sls_monitor.examples.inspect_interfaces

# IR8062调试 (原始数据探测)
python -m sls_monitor.examples.ir8062_debug --port COM16 --raw 2

# 串口扫描
python -m sls_monitor.tools.scan_ir_serial --port COM16 --seconds 3

# 暴力启动探测 (尝试不同的启动命令)
python -m sls_monitor.examples.bruteforce_ir8062 --port COM16
```

### 3. 数据采集模式

- **自动模式**: 系统自动检测扑粉过程并采集数据
- **查询模式**: 手动发送查询命令获取温度数据
- **模拟模式**: 生成模拟温度数据用于测试

### 4. 数据保存

- 温度数据: `.npy` 和 `.csv` 格式
- 伪彩色图像: `.png` 格式
- 元数据: `.txt` 格式
- 默认保存路径: `captures/` 目录

## 配置说明

### 1. IR8062红外热像传感器配置
**文件**: `config/ir8062_config.py`
```python
IR8062_CONFIG = {
    "port": "COM16",              # 串口号
    "baudrate": 1500000,         # 波特率
    "auto_baud": True,           # 自动波特率检测
    "resolution": {"width": 80, "height": 62},
    "temperature_range": {"min": 20.0, "max": 40.0},
    "auto_range": {"enabled": True},  # 自动温度范围
    "debug": {"verbose": True},       # 调试输出
    "raw_probe_seconds": 2.0,         # 原始数据探测时间
    "bootstrap_sequence": ["query:5", "delay:200", "auto"]
}
```

### 2. 振动传感器配置
**文件**: `config/vibration_config.py`
- 串口参数设置
- 振动阈值配置
- 检测算法参数
- 优化器设置

### 3. 系统配置
**文件**: `config/system_config.py`
- 输出目录设置
- 日志配置
- 时间戳格式
- 全局参数

## 注意事项

1. **硬件连接**
   - 确保所有设备正确连接并启动
   - 检查USB端口和串口设置

2. **数据保存**
   - 定期备份重要数据
   - 监控磁盘空间使用

3. **系统维护**
   - 定期检查日志文件
   - 及时更新系统配置

## 常见问题与解决方案

### 1. IR8062无数据问题
**现象**: 串口连接成功但读取不到温度数据
```bash
# 诊断步骤
python -m sls_monitor.examples.inspect_interfaces  # 检查接口
python -m sls_monitor.examples.ir8062_debug --port COM16 --raw 3  # 原始数据探测
python -m sls_monitor.examples.bruteforce_ir8062 --port COM16  # 尝试启动命令
```
**可能原因**:
- 设备可能使用UVC接口而非串口
- 需要特定的启动命令序列
- 波特率不匹配
- 硬件连接问题

### 2. 串口通信问题
**现象**: 无法打开串口或权限错误
- 检查串口号是否正确 (设备管理器)
- 确保没有其他程序占用串口
- Windows下可能需要管理员权限
- 检查USB驱动是否正确安装

### 3. 依赖安装问题
```bash
# 如果OpenCV安装失败
pip install opencv-python-headless  # 无GUI版本

# 如果pyserial安装失败
pip install pyserial --upgrade

# 如果numpy安装失败
pip install numpy --upgrade
```

### 4. 模拟模式测试
如果硬件有问题，可以使用模拟模式测试软件功能：
```bash
python -m sls_monitor.test_ir8062.test --simulation --frames 10
```

## 技术支持

如有问题，请联系：
- 电子邮件：[your-email]
- 项目主页：[project-url]

## 许可证

本项目采用 MIT 许可证