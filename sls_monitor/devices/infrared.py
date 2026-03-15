"""
红外热像仪控制模块
用于控制和管理Optris红外热像仪，处理温度数据采集和图像生成
"""

import ctypes
import os
import time
import numpy as np
import cv2
import threading
from ..config.infrared_config import INFRARED_CONFIG
from ..utils.error_handler import handle_device_error
from ..utils.image_utils import create_colorbar

class OptrisConnectSDK:
    """Optris红外热像仪控制类"""
    
    def __init__(self):
        """初始化红外热像仪控制器"""
        self.device_connected = False
        self.last_error = "未初始化"
        self.dll = None
        self.sdk_path = INFRARED_CONFIG["sdk_path"]
        self.dll_path = None
        self.device_index = INFRARED_CONFIG["device_index"]
        self.initialized = False
        
        # 图像参数
        self.width = 382  # PI450i LT分辨率
        self.height = 288
        self.frame_size = self.width * self.height
        
        # 温度参数
        self.temp_min = INFRARED_CONFIG["temperature_range"][0]
        self.temp_max = INFRARED_CONFIG["temperature_range"][1]
        
        # 帧率统计
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0.0
        self.fps_update_interval = 1.0  # 每秒更新一次帧率
        
        print(f"ℹ️ 初始化 {INFRARED_CONFIG['device_model']} Connect SDK")
        print(f"ℹ️ 分辨率: {self.width}x{self.height}")
        print(f"ℹ️ 温度范围: {self.temp_min}°C - {self.temp_max}°C")
    
    @handle_device_error
    def initialize(self):
        """初始化红外热像仪"""
        if not INFRARED_CONFIG["enabled"]:
            self.last_error = "红外热像仪功能已禁用"
            return False
            
        # 检查配置
        if not self.check_configuration():
            return False
            
        # 加载SDK
        if not self.load_sdk():
            return False
            
        # 连接设备
        self.device_connected = self.connect_device()
        self.initialized = True
            
        return True
    
    def check_configuration(self):
        """检查配置"""
        # 检查SDK路径
        if not os.path.exists(self.sdk_path):
            self.last_error = f"SDK路径不存在: {self.sdk_path}"
            print(f"❌ {self.last_error}")
            return False
        print(f"✅ SDK路径存在: {self.sdk_path}")
        
        # 检查DLL文件
        dll_name = INFRARED_CONFIG["dll_name"]
        self.dll_path = os.path.join(self.sdk_path, dll_name)
        
        if not os.path.exists(self.dll_path):
            self.last_error = f"DLL文件不存在: {self.dll_path}"
            print(f"❌ {self.last_error}")
            return False
        print(f"✅ DLL文件存在: {self.dll_path}")
        
        return True
    
    @handle_device_error
    def load_sdk(self):
        """加载Connect SDK DLL"""
        # 加载DLL
        self.dll = ctypes.cdll.LoadLibrary(self.dll_path)
        print(f"✅ 成功加载DLL: {self.dll_path}")
        
        # 定义Connect SDK函数原型
        try:
            # 初始化函数
            self.dll.InitImagerIPC.argtypes = [ctypes.c_ushort]
            self.dll.InitImagerIPC.restype = ctypes.c_long
            
            # 启动函数
            self.dll.StartImagerIPC.argtypes = [ctypes.c_ushort]
            self.dll.StartImagerIPC.restype = ctypes.c_long
            
            # 释放函数
            self.dll.ReleaseImagerIPC.argtypes = [ctypes.c_ushort]
            self.dll.ReleaseImagerIPC.restype = ctypes.c_long
            
            # 获取帧配置函数
            self.dll.GetFrameConfig.argtypes = [
                ctypes.c_ushort,
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int)
            ]
            self.dll.GetFrameConfig.restype = ctypes.c_long
            
            # 获取帧数据函数
            self.dll.GetFrame.argtypes = [
                ctypes.c_ushort,
                ctypes.c_ushort,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p
            ]
            self.dll.GetFrame.restype = ctypes.c_long
            
            print("✅ Connect SDK函数原型定义成功")
            return True
                
        except Exception as e:
            self.last_error = f"Connect SDK函数定义失败: {e}"
            print(f"❌ {self.last_error}")
            return False
    
    @handle_device_error
    def connect_device(self):
        """连接设备"""
        if not self.dll:
            self.last_error = "SDK未加载"
            print(f"❌ {self.last_error}")
            return False
        
        # 初始化IPC连接
        print(f"ℹ️ 正在初始化IPC连接，设备索引: {self.device_index}")
        result = self.dll.InitImagerIPC(self.device_index)
        
        # HRESULT成功值通常是0
        if result == 0:
            # 启动IPC
            start_result = self.dll.StartImagerIPC(self.device_index)
            if start_result == 0:
                self.last_error = ""
                print("✅ Connect SDK连接成功")
                
                # 获取图像配置确认连接
                width = ctypes.c_int()
                height = ctypes.c_int()
                depth = ctypes.c_int()
                config_result = self.dll.GetFrameConfig(
                    self.device_index,
                    ctypes.byref(width),
                    ctypes.byref(height),
                    ctypes.byref(depth)
                )
                
                if config_result == 0:
                    self.width = width.value
                    self.height = height.value
                    self.frame_size = self.width * self.height
                    print(f"ℹ️ 实际图像配置: {self.width}x{self.height}, 深度: {depth.value}")
                else:
                    print(f"⚠️ 无法获取图像配置，错误代码: {config_result:08X}")
                    print("⚠️ 设备连接成功但数据流可能未准备好，将使用默认配置")
                    print(f"ℹ️ 使用默认配置: {self.width}x{self.height}")
                
                return True
            else:
                self.last_error = f"启动IPC失败，错误代码: 0x{start_result:08X}"
                print(f"❌ {self.last_error}")
                return False
        else:
            self.last_error = f"IPC初始化失败，错误代码: {result:08X}"
            print(f"❌ Connect SDK初始化失败，错误代码: 0x{result:08X}")
            
            # 解释常见错误代码
            if result == 0x80004005:
                print("⚠️ 可能原因: PIX Connect软件未运行，或设备未连接")
            elif result == 0x80070006:
                print("⚠️ 可能原因: 无效的设备句柄")
            else:
                print("⚠️ 请检查PIX Connect软件是否正在运行")
            
            return False
    
    @handle_device_error
    def get_temperature_data(self):
        """获取温度数据"""
        if not self.device_connected or not self.dll:
            return None
        
        # 创建图像数据缓冲区
        buffer_size = self.frame_size * 2  # 假设16位数据
        image_buffer = (ctypes.c_ubyte * buffer_size)()
        
        # 创建元数据缓冲区
        metadata_buffer = (ctypes.c_ubyte * 64)()
        
        # 获取热图数据
        timeout_ms = INFRARED_CONFIG["data_timeout"]
        result = self.dll.GetFrame(
            self.device_index,
            timeout_ms,
            ctypes.cast(image_buffer, ctypes.c_void_p),
            buffer_size,
            ctypes.cast(metadata_buffer, ctypes.c_void_p)
        )
        
        if result == 0:
            # 转换为numpy数组
            temp_array = np.frombuffer(image_buffer, dtype=np.uint16)
            
            if len(temp_array) >= self.frame_size:
                temp_array = temp_array[:self.frame_size].reshape((self.height, self.width))
                
                # 转换为实际温度值
                temp_celsius = temp_array.astype(np.float32) / 100.0
                
                # 应用全局温度补偿偏移量
                temperature_offset = INFRARED_CONFIG["temperature_offset"]
                if temperature_offset != 0.0:
                    temp_celsius = temp_celsius + temperature_offset
                
                # 应用温度梯度补偿
                temp_celsius = self.apply_gradient_compensation(temp_celsius)
                
                # 更新帧率统计
                self.update_fps_statistics()
                
                return temp_celsius
                
            else:
                print(f"⚠️ 数据长度不足: {len(temp_array)} < {self.frame_size}")
                return None
        else:
            # 减少错误日志输出频率
            if hasattr(self, '_last_error_time'):
                if time.time() - self._last_error_time < 1.0:
                    return None
            self._last_error_time = time.time()
            
            print(f"⚠️ 获取温度数据失败，错误代码: 0x{result:08X}")
            return None
    
    def apply_gradient_compensation(self, temp_data):
        """应用温度梯度补偿"""
        if not INFRARED_CONFIG["gradient_compensation"]["enabled"]:
            return temp_data
            
        comp_config = INFRARED_CONFIG["gradient_compensation"]
        vertical_gradient = comp_config["vertical_gradient"]
        horizontal_gradient = comp_config["horizontal_gradient"]
        strength = comp_config["compensation_strength"]
        
        # 创建坐标网格
        y, x = np.mgrid[0:self.height, 0:self.width]
        
        # 计算中心点
        center_y = self.height / 2
        center_x = self.width / 2
        
        # 计算补偿值
        vertical_comp = (y - center_y) * vertical_gradient
        horizontal_comp = (x - center_x) * horizontal_gradient
        
        # 应用补偿
        compensated = temp_data + (vertical_comp + horizontal_comp) * strength
        
        return compensated
    
    def generate_thermal_image(self, display_width=300, display_height=180,
                             colormap=cv2.COLORMAP_JET):
        """生成热图图像"""
        temp_data = self.get_temperature_data()
        if temp_data is None:
            temp_data = self.generate_mock_temperature_data()
        
        if temp_data is None or temp_data.size == 0:
            print("⚠️ 温度数据无效，无法生成热力图")
            return None, None, None
        
        # 应用温度补偿
        compensated_temp = self.apply_gradient_compensation(temp_data)
        compensated_temp += INFRARED_CONFIG["temperature_offset"]
        
        # 动态调整温度范围
        actual_min = np.percentile(compensated_temp, 5)
        actual_max = np.percentile(compensated_temp, 95)
        
        # 确保有合理的温度范围
        if actual_max - actual_min < 1.0:
            actual_min = compensated_temp.min()
            actual_max = compensated_temp.max()
            if actual_max - actual_min < 0.5:
                actual_min -= 0.5
                actual_max += 0.5
        
        # 归一化温度数据
        temp_normalized = np.clip(
            (compensated_temp - actual_min) / (actual_max - actual_min) * 255,
            0, 255
        ).astype(np.uint8)
        
        # 应用伪彩色映射
        thermal_image = cv2.applyColorMap(temp_normalized, colormap)
        
        # 调整显示尺寸
        if thermal_image.shape[:2] != (display_height, display_width):
            main_image_width = display_width - 50
            thermal_image = cv2.resize(thermal_image, (main_image_width, display_height),
                                     interpolation=cv2.INTER_CUBIC)
        
        # 添加颜色条图例
        thermal_image = self.add_colorbar(thermal_image, actual_min, actual_max)
        
        return thermal_image, compensated_temp, (actual_min, actual_max)
    
    def add_colorbar(self, image, min_temp, max_temp):
        """为热图添加颜色条"""
        # 创建颜色条
        colorbar = create_colorbar(image.shape[0], min_temp, max_temp)
        
        # 将颜色条添加到图像右侧
        result = np.zeros((image.shape[0], image.shape[1] + colorbar.shape[1], 3),
                         dtype=np.uint8)
        result[:, :image.shape[1]] = image
        result[:, image.shape[1]:] = colorbar
        
        return result
    
    def generate_mock_temperature_data(self):
        """生成模拟温度数据（用于测试）"""
        # 创建基础温度场
        y, x = np.ogrid[:self.height, :self.width]
        center_x, center_y = self.width // 2, self.height // 2
        base_temp = 30.0
        
        temp_data = np.full((self.height, self.width), base_temp, dtype=np.float32)
        
        # 添加动态效果
        time_factor = time.time() * 0.5
        
        # 添加热点
        distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        hot_spot = 12.0 * np.exp(-distance / 50) * (0.8 + 0.2 * np.sin(time_factor))
        temp_data += hot_spot
        
        # 添加随机噪声
        temp_data += np.random.normal(0, 0.3, temp_data.shape)
        
        return temp_data
    
    def check_status(self):
        """
        检查设备状态
        
        Returns:
            bool: 设备是否正常工作
        """
        if not self.device_connected or not self.initialized:
            return False
            
        # 尝试获取一帧数据来验证设备是否正常工作
        try:
            data = self.get_temperature_data()
            return data is not None
        except:
            return False

    def __del__(self):
        """清理资源"""
        if self.dll and self.device_connected:
            try:
                self.dll.ReleaseImagerIPC(self.device_index)
                print("✅ 已释放红外热像仪资源")
            except:
                pass