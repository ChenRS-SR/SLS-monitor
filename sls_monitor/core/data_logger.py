"""
数据记录模块
负责处理系统产生的各类数据的保存和记录功能
"""

import os
import csv
import json
import threading
from datetime import datetime
import numpy as np
from ..config.system_config import SYSTEM_CONFIG
from ..utils.file_utils import ensure_directory, backup_file, save_csv, save_json
from ..utils.error_handler import handle_device_error

class DataLogger:
    """数据记录器类"""
    
    def __init__(self, base_dir=None):
        """
        初始化数据记录器
        
        Args:
            base_dir: 基础数据保存目录
        """
        self.base_dir = base_dir or SYSTEM_CONFIG["data_save_path"]
        self.ensure_directories()
        
        # 当前层数
        self.current_layer = 0
        
        # 数据缓存
        self.vibration_data = []
        self.temperature_data = []
        self.powder_cycles = []
        
        # 线程锁
        self.lock = threading.Lock()
        
        print(f"✅ 数据记录器初始化完成 (保存目录: {self.base_dir})")
    
    def ensure_directories(self):
        """确保必要的目录结构存在"""
        dirs = [
            self.base_dir,
            os.path.join(self.base_dir, "images"),
            os.path.join(self.base_dir, "images", "CH1"),
            os.path.join(self.base_dir, "images", "CH2"),
            os.path.join(self.base_dir, "images", "CH3"),
            os.path.join(self.base_dir, "images", "CH3_Raw"),
            os.path.join(self.base_dir, "data"),
            os.path.join(self.base_dir, "logs")
        ]
        
        for dir_path in dirs:
            ensure_directory(dir_path)
    
    def set_layer(self, layer_num):
        """设置当前层数"""
        self.current_layer = layer_num
        print(f"ℹ️ 当前层数: {self.current_layer}")
    
    @handle_device_error
    def save_vibration_data(self, data):
        """
        保存振动数据
        
        Args:
            data: 包含振动数据的字典
        """
        with self.lock:
            self.vibration_data.append({
                'timestamp': datetime.now().isoformat(),
                'layer': self.current_layer,
                **data
            })
            
            # 定期保存到文件
            if len(self.vibration_data) >= 1000:
                self.flush_vibration_data()
    
    def flush_vibration_data(self):
        """将缓存的振动数据写入文件"""
        if not self.vibration_data:
            return
            
        with self.lock:
            filename = os.path.join(
                self.base_dir,
                "data",
                f"vibration_data_{datetime.now().strftime('%Y%m%d')}.csv"
            )
            
            headers = [
                'timestamp', 'layer',
                'velocity_x', 'velocity_y', 'velocity_z',
                'displacement_x', 'displacement_y', 'displacement_z',
                'frequency_x', 'frequency_y', 'frequency_z',
                'temperature'
            ]
            
            save_csv(self.vibration_data, filename, headers, append=True)
            self.vibration_data = []
    
    @handle_device_error
    def save_temperature_data(self, temp_data, temp_range, metadata=None):
        """
        保存温度数据
        
        Args:
            temp_data: 温度数据数组
            temp_range: 温度范围元组 (min, max)
            metadata: 额外的元数据
        """
        timestamp = datetime.now()
        base_name = f"temp_data_L{self.current_layer:04d}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # 保存NPZ格式
        npz_path = os.path.join(self.base_dir, "data", f"{base_name}.npz")
        np.savez_compressed(
            npz_path,
            temperature_data=temp_data,
            timestamp=timestamp.isoformat(),
            layer=self.current_layer,
            temp_range=temp_range,
            metadata=metadata or {}
        )
        
        # 保存CSV格式（用于Excel分析）
        csv_path = os.path.join(self.base_dir, "data", f"{base_name}.csv")
        np.savetxt(csv_path, temp_data, delimiter=',', fmt='%.2f')
        
        print(f"✅ 温度数据已保存: {base_name}")
        return base_name
    
    @handle_device_error
    def save_powder_cycle(self, cycle_data):
        """
        保存扑粉周期数据
        
        Args:
            cycle_data: 扑粉周期信息字典
        """
        self.powder_cycles.append({
            'timestamp': datetime.now().isoformat(),
            'layer': self.current_layer,
            **cycle_data
        })
        
        # 定期保存到文件
        if len(self.powder_cycles) >= 10:
            self.flush_powder_cycles()
    
    def flush_powder_cycles(self):
        """将缓存的扑粉周期数据写入文件"""
        if not self.powder_cycles:
            return
            
        with self.lock:
            filename = os.path.join(
                self.base_dir,
                "data",
                f"powder_cycles_{datetime.now().strftime('%Y%m%d')}.csv"
            )
            
            headers = [
                'timestamp', 'layer', 'cycle_time',
                'first_motion_magnitude', 'second_motion_magnitude',
                'status'
            ]
            
            save_csv(self.powder_cycles, filename, headers, append=True)
            self.powder_cycles = []
    
    @handle_device_error
    def log_event(self, event_type, message, level="INFO"):
        """
        记录事件日志
        
        Args:
            event_type: 事件类型
            message: 事件消息
            level: 日志级别
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'type': event_type,
            'message': message,
            'layer': self.current_layer
        }
        
        log_file = os.path.join(
            self.base_dir,
            "logs",
            f"events_{datetime.now().strftime('%Y%m%d')}.log"
        )
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def save_image_record(self, image_info):
        """
        保存图像记录信息
        
        Args:
            image_info: 图像信息字典
        """
        record = {
            'timestamp': datetime.now().isoformat(),
            'layer': self.current_layer,
            **image_info
        }
        
        filename = os.path.join(
            self.base_dir,
            "data",
            f"image_records_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        
        save_csv([record], filename, append=True)
    
    def create_layer_summary(self):
        """创建当前层的总结数据"""
        summary = {
            'layer': self.current_layer,
            'timestamp': datetime.now().isoformat(),
            'vibration_stats': self._calculate_vibration_stats(),
            'temperature_stats': self._calculate_temperature_stats(),
            'powder_cycle_stats': self._calculate_powder_cycle_stats()
        }
        
        filename = os.path.join(
            self.base_dir,
            "data",
            f"layer_summary_{self.current_layer:04d}.json"
        )
        
        save_json(summary, filename)
        return summary
    
    def _calculate_vibration_stats(self):
        """计算振动数据统计"""
        if not self.vibration_data:
            return {}
            
        data = np.array([
            [d['velocity_x'], d['velocity_y'], d['velocity_z']]
            for d in self.vibration_data
        ])
        
        return {
            'mean': data.mean(axis=0).tolist(),
            'max': data.max(axis=0).tolist(),
            'min': data.min(axis=0).tolist(),
            'std': data.std(axis=0).tolist()
        }
    
    def _calculate_temperature_stats(self):
        """计算温度数据统计"""
        if not self.temperature_data:
            return {}
            
        data = np.array(self.temperature_data)
        return {
            'mean': float(np.mean(data)),
            'max': float(np.max(data)),
            'min': float(np.min(data)),
            'std': float(np.std(data))
        }
    
    def _calculate_powder_cycle_stats(self):
        """计算扑粉周期统计"""
        if not self.powder_cycles:
            return {}
            
        cycle_times = [cycle['cycle_time'] for cycle in self.powder_cycles]
        return {
            'total_cycles': len(self.powder_cycles),
            'average_cycle_time': np.mean(cycle_times),
            'min_cycle_time': min(cycle_times),
            'max_cycle_time': max(cycle_times),
            'success_rate': sum(1 for c in self.powder_cycles if c['status'] == 'success') / len(self.powder_cycles)
        }
    
    def cleanup(self):
        """清理和保存所有缓存的数据"""
        self.flush_vibration_data()
        self.flush_powder_cycles()
        print("✅ 数据记录器清理完成")