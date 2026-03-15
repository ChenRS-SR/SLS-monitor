"""
振动传感器优化配置模块
"""

import math
import time
import statistics

class VibrationOptimizer:
    """振动传感器优化配置类"""
    
    # 多种灵敏度算法名称
    SENSITIVITY_ALGORITHMS = {
        "average": "简单平均",
        "peak": "峰值检测",
        "rms": "均方根值",
        "weighted": "加权平均",
        "displacement_based": "位移优先",
        "frequency_based": "频率优先",
        "composite": "综合优化"
    }
    
    def __init__(self, sensor):
        """初始化优化器
        
        Args:
            sensor: VibrationSensor实例
        """
        self.sensor = sensor
        
        # 优化的传感器配置参数
        self.OPTIMIZED_CONFIG = {
            # 检测周期设置 (建议值：100-500，数值越小响应越快)
            "detection_period": 100,
            
            # 截止频率设置 (建议值：10-100Hz，影响高频噪声过滤)
            "cutoff_frequency_1": 50,  # 低频截止
            "cutoff_frequency_2": 200, # 高频截止
            
            # 数据读取频率 (毫秒)
            "read_interval": 50,  # 从200ms改为50ms，提高响应速度
        }
        
        # 算法实现
        self._algorithms = {
            "average": self._algorithm_average,
            "peak": self._algorithm_peak,
            "rms": self._algorithm_rms,
            "weighted": self._algorithm_weighted,
            "displacement_based": self._algorithm_displacement,
            "frequency_based": self._algorithm_frequency,
            "composite": self._algorithm_composite
        }
        
        # 当前使用的算法
        self.current_algorithm = "composite"
    
    def optimize_sensor_settings(self):
        """优化传感器硬件设置"""
        try:
            print("开始优化振动传感器设置...")
            
            # 1. 设置检测周期
            self.sensor.writeReg(0x65, self.OPTIMIZED_CONFIG["detection_period"])
            print(f"设置检测周期: {self.OPTIMIZED_CONFIG['detection_period']}")
            
            # 2. 设置截止频率
            self.sensor.writeReg(0x63, self.OPTIMIZED_CONFIG["cutoff_frequency_1"])
            print(f"设置低频截止: {self.OPTIMIZED_CONFIG['cutoff_frequency_1']} Hz")
            
            self.sensor.writeReg(0x64, self.OPTIMIZED_CONFIG["cutoff_frequency_2"])
            print(f"设置高频截止: {self.OPTIMIZED_CONFIG['cutoff_frequency_2']} Hz")
            
            print("✅ 传感器优化设置完成")
            return True
            
        except Exception as e:
            print(f"❌ 传感器优化设置失败: {e}")
            return False
    
    def _get_sensor_data(self):
        """获取传感器数据，转换为字典格式"""
        # 直接从设备读取最新数据，而不是依赖current_data缓存
        try:
            # 直接读取寄存器数据
            vx = self.sensor.get("58") or 0.0  # 振动速度X
            vy = self.sensor.get("59") or 0.0  # 振动速度Y  
            vz = self.sensor.get("60") or 0.0  # 振动速度Z
            
            dx = self.sensor.get("65") or 0.0  # 振动位移X
            dy = self.sensor.get("66") or 0.0  # 振动位移Y
            dz = self.sensor.get("67") or 0.0  # 振动位移Z
            
            fx = self.sensor.get("68") or 0.0  # 振动频率X
            fy = self.sensor.get("69") or 0.0  # 振动频率Y
            fz = self.sensor.get("70") or 0.0  # 振动频率Z
            
            temp = self.sensor.get("64") or 0.0  # 温度
            
            # 添加调试输出，但减少频率
            if not hasattr(self, '_debug_counter'):
                self._debug_counter = 0
            self._debug_counter += 1
            
            if self._debug_counter % 20 == 0:  # 每20次输出一次
                print(f"🔧 优化器直接读取数据: 速度=({vx:.3f}, {vy:.3f}, {vz:.3f})")
            
            return {
                'velocity_x': abs(vx),
                'velocity_y': abs(vy), 
                'velocity_z': abs(vz),
                'displacement_x': abs(dx),
                'displacement_y': abs(dy),
                'displacement_z': abs(dz),
                'frequency_x': abs(fx),
                'frequency_y': abs(fy),
                'frequency_z': abs(fz),
                'temperature': temp / 100.0 if temp else 0.0
            }
        except Exception as e:
            print(f"❌ 优化器读取数据失败: {e}")
            return None
    
    def read_all_sensor_data(self):
        """读取所有传感器数据（为外部调用提供接口）"""
        try:
            return self._get_sensor_data()
        except Exception as e:
            print(f"❌ 读取传感器数据失败: {e}")
            return None
    
    def calculate_vibration_magnitude(self, data=None):
        """使用当前算法计算振动强度
        
        Args:
            data: 传感器数据字典，如果为None则自动获取
        """
        if data is None:
            data = self._get_sensor_data()
        
        if not data:
            return 0.0
            
        algorithm_func = getattr(self, f"_algorithm_{self.current_algorithm}", self._algorithm_average)
        return algorithm_func(data)    
    
    def _algorithm_average(self, data):
        """原始平均算法"""
        vx = abs(data.get('velocity_x', 0))
        vy = abs(data.get('velocity_y', 0))
        vz = abs(data.get('velocity_z', 0))
        return (vx + vy + vz) / 3
    
    def _algorithm_peak(self, data):
        """峰值算法 - 取最大振动值"""
        vx = abs(data.get('velocity_x', 0))
        vy = abs(data.get('velocity_y', 0))
        vz = abs(data.get('velocity_z', 0))
        return max(vx, vy, vz)
    
    def _algorithm_rms(self, data):
        """RMS算法 - 均方根"""
        vx = abs(data.get('velocity_x', 0))
        vy = abs(data.get('velocity_y', 0))
        vz = abs(data.get('velocity_z', 0))
        return math.sqrt((vx**2 + vy**2 + vz**2) / 3)
    
    def _algorithm_weighted(self, data):
        """加权算法 - Z轴权重更高"""
        vx = abs(data.get('velocity_x', 0))
        vy = abs(data.get('velocity_y', 0))
        vz = abs(data.get('velocity_z', 0))
        # Z轴振动通常更重要（垂直振动）
        return (vx * 0.3 + vy * 0.3 + vz * 0.4)
    
    def _algorithm_displacement(self, data):
        """基于位移的算法"""
        dx = abs(data.get('displacement_x', 0))
        dy = abs(data.get('displacement_y', 0))
        dz = abs(data.get('displacement_z', 0))
        # 位移数据通常更敏感
        displacement_magnitude = (dx + dy + dz) / 3
        
        # 结合速度数据
        velocity_magnitude = self._algorithm_average(data)
        
        # 加权组合 (位移权重更高，因为更敏感)
        return displacement_magnitude * 0.7 + velocity_magnitude * 0.3
    
    def _algorithm_frequency(self, data):
        """基于频率的算法"""
        fx = abs(data.get('frequency_x', 0))
        fy = abs(data.get('frequency_y', 0))
        fz = abs(data.get('frequency_z', 0))
        
        # 频率变化也能反映振动状态
        frequency_magnitude = (fx + fy + fz) / 3
        
        # 结合速度数据
        velocity_magnitude = self._algorithm_average(data)
        
        return velocity_magnitude * 0.8 + frequency_magnitude * 0.2
    
    def _algorithm_composite(self, data):
        """综合算法 - 最敏感"""
        # 获取各种数据
        velocity_mag = self._algorithm_rms(data)
        displacement_mag = self._algorithm_displacement(data)
        
        # 频率变化检测
        fx = abs(data.get('frequency_x', 0))
        fy = abs(data.get('frequency_y', 0))
        fz = abs(data.get('frequency_z', 0))
        frequency_change = max(fx, fy, fz)
        
        # 综合评分 (多重指标)
        composite_score = (
            velocity_mag * 0.4 +           # 速度权重40%
            displacement_mag * 0.5 +       # 位移权重50% (最敏感)
            frequency_change * 0.1         # 频率权重10%
        )
        
        return composite_score
    
    def calibrate_sensor(self, calibration_time=30):
        """传感器校准 - 计算背景噪声水平
        
        Args:
            calibration_time (int): 校准时间（秒）
            
        Returns:
            dict: 校准结果，包含噪声水平和建议阈值
        """
        print(f"开始传感器校准，请保持设备静止 {calibration_time} 秒...")
        
        # 检查设备连接状态
        if not self.sensor.isOpen:
            print("❌ 设备未连接")
            return None
            
        noise_samples = []
        sample_count = int(calibration_time * 10)  # 每100ms采样一次
        valid_samples = 0
        
        for i in range(sample_count):
            data = self._get_sensor_data()
            if data:
                magnitude = self.calculate_vibration_magnitude()
                if magnitude is not None:
                    noise_samples.append(magnitude)
                    valid_samples += 1
            
            # 显示进度
            if i % 10 == 0:
                progress = (i + 1) / sample_count * 100
                print(f"校准进度: {progress:.1f}%")
            
            time.sleep(0.1)
        
        print(f"校准完成，总样本: {len(noise_samples)}, 有效样本: {valid_samples}")
        
        if noise_samples and valid_samples > 0:
            noise_level = statistics.mean(noise_samples)
            noise_std = statistics.stdev(noise_samples) if len(noise_samples) > 1 else 0
            
            # 建议阈值 = 噪声均值 + 3倍标准差，但最小值应该大于0.001
            recommended_threshold = max(noise_level + 3 * noise_std, 0.01)
            
            return {
                'noise_level': noise_level,
                'noise_std': noise_std,
                'recommended_threshold': recommended_threshold,
                'sample_count': valid_samples
            }
        else:
            print("❌ 校准失败：未获取到有效样本")
            return None
            
    def get_status(self):
        """获取优化器状态信息"""
        return {
            "current_algorithm": self.current_algorithm,
            "algorithm_name": self.SENSITIVITY_ALGORITHMS.get(self.current_algorithm, "未知"),
            "sensor_connected": self.sensor.isOpen if hasattr(self.sensor, 'isOpen') else False,
            "config": self.OPTIMIZED_CONFIG.copy()
        }
    
    def set_algorithm(self, algorithm_name):
        """设置当前使用的算法
        
        Args:
            algorithm_name: 算法名称
        """
        if algorithm_name in self.SENSITIVITY_ALGORITHMS:
            self.current_algorithm = algorithm_name
            print(f"✅ 已切换至{self.SENSITIVITY_ALGORITHMS[algorithm_name]}算法")
            return True
        else:
            print(f"❌ 未知的算法: {algorithm_name}")
            return False
            
    def clear_cache(self):
        """清除所有缓存的传感器数据"""
        # 重置所有缓存的数据
        if hasattr(self, '_cached_data'):
            self._cached_data = {}
        if hasattr(self, '_last_readings'):
            self._last_readings = {}
        # 记录清除操作
        print("✅ 振动优化器缓存已清除")
    
    def update_config(self, new_config):
        """更新优化配置
        
        Args:
            new_config (dict): 新的配置参数
        """
        try:
            for key, value in new_config.items():
                if key in self.OPTIMIZED_CONFIG:
                    self.OPTIMIZED_CONFIG[key] = value
            print("✅ 配置已更新")
            return True
        except Exception as e:
            print(f"❌ 更新配置失败: {e}")
            return False
    
    def test_sensitivity(self, test_duration=10):
        """灵敏度测试 - 比较不同算法
        
        Args:
            test_duration (int): 测试时长（秒）
            
        Returns:
            dict: 测试结果
        """
        print(f"开始灵敏度测试 {test_duration} 秒...")
        print("请在测试期间制造一些振动...")
        
        test_results = {alg: [] for alg in self.SENSITIVITY_ALGORITHMS.keys()}
        sample_count = int(test_duration * 10)
        
        for i in range(sample_count):
            data = self._get_sensor_data()
            if data:
                for alg_name, alg_func in self.SENSITIVITY_ALGORITHMS.items():
                    magnitude = alg_func(data)
                    test_results[alg_name].append(magnitude)
            
            # 显示进度
            if i % 10 == 0:
                progress = (i + 1) / sample_count * 100
                print(f"测试进度: {progress:.1f}%")
            
            time.sleep(0.1)
        
        # 分析结果
        sensitivity_results = {}
        print("\n=== 灵敏度测试结果 ===")
        for alg_name, samples in test_results.items():
            if samples:
                mean_value = statistics.mean(samples)
                max_value = max(samples)
                std_dev = statistics.stdev(samples) if len(samples) > 1 else 0
                
                sensitivity_results[alg_name] = {
                    'mean': mean_value,
                    'max': max_value,
                    'std_dev': std_dev
                }
                
                print(f"{alg_name}:")
                print(f"  平均值: {mean_value:.4f}")
                print(f"  最大值: {max_value:.4f}")
                print(f"  标准差: {std_dev:.4f}")
        
        return sensitivity_results