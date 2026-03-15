"""
透视变换数学原理详解
解释为什么透视变换公式是这样的形式
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def explain_perspective_transform_math():
    """解释透视变换的数学基础"""
    
    print("=" * 60)
    print("透视变换数学原理详解")
    print("=" * 60)
    
    print("""
为什么透视变换公式是：
x' = (m00×x + m01×y + m02) / (m20×x + m21×y + m22)
y' = (m10×x + m11×y + m12) / (m20×x + m21×y + m22)

这个公式来源于齐次坐标系和投影几何理论。
    """)
    
    print("\n1. 齐次坐标系的引入")
    print("-" * 30)
    print("""
在计算机视觉中，我们使用齐次坐标来表示点：
- 2D点 (x, y) → 齐次坐标 [x, y, 1]
- 3D点 (x, y, z) → 齐次坐标 [x, y, z, 1]

齐次坐标的优势：
1. 可以用矩阵乘法表示所有几何变换（包括平移）
2. 可以表示无穷远点
3. 投影变换变得线性化
    """)
    
    print("\n2. 透视变换矩阵")
    print("-" * 30)
    print("""
对于2D透视变换，我们使用3×3矩阵：

M = [[m00, m01, m02],
     [m10, m11, m12],
     [m20, m21, m22]]

点的变换：[x', y', w'] = M × [x, y, 1]

其中：
- x' = m00×x + m01×y + m02
- y' = m10×x + m11×y + m12  
- w' = m20×x + m21×y + m22

最终的笛卡尔坐标需要除以w'进行归一化：
- 最终x坐标 = x' / w'
- 最终y坐标 = y' / w'
    """)
    
    print("\n3. 为什么需要除法？")
    print("-" * 30)
    print("""
关键在于理解透视投影的本质：

现实世界 → 投影平面的过程：
1. 3D世界中的点 (X, Y, Z)
2. 通过摄像头中心投影到2D平面
3. 投影公式：x = f×X/Z, y = f×Y/Z （f是焦距）

注意这里有除法！距离越远(Z越大)，投影越小。

齐次坐标中的w'项实际上编码了深度信息：
- w' = m20×x + m21×y + m22
- m20, m21是透视参数，控制"近大远小"的效果
- 除以w'就是在模拟真实的透视投影
    """)
    
    print("\n4. 各项的物理意义")
    print("-" * 30)
    print("""
m00, m11: 缩放 - 控制图像放大缩小
m01, m10: 剪切/旋转 - 处理图像倾斜
m02, m12: 平移 - 控制图像位移
m20, m21: 透视 - 关键！控制"近大远小"效果
m22: 归一化 - 通常设为1

如果m20=m21=0，公式退化为仿射变换（没有透视效果）
如果m20≠0或m21≠0，就有真正的透视效果
    """)

def demonstrate_perspective_effect():
    """演示透视效果的产生"""
    
    print("\n5. 透视效果演示")
    print("-" * 30)
    
    # 创建一个网格
    x = np.linspace(-2, 2, 5)
    y = np.linspace(-2, 2, 5)
    X, Y = np.meshgrid(x, y)
    
    # 原始点（平面网格）
    points_2d = np.column_stack([X.flatten(), Y.flatten()])
    
    # 不同的透视变换矩阵
    transforms = {
        "无透视(仿射)": np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0], 
            [0.0, 0.0, 1.0]
        ]),
        
        "轻微透视": np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.1, 0.0, 1.0]  # m20=0.1，产生x方向透视
        ]),
        
        "强透视": np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.3, 0.2, 1.0]  # m20=0.3, m21=0.2，双向透视
        ])
    }
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    for i, (name, matrix) in enumerate(transforms.items()):
        # 应用变换
        transformed_points = []
        
        for point in points_2d:
            # 齐次坐标
            homog = np.array([point[0], point[1], 1.0])
            # 变换
            transformed_homog = matrix @ homog
            # 归一化（除以w）
            x_new = transformed_homog[0] / transformed_homog[2]
            y_new = transformed_homog[1] / transformed_homog[2]
            transformed_points.append([x_new, y_new])
        
        transformed_points = np.array(transformed_points)
        
        # 绘制结果
        axes[i].scatter(transformed_points[:, 0], transformed_points[:, 1], 
                       c='red', s=50, alpha=0.7)
        axes[i].set_title(f'{name}\nm20={matrix[2,0]}, m21={matrix[2,1]}')
        axes[i].grid(True, alpha=0.3)
        axes[i].set_xlim(-3, 3)
        axes[i].set_ylim(-3, 3)
        axes[i].set_aspect('equal')
        
        # 连线显示网格变形
        X_new = transformed_points[:, 0].reshape(5, 5)
        Y_new = transformed_points[:, 1].reshape(5, 5)
        
        # 水平线
        for j in range(5):
            axes[i].plot(X_new[j, :], Y_new[j, :], 'b-', alpha=0.5)
        # 垂直线  
        for j in range(5):
            axes[i].plot(X_new[:, j], Y_new[:, j], 'b-', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig('perspective_effect_demo.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print("透视效果演示图已保存为: perspective_effect_demo.png")
    print("""
观察结果：
- 无透视：网格保持规则矩形
- 轻微透视：网格产生轻微的梯形变形  
- 强透视：网格产生明显的透视变形，远端变小

这就是透视变换公式中除法的作用！
    """)

if __name__ == "__main__":
    explain_perspective_transform_math()
    demonstrate_perspective_effect()