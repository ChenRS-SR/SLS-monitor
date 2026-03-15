#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FOTRIC 628ch 红外热像仪集成类
基于官方 SDK (StreamSDK / restc / Radiation) 的 Python 封装。

当前实现提供以下能力：
- 加载 SDK 动态库 (若缺失自动回退到模拟模式)
- 通过 REST API 获取设备基础信息与温度 LUT
- 管理数据采集线程，实时推送温度帧
- 暴露与 IR8062Device 兼容的公开接口，方便上层无缝切换

提示：
- 真机采集依赖 Windows 平台及 SDK DLL 文件。
- 若 DLL 或设备不可用，类会自动启用模拟模式，以便流程联调。
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, Optional, Tuple, List

import numpy as np
import requests

# 动态导入配置文件
try:
    from ..config.fotric_config import API_URLS, FOTRIC_CONFIG
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from config.fotric_config import API_URLS, FOTRIC_CONFIG

# 流句柄类型定义
StreamHandle = ctypes.c_void_p


class StreamBuffer(ctypes.Structure):
    """流缓冲区结构体"""
    _fields_ = [
        ("buf_ptr", ctypes.c_void_p),   # 缓冲区指针
        ("buf_size", ctypes.c_uint),    # 缓冲区大小
        ("buf_pts", ctypes.c_uint),     # 缓冲区时间戳
    ]


@dataclass
class ThermalFrame:
    """热成像帧数据结构"""
    frame: np.ndarray       # 温度帧数据
    timestamp: datetime     # 时间戳
    frame_id: int          # 帧ID
    temp_min: float        # 最低温度
    temp_max: float        # 最高温度
    temp_avg: float        # 平均温度


