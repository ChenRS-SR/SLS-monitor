"""
相机面板模块
实现摄像头图像显示和控制
"""

import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
from ..config.camera_config import IMAGE_CONFIG
from ..utils.image_utils import resize_image_keep_aspect

class CameraPanel:
    """相机面板类，用于显示摄像头图像和控制"""
    
    def __init__(self, parent, camera, title, image_config=None):
        """
        初始化相机面板
        
        Args:
            parent: 父级窗口
            camera: 相机设备对象
            title: 面板标题
            image_config: 自定义图像配置参数，如果为None则使用默认配置
        """
        self.frame = ttk.LabelFrame(parent, text=title)
        # 应用加粗字体样式
        self.frame.configure(style='Bold.TLabelframe')
        self.camera = camera
        self.device = camera  # 添加device属性指向camera，与main_window.py中的期望匹配
        self.update_active = False  # 初始化时设为False
        
        # 使用自定义配置或默认配置
        self.image_config = image_config if image_config else IMAGE_CONFIG
        
        # 状态变量
        self.visible = tk.BooleanVar(value=True)
        self.visible.trace('w', self._on_visibility_change)
        
        # 初始化UI组件
        self._init_ui()
        
        # 启动图像更新
        self.start_update()
    
    def _init_ui(self):
        """初始化UI布局"""
        # 创建主要内容框架，使用水平布局
        main_content_frame = ttk.Frame(self.frame)
        main_content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=3, pady=3)  # 减小边距
        
        # 右侧控制区域，垂直排列（先创建以确定宽度）
        control_frame = ttk.Frame(main_content_frame, width=90)  # 稍微减小宽度
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(3, 0))  # 减小间距
        control_frame.pack_propagate(False)  # 保持固定宽度
        
        # 左侧图像显示区域
        image_frame = ttk.Frame(main_content_frame)
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))  # 减小间距
        
        # 创建图像显示容器（移除额外的边框空间）
        container_width = self.image_config["display_width"]
        container_height = self.image_config["display_height"]
        self.image_container = ttk.Frame(image_frame, width=container_width, height=container_height)
        self.image_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.image_container.pack_propagate(False)  # 防止容器被内容改变大小
        
        # 图像显示标签（移除内边距以去除黑边）
        self.image_label = ttk.Label(self.image_container)
        self.image_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # 第一行：状态显示（增加高度）
        self.status_label = ttk.Label(
            control_frame, 
            text="就绪", 
            font=("Arial", 8),
            relief=tk.RIDGE,
            padding=(3, 8),  # 增加垂直padding
            anchor="center",
            wraplength=80  # 允许文本换行
        )
        self.status_label.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))  # 减小间距
        
        # 第二行：暂停/继续按钮
        self.pause_button = ttk.Button(
            control_frame,
            text="暂停",
            command=self._toggle_pause
        )
        self.pause_button.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))  # 减小间距
        
        # 第三行：180度旋转按钮（简化文本）
        rotate_text = "旋转:开" if self.camera.get_rotate_180() else "旋转:关"
        self.rotate_button = ttk.Button(
            control_frame,
            text=rotate_text,
            command=self._toggle_rotate
        )
        self.rotate_button.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))  # 减小间距
    
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
            # 获取图像（已经在camera.py中缩放好了）
            frame = self.camera.get_display_frame()
            if frame is not None:
                try:
                    # 直接转换颜色空间，不需要再次缩放
                    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    
                    # 更新显示
                    photo = ImageTk.PhotoImage(image=image)
                    self.image_label.configure(image=photo)
                    self.image_label.image = photo  # 保持引用
                    
                    self.status_label.config(text="正常")
                except Exception as e:
                    self.status_label.config(text=f"图像处理错误: {str(e)}")
            else:
                self.status_label.config(text="无图像")
        
        except Exception as e:
            self.status_label.config(text=f"错误: {str(e)}")
        
        # 继续更新 - 使用配置文件中的更新间隔
        if self.update_active:
            update_interval = self.image_config.get('ui_update_interval', 66)  # 默认15fps
            self.frame.after(update_interval, self._update_image)
    
    def _toggle_pause(self):
        """切换暂停/继续状态"""
        if self.update_active:
            self.stop_update()
            self.pause_button.config(text="继续")
            self.status_label.config(text="已暂停")
        else:
            self.start_update()
            self.pause_button.config(text="暂停")
    
    def _toggle_rotate(self):
        """切换180度旋转状态"""
        try:
            rotate_enabled = self.camera.toggle_rotate_180()
            # 简化按钮文本
            rotate_text = "旋转:开" if rotate_enabled else "旋转:关"
            self.rotate_button.config(text=rotate_text)
            self.status_label.config(
                text=f"180度旋转已{'启用' if rotate_enabled else '禁用'}"
            )
        except Exception as e:
            self.status_label.config(text=f"旋转设置错误: {str(e)}")
    
    def _on_visibility_change(self, *args):
        """可见性改变回调"""
        if self.visible.get():
            self.frame.grid()
            if self.update_active:
                self._update_image()
        else:
            self.frame.grid_remove()
    
    def capture_image(self, filename_prefix, save_path=None):
        """
        捕获当前图像并保存
        
        Args:
            filename_prefix: 文件名前缀
            save_path: 保存路径，如果为None则使用默认路径
        """
        try:
            # 如果没有指定保存路径，则使用默认路径
            if save_path is None:
                from ..config.system_config import OUTPUT_DIR, IMAGE_DIR
                import os
                save_path = os.path.join(OUTPUT_DIR, IMAGE_DIR)
                print(f"[DEBUG] 使用默认保存路径: {save_path}")
            else:
                print(f"[DEBUG] 使用指定保存路径: {save_path}")
            
            # 确保保存路径存在
            import os
            if not os.path.exists(save_path):
                print(f"[DEBUG] 创建保存目录: {save_path}")
                os.makedirs(save_path, exist_ok=True)
            
            # 保存图像
            print(f"[DEBUG] 尝试保存图像，前缀: {filename_prefix}")
            saved_path = self.camera.save_frame(save_path, filename_prefix)
            
            if saved_path:
                print(f"[DEBUG] 图像已成功保存到: {saved_path}")
                self.status_label.config(text=f"已保存: {saved_path}")
                return True
            else:
                print(f"[DEBUG] 图像保存返回None，可能失败")
                self.status_label.config(text="保存失败: 未返回保存路径")
                return False
        except Exception as e:
            print(f"[DEBUG] 图像保存异常: {str(e)}")
            self.status_label.config(text=f"保存失败: {str(e)}")
            return False