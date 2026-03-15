import numpy as np
import cv2
import argparse

def create_rectification_maps(calibration_file, output_file):
    """
    创建立体校正映射
    
    参数:
    calibration_file: 联合标定数据文件
    output_file: 输出映射文件
    """
    
    data = np.load(calibration_file, allow_pickle=True)
    
    # 提取数据
    cam1_matrix = data['cam1_matrix']   # 内参矩阵
    cam1_dist = data['cam1_dist']       # 畸变系数
    cam1_size = tuple(data['cam1_size'])# 图像尺寸 (宽度, 高度)
    
    cam2_matrix = data['cam2_matrix']
    cam2_dist = data['cam2_dist']
    cam2_size = tuple(data['cam2_size'])
    
    cam3_matrix = data['cam3_matrix']
    cam3_dist = data['cam3_dist']
    cam3_size = tuple(data['cam3_size'])
    
    R_1_to_2 = data['rotation_matrix_1_to_2']
    T_1_to_2 = data['tvec_1_to_2']
    
    R_1_to_3 = data['rotation_matrix_1_to_3']
    T_1_to_3 = data['tvec_1_to_3']
    
    print("计算立体校正映射...")
    
    # --- 计算摄像头1和2之间的立体校正 ---
    print("计算摄像头1-2立体校正...")
    R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
        cam1_matrix, cam1_dist,
        cam2_matrix, cam2_dist,
        cam1_size, R_1_to_2, T_1_to_2,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0.9
    )
    
    # 计算校正映射
    map1_1, map1_2 = cv2.initUndistortRectifyMap(
        cam1_matrix, cam1_dist, R1, P1, cam1_size, cv2.CV_16SC2
    )
    map2_1, map2_2 = cv2.initUndistortRectifyMap(
        cam2_matrix, cam2_dist, R2, P2, cam2_size, cv2.CV_16SC2
    )
    
    # --- 计算摄像头1和3之间的立体校正 ---
    print("计算摄像头1-3立体校正...")
    R1_3, R3, P1_3, P3, Q_3, roi1_3, roi3 = cv2.stereoRectify(
        cam1_matrix, cam1_dist,
        cam3_matrix, cam3_dist,
        cam1_size, R_1_to_3, T_1_to_3,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0.9
    )
    
    map3_1, map3_2 = cv2.initUndistortRectifyMap(
        cam3_matrix, cam3_dist, R3, P3, cam3_size, cv2.CV_16SC2
    )
    
    # 保存所有映射
    np.savez(output_file,
             # 摄像头1-2校正
             map1_1=map1_1, map1_2=map1_2,          # 摄像头1的x,y映射
             map2_1=map2_1, map2_2=map2_2,          # 摄像头2的x,y映射
             R1=R1, R2=R2, P1=P1, P2=P2, Q=Q,       # 摄像头1-2校正参数
             
             
             # 摄像头1-3校正
             map3_1=map3_1, map3_2=map3_2,          # 摄像头3的x,y映射
             R3=R3, P3=P3, Q_3=Q_3,                 # 摄像头1-3校正参数
             roi1=roi1, roi2=roi2,roi3=roi3,        # 各摄像头校正后的有效区域
             
             # 图像尺寸
             cam1_size=cam1_size,
             cam2_size=cam2_size,
             cam3_size=cam3_size)
    
    print(f"立体校正映射已保存至: {output_file}")
    print("可以使用这些映射通过 cv2.remap() 函数实时校正图像")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='创建立体校正映射')
    parser.add_argument('--calibration_file', type=str, required=True, help='联合标定数据文件')
    parser.add_argument('--output', type=str, default='rectification_maps.npz', help='输出文件名')
    
    args = parser.parse_args()
    create_rectification_maps(args.calibration_file, args.output)


'''
python create_rectification_maps.py \
    --calibration_file joint_calibration.npz \
    --output rectification_maps.npz
'''
'''
映射表 (mapX_1, mapX_2)：

这是预计算的查找表，告诉我们在校正后的图像中，每个像素应该从原始图像的哪个位置取样

mapX_1：x方向坐标映射

mapX_2：y方向坐标映射
'''
'''
# 使用示例
# 加载校正映射
maps = np.load('rectification_maps.npz')

# 校正三路摄像头图像
rectified_visible1 = cv2.remap(original_visible1, maps['map1_1'], maps['map1_2'], cv2.INTER_LINEAR)
rectified_infrared = cv2.remap(original_infrared, maps['map2_1'], maps['map2_2'], cv2.INTER_LINEAR)
rectified_visible2 = cv2.remap(original_visible2, maps['map3_1'], maps['map3_2'], cv2.INTER_LINEAR)

# 现在三个图像已经精确对齐！
# 你可以直接比较相同位置的像素值
x, y = 500, 300  # 任意坐标
visible1_value = rectified_visible1[y, x]      # 主可见光值
infrared_value = rectified_infrared[y, x]      # 红外温度值  
visible2_value = rectified_visible2[y, x]      # 副可见光值
# '''
