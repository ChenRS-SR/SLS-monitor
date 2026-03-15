"""
错误处理装饰器
提供各种错误处理和日志记录功能
"""

import os
import logging
import functools
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

def handle_device_error(func):
    """
    设备相关错误处理装饰器
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Device error in {func.__name__}: {str(e)}"
            print(f"❌ {error_msg}")
            log_error(error_msg)
            return None
    return wrapper

def handle_image_error(func):
    """
    图像处理错误处理装饰器
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Image processing error in {func.__name__}: {str(e)}"
            print(f"❌ {error_msg}")
            log_error(error_msg)
            return None
    return wrapper

def retry_on_error(max_retries=3, delay_seconds=1):
    """
    失败重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay_seconds: 重试间隔时间（秒）
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        error_msg = f"Attempt {attempt + 1} failed: {str(e)}"
                        print(f"⚠️ {error_msg}")
                        log_error(error_msg)
                        time.sleep(delay_seconds)
                    else:
                        error_msg = f"All {max_retries} attempts failed in {func.__name__}: {str(e)}"
                        print(f"❌ {error_msg}")
                        log_error(error_msg)
                        raise
            return None
        return wrapper
    return decorator

def log_error(error_msg):
    """
    记录错误信息到文件
    
    Args:
        error_msg: 要记录的错误信息
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {error_msg}\n")
            f.write(f"Stack trace:\n{traceback.format_exc()}\n")
    except Exception as e:
        print(f"❌ Failed to log error: {e}")

def setup_logger(name, log_file, level=logging.INFO, max_size=10*1024*1024, backup_count=5):
    """
    配置日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        level: 日志级别
        max_size: 单个日志文件最大大小（默认10MB）
        backup_count: 保留的日志文件数量
    
    Returns:
        配置好的日志记录器
    """
    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 创建文件处理器（支持日志轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 配置日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def catch_and_log(logger=None):
    """
    异常捕获和日志记录装饰器
    
    Args:
        logger: 日志记录器实例（可选）
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"Exception in {func.__name__}: {str(e)}"
                if logger:
                    logger.error(error_msg, exc_info=True)
                else:
                    print(f"❌ {error_msg}")
                    log_error(error_msg)
                return None
        return wrapper
    return decorator