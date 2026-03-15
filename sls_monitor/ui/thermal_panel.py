"""
红外热像面板模块
实现红外热像仪图像显示和温度监测
"""

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
from ..config.camera_config import IMAGE_CONFIG
from ..utils.image_utils import resize_image_keep_aspect, create_colorbar, apply_text_overlay

class ThermalPanel:
    """红外热像面板类，用于显示热像图和温度数据"""
    
    def __init__(self, parent, thermal_device, title, image_config=None):
        """
        初始化红外热像面板
        
        Args:
            parent: 父级窗口
            thermal_device: 红外热像仪设备对象
            title: 面板标题
            image_config: 自定义图像配置参数，如果为None则使用默认配置
        """
        self.frame = ttk.LabelFrame(parent, text=title)
        # 应用加粗字体样式
        self.frame.configure(style='Bold.TLabelframe')
        self.thermal = thermal_device
        self.device = thermal_device  # 添加device属性指向thermal_device，与main_window.py中的期望匹配
        self.update_active = False
        
        # 使用自定义配置或默认配置
        self.image_config = image_config if image_config else IMAGE_CONFIG
        
        # 检测设备类型以调整显示逻辑
        self.is_fotric_device = hasattr(thermal_device, 'get_point_temperature')  # Fotric特有方法
        
        # 状态变量
        self.visible = tk.BooleanVar(value=True)
        self.visible.trace('w', self._on_visibility_change)
        self.show_temp = tk.BooleanVar(value=True)
        self.show_colorbar = tk.BooleanVar(value=True)  # 默认显示色带
        
        # 温度范围
        self.temp_min = 20.0  # 最小温度
        self.temp_max = 200.0  # 最大温度
        
        # 图像处理参数
        self.scale_factor = tk.StringVar(value="4x (320x248)")
        self.interpolation_method = tk.StringVar(value="双线性插值")
        self.filter_method = tk.StringVar(value="高斯模糊")
        
        # 当前应用的参数（用于实际处理）
        self.applied_scale = "4x (320x248)"
        self.applied_interpolation = "双线性插值"
        self.applied_filter = "高斯模糊"
        
        # 初始化UI组件
        self._init_ui()
        
        # 创建颜色映射
        self._create_colormap()
    
    def _init_ui(self):
        """初始化UI布局"""
        # 创建图像显示容器，尺寸比配置稍大以留出边框
        container_width = self.image_config["display_width"] + 20  # 两边各留10像素边框
        container_height = self.image_config["display_height"] + 20  # 上下各留10像素边框
        self.image_container = ttk.Frame(self.frame, width=container_width, height=container_height)
        self.image_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.image_container.pack_propagate(False)  # 防止容器被内容改变大小
        
        # 图像显示标签
        self.image_label = ttk.Label(self.image_container)
        self.image_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)  # 添加内边距
        
        # 控制面板
        control_frame = ttk.Frame(self.frame)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # 温度显示
        temp_frame = ttk.Frame(control_frame)
        temp_frame.pack(side=tk.LEFT)
        
        self.min_temp_label = ttk.Label(temp_frame, text=f"最低: {self.temp_min:.1f}°C")
        self.min_temp_label.pack(side=tk.LEFT, padx=5)
        
        self.max_temp_label = ttk.Label(temp_frame, text=f"最高: {self.temp_max:.1f}°C")
        self.max_temp_label.pack(side=tk.LEFT, padx=5)
        
        # 图像处理控制面板
        processing_frame = ttk.Frame(control_frame)
        processing_frame.pack(side=tk.LEFT, padx=10)
        
        # 只有非Fotric设备才显示插值控制
        if not self.is_fotric_device:
            # 分辨率倍率选择
            ttk.Label(processing_frame, text="分辨率:").grid(row=0, column=0, padx=2, sticky="w")
            scale_combo = ttk.Combobox(
                processing_frame,
                textvariable=self.scale_factor,
                values=["1x (80x62)", "2x (160x124)", "4x (320x248)"],
                width=12,
                state="readonly"
            )
            scale_combo.grid(row=0, column=1, padx=2)
            scale_combo.bind('<<ComboboxSelected>>', self._on_scale_change)
            
            # 插值方式选择
            ttk.Label(processing_frame, text="插值:").grid(row=1, column=0, padx=2, sticky="w")
            interp_combo = ttk.Combobox(
                processing_frame,
                textvariable=self.interpolation_method,
                values=["最近邻插值", "双线性插值", "双三次插值", "Lanczos插值"],
                width=12,
                state="readonly"
            )
            interp_combo.grid(row=1, column=1, padx=2)
            interp_combo.bind('<<ComboboxSelected>>', self._on_interpolation_change)
            
            # 滤波方式选择
            ttk.Label(processing_frame, text="滤波:").grid(row=2, column=0, padx=2, sticky="w")
            filter_combo = ttk.Combobox(
                processing_frame,
                textvariable=self.filter_method,
                values=["无滤波", "高斯模糊", "中值滤波", "双边滤波", "均值滤波", "形态学滤波"],
                width=12,
                state="readonly"
            )
            filter_combo.grid(row=2, column=1, padx=2)
            filter_combo.bind('<<ComboboxSelected>>', self._on_filter_change)
        else:
            # Fotric设备显示设备信息
            ttk.Label(processing_frame, text="设备类型: Fotric 628ch").grid(row=0, column=0, columnspan=2, padx=2, sticky="w")
            ttk.Label(processing_frame, text="高分辨率，无需插值").grid(row=1, column=0, columnspan=2, padx=2, sticky="w")
        
        # 控制按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.RIGHT)
        
        # 温度显示切换
        self.temp_button = ttk.Checkbutton(
            button_frame,
            text="显示温度",
            variable=self.show_temp,
            command=self._toggle_temp_display
        )
        self.temp_button.pack(side=tk.TOP, pady=2)
        
        # 色带显示切换
        self.colorbar_button = ttk.Checkbutton(
            button_frame,
            text="显示色带",
            variable=self.show_colorbar,
            command=self._toggle_colorbar_display
        )
        self.colorbar_button.pack(side=tk.TOP, pady=2)
        
        # 只有非Fotric设备才显示应用修改按钮
        if not self.is_fotric_device:
            # 应用修改按钮
            self.apply_button = ttk.Button(
                button_frame,
                text="应用修改",
                command=self._apply_changes
            )
            self.apply_button.pack(side=tk.TOP, pady=2)
        
        # 暂停/继续按钮
        self.pause_button = ttk.Button(
            button_frame,
            text="暂停",
            command=self._toggle_pause
        )
        self.pause_button.pack(side=tk.TOP, pady=2)
    
    def _create_colormap(self):
        """创建温度到颜色的映射"""
        # 创建铁红色映射
        colormap_size = 256
        self.colormap = np.zeros((colormap_size, 1, 3), dtype=np.uint8)
        
        # 生成颜色渐变
        for i in range(colormap_size):
            # 将值归一化到[0,1]
            t = i / (colormap_size - 1)
            
            if t < 0.25:  # 蓝到青
                r, g, b = 0, int(255 * t * 4), 255
            elif t < 0.5:  # 青到绿
                r, g, b = 0, 255, int(255 * (2 - t * 4))
            elif t < 0.75:  # 绿到黄
                r, g, b = int(255 * (t * 4 - 2)), 255, 0
            else:  # 黄到红
                r, g, b = 255, int(255 * (4 - t * 4)), 0
            
            self.colormap[i] = [b, g, r]  # OpenCV使用BGR顺序
    
    def _apply_colormap(self, thermal_data):
        """
        将温度数据转换为彩色图像
        
        Args:
            thermal_data: 温度数据数组
        
        Returns:
            彩色图像数组
        """
        # 动态调整温度范围
        data_min = thermal_data.min()
        data_max = thermal_data.max()
        
        # 将温度值归一化到[0,255]
        if data_max > data_min:
            normalized = np.clip((thermal_data - data_min) / (data_max - data_min), 0, 1)
        else:
            normalized = np.ones_like(thermal_data) * 0.5
        
        indices = (normalized * 255).astype(np.uint8)
        
        # 应用颜色映射
        colored = cv2.applyColorMap(indices, cv2.COLORMAP_JET)
        
        return colored
    
    def _get_interpolation_flag(self):
        """获取OpenCV插值标志"""
        method = self.applied_interpolation
        if method == "最近邻插值":
            return cv2.INTER_NEAREST
        elif method == "双线性插值":
            return cv2.INTER_LINEAR
        elif method == "双三次插值":
            return cv2.INTER_CUBIC
        elif method == "Lanczos插值":
            return cv2.INTER_LANCZOS4
        else:
            return cv2.INTER_LINEAR
    
    def _get_target_size(self):
        """获取目标分辨率"""
        scale = self.applied_scale
        if scale == "2x (160x124)":
            return (160, 124)
        elif scale == "4x (320x248)":
            return (320, 248)
        else:
            return (80, 62)
    
    def _apply_filter(self, image):
        """应用滤波处理"""
        filter_type = self.applied_filter
        
        if filter_type == "无滤波":
            return image
        elif filter_type == "高斯模糊":
            return cv2.GaussianBlur(image, (5, 5), 1.0)
        elif filter_type == "中值滤波":
            return cv2.medianBlur(image, 5)
        elif filter_type == "双边滤波":
            return cv2.bilateralFilter(image, 9, 75, 75)
        elif filter_type == "均值滤波":
            kernel = np.ones((5, 5), np.float32) / 25
            return cv2.filter2D(image, -1, kernel)
        elif filter_type == "形态学滤波":
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            return cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
        else:
            return image
    
    def _apply_changes(self):
        """应用当前下拉菜单的选择"""
        if self.is_fotric_device:
            # Fotric设备不需要应用修改
            return
            
        # 更新应用的参数
        self.applied_scale = self.scale_factor.get()
        self.applied_interpolation = self.interpolation_method.get()
        self.applied_filter = self.filter_method.get()
        
        print(f"✅ 应用修改:")
        print(f"  分辨率: {self.applied_scale}")
        print(f"  插值: {self.applied_interpolation}")
        print(f"  滤波: {self.applied_filter}")
        
        # 更新按钮文本显示已应用
        if hasattr(self, 'apply_button'):
            self.apply_button.config(text="✓ 已应用")
            
            # 2秒后恢复按钮文本
            self.frame.after(2000, lambda: self.apply_button.config(text="应用修改"))
    
    def _on_scale_change(self, event=None):
        """分辨率倍率改变回调"""
        if self.is_fotric_device:
            return
        print(f"分辨率选择更改为: {self.scale_factor.get()} (未应用)")
        # 更新按钮状态提示需要应用
        if hasattr(self, 'apply_button') and self.applied_scale != self.scale_factor.get():
            self.apply_button.config(text="应用修改 *")
    
    def _on_interpolation_change(self, event=None):
        """插值方式改变回调"""
        if self.is_fotric_device:
            return
        print(f"插值方式选择更改为: {self.interpolation_method.get()} (未应用)")
        # 更新按钮状态提示需要应用
        if hasattr(self, 'apply_button') and self.applied_interpolation != self.interpolation_method.get():
            self.apply_button.config(text="应用修改 *")
    
    def _on_filter_change(self, event=None):
        """滤波方式改变回调"""
        if self.is_fotric_device:
            return
        print(f"滤波方式选择更改为: {self.filter_method.get()} (未应用)")
        # 更新按钮状态提示需要应用
        if hasattr(self, 'apply_button') and self.applied_filter != self.filter_method.get():
            self.apply_button.config(text="应用修改 *")
    
    def start_update(self):
        """开始更新图像"""
        self.update_active = True
        self._update_image()
    
    def stop_update(self):
        """停止更新图像"""
        self.update_active = False
    
    def _update_image(self):
        """更新图像显示"""
        if not self.update_active or not self.visible.get():
            return
            
        try:
            # 获取温度数据
            thermal_data = self.thermal.get_thermal_data()
            if thermal_data is not None and thermal_data.size > 0:
                # 获取当前最高温度
                current_max_temp = np.max(thermal_data)
                self.max_temp_label.config(text=f"最高: {current_max_temp:.1f}°C")
                
                # 获取当前最低温度
                current_min_temp = np.min(thermal_data)
                self.min_temp_label.config(text=f"最低: {current_min_temp:.1f}°C")
                
                # 转换为彩色图像
                colored = self._apply_colormap(thermal_data)
                
                # 根据设备类型决定处理方式
                if not self.is_fotric_device:
                    # IR8062需要插值处理
                    target_width, target_height = self._get_target_size()
                    if (target_width, target_height) != (80, 62):
                        interp_flag = self._get_interpolation_flag()
                        colored = cv2.resize(colored, (target_width, target_height), interpolation=interp_flag)
                    
                    # 应用滤波处理
                    colored = self._apply_filter(colored)
                else:
                    # Fotric设备: 高分辨率数据，优化显示处理
                    original_h, original_w = colored.shape[:2]
                    
                    # 如果是高分辨率数据（640x480），进行智能缩放
                    if original_w >= 640 and original_h >= 480:
                        # 高分辨率模式：使用快速缩放，减少计算量
                        display_width = self.image_config['display_width']
                        display_height = self.image_config['display_height']
                        
                        # 计算合适的缩放尺寸，但限制最大尺寸以提高性能
                        max_display_w = min(display_width, 400)  # 限制最大宽度
                        max_display_h = min(display_height, 300)  # 限制最大高度
                        
                        # 保持宽高比缩放
                        scale_w = max_display_w / original_w
                        scale_h = max_display_h / original_h
                        scale = min(scale_w, scale_h)
                        
                        new_w = int(original_w * scale)
                        new_h = int(original_h * scale)
                        
                        # 使用快速插值算法减少计算时间
                        colored = cv2.resize(colored, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
                    else:
                        # 低分辨率模式：保持原有逻辑
                        scale_factor = min(320 / original_w, 248 / original_h)
                        new_w = int(original_w * scale_factor)
                        new_h = int(original_h * scale_factor)
                        colored = cv2.resize(colored, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                
                # 如果需要显示温度值
                if self.show_temp.get():
                    # 计算温度统计信息
                    center_y, center_x = thermal_data.shape[0] // 2, thermal_data.shape[1] // 2
                    center_temp = thermal_data[center_y, center_x]
                    average_temp = np.mean(thermal_data)
                    
                    # 在图像上添加温度信息（半透明叠加）
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.35
                    thickness = 1
                    text_color = (255, 255, 255)  # 白色文字
                    
                    # 准备文本内容
                    range_text = f"Range: {int(current_min_temp)}-{int(current_max_temp)}C"
                    center_text = f"Center: {int(center_temp)}C"
                    average_text = f"Average: {int(average_temp)}C"
                    
                    # 计算整体背景区域
                    texts = [range_text, center_text, average_text]
                    line_height = 15
                    padding = 3  # 上边距
                    bottom_padding = 1  # 下边距（更小）
                    start_x, start_y = 2, 8 + padding  # 第一行与顶部有padding距离
                    
                    # 计算最大文本宽度
                    max_width = 0
                    for text in texts:
                        (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)
                        max_width = max(max_width, text_width)
                    
                    # 创建半透明背景叠加层
                    bg_x1 = 0
                    bg_y1 = 0
                    bg_x2 = start_x + max_width + padding
                    bg_y2 = start_y + len(texts) * line_height + bottom_padding - padding - 6  # 使用更小的下边距
                    
                    # 创建背景蒙版
                    overlay = colored.copy()
                    cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)  # 黑色背景
                    
                    # 使用半透明叠加（0.4透明度）
                    alpha = 0.4  # 透明度
                    cv2.addWeighted(overlay, alpha, colored, 1 - alpha, 0, colored)
                    
                    # 添加文本
                    for i, text in enumerate(texts):
                        text_y = start_y + i * line_height
                        cv2.putText(colored, text, (start_x, text_y), font, font_scale, text_color, thickness)
                
                # 如果需要显示色带，添加到图像右侧
                if self.show_colorbar.get():
                    h, w = colored.shape[:2]
                    # 创建温度色带
                    colorbar = create_colorbar(
                        height=h,
                        min_val=current_min_temp,
                        max_val=current_max_temp,
                        colormap=cv2.COLORMAP_JET,
                        width=25  # 色带宽度
                    )
                    
                    # 增加色带与图像之间的间距
                    gap_width = 15  # 间距宽度
                    gap_area = np.zeros((h, gap_width, 3), dtype=np.uint8)  # 黑色间距区域
                    
                    # 将图像、间距和色带水平拼接
                    colorbar_h, colorbar_w = colorbar.shape[:2]
                    if colorbar_h == h:  # 高度匹配
                        # 水平拼接图像、间距和色带
                        colored = np.hstack((colored, gap_area, colorbar))
                    else:
                        # 如果高度不匹配，调整色带高度
                        colorbar_resized = cv2.resize(colorbar, (colorbar_w, h), interpolation=cv2.INTER_LINEAR)
                        colored = np.hstack((colored, gap_area, colorbar_resized))
                
                # 使用resize_image_keep_aspect调整图像大小，与camera_panel保持一致
                resized_frame = resize_image_keep_aspect(
                    colored,
                    self.image_config['display_width'],
                    self.image_config['display_height'],
                    fill_color=(0, 0, 0)
                )
                
                # 转换为PIL图像
                image = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))
                
                # 更新显示
                photo = ImageTk.PhotoImage(image=image)
                self.image_label.configure(image=photo)
                self.image_label.image = photo  # 保持引用
            else:
                # 显示"无数据"图像，增加调试信息
                device_type = "Fotric" if self.is_fotric_device else "IR8062"
                device_status = "Connected" if hasattr(self.thermal, 'is_connected') and self.thermal.is_connected else "Disconnected"
                if hasattr(self.thermal, 'simulation_mode') and self.thermal.simulation_mode:
                    device_status += " (Sim)"
                
                placeholder = np.zeros((self.image_config['display_height'], self.image_config['display_width'], 3), dtype=np.uint8)
                
                # 显示详细的状态信息
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(placeholder, "No Thermal Data", 
                           (self.image_config['display_width']//2-80, self.image_config['display_height']//2-40), 
                           font, 0.6, (255, 255, 255), 2)
                cv2.putText(placeholder, f"Device: {device_type}", 
                           (self.image_config['display_width']//2-60, self.image_config['display_height']//2-10), 
                           font, 0.4, (255, 255, 255), 1)
                cv2.putText(placeholder, f"Status: {device_status}", 
                           (self.image_config['display_width']//2-60, self.image_config['display_height']//2+15), 
                           font, 0.4, (255, 255, 255), 1)
                
                # 添加调试信息
                if hasattr(self.thermal, 'latest_frame'):
                    frame_info = "Frame: None" if self.thermal.latest_frame is None else f"Frame: {self.thermal.frame_count}"
                    cv2.putText(placeholder, frame_info, 
                               (self.image_config['display_width']//2-50, self.image_config['display_height']//2+40), 
                               font, 0.3, (255, 255, 255), 1)
                
                image = Image.fromarray(placeholder)
                photo = ImageTk.PhotoImage(image=image)
                self.image_label.configure(image=photo)
                self.image_label.image = photo
        
        except Exception as e:
            print(f"更新热像图失败: {str(e)}")
            # 显示错误图像，使用配置的显示尺寸
            try:
                error_img = np.zeros((self.image_config['display_height'], self.image_config['display_width'], 3), dtype=np.uint8)
                cv2.putText(error_img, "Error", (self.image_config['display_width']//2-30, self.image_config['display_height']//2), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                image = Image.fromarray(error_img)
                photo = ImageTk.PhotoImage(image=image)
                self.image_label.configure(image=photo)
                self.image_label.image = photo
            except:
                pass  # 如果连错误图像都无法显示，就静默忽略
        
        # 继续更新 - 使用配置文件中的热像更新频率
        if self.update_active:
            thermal_fps = self.image_config.get('thermal_fps', 15)  # 默认15fps，与配置文件一致
            update_interval = int(1000 / thermal_fps)  # 转换为毫秒
            # print(f"🌡️ 热像更新间隔: {update_interval}ms ({thermal_fps}fps)")  # 已注释掉高频调试输出
            self.frame.after(update_interval, self._update_image)
    
    def _toggle_pause(self):
        """切换暂停/继续状态"""
        if self.update_active:
            self.stop_update()
            self.pause_button.config(text="继续")
        else:
            self.start_update()
            self.pause_button.config(text="暂停")
    
    def _toggle_temp_display(self):
        """切换温度显示状态"""
        # 温度显示状态已切换，图像更新时会自动应用
        pass
    
    def _toggle_colorbar_display(self):
        """切换色带显示状态"""
        # 色带显示状态已切换，图像更新时会自动应用
        pass
    
    def _on_visibility_change(self, *args):
        """可见性改变回调"""
        if self.visible.get():
            self.frame.grid()
            if self.update_active:
                self._update_image()
        else:
            self.frame.grid_remove()
    
    def capture_image(self, filename_prefix):
        """
        捕获当前热像图并保存
        
        Args:
            filename_prefix: 文件名前缀
        """
        try:
            thermal_data = self.thermal.get_thermal_data()
            if thermal_data is not None:
                # 保存原始温度数据
                np.save(f"{filename_prefix}_thermal.npy", thermal_data)
                
                # 保存彩色图像
                colored = self._apply_colormap(thermal_data)
                
                # 应用分辨率插值
                target_width, target_height = self._get_target_size()
                if (target_width, target_height) != (80, 62):
                    interp_flag = self._get_interpolation_flag()
                    colored = cv2.resize(colored, (target_width, target_height), interpolation=interp_flag)
                
                # 应用滤波处理
                colored = self._apply_filter(colored)
                
                #这里加一个config里的参数，决定保存时是否显示温度和色带
                #就是要定义一下
                # 检查是否需要添加温度信息（同时检查界面显示和config配置）
                if self.show_temp.get() and self.image_config.get('save_with_temperature', True):
                    # 计算温度统计信息
                    current_min_temp = thermal_data.min()
                    current_max_temp = thermal_data.max()
                    center_y, center_x = thermal_data.shape[0] // 2, thermal_data.shape[1] // 2
                    center_temp = thermal_data[center_y, center_x]
                    average_temp = np.mean(thermal_data)
                    
                    # 添加温度信息（半透明叠加）
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.35
                    thickness = 1
                    text_color = (255, 255, 255)
                    
                    # 准备文本内容
                    range_text = f"Range: {int(current_min_temp)}-{int(current_max_temp)}C"
                    center_text = f"Center: {int(center_temp)}C"
                    average_text = f"Average: {int(average_temp)}C"
                    
                    # 计算整体背景区域
                    texts = [range_text, center_text, average_text]
                    line_height = 15
                    padding = 3  # 上边距
                    bottom_padding = 1  # 下边距（更小）
                    start_x, start_y = 2, 8 + padding  # 第一行与顶部有padding距离
                    
                    # 计算最大文本宽度
                    max_width = 0
                    for text in texts:
                        (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)
                        max_width = max(max_width, text_width)
                    
                    # 创建半透明背景叠加层
                    bg_x1 = 0
                    bg_y1 = 0
                    bg_x2 = start_x + max_width + padding
                    bg_y2 = start_y + len(texts) * line_height + bottom_padding - padding - 6  # 使用更小的下边距
                    
                    # 创建背景蒙版
                    overlay = colored.copy()
                    cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)  # 黑色背景
                    
                    # 使用半透明叠加（0.4透明度）
                    alpha = 0.4  # 透明度
                    cv2.addWeighted(overlay, alpha, colored, 1 - alpha, 0, colored)
                    
                    # 添加文本
                    for i, text in enumerate(texts):
                        text_y = start_y + i * line_height
                        cv2.putText(colored, text, (start_x, text_y), font, font_scale, text_color, thickness)
                
                # 如果需要保存时也显示色带（同时检查界面显示和config配置）
                if self.show_colorbar.get() and self.image_config.get('save_with_colorbar', True):
                    h, w = colored.shape[:2]
                    current_min_temp = thermal_data.min()
                    current_max_temp = thermal_data.max()
                    # 创建温度色带
                    colorbar = create_colorbar(
                        height=h,
                        min_val=current_min_temp,
                        max_val=current_max_temp,
                        colormap=cv2.COLORMAP_JET,
                        width=25
                    )
                    
                    # 增加色带与图像之间的间距
                    gap_width = 15  # 间距宽度
                    gap_area = np.zeros((h, gap_width, 3), dtype=np.uint8)  # 黑色间距区域
                    
                    # 将图像、间距和色带水平拼接
                    colorbar_h, colorbar_w = colorbar.shape[:2]
                    if colorbar_h == h:
                        colored = np.hstack((colored, gap_area, colorbar))
                    else:
                        colorbar_resized = cv2.resize(colorbar, (colorbar_w, h), interpolation=cv2.INTER_LINEAR)
                        colored = np.hstack((colored, gap_area, colorbar_resized))
                
                cv2.imwrite(f"{filename_prefix}_thermal.jpg", colored)
                return True
        
        except Exception as e:
            print(f"保存热像图失败: {str(e)}")
            return False
    
    def is_device_available(self):
        """检查热像仪设备是否可用
        
        Returns:
            bool: 设备可用返回True，否则返回False
        """
        try:
            if self.thermal is None or self.device is None:
                return False
            
            # 尝试获取数据来测试设备状态
            test_data = self.thermal.get_thermal_data()
            return test_data is not None and test_data.size > 0
            
        except Exception:
            return False
    
    def get_device_info(self):
        """获取热像仪设备信息
        
        Returns:
            dict: 包含设备状态信息的字典
        """
        info = {
            'device_available': False,
            'data_shape': None,
            'temperature_range': None,
            'last_error': None
        }
        
        try:
            if self.thermal is None or self.device is None:
                info['last_error'] = "设备引用为空"
                return info
            
            # 获取数据测试
            thermal_data = self.thermal.get_thermal_data()
            if thermal_data is not None and thermal_data.size > 0:
                info['device_available'] = True
                info['data_shape'] = thermal_data.shape
                info['temperature_range'] = (float(thermal_data.min()), float(thermal_data.max()))
            else:
                info['last_error'] = "无法获取有效数据"
                
        except Exception as e:
            info['last_error'] = str(e)
            
        return info