import cv2
import numpy as np
import os
import json
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
from pathlib import Path

class MultiCameraAlignment:
    """
    多摄像头图像对齐类
    使用四个标定点进行透视变换，将三个摄像头的图像对齐到统一的800×600尺寸
    """
    
    def __init__(self, target_size: Tuple[int, int] = (800, 600)):
        """
        初始化对齐器
        
        Args:
            target_size: 目标图像尺寸 (width, height)
        """
        self.target_size = target_size
        self.calibration_points = {}  # 存储每个通道的标定点
        self.transformation_matrices = {}  # 存储变换矩阵
        self.target_points = np.array([
            [0, 0],                           # 左上角
            [target_size[0]-1, 0],           # 右上角
            [target_size[0]-1, target_size[1]-1],  # 右下角
            [0, target_size[1]-1]            # 左下角
        ], dtype=np.float32)
    
    def set_calibration_points(self, channel: str, points: List[Tuple[int, int]]):
        """
        设置某个通道的标定点并计算变换矩阵
        
        标定逻辑详解：
        1. 用户在源图像中选择4个标定点（现实世界中的同一矩形区域的四个角）
        2. 这4个点将被映射到目标图像的四个角 (0,0), (799,0), (799,599), (0,599)
        3. 通过这种映射，实现视角统一和尺寸标准化
        
        Args:
            channel: 通道名称 (如 'CH1', 'CH2', 'CH3')
            points: 四个标定点坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
                   顺序：左上、右上、右下、左下
                   注意：这四个点应该对应现实世界中同一矩形区域的四个角
        """
        if len(points) != 4:
            raise ValueError("必须提供4个标定点")
        
        # 保存源图像中的标定点坐标
        self.calibration_points[channel] = np.array(points, dtype=np.float32)
        
        # 计算透视变换矩阵
        # cv2.getPerspectiveTransform() 会计算一个3×3矩阵，
        # 该矩阵将源图像中的4个标定点精确映射到目标图像的4个角点
        # 
        # 变换矩阵的含义：
        # [[m00, m01, m02],    m00,m11: 缩放因子
        #  [m10, m11, m12],    m01,m10: 剪切/旋转分量  
        #  [m20, m21, m22]]    m02,m12: 平移分量
        #                      m20,m21: 透视变换参数（产生透视效果）
        #                      m22: 归一化参数（通常为1）
        self.transformation_matrices[channel] = cv2.getPerspectiveTransform(
            self.calibration_points[channel],  # 源点：用户选择的4个标定点
            self.target_points                 # 目标点：800×600图像的四个角
        )
        
        print(f"通道 {channel} 标定完成")
    
    def interactive_calibration(self, image_path: str, channel: str):
        """
        交互式标定：点击图像选择标定点
        
        Args:
            image_path: 用于标定的图像路径
            channel: 通道名称
        """
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"无法读取图像: {image_path}")
        
        # 创建显示窗口
        window_name = f"标定 {channel} - 请按顺序点击四个角点"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1000, 750)
        
        points = []
        
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
                points.append((x, y))
                # 在图像上标记点
                cv2.circle(image, (x, y), 10, (0, 255, 0), -1)
                cv2.putText(image, f"{len(points)}", (x+15, y-15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow(window_name, image)
                
                if len(points) == 4:
                    print(f"标定点选择完成: {points}")
        
        cv2.setMouseCallback(window_name, mouse_callback)
        cv2.imshow(window_name, image)
        
        print(f"请按顺序点击四个标定点：1.左上 2.右上 3.右下 4.左下")
        print("完成后按任意键继续...")
        
        cv2.waitKey(0)
        cv2.destroyWindow(window_name)
        
        if len(points) == 4:
            self.set_calibration_points(channel, points)
            return points
        else:
            raise ValueError("标定点数量不足")
    
    def align_image(self, image: np.ndarray, channel: str) -> np.ndarray:
        """
        对齐单张图像 - 透视变换的核心应用
        
        cv2.warpPerspective 详解：
        这个函数是整个对齐过程的核心，它的工作原理：
        
        1. 逆向映射过程：
           - 对于输出图像(800×600)中的每个像素位置(x', y')
           - 使用变换矩阵的逆矩阵计算对应的源图像位置(x, y)
           - 数学公式：[x, y, 1]^T = M^(-1) × [x', y', 1]^T
        
        2. 插值采样：
           - 计算得到的(x, y)通常不是整数坐标
           - 使用双线性插值在源图像中采样该位置的像素值
           - 这保证了变换后图像的平滑性
        
        3. 透视校正：
           - 由于变换矩阵包含透视参数(m20, m21)
           - 可以校正因摄像头角度、距离不同造成的透视变形
           - 远近物体会有不同的缩放比例，符合透视投影规律
        
        Args:
            image: 输入图像
            channel: 通道名称
            
        Returns:
            对齐后的图像（800×600尺寸，统一视角）
        """
        if channel not in self.transformation_matrices:
            raise ValueError(f"通道 {channel} 尚未标定")
        
        # 应用透视变换
        # 参数说明：
        # - image: 源图像  
        # - transformation_matrices[channel]: 预计算的3×3变换矩阵
        # - self.target_size: 输出图像尺寸(800, 600)
        # 
        # 变换过程：将源图像中的标定区域变换为标准的800×600矩形
        aligned_image = cv2.warpPerspective(
            image,                                    # 源图像
            self.transformation_matrices[channel],    # 变换矩阵 
            self.target_size                         # 目标尺寸(width, height)
        )
        
        return aligned_image
    
    def align_image_from_path(self, image_path: str, channel: str):
        """
        从文件路径读取并对齐图像
        
        Args:
            image_path: 图像文件路径
            channel: 通道名称
            
        Returns:
            对齐后的图像
        """
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"无法读取图像: {image_path}")
        
        return self.align_image(image, channel)
    
    def batch_align_images(self, input_dirs: Dict[str, str], output_dir: str):
        """
        批量对齐图像
        
        Args:
            input_dirs: 输入目录字典 {'CH1': 'path/to/ch1', 'CH2': 'path/to/ch2', 'CH3': 'path/to/ch3'}
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        for channel, input_dir in input_dirs.items():
            if channel not in self.transformation_matrices:
                print(f"警告: 通道 {channel} 尚未标定，跳过")
                continue
            
            # 创建输出子目录
            channel_output_dir = os.path.join(output_dir, channel)
            os.makedirs(channel_output_dir, exist_ok=True)
            
            # 获取所有图像文件
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff']:
                image_files.extend(Path(input_dir).glob(ext))
                image_files.extend(Path(input_dir).glob(ext.upper()))
            
            print(f"处理通道 {channel}: 找到 {len(image_files)} 张图像")
            
            for i, image_file in enumerate(image_files):
                try:
                    # 对齐图像
                    aligned_image = self.align_image_from_path(str(image_file), channel)
                    
                    # 保存对齐后的图像
                    output_path = os.path.join(channel_output_dir, image_file.name)
                    cv2.imwrite(output_path, aligned_image)
                    
                    if (i + 1) % 10 == 0:
                        print(f"  已处理 {i + 1}/{len(image_files)} 张图像")
                        
                except Exception as e:
                    print(f"处理图像 {image_file} 时出错: {e}")
            
            print(f"通道 {channel} 处理完成")
    
    def visualize_alignment(self, image_paths: Dict[str, str], save_path: str = None):
        """
        可视化对齐结果
        
        Args:
            image_paths: 每个通道的示例图像路径
            save_path: 保存路径（可选）
        """
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        
        # 原始图像
        for i, (channel, image_path) in enumerate(image_paths.items()):
            image = cv2.imread(image_path)
            if image is not None:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                axes[0, i].imshow(image_rgb)
                axes[0, i].set_title(f'原始 {channel}')
                axes[0, i].axis('off')
                
                # 标记标定点
                if channel in self.calibration_points:
                    points = self.calibration_points[channel]
                    for j, (x, y) in enumerate(points):
                        axes[0, i].plot(x, y, 'ro', markersize=8)
                        axes[0, i].text(x+10, y-10, f'{j+1}', color='red', fontsize=12)
        
        # 对齐后图像
        for i, (channel, image_path) in enumerate(image_paths.items()):
            if channel in self.transformation_matrices:
                aligned_image = self.align_image_from_path(image_path, channel)
                aligned_rgb = cv2.cvtColor(aligned_image, cv2.COLOR_BGR2RGB)
                axes[1, i].imshow(aligned_rgb)
                axes[1, i].set_title(f'对齐后 {channel} ({self.target_size[0]}×{self.target_size[1]})')
                axes[1, i].axis('off')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def save_calibration(self, file_path: str):
        """
        保存标定数据
        
        Args:
            file_path: 保存文件路径
        """
        calibration_data = {
            'target_size': self.target_size,
            'calibration_points': {k: v.tolist() for k, v in self.calibration_points.items()},
            'target_points': self.target_points.tolist()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(calibration_data, f, indent=2, ensure_ascii=False)
        
        print(f"标定数据已保存到: {file_path}")
    
    def load_calibration(self, file_path: str):
        """
        加载标定数据
        
        Args:
            file_path: 标定文件路径
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            calibration_data = json.load(f)
        
        self.target_size = tuple(calibration_data['target_size'])
        self.target_points = np.array(calibration_data['target_points'], dtype=np.float32)
        
        for channel, points in calibration_data['calibration_points'].items():
            self.set_calibration_points(channel, points)
        
        print(f"标定数据已从 {file_path} 加载")
    
    def create_composite_image(self, aligned_images: Dict[str, np.ndarray], 
                             weights: Dict[str, float] = None):
        """
        创建多通道合成图像
        
        Args:
            aligned_images: 对齐后的图像字典
            weights: 每个通道的权重
            
        Returns:
            合成图像
        """
        if weights is None:
            weights = {channel: 1.0/len(aligned_images) for channel in aligned_images.keys()}
        
        composite = np.zeros((self.target_size[1], self.target_size[0], 3), dtype=np.float32)
        
        for channel, image in aligned_images.items():
            weight = weights.get(channel, 1.0/len(aligned_images))
            composite += image.astype(np.float32) * weight
        
        composite = np.clip(composite, 0, 255).astype(np.uint8)
        return composite


def main():
    """示例使用方法"""
    
    # 创建对齐器
    aligner = MultiCameraAlignment(target_size=(800, 600))
    
    # 图像目录
    base_dir = r"d:\College\Python_project\4Project\SLS\images"
    input_dirs = {
        'CH1': os.path.join(base_dir, 'CH1'),
        'CH2': os.path.join(base_dir, 'CH2'),
        'CH3': os.path.join(base_dir, 'CH3')
    }
    
    # 检查并进行交互式标定
    calibration_file = "camera_calibration.json"
    
    if os.path.exists(calibration_file):
        print("加载已有标定数据...")
        aligner.load_calibration(calibration_file)
    else:
        print("开始交互式标定...")
        
        # 为每个通道选择一张用于标定的图像
        for channel, input_dir in input_dirs.items():
            if os.path.exists(input_dir):
                # 找到第一张图像用于标定
                image_files = []
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
                    image_files.extend(Path(input_dir).glob(ext))
                    if image_files:
                        break
                
                if image_files:
                    print(f"\n标定通道 {channel}")
                    aligner.interactive_calibration(str(image_files[0]), channel)
                else:
                    print(f"警告: 通道 {channel} 目录中没有找到图像文件")
        
        # 保存标定数据
        aligner.save_calibration(calibration_file)
    
    # 批量处理图像
    output_dir = "aligned_images"
    print(f"\n开始批量对齐图像到 {output_dir}...")
    aligner.batch_align_images(input_dirs, output_dir)
    
    # 可视化结果
    sample_images = {}
    for channel, input_dir in input_dirs.items():
        if os.path.exists(input_dir):
            image_files = list(Path(input_dir).glob('*.jpg'))
            if not image_files:
                image_files = list(Path(input_dir).glob('*.png'))
            if image_files:
                sample_images[channel] = str(image_files[0])
    
    if sample_images:
        print("\n生成对齐可视化...")
        aligner.visualize_alignment(sample_images, "alignment_visualization.png")
    
    print("\n处理完成！")


if __name__ == "__main__":
    main()