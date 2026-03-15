"""
振动传感器控制模块
用于控制和读取WTVB02-485振动传感器的数据
"""

import time
import threading
import random
from .device_model import DeviceModel
from .vibration_optimizer import VibrationOptimizer
from ..config.vibration_config import VIBRATION_CONFIG, VIBRATION_DETECTION_CONFIG, VIBRATION_LEVELS
from ..utils.error_handler import handle_device_error, retry_on_error

# 尝试导入日志系统，如果失败则使用占位函数
try:
    from ..utils.logger import log_debug, log_info, log_warning, log_error
except ImportError:
    # 如果导入失败，创建占位函数
    def log_debug(msg, component="VIBRATION"):
        print(f"[DEBUG] [{component}] {msg}")
    def log_info(msg, component="VIBRATION"):
        print(f"[INFO] [{component}] {msg}")
    def log_warning(msg, component="VIBRATION"):
        print(f"[WARNING] [{component}] {msg}")
    def log_error(msg, component="VIBRATION"):
        print(f"[ERROR] [{component}] {msg}")


class VibrationDevice(DeviceModel):
    """振动传感器控制类"""
    
    def __init__(self):
        """初始化振动传感器控制器"""
        super().__init__(
            deviceName="WTVB02-485",
            portName=VIBRATION_CONFIG["com_port"],
            baud=VIBRATION_CONFIG["baudrate"],
            ADDR=VIBRATION_CONFIG["address"]
        )
        
        self.lock = threading.Lock()
        self.optimizer = None  # 初始化为None，稍后再创建优化器
        
        # 当前数据
        self.current_data = {
            'velocity_x': 0.0,
            'velocity_y': 0.0,
            'velocity_z': 0.0,
            'displacement_x': 0.0,
            'displacement_y': 0.0,
            'displacement_z': 0.0,
            'frequency_x': 0.0,
            'frequency_y': 0.0,
            'frequency_z': 0.0,
            'temperature': 0.0
        }
        
        # 峰值数据
        self.peak_data = {
            'velocity_x': 0.0,
            'velocity_y': 0.0,
            'velocity_z': 0.0
        }
        
        # 振动触发检测相关
        self.last_trigger_time = 0
        self.vibration_magnitude = 0.0
        self.detection_config = VIBRATION_DETECTION_CONFIG.copy()  # 使用配置文件中的设置
        
        # 日志回调函数列表
        self.log_callbacks = []
        
        print(f"ℹ️ 初始化振动传感器 (端口: {self.serialConfig.portName}, 波特率: {self.serialConfig.baud})")
        
    @handle_device_error
    def process_data(self, length):
        """重写数据解析方法"""
        if self.statReg is not None:
            for i in range(int(length / 2)):
                value = self.TempBytes[2 * i + 3] << 8 | self.TempBytes[2 * i + 4]
                value = float(value)
                
                # 根据寄存器地址更新相应数据
                reg_addr = self.statReg + i
                
                if reg_addr in [0x3A, 0x3B, 0x3C]:  # 速度数据
                    axis = ['x', 'y', 'z'][reg_addr - 0x3A]
                    self.current_data[f'velocity_{axis}'] = abs(value)
                    self.peak_data[f'velocity_{axis}'] = max(
                        self.peak_data[f'velocity_{axis}'],
                        self.current_data[f'velocity_{axis}']
                    )
                elif reg_addr in [0x3D, 0x3E, 0x3F]:  # 位移数据
                    axis = ['x', 'y', 'z'][reg_addr - 0x3D]
                    self.current_data[f'displacement_{axis}'] = abs(value)
                elif reg_addr in [0x40, 0x41, 0x42]:  # 频率数据
                    axis = ['x', 'y', 'z'][reg_addr - 0x40]
                    self.current_data[f'frequency_{axis}'] = abs(value)
                elif reg_addr == 0x43:  # 温度数据
                    self.current_data['temperature'] = value / 100.0
                    
                # 存储到设备数据字典
                self.set(str(self.statReg), value)
                self.statReg += 1
                
            # 应用优化器处理数据
            if self.optimizer is not None:
                self.optimizer.process_data(self.current_data)
            self.TempBytes.clear()
    
    @handle_device_error
    def init_optimizer(self):
        """初始化优化器"""
        if self.optimizer is None:
            self.optimizer = VibrationOptimizer(self)
            print("🔧 振动传感器优化器已加载")
    
    def connect(self):
        """连接设备"""
        import serial
        try:
            if not self.isOpen:
                # 先检查端口是否可用
                try:
                    test_serial = serial.Serial(
                        port=self.serialConfig.portName,
                        baudrate=self.serialConfig.baud,
                        timeout=0.1
                    )
                    test_serial.close()
                except serial.SerialException as e:
                    if "PermissionError" in str(e):
                        print(f"❌ {self.deviceName} 连接失败: 端口{self.serialConfig.portName}被占用或无权限访问")
                        print("⚠️ 请检查:")
                        print("  1. 是否有其他程序正在使用该端口")
                        print("  2. 是否以管理员权限运行程序")
                        print("  3. 设备是否正确连接到该端口")
                    else:
                        print(f"❌ {self.deviceName} 连接失败: {str(e)}")
                    return False
                
                # 端口可用，尝试连接设备
                result = self.openDevice()
                if result and self.isOpen:
                    print(f"✅ 成功连接到振动传感器 {self.serialConfig.portName}")
                    return True
                else:
                    print(f"❌ 无法连接到振动传感器 {self.serialConfig.portName}")
                    return False
            return self.isOpen
            
        except Exception as e:
            print(f"❌ 振动传感器连接异常: {str(e)}")
            self.isOpen = False
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.isOpen:
            self.closeDevice()
            print("ℹ️ 已断开与振动传感器的连接")
    
    def start_monitoring(self):
        """开始监测振动数据"""
        if self.connect():
            # 确保优化器已初始化
            self.init_optimizer()
            self.startLoopRead()
            print("✅ 开始振动监测")
            return True
        return False
    
    def stop_monitoring(self):
        """停止监测振动数据"""
        try:
            if self.loop:
                self.stopLoopRead()
                time.sleep(0.2)  # 给数据接收线程一点时间完成
                print("ℹ️ 停止振动监测")
        except Exception as e:
            print(f"⚠️ 停止监测时出现警告: {str(e)}")
    
    def cleanup(self):
        """清理所有资源"""
        try:
            # 先停止数据监测
            self.stop_monitoring()
            time.sleep(0.2)  # 等待监测线程完全停止
            
            # 关闭设备前确保所有数据处理完成
            with self.lock:
                if self.isOpen:
                    self.closeDevice()
                    time.sleep(0.1)  # 给设备一点时间完成关闭操作
            
            print("✅ 振动传感器资源已清理")
        except Exception as e:
            print(f"⚠️ 资源清理时出现警告: {str(e)}")
    
    def get_velocity_data(self):
        """获取振动速度数据"""
        return (self.current_data['velocity_x'],
                self.current_data['velocity_y'],
                self.current_data['velocity_z'])
    
    def get_displacement_data(self):
        """获取振动位移数据"""
        return (self.current_data['displacement_x'],
                self.current_data['displacement_y'],
                self.current_data['displacement_z'])
    
    def get_frequency_data(self):
        """获取振动频率数据"""
        return (self.current_data['frequency_x'],
                self.current_data['frequency_y'],
                self.current_data['frequency_z'])
    
    def get_temperature(self):
        """获取温度数据"""
        return self.current_data['temperature']
    
    def get_peak_velocity(self):
        """获取峰值振动速度"""
        return (self.peak_data['velocity_x'],
                self.peak_data['velocity_y'],
                self.peak_data['velocity_z'])
    
    def reset_peak_values(self):
        """重置峰值数据"""
        with self.lock:
            # 强制重置所有峰值数据
            for key in self.peak_data:
                self.peak_data[key] = 0.0
            
            # 设置最近重置时间
            self.last_peak_reset_time = time.time()
            
            # 打印更详细的日志
            print(f"✅ 振动峰值已强制重置 (reset_id={id(self)}_{int(time.time())})")            
            # 清除缓存数据，确保不会保留旧峰值
            if hasattr(self, 'optimizer') and self.optimizer:
                self.optimizer.clear_cache()
    
    def calculate_vibration_magnitude(self):
        """计算综合振动强度"""
        if self.optimizer is None:
            self.init_optimizer()
        return self.optimizer.calculate_vibration_magnitude()
    
    def get_current_data(self):
        """获取当前所有数据"""
        return self.current_data.copy()
    
    def get_optimization_status(self):
        """获取优化器状态"""
        if self.optimizer is None:
            self.init_optimizer()
        return self.optimizer.get_status()
    
    def set_optimization_algorithm(self, algorithm):
        """设置优化算法"""
        if self.optimizer is None:
            self.init_optimizer()
        self.optimizer.set_algorithm(algorithm)
    
    def add_log_callback(self, callback):
        """添加日志回调函数"""
        if callback not in self.log_callbacks:
            self.log_callbacks.append(callback)
    
    def remove_log_callback(self, callback):
        """移除日志回调函数"""
        if callback in self.log_callbacks:
            self.log_callbacks.remove(callback)
    
    def _log_message(self, message, level="INFO"):
        """发送日志消息到所有注册的回调函数"""
        # 终端输出
        print(message)
        
        # 界面日志输出
        for callback in self.log_callbacks:
            try:
                callback(message, level)
            except Exception as e:
                print(f"⚠️ 日志回调函数执行失败: {e}")
    
    def check_vibration_trigger(self):
        """检查振动信号是否超过阈值（优化版）"""
        try:
            # 如果设备未连接，返回调试模式的数据
            if not self.isOpen:
                return self._debug_mode_trigger()
            
            # 使用优化器读取所有传感器数据
            if self.optimizer:
                sensor_data = self.optimizer.read_all_sensor_data()
                if sensor_data:
                    # 更新当前振动值（保持兼容性）
                    self.current_data.update(sensor_data)
                    
                    # 使用优化的算法计算振动强度
                    self.vibration_magnitude = self.optimizer.calculate_vibration_magnitude(sensor_data)
                    
                    # 强制输出调试信息确认数据更新
                    #log_debug(f"[触发检查] 优化器更新vibration_magnitude: {self.vibration_magnitude:.3f}", "VIBRATION")
                    #print(f"🔧 [触发检查] 优化器更新vibration_magnitude: {self.vibration_magnitude:.3f}")
                    
                    # 减少调试信息频率
                    if not hasattr(self, '_debug_calc_counter'):
                        self._debug_calc_counter = 0
                    self._debug_calc_counter += 1
                    
                    if self._debug_calc_counter % 50 == 0:  # 每50次输出一次
                        print(f"🔧 优化器计算振动强度: {self.vibration_magnitude:.3f} (第{self._debug_calc_counter}次)")
                    
                    # 可选的详细信息显示（调试用）
                    if self.detection_config["verbose_logging"]:
                        displacement_mag = (abs(sensor_data.get('displacement_x', 0)) + 
                                          abs(sensor_data.get('displacement_y', 0)) + 
                                          abs(sensor_data.get('displacement_z', 0))) / 3
                        frequency_mag = (abs(sensor_data.get('frequency_x', 0)) + 
                                       abs(sensor_data.get('frequency_y', 0)) + 
                                       abs(sensor_data.get('frequency_z', 0))) / 3
                        # 只在非常详细的模式下输出
                        # self._log_message(f"振动详情 - 速度:{self.vibration_magnitude:.4f}, 位移:{displacement_mag:.4f}, 频率:{frequency_mag:.4f}", "DEBUG")
                else:
                    # 如果优化器失败，回退到原始方法
                    print(f"⚠️ 优化器读取失败，使用fallback方法")
                    return self._fallback_trigger_check()
            else:
                # 如果没有优化器，使用原始方法
                print(f"⚠️ 没有优化器，使用fallback方法")
                return self._fallback_trigger_check()
            
            # 更新峰值(检查是否在重置保护期内)
            current_time = time.time()
            # 如果最近重置过峰值，且在保护期内，则不更新峰值
            if hasattr(self, 'last_peak_reset_time') and (current_time - self.last_peak_reset_time) < 10.0:
                # 在重置后直10秒内不更新峰值，确保重置操作有效
                pass
            else:
                # 正常更新峰值
                self.peak_data['velocity_x'] = max(self.peak_data['velocity_x'], 
                                                abs(self.current_data.get('velocity_x', 0)))
                self.peak_data['velocity_y'] = max(self.peak_data['velocity_y'], 
                                                abs(self.current_data.get('velocity_y', 0)))
                self.peak_data['velocity_z'] = max(self.peak_data['velocity_z'], 
                                                abs(self.current_data.get('velocity_z', 0)))
            
            current_time = time.time()
            
            # 使用配置中的阈值和防抖时间
            motion_threshold = self.detection_config["motion_threshold"]
            debounce_time = self.detection_config["debounce_time"]
            
            # 强制输出阈值对比调试信息
            #log_debug(f"[触发检查] 阈值对比: self.threshold={self.threshold:.3f}, motion_threshold={motion_threshold:.3f}, magnitude={self.vibration_magnitude:.3f}", "VIBRATION")
            #print(f"🔧 [触发检查] 阈值对比: self.threshold={self.threshold:.3f}, motion_threshold={motion_threshold:.3f}, magnitude={self.vibration_magnitude:.3f}")
            
            # 额外的噪声过滤
            if self.detection_config["noise_filter_enabled"]:
                min_signal = self.detection_config["min_signal_strength"]
                if self.vibration_magnitude < min_signal:
                    return False, self.vibration_magnitude
            
            # 检测频率限制
            if self.detection_config["max_detection_rate"] > 0:
                min_interval = 1.0 / self.detection_config["max_detection_rate"]
                if (current_time - self.last_trigger_time) < min_interval:
                    return False, self.vibration_magnitude
            
            # 检查是否超过阈值且有足够的防抖时间
            if not hasattr(self, '_trigger_check_counter'):
                self._trigger_check_counter = 0
            self._trigger_check_counter += 1
            
            # 减少调试输出频率，只在重要时刻输出
            should_debug = (self._trigger_check_counter % 100 == 0 or  # 每100次
                          self.vibration_magnitude > motion_threshold or  # 超过阈值时
                          (current_time - self.last_trigger_time) < debounce_time * 2)  # 防抖期间
            
            if should_debug:
                pass
                #print(f"🔍 触发检查: magnitude={self.vibration_magnitude:.3f}, threshold={motion_threshold:.3f}, time_diff={current_time - self.last_trigger_time:.2f}, debounce={debounce_time}")
            
            if (self.vibration_magnitude > motion_threshold and 
                (current_time - self.last_trigger_time) > debounce_time):
                self.last_trigger_time = current_time
                
                # 输出振动触发信息（强制输出用于调试）
                trigger_msg = f"🔥 振动触发！强度: {self.vibration_magnitude:.3f}, 阈值: {motion_threshold}"
                self._log_message(trigger_msg, "WARNING")
                print(trigger_msg)  # 同时输出到控制台
                
                # 只在详细日志模式下输出额外信息
                if self.detection_config["verbose_logging"]:
                    detail_msg = f"🔥 振动触发详细信息！强度: {self.vibration_magnitude:.3f}"
                    self._log_message(detail_msg, "INFO")
                    
                    # 输出传感器详细数据
                    if sensor_data:
                        displacement_mag = (abs(sensor_data.get('displacement_x', 0)) + 
                                          abs(sensor_data.get('displacement_y', 0)) + 
                                          abs(sensor_data.get('displacement_z', 0))) / 3
                        frequency_mag = (abs(sensor_data.get('frequency_x', 0)) + 
                                       abs(sensor_data.get('frequency_y', 0)) + 
                                       abs(sensor_data.get('frequency_z', 0))) / 3
                        detail_data_msg = f"   📊 数据详情 - 位移:{displacement_mag:.4f}, 频率:{frequency_mag:.4f}"
                        self._log_message(detail_data_msg, "DEBUG")
                
                return True, self.vibration_magnitude
            
            return False, self.vibration_magnitude
            
        except Exception as e:
            # 减少错误输出频率
            if not hasattr(self, '_error_count'):
                self._error_count = 0
            self._error_count += 1
            
            # 只在每100次错误时输出一次，包含详细的错误信息
            if self._error_count % 100 == 0:
                import traceback
                error_msg = f"振动检测错误（累计{self._error_count}次）: {e}"
                self._log_message(error_msg, "ERROR")
                self._log_message(f"错误详情: {traceback.format_exc()}", "ERROR")
            return False, 0
    
    def _debug_mode_trigger(self):
        """调试模式的振动触发"""
        # 每10秒左右模拟一次振动触发（用于测试状态机）
        if not hasattr(self, '_debug_trigger_time'):
            self._debug_trigger_time = time.time()
        
        current_time = time.time()
        time_since_last = current_time - self._debug_trigger_time
        
        if time_since_last > 10:  # 每10秒触发一次
            self._debug_trigger_time = current_time
            self.vibration_magnitude = 0.08  # 超过阈值0.05
            self._log_message("🧪 调试模式：模拟振动触发", "INFO")
            return True, self.vibration_magnitude
        else:
            self.vibration_magnitude = random.uniform(0.001, 0.04)  # 低于阈值的随机值
            return False, self.vibration_magnitude
    
    def _fallback_trigger_check(self):
        """备用振动检测方法"""
        try:
            # 读取振动速度数据 (x, y, z 轴)
            vx = self.get(str(58))  # 0x3A 振动速度x
            vy = self.get(str(59))  # 0x3B 振动速度y
            vz = self.get(str(60))  # 0x3C 振动速度z
            
            # 检查数据有效性
            if vx is None or vy is None or vz is None:
                # 数据无效，使用默认值
                self.current_data['velocity_x'] = 0.0
                self.current_data['velocity_y'] = 0.0
                self.current_data['velocity_z'] = 0.0
            else:
                # 更新当前振动值
                self.current_data['velocity_x'] = abs(vx)
                self.current_data['velocity_y'] = abs(vy)
                self.current_data['velocity_z'] = abs(vz)
                
            # 计算综合振动强度（简单平均）
            self.vibration_magnitude = (self.current_data['velocity_x'] + 
                                       self.current_data['velocity_y'] + 
                                       self.current_data['velocity_z']) / 3
            
            print(f"🔧 fallback计算振动强度: {self.vibration_magnitude:.3f}")
            
            # 检查是否超过阈值（修复：原来这里始终返回False）
            import time
            current_time = time.time()
            motion_threshold = self.detection_config["motion_threshold"]
            debounce_time = self.detection_config["debounce_time"]
            
            if (self.vibration_magnitude > motion_threshold and 
                (current_time - self.last_trigger_time) > debounce_time):
                self.last_trigger_time = current_time
                print(f"🔥 fallback触发！强度: {self.vibration_magnitude:.3f}, 阈值: {motion_threshold}")
                return True, self.vibration_magnitude
            
            return False, self.vibration_magnitude
            
        except Exception as e:
            self._log_message(f"备用振动检测失败: {e}", "ERROR")
            return False, 0
    
    def update_detection_config(self, new_config):
        """更新检测配置"""
        try:
            for key, value in new_config.items():
                if key in self.detection_config:
                    self.detection_config[key] = value
            self._log_message("✅ 振动检测配置已更新", "INFO")
            return True
        except Exception as e:
            self._log_message(f"❌ 更新检测配置失败: {e}", "ERROR")
            return False
    
    def get_detection_config(self):
        """获取当前检测配置"""
        return self.detection_config.copy()
    
    def get_vibration_level(self, magnitude=None):
        """获取振动级别描述"""
        if magnitude is None:
            magnitude = self.vibration_magnitude
        
        for level_name, level_info in reversed(list(VIBRATION_LEVELS.items())):
            if magnitude >= level_info["threshold"]:
                return {
                    "level": level_name,
                    "color": level_info["color"],
                    "description": level_info["description"],
                    "threshold": level_info["threshold"]
                }
        
        # 如果都不满足，返回最低级别
        return {
            "level": "minimal",
            "color": "gray",
            "description": "几乎无振动",
            "threshold": 0.0
        }
    
    def get_vibration_status(self):
        """获取当前振动状态"""
        level_info = self.get_vibration_level()
        return {
            "magnitude": self.vibration_magnitude,
            "level_info": level_info,
            "current_data": self.current_data.copy(),
            "peak_data": self.peak_data.copy(),
            "connected": self.isOpen,
            "last_trigger_time": self.last_trigger_time,
            "config": self.detection_config.copy()
        }
    
    def __del__(self):
        """清理资源"""
        self.cleanup()
        
    def disconnect(self):
        self.close()    
        
    def close(self):
        """关闭传感器连接"""
        self.cleanup()