"""
统一日志管理系统 - 修复递归问题版本
"""
import os
import time
import datetime
import threading
from typing import Optional, List
import sys
from io import StringIO

class DebugLogger:
    """调试日志管理器"""
    
    def __init__(self, base_dir: str = None):
        """初始化日志管理器"""
        self.base_dir = base_dir or os.path.join(os.getcwd(), "output")
        self.log_dir = os.path.join(self.base_dir, "logs")
        
        # 确保日志目录存在
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建会话日志文件
        self.session_start = datetime.datetime.now()
        session_filename = self.session_start.strftime("debug_%Y%m%d_%H%M%S.log")
        self.log_file_path = os.path.join(self.log_dir, session_filename)
        
        # 日志缓冲区
        self.log_buffer: List[str] = []
        self.buffer_lock = threading.Lock()
        
        # 原始stdout/stderr备份
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # 是否启用实时写入
        self.real_time_logging = True
        
        # 初始化日志文件
        self._init_log_file()
        
        # 使用原始stdout输出初始化信息，避免递归
        sys.__stdout__.write(f"🗂️ 日志系统已启动，日志文件: {self.log_file_path}\n")
        sys.__stdout__.flush()
        
        # 日志缓冲区
        self.log_buffer: List[str] = []
        self.buffer_lock = threading.Lock()
        
        # 原始stdout/stderr备份
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # 是否启用实时写入
        self.real_time_logging = True
        
        # 初始化日志文件
        self._init_log_file()
        
        print(f"🗂️ 日志系统已启动，日志文件: {self.log_file_path}")
    
    def _init_log_file(self):
        """初始化日志文件"""
        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write(f"=== SLS 监控系统调试日志 ===\n")
                f.write(f"会话开始时间: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"日志文件: {self.log_file_path}\n")
                f.write("=" * 50 + "\n\n")
        except Exception as e:
            sys.__stderr__.write(f"❌ 初始化日志文件失败: {e}\n")
    
    def log(self, message: str, level: str = "INFO", component: str = "SYSTEM"):
        """记录日志消息"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]  # 精确到毫秒
        formatted_message = f"[{timestamp}] [{level}] [{component}] {message}"
        
        # 添加到缓冲区
        with self.buffer_lock:
            self.log_buffer.append(formatted_message)
        
        # 实时写入文件（如果启用）
        if self.real_time_logging:
            self._write_to_file(formatted_message)
        
        # 同时输出到控制台（使用原始stdout避免递归）
        try:
            sys.__stdout__.write(formatted_message + "\n")
            sys.__stdout__.flush()
        except Exception:
            # 如果输出失败，静默处理
            pass
    
    def _write_to_file(self, message: str):
        """写入日志文件"""
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(message + "\n")
                f.flush()  # 立即刷新到磁盘
        except Exception:
            # 静默处理写入错误，避免递归
            pass
    
    def flush_all_logs(self):
        """将缓冲区中的所有日志写入文件"""
        if not self.real_time_logging:
            try:
                with open(self.log_file_path, 'a', encoding='utf-8') as f:
                    with self.buffer_lock:
                        for message in self.log_buffer:
                            f.write(message + "\n")
                        f.flush()
                        print(f"✅ 已将 {len(self.log_buffer)} 条日志写入文件")
                        self.log_buffer.clear()
            except Exception as e:
                print(f"❌ 批量写入日志失败: {e}")
    
    def save_session_summary(self):
        """保存会话总结"""
        try:
            session_end = datetime.datetime.now()
            duration = session_end - self.session_start
            
            summary = f"""
{"=" * 50}
=== 会话总结 ===
会话结束时间: {session_end.strftime('%Y-%m-%d %H:%M:%S')}
会话总时长: {duration}
总日志条数: {len(self.log_buffer)} 条
日志文件大小: {self._get_file_size()} bytes
{"=" * 50}
"""
            
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(summary)
                f.flush()
            
            print(f"📋 会话总结已保存到: {self.log_file_path}")
            
        except Exception as e:
            print(f"❌ 保存会话总结失败: {e}")
    
    def _get_file_size(self) -> int:
        """获取日志文件大小"""
        try:
            return os.path.getsize(self.log_file_path)
        except:
            return 0
    
    def cleanup_old_logs(self, days_to_keep: int = 7):
        """清理旧日志文件"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)
            
            removed_count = 0
            for filename in os.listdir(self.log_dir):
                if filename.startswith("debug_") and filename.endswith(".log"):
                    file_path = os.path.join(self.log_dir, filename)
                    if os.path.getmtime(file_path) < cutoff_time:
                        os.remove(file_path)
                        removed_count += 1
            
            if removed_count > 0:
                print(f"🗑️ 已清理 {removed_count} 个超过 {days_to_keep} 天的旧日志文件")
                
        except Exception as e:
            print(f"❌ 清理旧日志失败: {e}")

class ConsoleCapture:
    """控制台输出捕获器"""
    
    def __init__(self, logger: DebugLogger):
        self.logger = logger
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.buffer = StringIO()
    
    def start_capture(self):
        """开始捕获控制台输出"""
        sys.stdout = self
        sys.stderr = self
        print("📹 开始捕获控制台输出到日志文件")
    
    def stop_capture(self):
        """停止捕获控制台输出"""
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        print("📹 停止捕获控制台输出")
    
    def write(self, text):
        """重写write方法，同时输出到控制台和日志"""
        # 输出到原始控制台
        self.original_stdout.write(text)
        
        # 记录到日志（去除多余的换行）
        if text.strip():
            # 检测日志级别
            level = "INFO"
            component = "CONSOLE"
            
            if "❌" in text or "ERROR" in text.upper():
                level = "ERROR"
            elif "⚠️" in text or "WARNING" in text.upper():
                level = "WARNING"
            elif "🔧" in text or "DEBUG" in text.upper():
                level = "DEBUG"
            elif "✅" in text or "SUCCESS" in text.upper():
                level = "SUCCESS"
            
            # 提取组件名称
            if "状态机" in text:
                component = "STATE_MACHINE"
            elif "振动" in text:
                component = "VIBRATION"
            elif "相机" in text:
                component = "CAMERA"
            elif "控制面板" in text:
                component = "CONTROL_PANEL"
            
            # 直接写入日志文件，避免递归调用print
            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            formatted_message = f"[{timestamp}] [{level}] [{component}] {text.strip()}"
            
            # 添加到缓冲区
            with self.logger.buffer_lock:
                self.logger.log_buffer.append(formatted_message)
            
            # 直接写入文件
            if self.logger.real_time_logging:
                try:
                    with open(self.logger.log_file_path, 'a', encoding='utf-8') as f:
                        f.write(formatted_message + "\n")
                        f.flush()
                except Exception:
                    # 如果写入失败，不要输出错误信息，避免递归
                    pass
    
    def flush(self):
        """刷新缓冲区"""
        self.original_stdout.flush()

# 全局日志实例
_global_logger: Optional[DebugLogger] = None
_console_capture: Optional[ConsoleCapture] = None

def init_logging(base_dir: str = None, enable_console_capture: bool = False):
    """初始化全局日志系统"""
    global _global_logger, _console_capture
    
    if _global_logger is None:
        _global_logger = DebugLogger(base_dir)
        
        # 清理旧日志
        _global_logger.cleanup_old_logs()
        
        # 暂时完全禁用控制台捕获功能，避免递归问题
        # if enable_console_capture:
        #     _console_capture = ConsoleCapture(_global_logger)
        #     _console_capture.start_capture()
        
        sys.__stdout__.write("📹 控制台捕获功能已禁用，避免递归问题\n")
    
    return _global_logger

def get_logger() -> Optional[DebugLogger]:
    """获取全局日志实例"""
    return _global_logger

def log_debug(message: str, component: str = "SYSTEM"):
    """记录调试日志"""
    if _global_logger:
        _global_logger.log(message, "DEBUG", component)

def log_info(message: str, component: str = "SYSTEM"):
    """记录信息日志"""
    if _global_logger:
        _global_logger.log(message, "INFO", component)

def log_warning(message: str, component: str = "SYSTEM"):
    """记录警告日志"""
    if _global_logger:
        _global_logger.log(message, "WARNING", component)

def log_error(message: str, component: str = "SYSTEM"):
    """记录错误日志"""
    if _global_logger:
        _global_logger.log(message, "ERROR", component)

def shutdown_logging():
    """关闭日志系统并保存所有数据"""
    global _global_logger, _console_capture
    
    if _console_capture:
        _console_capture.stop_capture()
        _console_capture = None
    
    if _global_logger:
        _global_logger.flush_all_logs()
        _global_logger.save_session_summary()
        print(f"📄 调试日志已保存到: {_global_logger.log_file_path}")
        _global_logger = None