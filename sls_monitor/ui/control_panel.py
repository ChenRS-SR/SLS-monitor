"""
控制面板模块
实现系统控制和状态显示
"""

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import json
import os
import time
import csv
import cv2
import numpy as np
from datetime import datetime
from sls_monitor.config.system_config import DEFAULT_PARAMS, DEFAULT_SAVE_PATH_CONFIG
from sls_monitor.config.servo_config import SERVO_CONFIG, SERVO_POSITION

# 尝试导入舵机控制器
try:
    from ..devices.servo_controller import ServoController
    SERVO_AVAILABLE = True
except ImportError:
    SERVO_AVAILABLE = False
    print("警告: servo_controller模块未找到，舵机功能不可用")

# 尝试导入日志系统，如果失败则使用占位函数
try:
    from ..utils.logger import log_debug, log_info, log_warning, log_error
except ImportError:
    # 如果导入失败，创建占位函数
    def log_debug(msg, component="CONTROL_PANEL"):
        print(f"[DEBUG] [{component}] {msg}")
    def log_info(msg, component="CONTROL_PANEL"):
        print(f"[INFO] [{component}] {msg}")
    def log_warning(msg, component="CONTROL_PANEL"):
        print(f"[WARNING] [{component}] {msg}")
    def log_error(msg, component="CONTROL_PANEL"):
        print(f"[ERROR] [{component}] {msg}")

