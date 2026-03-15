"""
调试工具模块
"""

import cv2
import numpy as np

def debug_frame(frame, name="debug"):
    """
    调试图像帧
    
    Args:
        frame: 图像帧
        name: 调试窗口名称
    """
    if frame is None:
        print(f"[DEBUG] {name}: 帧为空")
        return False
        
    if isinstance(frame, np.ndarray):
        # 检查帧的基本属性
        print(f"[DEBUG] {name} 帧信息:")
        print(f"- 形状: {frame.shape}")
        print(f"- 类型: {frame.dtype}")
        print(f"- 值范围: {frame.min()} - {frame.max()}")
        
        # 检查是否全黑或全白
        if frame.mean() < 1:
            print(f"[DEBUG] {name}: 警告 - 帧可能全黑")
        elif frame.mean() > 254:
            print(f"[DEBUG] {name}: 警告 - 帧可能全白")
            
        return True
    else:
        print(f"[DEBUG] {name}: 帧类型错误 - {type(frame)}")
        return False