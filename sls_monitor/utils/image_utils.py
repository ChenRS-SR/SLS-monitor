"""
图像处理工具函数
提供各种图像处理和分析功能
"""

import cv2
import numpy as np

def resize_image_keep_aspect(image, target_width, target_height, fill_color=(0, 0, 0)):
    """
    调整图像大小并保持长宽比，用指定颜色填充空白区域
    
    Args:
        image: OpenCV图像（BGR格式）
        target_width: 目标宽度
        target_height: 目标高度
        fill_color: 填充颜色（B, G, R）
    
    Returns:
        调整后的图像
    """
    h, w = image.shape[:2]
    
    # Calculate scale ratio
    scale = min(target_width / w, target_height / h)
    
    # Calculate new dimensions
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Resize image
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    
    # Create target size canvas
    canvas = np.full((target_height, target_width, 3), fill_color, dtype=np.uint8)
    
    # Calculate center position
    y_offset = (target_height - new_h) // 2
    x_offset = (target_width - new_w) // 2
    
    # Put resized image in center of canvas
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
    
    return canvas

def apply_text_overlay(image, text, position, font_scale=0.5, thickness=1,
                      font=cv2.FONT_HERSHEY_SIMPLEX, color=(255, 255, 255),
                      background_color=(0, 0, 0)):
    """
    在图像上添加带背景的文本叠加层
    
    Args:
        image: OpenCV图像
        text: 要添加的文本
        position: 文本位置（x, y）
        font_scale: 字体缩放因子
        thickness: 线条粗细
        font: OpenCV字体
        color: 文本颜色（B, G, R）
        background_color: 背景颜色（B, G, R）
    
    Returns:
        添加文本后的图像
    """
    # Get text size
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    
    # Calculate background rectangle
    padding = 2
    background_pt1 = (position[0], position[1] - text_height - padding)
    background_pt2 = (position[0] + text_width,
                     position[1] )
    
    # Draw background rectangle
    cv2.rectangle(image, background_pt1, background_pt2, background_color, -1)
    
    # Draw text
    cv2.putText(image, text, position, font, font_scale, color, thickness)
    
    return image

def create_colorbar(height, min_val, max_val, colormap=cv2.COLORMAP_JET, width=25):
    """
    创建垂直色带
    
    Args:
        height: 色带高度
        min_val: 最小值
        max_val: 最大值
        colormap: OpenCV颜色映射表
        width: 色带宽度
    
    Returns:
        带刻度的色带图像
    """
    # Create gradient
    gradient = np.linspace(0, 255, height)
    gradient = np.expand_dims(gradient, axis=1)
    gradient = np.tile(gradient, (1, width))
    gradient = gradient.astype(np.uint8)
    
    # Apply colormap
    colorbar = cv2.applyColorMap(gradient, colormap)
    
    # 增加距离和更宽的刻度区域
    gap = 8  # 与图像的距离
    scale_width = 50  # 刻度区域宽度
    total_width = width + gap + scale_width
    bar_with_scale = np.zeros((height, total_width, 3), dtype=np.uint8)
    
    # 放置色带，留出距离
    bar_with_scale[:, :width] = colorbar
    
    # 计算刻度位置（多个刻度）
    num_ticks = 6  # 刻度数量（包括上下两端）
    tick_positions = np.linspace(0, height-1, num_ticks).astype(int)
    tick_values = np.linspace(max_val, min_val, num_ticks)  # 从上到下（高温到低温）
    
    # 添加刻度标签
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.3  # 减小字体
    thickness = 1
    text_color = (255, 255, 255)
    
    for i, (pos, val) in enumerate(zip(tick_positions, tick_values)):
        # 绘制刻度线
        tick_start = width + 2
        tick_end = width + 6
        cv2.line(bar_with_scale, (tick_start, pos), (tick_end, pos), text_color, 1)
        
        # 添加数值标签（去掉小数点和°符号）
        temp_text = f"{int(val)}C"
        text_x = width + gap + 2
        text_y = pos + 4  # 微调文本位置
        
        cv2.putText(bar_with_scale, temp_text, (text_x, text_y), 
                   font, font_scale, text_color, thickness)
    
    return bar_with_scale