"""
扑粉检测核心逻辑
实现基于振动传感器的SLM扑粉过程检测
"""

import time
import threading
from enum import Enum
from datetime import datetime
from ..config.powder_detection_config import POWDER_DETECTION_CONFIG
from ..utils.error_handler import handle_device_error

class MotionState(Enum):
    """扑粉运动状态枚举"""
    IDLE = "idle"                    # 空闲状态
    FIRST_MOTION = "first_motion"    # 第一次振动
    BETWEEN_MOTIONS = "between_motions"  # 两次振动之间
    SECOND_MOTION = "second_motion"   # 第二次振动

class PowderDetector:
    """扑粉检测器类"""
    
    def __init__(self, vibration_sensor):
        """
        初始化扑粉检测器
        
        Args:
            vibration_sensor: 振动传感器实例
        """
        self.vibration_sensor = vibration_sensor
        self.config = POWDER_DETECTION_CONFIG
        
        # 状态变量
        self.current_state = MotionState.IDLE
        self.detection_active = True
        self.last_trigger_time = 0
        self.motion_start_time = 0
        self.consecutive_low_count = 0
        
        # 事件回调
        self.on_first_motion = None
        self.on_second_motion = None
        self.on_cycle_complete = None
        
        # 统计数据
        self.detection_stats = {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'average_cycle_time': 0,
            'last_cycle_time': 0
        }
        
        # 线程控制
        self.detection_thread = None
        self.thread_running = False
        self._lock = threading.Lock()
        
        print("✅ 扑粉检测器初始化完成")
    
    def start_detection(self):
        """启动扑粉检测"""
        if self.detection_thread and self.thread_running:
            print("⚠️ 检测已在运行中")
            return
            
        self.thread_running = True
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        print("✅ 扑粉检测已启动")
    
    def stop_detection(self):
        """停止扑粉检测"""
        self.thread_running = False
        if self.detection_thread:
            self.detection_thread.join()
            self.detection_thread = None
        print("✅ 扑粉检测已停止")
    
    def _detection_loop(self):
        """检测主循环"""
        while self.thread_running:
            try:
                if not self.detection_active:
                    time.sleep(self.config["pause_delay"])
                    continue
                
                # 更新振动数据
                self.vibration_sensor.update_all_data()
                vibration_magnitude = self.vibration_sensor.calculate_vibration_magnitude()
                
                # 状态机处理
                self._handle_state_machine(vibration_magnitude)
                
                # 主循环延迟
                time.sleep(self.config["main_loop_delay"])
                
            except Exception as e:
                print(f"❌ 检测循环错误: {e}")
                time.sleep(self.config["state_reset_delay"])
    
    def _handle_state_machine(self, vibration_magnitude):
        """
        处理状态机逻辑
        
        Args:
            vibration_magnitude: 当前振动强度
        """
        current_time = time.time()
        
        # 防抖处理
        if (current_time - self.last_trigger_time) < self.config["debounce_time"]:
            return
        
        with self._lock:
            if self.current_state == MotionState.IDLE:
                self._handle_idle_state(vibration_magnitude, current_time)
                
            elif self.current_state == MotionState.FIRST_MOTION:
                self._handle_first_motion_state(vibration_magnitude, current_time)
                
            elif self.current_state == MotionState.BETWEEN_MOTIONS:
                self._handle_between_motions_state(vibration_magnitude, current_time)
                
            elif self.current_state == MotionState.SECOND_MOTION:
                self._handle_second_motion_state(vibration_magnitude, current_time)
    
    def _handle_idle_state(self, vibration_magnitude, current_time):
        """处理空闲状态"""
        if vibration_magnitude > self.config["motion_threshold"]:
            self.current_state = MotionState.FIRST_MOTION
            self.motion_start_time = current_time
            self.last_trigger_time = current_time
            
            if self.config["verbose_logging"]:
                print(f"🔄 检测到第一次振动 (强度: {vibration_magnitude:.3f})")
            
            # 触发第一次振动回调
            if self.on_first_motion:
                self.on_first_motion()
    
    def _handle_first_motion_state(self, vibration_magnitude, current_time):
        """处理第一次振动状态"""
        # 检查最小持续时间
        time_in_motion = current_time - self.motion_start_time
        
        if time_in_motion >= self.config["first_motion_min_duration"]:
            # 检查振动是否停止
            if vibration_magnitude < (self.config["motion_threshold"] * 
                                    self.config["motion_threshold_factor"]):
                self.consecutive_low_count += 1
                
                if self.consecutive_low_count >= self.config["required_consecutive_low"]:
                    self.current_state = MotionState.BETWEEN_MOTIONS
                    self.consecutive_low_count = 0
                    
                    if self.config["verbose_logging"]:
                        print("🔄 进入两次振动之间的等待状态")
            else:
                self.consecutive_low_count = 0
    
    def _handle_between_motions_state(self, vibration_magnitude, current_time):
        """处理两次振动之间的状态"""
        # 检查是否超时
        if (current_time - self.motion_start_time) > self.config["between_motions_timeout"]:
            self._reset_state()
            self.failed_cycles += 1
            print("⚠️ 等待第二次振动超时")
            return
            
        # 检查最小等待时间
        if (current_time - self.motion_start_time) < self.config["between_motions_min_wait"]:
            return
            
        # 检测第二次振动
        if vibration_magnitude > self.config["motion_threshold"]:
            self.current_state = MotionState.SECOND_MOTION
            self.last_trigger_time = current_time
            
            if self.config["verbose_logging"]:
                print(f"🔄 检测到第二次振动 (强度: {vibration_magnitude:.3f})")
            
            # 触发第二次振动回调
            if self.on_second_motion:
                self.on_second_motion()
    
    def _handle_second_motion_state(self, vibration_magnitude, current_time):
        """处理第二次振动状态"""
        # 等待振动停止
        if vibration_magnitude < (self.config["motion_threshold"] * 
                                self.config["motion_threshold_factor"]):
            self.consecutive_low_count += 1
            
            if self.consecutive_low_count >= self.config["required_consecutive_low"]:
                # 完成一个完整周期
                cycle_time = current_time - self.motion_start_time
                self._update_statistics(cycle_time)
                
                if self.on_cycle_complete:
                    self.on_cycle_complete()
                
                self._reset_state()
                
                if self.config["verbose_logging"]:
                    print(f"✅ 扑粉周期完成 (用时: {cycle_time:.1f}秒)")
        else:
            self.consecutive_low_count = 0
    
    def _reset_state(self):
        """重置状态"""
        self.current_state = MotionState.IDLE
        self.consecutive_low_count = 0
        time.sleep(self.config["state_reset_delay"])
    
    def _update_statistics(self, cycle_time):
        """更新统计数据"""
        self.detection_stats['total_cycles'] += 1
        self.detection_stats['successful_cycles'] += 1
        self.detection_stats['last_cycle_time'] = cycle_time
        
        # 更新平均周期时间
        if self.detection_stats['average_cycle_time'] == 0:
            self.detection_stats['average_cycle_time'] = cycle_time
        else:
            self.detection_stats['average_cycle_time'] = (
                0.9 * self.detection_stats['average_cycle_time'] + 0.1 * cycle_time
            )
    
    def get_statistics(self):
        """获取检测统计数据"""
        return self.detection_stats.copy()
    
    def reset_statistics(self):
        """重置统计数据"""
        self.detection_stats = {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'average_cycle_time': 0,
            'last_cycle_time': 0
        }