# 三摄像头图像对齐指南

## 概述
这个工具可以将来自三个不同位置摄像头的图像对齐到统一的800×600尺寸，使用四个标定点进行透视变换。

## 工作原理

### 1. 透视变换
- 使用四个标定点定义源图像中的感兴趣区域
- 通过透视变换将这个区域映射到800×600的标准尺寸
- 确保三个摄像头看到的同一区域在对齐后完全重合

### 2. 标定点要求
- **数量**: 必须是4个点
- **顺序**: 左上角 → 右上角 → 右下角 → 左下角
- **位置**: 应该选择容易识别且稳定的特征点
- **一致性**: 三个摄像头的标定点应该对应同一物理区域的四个角

## 使用步骤

### 第一步：准备工作
1. 确保三个摄像头的图像都保存在对应目录中：
   - `SLS/images/CH1/` - 第一个摄像头
   - `SLS/images/CH2/` - 第二个摄像头  
   - `SLS/images/CH3/` - 第三个摄像头

### 第二步：运行标定
```bash
cd d:\College\Python_project\4Project\SLS\DataAnalysis
python 标定.py
```

### 第三步：交互式标定
1. 程序会依次显示每个摄像头的图像
2. 按顺序点击四个标定点（左上→右上→右下→左下）
3. 每个点击会在图像上显示绿色圆圈和编号
4. 完成4个点后按任意键继续下一个摄像头

### 第四步：选择操作
- **选项1**: 批量对齐所有图像
- **选项2**: 测试单张图像对齐效果
- **选项3**: 生成对齐效果对比图

## 文件说明

### 核心文件
- `multi_camera_alignment.py` - 主要的对齐算法类
- `标定.py` - 主程序入口，提供完整的标定和处理流程
- `alignment_demo.py` - 演示脚本，包含各种使用示例

### 输出文件
- `camera_calibration.json` - 保存的标定数据
- `aligned_images_800x600/` - 对齐后的图像目录
- `alignment_comparison.png` - 对齐效果对比图

## 标定技巧

### 选择好的标定点
1. **明显特征**: 选择边角分明、容易识别的点
2. **稳定性**: 避免选择可能移动或变化的物体
3. **分布均匀**: 四个点应该尽量覆盖整个感兴趣区域
4. **对应关系**: 确保三个摄像头的标定点对应同一物理位置

### 常见标定点选择
- 工作台的四个角
- 固定标记物的四个角
- 设备边框的四个角点
- 预先放置的标定板四角

## 高级用法

### 手动设置标定点
如果你已经知道标定点坐标，可以直接在代码中设置：

```python
from multi_camera_alignment import MultiCameraAlignment

aligner = MultiCameraAlignment(target_size=(800, 600))

# 手动设置标定点 [左上, 右上, 右下, 左下]
aligner.set_calibration_points('CH1', [(100, 150), (500, 160), (480, 400), (120, 390)])
aligner.set_calibration_points('CH2', [(80, 120), (520, 140), (510, 420), (90, 400)])
aligner.set_calibration_points('CH3', [(110, 140), (490, 150), (470, 380), (130, 370)])
```

### 批量处理自定义目录
```python
input_dirs = {
    'CAM1': 'path/to/camera1/images',
    'CAM2': 'path/to/camera2/images', 
    'CAM3': 'path/to/camera3/images'
}

aligner.batch_align_images(input_dirs, 'output_directory')
```

### 创建合成图像
```python
# 对齐后的图像
aligned_images = {
    'CH1': aligner.align_image_from_path('image1.jpg', 'CH1'),
    'CH2': aligner.align_image_from_path('image2.jpg', 'CH2'),
    'CH3': aligner.align_image_from_path('image3.jpg', 'CH3')
}

# 创建加权合成图像
weights = {'CH1': 0.4, 'CH2': 0.3, 'CH3': 0.3}
composite = aligner.create_composite_image(aligned_images, weights)
```

## 故障排除

### 常见问题
1. **图像路径错误**: 检查图像目录是否存在且包含图像文件
2. **标定点不准确**: 重新进行交互式标定
3. **内存不足**: 处理大量图像时可能需要分批处理
4. **变换矩阵奇异**: 检查标定点是否共线或过于接近

### 调试技巧
1. 使用单张图像测试功能验证标定效果
2. 查看对齐效果对比图检查视觉质量
3. 检查标定数据文件确认标定点坐标

## 扩展功能
- 支持不同的目标尺寸
- 可以保存和加载标定数据
- 提供可视化验证功能
- 支持图像合成和融合
- 批量处理大量图像