class ControlPanel:
    """控制面板类，用于系统控制和状态显示"""
    
    def __init__(self, parent, devices, start_callback, stop_callback,
                 capture_callback, layer_callback):
        """
        初始化控制面板
        
        Args:
            parent: 父级窗口
            devices: 设备字典
            start_callback: 开始监控回调
            stop_callback: 停止监控回调
            capture_callback: 捕获图像回调
            layer_callback: 层数变化回调
        """
        self.frame = ttk.LabelFrame(parent, text="控制面板")
        # 应用加粗字体样式
        self.frame.configure(style='Bold.TLabelframe')
        self.devices = devices
        # 回调函数
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.capture_callback = capture_callback
        self.layer_callback = layer_callback
        # 当前算法
        self.current_algorithm = tk.StringVar(value="composite")
        # 状态变量
        self.monitoring = False
        self.current_layer = tk.StringVar(value="0")
        self.current_layer.trace('w', self._on_layer_change)
        # 摄像头调试开关
        self.debug_enabled = False
        # 根据配置设置默认保存路径
        if DEFAULT_SAVE_PATH_CONFIG["use_custom_default"] == 1:
            default_path = DEFAULT_SAVE_PATH_CONFIG["custom_default_path"]
        else:
            default_path = DEFAULT_SAVE_PATH_CONFIG["project_default_path"]
        
        # 保存位置相关变量
        self.save_path = tk.StringVar(value=default_path)
        # 记录相关变量
        self.recording = False  # 是否正在记录
        self.recording_paused = False  # 是否暂停记录
        self.recording_dir = ""  # 当前记录的文件夹
        self.recording_start_time = None  # 记录开始时间
        # 基于振动的状态检测变量
        self.motion_state = "idle"  # 当前运动状态: idle, first_motion, between_motions, second_motion (复杂模式) 或 idle, motion (简单模式)
        self.state_machine_mode = "simple"  # 状态机模式: "complex" 或 "simple"
        self.first_motion_detected = False  # 第一次振动是否检测到
        self.second_motion_detected = False  # 第二次振动是否检测到
        self.motion_threshold = 0.05  # 振动阈值
        self.debounce_time = 1.0  # 防抖时间
        self.last_trigger_time = 0  # 上次触发时间
        self.first_motion_start_time = 0  # 第一次运动开始时间
        self.between_motions_timeout = 15.0  # 两次运动之间的超时时间
        self.second_motion_settle_time = 0.5  # 第二次运动结束后的稳定时间
        self.motion_monitor_timer_id = None  # 运动监测定时器ID
        
        # 连续采样相关变量
        self.continuous_sampling = False  # 是否正在连续采样
        self.sampling_timer_id = None     # 采样定时器ID
        self.sampling_interval = 1.0      # 采样间隔（秒），对应1Hz
        self.current_frame_count = 0      # 当前帧计数
        self.sampling_start_time = None   # 采样开始时间
        
        # 工艺参数历史记录
        self.parameter_history = []       # 参数变化历史记录
        self.current_parameters = None    # 当前工艺参数
        self.parameters_start_layer = 0   # 当前参数开始的层数
        
        # main_data.csv记录相关
        self.main_data_records = []       # 主数据记录列表
        
        # 舵机控制器
        self.servo_controller = None      # 舵机控制器实例
        self.servo_config = SERVO_CONFIG.copy()  # 舵机配置
        
        # 初始化UI组件
        self._init_ui()
        # 注册振动设备的日志回调
        self._setup_vibration_logging()
        
        # 用于引用其他组件的属性（由主窗口设置）
        self.vibration_panel_ref = None  # 振动面板的引用
        self.parent_window_ref = None    # 主窗口的引用
        self.thermal_panel_ref = None    # 热像仪面板的引用
        
        # 线程化操作相关
        import threading
        self._capture_executor = None  # 用于异步捕获图像的线程池
        self._capture_lock = threading.Lock()  # 捕获操作的锁
        
        # 初始化时同步阈值到设备
        self._sync_threshold_to_device(self.motion_threshold)
        
        # 初始化时应用默认采样频率（根据界面默认值"不采样"）
        self._apply_sampling_frequency()

        # 日志节流配置（防止高频刷屏）
        self._log_last_times = {}
        # 关键模式 -> 最小打印间隔(秒) - 大幅增加间隔减少刷屏
        self._log_min_intervals = {
            "热像更新间隔": 10.0,  # 从1.0秒增加到10.0秒
            "数据读取失败": 5.0,   # 从2.0秒增加到5.0秒  
            "振动触发检查": 10.0,  # 从1.0秒增加到10.0秒
            "成功解析温度快照": 60.0,  # 改为60秒，大幅减少刷屏
            "成功获取全分辨率温度矩阵": 60.0,  # 改为60秒，大幅减少刷屏
            "[简单模式] idle状态": 10.0,  # 状态机循环检测日志节流
            "[简单模式] motion状态": 10.0,
            "[简单模式] 运动停止检查": 10.0,
            "[复杂模式] idle状态": 10.0,
            "[复杂模式] first_motion状态": 10.0,
            "[复杂模式] between_motions状态": 10.0,
            "[复杂模式] second_motion状态": 10.0,
        }

        # 错误去重相关变量
        self._last_error_message = None  # 上一条错误消息
        self._last_error_count = 0       # 重复错误计数
        self._last_error_timestamp = None  # 最后错误时间戳
    
    def _init_ui(self):
        """初始化UI布局"""
        # 主控制区
        main_control = ttk.Frame(self.frame)
        main_control.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # 保存位置区域
        save_path_frame = ttk.Frame(main_control)
        save_path_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(save_path_frame, text="保存位置:").pack(side=tk.LEFT)
        self.save_path_entry = ttk.Entry(save_path_frame, textvariable=self.save_path, width=20, state="readonly")
        self.save_path_entry.pack(side=tk.LEFT, padx=5)
        select_btn = ttk.Button(save_path_frame, text="选择文件夹", command=self._choose_save_folder)
        select_btn.pack(side=tk.LEFT)

        # 添加系统调试输出区域
        if 'vibration' in self.devices:
            debug_frame = ttk.LabelFrame(main_control, text="系统调试输出")
            # 应用加粗字体样式
            debug_frame.configure(style='SysDebug.TLabelframe')
            debug_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
            
            # 顶部控制按钮区域
            debug_control_frame = ttk.Frame(debug_frame)
            debug_control_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))
            
            # 日志级别选择
            ttk.Label(debug_control_frame, text="显示级别:").pack(side=tk.LEFT, padx=(0, 5))
            self.debug_level = tk.StringVar(value="重要信息")
            debug_level_combo = ttk.Combobox(
                debug_control_frame,
                textvariable=self.debug_level,
                values=["重要信息", "详细信息", "全部信息"],
                width=10,
                state="readonly"
            )
            debug_level_combo.pack(side=tk.LEFT, padx=(0, 10))
            debug_level_combo.bind('<<ComboboxSelected>>', self._on_debug_level_change)
            
            # 控制按钮
            clear_debug_btn = ttk.Button(debug_control_frame, text="清除", command=self._clear_debug_log)
            clear_debug_btn.pack(side=tk.RIGHT, padx=(5, 0))
            
            pause_debug_btn = ttk.Button(debug_control_frame, text="暂停", command=self._toggle_debug_pause)
            pause_debug_btn.pack(side=tk.RIGHT, padx=(5, 0))
            self.pause_debug_btn = pause_debug_btn  # 保存引用以便更新文本
            
            # 文本显示区域和滚动条
            text_frame = ttk.Frame(debug_frame)
            text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            
            self.vibration_debug_text = tk.Text(text_frame, height=4, width=50, wrap=tk.WORD, font=("Arial", 9))
            self.vibration_debug_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            debug_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.vibration_debug_text.yview)
            debug_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.vibration_debug_text.config(yscrollcommand=debug_scrollbar.set)
            
            # 初始化调试输出控制变量
            self.debug_paused = False

        # 主操作按钮区域（第一行）
        main_buttons_frame = ttk.Frame(main_control)
        main_buttons_frame.pack(side=tk.LEFT, padx=5)
        
        # 开始/停止按钮 - 使用tk.Button支持背景色
        self.start_button = tk.Button(
            main_buttons_frame,
            text="开始监控",
            command=self._toggle_monitoring,
            bg="#4CAF50",  # 绿色
            fg="white",
            activebackground="#45a049",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=2
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # 停止监控按钮 - 使用tk.Button支持背景色
        self.stop_button = tk.Button(
            main_buttons_frame,
            text="停止监控",
            command=self._stop_monitoring,
            bg="#f44336",  # 红色
            fg="white",
            activebackground="#da190b",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=2,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 手动捕获按钮 - 使用tk.Button支持背景色
        self.capture_button = tk.Button(
            main_buttons_frame,
            text="手动捕获",
            command=self._capture_images,
            bg="#2196F3",  # 蓝色
            fg="white",
            activebackground="#0b7dda",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=2,
            state=tk.DISABLED
        )
        self.capture_button.pack(side=tk.LEFT, padx=5)
        
        # 次要操作按钮区域（第二行）
        secondary_buttons_frame = ttk.Frame(main_control)
        secondary_buttons_frame.pack(side=tk.LEFT, padx=5)
        
        # 摄像头调试按钮
        self.debug_button = ttk.Button(
            secondary_buttons_frame,
            text="开启摄像头调试",
            command=self._toggle_camera_debug
        )
        self.debug_button.pack(side=tk.LEFT, padx=5)
        
        # 添加记录相关按钮
        recording_frame = ttk.Frame(self.frame)
        recording_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Label(recording_frame, text="数据记录:").pack(side=tk.LEFT, padx=(0, 10))
        
        # 记录控制按钮区域
        recording_buttons_frame = ttk.Frame(recording_frame)
        recording_buttons_frame.pack(side=tk.LEFT)
        
        # 开始/暂停/继续 切换按钮 - 使用tk.Button支持背景色
        self.toggle_recording_button = tk.Button(
            recording_buttons_frame,
            text="▶ 开始记录",
            command=self._toggle_recording,
            bg="#4CAF50",  # 绿色
            fg="white",
            activebackground="#45a049",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=2
        )
        self.toggle_recording_button.pack(side=tk.LEFT, padx=5)
        
        # 结束记录按钮 - 使用tk.Button支持背景色
        self.stop_recording_button = tk.Button(
            recording_buttons_frame,
            text="⏹ 结束记录",
            command=self._stop_recording,
            bg="#f44336",  # 红色
            fg="white",
            activebackground="#da190b",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=2,
            state=tk.DISABLED
        )
        self.stop_recording_button.pack(side=tk.LEFT, padx=5)
        
        # 采样频率控制区域
        sampling_frame = ttk.Frame(recording_frame)
        sampling_frame.pack(side=tk.RIGHT, padx=10)
        
        ttk.Label(sampling_frame, text="采样频率:").pack(side=tk.LEFT, padx=(0, 5))
        
        # 采样频率下拉菜单
        self.sampling_frequency = tk.StringVar(value="不采样")
        self.sampling_combo = ttk.Combobox(
            sampling_frame,
            textvariable=self.sampling_frequency,
            values=["0.2Hz (5.0s)", "0.5Hz (2.0s)", "1Hz (1.0s)", "2Hz (0.5s)", "5Hz (0.2s)", "10Hz (0.1s)","不采样"],
            width=12,
            state="readonly"
        )
        self.sampling_combo.pack(side=tk.LEFT, padx=2)
        
        # 应用按钮
        self.apply_sampling_button = ttk.Button(
            sampling_frame,
            text="应用采样频率",
            command=self._apply_sampling_frequency
        )
        self.apply_sampling_button.pack(side=tk.LEFT, padx=5)
        
        # 记录状态显示
        self.recording_status = ttk.Label(recording_frame, text="未记录")
        self.recording_status.pack(side=tk.RIGHT, padx=5)
        
        # 添加舵机控制区域
        self._create_servo_control_panel()
        
        # 添加振动监测区域
        debug_frame = ttk.LabelFrame(self.frame, text="振动监测")
        # 应用加粗字体样式
        debug_frame.configure(style='VibMon.TLabelframe')
        debug_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # 第一行：实时振动数据显示
        vibration_display_frame = ttk.Frame(debug_frame)
        vibration_display_frame.pack(fill=tk.X, pady=1)  # 减小间距
        
        ttk.Label(vibration_display_frame, text="当前振动强度:", font=("Arial", 9)).pack(side=tk.LEFT)  # 减小字体
        self.vibration_value_label = ttk.Label(vibration_display_frame, text="0.000", font=("Arial", 11, "bold"), foreground="blue")  # 减小字体
        self.vibration_value_label.pack(side=tk.LEFT, padx=8)  # 减小间距
        
        ttk.Label(vibration_display_frame, text="检测状态:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(15, 3))  # 减小字体和间距
        self.motion_state_label = ttk.Label(vibration_display_frame, text="idle", font=("Arial", 9, "bold"), foreground="green")  # 减小字体
        self.motion_state_label.pack(side=tk.LEFT, padx=3)  # 减小间距
        
        # 第二行：阈值调节
        threshold_frame = ttk.Frame(debug_frame)
        threshold_frame.pack(fill=tk.X, pady=1)  # 减小间距
        
        ttk.Label(threshold_frame, text="振动阈值:").pack(side=tk.LEFT)
        
        # 阈值滑块
        self.threshold_var = tk.DoubleVar(value=self.motion_threshold)
        self.threshold_scale = ttk.Scale(threshold_frame, from_=0.01, to=10, orient=tk.HORIZONTAL, 
                                        variable=self.threshold_var, command=self._on_threshold_scale_change)
        self.threshold_scale.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        # 阈值数值显示标签
        self.threshold_value_label = ttk.Label(threshold_frame, text=f"{self.motion_threshold:.2f}", font=("Arial", 9, "bold"), width=6)
        self.threshold_value_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # 快捷设置按钮
        ttk.Button(threshold_frame, text="敏感", command=lambda: self._set_threshold(0.1)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(threshold_frame, text="中等", command=lambda: self._set_threshold(0.5)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(threshold_frame, text="低敏", command=lambda: self._set_threshold(1.0)).pack(side=tk.RIGHT, padx=2)
        
        # 防抖时间控制
        debounce_frame = ttk.Frame(debug_frame)
        debounce_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(debounce_frame, text="防抖时间:").pack(side=tk.LEFT)
        
        # 防抖时间输入框
        self.debounce_var = tk.DoubleVar(value=self.debounce_time)
        debounce_entry = ttk.Entry(debounce_frame, textvariable=self.debounce_var, width=8)
        debounce_entry.pack(side=tk.LEFT, padx=5)
        debounce_entry.bind('<KeyRelease>', self._on_debounce_change)
        
        # 快捷设置按钮
        ttk.Button(debounce_frame, text="0.5s", command=lambda: self._set_debounce_time(0.5)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(debounce_frame, text="1.0s", command=lambda: self._set_debounce_time(1.0)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(debounce_frame, text="2.0s", command=lambda: self._set_debounce_time(2.0)).pack(side=tk.RIGHT, padx=2)
        
        # 第三行：测试控制
        test_frame = ttk.Frame(debug_frame)
        test_frame.pack(fill=tk.X, pady=2)
        
        self.test_mode = tk.BooleanVar(value=False)
        test_checkbox = ttk.Checkbutton(test_frame, text="测试模式（不保存图像）", variable=self.test_mode)
        test_checkbox.pack(side=tk.LEFT)
        
        # 第四行：状态机模式选择
        state_machine_frame = ttk.Frame(debug_frame)
        state_machine_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(state_machine_frame, text="状态机模式:").pack(side=tk.LEFT)
        
        # 简单模式：idle → motion → idle
        simple_radio = ttk.Radiobutton(state_machine_frame, text="简单模式(单向刮刀)", 
                                       value="simple", variable=tk.StringVar(value=self.state_machine_mode),
                                       command=self._on_state_machine_mode_change)
        simple_radio.pack(side=tk.LEFT, padx=5)
        
        # 复杂模式：idle → first_motion → between_motions → second_motion → idle  
        complex_radio = ttk.Radiobutton(state_machine_frame, text="复杂模式(双向刮刀)", 
                                        value="complex", variable=tk.StringVar(value=self.state_machine_mode),
                                        command=self._on_state_machine_mode_change)
        complex_radio.pack(side=tk.LEFT, padx=5)
        
        # 创建状态机模式变量并设置默认值
        self.state_machine_mode_var = tk.StringVar(value=self.state_machine_mode)
        simple_radio.config(variable=self.state_machine_mode_var)
        complex_radio.config(variable=self.state_machine_mode_var)
        
        ttk.Button(test_frame, text="重置状态", command=self._reset_motion_state).pack(side=tk.RIGHT, padx=5)
        ttk.Button(test_frame, text="手动触发", command=self._manual_trigger).pack(side=tk.RIGHT, padx=5)
        ttk.Button(test_frame, text="测试阈值同步", command=self._test_threshold_sync).pack(side=tk.RIGHT, padx=5)
        
        # 层数控制
        layer_frame = ttk.Frame(main_control)
        layer_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(layer_frame, text="当前层数:").pack(side=tk.LEFT)
        
        # 层数输入
        vcmd = (self.frame.register(self._validate_layer), '%P')
        self.layer_entry = ttk.Entry(
            layer_frame,
            textvariable=self.current_layer,
            width=5,
            validate='key',
            validatecommand=vcmd
        )
        self.layer_entry.pack(side=tk.LEFT, padx=5)
        
        # 层数控制按钮
        ttk.Button(
            layer_frame,
            text="+",
            width=2,
            command=lambda: self._change_layer(1)
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            layer_frame,
            text="-",
            width=2,
            command=lambda: self._change_layer(-1)
        ).pack(side=tk.LEFT)
        
        # 不再需要单独的系统日志区域，所有调试输出都在上面的调试输出区域显示
        
        # 启动振动数据显示更新
        self._update_vibration_display()

    def _choose_save_folder(self):
        """弹窗选择保存文件夹"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="选择保存位置")
        if folder:
            # 规范化 & 兼容 Windows 盘符根路径 (如 仅选中 "G:" 会导致后续 os.path.join 变成相对路径 "G:vibration_recording_...")
            import os
            original = folder
            folder = os.path.abspath(folder)
            # 如果用户只选了盘符根且没有反斜杠，补一个
            if len(folder) == 2 and folder[1] == ':':
                folder = folder + os.sep  # 变成 'G:\\'
            # 再次保证末尾没有多余空格
            folder = folder.strip()
            try:
                # 若目录不存在尝试创建（避免之后开始记录时报错又回退到默认的错觉）
                os.makedirs(folder, exist_ok=True)
            except Exception as e:
                messagebox.showerror("错误", f"创建目录失败: {folder}\n原因: {e}")
                self._log(f"❌ 保存路径修改失败: {folder} -> {e}")
                return
            old_path = self.save_path.get()
            self.save_path.set(folder)
            # 日志提示
            self._log(f"🗂️ 保存路径已修改: {old_path} -> {folder} (原始选择: {original})")

    # ---------------- 路径工具函数 ----------------
    def _get_base_save_path(self):
        """获取规范化的基础保存路径 (确保绝对路径 & 盘符根正确拼接)
        Returns:
            str: 规范化后的路径，不存在时会尝试创建
        Raises:
            OSError: 目录创建失败
        """
        import os
        path = self.save_path.get().strip()
        if not path:
            return ""  # 外层再判断
        path = os.path.abspath(path)
        if len(path) == 2 and path[1] == ':':  # 'G:' 这种情况
            path = path + os.sep
        # 尝试创建
        os.makedirs(path, exist_ok=True)
        return path
    
    def set_component_references(self, vibration_panel=None, parent_window=None, thermal_panel=None):
        """设置其他组件的引用
        
        Args:
            vibration_panel: VibrationPanel实例的引用
            parent_window: 主窗口的引用
            thermal_panel: ThermalPanel实例的引用
        """
        self.vibration_panel_ref = vibration_panel
        self.parent_window_ref = parent_window
        self.thermal_panel_ref = thermal_panel
        self._log("控制面板组件引用已设置（包括热像仪面板）")
        
        # 立即测试数据获取
        self._test_vibration_data_access()
    
    def _test_vibration_data_access(self):
        """测试振动数据获取方式"""
        try:
            self._log("=== 振动数据获取测试 ===")
            
            # 测试从振动面板获取
            if self.vibration_panel_ref:
                try:
                    magnitude_text = self.vibration_panel_ref.magnitude_label.cget("text")
                    self._log(f"振动面板显示: {magnitude_text}")
                except Exception as e:
                    self._log(f"从振动面板获取失败: {e}")
            
            # 测试从设备获取
            if 'vibration' in self.devices:
                device = self.devices['vibration']
                self._log(f"设备vibration_magnitude属性: {getattr(device, 'vibration_magnitude', '未找到')}")
                
                if hasattr(device, 'check_vibration_trigger'):
                    try:
                        is_triggered, magnitude = device.check_vibration_trigger()
                        self._log(f"check_vibration_trigger结果: triggered={is_triggered}, magnitude={magnitude}")
                    except Exception as e:
                        self._log(f"check_vibration_trigger失败: {e}")
            
            # 测试从主窗口获取
            if self.parent_window_ref:
                magnitude = getattr(self.parent_window_ref, 'vibration_magnitude', '未找到')
                self._log(f"主窗口vibration_magnitude: {magnitude}")
            
            self._log("=== 测试完成 ===")
            
        except Exception as e:
            self._log(f"振动数据测试失败: {e}")
    
    def _validate_layer(self, new_value):
        """验证层数输入"""
        if new_value == "":
            return True
        try:
            value = int(new_value)
            return value >= 0
        except ValueError:
            return False
    
    def _change_layer(self, delta):
        """改变层数"""
        try:
            current = int(self.current_layer.get())
            new_layer = max(0, current + delta)
            self.current_layer.set(str(new_layer))
        except ValueError:
            self.current_layer.set("0")
    
    def _on_layer_change(self, *args):
        """层数变化回调"""
        try:
            layer = int(self.current_layer.get())
            self.layer_callback(layer)
            
            # 如果正在记录，更新参数历史
            if self.recording:
                self._update_parameter_history_on_layer_change()
        except ValueError:
            pass
    
    def _clear_debug_log(self):
        """清除调试日志"""
        if hasattr(self, 'vibration_debug_text'):
            self.vibration_debug_text.delete(1.0, tk.END)
            self._log("🧹 调试日志已清除")
    
    def _toggle_debug_pause(self):
        """切换调试输出暂停状态"""
        self.debug_paused = not self.debug_paused
        if hasattr(self, 'pause_debug_btn'):
            if self.debug_paused:
                self.pause_debug_btn.config(text="继续")
                self._log("⏸️ 调试输出已暂停")
            else:
                self.pause_debug_btn.config(text="暂停")  
                self._log("▶️ 调试输出已恢复")
    
    def _on_debug_level_change(self, event=None):
        """调试级别改变回调"""
        level = self.debug_level.get()
        self._log(f"🔧 调试显示级别已设置为: {level}")
        
        # 更新过滤规则
        if level == "重要信息":
            # 只显示最重要的信息
            self._update_debug_filter_strict()
        elif level == "详细信息":
            # 显示中等重要的信息
            self._update_debug_filter_moderate()
        else:  # "全部信息"
            # 显示所有信息
            self._update_debug_filter_verbose()
    
    def _update_debug_filter_strict(self):
        """更新为严格过滤模式（只显示最重要信息）"""
        if not hasattr(self, '_debug_panel_throttle'):
            self._debug_panel_throttle = {}
        # 大幅增加节流时间
        self._debug_panel_throttle.update({
            "数据读取失败": 300.0,  # 5分钟
            "振动触发检查": 300.0,  # 5分钟
            "处理后数据": 600.0,    # 10分钟
            "综合强度": 600.0,      # 10分钟
            "振动调试运行正常": 900.0, # 15分钟
            "状态机运行中": 600.0,   # 10分钟
        })
    
    def _update_debug_filter_moderate(self):
        """更新为中等过滤模式"""
        if not hasattr(self, '_debug_panel_throttle'):
            self._debug_panel_throttle = {}
        # 中等节流时间
        self._debug_panel_throttle.update({
            "数据读取失败": 60.0,   # 1分钟
            "振动触发检查": 60.0,   # 1分钟
            "处理后数据": 120.0,    # 2分钟
            "综合强度": 120.0,      # 2分钟
            "振动调试运行正常": 300.0, # 5分钟
            "状态机运行中": 120.0,   # 2分钟
        })
    
    def _update_debug_filter_verbose(self):
        """更新为详细模式（显示更多信息）"""
        if not hasattr(self, '_debug_panel_throttle'):
            self._debug_panel_throttle = {}
        # 最小节流时间
        self._debug_panel_throttle.update({
            "数据读取失败": 10.0,   # 10秒
            "振动触发检查": 10.0,   # 10秒
            "处理后数据": 30.0,     # 30秒
            "综合强度": 30.0,       # 30秒
            "振动调试运行正常": 60.0,  # 1分钟
            "状态机运行中": 30.0,    # 30秒
        })
    
    def add_debug_log(self, message):
        """添加调试日志信息（带节流、过滤和错误去重）"""
        if not hasattr(self, 'vibration_debug_text'):
            return
        
        # 对界面调试输出应用节流机制和暂停控制
        should_show = self._should_show_in_debug_panel(message)
        if not should_show:
            return
        
        # 错误去重处理
        message = self._deduplicate_error(message)
        if message is None:  # 如果是重复错误且已合并，不显示
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        # 插入消息并自动滚动
        self.vibration_debug_text.insert(tk.END, formatted_message)
        self.vibration_debug_text.see(tk.END)  # 自动滚动到最底部
        
        # 限制日志行数，避免内存占用过多
        lines = self.vibration_debug_text.get(1.0, tk.END).split('\n')
        if len(lines) > 30:  # 进一步减少最大行数从50到30
            # 保留最新的25行
            self.vibration_debug_text.delete(1.0, tk.END)
            self.vibration_debug_text.insert(1.0, '\n'.join(lines[-25:]))
    
    def _deduplicate_error(self, message):
        """错误消息去重处理
        
        Args:
            message: 原始消息
            
        Returns:
            str: 处理后的消息，如果为None表示不显示（已合并到上一条）
        """
        import time
        
        # 定义需要合并的错误模式
        error_patterns = [
            "数据读取失败",
            "振动检测错误",
            "连接超时",
            "设备未响应",
        ]
        
        # 检查是否是错误消息
        is_error = any(pattern in message for pattern in error_patterns)
        
        if not is_error:
            # 非错误消息，重置错误计数并正常显示
            if self._last_error_message is not None:
                self._last_error_message = None
                self._last_error_count = 0
                self._last_error_timestamp = None
            return message
        
        # 是错误消息，检查是否与上一条相同
        current_time = time.time()
        
        if self._last_error_message == message:
            # 相同错误，增加计数
            self._last_error_count += 1
            self._last_error_timestamp = current_time
            # 更新上一条消息的显示，添加计数
            return None  # 不显示新消息，而是更新上一条
        else:
            # 不同错误或第一条错误
            # 如果有之前的重复错误，先显示合并结果
            if self._last_error_count > 1:
                # 更新上一条消息，添加计数信息
                self._update_last_error_with_count()
            
            # 记录新错误
            self._last_error_message = message
            self._last_error_count = 1
            self._last_error_timestamp = current_time
            return message
    
    def _update_last_error_with_count(self):
        """更新最后一条错误消息，添加重复计数"""
        try:
            # 获取所有文本
            all_text = self.vibration_debug_text.get(1.0, tk.END)
            lines = all_text.split('\n')
            
            if len(lines) >= 2:
                # 找到最后一条非空行
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip():
                        # 检查是否已经包含计数
                        if "(重复" not in lines[i]:
                            # 添加计数信息
                            lines[i] = f"{lines[i]} (重复 {self._last_error_count}次)"
                            # 更新文本
                            new_text = '\n'.join(lines)
                            self.vibration_debug_text.delete(1.0, tk.END)
                            self.vibration_debug_text.insert(1.0, new_text)
                            self.vibration_debug_text.see(tk.END)
                        break
        except Exception:
            pass  # 忽略更新错误
    
    def _should_show_in_debug_panel(self, message):
        """判断是否在调试面板中显示该消息（重要信息过滤）"""
        import time
        
        # 如果调试输出被暂停，不显示任何消息
        if getattr(self, 'debug_paused', False):
            return False
        
        # 高优先级信息（总是显示）
        high_priority_keywords = [
            "开始监控", "停止监控", "手动捕获",
            "开始记录", "结束记录", "暂停记录",
            "检测到振动", "状态转换", "完成层",
            "已拍摄", "阈值设置", "保存路径已修改",
            "错误", "失败", "异常", "成功",
            "工艺参数更新", "振动峰值已重置"
        ]
        
        # 检查是否为高优先级信息
        for keyword in high_priority_keywords:
            if keyword in message:
                return True
        
        # 获取当前调试级别
        debug_level = getattr(self, 'debug_level', tk.StringVar(value="重要信息")).get()
        
        # 重要信息模式：只显示高优先级
        if debug_level == "重要信息":
            return False  # 低优先级信息不显示
        
        # 详细信息和全部信息模式：需要检查节流
        low_priority_patterns = {
            "数据读取失败": 30.0,     # 默认30秒
            "振动触发检查": 30.0,     # 默认30秒
            "处理后数据": 60.0,       # 默认60秒
            "综合强度": 60.0,         # 默认60秒
            "振动调试运行正常": 120.0, # 默认120秒
            "状态机运行中": 60.0,     # 默认60秒
            "状态机检查": 30.0,       # 默认30秒
            "等待振动检测": 60.0,     # 默认60秒
        }
        
        # 检查低优先级信息的节流
        now = time.time()
        for pattern, default_interval in low_priority_patterns.items():
            if pattern in message:
                # 使用独立的节流计时器
                if not hasattr(self, '_debug_panel_throttle'):
                    self._debug_panel_throttle = {}
                    
                # 获取当前的节流间隔（可能被级别设置修改过）
                current_interval = self._debug_panel_throttle.get(pattern, default_interval)
                
                last_time = self._debug_panel_throttle.get(f"{pattern}_last", 0)
                if now - last_time < current_interval:
                    return False  # 被节流
                else:
                    self._debug_panel_throttle[f"{pattern}_last"] = now
                    return True
        
        # 对于全部信息模式，显示其他未分类的信息
        if debug_level == "全部信息":
            return True
        
        # 详细信息模式，不显示其他未分类信息
        return False
    
    def _toggle_monitoring(self):
        """切换监控状态（开始监控）"""
        if not self.monitoring:
            # 检查设备状态
            if not self._check_devices():
                messagebox.showerror(
                    "错误",
                    "一个或多个设备未就绪，请检查设备连接"
                )
                return
            
            # 启动监控
            self.monitoring = True
            self.start_button.config(state=tk.DISABLED)  # 禁用开始按钮
            self.stop_button.config(state=tk.NORMAL)     # 启用停止按钮
            self.capture_button.config(state=tk.NORMAL)
            self.start_callback()
            self._log("开始监控")
    
    def _stop_monitoring(self):
        """停止监控"""
        if self.monitoring:
            # 停止监控
            self.monitoring = False
            self.start_button.config(state=tk.NORMAL)     # 启用开始按钮
            self.stop_button.config(state=tk.DISABLED)    # 禁用停止按钮
            self.capture_button.config(state=tk.DISABLED)
            self.stop_callback()
            self._log("停止监控")
    
    def _capture_images(self):
        """捕获图像"""
        if not self.monitoring:
            messagebox.showwarning("警告", "请先开始监控")
            return
        
        self.capture_callback()
        self._log("手动捕获图像")
    
    def _check_devices(self):
        """检查所有设备状态"""
        all_ready = True
        for device_name, device in self.devices.items():
            # 检查设备连接状态
            if hasattr(device, 'isOpen'):
                is_connected = device.isOpen
            elif hasattr(device, 'is_connected'):
                is_connected = device.is_connected
            else:
                is_connected = False
                
            # 振动设备即使未连接也可以工作（调试模式）
            if device_name == 'vibration':
                continue  # 振动设备总是可用的
                
            if not is_connected:
                print(f"设备{device_name}未连接")
                all_ready = False
                
        return all_ready
    
    def _log(self, message):
        """添加日志记录 - 同步输出到界面、终端和日志文件"""
        # 节流判定
        now_ts = time.time()
        suppress = False
        for key, interval in getattr(self, '_log_min_intervals', {}).items():
            if key in message:
                last = self._log_last_times.get(key, 0)
                if now_ts - last < interval:
                    suppress = True
                else:
                    self._log_last_times[key] = now_ts
                break
        if suppress:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 1. 输出到界面调试框
        if hasattr(self, 'vibration_debug_text'):
            self.add_debug_log(message)
        
        # 2. 输出到终端
        print(formatted_message)
        
        # 3. 输出到日志文件（如果日志系统可用）
        try:
            from ..utils.logger import log_info
            log_info(message, "CONTROL")
        except Exception:
            pass  # 日志系统不可用时忽略
    
    def _setup_vibration_logging(self):
        """设置振动设备的日志回调"""
        if 'vibration' in self.devices:
            vibration_device = self.devices['vibration']
            if hasattr(vibration_device, 'add_log_callback'):
                vibration_device.add_log_callback(self._vibration_log_callback)
    
    def _vibration_log_callback(self, message, level="INFO"):
        """振动日志回调函数"""
        # 根据日志级别设置前缀
        level_prefix = {
            "DEBUG": "🔍",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }
        prefix = level_prefix.get(level, "📝")
        
        # 在主线程中更新日志
        import threading
        if threading.current_thread() is threading.main_thread():
            self._log(f"{prefix} {message}")
        else:
            # 如果不在主线程，使用after方法
            self.frame.after(0, lambda: self._log(f"{prefix} {message}"))
    
    def _toggle_camera_debug(self):
        """切换摄像头调试状态"""
        self.debug_enabled = not self.debug_enabled
        
        # 更新所有相机的调试状态
        for device in self.devices.values():
            if hasattr(device, 'debug_enabled'):
                device.debug_enabled = self.debug_enabled
        
        # 更新按钮文本
        self.debug_button.config(
            text="关闭摄像头调试" if self.debug_enabled else "开启摄像头调试"
        )
        
        # 添加日志记录
        self._log(f"{'开启' if self.debug_enabled else '关闭'}摄像头调试模式")
    
    def save_settings(self):
        """保存当前设置"""
        # 如果正在记录，先停止记录
        if self.recording:
            self._stop_recording()
        
        settings = {
            'current_layer': self.current_layer.get(),
            'monitoring': self.monitoring,
            'debug_enabled': self.debug_enabled,
            'motion_threshold': self.motion_threshold,
            'debounce_time': self.debounce_time,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            with open('control_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"保存设置失败: {str(e)}")
    
    def _on_algorithm_change(self, event=None):
        """算法选择改变回调"""
        new_algorithm = self.current_algorithm.get()
        if 'vibration' in self.devices:
            if self.devices['vibration'].switch_algorithm(new_algorithm):
                self._log(f"切换到{new_algorithm}算法")
            else:
                self._log(f"切换算法失败: {new_algorithm}")
    
    def load_settings(self):
        """加载保存的设置"""
        try:
            with open('control_settings.json', 'r') as f:
                settings = json.load(f)
                self.current_layer.set(settings.get('current_layer', '0'))
        except Exception:
            pass  # 文件不存在或格式错误时使用默认值

    def _toggle_recording(self):
        """切换记录状态（开始/暂停/继续）"""
        if not self.recording:
            # 开始记录
            self._start_recording()
        else:
            # 暂停或继续记录
            self._pause_recording()
    
    def _start_recording(self):
        """开始基于振动检测的记录"""
        if self.recording:
            self._log("记录已经在进行中")
            return
        
        # 检查振动传感器是否可用
        if 'vibration' not in self.devices:
            messagebox.showerror("错误", "振动传感器不可用，无法启动基于振动的记录")
            return
            
        # 获取 & 规范化 基本保存路径
        try:
            base_path = self._get_base_save_path()
        except Exception as e:
            messagebox.showerror("错误", f"保存路径无效或创建失败: {e}")
            self._log(f"❌ 保存路径无效: {self.save_path.get()} -> {e}")
            return
        if not base_path:
            messagebox.showerror("错误", "请先选择保存位置")
            self._log("❌ 未选择保存路径，无法开始记录")
            return
        
        # 立即禁用按钮，显示正在启动状态
        self.toggle_recording_button.config(state=tk.DISABLED)
        self.recording_status.config(text="正在启动记录...")
        self._log("🚀 正在初始化记录系统...")
        
        # 异步执行耗时的初始化操作
        self._async_start_recording(base_path)
    
    def _async_start_recording(self, base_path):
        """异步执行记录启动操作，防止UI卡顿"""
        import threading
        import os
        from datetime import datetime
        
        def start_recording_task():
            """后台启动任务"""
            try:
                # 使用当前时间戳创建文件夹
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.recording_dir = os.path.join(base_path, f"vibration_recording_{timestamp}")
                
                # 创建主文件夹
                os.makedirs(self.recording_dir, exist_ok=True)
                
                # 创建新的文件夹结构
                # 1. csv_data文件夹（暂无内容）
                csv_data_dir = os.path.join(self.recording_dir, "csv_data")
                os.makedirs(csv_data_dir, exist_ok=True)
                
                # 2. images文件夹及其子文件夹
                images_dir = os.path.join(self.recording_dir, "images")
                ch_dirs = [
                    os.path.join(images_dir, "CH1"),       # 主摄像头
                    os.path.join(images_dir, "CH2"),       # 副摄像头
                    os.path.join(images_dir, "CH3"),       # 红外热像仪图像
                    os.path.join(images_dir, "CH3_Data"),  # 红外热像仪数据
                    os.path.join(images_dir, "CH3_Field")  # 红外热像仪连续采样
                ]
                
                for ch_dir in ch_dirs:
                    os.makedirs(ch_dir, exist_ok=True)
                
                # 在主线程中完成初始化
                self.frame.after(0, lambda: self._complete_recording_initialization(timestamp))
                
            except Exception as e:
                error_msg = f"创建记录文件夹失败: {str(e)}"
                self.frame.after(0, lambda: self._handle_recording_start_error(error_msg))
        
        # 在后台线程中执行
        thread = threading.Thread(target=start_recording_task, daemon=True)
        thread.start()
    
    def _complete_recording_initialization(self, timestamp):
        """在主线程中完成记录初始化"""
        from datetime import datetime
        
        try:
            # 初始化记录状态
            self.recording = True
            self.recording_paused = False
            self.recording_start_time = datetime.now()
            
            # 初始化振动检测状态
            self.motion_state = "idle"
            self.first_motion_detected = False
            self.second_motion_detected = False
            self.last_trigger_time = 0
            self.first_motion_start_time = 0
            
            # 初始化main_data记录列表
            self.main_data_records = []
            
            # 更新UI - 切换按钮显示为暂停
            self.toggle_recording_button.config(
                text="⏸ 暂停记录",
                bg="#FF9800",  # 橙色
                activebackground="#F57C00",
                state=tk.NORMAL
            )
            self.stop_recording_button.config(state=tk.NORMAL)
            self.recording_status.config(text=f"等待振动检测: 层{self.current_layer.get()}")
            
            # 记录日志
            self._log(f"🎬 开始基于振动的记录到: {self.recording_dir}")
            self._log(f"📋 初始状态: recording={self.recording}, paused={self.recording_paused}")
            self._log(f"🔧 振动参数: 阈值={self.motion_threshold:.3f}, 防抖时间={self.debounce_time}s")
            self._log(f"🎯 状态机初始化: {self.motion_state}")
            self._log(f"🔧 使用的振动设备: {id(self.devices.get('vibration'))} (类型: {type(self.devices.get('vibration')).__name__})")
            
            # 启动振动监测
            self._start_motion_monitoring()
            
            # 异步初始化工艺参数（避免设备通信阻塞）
            self._async_initialize_process_parameters()
            
        except Exception as e:
            self._handle_recording_start_error(f"记录初始化失败: {str(e)}")
    
    def _async_initialize_process_parameters(self):
        """异步初始化工艺参数，避免设备通信阻塞UI"""
        import threading
        
        def init_params_task():
            """后台参数初始化任务"""
            try:
                if self.parent_window_ref and hasattr(self.parent_window_ref, 'get_current_process_params'):
                    try:
                        current_params = self.parent_window_ref.get_current_process_params()
                        
                        # 在主线程中更新参数
                        self.frame.after(0, lambda: self._update_process_parameters(current_params))
                        
                    except Exception as e:
                        self._log(f"获取工艺参数失败: {str(e)}")
                        # 使用默认参数
                        self.frame.after(0, lambda: self._use_default_parameters())
                else:
                    # 使用默认参数
                    self.frame.after(0, lambda: self._use_default_parameters())
                    
            except Exception as e:
                self._log(f"工艺参数初始化异常: {str(e)}")
                self.frame.after(0, lambda: self._use_default_parameters())
        
        # 在后台线程中执行
        thread = threading.Thread(target=init_params_task, daemon=True)
        thread.start()
    
    def _update_process_parameters(self, current_params):
        """在主线程中更新工艺参数"""
        try:
            # 如果参数发生了变化，记录新的参数
            if self.current_parameters != current_params:
                # 如果之前有参数记录，更新其结束层数
                if self.parameter_history:
                    current_layer = int(self.current_layer.get())
                    for param in self.parameter_history[-4:]:  # 更新最后4个参数的end_layer
                        param['end_layer'] = current_layer - 1
                
                # 记录新参数
                self.current_parameters = current_params.copy()
                self.parameters_start_layer = int(self.current_layer.get())
                self._add_parameter_record()
                self._log("✅ 工艺参数初始化完成")
        except Exception as e:
            self._log(f"更新工艺参数失败: {str(e)}")
            self._use_default_parameters()
    
    def _handle_recording_start_error(self, error_msg):
        """处理记录启动错误"""
        messagebox.showerror("错误", error_msg)
        self.recording = False
        self.recording_dir = ""
        self._log(f"❌ {error_msg}")
        
        # 恢复按钮状态
        self.toggle_recording_button.config(
            text="▶ 开始记录",
            bg="#4CAF50",
            activebackground="#45a049",
            state=tk.NORMAL
        )
        self.stop_recording_button.config(state=tk.DISABLED)
        self.recording_status.config(text="记录启动失败")
    
    
    def _start_motion_monitoring(self):
        """启动振动监测循环"""
        if not self.recording or self.recording_paused:
            self._log(f"⚠️ 无法启动振动监测: recording={self.recording}, paused={self.recording_paused}")
            return
            
        self._log(f"🚀 启动振动监测循环 - 100ms间隔")
        # 每100ms检查一次振动状态
        self.motion_monitor_timer_id = self.frame.after(100, self._check_motion_state)
    
    def _check_motion_state(self):
        """检查振动状态并处理状态机逻辑"""
        # 详细检查记录状态
        if not self.recording:
            # 降低频率避免刷屏
            if not hasattr(self, '_last_not_recording_log') or time.time() - self._last_not_recording_log > 10.0:
                self._log(f"🔴 状态机停止 - 未开启记录 (recording={self.recording})")
                self._last_not_recording_log = time.time()
            return
            
        if self.recording_paused:
            if not hasattr(self, '_last_paused_log') or time.time() - self._last_paused_log > 10.0:
                self._log(f"⏸️ 状态机暂停 - 记录已暂停 (recording_paused={self.recording_paused})")
                self._last_paused_log = time.time()
            return
            
        try:
            import time
            current_time = time.time()
            
            # 输出状态机正在运行的信息
            if not hasattr(self, '_last_running_log') or current_time - self._last_running_log > 5.0:
                self._log(f"🤖 状态机运行中: 状态={self.motion_state}, recording={self.recording}")
                self._last_running_log = current_time
            
            # 获取当前振动数据
            vibration_device = self.devices.get('vibration')
            if not vibration_device:
                self._log(f"❌ 振动设备不存在")
                return
                
            # 确保设备阈值与控制面板同步
            if hasattr(vibration_device, 'detection_config'):
                old_device_threshold = vibration_device.detection_config.get("motion_threshold", 0.05)
                if abs(old_device_threshold - self.motion_threshold) > 0.001:  # 如果阈值不同步
                    vibration_device.detection_config["motion_threshold"] = self.motion_threshold
                    self._log(f"🔄 设备阈值已同步: {old_device_threshold:.3f} -> {self.motion_threshold:.3f}")
                    
            # 检查是否有振动触发
            try:
                # 获取振动强度 - 使用与UI显示相同的数据源（振动面板综合强度）
                magnitude = 0.0
                data_source = "none"
                
                # 首先尝试从振动面板获取综合强度
                if hasattr(self, 'vibration_panel_ref') and self.vibration_panel_ref:
                    try:
                        magnitude_text = self.vibration_panel_ref.magnitude_label.cget("text")
                        if ":" in magnitude_text:
                            magnitude = float(magnitude_text.split(":")[1].strip())
                            data_source = "vibration_panel"
                    except (AttributeError, ValueError, IndexError):
                        pass
                
                # 如果振动面板获取失败，使用设备数据作为备用
                if data_source == "none" and vibration_device:
                    try:
                        is_triggered_fallback, magnitude = vibration_device.check_vibration_trigger()
                        data_source = "device_fallback"
                    except Exception:
                        magnitude = 0.0
                
                # 基于振动强度和阈值判断是否触发
                is_triggered = magnitude > self.motion_threshold
                
                # 记录每次检查的结果
                self._log(f"🔍 状态机检查: triggered={is_triggered}, magnitude={magnitude:.3f} (来源:{data_source}), 当前状态={self.motion_state}")
                
                # 只在状态变化或高强度振动时输出详细信息
                if is_triggered or magnitude > 1.0:  # 高强度振动
                    self._log(f"🔍 振动检测返回: triggered={is_triggered}, magnitude={magnitude:.3f} (数据源:{data_source})")
            except Exception as e:
                self._log(f"❌ 振动检测调用失败: {e}")
                return
            
            # 获取设备内部的阈值配置
            device_threshold = getattr(vibration_device, 'detection_config', {}).get('motion_threshold', '未知')
            
            # 每2秒输出一次详细状态（降低频率避免刷屏）
            if not hasattr(self, '_last_debug_time') or current_time - self._last_debug_time > 2.0:
                self._log(f"📊 状态机运行: 强度={magnitude:.3f}, 控制面板阈值={self.motion_threshold:.3f}, 设备阈值={device_threshold}, 触发={is_triggered}, 状态={self.motion_state}")
                self._log(f"📍 记录状态: recording={self.recording}, paused={self.recording_paused}")
                self._last_debug_time = current_time
            
            # 根据模式选择不同的状态机逻辑
            if self.state_machine_mode == "simple":
                self._handle_simple_state_machine(is_triggered, magnitude, current_time)
            else:  # complex mode
                self._handle_complex_state_machine(is_triggered, magnitude, current_time)
                        
        except Exception as e:
            self._log(f"振动检测错误: {str(e)}")
            
        # 继续监测
        if self.recording and not self.recording_paused:
            self.motion_monitor_timer_id = self.frame.after(100, self._check_motion_state)
    
    def _async_capture_images(self, layer_str, phase, timestamp):
        """异步捕获图像，防止UI卡顿"""
        import threading
        
        def capture_task():
            """后台捕获任务"""
            try:
                with self._capture_lock:
                    self._capture_channel_images_sync(layer_str, phase, timestamp)
                    # 记录main_data
                    if not self.test_mode.get():
                        self._record_main_data(layer_str, timestamp, f"powder_{phase}")
                
                # 在主线程中更新UI状态
                layer_num = layer_str.replace('L', '').lstrip('0') or '0'
                if phase == "before":
                    status_text = f"已捕获before: 层{layer_num}"
                    log_msg = f"已拍摄before图像: {layer_str}"
                else:
                    status_text = f"已捕获after: 层{layer_num}"
                    log_msg = f"已拍摄after图像: {layer_str}"
                
                if self.test_mode.get():
                    log_msg = f"测试模式: {log_msg}(未记录main_data)"
                
                self.frame.after(0, lambda: self.recording_status.config(text=status_text))
                self.frame.after(0, lambda: self._log(log_msg))
                
            except Exception as e:
                error_msg = f"捕获{phase}图像失败: {str(e)}"
                self._log(error_msg)
                print(f"❌ {error_msg}")
                # 在主线程中更新错误状态
                self.frame.after(0, lambda: self.recording_status.config(text=f"捕获失败: {phase}"))
        
        # 在后台线程中执行
        thread = threading.Thread(target=capture_task, daemon=True)
        thread.start()
    
    def _capture_before_images(self):
        """拍摄before图像（刮刀运动开始时）
        
        流程:
        1. 先移动舵机到开启位置(2500)，不遮挡红外摄像头
        2. 等待舵机到位
        3. 拍摄所有通道图像
        """
        try:
            from datetime import datetime
            import os
            
            # 第1步: 开启舵机（不遮挡红外）
            self._open_servo()
            
            # 第2步: 拍摄图像
            current_layer_str = f"L{int(self.current_layer.get()):04d}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 添加毫秒精度
            
            self.recording_status.config(text=f"拍摄before: 层{self.current_layer.get()}")
            self._async_capture_images(current_layer_str, "before", timestamp)
            
        except Exception as e:
            self._log(f"拍摄before图像失败: {str(e)}")
    
    def _capture_after_images(self):
        """拍摄after图像（刮刀运动结束时）
        
        流程:
        1. 先拍摄所有通道图像
        2. 然后移动舵机到关闭位置(1500)，遮挡红外摄像头
        """
        try:
            from datetime import datetime
            import os
            
            # 第1步: 拍摄图像
            current_layer_str = f"L{int(self.current_layer.get()):04d}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 添加毫秒精度
            
            self.recording_status.config(text=f"拍摄after: 层{self.current_layer.get()}")
            self._async_capture_images(current_layer_str, "after", timestamp)
            
            # 第2步: 关闭舵机（遮挡红外）
            self._close_servo()
            
        except Exception as e:
            self._log(f"拍摄after图像失败: {str(e)}")

    
    def _create_thermal_placeholder(self, save_path, error_message="Thermal unavailable"):
        """创建热像仪占位图像
        
        Args:
            save_path: 保存路径
            error_message: 错误信息文本
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            import cv2
            import numpy as np
            
            # 创建黑色图像
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # 添加错误信息文本
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            color = (0, 255, 255)  # 黄色文字
            thickness = 2
            
            # 计算文本位置（居中）
            text_size = cv2.getTextSize(error_message, font, font_scale, thickness)[0]
            text_x = (placeholder.shape[1] - text_size[0]) // 2
            text_y = (placeholder.shape[0] + text_size[1]) // 2
            
            cv2.putText(placeholder, error_message, (text_x, text_y), font, font_scale, color, thickness)
            cv2.putText(placeholder, "CH3 - Thermal Channel", (10, 30), font, 0.5, (128, 128, 128), 1)
            
            # 保存图像
            success = cv2.imwrite(save_path, placeholder)
            if success:
                self._log(f"📝 热像仪占位图像已保存: {save_path}")
            return success
            
        except Exception as e:
            self._log(f"❌ 创建占位图像失败: {e}")
            return False

    def _capture_thermal_image(self, save_path):
        """捕获热像仪图像并保存到指定路径
        
        Args:
            save_path: 保存图像的完整路径（包括文件名）
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            # 首先尝试通过设备字典直接访问
            thermal_device = None
            if 'thermal' in self.devices:
                thermal_device = self.devices['thermal']
                self._log("✅ 通过devices字典找到热像仪设备")
            elif self.thermal_panel_ref is not None:
                thermal_device = getattr(self.thermal_panel_ref, 'device', None)
                self._log("✅ 通过thermal_panel引用找到热像仪设备")
            
            if thermal_device is None:
                self._log("❌ 未找到热像仪设备，检查设备字典或热像仪面板引用")
                return False
                
            # 去掉文件扩展名（设备方法会自动添加.png和.npy）
            file_prefix = save_path.rsplit('.', 1)[0] if '.' in save_path else save_path
            
            # 优先使用支持thermal_panel设置的高级保存方法
            success = False
            if hasattr(thermal_device, 'save_frame_with_panel_settings'):
                success = thermal_device.save_frame_with_panel_settings(file_prefix, self.thermal_panel_ref)
                self._log("🎨 使用thermal_panel设置保存热像仪图像")
            elif hasattr(thermal_device, 'save_current_frame'):
                success = thermal_device.save_current_frame(file_prefix)
                self._log("📷 使用设备默认设置保存热像仪图像")
            else:
                self._log("❌ 热像仪设备缺少保存方法")
                return False
            
            if success:
                # 获取温度统计信息用于日志
                if hasattr(thermal_device, 'get_temperature_stats'):
                    stats = thermal_device.get_temperature_stats()
                    if stats:
                        temp_range = f"{stats['min_temp']:.1f}°C ~ {stats['max_temp']:.1f}°C"
                        self._log(f"🌡️ 热像仪图像已保存: {file_prefix}.png (温度范围: {temp_range})")
                        self._log(f"📊 热像仪数据已保存到CH3_Data文件夹: .npy .npz .mat .csv")
                    else:
                        self._log(f"🌡️ 热像仪图像已保存: {file_prefix}.png")
                        self._log(f"📊 热像仪数据已保存到CH3_Data文件夹")
                else:
                    self._log(f"🌡️ 热像仪图像已保存: {file_prefix}.png")
                    self._log(f"📊 热像仪数据已保存到CH3_Data文件夹")
                
                # 如果原路径有特定扩展名，需要重命名文件
                if save_path.endswith('.png') and save_path != f"{file_prefix}.png":
                    import os
                    try:
                        if os.path.exists(f"{file_prefix}.png"):
                            os.rename(f"{file_prefix}.png", save_path)
                            self._log(f"📁 文件已重命名为: {save_path}")
                    except Exception as e:
                        self._log(f"⚠️ 文件重命名失败: {e}")
                
                return True
            else:
                self._log(f"❌ 热像仪设备保存失败: {file_prefix}")
                return False
                
        except Exception as e:
            self._log(f"❌ 捕获热像仪图像时发生异常: {type(e).__name__}: {e}")
            return False

    def _create_servo_control_panel(self):
        """创建舵机控制面板"""
        servo_frame = ttk.LabelFrame(self.frame, text="舵机控制")
        servo_frame.configure(style='Bold.TLabelframe')
        servo_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # 启用/禁用复选框
        self.servo_enabled = tk.BooleanVar(value=self.servo_config["enabled"])
        enable_check = ttk.Checkbutton(
            servo_frame, 
            text="启用舵机控制", 
            variable=self.servo_enabled,
            command=self._on_servo_enable_change
        )
        enable_check.pack(side=tk.LEFT, padx=5)
        
        # 串口选择
        ttk.Label(servo_frame, text="串口:").pack(side=tk.LEFT, padx=(10, 2))
        self.servo_port = tk.StringVar(value=self.servo_config["port"])
        port_entry = ttk.Entry(servo_frame, textvariable=self.servo_port, width=8)
        port_entry.pack(side=tk.LEFT, padx=2)
        
        # 应用按钮
        apply_btn = ttk.Button(
            servo_frame, 
            text="应用设置", 
            command=self._apply_servo_config
        )
        apply_btn.pack(side=tk.LEFT, padx=5)
        
        # 测试按钮
        test_frame = ttk.Frame(servo_frame)
        test_frame.pack(side=tk.RIGHT, padx=5)
        
        open_btn = ttk.Button(
            test_frame, 
            text="开启(2500)", 
            command=lambda: self._move_servo_to(2500),
            bg="#4CAF50",
            fg="white"
        )
        open_btn.pack(side=tk.LEFT, padx=2)
        
        close_btn = ttk.Button(
            test_frame, 
            text="关闭(1500)", 
            command=lambda: self._move_servo_to(1500),
            bg="#f44336",
            fg="white"
        )
        close_btn.pack(side=tk.LEFT, padx=2)
        
        # 状态显示
        self.servo_status = ttk.Label(servo_frame, text="未连接", foreground="gray")
        self.servo_status.pack(side=tk.RIGHT, padx=10)

    def _on_servo_enable_change(self):
        """舵机启用状态改变回调"""
        self.servo_config["enabled"] = self.servo_enabled.get()
        self._log(f"{'启用' if self.servo_enabled.get() else '禁用'}舵机控制")

    def _apply_servo_config(self):
        """应用舵机配置"""
        self.servo_config["port"] = self.servo_port.get()
        self.servo_config["enabled"] = self.servo_enabled.get()
        self._log(f"舵机配置已应用: 串口={self.servo_port.get()}, 启用={self.servo_enabled.get()}")

    def _init_servo_controller(self):
        """初始化舵机控制器"""
        if not SERVO_AVAILABLE or not self.servo_config.get("enabled", False):
            return False
        
        try:
            if self.servo_controller is None:
                self.servo_controller = ServoController(
                    port=self.servo_config["port"],
                    baudrate=self.servo_config["baudrate"]
                )
            if not self.servo_controller.is_connected:
                if self.servo_controller.connect():
                    self.servo_status.config(text="已连接", foreground="green")
                    self._log(f"✅ 舵机控制器已连接: {self.servo_config['port']}")
                    return True
                else:
                    self.servo_status.config(text="连接失败", foreground="red")
                    self._log(f"❌ 舵机控制器连接失败: {self.servo_config['port']}")
                    return False
            return True
        except Exception as e:
            self.servo_status.config(text="错误", foreground="red")
            self._log(f"❌ 舵机控制器初始化失败: {e}")
            return False

    def _move_servo_to(self, position):
        """移动舵机到指定位置
        
        Args:
            position: 目标位置 (1500=关闭/遮挡, 2500=开启/不遮挡)
        """
        if not self.servo_config.get("enabled", False):
            self._log("ℹ️ 舵机控制已禁用")
            return False
        
        if not SERVO_AVAILABLE:
            self._log("❌ 舵机模块不可用")
            return False
        
        # 初始化控制器
        if not self._init_servo_controller():
            return False
        
        try:
            servo_id = self.servo_config.get("servo_id", 1)
            duration = self.servo_config.get("duration", 500)
            wait = self.servo_config.get("wait", True)
            
            position_name = "开启" if position == 2500 else "关闭"
            self._log(f"🎯 舵机移动到{position_name}位置: {position}")
            
            self.servo_controller.move_servo_to_position(
                servo_id=servo_id,
                position=position,
                duration=duration,
                wait=wait
            )
            
            self._log(f"✅ 舵机已移动到{position_name}位置: {position}")
            return True
            
        except Exception as e:
            self._log(f"❌ 舵机移动失败: {e}")
            return False

    def _open_servo(self):
        """开启舵机 (2500位置，不遮挡红外)"""
        return self._move_servo_to(SERVO_POSITION["open"])

    def _close_servo(self):
        """关闭舵机 (1500位置，遮挡红外)"""
        return self._move_servo_to(SERVO_POSITION["closed"])

    def _capture_channel_images_sync(self, layer_str, phase, timestamp):
        """为所有通道拍摄图像"""
        import os
        import cv2
        import numpy as np
        
        # 调试日志：打印当前recording_dir
        self._log(f"🔧 _capture_channel_images called: recording_dir={self.recording_dir}")
        
        # 生成文件名
        filename = f"{layer_str}_{phase}_{timestamp}.png"
        
        # 新的文件夹结构：recording_dir/images/CH1, CH2, CH3
        images_dir = os.path.join(self.recording_dir, "images")
        self._log(f"🗂️ Images base dir: {images_dir}")
        
        # CH1 - 主摄像头
        ch1_dir = os.path.join(images_dir, "CH1")
        ch1_path = os.path.join(ch1_dir, filename)
        os.makedirs(ch1_dir, exist_ok=True)
        self._log(f"📷 CH1 target: {ch1_path}")
        if 'camera' in self.devices and getattr(self.devices['camera'], 'is_connected', False):
            result = self.devices['camera'].save_frame(ch1_dir, f"{layer_str}_{phase}_{timestamp}")
            if result:
                self._log(f"✅ CH1 saved to: {result}")
            else:
                self._log(f"❌ CH1 save failed to: {ch1_dir}")
        else:
            # 保存黑色占位图像为PNG格式
            black_img = np.zeros((480, 640, 3), dtype=np.uint8)
            success = cv2.imwrite(ch1_path, black_img)
            self._log(f"📝 CH1 placeholder: {ch1_path} -> {success}")
            
        # CH2 - 副摄像头
        ch2_dir = os.path.join(images_dir, "CH2")
        ch2_path = os.path.join(ch2_dir, filename)
        os.makedirs(ch2_dir, exist_ok=True)
        self._log(f"📷 CH2 target: {ch2_path}")
        if 'secondary_camera' in self.devices and getattr(self.devices['secondary_camera'], 'is_connected', False):
            result = self.devices['secondary_camera'].save_frame(ch2_dir, f"{layer_str}_{phase}_{timestamp}")
            if result:
                self._log(f"✅ CH2 saved to: {result}")
            else:
                self._log(f"❌ CH2 save failed to: {ch2_dir}")
        else:
            # 保存黑色占位图像为PNG格式
            black_img = np.zeros((480, 640, 3), dtype=np.uint8)
            success = cv2.imwrite(ch2_path, black_img)
            self._log(f"📝 CH2 placeholder: {ch2_path} -> {success}")
            
        # CH3 - 红外热像仪
        ch3_dir = os.path.join(images_dir, "CH3")
        ch3_path = os.path.join(ch3_dir, filename)
        os.makedirs(ch3_dir, exist_ok=True)
        self._log(f"🌡️ CH3 target: {ch3_path}")
        thermal_success = self._capture_thermal_image(ch3_path)
        
        # 如果热像仪捕获失败，则保存带错误信息的占位图像
        if not thermal_success:
            self._log("⚠️ 热像仪捕获失败，CH3使用占位图像")
            # 尝试创建带信息的占位图像，如果失败则使用简单的黑色图像
            if not self._create_thermal_placeholder(ch3_path, "Thermal Unavailable"):
                black_img = np.zeros((480, 640, 3), dtype=np.uint8)
                success = cv2.imwrite(ch3_path, black_img)  # 已经是PNG格式路径
                self._log(f"📝 CH3 black placeholder: {ch3_path} -> {success}")
        else:
            self._log(f"✅ CH3 thermal saved successfully")
    
    def _start_continuous_sampling(self):
        """开始连续采样"""
        # 如果设置为不采样，直接返回
        if self.sampling_interval <= 0:
            self._log("ℹ️ 连续采样已禁用（采样间隔=0）")
            return
        
        if self.continuous_sampling:
            return  # 已经在采样中
            
        self.continuous_sampling = True
        self.current_frame_count = 0
        self.sampling_start_time = time.time()
        
        layer_str = f"L{int(self.current_layer.get()):04d}"
        self._log(f"🎬 开始连续采样 - {layer_str}")
        
        # 立即采样第一帧
        self._capture_continuous_frame()
    
    def _stop_continuous_sampling(self):
        """停止连续采样"""
        if not self.continuous_sampling:
            return
            
        self.continuous_sampling = False
        if self.sampling_timer_id:
            self.frame.after_cancel(self.sampling_timer_id)
            self.sampling_timer_id = None
            
        layer_str = f"L{int(self.current_layer.get()):04d}"
        sampling_duration = time.time() - self.sampling_start_time if self.sampling_start_time else 0
        self._log(f"⏹️ 停止连续采样 - {layer_str}, 共{self.current_frame_count}帧, 耗时{sampling_duration:.1f}秒")
    
    def _apply_sampling_frequency(self):
        """应用选中的采样频率"""
        try:
            freq_text = self.sampling_frequency.get()
            
            # 解析频率设置
            freq_map = {
                "1Hz (1.0s)": 1.0,
                "2Hz (0.5s)": 0.5,
                "5Hz (0.2s)": 0.2,
                "10Hz (0.1s)": 0.1,
                "20Hz (0.05s)": 0.05,
                "不采样": 0.0
            }
            
            if freq_text in freq_map:
                old_interval = self.sampling_interval
                new_interval = freq_map[freq_text]
                self.sampling_interval = new_interval
                
                # 处理不采样的情况
                if new_interval <= 0:
                    self._log("🛑 采样频率已设置为: 不采样")
                    # 如果正在采样，停止它
                    if self.continuous_sampling:
                        self._stop_continuous_sampling()
                else:
                    # 计算频率
                    new_freq = 1.0 / new_interval
                    old_freq = 1.0 / old_interval if old_interval > 0 else 0
                    self._log(f"🎛️ 采样频率已更新: {old_freq:.1f}Hz → {new_freq:.1f}Hz")
                
                # 更新按钮显示应用成功
                self.apply_sampling_button.config(text="✓ 已应用")
                
                # 2秒后恢复按钮文本
                self.frame.after(2000, lambda: self.apply_sampling_button.config(text="应用"))
                
                # 如果正在采样，给出提示
                if self.continuous_sampling:
                    self._log("ℹ️ 新频率将在下次开始采样时生效")
            else:
                self._log(f"❌ 无效的采样频率选择: {freq_text}")
                
        except Exception as e:
            self._log(f"❌ 应用采样频率失败: {str(e)}")
    
    def _capture_continuous_frame(self):
        """采样一帧热像仪数据"""
        if not self.continuous_sampling:
            return
            
        try:
            # 生成帧计数
            self.current_frame_count += 1
            layer_str = f"L{int(self.current_layer.get()):04d}"
            frame_str = f"{self.current_frame_count:04d}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 包含毫秒
            
            # 构建文件路径 - 确保使用正确的recording_dir
            self._log(f"🎬 Continuous sampling: recording_dir={self.recording_dir}")
            images_dir = os.path.join(self.recording_dir, "images")
            ch3_field_dir = os.path.join(images_dir, "CH3_Field")
            os.makedirs(ch3_field_dir, exist_ok=True)
            
            filename = f"{layer_str}_{frame_str}_{timestamp}.png"
            ch3_field_path = os.path.join(ch3_field_dir, filename)
            self._log(f"🌡️ CH3_Field target: {ch3_field_path}")
            
            # 保存热像仪数据
            thermal_success = self._capture_thermal_image(ch3_field_path)
            if not thermal_success:
                # 如果热像仪失败，保存占位图像
                black_img = np.zeros((480, 640, 3), dtype=np.uint8)
                success = cv2.imwrite(ch3_field_path, black_img)
                self._log(f"📝 CH3_Field placeholder: {ch3_field_path} -> {success}")
            else:
                self._log(f"✅ CH3_Field thermal saved: frame #{self.current_frame_count}")
            
            # 调度下一次采样
            if self.continuous_sampling:
                # 计算下次采样的延时（毫秒）
                delay_ms = int(self.sampling_interval * 1000)
                self.sampling_timer_id = self.frame.after(delay_ms, self._capture_continuous_frame)
                
        except Exception as e:
            self._log(f"❌ 连续采样失败: {str(e)}")
    
    def _handle_simple_state_machine(self, is_triggered, magnitude, current_time):
        """处理简单状态机逻辑: idle → motion → idle"""
        try:
            if self.motion_state == "idle":
                # 等待运动开始
                # 使用_log进行节流，每10秒最多输出一次
                self._log(f"[简单模式] idle状态: is_triggered={is_triggered}, magnitude={magnitude:.3f}")
                
                if is_triggered:
                    self.motion_state = "motion"
                    self.last_trigger_time = current_time
                    
                    # 更新UI显示
                    self.motion_state_label.config(text="motion", foreground="orange")
                    
                    # 拍摄before图像
                    if self.test_mode.get():
                        # 在before拍摄前停止上一层的连续采样
                        self._stop_continuous_sampling()
                        print(f"📷 [简单模式] 测试模式: 模拟拍摄before图像 - 层{self.current_layer.get()}")
                        self._log(f"[简单模式] 测试模式: 模拟拍摄before图像 - 层{self.current_layer.get()}")
                    else:
                        # 在before拍摄前停止上一层的连续采样
                        self._stop_continuous_sampling()
                        self._capture_before_images()
                    
                    print(f"🟢 [简单模式] 状态转换: idle -> motion (强度: {magnitude:.3f})")
                    self._log(f"🟢 [简单模式] 检测到刮刀运动: 层{self.current_layer.get()}")
                    self.recording_status.config(text=f"检测到刮刀运动: 层{self.current_layer.get()}")
                else:
                    # 等待振动触发
                    # idle 状态下不需要主动初始化舵机，会在拍摄时自动控制
                    
                    if not hasattr(self, '_last_simple_log') or current_time - self._last_simple_log > 10.0:
                        self._log(f"[简单模式] 等待刮刀运动: 强度={magnitude:.3f}")
                        print(f"⭕ [简单模式] 等待刮刀运动...")
                        self._last_simple_log = current_time
                        
            elif self.motion_state == "motion":
                # 运动中，等待停止
                # 使用_log进行节流，每10秒最多输出一次
                self._log(f"[简单模式] motion状态: is_triggered={is_triggered}, magnitude={magnitude:.3f}")
                
                if is_triggered:
                    # 仍在运动中，更新触发时间
                    self.last_trigger_time = current_time
                    self._log(f"🔄 [简单模式] 运动持续中，强度={magnitude:.3f}")
                else:
                    # 检查是否稳定停止
                    time_since_last = current_time - self.last_trigger_time
                    # 使用_log进行节流，每10秒最多输出一次
                    self._log(f"[简单模式] 运动停止检查: 停止时间={time_since_last:.2f}s, 需要={self.debounce_time}s")
                    self._log(f"⏱️ [简单模式] 等待稳定停止: {time_since_last:.2f}s / {self.debounce_time}s")
                    
                    if time_since_last > self.debounce_time:
                        # 拍摄after图像并完成层循环
                        if self.test_mode.get():
                            print(f"📷 [简单模式] 测试模式: 模拟拍摄after图像 - 层{self.current_layer.get()}")
                            self._log(f"[简单模式] 测试模式: 模拟拍摄after图像 - 层{self.current_layer.get()}")
                        else:
                            self._capture_after_images()
                        
                        # after图像拍摄完成后，启动当前层的连续采样
                        self._start_continuous_sampling()
                        
                        # 更新UI显示为idle状态
                        self.motion_state_label.config(text="idle", foreground="green")
                        
                        print(f"🔵 [简单模式] 状态转换: motion -> idle (停止时间: {time_since_last:.2f}s, 完成层)")
                        self._log(f"🔵 [简单模式] 刮刀运动完成，进入下一层")
                        self._complete_layer_cycle()
                        
        except Exception as e:
            log_error(f"[简单模式] 状态机处理错误: {e}", "STATE_MACHINE")
            self._log(f"❌ [简单模式] 状态机错误: {e}")
    
    def _handle_complex_state_machine(self, is_triggered, magnitude, current_time):
        """处理复杂状态机逻辑: idle → first_motion → between_motions → second_motion → idle"""
        try:
            if self.motion_state == "idle":
                # 等待第一次振动（刮刀开始运动）
                # 使用_log进行节流，每10秒最多输出一次
                self._log(f"[复杂模式] idle状态: is_triggered={is_triggered}, magnitude={magnitude:.3f}")
                
                if is_triggered:
                    self.motion_state = "first_motion"
                    self.first_motion_detected = True
                    self.first_motion_start_time = current_time
                    self.last_trigger_time = current_time
                    
                    # 更新UI显示
                    self.motion_state_label.config(text="first_motion", foreground="orange")
                    
                    # 拍摄before图像
                    if self.test_mode.get():
                        # 在before拍摄前停止上一层的连续采样
                        self._stop_continuous_sampling()
                        print(f"📷 [复杂模式] 测试模式: 模拟拍摄before图像 - 层{self.current_layer.get()}")
                        self._log(f"[复杂模式] 测试模式: 模拟拍摄before图像 - 层{self.current_layer.get()}")
                    else:
                        # 在before拍摄前停止上一层的连续采样
                        self._stop_continuous_sampling()
                        self._capture_before_images()
                    
                    print(f"🟢 [复杂模式] 状态转换: idle -> first_motion (强度: {magnitude:.3f})")
                    self._log(f"🟢 [复杂模式] 检测到第一次运动: 层{self.current_layer.get()}")
                    self.recording_status.config(text=f"检测到第一次运动: 层{self.current_layer.get()}")
                else:
                    # 等待振动触发
                    if not hasattr(self, '_last_complex_log') or current_time - self._last_complex_log > 10.0:
                        self._log(f"[复杂模式] 等待第一次运动: 强度={magnitude:.3f}")
                        print(f"⭕ [复杂模式] 等待第一次运动...")
                        self._last_complex_log = current_time
                        
            elif self.motion_state == "first_motion":
                # 第一次运动中，等待振动停止
                # 使用_log进行节流，每10秒最多输出一次
                self._log(f"[复杂模式] first_motion状态: is_triggered={is_triggered}, magnitude={magnitude:.3f}")
                if is_triggered:
                    self.last_trigger_time = current_time
                else:
                    time_since_last = current_time - self.last_trigger_time
                    if time_since_last > self.debounce_time:
                        self.motion_state = "between_motions"
                        
                        # 更新UI显示
                        self.motion_state_label.config(text="between_motions", foreground="blue")
                        
                        print(f"🟡 [复杂模式] 状态转换: first_motion -> between_motions")
                        self._log(f"第一次运动结束，等待第二次运动")
                        self.recording_status.config(text=f"等待第二次运动: 层{self.current_layer.get()}")
                        
            elif self.motion_state == "between_motions":
                # 在两次运动之间等待第二次振动
                # 使用_log进行节流，每10秒最多输出一次
                self._log(f"[复杂模式] between_motions状态: is_triggered={is_triggered}, magnitude={magnitude:.3f}")
                if is_triggered:
                    self.motion_state = "second_motion"
                    self.second_motion_detected = True
                    self.last_trigger_time = current_time
                    
                    # 更新UI显示
                    self.motion_state_label.config(text="second_motion", foreground="red")
                    
                    print(f"🟠 [复杂模式] 状态转换: between_motions -> second_motion")
                    self._log(f"检测到第二次运动")
                    self.recording_status.config(text=f"检测到第二次运动: 层{self.current_layer.get()}")
                    
                elif (current_time - self.first_motion_start_time) > self.between_motions_timeout:
                    # 超时，直接完成
                    print(f"⚠️ [复杂模式] between_motions超时，直接完成")
                    if self.test_mode.get():
                        self._log(f"[复杂模式] 测试模式: 超时模拟拍摄after图像")
                    else:
                        self._capture_after_images()
                    
                    # after图像拍摄完成后，启动连续采样
                    self._start_continuous_sampling()
                    
                    # 更新UI显示为idle状态
                    self.motion_state_label.config(text="idle", foreground="green")
                    
                    self._complete_layer_cycle()
                    
            elif self.motion_state == "second_motion":
                # 第二次运动中，等待振动停止
                # 使用_log进行节流，每10秒最多输出一次
                self._log(f"[复杂模式] second_motion状态: is_triggered={is_triggered}, magnitude={magnitude:.3f}")
                if is_triggered:
                    self.last_trigger_time = current_time
                else:
                    time_since_last = current_time - self.last_trigger_time
                    if time_since_last > self.second_motion_settle_time:
                        # 拍摄after图像并完成层循环
                        if self.test_mode.get():
                            print(f"📷 [复杂模式] 测试模式: 模拟拍摄after图像")
                            self._log(f"[复杂模式] 测试模式: 模拟拍摄after图像")
                        else:
                            self._capture_after_images()
                        
                        # after图像拍摄完成后，启动当前层的连续采样
                        self._start_continuous_sampling()
                        
                        # 更新UI显示为idle状态
                        self.motion_state_label.config(text="idle", foreground="green")
                        
                        print(f"🔵 [复杂模式] 状态转换: second_motion -> idle (完成层)")
                        self._complete_layer_cycle()
                        
        except Exception as e:
            log_error(f"[复杂模式] 状态机处理错误: {e}", "STATE_MACHINE")
            self._log(f"❌ [复杂模式] 状态机错误: {e}")
    
    def _complete_layer_cycle(self):
        """完成一个层的周期，层数加一并重置状态"""
        try:
            # 层数加一
            current = int(self.current_layer.get())
            new_layer = current + 1
            
            self._log(f"🎯 开始完成层周期: 当前层={current}, 将设置为={new_layer}")
            
            self.current_layer.set(str(new_layer))
            
            # 验证层数确实被设置了
            actual_layer = self.current_layer.get()
            self._log(f"✅ 层数已设置: 期望={new_layer}, 实际={actual_layer}")
            
            # 重置状态机
            old_state = self.motion_state
            self.motion_state = "idle"
            self.first_motion_detected = False
            self.second_motion_detected = False
            self.last_trigger_time = 0
            self.first_motion_start_time = 0
            
            # 更新状态显示
            self.motion_state_label.config(text="idle", foreground="green")
            self.recording_status.config(text=f"等待振动检测: 层{new_layer}")
            
            self._log(f"🎉 完成层 {current}，进入层 {new_layer}，状态 {old_state} → idle")
            print(f"🎉 [层周期完成] 层数: {current} → {new_layer}")
            
        except Exception as e:
            self._log(f"❌ 完成层周期失败: {str(e)}")
            import traceback
            self._log(f"详细错误: {traceback.format_exc()}")
    
    def _on_threshold_change(self, event=None):
        """阈值输入框变化时的回调"""
        try:
            new_threshold = self.threshold_var.get()
            if 0.001 <= new_threshold <= 10.0:  # 扩大范围到10
                self.motion_threshold = new_threshold
                # 同步到振动设备
                self._sync_threshold_to_device(new_threshold)
                self._log(f"振动阈值设置为: {new_threshold:.3f}")
        except tk.TclError:
            pass  # 忽略无效输入
    
    def _on_threshold_scale_change(self, value):
        """阈值滑块变化时的回调"""
        new_threshold = float(value)
        self.motion_threshold = new_threshold
        self.threshold_var.set(new_threshold)
        # 实时更新阈值显示标签
        if hasattr(self, 'threshold_value_label'):
            self.threshold_value_label.config(text=f"{new_threshold:.2f}")
        # 同步到振动设备
        self._sync_threshold_to_device(new_threshold)
        # 不要过于频繁的日志输出
    
    def _set_threshold(self, value):
        """设置阈值为指定值"""
        self.threshold_var.set(value)
        self.motion_threshold = value
        # 实时更新阈值显示标签
        if hasattr(self, 'threshold_value_label'):
            self.threshold_value_label.config(text=f"{value:.2f}")
        # 同步到振动设备
        self._sync_threshold_to_device(value)
        self._log(f"振动阈值设置为: {value:.3f}")
    
    def _on_debounce_change(self, event=None):
        """防抖时间输入框变化时的回调"""
        try:
            new_debounce = self.debounce_var.get()
            if 0.1 <= new_debounce <= 10.0:
                self.debounce_time = new_debounce
                self._log(f"防抖时间设置为: {new_debounce:.1f}s")
        except tk.TclError:
            pass  # 忽略无效输入
    
    def _set_debounce_time(self, value):
        """设置防抖时间为指定值"""
        self.debounce_var.set(value)
        self.debounce_time = value
        self._log(f"防抖时间设置为: {value:.1f}s")
    
    def _on_state_machine_mode_change(self):
        """状态机模式切换回调"""
        try:
            new_mode = self.state_machine_mode_var.get()
            old_mode = self.state_machine_mode
            
            if new_mode != old_mode:
                self.state_machine_mode = new_mode
                
                # 重置状态机状态
                self._reset_motion_state()
                
                # 记录模式切换
                mode_names = {"simple": "简单模式(单向刮刀)", "complex": "复杂模式(双向刮刀)"}
                print(f"🔄 状态机模式切换: {mode_names.get(old_mode, old_mode)} → {mode_names.get(new_mode, new_mode)}")
                self._log(f"状态机模式切换为: {mode_names.get(new_mode, new_mode)}")
                
                # 更新界面显示
                if hasattr(self, 'recording_status'):
                    self.recording_status.config(text=f"模式切换为: {mode_names.get(new_mode, new_mode)}")
                    
        except Exception as e:
            log_error(f"状态机模式切换失败: {e}", "STATE_MACHINE")
            self._log(f"状态机模式切换失败: {e}")
    
    def _reset_motion_state(self):
        """重置运动状态"""
        self.motion_state = "idle"
        self.first_motion_detected = False
        self.second_motion_detected = False
        self.last_trigger_time = 0
        self.first_motion_start_time = 0
        
        self.motion_state_label.config(text="idle", foreground="green")
        if self.recording:
            self.recording_status.config(text=f"等待振动检测: 层{self.current_layer.get()}")
        
        self._log("运动状态已重置")
    
    def _test_threshold_sync(self):
        """测试阈值同步功能"""
        try:
            self._log("=== 阈值同步测试 ===")
            
            if 'vibration' in self.devices:
                device = self.devices['vibration']
                
                # 显示当前状态
                control_threshold = self.motion_threshold
                device_threshold = device.detection_config.get("motion_threshold", "未知") if hasattr(device, 'detection_config') else "无配置"
                
                self._log(f"控制面板阈值: {control_threshold:.3f}")
                self._log(f"设备当前阈值: {device_threshold}")
                
                # 强制同步
                if hasattr(device, 'detection_config'):
                    device.detection_config["motion_threshold"] = control_threshold
                    self._log(f"✅ 已强制同步设备阈值为: {control_threshold:.3f}")
                    
                    # 验证同步结果
                    new_device_threshold = device.detection_config.get("motion_threshold")
                    self._log(f"验证设备阈值: {new_device_threshold:.3f}")
                    
                    # 测试振动检测
                    try:
                        is_triggered, magnitude = device.check_vibration_trigger()
                        self._log(f"测试检测结果: triggered={is_triggered}, magnitude={magnitude:.3f}")
                    except Exception as e:
                        self._log(f"检测测试失败: {e}")
                else:
                    self._log("❌ 设备没有detection_config属性")
            else:
                self._log("❌ 振动设备不存在")
                
            self._log("=== 测试完成 ===")
            
        except Exception as e:
            self._log(f"阈值同步测试失败: {e}")
    
    def _sync_threshold_to_device(self, threshold):
        """将阈值同步到振动设备"""
        try:
            if 'vibration' in self.devices:
                vibration_device = self.devices['vibration']
                if hasattr(vibration_device, 'detection_config'):
                    old_motion_threshold = vibration_device.detection_config.get("motion_threshold", 0.05)
                    old_threshold = getattr(vibration_device, 'threshold', 0.05)
                    
                    # 同步两个阈值属性
                    vibration_device.detection_config["motion_threshold"] = threshold
                    vibration_device.threshold = threshold  # 同步到threshold属性
                    
                    self._log(f"阈值已同步到设备: motion_threshold {old_motion_threshold:.3f} -> {threshold:.3f}, threshold {old_threshold:.3f} -> {threshold:.3f}")
                else:
                    self._log("设备不支持阈值配置")
        except Exception as e:
            self._log(f"同步阈值到设备失败: {e}")
    
    def _manual_trigger(self):
        """手动触发振动检测（用于测试）"""
        if not self.recording:
            self._log("请先开始记录再使用手动触发")
            return
            
        import time
        current_time = time.time()
        
        # 根据状态机模式选择不同的触发逻辑
        if self.state_machine_mode == "simple":
            # 简单模式: idle <-> motion 切换
            if self.motion_state == "idle":
                self.motion_state = "motion"
                self.last_trigger_time = current_time
                # 停止上一层连续采样并拍摄before（测试模式也拍摄但不记录main_data）
                self._stop_continuous_sampling()
                self._capture_before_images()
                self._log(f"手动触发[简单]: idle -> motion")
                self.motion_state_label.config(text="motion", foreground="orange")
                self.recording_status.config(text=f"手动触发-运动中: 层{self.current_layer.get()}")
            elif self.motion_state == "motion":
                self.motion_state = "idle"
                # 拍摄after并启动连续采样
                self._capture_after_images()
                self._start_continuous_sampling()
                self._log(f"手动触发[简单]: motion -> idle")
                self.motion_state_label.config(text="idle", foreground="green")
                self._complete_layer_cycle()
            else:
                self._log(f"简单模式当前状态 {self.motion_state} 不支持手动触发")
        
        else:
            # 复杂模式: 与设备真实流程保持一致，但测试模式也拍摄图像（不记录main_data）
            if self.motion_state == "idle":
                self.motion_state = "first_motion"
                self.first_motion_detected = True
                self.first_motion_start_time = current_time
                self.last_trigger_time = current_time
                self._stop_continuous_sampling()
                self._capture_before_images()
                self._log(f"手动触发[复杂]: 检测到第一次运动")
                self.motion_state_label.config(text="first_motion", foreground="orange")
                self.recording_status.config(text=f"手动触发-第一次运动: 层{self.current_layer.get()}")
            elif self.motion_state == "between_motions":
                self.motion_state = "second_motion"
                self.second_motion_detected = True
                self.last_trigger_time = current_time
                self._log(f"手动触发[复杂]: 检测到第二次运动")
                self.motion_state_label.config(text="second_motion", foreground="red")
                self.recording_status.config(text=f"手动触发-第二次运动: 层{self.current_layer.get()}")
            else:
                self._log(f"复杂模式当前状态 {self.motion_state} 不支持手动触发")
    
    def _update_vibration_display(self):
        """更新振动数据显示"""
        try:
            magnitude = 0.0
            data_source = "none"
            panel_success = False
            
            # 直接从振动面板获取综合强度数据
            if hasattr(self, 'vibration_panel_ref') and self.vibration_panel_ref:
                try:
                    magnitude_text = self.vibration_panel_ref.magnitude_label.cget("text")
                    #print(f"🔍 [DEBUG] 振动面板原始文本: '{magnitude_text}'")
                    
                    # 提取数值部分："综合强度: 0.123" -> "0.123"
                    if ":" in magnitude_text:
                        magnitude = float(magnitude_text.split(":")[1].strip())
                        panel_success = True
                        data_source = "vibration_panel"
                        #print(f"✅ [DEBUG] 从振动面板获取到magnitude: {magnitude}")
                    else:
                        print(f"⚠️ [DEBUG] 振动面板文本格式异常，无冒号")
                except (AttributeError, ValueError, IndexError) as e:
                    #print(f"❌ [DEBUG] 从振动面板获取magnitude失败: {e}")
                    magnitude = 0.0
                    panel_success = False
            else:
                print(f"⚠️ [DEBUG] 振动面板引用不存在")
            
            # 只有在从面板获取失败时才使用设备数据作为备用
            if not panel_success and 'vibration' in self.devices:
                #print(f"🔄 [DEBUG] 振动面板获取失败，尝试从设备获取...")
                vibration_device = self.devices['vibration']
                if hasattr(vibration_device, 'vibration_magnitude'):
                    magnitude = vibration_device.vibration_magnitude
                    data_source = "device.vibration_magnitude"
                    #print(f"📊 [DEBUG] 从设备vibration_magnitude获取: {magnitude}")
                elif hasattr(vibration_device, 'calculate_vibration_magnitude'):
                    magnitude = vibration_device.calculate_vibration_magnitude()
                    data_source = "device.calculate_vibration_magnitude"
                    #print(f"📊 [DEBUG] 从设备calculate_vibration_magnitude获取: {magnitude}")
                elif hasattr(self, 'parent_window_ref') and self.parent_window_ref:
                    magnitude = getattr(self.parent_window_ref, 'vibration_magnitude', 0.0)
                    data_source = "parent_window"
                    #print(f"📊 [DEBUG] 从父窗口获取: {magnitude}")
            elif panel_success:
                #print(f"✅ [DEBUG] 使用振动面板数据，跳过设备fallback")
                pass
            
            # 输出最终结果
            #print(f"📈 [DEBUG] 最终magnitude: {magnitude:.3f} (来源: {data_source})")
            
            # 更新振动值显示
            self.vibration_value_label.config(text=f"{magnitude:.3f}")
            
            # 根据振动强度设置颜色
            if magnitude > self.motion_threshold:
                self.vibration_value_label.config(foreground="red")
            elif magnitude > self.motion_threshold * 0.5:
                self.vibration_value_label.config(foreground="orange")
            else:
                self.vibration_value_label.config(foreground="blue")
            
            # 更新状态显示 - 考虑实时振动强度和状态机状态
            display_state = self.motion_state
            display_color = "green"
            
            # 状态显示逻辑：
            # 1. 如果当前振动强度超过阈值，显示活跃状态
            # 2. 如果振动强度低于阈值，但状态机不是idle，显示状态机状态但用暗色表示等待
            # 3. 如果振动强度低于阈值且状态机是idle，显示idle
            
            if magnitude > self.motion_threshold:
                # 当前有振动，根据状态机状态显示
                if self.motion_state == "idle":
                    display_state = "detecting"  # 检测到振动但还未触发状态机
                    display_color = "orange"
                elif self.motion_state == "motion":
                    display_state = "motion"
                    display_color = "red"
                elif self.motion_state == "first_motion":
                    display_state = "first_motion"
                    display_color = "orange"
                elif self.motion_state == "between_motions":
                    display_state = "between_motions"
                    display_color = "blue"
                elif self.motion_state == "second_motion":
                    display_state = "second_motion"
                    display_color = "red"
                else:
                    display_state = self.motion_state
                    display_color = "orange"
            else:
                # 当前无振动，根据状态机状态显示等待状态
                if self.motion_state == "idle":
                    display_state = "idle"
                    display_color = "green"
                elif self.motion_state == "motion":
                    display_state = "motion_waiting"  # 运动状态但当前无振动
                    display_color = "gray"
                elif self.motion_state == "first_motion":
                    display_state = "first_waiting"   # 第一次运动状态但当前无振动
                    display_color = "gray"
                elif self.motion_state == "between_motions":
                    display_state = "between_motions"
                    display_color = "lightblue"
                elif self.motion_state == "second_motion":
                    display_state = "second_waiting"  # 第二次运动状态但当前无振动
                    display_color = "gray"
                else:
                    display_state = f"{self.motion_state}_waiting"
                    display_color = "gray"
            
            self.motion_state_label.config(
                text=display_state,
                foreground=display_color
            )
            
        except Exception as e:
            # 添加错误日志便于调试
            self._log(f"振动显示更新错误: {str(e)}")
        
        # 每200ms更新一次
        self.frame.after(200, self._update_vibration_display)
    
    def _pause_recording(self):
        """暂停或继续振动检测记录"""
        if not self.recording:
            return
            
        if self.recording_paused:
            # 继续记录
            self.recording_paused = False
            self.toggle_recording_button.config(
                text="⏸ 暂停记录",
                bg="#FF9800",  # 橙色
                activebackground="#F57C00"
            )
            self._log("继续振动检测记录")
            
            # 重新开始振动监测
            self._start_motion_monitoring()
        else:
            # 暂停记录
            self.recording_paused = True
            self.toggle_recording_button.config(
                text="▶ 继续记录",
                bg="#4CAF50",  # 绿色
                activebackground="#45a049"
            )
            self._log("暂停振动检测记录")
            
            # 取消振动监测定时器
            if self.motion_monitor_timer_id:
                self.frame.after_cancel(self.motion_monitor_timer_id)
                self.motion_monitor_timer_id = None
    
    def _stop_recording(self):
        """结束振动检测记录"""
        if not self.recording:
            return
        
        # 停止连续采样
        self._stop_continuous_sampling()
        
        # 取消振动监测定时器
        if self.motion_monitor_timer_id:
            self.frame.after_cancel(self.motion_monitor_timer_id)
            self.motion_monitor_timer_id = None
        
        # 更新状态
        self.recording = False
        self.recording_paused = False
        
        # 重置振动检测状态
        self.motion_state = "idle"
        self.first_motion_detected = False
        self.second_motion_detected = False
        self.last_trigger_time = 0
        self.first_motion_start_time = 0
        
        # 更新UI
        self.toggle_recording_button.config(
            text="▶ 开始记录",
            bg="#4CAF50",  # 绿色
            activebackground="#45a049",
            state=tk.NORMAL
        )
        self.stop_recording_button.config(state=tk.DISABLED)
        self.recording_status.config(text="未记录")
        
        # 保存工艺参数历史和main_data到CSV文件
        if self.recording_dir:
            self._save_process_parameters_csv()
            self._save_main_data_csv()
            self._save_main_data_csv()
            
        # 记录日志
        if self.recording_dir:
            self._log(f"结束振动检测记录，数据保存至: {self.recording_dir}")
            self.recording_dir = ""
    
    def _initialize_process_parameters(self):
        """初始化工艺参数记录"""
        if self.parent_window_ref and hasattr(self.parent_window_ref, 'get_current_process_params'):
            try:
                current_params = self.parent_window_ref.get_current_process_params()
                
                # 如果参数发生了变化，记录新的参数
                if self.current_parameters != current_params:
                    # 如果之前有参数记录，更新其结束层数
                    if self.parameter_history:
                        current_layer = int(self.current_layer.get())
                        for param in self.parameter_history[-4:]:  # 更新最后4个参数的end_layer
                            param['end_layer'] = current_layer - 1
                    
                    # 记录新参数
                    self.current_parameters = current_params.copy()
                    self.parameters_start_layer = int(self.current_layer.get())
                    self._add_parameter_record()
                    
            except Exception as e:
                self._log(f"初始化工艺参数失败: {str(e)}")
                # 使用默认参数
                self._use_default_parameters()
        else:
            # 使用默认参数
            self._use_default_parameters()
    
    def _use_default_parameters(self):
        """使用默认工艺参数"""
        self.current_parameters = DEFAULT_PARAMS.copy()
        self.parameters_start_layer = 0
        self._add_parameter_record()
    
    def _add_parameter_record(self):
        """添加参数记录到历史"""
        if not self.current_parameters:
            return
        
        current_layer = self.parameters_start_layer
        
        # 添加四个基本参数记录
        parameters_info = [
            {
                'parameter': 'layer_thickness',
                'value': self.current_parameters.get('layer_thickness', DEFAULT_PARAMS['layer_thickness']),
                'unit': 'mm',
                'description': '分层厚度',
                'start_layer': current_layer,
                'end_layer': current_layer  # 初始设为当前层，后续会更新
            },
            {
                'parameter': 'fill_spacing',
                'value': self.current_parameters.get('fill_spacing', DEFAULT_PARAMS['fill_spacing']),
                'unit': 'mm',
                'description': '填充间距',
                'start_layer': current_layer,
                'end_layer': current_layer
            },
            {
                'parameter': 'fill_speed',
                'value': self.current_parameters.get('fill_speed', DEFAULT_PARAMS['fill_speed']),
                'unit': 'mm/s',
                'description': '填充速度',
                'start_layer': current_layer,
                'end_layer': current_layer
            },
            {
                'parameter': 'fill_power',
                'value': self.current_parameters.get('fill_power', DEFAULT_PARAMS['fill_power']),
                'unit': 'W',
                'description': '填充功率',
                'start_layer': current_layer,
                'end_layer': current_layer
            }
        ]
        
        self.parameter_history.extend(parameters_info)
        self._log(f"添加工艺参数记录 - 层数: {current_layer}")
    
    def _update_parameter_history_on_layer_change(self):
        """在层数变化时更新参数历史"""
        try:
            current_layer = int(self.current_layer.get())
            
            # 检查是否有参数变化
            if self.parent_window_ref and hasattr(self.parent_window_ref, 'get_current_process_params'):
                new_params = self.parent_window_ref.get_current_process_params()
                
                # 如果参数发生变化
                if self.current_parameters != new_params:
                    # 更新之前参数的结束层数
                    if self.parameter_history:
                        for param in self.parameter_history[-4:]:  # 更新最后4个参数的end_layer
                            param['end_layer'] = current_layer - 1
                    
                    # 记录新参数
                    self.current_parameters = new_params.copy()
                    self.parameters_start_layer = current_layer
                    self._add_parameter_record()
                else:
                    # 参数没有变化，只更新当前参数的结束层数
                    if self.parameter_history:
                        for param in self.parameter_history[-4:]:
                            param['end_layer'] = current_layer
                            
        except Exception as e:
            self._log(f"更新参数历史失败: {str(e)}")
    
    def _save_process_parameters_csv(self):
        """保存工艺参数历史到CSV文件"""
        if not self.recording_dir or not self.parameter_history:
            return
        
        try:
            # 创建csv_data文件夹
            csv_data_dir = os.path.join(self.recording_dir, "csv_data")
            os.makedirs(csv_data_dir, exist_ok=True)
            
            # CSV文件路径
            csv_file = os.path.join(csv_data_dir, "process_parameters.csv")
            
            # 写入CSV文件
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)  # 使用默认的逗号分隔符
                
                # 写入表头
                writer.writerow(['parameter', 'value', 'unit', 'description', 'start_layer', 'end_layer'])
                
                # 写入参数数据
                for param in self.parameter_history:
                    writer.writerow([
                        param['parameter'],
                        param['value'],
                        param['unit'],
                        param['description'],
                        param['start_layer'],
                        param['end_layer']
                    ])
            
            self._log(f"工艺参数历史已保存到: {csv_file}")
            
        except Exception as e:
            self._log(f"保存工艺参数CSV失败: {str(e)}")
            print(f"❌ 保存工艺参数CSV失败: {str(e)}")
    
    def on_parameter_change(self):
        """参数变化通知方法"""
        if self.recording and self.parent_window_ref:
            try:
                # 当参数变化时，立即更新参数历史
                self._update_parameter_history_on_layer_change()
                self._log("检测到工艺参数变化，已更新参数历史记录")
            except Exception as e:
                self._log(f"处理参数变化失败: {str(e)}")
    
    def _record_main_data(self, layer_str, timestamp, trigger_type):
        """记录主数据信息到main_data列表
        
        Args:
            layer_str: 层数字符串，如 "L0000"
            timestamp: 时间戳，如 "20250919_164834_577"
            trigger_type: 触发类型，"powder_before" 或 "powder_after"
        """
        try:
            # 提取层数
            layer_num = int(layer_str[1:])  # 去掉"L"前缀
            
            # 获取当前工艺参数
            current_params = self.parent_window_ref.get_current_process_params() if self.parent_window_ref else DEFAULT_PARAMS
            
            # 生成文件名（不包含扩展名）
            base_filename = f"{layer_str}_{trigger_type.split('_')[1]}_{timestamp}"
            
            # 获取thermal设备的温度范围
            thermal_min, thermal_max = None, None
            if 'thermal' in self.devices and self.devices['thermal']:
                thermal_device = self.devices['thermal']
                if hasattr(thermal_device, 'get_current_temp_range'):
                    thermal_min, thermal_max = thermal_device.get_current_temp_range()
            
            # 创建main_data记录
            record = {
                'layer': layer_num,
                'timestamp': timestamp,
                'trigger_type': trigger_type,
                'image_name_CH1': f"{base_filename}.png",  # 改为PNG格式
                'image_name_CH2': f"{base_filename}.png",  # 改为PNG格式
                'thermal_name_CH3': f"{base_filename}.png",  # 改为PNG格式
                'thermal_data_npz': f"{base_filename}.npz",  # 只保留NPZ格式，去除_raw后缀
                'thermal_temp_min': thermal_min if thermal_min is not None else 0.0,
                'thermal_temp_max': thermal_max if thermal_max is not None else 0.0,
                'layer_thickness': current_params.get('layer_thickness', 0.0),
                'fill_spacing': current_params.get('fill_spacing', 0.0),
                'fill_speed': current_params.get('fill_speed', 0.0),
                'fill_power': current_params.get('fill_power', 0.0)
            }
            
            self.main_data_records.append(record)
            self._log(f"已记录main_data: 层{layer_num} {trigger_type} {timestamp}")
            
        except Exception as e:
            self._log(f"记录main_data失败: {str(e)}")
            print(f"❌ 记录main_data失败: {str(e)}")
    
    def _save_main_data_csv(self):
        """保存主数据记录到CSV文件"""
        if not self.recording_dir or not self.main_data_records:
            return
        
        try:
            # 创建csv_data文件夹
            csv_data_dir = os.path.join(self.recording_dir, "csv_data")
            os.makedirs(csv_data_dir, exist_ok=True)
            
            # CSV文件路径
            csv_file = os.path.join(csv_data_dir, "main_data.csv")
            
            # 写入CSV文件
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 写入表头
                writer.writerow([
                    'layer', 'timestamp', 'trigger_type',
                    'image_name_CH1', 'image_name_CH2', 'thermal_name_CH3',
                    'thermal_data_npz',  # 只保留NPZ列
                    'thermal_temp_min', 'thermal_temp_max',
                    'layer_thickness', 'fill_spacing', 'fill_speed', 'fill_power'
                ])
                
                # 写入数据记录
                for record in self.main_data_records:
                    writer.writerow([
                        record['layer'],
                        record['timestamp'],
                        record['trigger_type'],
                        record['image_name_CH1'],
                        record['image_name_CH2'],
                        record['thermal_name_CH3'],
                        record['thermal_data_npz'],  # 只写入NPZ列
                        record['thermal_temp_min'],
                        record['thermal_temp_max'],
                        record['layer_thickness'],
                        record['fill_spacing'],
                        record['fill_speed'],
                        record['fill_power']
                    ])
            
            self._log(f"主数据记录已保存到: {csv_file}")
            
        except Exception as e:
            self._log(f"保存主数据CSV失败: {str(e)}")
            print(f"❌ 保存主数据CSV失败: {str(e)}")
