import sys
import os

# 强制实时输出，解决终端缓冲问题
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
os.environ['PYTHONUNBUFFERED'] = '1'

# 添加 slm_monitor 到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sls_monitor.main import main

if __name__ == "__main__":
    main()
    # OpenCV 可能未安装; 做一个优雅降级
    