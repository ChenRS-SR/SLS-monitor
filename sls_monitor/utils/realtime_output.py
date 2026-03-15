"""
实时输出工具模块
解决Python GUI程序的终端输出缓冲问题
"""

import sys
import os
import builtins

# 保存原始的print函数
_original_print = builtins.print

def setup_realtime_output():
    """设置实时输出，防止终端缓冲"""
    # 设置环境变量强制无缓冲输出
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    # 重新配置stdout和stderr为行缓冲
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except AttributeError:
        # Python 3.6及以下版本的兼容处理
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, line_buffering=True)

def realtime_print(*args, **kwargs):
    """实时打印函数，确保立即输出到终端"""
    # 强制添加flush=True参数，使用原始的print函数避免递归
    kwargs['flush'] = True
    _original_print(*args, **kwargs)

def progress_print(message, end='\n'):
    """进度打印，带emoji和实时输出"""
    realtime_print(f"🔄 {message}", end=end)

def success_print(message):
    """成功消息打印"""
    realtime_print(f"✅ {message}")

def error_print(message):
    """错误消息打印"""
    realtime_print(f"❌ {message}")

def warning_print(message):
    """警告消息打印"""
    realtime_print(f"⚠️ {message}")

def info_print(message):
    """信息消息打印"""
    realtime_print(f"ℹ️ {message}")

def debug_print(message):
    """调试消息打印"""
    realtime_print(f"🐛 {message}")

# 自动在模块加载时设置实时输出
setup_realtime_output()

# 替换内置print函数为实时版本
builtins.print = realtime_print