"""
三摄像头系统的3D标定方案
考虑Z轴高度变化的多帧图像标定
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict
import json

class Camera3DCalibrator:
    """
    3D相机标定系统
    处理具有Z轴高度变化的多帧图像
    """
    
    def __init__(self):
        # 相机内参
        self.camera_matrices = {}      # 存储每个相机的内参矩阵
        self.dist_coeffs = {}          # 存储每个相机的畸变系数
        
        # 相机外参
        self.rvecs = {}               # 旋转向量
        self.tvecs = {}               # 平移向量
        
        # 标定板参数
        self.pattern_size = (8, 6)     # 标定板内角点数量
        self.square_size = 25.0        # 标定板方格尺寸(mm)
        
        # 存储多帧图像的数据
        self.image_points = {}         # 每个相机每帧图像中的角点
        self.frame_z_heights = []      # 每帧图像对应的Z轴高度
        
    def create_object_points(self) -> np.ndarray:
        """
        创建标定板的三维坐标点
        按照Z轴高度变化创建多组坐标点
        """
        pattern_points = np.zeros((self.pattern_size[0] * self.pattern_size[1], 3), np.float32)
        pattern_points[:, :2] = np.indices(self.pattern_size).T.reshape(-1, 2)
        pattern_points *= self.square_size
        return pattern_points
    
    def detect_corners(self, image: np.ndarray) -> Tuple[bool, np.ndarray]:
        """
        检测标定板角点
        
        Args:
            image: 输入图像
            
        Returns:
            found: 是否找到所有角点
            corners: 检测到的角点坐标
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, self.pattern_size, None)
        
        if found:
            # 亚像素级角点检测
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
            cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        
        return found, corners
    
    def calibrate_camera(self, 
                        images: Dict[str, List[str]], 
                        z_heights: List[float]):
        """
        执行相机标定
        
        Args:
            images: 每个相机的图像路径列表
                   {'cam1': ['frame1.jpg', 'frame2.jpg', ...], ...}
            z_heights: 每帧图像对应的Z轴高度(mm)
        """
        self.frame_z_heights = z_heights
        object_points = self.create_object_points()
        
        print("开始相机标定...")
        print(f"标定板参数: {self.pattern_size[0]}×{self.pattern_size[1]} 角点")
        print(f"总帧数: {len(z_heights)}")
        
        for camera_id, image_files in images.items():
            print(f"\n处理相机 {camera_id}...")
            
            # 存储这个相机的所有角点
            imgpoints = []  # 图像平面点
            objpoints = []  # 对应的三维点
            
            for frame_idx, (image_file, z_height) in enumerate(zip(image_files, z_heights)):
                # 读取图像
                image = cv2.imread(image_file)
                if image is None:
                    print(f"警告: 无法读取图像 {image_file}")
                    continue
                
                # 检测角点
                found, corners = self.detect_corners(image)
                
                if found:
                    # 创建这一帧的三维点（考虑Z轴高度）
                    frame_objpoints = object_points.copy()
                    frame_objpoints[:, 2] = z_height  # 设置Z轴高度
                    
                    imgpoints.append(corners)
                    objpoints.append(frame_objpoints)
                    
                    # 可视化角点检测结果
                    cv2.drawChessboardCorners(image, self.pattern_size, corners, found)
                    output_file = f"calibration_{camera_id}_frame{frame_idx}.jpg"
                    cv2.imwrite(output_file, image)
                    
                    print(f"✓ 帧 {frame_idx}: 检测到 {len(corners)} 个角点, Z = {z_height}mm")
                else:
                    print(f"✗ 帧 {frame_idx}: 未检测到角点")
            
            if not imgpoints:
                print(f"错误: 相机 {camera_id} 没有检测到任何角点")
                continue
            
            print(f"\n标定相机 {camera_id}...")
            # 执行相机标定
            ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
                objpoints, imgpoints, image.shape[:2][::-1], None, None
            )
            
            # 保存标定结果
            self.camera_matrices[camera_id] = mtx
            self.dist_coeffs[camera_id] = dist
            self.rvecs[camera_id] = rvecs
            self.tvecs[camera_id] = tvecs
            self.image_points[camera_id] = imgpoints
            
            print(f"""
相机 {camera_id} 标定结果:
- 重投影误差: {ret}
- 相机矩阵:
{mtx}
- 畸变系数: {dist.ravel()}
            """)
    
    def stereo_calibrate(self, ref_camera_id: str):
        """
        执行多相机的立体标定
        
        Args:
            ref_camera_id: 参考相机ID
        """
        print("\n执行立体标定...")
        
        for camera_id in self.camera_matrices.keys():
            if camera_id == ref_camera_id:
                continue
                
            # 计算两个相机之间的关系
            ret, r_mat, t_vec, _ = cv2.solvePnP(
                self.create_object_points(),
                self.image_points[camera_id][0],  # 使用第一帧
                self.camera_matrices[camera_id],
                self.dist_coeffs[camera_id]
            )
            
            print(f"""
{ref_camera_id} → {camera_id} 变换:
- 旋转矩阵:
{r_mat}
- 平移向量: {t_vec.ravel()}
            """)
    
    def reconstruct_3d_points(self, 
                            image_points: Dict[str, np.ndarray], 
                            z_height: float) -> np.ndarray:
        """
        重建三维点云
        
        Args:
            image_points: 每个相机中的图像点
            z_height: 当前帧的Z轴高度
            
        Returns:
            重建的3D点云
        """
        # TODO: 实现三角化重建
        pass
    
    def save_calibration(self, filename: str):
        """保存标定结果"""
        calibration_data = {
            'camera_matrices': {k: v.tolist() for k, v in self.camera_matrices.items()},
            'dist_coeffs': {k: v.tolist() for k, v in self.dist_coeffs.items()},
            'pattern_size': self.pattern_size,
            'square_size': self.square_size
        }
        
        with open(filename, 'w') as f:
            json.dump(calibration_data, f, indent=2)
        
        print(f"标定数据已保存到: {filename}")
    
    def load_calibration(self, filename: str):
        """加载标定数据"""
        with open(filename, 'r') as f:
            data = json.load(f)
        
        self.camera_matrices = {k: np.array(v) for k, v in data['camera_matrices'].items()}
        self.dist_coeffs = {k: np.array(v) for k, v in data['dist_coeffs'].items()}
        self.pattern_size = tuple(data['pattern_size'])
        self.square_size = data['square_size']
        
        print(f"已加载标定数据: {filename}")
    
    def visualize_calibration(self):
        """可视化标定结果"""
        # 创建3D图
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # 绘制相机位置和方向
        for camera_id in self.camera_matrices.keys():
            if camera_id in self.rvecs and camera_id in self.tvecs:
                # 获取第一帧的位姿
                rvec = self.rvecs[camera_id][0]
                tvec = self.tvecs[camera_id][0]
                
                # 转换旋转向量为旋转矩阵
                R, _ = cv2.Rodrigues(rvec)
                
                # 绘制相机位置
                ax.scatter(tvec[0], tvec[1], tvec[2], 
                         c='r', marker='o', s=100, label=camera_id)
                
                # 绘制相机坐标轴
                axis_length = 100  # mm
                
                for i, color in enumerate(['r', 'g', 'b']):
                    axis = np.zeros((4, 3))
                    axis[1, i] = axis_length
                    
                    # 变换到世界坐标系
                    axis_world = np.dot(R, axis.T).T + tvec.T
                    
                    ax.plot3D(axis_world[[0,1], 0],
                             axis_world[[0,1], 1],
                             axis_world[[0,1], 2],
                             color=color)
        
        # 绘制标定板位置
        z_heights = np.array(self.frame_z_heights)
        pattern_points = self.create_object_points()
        
        for z in z_heights:
            points = pattern_points.copy()
            points[:, 2] = z
            ax.scatter(points[:, 0], points[:, 1], points[:, 2],
                      c='gray', alpha=0.3, s=10)
        
        # 设置图表
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_zlabel('Z (mm)')
        ax.legend()
        
        plt.title('3D相机标定结果可视化')
        plt.savefig('calibration_3d_visualization.png', dpi=300, bbox_inches='tight')
        plt.show()
        
def main():
    """主程序"""
    calibrator = Camera3DCalibrator()
    
    # 图像路径设置（示例）
    images = {
        'CAM1': [f'images/cam1/frame{i:02d}.jpg' for i in range(20)],
        'CAM2': [f'images/cam2/frame{i:02d}.jpg' for i in range(20)],
        'CAM3': [f'images/cam3/frame{i:02d}.jpg' for i in range(20)]
    }
    
    # Z轴高度设置（每帧增加0.08mm）
    z_heights = [i * 0.08 for i in range(20)]
    
    # 执行标定
    calibrator.calibrate_camera(images, z_heights)
    
    # 立体标定（以CAM1为参考）
    calibrator.stereo_calibrate('CAM1')
    
    # 保存标定结果
    calibrator.save_calibration('camera_calibration_3d.json')
    
    # 可视化标定结果
    calibrator.visualize_calibration()

if __name__ == "__main__":
    main()