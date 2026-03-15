#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三摄像头图像对齐标定工具
使用四个标定点进行透视变换，将三个摄像头的图像统一对齐到800×600
"""

from multi_camera_alignment import MultiCameraAlignment
import os

def main():
    """主程序入口"""
    
    print("=== 三摄像头图像对齐标定 ===")
    print("目标尺寸: 800×600")
    print()
    
    # 创建对齐器
    aligner = MultiCameraAlignment(target_size=(800, 600))
    
    # 图像路径设置
    base_dir = r"d:\College\Python_project\4Project\SLS\images"
    channels = ['CH1', 'CH2', 'CH3']
    
    # 检查是否有已保存的标定数据
    calibration_file = "camera_calibration.json"
    
    if os.path.exists(calibration_file):
        choice = input("发现已有标定文件，是否重新标定？(y/n): ").lower()
        if choice != 'y':
            aligner.load_calibration(calibration_file)
            print("已加载标定数据")
        else:
            # 重新标定
            perform_calibration(aligner, base_dir, channels)
            aligner.save_calibration(calibration_file)
    else:
        # 首次标定
        perform_calibration(aligner, base_dir, channels)
        aligner.save_calibration(calibration_file)
    
    # 处理选项
    print("\n请选择操作:")
    print("1. 批量对齐所有图像")
    print("2. 对齐单张图像测试")
    print("3. 查看对齐效果")
    
    choice = input("请输入选择 (1/2/3): ").strip()
    
    if choice == "1":
        batch_align_all(aligner, base_dir, channels)
    elif choice == "2":
        test_single_image(aligner, base_dir, channels)
    elif choice == "3":
        show_alignment_result(aligner, base_dir, channels)
    else:
        print("无效选择")

def perform_calibration(aligner, base_dir, channels):
    """执行标定过程"""
    
    print("开始交互式标定...")
    print("操作说明：")
    print("- 请按顺序点击四个标定点：左上 → 右上 → 右下 → 左下")
    print("- 点击完成后按任意键继续")
    print()
    
    for channel in channels:
        channel_dir = os.path.join(base_dir, channel)
        
        if not os.path.exists(channel_dir):
            print(f"警告: 目录 {channel_dir} 不存在，跳过")
            continue
        
        # 找第一张可用的图像
        image_files = []
        for ext in ['jpg', 'jpeg', 'png', 'bmp']:
            image_files.extend([f for f in os.listdir(channel_dir) 
                              if f.lower().endswith(f'.{ext}')])
            if image_files:
                break
        
        if not image_files:
            print(f"警告: {channel} 目录中没有找到图像文件")
            continue
        
        image_path = os.path.join(channel_dir, image_files[0])
        
        print(f"\n=== 标定 {channel} ===")
        print(f"使用图像: {image_files[0]}")
        
        try:
            aligner.interactive_calibration(image_path, channel)
            print(f"{channel} 标定完成")
        except Exception as e:
            print(f"标定 {channel} 时出错: {e}")

def batch_align_all(aligner, base_dir, channels):
    """批量对齐所有图像"""
    
    input_dirs = {}
    for channel in channels:
        channel_dir = os.path.join(base_dir, channel)
        if os.path.exists(channel_dir):
            input_dirs[channel] = channel_dir
    
    if not input_dirs:
        print("没有找到可处理的图像目录")
        return
    
    output_dir = "aligned_images_800x600"
    
    print(f"\n开始批量处理到目录: {output_dir}")
    print("这可能需要一些时间...")
    
    aligner.batch_align_images(input_dirs, output_dir)
    print("批量处理完成!")

def test_single_image(aligner, base_dir, channels):
    """测试单张图像对齐"""
    
    import cv2
    
    print("\n=== 单张图像测试 ===")
    
    for channel in channels:
        channel_dir = os.path.join(base_dir, channel)
        
        if not os.path.exists(channel_dir) or channel not in aligner.transformation_matrices:
            continue
        
        # 找第一张图像
        image_files = [f for f in os.listdir(channel_dir) 
                      if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        
        if image_files:
            test_file = os.path.join(channel_dir, image_files[0])
            
            print(f"测试 {channel}: {image_files[0]}")
            
            # 读取原始图像
            original = cv2.imread(test_file)
            
            # 对齐图像
            aligned = aligner.align_image_from_path(test_file, channel)
            
            # 显示对比
            cv2.imshow(f'{channel} - 原始图像', original)
            cv2.imshow(f'{channel} - 对齐后 (800x600)', aligned)
            
            print(f"原始尺寸: {original.shape[1]}×{original.shape[0]}")
            print(f"对齐尺寸: {aligned.shape[1]}×{aligned.shape[0]}")
            
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            
            break

def show_alignment_result(aligner, base_dir, channels):
    """显示对齐效果"""
    
    sample_images = {}
    
    for channel in channels:
        channel_dir = os.path.join(base_dir, channel)
        
        if os.path.exists(channel_dir):
            image_files = [f for f in os.listdir(channel_dir) 
                          if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
            
            if image_files:
                sample_images[channel] = os.path.join(channel_dir, image_files[0])
    
    if sample_images:
        print("生成对齐效果图...")
        aligner.visualize_alignment(sample_images, "alignment_comparison.png")
        print("对齐效果图已保存为: alignment_comparison.png")
    else:
        print("没有找到可用的图像文件")

if __name__ == "__main__":
    main()