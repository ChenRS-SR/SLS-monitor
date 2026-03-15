"""
三摄像头图像对齐 - 技术原理详解
====================================

本文档详细解释标定逻辑、变换矩阵的含义以及 cv2.warpPerspective 函数的工作原理。
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt

class CalibrationExplainer:
    """标定原理解释器"""
    
    def __init__(self):
        print("三摄像头图像对齐技术原理解释")
        print("=" * 50)
    
    def explain_perspective_transform(self):
        """解释透视变换的基本原理"""
        
        print("\n1. 透视变换基本原理")
        print("-" * 30)
        
        print("""
透视变换（Perspective Transformation）是一种几何变换，可以将图像从一个视角
映射到另一个视角。它模拟了3D世界中物体在不同视角下的投影关系。

核心思想：
- 在源图像中定义4个点（通常是矩形的四个角）
- 在目标图像中定义对应的4个点
- 计算一个3×3的变换矩阵，使得源点精确映射到目标点
- 通过这个矩阵可以变换整个图像

数学原理：
对于任意点 (x, y)，透视变换的公式为：

    x' = (a11*x + a12*y + a13) / (a31*x + a32*y + a33)
    y' = (a21*x + a22*y + a23) / (a31*x + a32*y + a33)

其中矩阵 M = [[a11, a12, a13],
             [a21, a22, a23],
             [a31, a32, a33]]

就是我们说的变换矩阵。
        """)
    
    def explain_calibration_logic(self):
        """解释标定逻辑"""
        
        print("\n2. 标定逻辑详解")
        print("-" * 30)
        
        print("""
我们的三摄像头对齐系统使用以下标定逻辑：

步骤1: 定义目标空间
- 我们希望所有摄像头的图像都对齐到 800×600 的标准尺寸
- 目标点固定为图像的四个角：
  * 左上: (0, 0)
  * 右上: (799, 0)  
  * 右下: (799, 599)
  * 左下: (0, 599)

步骤2: 标定源空间
- 对每个摄像头，我们在其图像中选择4个标定点
- 这4个点应该对应现实世界中的同一个矩形区域
- 比如工作台的四个角，或者预先放置的标定板

步骤3: 建立映射关系
- 将每个摄像头的4个源点映射到目标空间的4个角点
- 计算透视变换矩阵
- 这个矩阵描述了如何将任意源图像点变换到目标位置

步骤4: 应用变换
- 使用计算得到的矩阵对整个图像进行透视变换
- 结果是所有摄像头的图像都"看向"同一个区域，且尺寸统一
        """)
    
    def explain_transformation_matrix(self):
        """解释变换矩阵的含义"""
        
        print("\n3. 变换矩阵详解")
        print("-" * 30)
        
        print("""
变换矩阵 (transformation_matrices) 包含什么？

这是一个 3×3 的齐次坐标变换矩阵：

    M = [[m00, m01, m02],
         [m10, m11, m12], 
         [m20, m21, m22]]

每个元素的物理意义：
- m00, m11: 缩放因子（x方向和y方向）
- m01, m10: 剪切/旋转分量
- m02, m12: 平移分量（x方向和y方向）
- m20, m21: 透视变换参数（产生透视效果）
- m22: 通常归一化为1

特点：
1. 非线性变换：由于m20和m21的存在，远近物体的缩放比例不同
2. 保持直线：直线在变换后仍然是直线
3. 不保持平行线：平行线可能在无穷远处相交
4. 可以纠正因摄像头角度、距离不同造成的视角差异
        """)
    
    def explain_warp_perspective(self):
        """解释 cv2.warpPerspective 函数"""
        
        print("\n4. cv2.warpPerspective 函数详解")
        print("-" * 40)
        
        print("""
cv2.warpPerspective(src, M, dsize, flags, borderMode, borderValue)

参数说明：
- src: 源图像（输入图像）
- M: 3×3 透视变换矩阵
- dsize: 输出图像尺寸 (width, height)
- flags: 插值方法（默认 cv2.INTER_LINEAR）
- borderMode: 边界处理方式
- borderValue: 边界填充值

工作流程：
1. 对于输出图像的每一个像素位置 (x', y')
2. 使用变换矩阵的逆矩阵计算对应的源图像位置 (x, y)
3. 在源图像中采样该位置的像素值（可能需要插值）
4. 将采样值赋给输出图像的 (x', y') 位置

