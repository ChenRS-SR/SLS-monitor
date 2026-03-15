"""
主窗口模块
实现SLM监控系统的主界面
"""

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import time
from datetime import datetime
from sls_monitor.config.system_config import DEFAULT_PARAMS
from sls_monitor.config.camera_config import IMAGE_CONFIG

# 尝试导入日志系统
try:
    from sls_monitor.utils.logger import log_info, log_error, shutdown_logging
    
    # 导入debug配置
    from sls_monitor.config.debug_config import CONSOLE_OUTPUT, LOG_LEVELS
except ImportError:
    # 如果导入失败，创建占位函数
    def log_info(msg, component="MAIN_WINDOW"):
        print(f"[INFO] [{component}] {msg}")
    def log_error(msg, component="MAIN_WINDOW"):
        print(f"[ERROR] [{component}] {msg}")
    def shutdown_logging():
        pass

# 重新定义图像尺寸以适应较小的窗口高度
import copy
ADJUSTED_IMAGE_CONFIG = copy.deepcopy(IMAGE_CONFIG)
ADJUSTED_IMAGE_CONFIG["display_height"] = 180  # 降低图像显示高度
# 确保热像更新频率配置被正确传递
print(f"[CONFIG] thermal_fps = {ADJUSTED_IMAGE_CONFIG.get('thermal_fps', 'N/A')}")
from sls_monitor.ui.camera_panel import CameraPanel
from sls_monitor.ui.thermal_panel import ThermalPanel
from sls_monitor.ui.control_panel import ControlPanel
from sls_monitor.ui.vibration_panel import VibrationPanel