class Fotric628CHDevice:
    """FOTRIC 628ch 红外热像仪设备类"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or FOTRIC_CONFIG
        self.logger = logging.getLogger("Fotric628CHDevice")
        self.logger.setLevel(logging.DEBUG)  # 明确设置为DEBUG级别

        # 网络连接配置
        network = self.config.get("network", {})
        self.ip_address = network.get("ip_address", "192.168.1.100")
        self.command_port = network.get("command_port", 10080)
        self.stream_port = network.get("stream_port", 10081)
        self.username = network.get("username", "admin")
        self.password = network.get("password", "123456")
        self.connection_timeout = network.get("connection_timeout", 5.0)

        # 传感器配置参数
        sensor_cfg = self.config.get("sensor", {})
        self.width = sensor_cfg.get("width", 640)
        self.height = sensor_cfg.get("height", 480)
        self.frame_rate = sensor_cfg.get("frame_rate", 25)

        # 设备状态标记
        self.connected = False
        self.streaming = False
        self._simulation_enabled = self.config.get("simulation", {}).get("enabled", False)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frame_queue: Deque[ThermalFrame] = deque(maxlen=self.config.get("advanced", {}).get("stream_buffer_count", 10))
        self._latest_frame: Optional[ThermalFrame] = None
        self._frame_counter = 0

        # 温度查找表相关
        self._lut: Optional[np.ndarray] = None
        self._lut_from = 0
        self._lut_to = 0
        self._factory_lut: Optional[List[Dict]] = None  # 原始工厂LUT
        self._current_lut_index = 0  # 当前LUT索引
        self._corrected_lut: Optional[np.ndarray] = None  # 修正后的LUT
        
        # 环境参数（用于LUT修正）
        self._emissivity = 0.97
        self._humidity = 0.5
        self._reflect_temp = 20.0
        self._ambient_temp = 20.0
        self._distance = 1.0

        # SDK 动态库句柄
        self._streamsdk = None
        self._restsdk = None
        self._radiation = None

        self._load_sdk_libraries()

    # ------------------------------------------------------------------
    # SDK 初始化
    # ------------------------------------------------------------------
    def _load_sdk_libraries(self):
        sdk_cfg = self.config.get("sdk", {})
        # 更新SDK搜索路径，指向新的Fotric_628ch/sdk目录
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Fotric_628ch", "sdk"))

        def _load_library(filename: str) -> Optional[ctypes.WinDLL]:
            """加载动态库文件"""
            search_paths = [
                filename,  # 当前工作目录
                os.path.join(base_dir, filename),  # Fotric_628ch/sdk目录
                os.path.join(os.getcwd(), filename),  # 当前工作目录
                os.path.join(os.path.dirname(__file__), "..", "sdk", filename),  # 相对路径sdk目录
                os.path.join(os.path.dirname(__file__), "..", "Fotric_628ch", "sdk", filename),  # Fotric_628ch/sdk目录
                os.path.join(os.path.dirname(__file__), filename),  # devices目录
            ]
            
            self.logger.debug(f"尝试加载库文件: {filename}")
            for path in search_paths:
                self.logger.debug(f"  搜索路径: {path}")
                if os.path.exists(path):
                    self.logger.debug(f"  文件存在，尝试加载...")
                    try:
                        dll = ctypes.WinDLL(path)
                        self.logger.info(f"成功加载 {filename} 从 {path}")
                        return dll
                    except OSError as e:
                        self.logger.debug(f"  加载失败: {e}")
                else:
                    self.logger.debug(f"  文件不存在")
            
            self.logger.warning(f"无法找到或加载库文件: {filename}")
            return None

        try:
            self.logger.info("开始加载 FOTRIC SDK 动态库...")
            self._streamsdk = _load_library(sdk_cfg.get("dll_path", "StreamSDK.dll"))
            self._restsdk = _load_library(sdk_cfg.get("rest_dll_path", "restc.dll"))
            self._radiation = _load_library(sdk_cfg.get("radiation_dll_path", "Radiation.dll"))

            missing_libs = []
            if not self._streamsdk:
                missing_libs.append("StreamSDK.dll")
            if not self._restsdk:
                missing_libs.append("restc.dll")
            if not self._radiation:
                missing_libs.append("Radiation.dll")

            if missing_libs:
                raise OSError(f"缺少 FOTRIC SDK 动态库文件: {', '.join(missing_libs)}")

            self._initialize_streamsdk_functions()
            self._initialize_rest_sdk_functions()
            self.logger.info("FOTRIC SDK 库加载成功")
        except OSError as exc:
            self.logger.warning("无法加载 FOTRIC SDK (%s)，启用模拟模式", exc)
            self._simulation_enabled = True

    def _initialize_streamsdk_functions(self):
        if not self._streamsdk:
            return

        self._streamsdk.streamsdk_set_thread_pool_size.argtypes = [ctypes.c_int]
        self._streamsdk.streamsdk_set_thread_pool_size.restype = ctypes.c_int

        self._streamsdk.streamsdk_create_stream.argtypes = [ctypes.c_char_p, ctypes.c_ushort, ctypes.POINTER(StreamHandle)]
        self._streamsdk.streamsdk_create_stream.restype = ctypes.c_int

        self._streamsdk.streamsdk_destroy_stream.argtypes = [StreamHandle]
        self._streamsdk.streamsdk_destroy_stream.restype = ctypes.c_int

        self._streamsdk.streamsdk_start_stream.argtypes = [
            StreamHandle,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._streamsdk.streamsdk_start_stream.restype = ctypes.c_int

        self._streamsdk.streamsdk_stop_stream.argtypes = [StreamHandle]
        self._streamsdk.streamsdk_stop_stream.restype = ctypes.c_int

        self._streamsdk.streamsdk_grab_buffer.argtypes = [StreamHandle, ctypes.POINTER(StreamBuffer), ctypes.c_int]
        self._streamsdk.streamsdk_grab_buffer.restype = ctypes.c_int

    def _initialize_rest_sdk_functions(self):
        """初始化REST SDK函数签名"""
        if not self._restsdk:
            return
        
        try:
            # restc_set_authroization - 全局设置认证信息
            self._restsdk.restc_set_authroization.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            self._restsdk.restc_set_authroization.restype = ctypes.c_int
            
            # restc_create_connection
            self._restsdk.restc_create_connection.argtypes = [ctypes.c_char_p, ctypes.c_ushort]
            self._restsdk.restc_create_connection.restype = ctypes.c_void_p
            
            # restc_destroy_connection
            self._restsdk.restc_destroy_connection.argtypes = [ctypes.c_void_p]
            self._restsdk.restc_destroy_connection.restype = ctypes.c_int
            
            # restc_set_timeout
            self._restsdk.restc_set_timeout.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self._restsdk.restc_set_timeout.restype = ctypes.c_int
            
            # restc_get
            self._restsdk.restc_get.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, 
                                               ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
            self._restsdk.restc_get.restype = ctypes.c_int
            
            self.logger.debug("REST SDK函数签名设置完成")
            
        except Exception as e:
            self.logger.warning("REST SDK函数签名设置失败: %s", e)

    # ------------------------------------------------------------------
    # 设备连接与参数配置
    # ------------------------------------------------------------------
    def connect(self):
        if self._simulation_enabled:
            self.logger.info("FOTRIC 628ch 启动模拟模式")
            self.connected = True
            self._create_simulation_lut()
            return True

        try:
            self.logger.info("连接 FOTRIC 设备 %s", self.ip_address)
            if not self._authenticate():
                self.logger.error("FOTRIC 登录失败 (HTTP 认证错误)")
                return False

            # 尝试获取传感器尺寸，如果失败则使用默认值
            if not self._fetch_sensor_dimension():
                self.logger.warning("无法获取传感器尺寸，使用默认配置值")
                # 不返回False，继续初始化

            # 尝试更新LUT，如果失败则创建模拟LUT
            try:
                self._update_lut()
            except Exception as e:
                self.logger.warning("无法获取设备LUT，使用模拟LUT: %s", e)
                self._create_simulation_lut()

            self.connected = True
            self.logger.info("FOTRIC 628ch 连接成功：分辨率 %dx%d", self.width, self.height)
            return True
        except requests.RequestException as exc:
            self.logger.error("连接 FOTRIC 失败: %s", exc)
            return False

    def _authenticate(self):
        """设备认证 - 使用REST SDK全局认证"""
        try:
            # 首先尝试使用REST SDK进行全局认证
            if self._restsdk and hasattr(self._restsdk, 'restc_set_authroization'):
                username_bytes = self.username.encode('utf-8')
                password_bytes = self.password.encode('utf-8')
                
                result = self._restsdk.restc_set_authroization(username_bytes, password_bytes)
                if result == 0:  # EC_OK = 0
                    self.logger.info("REST SDK全局认证设置成功")
                else:
                    self.logger.warning("REST SDK全局认证设置失败，返回码: %d", result)
            
            # 验证认证是否成功 - 测试admin/info接口
            url = self._build_url(API_URLS["admin_info"])
            response = requests.get(url, timeout=self.connection_timeout, auth=(self.username, self.password))
            if response.status_code == 200:
                self.logger.info("FOTRIC 设备认证成功")
                return True
            elif response.status_code == 401:
                self.logger.error("认证失败：用户名或密码错误 (用户: %s)", self.username)
                return False
            else:
                self.logger.error("认证失败：HTTP状态码 %s", response.status_code)
                return False
        except requests.exceptions.ConnectTimeout:
            self.logger.error("连接超时：无法连接到设备 %s:%s", self.ip_address, self.command_port)
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error("连接错误：设备可能未开机或网络不通 %s:%s", self.ip_address, self.command_port)
            return False

    def _rest_sdk_get(self, url_path: str):
        """使用REST SDK执行GET请求"""
        if not self._restsdk:
            return -1, None
            
        try:
            # 创建连接
            ip_bytes = self.ip_address.encode('utf-8')
            connection = self._restsdk.restc_create_connection(ip_bytes, self.command_port)
            if not connection:
                self.logger.error("REST SDK连接创建失败")
                return -1, None
            
            # 设置超时
            timeout_ms = int(self.connection_timeout * 1000)
            self._restsdk.restc_set_timeout(connection, timeout_ms)
            
            # 准备缓冲区
            buffer_size = 10240  # 10KB缓冲区
            buffer = ctypes.create_string_buffer(buffer_size)
            length = ctypes.c_size_t(0)
            
            # 执行GET请求
            url_path_bytes = url_path.encode('utf-8')
            status_code = self._restsdk.restc_get(
                connection, 
                url_path_bytes, 
                None,  # headers
                buffer, 
                buffer_size, 
                ctypes.byref(length)
            )
            
            # 销毁连接
            self._restsdk.restc_destroy_connection(connection)
            
            # 解析响应
            if status_code == 200 and length.value > 0:
                response_data = buffer.value[:length.value].decode('utf-8')
                return status_code, response_data
            else:
                return status_code, None
                
        except Exception as e:
            self.logger.error("REST SDK GET请求失败: %s", e)
            return -1, None

    def _fetch_sensor_dimension(self):
        """获取传感器尺寸 - 使用官方推荐的方法"""
        # 根据C++参考代码，直接使用REST SDK获取传感器尺寸
        if self._restsdk:
            status_code, response_data = self._rest_sdk_get("/sensor/dimension")
            if status_code == 200 and response_data:
                try:
                    import json
                    payload = json.loads(response_data)
                    self.width = int(payload.get("w", self.width))
                    self.height = int(payload.get("h", self.height))
                    self.logger.info("成功获取传感器尺寸：%dx%d", self.width, self.height)
                    return True
                except Exception as e:
                    self.logger.warning("传感器尺寸响应解析失败: %s", e)
        
        # 如果REST SDK失败，记录日志但继续使用默认配置
        self.logger.info("使用配置文件默认传感器尺寸：%dx%d", self.width, self.height)
        return True  # 返回True，允许继续初始化

    def _update_lut(self):
        url_lut_index = self._build_url(API_URLS["sensor_lut"])
        response = requests.get(url_lut_index, timeout=self.connection_timeout, auth=(self.username, self.password))
        response.raise_for_status()
        lut_index = int(response.json())

        table_url = self._build_url(API_URLS["sensor_lut_table"].format(lut_index))
        response = requests.get(table_url, timeout=self.connection_timeout, auth=(self.username, self.password))
        response.raise_for_status()
        lut_table = response.json()

        lut_size = self.config.get("temperature", {}).get("lut_size", 65536)
        lut = np.zeros(lut_size, dtype=np.float32)
        from_value = lut_table[0]["r"]
        to_value = lut_table[0]["r"]

        for idx in range(len(lut_table) - 1):
            start = lut_table[idx]
            end = lut_table[idx + 1]
            r0, r1 = start["r"], end["r"]
            t0, t1 = start["t"], end["t"]
            if r1 == r0:
                continue
            temp_values = np.linspace(t0, t1, r1 - r0 + 1, dtype=np.float32)
            lut[r0 : r1 + 1] = temp_values
            to_value = r1

        lut[:from_value] = lut[from_value]
        lut[to_value + 1 :] = lut[to_value]
        self._lut = lut
        self._lut_from = from_value
        self._lut_to = to_value

    def _create_simulation_lut(self):
        lut_size = self.config.get("temperature", {}).get("lut_size", 65536)
        self._lut = np.linspace(-20.0, 150.0, lut_size, dtype=np.float32)
        self._lut_from = 0
        self._lut_to = lut_size - 1

    def _build_url(self, path: str):
        return f"http://{self.ip_address}:{self.command_port}{path}"

    # ------------------------------------------------------------------
    # 热成像数据采集
    # ------------------------------------------------------------------
    def start_stream(self):
        if not self.connected:
            self.logger.error("请先 connect() 再调用 start_stream()")
            return False
        if self.streaming:
            return True

        self._stop_event.clear()
        self._frame_queue.clear()
        target = self._run_simulation if self._simulation_enabled else self._run_stream_loop
        self._thread = threading.Thread(target=target, name="FotricStream", daemon=True)
        self._thread.start()
        self.streaming = True
        self.logger.info("FOTRIC 628ch 热像流已启动 (%s)", "模拟模式" if self._simulation_enabled else "SDK模式")
        return True

    def stop_stream(self):
        if not self.streaming:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.streaming = False

    def _run_simulation(self):
        sim_cfg = self.config.get("simulation", {})
        base_temp = sim_cfg.get("base_temperature", 25.0)
        variation = sim_cfg.get("temperature_variation", 10.0)
        noise_level = sim_cfg.get("noise_level", 0.2)
        hotspot_count = sim_cfg.get("hotspot_count", 3)
        update_rate = sim_cfg.get("update_rate", 25)
        interval = 1.0 / max(update_rate, 1)

        while not self._stop_event.is_set():
            frame = self._generate_simulation_frame(base_temp, variation, noise_level, hotspot_count)
            self._push_frame(frame)
            time.sleep(interval)

    def _generate_simulation_frame(self, base: float, variation: float, noise: float, hotspots: int):
        y_coords, x_coords = np.ogrid[: self.height, : self.width]
        cx, cy = self.width // 2, self.height // 2
        radius = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
        frame = base + variation * np.exp(-radius / (0.35 * max(self.width, self.height)))
        frame += np.random.normal(0.0, noise, frame.shape)

        for idx in range(hotspots):
            hx = int(self.width * (idx + 1) / (hotspots + 1))
            hy = int(self.height * (idx + 1) / (hotspots + 1))
            if 0 <= hx < self.width and 0 <= hy < self.height:
                frame[hy, hx] += variation * 1.5

        return frame.astype(np.float32)

    def _run_stream_loop(self):
        if not self._streamsdk:
            self.logger.error("StreamSDK 未加载，无法启动真实数据流")
            return

        self._streamsdk.streamsdk_set_thread_pool_size(self.config.get("sdk", {}).get("thread_pool_size", 4))
        stream_handle = StreamHandle()
        create_code = self._streamsdk.streamsdk_create_stream(self.ip_address.encode("ascii"), self.stream_port, ctypes.byref(stream_handle))
        if create_code != 0:
            self.logger.error("创建流失败，错误码 %s", create_code)
            return

        try:
            max_packet = self._get_stream_packet_size()
            self.logger.info("获取到数据流包大小: %d 字节", max_packet)
            start_code = self._streamsdk.streamsdk_start_stream(
                stream_handle,
                "/video/raw".encode("ascii"),  # 修正为C++代码中的路径
                max_packet,
                None,
                None,
            )
            if start_code != 0:
                self.logger.error("启动流失败，错误码 %s", start_code)
                return

            buffer_size = max_packet * 2
            raw_buffer = ctypes.create_string_buffer(buffer_size)
            stream_buffer = StreamBuffer(ctypes.cast(raw_buffer, ctypes.c_void_p), buffer_size, 0)
            timeout_ms = int(1000 / max(self.frame_rate, 1))

            while not self._stop_event.is_set():
                result = self._streamsdk.streamsdk_grab_buffer(stream_handle, ctypes.byref(stream_buffer), timeout_ms)
                if result != 0:
                    if result == 2:  # STREAMSDK_EC_TIMEOUT
                        self.logger.debug("数据流获取超时")
                    else:
                        self.logger.debug("数据流获取失败，错误码: %d", result)
                    continue
                
                self.logger.debug("成功获取数据帧，大小: %d 字节", stream_buffer.buf_size)
                frame = self._convert_raw_to_temperature(raw_buffer, stream_buffer.buf_size)
                if frame is not None:
                    self._push_frame(frame)
                else:
                    self.logger.debug("数据转换失败")
        finally:
            self._streamsdk.streamsdk_stop_stream(stream_handle)
            self._streamsdk.streamsdk_destroy_stream(stream_handle)

    def _get_stream_packet_size(self) -> int:
        # 根据C++代码，使用正确的URL路径
        url = self._build_url("/stream/video/raw")  # 直接使用正确的路径
        try:
            response = requests.get(url, timeout=self.connection_timeout, auth=(self.username, self.password))
            response.raise_for_status()
            payload = response.json()
            packet_size = int(payload.get("max-packet-size", self.config.get("sdk", {}).get("max_packet_size", 65536)))
            self.logger.debug("从设备获取到包大小: %d", packet_size)
            return packet_size
        except Exception as e:
            # 如果获取失败，使用默认值
            default_size = self.config.get("sdk", {}).get("max_packet_size", 65536)
            self.logger.warning("无法获取流包大小，使用默认值 %d: %s", default_size, e)
            return default_size

    def _convert_raw_to_temperature(self, raw_buffer: ctypes.Array, buf_size: int) -> Optional[np.ndarray]:
        """将全辐射流转换为实时温度数据 - 实现官方文档步骤4"""
        pixel_count = self.width * self.height
        expected_bytes = pixel_count * 2  # uint16_t = 2字节
        if buf_size < expected_bytes:
            self.logger.debug("缓冲区大小不足: %d < %d", buf_size, expected_bytes)
            return None

        try:
            # 从缓冲区解析uint16数据（AD值）
            raw_array = np.frombuffer(raw_buffer[:expected_bytes], dtype=np.uint16, count=pixel_count)
            raw_array = raw_array.reshape((self.height, self.width))
            
            # 如果没有修正后的LUT，使用基础转换
            if self._lut is None:
                self.logger.debug("没有LUT表，使用线性转换")
                # 简单的线性转换作为备用方案
                return (raw_array.astype(np.float32) - 32768) * 0.04  # 假设的线性关系
            
            # 使用修正后的LUT转换为温度值
            temp_array = np.zeros_like(raw_array, dtype=np.float32)
            
            # 处理超出LUT范围的值
            mask_low = raw_array < self._lut_from
            if np.any(mask_low):
                temp_array[mask_low] = self._lut[0]
            
            mask_high = raw_array > self._lut_to  
            if np.any(mask_high):
                temp_array[mask_high] = self._lut[-1]
            
            # 正常范围内的值使用LUT查找
            mask_normal = (raw_array >= self._lut_from) & (raw_array <= self._lut_to)
            if np.any(mask_normal):
                indices = raw_array[mask_normal] - self._lut_from
                # 确保索引在有效范围内
                indices = np.clip(indices, 0, len(self._lut) - 1)
                temp_array[mask_normal] = self._lut[indices]
            
            return temp_array
            
        except Exception as e:
            self.logger.error("温度转换失败: %s", e)
            return None
        
        return temp_array

    def _push_frame(self, frame: np.ndarray):
        timestamp = datetime.now()
        self._frame_counter += 1
        container = ThermalFrame(
            frame=frame,
            timestamp=timestamp,
            frame_id=self._frame_counter,
            temp_min=float(frame.min()),
            temp_max=float(frame.max()),
            temp_avg=float(frame.mean()),
        )
        self._frame_queue.append(container)
        self._latest_frame = container

    def get_point_temperature(self, x: int, y: int) -> Optional[float]:
        """获取图像上特定点的温度 - 参考C++代码GetTemperature方法"""
        if not self.connected:
            return None
            
        # 方法1：从实时数据中获取
        if self._latest_frame and self._latest_frame.frame is not None:
            if 0 <= x < self.width and 0 <= y < self.height:
                return float(self._latest_frame.frame[y, x])
        
        # 方法2：通过REST API获取（参考C++代码）
        try:
            if self._restsdk:
                status_code, response = self._rest_sdk_get(f"/isp/t?x={x}&y={y}")
                if status_code == 200 and response:
                    import json
                    data = json.loads(response)
                    return float(data["t"])
            
            # 备用方法：使用requests
            url = self._build_url(f"/isp/t?x={x}&y={y}")
            response = requests.get(url, timeout=self.connection_timeout, auth=(self.username, self.password))
            if response.status_code == 200:
                return float(response.json()["t"])
                
        except Exception as e:
            self.logger.debug("获取点温度失败: %s", e)
        
        return None
    
    def update_environment_parameters(self, emissivity: float = None, humidity: float = None, 
                                    reflect_temp: float = None, ambient_temp: float = None, 
                                    distance: float = None):
        """更新环境参数并重新计算LUT"""
        params_changed = False
        
        if emissivity is not None and emissivity != self._emissivity:
            self._emissivity = emissivity
            params_changed = True
            
        if humidity is not None and humidity != self._humidity:
            self._humidity = humidity
            params_changed = True
            
        if reflect_temp is not None and reflect_temp != self._reflect_temp:
            self._reflect_temp = reflect_temp
            params_changed = True
            
        if ambient_temp is not None and ambient_temp != self._ambient_temp:
            self._ambient_temp = ambient_temp
            params_changed = True
            
        if distance is not None and distance != self._distance:
            self._distance = distance
            params_changed = True
        
        # 如果参数变化，重新计算LUT
        if params_changed and self._factory_lut:
            self.logger.info("环境参数更新，重新计算LUT")
            corrected_lut = self._correct_factory_lut(self._factory_lut)
            self._build_lookup_table(corrected_lut)

    # ------------------------------------------------------------------
    # 公开接口（与 IR8062Device 兼容）
    # ------------------------------------------------------------------
    def get_thermal_data(self):
        return None if self._latest_frame is None else self._latest_frame.frame

    def get_latest_frame(self):
        if not self._latest_frame:
            return None
        return {
            "frame": self._latest_frame.frame,
            "timestamp": self._latest_frame.timestamp,
            "frame_id": self._latest_frame.frame_id,
            "temp_min": self._latest_frame.temp_min,
            "temp_max": self._latest_frame.temp_max,
            "temp_avg": self._latest_frame.temp_avg,
        }

    def get_temperature_stats(self):
        if not self._latest_frame:
            return None
        return {
            "min_temp": self._latest_frame.temp_min,
            "max_temp": self._latest_frame.temp_max,
            "avg_temp": self._latest_frame.temp_avg,
            "frame_id": self._latest_frame.frame_id,
            "timestamp": self._latest_frame.timestamp,
        }

    def get_current_temp_range(self) -> Tuple[Optional[float], Optional[float]]:
        if not self._latest_frame:
            return (None, None)
        return (self._latest_frame.temp_min, self._latest_frame.temp_max)

    def initialize(self) -> bool:
        return self.connected

    def check_status(self) -> bool:
        return self.connected and self.streaming

    def save_current_frame(self, filepath: str):
        if not self._latest_frame:
            return False
        try:
            frame = self._latest_frame.frame
            temp_min = frame.min()
            temp_max = frame.max()
            normalized = (frame - temp_min) / max(temp_max - temp_min, 1e-6)
            image = (normalized * 255).astype(np.uint8)
            if image.ndim == 2:
                image = np.stack([image] * 3, axis=-1)
            import cv2

            success = cv2.imwrite(filepath, image)
            return bool(success)
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.error("保存 FOTRIC 帧失败: %s", exc)
            return False

    def disconnect(self):
        self.stop_stream()
        self.connected = False

    # ------------------------------------------------------------------
    # 工具与辅助方法
    # ------------------------------------------------------------------
    def __del__(self):
        try:
            self.disconnect()
        except Exception:  # pylint: disable=broad-except
            pass


# 向后兼容的类别名
class FotricDevice(Fotric628CHDevice):
    """
FOTRIC 设备类别名，用于向后兼容
    """
    pass