关键特性：
- 逆向映射：从目标图像反推源图像位置
- 插值处理：当映射位置不是整数时进行插值
- 边界处理：源图像范围外的区域如何填充
        """)
    
    def demonstrate_with_example(self):
        """用具体例子演示"""
        
        print("\n5. 具体例子演示")
        print("-" * 30)
        
        # 创建一个示例图像
        image = np.zeros((400, 600, 3), dtype=np.uint8)
        
        # 画一个网格作为参考
        for i in range(0, 600, 50):
            cv2.line(image, (i, 0), (i, 400), (100, 100, 100), 1)
        for i in range(0, 400, 50):
            cv2.line(image, (0, i), (600, i), (100, 100, 100), 1)
        
        # 画四个角点标记
        corners = [(100, 100), (500, 100), (500, 300), (100, 300)]
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        
        for i, (corner, color) in enumerate(zip(corners, colors)):
            cv2.circle(image, corner, 15, color, -1)
            cv2.putText(image, f'{i+1}', (corner[0]-10, corner[1]+5),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        print("""
假设我们有一个 600×400 的源图像，其中：
- 标定点1（左上）: (100, 100) - 红色
- 标定点2（右上）: (500, 100) - 绿色  
- 标定点3（右下）: (500, 300) - 蓝色
- 标定点4（左下）: (100, 300) - 黄色

目标：将这四个点映射到 300×200 图像的四个角
        """)
        
        # 定义源点和目标点
        src_points = np.float32(corners)
        dst_points = np.float32([(0, 0), (299, 0), (299, 199), (0, 199)])
        
        # 计算变换矩阵
        matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        
        print("\n计算得到的变换矩阵:")
        print(matrix)
        
        print(f"""
矩阵分析:
- 这个矩阵描述了如何将源图像的 (100,100)-(500,300) 区域
- 变换到目标图像的 (0,0)-(299,199) 区域
- 包含了缩放、平移、和轻微的透视校正
        """)
        
        # 应用变换
        result = cv2.warpPerspective(image, matrix, (300, 200))
        
        # 保存示例图像
        cv2.imwrite("example_source.jpg", image)
        cv2.imwrite("example_transformed.jpg", result)
        
        print("\n示例图像已保存:")
        print("- example_source.jpg: 源图像")
        print("- example_transformed.jpg: 变换后图像")
    
    def explain_multi_camera_alignment(self):
        """解释多摄像头对齐的完整流程"""
        
        print("\n6. 多摄像头对齐完整流程")
        print("-" * 35)
        
        print("""
现在我们有三个摄像头 CH1, CH2, CH3，它们从不同角度拍摄同一个区域。

问题：
- 三个摄像头的视角不同（角度、距离、高度）
- 图像尺寸可能不同
- 同一个物理点在三个图像中的像素坐标不同

解决方案：
1. 在真实世界中放置或选择4个明显的标定点
2. 在每个摄像头的图像中标记这4个点的像素坐标
3. 为每个摄像头计算一个变换矩阵，将其4个标定点映射到统一的目标位置
4. 应用各自的变换矩阵，得到对齐的图像

结果：
- 所有图像都是800×600尺寸
- 同一个物理点在所有图像中的像素坐标相同
- 可以进行像素级的对比、融合、分析

实际应用：
- 多角度监控融合
- 3D重建预处理
- 全景图像拼接
- 缺陷检测对比
        """)

def main():
    """主演示函数"""
    
    explainer = CalibrationExplainer()
    
    # 逐一解释各个概念
    explainer.explain_perspective_transform()
    explainer.explain_calibration_logic() 
    explainer.explain_transformation_matrix()
    explainer.explain_warp_perspective()
    explainer.demonstrate_with_example()
    explainer.explain_multi_camera_alignment()
    
    print("\n" + "=" * 50)
    print("总结：")
    print("""
1. 透视变换是核心技术，用3×3矩阵描述图像间的映射关系
2. 标定就是通过4个对应点计算这个变换矩阵
3. transformation_matrices存储每个摄像头的专用变换矩阵
4. cv2.warpPerspective使用矩阵对整个图像进行几何变换
5. 最终实现多摄像头图像的视角统一和尺寸对齐
    """)

if __name__ == "__main__":
    main()