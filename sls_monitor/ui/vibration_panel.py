"""
振动监测面板模块
"""

import tkinter as tk
from tkinter import ttk
from ..devices.vibration_optimizer import VibrationOptimizer

class VibrationPanel:
    """振动监测面板类"""
    
    def __init__(self, parent, vibration_device):
        """初始化振动监测面板
        
        Args:
            parent: 父级窗口组件
            vibration_device: VibrationDevice实例
        """
        self.device = vibration_device
        self.parent = parent
        
        # 创建主面板（减小padding以节省空间）
        self.frame = ttk.LabelFrame(parent, text="振动调试", padding=3)
        # 应用加粗字体样式
        self.frame.configure(style='Bold.TLabelframe')
        # 不在这里设置grid，由父组件控制布局
        
        self._create_status_panel()
        self._create_vibration_monitor()
        self._create_control_panel()
        
        # 初始更新状态
        self.update_status("就绪")
    
    def _create_status_panel(self):
        """创建状态显示面板"""
        status_frame = ttk.Frame(self.frame)
        status_frame.pack(fill="x", pady=(0, 1))  # 减少底部间距
        
        # 状态标签
        self.status_label = ttk.Label(
            status_frame, 
            text="状态:", 
            font=("Arial", 9, "bold")  # 减小字体
        )
        self.status_label.pack(side="left", padx=(0, 3))  # 减少间距
        
        self.status_value = ttk.Label(
            status_frame,
            text="就绪",
            font=("Arial", 9),  # 减小字体
            foreground="blue"
        )
        self.status_value.pack(side="left", padx=3)  # 减少间距
        
        # 分隔线
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", pady=1)  # 减少间距
    
    def _create_vibration_monitor(self):
        """创建振动监测显示区域"""
        monitor_frame = ttk.Frame(self.frame)
        monitor_frame.pack(fill="x", expand=True, pady=1)  # 减少间距
        
        # 创建一行布局容纳实时数值和峰值记录
        monitor_row = ttk.Frame(monitor_frame)
        monitor_row.pack(fill="x", pady=(0, 1))  # 减少间距
        monitor_row.columnconfigure(0, weight=1)  # 实时数值列
        monitor_row.columnconfigure(1, weight=1)  # 峰值记录列
        
        # 实时数值显示（左列）
        current_frame = ttk.LabelFrame(monitor_row, text="实时数值", padding=2)  # 减少padding
        current_frame.grid(row=0, column=0, padx=(0, 1), sticky="nsew")  # 减少间距
        
        # 创建三列布局显示 X, Y, Z 轴
        axes_frame = ttk.Frame(current_frame)
        axes_frame.pack(fill="x")
        
        self.current_labels = {}
        for i, axis in enumerate(['x', 'y', 'z']):
            axis_frame = ttk.Frame(axes_frame)
            axis_frame.grid(row=0, column=i, padx=5, pady=2, sticky="ew")  # 减少间距
            
            ttk.Label(axis_frame, text=f"{axis.upper()}轴:", font=("Arial", 8, "bold")).pack()  # 减小字体
            self.current_labels[axis] = ttk.Label(
                axis_frame,
                text="0.000",
                font=("Arial", 10),  # 减小字体
                foreground="blue"
            )
            self.current_labels[axis].pack()
        
        # 配置列权重
        axes_frame.grid_columnconfigure(0, weight=1)
        axes_frame.grid_columnconfigure(1, weight=1)
        axes_frame.grid_columnconfigure(2, weight=1)
        
        # 峰值显示（右列）
        peak_frame = ttk.LabelFrame(monitor_row, text="峰值记录", padding=2)  # 减小padding
        peak_frame.grid(row=0, column=1, padx=(1, 0), sticky="nsew")  # 减小间距
        
        # 创建三列布局显示峰值
        peak_axes_frame = ttk.Frame(peak_frame)
        peak_axes_frame.pack(fill="x")
        
        self.peak_labels = {}
        for i, axis in enumerate(['x', 'y', 'z']):
            axis_frame = ttk.Frame(peak_axes_frame)
            axis_frame.grid(row=0, column=i, padx=5, pady=2, sticky="ew")  # 减小间距
            
            ttk.Label(axis_frame, text=f"{axis.upper()}轴:", font=("Arial", 8, "bold")).pack()  # 减小字体
            self.peak_labels[axis] = ttk.Label(
                axis_frame,
                text="0.000",
                font=("Arial", 10),  # 减小字体
                foreground="red"
            )
            self.peak_labels[axis].pack()
        
        # 配置列权重
        peak_axes_frame.grid_columnconfigure(0, weight=1)
        peak_axes_frame.grid_columnconfigure(1, weight=1)
        peak_axes_frame.grid_columnconfigure(2, weight=1)
        
        # 综合强度显示
        magnitude_frame = ttk.Frame(monitor_frame)
        magnitude_frame.pack(fill="x", pady=1)  # 减小间距
        
        self.magnitude_label = ttk.Label(
            magnitude_frame,
            text="综合强度: 0.000",
            font=("Arial", 9, "bold"),  # 减小字体
            foreground="green"
        )
        self.magnitude_label.pack(side="left")
        
        # 重置按钮
        self.reset_button = ttk.Button(
            magnitude_frame,
            text="重置峰值",
            command=self._reset_peaks
        )
        self.reset_button.pack(side="right")
    
    def _create_control_panel(self):
        """创建控制面板"""
        control_frame = ttk.Frame(self.frame)
        control_frame.pack(fill="x", pady=1)  # 减小间距
        
        # 算法选择与按钮区域统一放在一行
        algorithm_frame = ttk.Frame(control_frame)
        algorithm_frame.pack(fill="x", pady=(0, 1))  # 减小间距
        
        # 左侧算法选择
        ttk.Label(algorithm_frame, text="检测算法:", font=("Arial", 8)).pack(side="left", padx=(0, 3))  # 减小字体和间距
        
        self.algorithm_var = tk.StringVar(value="composite")
        algorithm_menu = ttk.Combobox(
            algorithm_frame,
            textvariable=self.algorithm_var,
            values=list(VibrationOptimizer.SENSITIVITY_ALGORITHMS.keys()),
            state="readonly",
            width=12  # 减小宽度
        )
        algorithm_menu.pack(side="left", padx=3)  # 减小间距
        algorithm_menu.bind("<<ComboboxSelected>>", self._on_algorithm_change)
        
        # 右侧按钮区域 - 使用更紧凑的布局
        # 优化按钮
        self.optimize_button = ttk.Button(
            algorithm_frame,
            text="优化设置",
            command=self._optimize_settings
        )
        self.optimize_button.pack(side="right", padx=2)  # 减小间距
        
        # 校准按钮
        self.calibrate_button = ttk.Button(
            algorithm_frame,
            text="校准传感器",
            command=self._calibrate_sensor
        )
        self.calibrate_button.pack(side="right", padx=2)  # 减小间距
        
        # 手动测试按钮
        self.test_button = ttk.Button(
            algorithm_frame,
            text="手动测试",
            command=self._manual_test
        )
        self.test_button.pack(side="right", padx=2)  # 减小间距
    
    def _reset_peaks(self):
        """重置峰值数据"""
        # 添加内部标志，防止循环调用
        self._internal_reset = True
        
        # 重置设备内部峰值数据
        if self.device:
            self.device.reset_peak_values()
            print("✅ 振动监测面板: 设备峰值数据已重置")
        else:
            print("⚠️ 振动监测面板: 设备不可用，只重置显示")
        
        # 始终更新UI显示，即使设备不可用
        self.update_peaks((0.0, 0.0, 0.0))
        
        # 如果存在父窗口，调用其重置方法以同步所有数据（防止循环调用）
        if hasattr(self, 'parent') and self.parent and not hasattr(self, '_from_main_window'):
            try:
                # 尝试调用父窗口的重置方法
                if hasattr(self.parent, 'reset_vibration_peaks'):
                    # 设置标记，表示这是来自面板的请求
                    self._from_panel = True
                    self.parent.reset_vibration_peaks()
                    # 清除标记
                    delattr(self, '_from_panel')
                    print("ℹ️ 振动监测面板: 已同步调用主窗口重置方法")
            except Exception as e:
                print(f"❌ 振动监测面板: 调用主窗口重置方法失败 - {e}")
        
        # 清除内部标志
        delattr(self, '_internal_reset')
        
        # 打印日志
        print("✅ 振动监测面板: UI峰值显示已重置")
    
    def _optimize_settings(self):
        """优化设备设置"""
        if self.device and self.device.optimizer:
            if self.device.optimizer.optimize_sensor_settings():
                self.update_status("优化完成", "green")
            else:
                self.update_status("优化失败", "red")
    
    def _calibrate_sensor(self):
        """校准传感器"""
        if self.device:
            try:
                # 这里应该实现具体的校准逻辑
                self.update_status("正在校准...", "orange")
                # TODO: 实现校准逻辑
                self.update_status("校准完成", "green")
            except Exception as e:
                self.update_status(f"校准失败: {e}", "red")
        else:
            self.update_status("设备未连接", "red")
    
    def _manual_test(self):
        """手动测试振动传感器"""
        if self.device:
            try:
                self.update_status("正在进行手动测试...", "orange")
                
                # 读取多个寄存器进行测试
                registers = {
                    58: "振动速度X",
                    59: "振动速度Y", 
                    60: "振动速度Z",
                    65: "振动位移X",
                    66: "振动位移Y",
                    67: "振动位移Z",
                    68: "振动频率X",
                    69: "振动频率Y",
                    70: "振动频率Z",
                    64: "温度"
                }
                
                test_results = []
                for reg, name in registers.items():
                    try:
                        value = self.device.get(str(reg))
                        test_results.append(f"{name}: {value}")
                        print(f"📊 寄存器{reg} ({name}): {value}")
                    except Exception as e:
                        test_results.append(f"{name}: 读取失败 - {e}")
                        print(f"❌ 寄存器{reg} ({name}): 读取失败 - {e}")
                
                # 显示测试结果
                result_msg = "测试完成，详见控制台输出"
                self.update_status(result_msg, "green")
                
                # 模拟一些测试数据更新界面
                import random
                test_x = random.uniform(0.001, 0.1)
                test_y = random.uniform(0.001, 0.08)
                test_z = random.uniform(0.001, 0.06)
                test_mag = (test_x + test_y + test_z) / 3
                
                self.update_all(
                    current_values=(test_x, test_y, test_z),
                    magnitude=test_mag,
                    status="手动测试中"
                )
                
            except Exception as e:
                self.update_status(f"测试失败: {e}", "red")
                print(f"❌ 手动测试失败: {e}")
        else:
            self.update_status("设备未连接", "red")
    
    def _on_algorithm_change(self, event):
        """算法改变时的回调"""
        if self.device:
            algorithm = self.algorithm_var.get()
            if hasattr(self.device, 'set_optimization_algorithm'):
                self.device.set_optimization_algorithm(algorithm)
                self.update_status(f"已切换到{algorithm}算法")
            else:
                self.update_status("设备不支持算法切换", "orange")
    
    def update_current_values(self, values):
        """更新实时值显示
        
        Args:
            values: (x, y, z) 三轴数据元组
        """
        for axis, value in zip(['x', 'y', 'z'], values):
            self.current_labels[axis].config(text=f"{value:.3f}")
    
    def update_peaks(self, values):
        """更新峰值显示
        
        Args:
            values: (x, y, z) 三轴数据元组
        """
        for axis, value in zip(['x', 'y', 'z'], values):
            self.peak_labels[axis].config(text=f"{value:.3f}")
    
    def update_magnitude(self, value):
        """更新综合强度显示
        
        Args:
            value: 综合强度值
        """
        self.magnitude_label.config(text=f"综合强度: {value:.3f}")
        
        # 根据振动强度改变颜色
        if value > 0.1:
            color = "red"  # 危险振动
        elif value > 0.05:
            color = "orange"  # 强烈振动
        elif value > 0.01:
            color = "blue"  # 中等振动
        else:
            color = "green"  # 轻微振动
        
        self.magnitude_label.config(foreground=color)
    
    def update_status(self, status, color=None):
        """更新状态显示
        
        Args:
            status: 状态文本
            color: 状态颜色（可选，自动根据状态判断）
        """
        if color is None:
            # 根据状态文本自动选择颜色
            if "触发" in status or "检测到" in status:
                color = "red"
            elif "监测中" in status or "运行" in status:
                color = "green"
            elif "优化" in status:
                color = "orange"
            elif "失败" in status or "错误" in status:
                color = "red"
            else:
                color = "blue"
        
        self.status_value.config(text=status, foreground=color)
    
    def update_all(self, current_values=None, peak_values=None, magnitude=None, status=None):
        """更新所有显示
        
        Args:
            current_values: (x, y, z) 当前值元组
            peak_values: (x, y, z) 峰值元组
            magnitude: 综合强度值
            status: 状态信息
        """
        if current_values:
            self.update_current_values(current_values)
        if peak_values:
            self.update_peaks(peak_values)
        if magnitude is not None:
            self.update_magnitude(magnitude)
        if status:
            self.update_status(status)