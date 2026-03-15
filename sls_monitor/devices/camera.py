"""
Camera device control class
"""

import cv2
import numpy as np
from datetime import datetime
import threading
from ..config.camera_config import CAMERA_CONFIG, IMAGE_CONFIG, MAX_CAMERA_ERRORS, MAX_RECONNECT_ATTEMPTS
from ..utils.image_utils import resize_image_keep_aspect

class CameraDevice:
    def __init__(self, camera_index, camera_name="Main Camera"):
        self.camera_index = camera_index
        self.camera_name = camera_name
        self.camera = None
        self.error_count = 0
        self.reconnect_attempts = 0
        self.is_connected = False
        self.lock = threading.Lock()
        self.rotate_180 = True  # 默认启用180度旋转
    
    @staticmethod
    def scan_available_cameras(max_index=10):
        """扫描所有可用的摄像头索引"""
        print(f"🔍 正在扫描系统中所有可用的摄像头（索引 0-{max_index}）...")
        available_cameras = []
        
        backends_to_try = [
            (cv2.CAP_DSHOW, "DSHOW"),
            (cv2.CAP_MSMF, "MSMF"),
        ]
        
        for backend_id, backend_name in backends_to_try:
            print(f"🔍 使用 {backend_name} 后端扫描...")
            for i in range(max_index + 1):
                try:
                    cap = cv2.VideoCapture(i, backend_id)
                    if cap.isOpened():
                        # 尝试读取一帧来验证摄像头是否真正可用
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            # 获取摄像头信息
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            
                            camera_info = {
                                'index': i,
                                'backend': backend_name,
                                'width': width,
                                'height': height,
                                'fps': fps,
                                'working': True
                            }
                            
                            # 检查是否已经在列表中（避免重复）
                            if not any(cam['index'] == i for cam in available_cameras):
                                available_cameras.append(camera_info)
                                print(f"✅ 索引 {i}: {width}x{height} @{fps:.1f}fps ({backend_name})") 
                        else:
                            print(f"⚠️ 索引 {i}: 可打开但无法读取帧 ({backend_name})")
                    cap.release()
                except Exception as e:
                    # 静默失败，继续扫描
                    pass
            
            if available_cameras:
                break  # 如果已经找到摄像头，不需要尝试其他后端
        
        print(f"📊 扫描完成，共发现 {len(available_cameras)} 个可用摄像头")
        return available_cameras

    def connect(self):
        """Connect to the camera"""
        # 尝试多种后端和索引
        backends_to_try = [
            cv2.CAP_DSHOW,
            cv2.CAP_MSMF,
            cv2.CAP_ANY
        ]
        
        # 首先尝试指定的camera_index，然后尝试其他常见索引
        if "主" in self.camera_name:
            # 主摄像头：先尝试指定索引，再尝试0, 1
            indices_to_try = [self.camera_index] + [i for i in [0, 1] if i != self.camera_index]
        else:
            # 副摄像头：先尝试指定索引，再尝试1, 2, 0
            indices_to_try = [self.camera_index] + [i for i in [1, 2, 0] if i != self.camera_index]
            
        print(f"🔍 正在检测{self.camera_name}的可用索引...")
        
        for backend in backends_to_try:
            backend_name = {
                cv2.CAP_DSHOW: "DSHOW",
                cv2.CAP_MSMF: "MSMF", 
                cv2.CAP_ANY: "ANY"
            }.get(backend, "UNKNOWN")
            
            for index in indices_to_try:
                try:
                    print(f"📷 尝试索引 {index} 使用 {backend_name} 后端...")
                    self.camera = cv2.VideoCapture(index, backend)
                    
                    if self.camera.isOpened():
                        # 读取一帧测试
                        ret, frame = self.camera.read()
                        if ret and frame is not None:
                            # Set camera parameters
                            self.camera.set(cv2.CAP_PROP_FPS, CAMERA_CONFIG["fps"])
                            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                            
                            # 等待摄像头初始化
                            import time
                            time.sleep(0.5)
                            
                            # 读取几帧以确保摄像头已经准备好
                            for _ in range(3):
                                self.camera.read()
                                
                            self.camera_index = index  # 更新实际使用的索引
                            self.is_connected = True
                            self.error_count = 0
                            print(f"✅ {self.camera_name}连接成功（索引: {index}, 后端: {backend_name}）")
                            return True
                        else:
                            print(f"⚠️ 索引 {index} 打开但无法读取帧")
                            self.camera.release()
                    else:
                        print(f"❌ 索引 {index} 无法打开")
                        
                except Exception as e:
                    print(f"❌ 索引 {index} 尝试失败: {e}")
                    if self.camera:
                        self.camera.release()
                        
        print(f"❌ {self.camera_name}所有索引和后端都尝试失败")
        return False

    def disconnect(self):
        """Disconnect from the camera"""
        if self.camera is not None:
            self.camera.release()
            self.camera = None
            self.is_connected = False
            print(f"ℹ️ Disconnected from {self.camera_name}")

    def reconnect(self):
        """Attempt to reconnect to the camera"""
        print(f"🔄 Attempting to reconnect to {self.camera_name}...")
        self.disconnect()
        if self.reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            self.reconnect_attempts += 1
            if self.connect():
                self.reconnect_attempts = 0
                return True
            else:
                print(f"❌ Reconnection attempt {self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS} failed")
                return False
        else:
            print(f"❌ Maximum reconnection attempts reached for {self.camera_name}")
            return False

    def capture_frame(self):
        """Capture a frame from the camera"""
        if not self.is_connected or self.camera is None:
            print(f"[DEBUG] {self.camera_name}: 摄像头未连接")
            return None

        with self.lock:
            try:
                ret, frame = self.camera.read()
                if ret and frame is not None:
                    # 应用180度旋转（如果启用）
                    if self.rotate_180:
                        frame = cv2.rotate(frame, cv2.ROTATE_180)
                    
                    if hasattr(self, 'debug_enabled') and self.debug_enabled:
                        from ..utils.debug_utils import debug_frame
                        debug_frame(frame, self.camera_name)
                    self.error_count = 0
                    return frame
                else:
                    self.error_count += 1
                    print(f"[DEBUG] {self.camera_name}: 获取帧失败 (ret={ret})")
                    if self.error_count >= MAX_CAMERA_ERRORS:
                        print(f"⚠️ Multiple frame capture failures for {self.camera_name}")
                        self.reconnect()
                    return None
            except Exception as e:
                print(f"❌ Frame capture error: {e}")
                return None

    def get_display_frame(self):
        """Get a frame sized for display"""
        frame = self.capture_frame()
        if frame is not None:
            # 直接缩放到目标尺寸，不保持比例以避免黑边
            h, w = frame.shape[:2]
            target_w, target_h = IMAGE_CONFIG["display_width"], IMAGE_CONFIG["display_height"]
            
            # 直接缩放到目标尺寸
            resized_frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            return resized_frame
        return None

    def get_save_frame(self):
        """Get a frame sized for saving"""
        frame = self.capture_frame()
        if frame is not None:
            return resize_image_keep_aspect(
                frame,
                IMAGE_CONFIG["save_width"],
                IMAGE_CONFIG["save_height"]
            )
        return None

    def save_frame(self, save_path, prefix=""):
        """Save the current frame to a file"""
        # 统一增强：允许 save_path 既可以是目录也可以是完整文件路径
        # 兼容外部误传入包含 .png/.jpg 的完整路径
        import os
        try:
            frame = self.get_save_frame()
            if frame is None:
                print(f"[DEBUG] 获取保存帧失败 - 相机: {self.camera_name}")
                return None

            # 判断是否是文件路径（带扩展名）
            _, ext = os.path.splitext(save_path)
            is_file_path = ext.lower() in {'.png', '.jpg', '.jpeg', '.bmp'}

            if is_file_path:
                # 视为完整文件路径
                target_dir = os.path.dirname(save_path) or '.'
                os.makedirs(target_dir, exist_ok=True)
                final_path = save_path
            else:
                # 视为目录；需要构造文件名
                target_dir = save_path
                os.makedirs(target_dir, exist_ok=True)
                if not os.path.exists(target_dir):
                    print(f"[DEBUG] 保存目录创建失败: {target_dir}")
                    return None
                if prefix:
                    # 去掉可能重复传入的扩展
                    if prefix.lower().endswith('.png'):
                        prefix = prefix[:-4]
                    filename = f"{prefix}.png"
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{timestamp}.png"
                final_path = os.path.join(target_dir, filename)

            # 使用支持中文路径的保存方法
            try:
                # 方法1：尝试直接保存（适用于纯英文路径）
                success = cv2.imwrite(final_path, frame)
                if success:
                    #print(f"✅ 已成功保存图像到: {final_path}")
                    return final_path
                else:
                    # 方法2：使用编码方式处理中文路径
                    #print(f"[DEBUG] 直接保存失败，尝试中文路径兼容保存...")
                    # 获取文件扩展名
                    _, ext = os.path.splitext(final_path)
                    if not ext:
                        ext = '.png'
                    # 使用cv2.imencode编码图像
                    if ext.lower() == '.png':
                        encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
                    elif ext.lower() in ['.jpg', '.jpeg']:
                        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
                    else:
                        encode_param = []
                        
                    result, encimg = cv2.imencode(ext, frame, encode_param)
                    if result:
                        # 使用numpy保存到中文路径
                        encimg.tofile(final_path)
                        #print(f"✅ 已成功保存图像到（中文路径）: {final_path}")
                        return final_path
                    else:
                        print(f"❌ 图像编码失败: {final_path}")
                        return None
            except UnicodeEncodeError as e:
                print(f"[DEBUG] 路径编码错误: {e}")
                return None
            except Exception as e:
                print(f"[DEBUG] 保存过程异常: {e}")
                # 输出调试信息帮助定位问题
                try:
                    dir_path = os.path.dirname(final_path)
                    print(f"[DEBUG] 目录存在: {os.path.isdir(dir_path)}, 可写: {os.access(dir_path, os.W_OK)}")
                    print(f"[DEBUG] 文件路径长度: {len(final_path)}")
                    print(f"[DEBUG] 路径包含中文: {any(ord(c) > 127 for c in final_path)}")
                    print(f"[DEBUG] 图像尺寸: {frame.shape if frame is not None else 'None'}")
                except Exception as diag_error:
                    print(f"[DEBUG] 诊断信息获取失败: {diag_error}")
                return None
        except Exception as e:
            print(f"[DEBUG] 保存图像异常: {e}")
            return None

    def set_rotate_180(self, rotate):
        """设置是否启用180度旋转"""
        self.rotate_180 = rotate
        print(f"📷 {self.camera_name}: 180度旋转已{'启用' if rotate else '禁用'}")
    
    def get_rotate_180(self):
        """获取当前旋转状态"""
        return self.rotate_180
    
    def toggle_rotate_180(self):
        """切换180度旋转状态"""
        self.rotate_180 = not self.rotate_180
        print(f"📷 {self.camera_name}: 180度旋转已切换为{'启用' if self.rotate_180 else '禁用'}")
        return self.rotate_180

    def __del__(self):
        """Cleanup when the object is destroyed"""
        self.disconnect()