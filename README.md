# SLS监控系统 (SLS Monitor)

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenCV](https://img.shields.io/badge/opencv-4.5+-green.svg)](https://opencv.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> 基于振动触发的选择性激光烧结(SLS)3D打印过程监控系统

## 📖 项目简介

SLS监控系统是一个专为选择性激光烧结(SLS)3D打印工艺设计的实时监控解决方案。系统通过多传感器融合（摄像头、红外热像仪、振动传感器）实现对打印过程的全面监控，并基于振动信号自动触发图像捕获，记录每层打印前后的状态。

### ✨ 核心特性

- 🔴 **双摄像头监控** - 主/副摄像头多角度实时监控
- 🌡️ **红外热成像** - 支持Fotric 628ch和IR8062两种热像仪
- 📳 **振动检测** - 智能识别铺粉动作，自动触发拍照
- 🤖 **状态机模式** - 支持单向/双向刮刀两种铺粉模式
- 📸 **自动图像捕获** - 基于振动触发的before/after图像记录
- 📊 **数据记录** - 完整的温度、振动、图像数据存储
- 🖥️ **图形界面** - 基于Tkinter的友好操作界面

## 🏗️ 系统架构

```
SLS Monitor
├── 📷 视觉监控层
│   ├── 主摄像头 (USB Camera)
│   └── 副摄像头 (USB Camera)
│
├── 🌡️ 温度监控层
│   ├── Fotric 628ch (网络接口)
│   └── IR8062 (USB串口)
│
├── 📳 振动检测层
│   └── WTVB02-485 (RS485串口)
│
├── 🧠 核心逻辑层
│   ├── 扑粉检测器 (状态机)
│   └── 数据记录器
│
└── 🖥️ 用户界面层
    └── Tkinter GUI
```

## 🚀 快速开始

### 环境要求

- Windows 10/11
- Python 3.8+
- USB端口（摄像头、IR8062）
- 网络接口（Fotric热像仪）
- RS485串口（振动传感器）

### 安装步骤

1. **克隆仓库**
```bash
git clone git@github.com:ChenRS-SR/SLS-monitor.git
cd SLS-monitor
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **快速启动**
```bash
# 方式1：使用启动脚本
启动SLS.bat

# 方式2：直接运行
python run.py
```

## 📁 项目结构

```
SLS/
├── run.py                      # 主入口程序
├── 启动SLS.bat                # Windows快速启动脚本
├── requirements.txt           # Python依赖清单
├── README.md                  # 项目说明
│
├── sls_monitor/               # 核心监控模块
│   ├── main.py               # 系统主程序
│   ├── ui/                   # 用户界面
│   │   ├── main_window.py    # 主窗口
│   │   ├── camera_panel.py   # 摄像头面板
│   │   ├── thermal_panel.py  # 热成像面板
│   │   ├── control_panel.py  # 控制面板
│   │   └── vibration_panel.py # 振动面板
│   ├── devices/              # 设备驱动
│   │   ├── camera.py         # USB摄像头
│   │   ├── Fotric_628ch*.py  # Fotric热像仪
│   │   ├── ir8062*.py        # IR8062热像仪
│   │   ├── vibration.py      # 振动传感器
│   │   └── servo_controller.py # 伺服控制
│   ├── core/                 # 核心功能
│   │   ├── powder_detector.py # 扑粉检测器
│   │   └── data_logger.py    # 数据记录器
│   ├── config/               # 配置文件
│   └── utils/                # 工具函数
│
├── pysenxor-master/          # IR8062依赖库
├── DataAnalysis/             # 数据分析模块
└── output/                   # 输出目录
    ├── images/              # 捕获图像
    ├── logs/                # 日志文件
    └── data/                # 数据文件
```

## ⚙️ 配置说明

### 系统配置 (`sls_monitor/config/system_config.py`)

```python
# 红外摄像头选择
THERMAL_CAMERA_CONFIG = {
    "thermal_camera_type": 1,  # 0: IR8062, 1: Fotric628ch
    "fotric_ip": "192.168.1.100",
    "fotric_port": 10080,
    "simulation_mode": False,  # 是否使用模拟模式
}

# 默认工艺参数
DEFAULT_PARAMS = {
    'layer_thickness': 0.1,   # 分层厚度 (mm)
    'fill_spacing': 0.1,      # 填充间距 (mm)
    'fill_speed': 2000,       # 填充速度 (mm/s)
    'fill_power': 10          # 填充功率 (W)
}
```

### 振动配置 (`sls_monitor/config/vibration_config.py`)

```python
VIBRATION_CONFIG = {
    "com_port": "COM3",       # 串口号
    "baudrate": 9600,         # 波特率
    "address": 1              # 设备地址
}
```

## 🎯 使用指南

### 启动系统

1. 连接所有硬件设备
2. 运行 `启动SLS.bat` 或 `python run.py`
3. 系统会自动检测并初始化设备

### 界面操作

| 功能区 | 说明 |
|--------|------|
| 主摄像头视图 | 显示主摄像头实时画面 |
| 红外热像视图 | 显示温度分布热图 |
| 控制面板 | 启动/停止监控、拍照、参数设置 |
| 工艺参数 | 设置分层厚度、填充间距等 |
| 振动监测 | 实时显示振动数据 |

### 状态机模式

系统支持两种铺粉检测模式：

#### 🔵 简单模式（单向刮刀）
```
idle → motion → idle
```
适用于双粉缸SLS打印机，刮刀单向运动

#### 🟠 复杂模式（双向刮刀）
```
idle → first_motion → between_motions → second_motion → idle
```
适用于传统SLS打印机，铺粉+平整两个动作

## 📸 图像捕获

系统会自动在以下时机捕获图像：
- **Before**: 检测到铺粉动作开始时
- **After**: 铺粉动作结束后

图像命名格式：`L{层数:04d}_{before/after}_{时间戳}.png`

## 🔧 故障排除

### 设备连接失败

1. **摄像头未找到**
   - 检查USB连接
   - 修改 `camera_config.py` 中的摄像头索引

2. **红外热像仪连接失败**
   - 检查网络连接（Fotric）或USB连接（IR8062）
   - 系统会自动切换到模拟模式

3. **振动传感器无数据**
   - 检查RS485连接
   - 确认串口号配置正确
   - 检查设备地址

### 状态机不触发

1. 检查振动阈值设置是否合适
2. 查看振动面板是否有数据更新
3. 调整防抖时间参数

## 📚 文档

- [最终部署清单](最终部署清单.md) - 部署和移植指南
- [状态机模式说明](状态机模式说明.md) - 扑粉检测逻辑详解
- [标定思路](标定思路.md) - 相机标定方法

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 👨‍💻 作者

**ChenRS** - [GitHub](https://github.com/ChenRS-SR)

---

> 💡 **提示**: 首次使用前建议运行 `python 部署验证.py` 检查系统环境
