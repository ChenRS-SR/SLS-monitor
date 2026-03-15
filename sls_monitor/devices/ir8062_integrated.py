#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IR8062 热成像设备类 - SLS项目集成版本
基于pysenxor MI48直接读取，替代复杂的串口解析

版本更新 v2.0：
- 使用pysenxor MI48直接读取IR8062数据
- 正确的80x62分辨率，数据格式为(62,80)
- 简化代码，消除复杂的USB包解析
- 基于成功的stream_usb_fixed.py工作流程
"""

import sys
import os
import time
import numpy as np
import cv2
import threading
import queue
from datetime import datetime
import logging

# 添加pysenxor路径
pysenxor_path = os.path.join(os.path.dirname(__file__), '..', '..', 'pysenxor-master')
sys.path.insert(0, pysenxor_path)

try:
    from senxor.mi48 import MI48
    from senxor.utils import data_to_frame, connect_senxor
    PYSENXOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ pysenxor不可用: {e}")
    PYSENXOR_AVAILABLE = False

class IR8062Device:
    """IR8062红外热成像设备类 - 基于pysenxor MI48"""
    
    def __init__(self, port=None, simulation_mode=False):
        self.port = port
        self.simulation_mode = simulation_mode
        self.mi48 = None
        self.is_running = False
        self.connected = False
        self.data_queue = queue.Queue(maxsize=100)
        self.latest_frame = None
        self.frame_count = 0
        
        # 图像尺寸 (基于pysenxor的正确实现)
        self.width = 80
        self.height = 62
        
        # 设置日志
        self.logger = logging.getLogger('IR8062Device')
        self.logger.setLevel(logging.WARNING)  # 减少调试输出
        
        # 自动连接
        self._initialize_connection()
    
    def _initialize_connection(self):
        """初始化连接"""
        if self.connect():
            self.start_monitoring()
    
    def connect(self):
        """连接设备"""
        if self.simulation_mode:
            self.connected = True
            self.logger.info("IR8062模拟模式已启用")
            return True
        
        if not PYSENXOR_AVAILABLE:
            self.logger.warning("pysenxor不可用，启用模拟模式")
            self.simulation_mode = True
            self.connected = True
            return True
        
        # 先确保之前的连接已断开
        self._safe_disconnect()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.logger.info(f"IR8062连接尝试 {attempt + 1}/{max_retries}...")
                
                # 使用pysenxor连接设备
                if self.port:
                    self.mi48, connected_port, port_names = connect_senxor(src=self.port)
                else:
                    self.mi48, connected_port, port_names = connect_senxor()
                
                if self.mi48:
                    self.connected = True
                    self.logger.info(f"✅ IR8062连接成功: {connected_port}")
                    
                    # 配置设备
                    try:
                        self.mi48.set_fps(10)
                        self.mi48.disable_filter(f1=True, f2=True, f3=True)
                        self.mi48.set_sens_factor(100)
                        
                        # 启动数据流
                        self.mi48.start(stream=True, with_header=False)
                        return True
                    except Exception as config_error:
                        self.logger.warning(f"设备配置失败: {config_error}")
                        self._safe_disconnect()
                        continue
                else:
                    self.logger.warning(f"连接失败 (尝试 {attempt + 1})，尝试过的端口: {port_names}")
                    
            except Exception as e:
                self.logger.warning(f"连接异常 (尝试 {attempt + 1}): {e}")
                self._safe_disconnect()
                
            # 重试前等待
            if attempt < max_retries - 1:
                time.sleep(2)
        
        # 所有尝试失败，启用模拟模式
        self.logger.warning("所有连接尝试失败，启用模拟模式作为备选")
        self.simulation_mode = True
        self.connected = True
        return True
    
    def disconnect(self):
        """断开连接"""
        self._safe_disconnect()
        self.logger.info("已断开连接")
    
    def _safe_disconnect(self):
        """安全断开连接的内部方法"""
        self.is_running = False
        
        if self.mi48 and not self.simulation_mode:
            try:
                self.logger.info("正在停止IR8062数据流...")
                self.mi48.stop()
                time.sleep(0.5)  # 给设备时间停止
                
                # 尝试清空缓冲区
                if hasattr(self.mi48, 'ser') and self.mi48.ser and self.mi48.ser.is_open:
                    self.mi48.ser.reset_input_buffer()
                    self.mi48.ser.reset_output_buffer()
                    
                self.logger.info("IR8062设备已安全停止")
            except Exception as e:
                self.logger.warning(f"停止设备时出现警告: {e}")
            finally:
                self.mi48 = None
                
        self.connected = False
    
    def _read_thermal_frame(self):
        """读取热成像帧数据 - 使用pysenxor MI48"""
        try:
            if self.simulation_mode:
                return self._generate_simulation_data()
            
            if not self.mi48:
                return None
            
            # 读取原始数据
            data, header = self.mi48.read()
            
            if data is None:
                return None
            
            # 转换为80x62的2D数组 (结果是62x80)
            frame_2d = data_to_frame(data, (self.width, self.height), hflip=False)
            
            return frame_2d
            
        except Exception as e:
            self.logger.error(f"读取帧失败: {e}")
            return None
    
    def _generate_simulation_data(self):
        """生成模拟温度数据 - 80x62分辨率"""
        # 创建基础温度场
        base_temp = 25.0 + 5 * np.sin(time.time() * 0.5)
        
        # 创建温度梯度
        y, x = np.ogrid[:self.height, :self.width]
        center_x, center_y = self.width // 2, self.height // 2
        
        # 径向温度分布
        distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        max_distance = np.sqrt(center_x**2 + center_y**2)
        
        # 温度场
        temp_field = base_temp + 10 * np.exp(-distance / max_distance * 2)
        
        # 添加噪声
        noise = np.random.normal(0, 0.5, temp_field.shape)
        temp_field += noise
        
        # 添加多个动态热点 (适配更高分辨率)
        hot_spots = [
            (center_x + 15 * np.sin(time.time() * 0.3), center_y + 8 * np.cos(time.time() * 0.4), 8),
            (center_x - 20 * np.cos(time.time() * 0.2), center_y + 12 * np.sin(time.time() * 0.5), 6),
            (center_x + 10 * np.sin(time.time() * 0.6), center_y - 15 * np.cos(time.time() * 0.3), 5)
        ]
        
        for hot_x, hot_y, intensity in hot_spots:
            hot_x, hot_y = int(hot_x), int(hot_y)
            if 0 <= hot_x < self.width and 0 <= hot_y < self.height:
                # 创建高斯热点
                for dy in range(-3, 4):
                    for dx in range(-3, 4):
                        y_pos, x_pos = hot_y + dy, hot_x + dx
                        if 0 <= y_pos < self.height and 0 <= x_pos < self.width:
                            distance = np.sqrt(dx*dx + dy*dy)
                            temp_field[y_pos, x_pos] += intensity * np.exp(-distance/2)
        
        return temp_field.astype(np.float32)
    
    def _data_reader_thread(self):
        """数据读取线程 - 简化版本使用pysenxor"""
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while self.is_running:
            try:
                # 读取热成像帧
                frame = self._read_thermal_frame()
                
                if frame is not None:
                    # 重置错误计数器
                    consecutive_errors = 0
                    
                    # 更新最新帧
                    self.latest_frame = {
                        'frame': frame,
                        'timestamp': datetime.now(),
                        'frame_id': self.frame_count,
                        'temp_min': frame.min(),
                        'temp_max': frame.max(),
                        'temp_avg': frame.mean()
                    }
                    
                    # 添加到队列
                    try:
                        self.data_queue.put(self.latest_frame, block=False)
                    except queue.Full:
                        try:
                            self.data_queue.get(block=False)
                            self.data_queue.put(self.latest_frame, block=False)
                        except queue.Empty:
                            pass
                    
                    self.frame_count += 1
                else:
                    consecutive_errors += 1
                
                time.sleep(0.1)  # 10 FPS
                
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= 3:  # 只记录前3个错误
                    self.logger.warning(f"数据读取错误 ({consecutive_errors}): {e}")
                
                # 如果连续错误太多，切换到模拟模式
                if consecutive_errors >= max_consecutive_errors and not self.simulation_mode:
                    self.logger.error(f"连续{max_consecutive_errors}次读取失败，切换到模拟模式")
                    self.simulation_mode = True
                    self._safe_disconnect()
                    consecutive_errors = 0
                
                time.sleep(1 if consecutive_errors > 5 else 0.5)
    
    def start_monitoring(self):
        """开始监控"""
        if self.is_running:
            return True
        
        self.is_running = True
        self.reader_thread = threading.Thread(target=self._data_reader_thread, daemon=True)
        self.reader_thread.start()
        
        self.logger.info("开始热成像监控")
        return True
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        if hasattr(self, 'reader_thread'):
            self.reader_thread.join(timeout=2)
        self.logger.info("停止热成像监控")
    
    # === SLS项目兼容接口 ===
    
    def get_thermal_data(self):
        """获取最新的热成像数据 - SLS项目接口"""
        if self.latest_frame:
            return self.latest_frame['frame']
        return None
    
    def get_latest_frame(self):
        """获取最新帧的完整信息"""
        return self.latest_frame
    
    def get_temperature_stats(self):
        """获取温度统计信息"""
        if self.latest_frame:
            return {
                'min_temp': self.latest_frame['temp_min'],
                'max_temp': self.latest_frame['temp_max'],
                'avg_temp': self.latest_frame['temp_avg'],
                'frame_id': self.latest_frame['frame_id'],
                'timestamp': self.latest_frame['timestamp']
            }
        return None
    
    def get_current_temp_range(self):
        """获取当前帧的温度最值
        
        Returns:
            tuple: (temp_min, temp_max) 如果没有数据返回 (None, None)
        """
        if self.latest_frame:
            return self.latest_frame['temp_min'], self.latest_frame['temp_max']
        return None, None
    
    def initialize(self):
        """初始化设备 - SLS项目接口"""
        return self.connected or self.simulation_mode
    
    def check_status(self):
        """检查设备状态 - SLS项目接口"""
        return self.connected and self.is_running
    
    def save_current_frame(self, filepath):
        """保存当前帧 - CH3图像到指定路径，数据文件到CH3_Data文件夹"""
        if not self.latest_frame:
            return False
            
        frame = self.latest_frame['frame']
        
        # 分离目录和文件名
        import os
        base_dir = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        
        # 创建CH3_Data文件夹（与CH3同级，都在images目录下）
        images_dir = os.path.dirname(base_dir)  # 获取images目录
        data_dir = os.path.join(images_dir, "CH3_Data")
        os.makedirs(data_dir, exist_ok=True)
        
        # 数据文件路径
        data_filepath = os.path.join(data_dir, filename)
        
        # 保存多种格式的数据文件到CH3_Data
        try:
            # 1. 保存.npy格式
            np.save(f"{data_filepath}.npy", frame)
            
            # 2. 保存.npz格式（压缩，包含元数据）
            metadata = {
                'timestamp': self.latest_frame['timestamp'].isoformat(),
                'frame_id': self.latest_frame['frame_id'],
                'temp_min': self.latest_frame['temp_min'],
                'temp_max': self.latest_frame['temp_max'],
                'temp_avg': self.latest_frame['temp_avg'],
                'width': self.width,
                'height': self.height
            }
            np.savez_compressed(f"{data_filepath}.npz", 
                              thermal_data=frame, 
                              metadata=metadata)
            
            # 3. 保存.mat格式（MATLAB兼容）
            try:
                import scipy.io
                mat_data = {
                    'thermal_data': frame,
                    'timestamp': self.latest_frame['timestamp'].isoformat(),
                    'frame_id': self.latest_frame['frame_id'],
                    'temp_min': self.latest_frame['temp_min'],
                    'temp_max': self.latest_frame['temp_max'],
                    'temp_avg': self.latest_frame['temp_avg'],
                    'width': self.width,
                    'height': self.height
                }
                scipy.io.savemat(f"{data_filepath}.mat", mat_data)
            except ImportError:
                self.logger.warning("scipy不可用，跳过.mat文件保存")
            
            # 4. 保存.csv格式（二维数据展平）
            try:
                import pandas as pd
                # 将2D数组展平并创建DataFrame
                df = pd.DataFrame(frame)
                # 添加元数据作为注释在CSV文件开头
                with open(f"{data_filepath}.csv", 'w') as f:
                    f.write(f"# Thermal Data - {self.latest_frame['timestamp'].isoformat()}\n")
                    f.write(f"# Frame ID: {self.latest_frame['frame_id']}\n")
                    f.write(f"# Temperature Range: {self.latest_frame['temp_min']:.2f} - {self.latest_frame['temp_max']:.2f} °C\n")
                    f.write(f"# Average Temperature: {self.latest_frame['temp_avg']:.2f} °C\n")
                    f.write(f"# Dimensions: {self.width} x {self.height}\n")
                    f.write("# Data starts below:\n")
                df.to_csv(f"{data_filepath}.csv", mode='a', header=True, index=True)
            except ImportError:
                self.logger.warning("pandas不可用，跳过.csv文件保存")
            
        except Exception as e:
            self.logger.error(f"保存数据文件失败: {e}")
        
        # 保存可视化图像到CH3文件夹（原filepath）
        try:
            temp_min, temp_max = frame.min(), frame.max()
            if temp_max > temp_min:
                normalized = ((frame - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)
            else:
                normalized = np.zeros_like(frame, dtype=np.uint8)
            
            colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
            resized = cv2.resize(colored, (640, 496), interpolation=cv2.INTER_NEAREST)  # 80*8 x 62*8
            
            # 使用支持中文路径的保存方法
            try:
                # 方法1：尝试直接保存
                success = cv2.imwrite(f"{filepath}.png", resized)
                if success:
                    return success
                else:
                    # 方法2：使用编码方式处理中文路径
                    self.logger.info("直接保存失败，尝试中文路径兼容保存...")
                    encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
                    result, encimg = cv2.imencode('.png', resized, encode_param)
                    if result:
                        encimg.tofile(f"{filepath}.png")
                        self.logger.info(f"CH3热像图已保存（中文路径）: {filepath}.png")
                        return True
                    else:
                        self.logger.error(f"图像编码失败: {filepath}.png")
                        return False
            except Exception as e:
                self.logger.error(f"保存CH3图像异常: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"保存图像文件失败: {e}")
            return False
    
    def save_frame_with_panel_settings(self, filepath, thermal_panel=None):
        """使用thermal_panel的设置保存当前帧（如果提供）
        
        Args:
            filepath: 保存路径（不包含扩展名）
            thermal_panel: ThermalPanel实例，如果提供则使用其设置
            
        Returns:
            bool: 保存成功返回True
        """
        if not self.latest_frame:
            return False
            
        frame = self.latest_frame['frame']
        
        # 分离目录和文件名
        import os
        base_dir = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        
        # 创建CH3_Data文件夹（与CH3同级，都在images目录下）
        images_dir = os.path.dirname(base_dir)  # 获取images目录
        data_dir = os.path.join(images_dir, "CH3_Data")
        os.makedirs(data_dir, exist_ok=True)
        
        # 数据文件路径
        data_filepath = os.path.join(data_dir, filename)
        
        # 保存多种格式的数据文件到CH3_Data（与基本方法相同）
        try:
            # 1. 保存.npy格式
            np.save(f"{data_filepath}.npy", frame)
            
            # 2. 保存.npz格式（压缩，包含元数据）
            metadata = {
                'timestamp': self.latest_frame['timestamp'].isoformat(),
                'frame_id': self.latest_frame['frame_id'],
                'temp_min': self.latest_frame['temp_min'],
                'temp_max': self.latest_frame['temp_max'],
                'temp_avg': self.latest_frame['temp_avg'],
                'width': self.width,
                'height': self.height
            }
            np.savez_compressed(f"{data_filepath}.npz", 
                              thermal_data=frame, 
                              metadata=metadata)
            
            # 3. 保存.mat格式（MATLAB兼容）
            try:
                import scipy.io
                mat_data = {
                    'thermal_data': frame,
                    'timestamp': self.latest_frame['timestamp'].isoformat(),
                    'frame_id': self.latest_frame['frame_id'],
                    'temp_min': self.latest_frame['temp_min'],
                    'temp_max': self.latest_frame['temp_max'],
                    'temp_avg': self.latest_frame['temp_avg'],
                    'width': self.width,
                    'height': self.height
                }
                scipy.io.savemat(f"{data_filepath}.mat", mat_data)
            except ImportError:
                self.logger.warning("scipy不可用，跳过.mat文件保存")
            
            # 4. 保存.csv格式
            try:
                import pandas as pd
                df = pd.DataFrame(frame)
                with open(f"{data_filepath}.csv", 'w') as f:
                    f.write(f"# Thermal Data - {self.latest_frame['timestamp'].isoformat()}\n")
                    f.write(f"# Frame ID: {self.latest_frame['frame_id']}\n")
                    f.write(f"# Temperature Range: {self.latest_frame['temp_min']:.2f} - {self.latest_frame['temp_max']:.2f} °C\n")
                    f.write(f"# Average Temperature: {self.latest_frame['temp_avg']:.2f} °C\n")
                    f.write(f"# Dimensions: {self.width} x {self.height}\n")
                    f.write("# Data starts below:\n")
                df.to_csv(f"{data_filepath}.csv", mode='a', header=True, index=True)
            except ImportError:
                self.logger.warning("pandas不可用，跳过.csv文件保存")
            
        except Exception as e:
            self.logger.error(f"保存数据文件失败: {e}")
        
        # 保存可视化图像到CH3文件夹
        try:
            # 如果提供了thermal_panel，使用其处理设置
            if thermal_panel is not None:
                # 使用thermal_panel的图像处理方法
                colored = thermal_panel._apply_colormap(frame)
                
                # 应用分辨率插值
                target_width, target_height = thermal_panel._get_target_size()
                if (target_width, target_height) != (80, 62):
                    interp_flag = thermal_panel._get_interpolation_flag()
                    colored = cv2.resize(colored, (target_width, target_height), interpolation=interp_flag)
                
                # 应用滤波处理
                colored = thermal_panel._apply_filter(colored)
                
                # 添加温度范围信息
                if hasattr(thermal_panel, 'show_temp') and thermal_panel.show_temp.get():
                    temp_min, temp_max = frame.min(), frame.max()
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.putText(colored, f"Range: {temp_min:.1f}-{temp_max:.1f}°C",
                              (10, 25), font, 0.5, (255,255,255), 1)
                    cv2.putText(colored, f"Size: {target_width}x{target_height}",
                              (10, 45), font, 0.4, (255,255,255), 1)
            else:
                # 使用默认处理方式
                temp_min, temp_max = frame.min(), frame.max()
                if temp_max > temp_min:
                    normalized = ((frame - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)
                else:
                    normalized = np.zeros_like(frame, dtype=np.uint8)
                
                colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
                colored = cv2.resize(colored, (640, 496), interpolation=cv2.INTER_NEAREST)
            
            # 保存图像到CH3文件夹
            try:
                # 方法1：尝试直接保存
                success = cv2.imwrite(f"{filepath}.png", colored)
                if success:
                    return success
                else:
                    # 方法2：使用编码方式处理中文路径
                    self.logger.info("直接保存失败，尝试中文路径兼容保存...")
                    encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
                    result, encimg = cv2.imencode('.png', colored, encode_param)
                    if result:
                        encimg.tofile(f"{filepath}.png")
                        self.logger.info(f"CH3热像图已保存（中文路径）: {filepath}.png")
                        return True
                    else:
                        self.logger.error(f"图像编码失败: {filepath}.png")
                        return False
            except Exception as e:
                # 如果高级处理失败，回退到基本保存方法
                self.logger.warning(f"高级保存失败，使用基本方法: {e}")
                return self.save_current_frame(filepath)
                
        except Exception as e:
            # 如果高级处理失败，回退到基本保存方法
            self.logger.warning(f"高级保存失败，使用基本方法: {e}")
            return self.save_current_frame(filepath)
    
    def __del__(self):
        """清理资源"""
        try:
            self.stop_monitoring()
            self._safe_disconnect()
        except Exception as e:
            # 在析构函数中不要抛出异常
            pass


# 为了保持向后兼容，创建别名
class IR8062(IR8062Device):
    """向后兼容的类名"""
    pass