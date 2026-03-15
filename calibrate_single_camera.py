
'''
准备数据
输入1： 10张不同层高的棋盘格图片（例如 layer_1_cam1.jpg, layer_2_cam1.jpg, ... layer_10_cam1.jpg）。
输入2： 棋盘格的尺寸 (8, 10)。这指的是内部角点的数量，即方格数减一。你的8x10棋盘格，内部角点就是7x9。
输入3： 每一层对应的物理高度（Z坐标）。假设你的层厚是0.1mm。
第1层 Z = 0.0 mm
第2层 Z = 0.1 mm
...
第10层 Z = 0.9 mm

这一步的输出是什么？
camera_matrix (内参矩阵):
# 形式如下：
# [[fx,  0, cx],
#  [ 0, fy, cy],
#  [ 0,  0,  1]]
fx, fy: 焦距，以像素为单位。
cx, cy: 主点，通常是图像中心。
dist_coeffs (畸变系数):
# 形式如下：
# [k1, k2, p1, p2, k3, ...]
k1, k2, k3: 径向畸变系数
p1, p2: 切向畸变系数
这些参数可以用来校正图像畸变，进行3D重建等
ret (重投影误差):
这是标定精度的关键指标。它表示检测到的角点与通过标定参数重新投影回去的角点之间的平均像素距离。这个值通常应小于0.5像素，值越小说明标定越精确。
rvecs, tvecs: 每一张标定图片的旋转和平移向量（外参），对于单独标定，我们暂时不需要它们。
'''


import numpy as np
import cv2
import glob
import argparse
import os

def calibrate_single_camera(image_folder, chessboard_size, square_size, layer_heights, output_file):
    """
    单独标定单个摄像头
    
    参数:
    image_folder: 包含标定图像的文件夹路径
    chessboard_size: 棋盘格内部角点数量 (width, height)
    square_size: 每个方格的实际物理尺寸（毫米）
    layer_heights: 各图层对应的Z坐标数组（毫米）
    output_file: 输出文件名
    """
    
    # --- 步骤1: 准备"理想"的世界坐标系点 ---
    objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)
    objp *= square_size

    objpoints = [] # 3D点在世界坐标系中
    imgpoints = [] # 对应的2D点在图像像素坐标系中

    # 获取所有标定图片的文件路径
    images = glob.glob(os.path.join(image_folder, '*.jpg')) + \
             glob.glob(os.path.join(image_folder, '*.png'))
    images.sort()  # 确保按顺序处理

    if len(images) != len(layer_heights):
        print(f"警告: 图像数量({len(images)})与层高数量({len(layer_heights)})不匹配!")

    print(f"正在处理文件夹: {image_folder}")
    print(f"找到 {len(images)} 张图像")

    # --- 步骤2: 遍历所有图片，查找角点 ---
    success_count = 0
    for i, fname in enumerate(images):
        img = cv2.imread(fname)
        if img is None:
            print(f"无法读取图像: {fname}")
            continue
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 查找棋盘格角点
        ret, corners = cv2.findChessboardCorners(gray, chessboard_size, None)

        if ret:
            # 为当前图片复制一份objp并设置Z坐标
            objp_temp = objp.copy()
            objp_temp[:, 2] = layer_heights[i] if i < len(layer_heights) else 0.0
            objpoints.append(objp_temp)

            # 提高角点检测精度
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners_refined)
            success_count += 1

            print(f"✓ 成功检测角点: {os.path.basename(fname)}")
        else:
            print(f"✗ 未找到角点: {os.path.basename(fname)}")

    print(f"\n成功处理 {success_count}/{len(images)} 张图像")

    if success_count < 5:
        print("错误: 成功标定的图像数量不足!")
        return False

    # --- 步骤3: 执行相机标定 ---
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, gray.shape[::-1], None, None
    )

    # --- 输出结果 ---
    print(f"\n=== 相机标定结果 ===")
    print(f"重投影误差: {ret:.4f} 像素")
    print("内参矩阵:")
    print(camera_matrix)
    print("\n畸变系数:")
    print(dist_coeffs.ravel())

    # 保存结果
    np.savez(output_file,
             camera_matrix=camera_matrix,
             dist_coeffs=dist_coeffs,
             image_size=gray.shape[::-1],
             reprojection_error=ret,
             objpoints=objpoints,
             imgpoints=imgpoints)

    print(f"\n标定数据已保存至: {output_file}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='单独标定单个摄像头')
    parser.add_argument('--image_folder', type=str, required=True, help='包含标定图像的文件夹路径')
    parser.add_argument('--chessboard_width', type=int, default=7, help='棋盘格横向内部角点数')
    parser.add_argument('--chessboard_height', type=int, default=9, help='棋盘格纵向内部角点数')
    parser.add_argument('--square_size', type=float, default=1.0, help='每个方格的物理尺寸（毫米）')
    parser.add_argument('--layer_heights', type=float, nargs='+', required=True, help='各图层的Z坐标（毫米）')
    parser.add_argument('--output', type=str, default='camera_calibration.npz', help='输出文件名')
    
    args = parser.parse_args()
    
    chessboard_size = (args.chessboard_width, args.chessboard_height)
    
    calibrate_single_camera(args.image_folder, chessboard_size, args.square_size, 
                           args.layer_heights, args.output)


'''
# 标定摄像头1
python calibrate_single_camera.py \
    --image_folder ./images/cam1 \
    --chessboard_width 7 \
    --chessboard_height 9 \
    --square_size 1.0 \
    --layer_heights 0.0 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 \
    --output cam1_calibration.npz

# 同理标定摄像头2和3
'''