class MainWindow:
    """主窗口类"""
    
    def __init__(self, devices):
        """
        初始化主窗口
        
        Args:
            devices: 设备控制器字典
        """
        print("� 开始创建主窗口...", flush=True)
        
        try:
            self.root = tk.Tk()
            self.root.title("SLS监控系统")
            
            # 获取屏幕分辨率并智能调整窗口大小
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            print(f"🖥️ 检测到屏幕分辨率: {screen_width}x{screen_height}")
            
            # 计算合适的窗口大小（屏幕的90%，但不超过最佳尺寸）
            optimal_width = min(1400, int(screen_width * 0.9))  # 增加最佳宽度
            optimal_height = min(900, int(screen_height * 0.85))  # 增加最佳高度
            
            # 确保不小于最小尺寸
            window_width = max(1200, optimal_width)  # 提高最小宽度
            window_height = max(800, optimal_height)  # 提高最小高度
            
            # 窗口居中显示
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            self.root.minsize(1200, 800)  # 提高最小尺寸以确保所有内容显示完整
            
            print(f"📐 设置窗口大小: {window_width}x{window_height} (位置: {x}, {y})")
            print("✅ Tkinter根窗口创建成功")
            
            # 设备控制器
            self.devices = devices
            print(f"📦 设备列表: {list(devices.keys())}", flush=True)
            
            # 初始化状态变量
            self.is_shutting_down = False
            
            # 初始化状态变量（必须在_init_ui之前）
            self.monitoring_active = False
            self.current_layer = 0
            self.process_params = DEFAULT_PARAMS.copy()
            
            # 工艺参数变量（必须在_init_ui之前）
            self.layer_thickness = tk.StringVar(value=DEFAULT_PARAMS['layer_thickness'])
            self.fill_spacing = tk.StringVar(value=DEFAULT_PARAMS['fill_spacing'])
            self.fill_speed = tk.StringVar(value=DEFAULT_PARAMS['fill_speed'])
            self.fill_power = tk.StringVar(value=DEFAULT_PARAMS['fill_power'])

            # 振动数据变量
            self.current_vibration_x = 0.0
            self.current_vibration_y = 0.0
            self.current_vibration_z = 0.0
            self.peak_vibration_x = 0.0
            self.peak_vibration_y = 0.0
            self.peak_vibration_z = 0.0
            self.vibration_magnitude = 0.0
            self.is_shutting_down = False
            
            # 振动数据更新的计数器
            self.debug_counter = 0
            self.error_counter = 0
            self.exception_count = 0
            self.disconnect_count = 0
            
            # 添加日志节流机制（与main_window独立）
            self._log_last_times = {}
            self._log_min_intervals = {
                "数据读取失败": 30.0,  # 从10秒增加到30秒，减少干扰
                "振动触发检查": 10.0,  # 每10秒最多输出一次
                "设备没有get方法": 60.0,  # 从30秒增加到60秒
                "设备没有check_vibration_trigger方法": 60.0,  # 从30秒增加到60秒
            }
            
            # 初始化UI组件
            print("🎨 开始初始化UI组件...", flush=True)
            self._init_ui()
            print("✅ UI组件初始化完成", flush=True)
            
        except Exception as e:
            print(f"❌ 主窗口初始化失败: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise
        
        # 自动启动振动监测（振动监测应该一直运行）
        if 'vibration' in self.devices:
            self.monitoring_active = True  # 设置为监控状态
            self._start_vibration_monitoring()
        
        # 自动启动热成像面板更新
        if 'thermal' in self.devices and hasattr(self, 'panels') and 'thermal' in self.panels:
            try:
                thermal_panel = self.panels['thermal']['panel']
                thermal_panel.start_update()
                print("✅ 热成像面板已自动启动", flush=True)
            except Exception as e:
                print(f"⚠️ 启动热成像面板失败: {e}")
        
        print("✅ 主窗口初始化完成")
    
    def _init_global_styles(self):
        """初始化全局样式配置"""
        style = ttk.Style()
        # 为所有面板标题配置加粗字体
        style.configure('Bold.TLabelframe.Label', font=('Arial', 11, 'bold'))
        style.configure('ProcessParams.TLabelframe.Label', font=('Arial', 11, 'bold'))
        style.configure('DeviceStatus.TLabelframe.Label', font=('Arial', 11, 'bold'))
        style.configure('VibMon.TLabelframe.Label', font=('Arial', 11, 'bold'))
        style.configure('SysDebug.TLabelframe.Label', font=('Arial', 11, 'bold'))
    
    def _init_ui(self):
        """初始化UI布局"""
        # 首先初始化全局样式
        self._init_global_styles()
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建左右分栏，自适应宽度
        # 计算左侧面板宽度（根据图像显示尺寸 + 控制区域）
        left_panel_width = ADJUSTED_IMAGE_CONFIG["display_width"] + 140  # 图像宽度 + 控制区域 + 边距
        left_frame = ttk.Frame(self.main_frame, width=left_panel_width, height=900)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_frame.grid_propagate(False)  # 防止缩放
        
        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # 创建面板容器
        self.panels = {}
        
        # 左侧面板（主摄像头）
        if 'camera' in self.devices:
            self.panels['camera'] = {
                'panel': CameraPanel(
                    left_frame,
                    self.devices['camera'],
                    "主摄像头视图",
                    ADJUSTED_IMAGE_CONFIG
                ),
                'grid': {'row': 0, 'column': 0, 'padx': 0, 'pady': 0, 'sticky': "nsew"}
            }
            self.panels['camera']['panel'].frame.grid(
                **self.panels['camera']['grid']
            )
            # 调整面板边距为更紧凑的外观
            self.panels['camera']['panel'].frame.grid(padx=0, pady=0)
            self.panels['camera']['panel'].image_container.pack(padx=0, pady=0)
            # 设置网格权重以确保面板能够正确扩展
            self.panels['camera']['panel'].frame.grid_propagate(False)
        
        # 中间面板（红外热像）
        if 'thermal' in self.devices:
            self.panels['thermal'] = {
                'panel': ThermalPanel(
                    left_frame,
                    self.devices['thermal'],
                    "红外热像视图",
                    ADJUSTED_IMAGE_CONFIG  # 传递与camera_panel相同的图像配置
                ),
                'grid': {'row': 1, 'column': 0, 'padx': 0, 'pady': 0, 'sticky': "nsew"}
            }
            self.panels['thermal']['panel'].frame.grid(
                **self.panels['thermal']['grid']
            )
        else:
            # 创建一个具有固定大小的空面板
            container_width = IMAGE_CONFIG["display_width"] 
            container_height = IMAGE_CONFIG["display_height"] 
            empty_frame = ttk.LabelFrame(left_frame, text="红外热像视图")
            empty_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
            
            # 创建固定大小的内部容器
            inner_frame = ttk.Frame(empty_frame, width=container_width, height=container_height)
            inner_frame.pack(padx=0, pady=0)
            inner_frame.pack_propagate(False)  # 防止缩放
            
            # 添加未连接提示
            ttk.Label(inner_frame, text="红外模块未连接").pack(expand=True)
            
            self.panels['thermal'] = {
                'panel': None,
                'frame': empty_frame,
                'grid': {'row': 1, 'column': 0, 'padx': 0, 'pady': 0, 'sticky': "nsew"}
            }
        
        # 左下面板（副摄像头）
        if 'secondary_camera' in self.devices:
            self.panels['secondary_camera'] = {
                'panel': CameraPanel(
                    left_frame,
                    self.devices['secondary_camera'],
                    "副摄像头视图",
                    ADJUSTED_IMAGE_CONFIG
                ),
                'grid': {'row': 2, 'column': 0, 'padx': 5, 'pady': 5, 'sticky': "nsew"}
            }
            self.panels['secondary_camera']['panel'].frame.grid(
                **self.panels['secondary_camera']['grid']
            )
        
        # 右侧控制面板
        self.control_panel = ControlPanel(
            right_frame,
            self.devices,
            self.on_start_monitoring,
            self.on_stop_monitoring,
            self.on_capture_images,
            self.on_layer_change
        )
        self.control_panel.frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # 创建参数和状态面板的横向容器
        params_status_frame = ttk.Frame(right_frame)
        params_status_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # 配置横向容器的列权重
        params_status_frame.grid_columnconfigure(0, weight=1)  # 工艺参数面板
        params_status_frame.grid_columnconfigure(1, weight=1)  # 设备状态面板
        
        # 创建工艺参数面板
        self._create_process_params_panel(params_status_frame)
        
        # 创建设备状态面板
        self._create_device_status_panel(params_status_frame)
        
        # 创建振动调试面板
        if 'vibration' in self.devices:
            print("🔧 开始创建振动调试面板...")
            try:
                self.vibration_panel = VibrationPanel(
                    right_frame,
                    self.devices['vibration']
                )
                self.vibration_panel.frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
                print("✅ 振动调试面板创建成功")
            except Exception as e:
                print(f"❌ 振动调试面板创建失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("⚠️ 未找到振动设备，跳过振动面板创建")
        
        # 设置组件之间的引用关系（在所有面板创建完成后）
        if hasattr(self, 'vibration_panel'):
            self.control_panel.set_component_references(
                vibration_panel=self.vibration_panel,
                parent_window=self,
                thermal_panel=self.panels.get('thermal', {}).get('panel')
            )
            print("✅ 控制面板组件引用已设置")
        
        # 启动设备状态更新
        self._start_device_status_update()
        
        # 配置主框架网格权重 - 优化布局
        self.main_frame.grid_columnconfigure(0, weight=0, minsize=left_panel_width)  # 左侧固定宽度
        self.main_frame.grid_columnconfigure(1, weight=1)  # 右侧自适应
        self.main_frame.grid_rowconfigure(0, weight=1)  # 主行可伸缩
        
        # 配置右侧框架的行权重
        right_frame.grid_rowconfigure(0, weight=4)  # 控制面板占主要高度
        right_frame.grid_rowconfigure(1, weight=0)  # 参数和状态面板固定高度  
        right_frame.grid_rowconfigure(2, weight=1)  # 振动调试面板较小高度
        right_frame.grid_columnconfigure(0, weight=1)
        
        # 配置左侧框架权重
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=1)  # 主摄像头
        left_frame.grid_rowconfigure(1, weight=1)  # 红外热像
        left_frame.grid_rowconfigure(2, weight=1)  # 副摄像头
        
        # 启动设备状态更新
        self._start_device_status_update()
        
        # 状态栏
        self.status_bar = ttk.Label(self.root, text="就绪", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 创建菜单栏
        self._create_menu()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def _create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="保存当前图像", command=self.save_current_images)
        file_menu.add_command(label="导出数据", command=self.export_data)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.on_closing)
        
        # 设置菜单
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="优化窗口大小", command=self._optimize_window_size)
        settings_menu.add_command(label="重置布局", command=self._reset_layout)
        settings_menu.add_command(label="相机设置", command=self.show_camera_settings)
        settings_menu.add_command(label="红外设置", command=self.show_thermal_settings)
        settings_menu.add_command(label="振动设置", command=self.show_vibration_settings)
        settings_menu.add_command(label="工艺参数", command=self.show_process_params)
        
        # 视图菜单
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="视图", menu=view_menu)
        
        # 创建可见性变量
        self.panel_visibility = {
            'camera': tk.BooleanVar(value=True),
            'thermal': tk.BooleanVar(value=True),
            'secondary_camera': tk.BooleanVar(value=True)
        }
        
        # 添加菜单项
        view_menu.add_checkbutton(
            label="主摄像头",
            variable=self.panel_visibility['camera'],
            command=lambda: self._toggle_panel_visibility('camera')
        )
        
        view_menu.add_checkbutton(
            label="红外热像",
            variable=self.panel_visibility['thermal'],
            command=lambda: self._toggle_panel_visibility('thermal')
        )
        
        view_menu.add_checkbutton(
            label="副摄像头",
            variable=self.panel_visibility['secondary_camera'],
            command=lambda: self._toggle_panel_visibility('secondary_camera')
        )
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
    
    def on_start_monitoring(self):
        """开始监控回调"""
        print("🎥 启动相机面板监控...")
        self.monitoring_active = True
        self.update_status("监控进行中...")
        
        # 只启动相机面板的更新，振动调试已经在自动运行
        for panel_info in self.panels.values():
            if hasattr(panel_info['panel'], 'start_update'):
                print(f"🎥 启动面板更新: {panel_info}")
                panel_info['panel'].start_update()
            if panel_info['panel'] and hasattr(panel_info['panel'], 'start_update'):
                print(f"🎥 启动面板更新 (备用): {panel_info}")
                panel_info['panel'].start_update()
        
        # 振动调试已经在运行，不需要重新启动
        print("ℹ️ 振动调试保持运行状态")
        
        print("✅ 相机监控已启动")
    
    def on_stop_monitoring(self):
        """停止监控回调"""
        print("🛑 on_stop_monitoring 被调用")
        print(f"🔍 调用堆栈:")
        import traceback
        traceback.print_stack()
        
        # 只停止相机监控，不停止振动调试
        self.monitoring_active = False
        self.update_status("相机监控已停止")
        
        # 停止相机面板的更新
        for panel_info in self.panels.values():
            if panel_info['panel'] and hasattr(panel_info['panel'], 'stop_update'):
                panel_info['panel'].stop_update()
        
        print("✅ 相机监控已停止")
        print("ℹ️ 振动调试继续运行")
    
    def _should_log(self, message_key):
        """检查是否应该输出日志（节流机制）"""
        import time
        now = time.time()
        
        for key, interval in self._log_min_intervals.items():
            if key in message_key:
                last_time = self._log_last_times.get(key, 0)
                if now - last_time < interval:
                    return False  # 被节流
                else:
                    self._log_last_times[key] = now
                    return True
        return True  # 默认允许输出
    
    def _start_vibration_monitoring(self):
        """启动振动调试循环"""
        if 'vibration' in self.devices:
            # 检查是否已经在运行
            if hasattr(self, '_vibration_monitoring_started') and self._vibration_monitoring_started:
                print("ℹ️ 振动调试已在运行，跳过重复启动")
                return
            
            print("🔄 启动振动数据更新循环...")
            self._vibration_monitoring_started = True
            self._update_vibration_data()
    
    def _update_vibration_data(self):
        """更新振动数据"""
        # 检查是否正在关闭程序
        if self.is_shutting_down:
            return
        
        # 检查振动面板是否存在
        try:
            if not hasattr(self, 'vibration_panel') or not hasattr(self.vibration_panel, 'frame'):
                if not self.is_shutting_down:
                    self.root.after(100, self._update_vibration_data)
                return
        except:
            if not self.is_shutting_down:
                self.root.after(100, self._update_vibration_data)
            return
        
        try:
            # 如果设备可用，读取振动数据
            if 'vibration' in self.devices and self.devices['vibration']:
                device = self.devices['vibration']
                try:
                    # 设备状态检查（减少debug输出）
                    if CONSOLE_OUTPUT['enable_vibration_debug'] and self.debug_counter < 2:
                        debug_msg = f"🔍 振动设备状态检查"
                        print(debug_msg)
                        if hasattr(self, 'control_panel'):
                            self.control_panel.add_debug_log(debug_msg)
                    
                    # 检查设备是否有get方法
                    if hasattr(device, 'get'):
                        if CONSOLE_OUTPUT['enable_vibration_debug'] and self.debug_counter < 1:
                            debug_msg = f"✅ 设备有get方法"
                            print(debug_msg)
                            if hasattr(self, 'control_panel'):
                                self.control_panel.add_debug_log(debug_msg)
                        
                        # 读取过程（静默模式）
                        if CONSOLE_OUTPUT['enable_vibration_debug'] and self.debug_counter < 1:
                            debug_msg = f"📡 开始读取振动传感器数据..."
                            print(debug_msg)
                            if hasattr(self, 'control_panel'):
                                self.control_panel.add_debug_log(debug_msg)
                            
                        vx = device.get(str(58))  # 振动速度X
                        if CONSOLE_OUTPUT['enable_vibration_debug'] and LOG_LEVELS['VibrationDevice'] == 'DEBUG' and self.debug_counter < 1:
                            debug_msg = f"  X轴: {vx}"
                            print(debug_msg)
                        
                        vy = device.get(str(59))  # 振动速度Y  
                        if CONSOLE_OUTPUT['enable_vibration_debug'] and LOG_LEVELS['VibrationDevice'] == 'DEBUG' and self.debug_counter < 1:
                            debug_msg = f"  Y轴: {vy}"
                            print(debug_msg)
                        
                        vz = device.get(str(60))  # 振动速度Z
                        if CONSOLE_OUTPUT['enable_vibration_debug'] and LOG_LEVELS['VibrationDevice'] == 'DEBUG' and self.debug_counter < 1:
                            debug_msg = f"  Z轴: {vz}"
                            print(debug_msg)
                        
                        # 检查传感器其他寄存器状态（调试模式下）
                        if CONSOLE_OUTPUT['enable_vibration_debug'] and LOG_LEVELS['VibrationDevice'] == 'DEBUG' and self.debug_counter < 1 and vx == 0.0 and vy == 0.0 and vz == 0.0:
                            # 仅检查位移数据用于调试，不影响显示
                            test_vx = device.get(str(65))  # 振动位移X  
                            test_vy = device.get(str(66))  # 振动位移Y
                            test_vz = device.get(str(67))  # 振动位移Z
                            
                            debug_msg = f"📊 检查位移数据: X={test_vx}, Y={test_vy}, Z={test_vz}"
                            print(debug_msg)
                        
                        if vx is not None and vy is not None and vz is not None:
                            # 更新全局变量
                            self.current_vibration_x = abs(vx)
                            self.current_vibration_y = abs(vy)
                            self.current_vibration_z = abs(vz)
                            self.vibration_magnitude = (self.current_vibration_x + self.current_vibration_y + self.current_vibration_z) / 3
                            
                            # 更新峰值 (仅当不在重置保护期内时)
                            if not hasattr(self, '_peak_reset_flag') or not self._peak_reset_flag:
                                # 检查设备是否最近已重置
                                device_reset = False
                                if 'vibration' in self.devices and self.devices['vibration']:
                                    device = self.devices['vibration']
                                    if hasattr(device, 'last_peak_reset_time'):
                                        # 如果设备在最近10秒内重置过，不更新峰值
                                        if (time.time() - device.last_peak_reset_time) < 10.0:
                                            device_reset = True
                                            
                                if not device_reset:    
                                    self.peak_vibration_x = max(self.peak_vibration_x, self.current_vibration_x)
                                    self.peak_vibration_y = max(self.peak_vibration_y, self.current_vibration_y)
                                    self.peak_vibration_z = max(self.peak_vibration_z, self.current_vibration_z)
                                else:
                                    # 设备重置保护期内
                                    if self.debug_counter % 20 == 0:  # 减少日志输出
                                        debug_msg = "🛡️ 设备重置保护期内，暂停峰值更新"
                                        if hasattr(self, 'control_panel'):
                                            self.control_panel.add_debug_log(debug_msg)
                            else:
                                # 界面重置保护期内，保持峰值为0并强制更新显示
                                if self.debug_counter % 20 == 0:  # 减少日志输出
                                    protection_time = "unknown"
                                    if hasattr(self, '_peak_reset_timestamp'):
                                        protection_time = round(time.time() - self._peak_reset_timestamp, 1)
                                    debug_msg = f"🛡️ 峰值重置保护期内，暂停峰值更新 ({protection_time}s)"
                                    if hasattr(self, 'control_panel'):
                                        self.control_panel.add_debug_log(debug_msg)
                                # 在重置保护期内，强制重置峰值为0
                                self.peak_vibration_x = 0.0
                                self.peak_vibration_y = 0.0
                                self.peak_vibration_z = 0.0
                            
                            # 调试信息（每20次打印一次避免刷屏）
                            self.debug_counter += 1
                            
                            # 每500次打印一次处理后的数据（大幅减少输出频率）
                            if self.debug_counter % 500 == 0:
                                debug_msg = f"📊 处理后数据: X={self.current_vibration_x:.4f}, Y={self.current_vibration_y:.4f}, Z={self.current_vibration_z:.4f}"
                                if self.debug_counter % 1000 == 0:  # 控制台输出保持极低频率
                                    print(debug_msg)
                                if hasattr(self, 'control_panel'):
                                    self.control_panel.add_debug_log(debug_msg)
                                    
                                debug_msg = f"🎯 综合强度: {self.vibration_magnitude:.4f}"
                                if self.debug_counter % 1000 == 0:  # 控制台输出保持极低频率
                                    print(debug_msg)
                                if hasattr(self, 'control_panel'):
                                    self.control_panel.add_debug_log(debug_msg)
                            
                            # 每1000次显示一次运行状态（大幅减少状态报告）
                            if self.debug_counter % 1000 == 0:
                                status_msg = f"💓 振动调试运行正常 (更新次数: {self.debug_counter})"
                                print(status_msg)
                                if hasattr(self, 'control_panel'):
                                    self.control_panel.add_debug_log(status_msg)
                                
                        else:
                            debug_msg = f"❌ 数据读取失败: vx={vx}, vy={vy}, vz={vz}"
                            # 使用节流机制控制输出频率
                            if self._should_log("数据读取失败"):
                                print(debug_msg)
                                # 只有在允许输出时才发送到调试面板
                                if hasattr(self, 'control_panel'):
                                    self.control_panel.add_debug_log(debug_msg)
                            # 减少错误信息输出频率
                            self.error_counter += 1
                            
                            # 只在每100次错误时输出一次
                            if self.error_counter % 100 == 0:
                                print(f"⚠️ 振动数据读取失败（已累计{self.error_counter}次）")
                    else:
                        debug_msg = f"❌ 设备没有get方法: 可用方法={[m for m in dir(device) if not m.startswith('_')]}"
                        if self._should_log("设备没有get方法"):
                            print(debug_msg)
                            # 只有在允许输出时才发送到调试面板
                            if hasattr(self, 'control_panel'):
                                self.control_panel.add_debug_log(debug_msg)
                    
                    # 检查振动触发（使用节流机制减少输出频率）
                    if hasattr(device, 'check_vibration_trigger'):
                        triggered, magnitude = device.check_vibration_trigger()
                        debug_msg = f"🚨 振动触发检查: triggered={triggered}, magnitude={magnitude}"
                        # 只在触发时或节流允许时输出
                        if triggered or self._should_log("振动触发检查"):
                            print(debug_msg)
                            # 只有在允许输出时才发送到调试面板
                            if hasattr(self, 'control_panel'):
                                self.control_panel.add_debug_log(debug_msg)
                    else:
                        debug_msg = f"⚠️ 设备没有check_vibration_trigger方法"
                        if self._should_log("设备没有check_vibration_trigger方法"):
                            print(debug_msg)
                            # 只有在允许输出时才发送到调试面板
                            if hasattr(self, 'control_panel'):
                                self.control_panel.add_debug_log(debug_msg)
                    
                except Exception as e:
                    # 减少异常输出频率
                    self.exception_count += 1
                    
                    # 只在每50次异常时输出一次
                    if self.exception_count % 50 == 0:
                        print(f"❌ 振动数据异常（已累计{self.exception_count}次）: {e}")
            else:
                # 减少设备未连接的输出频率
                self.disconnect_count += 1
                
                # 只在每200次时输出一次
                if self.disconnect_count % 200 == 0:
                    print(f"⚠️ 振动传感器设备未连接（已累计{self.disconnect_count}次）")
            
            # 更新振动面板显示
            if hasattr(self, 'vibration_panel'):
                # 振动调试状态独立于相机监控状态
                vibration_status = "振动调试中" if hasattr(self, '_vibration_monitoring_started') and self._vibration_monitoring_started else "已停止"
                self.vibration_panel.update_all(
                    current_values=(self.current_vibration_x, self.current_vibration_y, self.current_vibration_z),
                    peak_values=(self.peak_vibration_x, self.peak_vibration_y, self.peak_vibration_z),
                    magnitude=self.vibration_magnitude,
                    status=vibration_status
                )
            
        except Exception as e:
            print(f"❌ 振动显示更新错误: {e}")
        
        # 每200毫秒更新一次振动显示，减少CPU占用
        if not self.is_shutting_down:
            self.root.after(200, self._update_vibration_data)
    
    def on_capture_images(self):
        """捕获图像回调"""
        print("[DEBUG] on_capture_images 被调用")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 获取保存路径（优先用control_panel的save_path）
        save_path = None
        if hasattr(self, 'control_panel') and hasattr(self.control_panel, 'save_path'):
            save_path = self.control_panel.save_path.get()
            print(f"[DEBUG] 从控制面板获取保存路径: {save_path}")
        
        if not save_path:
            save_path = r"D:\College\Python_project\4Project\SLS\sls_monitor\output"
            print(f"[DEBUG] 使用默认保存路径: {save_path}")
        
        # 确保保存目录存在
        import os
        if not os.path.exists(save_path):
            print(f"[DEBUG] 创建保存目录: {save_path}")
            os.makedirs(save_path, exist_ok=True)
        
        # 捕获所有相机的图像
        saved_count = 0
        for name, panel_info in self.panels.items():
            print(f"[DEBUG] 处理面板: {name}")
            
            # 检查面板是否可用
            panel = panel_info.get('panel')
            if not panel:
                print(f"[DEBUG] {name}面板对象不存在")
                continue
            
            # 检查capture_image方法
            if not hasattr(panel, 'capture_image'):
                print(f"[DEBUG] {name}面板没有capture_image方法")
                continue
                
            # 尝试保存图像
            try:
                print(f"[DEBUG] 调用{name}面板的capture_image方法")
                filename_prefix = f"L{self.current_layer:04d}_{timestamp}"
                success = panel.capture_image(filename_prefix, save_path)
                if success:
                    print(f"[DEBUG] 成功保存{name}图像")
                    saved_count += 1
                else:
                    print(f"[DEBUG] 保存{name}图像失败: capture_image返回False")
            except Exception as e:
                print(f"[DEBUG] 保存{name}图像时发生异常: {str(e)}")
                import traceback
                traceback.print_exc()
        
        status_message = f"已保存{saved_count}个图像到: {save_path} ({timestamp})"
        print(f"[DEBUG] {status_message}")
        self.update_status(status_message)
        
    def _toggle_panel_visibility(self, panel_name):
        """
        切换面板可见性
        
        Args:
            panel_name: 面板名称
        """
        if panel_name not in self.panels:
            return
            
        panel_info = self.panels[panel_name]
        visible = self.panel_visibility[panel_name].get()
        
        if visible:
            # 显示面板
            if panel_info['panel']:
                panel_info['panel'].frame.grid(**panel_info['grid'])
            elif 'frame' in panel_info:
                panel_info['frame'].grid(**panel_info['grid'])
        else:
            # 隐藏面板
            if panel_info['panel']:
                panel_info['panel'].frame.grid_remove()
            elif 'frame' in panel_info:
                panel_info['frame'].grid_remove()
    
    def on_layer_change(self, layer_num):
        """层数变化回调"""
        self.current_layer = layer_num
        self.update_status(f"当前层数: {layer_num}")
        print(f"ℹ️ 当前层数: {layer_num}")
    
    def update_status(self, message):
        """更新状态栏消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_bar.config(text=f"[{timestamp}] {message}")
    
    def _create_process_params_panel(self, parent):
        """创建工艺参数面板"""
        self.process_params_panel = ttk.LabelFrame(parent, text="工艺参数", padding=5)  # 减小padding
        # 应用加粗字体样式
        self.process_params_panel.configure(style='ProcessParams.TLabelframe')
        self.process_params_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 2), pady=0)
        
        # 创建参数输入框架
        params_frame = ttk.Frame(self.process_params_panel)
        params_frame.pack(fill="x", expand=True)
        
        # 第一行：分层厚度、填充间距和更新按钮
        row1_frame = ttk.Frame(params_frame)
        row1_frame.pack(fill="x", pady=(0, 5))
        
        # 分层厚度
        ttk.Label(row1_frame, text="分层厚度:", font=("Arial", 10)).pack(side="left", padx=(0, 5))
        thickness_entry = ttk.Entry(row1_frame, textvariable=self.layer_thickness, width=8)
        thickness_entry.pack(side="left", padx=(0, 5))
        ttk.Label(row1_frame, text="mm", font=("Arial", 10)).pack(side="left", padx=(0, 15))
        
        # 填充间距
        ttk.Label(row1_frame, text="填充间距:", font=("Arial", 10)).pack(side="left", padx=(0, 5))
        spacing_entry = ttk.Entry(row1_frame, textvariable=self.fill_spacing, width=8)
        spacing_entry.pack(side="left", padx=(0, 5))
        ttk.Label(row1_frame, text="mm", font=("Arial", 10)).pack(side="left", padx=(0, 15))
        
        # 更新按钮放在第一行右边
        update_btn = ttk.Button(
            row1_frame,
            text="更新参数",
            command=self._update_process_params,
            style="Accent.TButton"
        )
        update_btn.pack(side="right", padx=(5, 0))
        
        # 第二行：填充速度、填充功率
        row2_frame = ttk.Frame(params_frame)
        row2_frame.pack(fill="x", pady=(0, 5))
        
        # 填充速度
        ttk.Label(row2_frame, text="填充速度:", font=("Arial", 10)).pack(side="left", padx=(0, 5))
        speed_entry = ttk.Entry(row2_frame, textvariable=self.fill_speed, width=8)
        speed_entry.pack(side="left", padx=(0, 5))
        ttk.Label(row2_frame, text="mm/s", font=("Arial", 10)).pack(side="left", padx=(0, 15))
        
        # 填充功率
        ttk.Label(row2_frame, text="填充功率:", font=("Arial", 10)).pack(side="left", padx=(0, 5))
        power_entry = ttk.Entry(row2_frame, textvariable=self.fill_power, width=8)
        power_entry.pack(side="left", padx=(0, 5))
        ttk.Label(row2_frame, text="W", font=("Arial", 10)).pack(side="left", padx=(0, 15))
        
        # 第三行：参数状态显示
        row3_frame = ttk.Frame(params_frame)
        row3_frame.pack(fill="x", pady=(0, 10))
        
        # 参数状态显示居中
        self.params_status = ttk.Label(
            row3_frame,
            text="参数已就绪",
            font=("Arial", 9),
            foreground="green"
        )
        self.params_status.pack(pady=(5, 0))
    
    def _create_device_status_panel(self, parent):
        """创建设备状态面板 - 图标化紧凑布局"""
        self.device_status_panel = ttk.LabelFrame(parent, text="设备状态", padding=5)
        # 应用加粗字体样式
        self.device_status_panel.configure(style='DeviceStatus.TLabelframe')
        self.device_status_panel.grid(row=0, column=1, sticky="nsew", padx=(2, 0), pady=0)
        
        # 创建设备状态指示器字典
        self.status_indicators = {}
        
        # 设备图标映射
        self.device_icons = {
            'camera': '📷',
            'secondary_camera': '📹',
            'thermal': '🌡️',
            'vibration': '📳'
        }
        
        # 设备显示名称映射
        self.device_display_names = {
            'camera': 'Camera',
            'secondary_camera': 'Secondary',
            'thermal': 'Thermal',
            'vibration': 'Vibration'
        }
        
        # 创建2x2网格布局
        self.device_status_panel.grid_columnconfigure(0, weight=1)
        self.device_status_panel.grid_columnconfigure(1, weight=1)
        
        row = 0
        col = 0
        for device_name in self.devices.keys():
            indicator = self._create_compact_status_indicator(
                self.device_status_panel,
                device_name
            )
            self.status_indicators[device_name] = indicator
            indicator['frame'].grid(row=row, column=col, sticky="w", padx=5, pady=2)
            
            col += 1
            if col > 1:
                col = 0
                row += 1
    
    def _create_compact_status_indicator(self, parent, device_name):
        """创建紧凑的设备状态指示器"""
        frame = ttk.Frame(parent)
        
        icon = self.device_icons.get(device_name, '❓')
        display_name = self.device_display_names.get(device_name, device_name.replace('_', ' ').title())
        
        # 图标标签
        icon_label = ttk.Label(frame, text=icon, font=('Arial', 12))
        icon_label.pack(side=tk.LEFT, padx=(0, 3))
        
        # 设备名称标签
        name_label = ttk.Label(frame, text=display_name, font=('Arial', 9))
        name_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # 状态圆点标签
        status_label = ttk.Label(frame, text='⚪', font=('Arial', 10))
        status_label.pack(side=tk.LEFT)
        
        return {
            'frame': frame,
            'icon_label': icon_label,
            'name_label': name_label,
            'status_label': status_label
        }
    
    def _start_device_status_update(self):
        """启动设备状态更新循环"""
        self._update_device_status()
    
    def _update_device_status(self):
        """更新设备状态显示 - 图标化紧凑布局"""
        if hasattr(self, 'status_indicators'):
            for device_name, device in self.devices.items():
                if device_name in self.status_indicators:
                    indicator = self.status_indicators[device_name]
                    status_label = indicator['status_label']
                    
                    # 检查设备连接状态
                    try:
                        if hasattr(device, 'isOpen'):
                            is_connected = device.isOpen
                        elif hasattr(device, 'is_connected'):
                            is_connected = device.is_connected
                        elif hasattr(device, 'connected'):
                            # Thermal设备使用connected属性
                            is_connected = device.connected
                        else:
                            is_connected = False
                        
                        # 确定状态类型和对应的颜色圆点
                        status_type = 'disconnected'  # 默认未连接
                        
                        if is_connected:
                            # 检查是否为仿真/调试模式
                            is_simulation = False
                            if device_name == 'thermal' and hasattr(device, 'simulation_mode') and device.simulation_mode:
                                is_simulation = True
                            elif device_name == 'vibration' and hasattr(device, 'debug_mode') and device.debug_mode:
                                is_simulation = True
                            
                            if is_simulation:
                                status_type = 'simulation'
                            else:
                                status_type = 'connected'
                        else:
                            # 振动设备即使未连接也可以使用调试模式
                            if device_name == 'vibration':
                                status_type = 'simulation'
                            # thermal设备如果处于仿真模式
                            elif device_name == 'thermal' and hasattr(device, 'simulation_mode') and device.simulation_mode:
                                status_type = 'simulation'
                            else:
                                status_type = 'disconnected'
                        
                        # 根据状态类型设置颜色圆点
                        status_dots = {
                            'connected': '🟢',    # 已连接/正常 - 绿色
                            'simulation': '🟡',   # 仿真模式/调试模式 - 橙色
                            'disconnected': '⚪',  # 未连接 - 灰色
                            'error': '🔴'         # 错误 - 红色
                        }
                        
                        status_dot = status_dots.get(status_type, '⚪')
                        status_label.config(text=status_dot)
                        
                    except Exception as e:
                        print(f"设备{device_name}状态检查失败: {str(e)}")
                        status_label.config(text='🔴')  # 错误状态
        
        # 每2秒更新一次设备状态，减少频繁查询
        if not self.is_shutting_down:
            self.root.after(2000, self._update_device_status)
    
    def _update_process_params(self):
        """更新工艺参数"""
        try:
            # 获取参数值并验证
            thickness = float(self.layer_thickness.get())
            spacing = float(self.fill_spacing.get())
            speed = float(self.fill_speed.get())
            power = float(self.fill_power.get())
            
            # 参数范围验证
            if thickness <= 0 or thickness > 1.0:
                raise ValueError("分层厚度必须在0-1.0mm范围内")
            if spacing <= 0 or spacing > 1.0:
                raise ValueError("填充间距必须在0-1.0mm范围内")
            if speed <= 0 or speed > 10000:
                raise ValueError("填充速度必须在0-10000mm/s范围内")
            if power <= 0 or power > 100:
                raise ValueError("填充功率必须在0-100W范围内")
            
            # 更新参数到存储变量
            self.process_params.update({
                'layer_thickness': thickness,
                'fill_spacing': spacing,
                'fill_speed': speed,
                'fill_power': power
            })
            
            # 更新状态显示（简洁版本）
            self.params_status.config(
                text=f"已更新 {thickness}/{spacing}mm {speed}mm/s {power}W",
                foreground="green"
            )
            
            # 更新主状态栏
            self.update_status(f"工艺参数已更新: 厚度{thickness}mm, 间距{spacing}mm, 速度{speed}mm/s, 功率{power}W")
            
            # 打印到控制台
            print(f"✅ 工艺参数更新:")
            print(f"   分层厚度: {thickness} mm")
            print(f"   填充间距: {spacing} mm")
            print(f"   填充速度: {speed} mm/s")
            print(f"   填充功率: {power} W")
            
            # 如果有控制面板，也添加到调试日志并通知参数变化
            if hasattr(self, 'control_panel'):
                self.control_panel.add_debug_log(
                    f"工艺参数更新: 厚度{thickness}mm, 间距{spacing}mm, 速度{speed}mm/s, 功率{power}W"
                )
                # 通知控制面板参数发生了变化
                if hasattr(self.control_panel, 'on_parameter_change'):
                    self.control_panel.on_parameter_change()
            
        except ValueError as e:
            # 参数验证失败
            error_msg = f"参数错误: {str(e)}"
            self.params_status.config(text=error_msg, foreground="red")
            self.update_status(error_msg)
            print(f"❌ {error_msg}")
            
            # 弹出错误提示
            import tkinter.messagebox as msgbox
            msgbox.showerror("参数错误", str(e))
            
        except Exception as e:
            # 其他错误
            error_msg = f"更新失败: {str(e)}"
            self.params_status.config(text=error_msg, foreground="red")
            self.update_status(error_msg)
            print(f"❌ 工艺参数更新失败: {e}")
    
    def get_current_process_params(self):
        """获取当前工艺参数"""
        return self.process_params.copy()

    
    def reset_vibration_peaks(self):
        """重置振动峰值"""
        # 创建唯一的重置标识符
        reset_id = f"reset_{int(time.time())}"
        
        # 检查是否是来自振动面板的调用，防止循环调用
        if hasattr(self, 'vibration_panel') and hasattr(self.vibration_panel, '_from_panel'):
            print(f"ℹ️ 主窗口: 检测到来自面板的重置请求，避免重复处理 ({reset_id})")
            return
            
        # 创建重置标志，防止数据更新循环立即更新峰值
        self._peak_reset_flag = True
        self._peak_reset_timestamp = time.time()
        
        # 记录重置时间
        self._last_peak_reset_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 重置本地峰值变量
        self.peak_vibration_x = 0.0
        self.peak_vibration_y = 0.0
        self.peak_vibration_z = 0.0
        
        # 重置设备内部的峰值
        if 'vibration' in self.devices and self.devices['vibration']:
            device = self.devices['vibration']
            if hasattr(device, 'reset_peak_values'):
                device.reset_peak_values()
                print(f"✅ 主窗口: 设备峰值数据已重置 ({reset_id})")
                
        # 强制更新振动面板的显示
        if hasattr(self, 'vibration_panel'):
            # 设置标记防止循环调用
            self.vibration_panel._from_main_window = True
            # 更新面板显示
            self.vibration_panel.update_peaks((0.0, 0.0, 0.0))
            # 移除标记
            delattr(self.vibration_panel, '_from_main_window')
            print(f"✅ 主窗口: 振动面板显示已更新 ({reset_id})")
            
        # 添加更详细的调试日志
        print(f"✅ 振动峰值已重置 - 峰值数据已清零 ({reset_id})")
        if hasattr(self, 'control_panel'):
            self.control_panel.add_debug_log(f"振动峰值已重置 - 峰值数据已清零 ({self._last_peak_reset_time})")
            
        # 维持重置保护期10秒，延长保护期确保界面有足够时间显示0值
        self.root.after(10000, self._clear_peak_reset_flag)
        
    def _clear_peak_reset_flag(self):
        """清除峰值重置标志"""
        if hasattr(self, '_peak_reset_flag'):
            # 计算保护期的实际时间
            duration = 0
            if hasattr(self, '_peak_reset_timestamp'):
                duration = round(time.time() - self._peak_reset_timestamp, 1)
                
            # 清除标志
            self._peak_reset_flag = False
            
            # 记录当前时间
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            
            # 打印日志信息
            print(f"ℹ️ 主窗口: 峰值重置保护期结束 (duration={duration}s)")
            if hasattr(self, 'control_panel'):
                self.control_panel.add_debug_log(f"峰值重置保护期结束 ({current_time}) - 恢复峰值记录")
    
    def save_current_images(self):
        """保存所有相机的当前图像到控制面板指定路径"""
        print("[DEBUG] save_current_images 被调用")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 获取保存路径（优先用control_panel的save_path）
        save_path = None
        if hasattr(self, 'control_panel') and hasattr(self.control_panel, 'save_path'):
            save_path = self.control_panel.save_path.get()
            print(f"[DEBUG] 从控制面板获取保存路径: {save_path}")
        
        if not save_path:
            save_path = r"D:\College\Python_project\4Project\SLS\sls_monitor\output"
            print(f"[DEBUG] 使用默认保存路径: {save_path}")
        
        # 确保保存目录存在
        import os
        if not os.path.exists(save_path):
            print(f"[DEBUG] 创建保存目录: {save_path}")
            os.makedirs(save_path, exist_ok=True)
        
        # 保存所有相机的图像
        saved_count = 0
        for name, panel_info in self.panels.items():
            print(f"[DEBUG] 处理面板: {name}")
            
            # 详细检查面板可用性
            panel = panel_info.get('panel')
            if not panel:
                print(f"[DEBUG] {name}面板对象不存在")
                continue
                
            # 检查device属性
            if not hasattr(panel, 'device'):
                print(f"[DEBUG] {name}面板没有device属性")
                continue
            
            device = panel.device
            if device is None:
                print(f"[DEBUG] {name}面板的device属性为None")
                continue
                
            # 检查save_frame方法
            if not hasattr(device, 'save_frame'):
                print(f"[DEBUG] {name}面板的device没有save_frame方法")
                continue
                
            # 尝试保存图像
            try:
                print(f"[DEBUG] 调用{name}的save_frame方法")
                saved_path = device.save_frame(save_path, prefix=name)
                if saved_path:
                    print(f"[DEBUG] 成功保存{name}图像到: {saved_path}")
                    saved_count += 1
                else:
                    print(f"[DEBUG] 保存{name}图像失败: save_frame返回None")
            except Exception as e:
                print(f"[DEBUG] 保存{name}图像时发生异常: {str(e)}")
                import traceback
                traceback.print_exc()
        
        status_message = f"已保存{saved_count}个图像到: {save_path} ({timestamp})"
        print(f"[DEBUG] {status_message}")
        self.update_status(status_message)
    
    def export_data(self):
        """导出数据"""
        # TODO: 实现数据导出功能
        self.update_status("数据导出功能开发中...")
    
    def show_camera_settings(self):
        """显示相机设置对话框"""
        # TODO: 实现相机设置对话框
        self.update_status("相机设置功能开发中...")
    
    def show_thermal_settings(self):
        """显示红外设置对话框"""
        # TODO: 实现红外设置对话框
        self.update_status("红外设置功能开发中...")
    
    def show_vibration_settings(self):
        """显示振动设置对话框"""
        # TODO: 实现振动设置对话框
        self.update_status("振动设置功能开发中...")
    
    def show_process_params(self):
        """显示工艺参数对话框"""
        # TODO: 实现工艺参数对话框
        self.update_status("工艺参数设置功能开发中...")
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
        SLM监控系统使用说明
        
        1. 开始监控：点击"开始"按钮
        2. 停止监控：点击"停止"按钮
        3. 手动捕获：点击"捕获"按钮
        4. 层数设置：使用控制面板的输入框
        
        详细说明请参考使用手册。
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("使用说明")
        help_window.geometry("400x300")
        
        text = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        text.insert(tk.END, help_text)
        text.config(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True)
    
    def show_about(self):
        """显示关于信息"""
        about_text = """
        SLM监控系统
        版本: 1.0.0
        
        用于选择性激光熔化(SLM)设备的实时监控系统
        
        功能:
        - 双摄像头实时监控
        - 红外热像温度监测
        - 振动传感器数据采集
        - 智能扑粉检测
        
        开发者: Your Name
        """
        
        tk.messagebox.showinfo("关于", about_text)
    
    def on_closing(self):
        """关闭窗口回调"""
        print("🚪 on_closing 被调用 - 用户要关闭窗口")
        print(f"🔍 调用堆栈:")
        import traceback
        traceback.print_stack()
        
        if tk.messagebox.askokcancel("退出", "确定要退出程序吗？"):
            print("✅ 用户确认退出")
            self.is_shutting_down = True
            
            # 停止振动调试
            if hasattr(self, '_vibration_monitoring_started'):
                self._vibration_monitoring_started = False
                print("🛑 振动调试已停止")
            
            # 停止相机监控
            self.on_stop_monitoring()
            
            # 安全关闭所有设备
            print("🔧 正在安全关闭设备...")
            try:
                for device_name, device in self.devices.items():
                    print(f"📱 关闭设备: {device_name}")
                    try:
                        if hasattr(device, 'stop_monitoring'):
                            device.stop_monitoring()
                        if hasattr(device, 'disconnect'):
                            device.disconnect()
                        print(f"✅ 设备 {device_name} 已安全关闭")
                    except Exception as e:
                        print(f"⚠️ 关闭设备 {device_name} 时出现警告: {e}")
            except Exception as e:
                print(f"⚠️ 设备清理过程中出现错误: {e}")
            
            time.sleep(1.0)  # 增加等待时间确保设备完全断开
            print("✨ 所有设备已清理完毕")
            self.root.quit()
        else:
            print("❌ 用户取消退出")
    
    def run(self):
        """运行主窗口"""
        log_info("开始运行主窗口...", "MAIN_WINDOW")
        print("🚀 开始运行主窗口...")
        print("📱 窗口标题:", self.root.title())
        print("📐 窗口大小:", self.root.geometry())
        
        # 检查窗口大小是否合适
        def check_window_layout():
            current_geometry = self.root.geometry()
            width, height = map(int, current_geometry.split('+')[0].split('x'))
            if width < 1200 or height < 800:
                print(f"⚠️ 警告: 当前窗口尺寸 {width}x{height} 可能导致内容显示不完整")
                print("💡 建议: 将窗口拖拽到更大尺寸或最大化窗口以获得最佳显示效果")
            else:
                print(f"✅ 窗口尺寸 {width}x{height} 适合完整显示所有内容")
        
        # 延迟检查，让窗口有时间完全初始化
        self.root.after(1000, check_window_layout)
        
        print("🔄 进入Tkinter主循环...")
        
        # 设置窗口关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        try:
            self.root.mainloop()
            log_info("Tkinter主循环结束", "MAIN_WINDOW")
            print("🔚 Tkinter主循环结束")
        except Exception as e:
            log_error(f"主循环运行错误: {e}", "MAIN_WINDOW")
            print(f"❌ 主循环运行错误: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_closing(self):
        """窗口关闭事件处理"""
        log_info("用户关闭窗口，开始清理资源...", "MAIN_WINDOW")
        print("🔄 用户关闭窗口，开始清理资源...")
        
        # 设置关闭标记，停止设备状态更新循环
        self.is_shutting_down = True
        
        try:
            # 停止所有正在运行的任务
            if hasattr(self, 'control_panel') and self.control_panel:
                if hasattr(self.control_panel, 'recording') and self.control_panel.recording:
                    self.control_panel._stop_recording()
                    log_info("已停止录制任务", "MAIN_WINDOW")
            
            # 保存日志并关闭日志系统
            log_info("程序正常退出，保存日志文件", "MAIN_WINDOW")
            shutdown_logging()
            
        except Exception as e:
            print(f"⚠️ 清理资源时出错: {e}")
        finally:
            # 销毁窗口
            self.root.destroy()
    
    def _optimize_window_size(self):
        """优化窗口大小以确保最佳显示效果"""
        try:
            # 获取屏幕尺寸
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # 计算最佳窗口尺寸
            optimal_width = min(1400, int(screen_width * 0.9))
            optimal_height = min(900, int(screen_height * 0.85))
            
            # 确保不小于最小尺寸
            window_width = max(1200, optimal_width)
            window_height = max(800, optimal_height)
            
            # 窗口居中
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # 更新状态栏
            self.status_bar.config(text=f"窗口已优化为 {window_width}x{window_height}")
            print(f"✅ 窗口已优化为 {window_width}x{window_height}")
            
            # 3秒后恢复状态栏
            self.root.after(3000, lambda: self.status_bar.config(text="就绪"))
            
        except Exception as e:
            print(f"❌ 优化窗口大小失败: {e}")
            self.status_bar.config(text="窗口优化失败")
    
    def _reset_layout(self):
        """重置布局到默认状态"""
        try:
            # 重置到默认尺寸
            self.root.geometry("1300x850")
            
            # 更新状态栏
            self.status_bar.config(text="布局已重置")
            print("✅ 布局已重置")
            
            # 3秒后恢复状态栏
            self.root.after(3000, lambda: self.status_bar.config(text="就绪"))
            
        except Exception as e:
            print(f"❌ 重置布局失败: {e}")
            self.status_bar.config(text="布局重置失败")

if __name__ == "__main__":
    # 测试代码
    class MockDevice:
        def __init__(self, name):
            self.name = name
    
    devices = {
        'camera': MockDevice('Camera'),
        'thermal': MockDevice('Thermal'),
        'secondary_camera': MockDevice('Secondary'),
        'vibration': MockDevice('Vibration')
    }
    
    app = MainWindow(devices)
    app.run()