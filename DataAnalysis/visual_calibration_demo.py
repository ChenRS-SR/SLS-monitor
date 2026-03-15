"""
可视化演示：透视变换和标定过程
帮助理解标定逻辑和变换矩阵的作用
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt

def create_demo_image():
    """创建一个演示用的图像"""
    
    # 创建 800×600 的图像
    image = np.ones((600, 800, 3), dtype=np.uint8) * 240  # 浅灰色背景
    
    # 绘制网格线
    for x in range(0, 800, 100):
        cv2.line(image, (x, 0), (x, 600), (200, 200, 200), 2)
    for y in range(0, 600, 100):
        cv2.line(image, (0, y), (800, y), (200, 200, 200), 2)
    
    # 绘制一个"工作区域"矩形
    work_area = [(200, 150), (600, 150), (600, 450), (200, 450)]
    cv2.rectangle(image, work_area[0], work_area[2], (100, 100, 255), 3)
    
    # 标记四个角点
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    labels = ['P1(左上)', 'P2(右上)', 'P3(右下)', 'P4(左下)']
    
    for i, (point, color, label) in enumerate(zip(work_area, colors, labels)):
        cv2.circle(image, point, 12, color, -1)
        cv2.circle(image, point, 12, (0, 0, 0), 2)
        cv2.putText(image, f'{i+1}', (point[0]-8, point[1]+5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(image, label, (point[0]+20, point[1]-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    # 添加一些"物体"作为参考
    # 圆形物体
    cv2.circle(image, (300, 250), 30, (150, 100, 50), -1)
    cv2.putText(image, 'Object1', (260, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    # 矩形物体
    cv2.rectangle(image, (450, 300), (520, 370), (50, 150, 100), -1)
    cv2.putText(image, 'Object2', (430, 390), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    return image, work_area

def simulate_camera_perspective(image, angle_x=15, angle_y=10, scale=0.8):
    """模拟摄像头视角，产生透视变形"""
    
    h, w = image.shape[:2]
    
    # 创建透视变换，模拟摄像头角度
    # 原始四个角点
    src_corners = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])
    
    # 模拟视角变化后的四个角点
    offset_x = int(w * 0.1 * np.sin(np.radians(angle_x)))
    offset_y = int(h * 0.1 * np.sin(np.radians(angle_y)))
    
    dst_corners = np.float32([
        [offset_x, offset_y],                    # 左上
        [w-1-offset_x, offset_y//2],            # 右上  
        [w-1+offset_x//2, h-1-offset_y],        # 右下
        [-offset_x//2, h-1+offset_y//2]         # 左下
    ])
    
    # 计算透视变换矩阵
    matrix = cv2.getPerspectiveTransform(src_corners, dst_corners)
    
    # 应用变换
    warped = cv2.warpPerspective(image, matrix, (w, h))
    
    return warped, dst_corners

def demonstrate_calibration_process():
    """演示完整的标定过程"""
    
    print("=" * 60)
    print("透视变换与多摄像头标定可视化演示")
    print("=" * 60)
    
    # 1. 创建理想的俯视图像
    print("\n1. 创建理想俯视图（标准视角）")
    ideal_image, work_area = create_demo_image()
    cv2.imwrite("demo_1_ideal_view.jpg", ideal_image)
    print("   保存为: demo_1_ideal_view.jpg")
    print(f"   工作区域四个角点: {work_area}")
    
    # 2. 模拟三个不同角度的摄像头
    print("\n2. 模拟三个摄像头的不同视角")
    
    cameras = [
        ("CH1", 10, 5, 0.9),   # 轻微角度
        ("CH2", -15, 10, 0.8), # 较大角度  
        ("CH3", 20, -8, 0.85)  # 另一个角度
    ]
    
    camera_images = {}
    camera_corners = {}
    
    for name, angle_x, angle_y, scale in cameras:
        warped_img, corners = simulate_camera_perspective(ideal_image, angle_x, angle_y, scale)
        camera_images[name] = warped_img
        camera_corners[name] = corners
        
        filename = f"demo_2_{name}_perspective.jpg"
        cv2.imwrite(filename, warped_img)
        print(f"   {name}: 保存为 {filename}")
        print(f"        角度: x={angle_x}°, y={angle_y}°, 缩放={scale}")
    
    # 3. 在变形图像中找到对应的标定点
    print("\n3. 在每个摄像头图像中找到对应的工作区域角点")
    
    for name, img in camera_images.items():
        # 在变形的图像中，原来的工作区域四个角点会变成新的位置
        # 这里我们简化处理，直接在图像中寻找特征点
        
        # 转换为灰度图进行角点检测
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 使用goodFeaturesToTrack检测角点
        corners = cv2.goodFeaturesToTrack(gray, maxCorners=100, qualityLevel=0.01, minDistance=10)
        
        if corners is not None:
            # 在原图上标记检测到的角点
            marked_img = img.copy()
            for corner in corners:
                x, y = corner.ravel()
                cv2.circle(marked_img, (int(x), int(y)), 5, (0, 255, 0), -1)
            
            filename = f"demo_3_{name}_corners.jpg"
            cv2.imwrite(filename, marked_img)
            print(f"   {name}: 检测到 {len(corners)} 个角点，保存为 {filename}")
    
    # 4. 演示变换矩阵的计算
    print("\n4. 计算透视变换矩阵")
    
    # 手动定义一些标定点（模拟用户点击选择的过程）
    calibration_points = {
        'CH1': [(180, 140), (620, 145), (615, 465), (185, 460)],
        'CH2': [(160, 120), (580, 160), (570, 480), (170, 440)], 
        'CH3': [(220, 130), (640, 140), (635, 470), (225, 465)]
    }
    
    # 目标点（统一的800×600图像的四个角）
    target_points = np.float32([(0, 0), (799, 0), (799, 599), (0, 599)])
    
    transformation_matrices = {}
    
    for channel, points in calibration_points.items():
        src_points = np.float32(points)
        
        # 计算透视变换矩阵
        matrix = cv2.getPerspectiveTransform(src_points, target_points)
        transformation_matrices[channel] = matrix
        
        print(f"\n   {channel} 变换矩阵:")
        print(f"   标定点: {points}")
        print(f"   矩阵:\n{matrix}")
        
        # 分析矩阵含义
        print(f"   矩阵分析:")
        print(f"     缩放因子: x={matrix[0,0]:.3f}, y={matrix[1,1]:.3f}")
        print(f"     平移量: x={matrix[0,2]:.1f}, y={matrix[1,2]:.1f}")
        print(f"     透视参数: {matrix[2,0]:.6f}, {matrix[2,1]:.6f}")
    
    # 5. 应用变换矩阵进行对齐
    print("\n5. 应用变换矩阵，对齐所有图像")
    
    aligned_images = {}
    
    for channel in calibration_points.keys():
        if channel in camera_images and channel in transformation_matrices:
            # 应用透视变换
            aligned = cv2.warpPerspective(
                camera_images[channel], 
                transformation_matrices[channel], 
                (800, 600)
            )
            
            aligned_images[channel] = aligned
            
            filename = f"demo_4_{channel}_aligned.jpg"
            cv2.imwrite(filename, aligned)
            print(f"   {channel}: 对齐完成，保存为 {filename}")
    
    # 6. 创建对比图
    print("\n6. 创建对齐前后对比图")
    create_comparison_visualization(camera_images, aligned_images, ideal_image)
    
    # 7. 演示 cv2.warpPerspective 的工作原理
    print("\n7. cv2.warpPerspective 工作原理演示")
    demonstrate_warp_perspective_details()
    
    print("\n" + "=" * 60)
    print("演示完成！请查看生成的图像文件了解效果。")
    print("=" * 60)

def create_comparison_visualization(original_images, aligned_images, ideal_image):
    """创建对齐前后的可视化对比"""
    
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    
    channels = list(original_images.keys())
    
    for i, channel in enumerate(channels):
        # 原始图像
        if channel in original_images:
            img = cv2.cvtColor(original_images[channel], cv2.COLOR_BGR2RGB)
            axes[i, 0].imshow(img)
            axes[i, 0].set_title(f'{channel} - 原始视角')
            axes[i, 0].axis('off')
        
        # 对齐后图像  
        if channel in aligned_images:
            img = cv2.cvtColor(aligned_images[channel], cv2.COLOR_BGR2RGB)
            axes[i, 1].imshow(img)
            axes[i, 1].set_title(f'{channel} - 对齐后')
            axes[i, 1].axis('off')
        
        # 理想图像作为参考
        ideal = cv2.cvtColor(ideal_image, cv2.COLOR_BGR2RGB)
        axes[i, 2].imshow(ideal)
        axes[i, 2].set_title('理想俯视图（参考）')
        axes[i, 2].axis('off')
    
    plt.tight_layout()
    plt.savefig('demo_5_comparison.png', dpi=300, bbox_inches='tight')
    print("   对比图保存为: demo_5_comparison.png")
    plt.close()

def demonstrate_warp_perspective_details():
    """详细演示 cv2.warpPerspective 的工作过程"""
    
    print("\n   cv2.warpPerspective 详细工作流程:")
    print("   " + "-" * 40)
    
    # 创建一个简单的示例
    src = np.array([[100, 100], [300, 120], [280, 250], [120, 230]], dtype=np.float32)
    dst = np.array([[0, 0], [200, 0], [200, 150], [0, 150]], dtype=np.float32)
    
    matrix = cv2.getPerspectiveTransform(src, dst)
    
    print(f"""
   示例：将四边形 {src.tolist()} 
         变换为矩形 {dst.tolist()}
   
   计算得到的变换矩阵:
   {matrix}
   
   变换过程解释:
   1. 对于输出图像中的每个像素 (x', y')
   2. 使用逆变换矩阵计算对应的源图像位置:
      
      原始坐标 = 逆矩阵 × [x', y', 1]^T
      
   3. 在源图像中插值采样该位置的像素值
   4. 将采样值赋给输出图像的 (x', y') 位置
   
   关键点:
   - 这是"后向映射"：从目标像素找源像素
   - 避免了"前向映射"可能产生的空洞问题
   - 需要插值处理非整数像素位置
   """)
    
    # 演示几个具体的点变换
    print("   具体点变换示例:")
    test_points = [[0, 0], [100, 0], [200, 150], [0, 150]]
    
    for point in test_points:
        # 使用变换矩阵计算对应的源位置
        homog_point = np.array([point[0], point[1], 1.0])
        
        # 计算逆变换
        inv_matrix = np.linalg.inv(matrix)
        src_homog = inv_matrix @ homog_point
        
        # 转换为笛卡尔坐标
        src_x = src_homog[0] / src_homog[2]
        src_y = src_homog[1] / src_homog[2]
        
        print(f"   目标点 {point} → 源点 ({src_x:.1f}, {src_y:.1f})")

if __name__ == "__main__":
    demonstrate_calibration_process()