"""
IR8062红外传感器模块
实现基本的温度数据采集功能，支持实际硬件和模拟模式
"""

import time
import serial
import numpy as np
import cv2
import struct
import binascii
from typing import Optional, Tuple, Union
from ..config.ir8062_config import IR8062_CONFIG
try:
    import serial.tools.list_ports as list_ports
except Exception:  # pragma: no cover
    list_ports = None

class IR8062:
    def __init__(self,
                 simulation_mode: bool = False,
                 raw_probe_seconds: float = 0.0,
                 bootstrap_sequence=None,
                 transport=None):
        """
        初始化IR8062传感器
        
        Args:
            simulation_mode: 是否使用模拟模式
            raw_probe_seconds: 启动时原始字节探测秒数(不解析, 仅打印前缀)
            bootstrap_sequence: 引导指令序列 (例如 ["query:5", "delay:200", "auto"])
            transport: 预留外部传输层抽象(未来可支持 USB bulk 等)
        """
        self.config = IR8062_CONFIG
        # 如果未显式指定但配置里 mock_mode 启用，则自动进入模拟
        self.simulation_mode = simulation_mode or self.config.get("mock_mode", {}).get("enabled", False)
        self.serial = None  # underlying serial object (or transport.serial)
        self.frame_buffer = bytearray()
        self.last_frame = None
        self.connected = False
        self._bootstrap_done = False
        self._raw_probe_seconds = raw_probe_seconds or self.config.get("raw_probe_seconds", 0.0)
        self._bootstrap_sequence = bootstrap_sequence or self.config.get("bootstrap_sequence")
        # 统计信息
        self._total_bytes_read = 0
        self._read_calls = 0
        self._first_read_time = None
        self._last_read_time = None
        self._transport = transport  # 预留未来可插拔接口
        
        # 图像尺寸
        self.width = self.config["resolution"]["width"]
        self.height = self.config["resolution"]["height"]
        # 动态显示范围缓存（用于 auto_range）
        tr = self.config.get("temperature_range", {})
        self._disp_min = tr.get("min", 20.0)
        self._disp_max = tr.get("max", 40.0)
        
        # 调试开关 (需在硬件连接前初始化, 以便在 _connect 之后使用)
        self._debug_cfg = self.config.get("debug", {})
        self._debug_printed_intro = False
        self._debug_frame_count = 0
        # 保存最近帧元数据
        self.meta = {}
        # 空读次数计数，用于触发查询回退
        self._empty_reads = 0

        if not self.simulation_mode:
            self._init_hardware()

    # ---------------- initialization sequences -----------------
    def _init_hardware(self):
        self._connect()
        if not self.connected:
            return
        # 可选 DTR/RTS 激励
        if self.config.get("toggle_lines"):
            try:
                self.serial.dtr = False; self.serial.rts = False
                time.sleep(0.08)
                self.serial.dtr = True; self.serial.rts = True
                if self._debug_cfg.get("verbose"):
                    print("[IR8062][IO] toggled DTR/RTS")
            except Exception:  # pragma: no cover
                pass
        # 可选自动波特率探测
        if self.config.get("auto_baud"):
            self._attempt_auto_baud()
        # 引导序列（可指定多次 query / delay / auto）
        if self._bootstrap_sequence:
            self._run_bootstrap_sequence(self._bootstrap_sequence)
        else:
            # 默认直接尝试进入自动模式
            try:
                self._set_output_mode('auto')
            except Exception as _e:
                if self._debug_cfg.get("verbose"):
                    print(f"[IR8062][WARN] set auto mode failed: {_e}")
            time.sleep(0.15)
        self._bootstrap_done = True
        # 原始探测：在正式帧解析前采集原始字节
        if self._raw_probe_seconds > 0:
            self._raw_probe(self._raw_probe_seconds)

    def _run_bootstrap_sequence(self, seq):
        if self._debug_cfg.get("verbose"):
            print(f"[IR8062][BOOT] sequence={seq}")
        for step in seq:
            try:
                if isinstance(step, str):
                    low = step.lower()
                    if low.startswith("query:"):
                        n = int(low.split(":",1)[1])
                        for i in range(n):
                            self.query_once()
                            time.sleep(0.12)
                    elif low == "auto":
                        self.force_auto(); time.sleep(0.15)
                    elif low.startswith("delay:"):
                        # delay:ms
                        ms = int(low.split(":",1)[1])
                        time.sleep(ms/1000.0)
                    else:
                        if self._debug_cfg.get("verbose"):
                            print(f"[IR8062][BOOT] unknown step '{step}'")
                else:
                    if self._debug_cfg.get("verbose"):
                        print(f"[IR8062][BOOT] unsupported step type {type(step)}")
            except Exception as e:  # pragma: no cover
                if self._debug_cfg.get("verbose"):
                    print(f"[IR8062][BOOT] step '{step}' failed: {e}")

    def _raw_probe(self, seconds: float):
        if not self.serial or not self.serial.is_open:
            return
        if self._debug_cfg.get("verbose"):
            print(f"[IR8062][RAW] probing raw bytes for {seconds:.2f}s ...")
        start = time.time()
        collected = bytearray()
        next_report = start + 0.5
        while time.time() - start < seconds:
            waiting = self.serial.in_waiting
            if waiting:
                chunk = self.serial.read(waiting)
                collected.extend(chunk)
            else:
                # 读 1 字节以触发超时推进
                self.serial.read(1)
            if time.time() >= next_report:
                if self._debug_cfg.get("verbose"):
                    preview = ' '.join(f"{b:02X}" for b in collected[:32])
                    print(f"[IR8062][RAW] bytes={len(collected)} head={preview}")
                next_report += 0.5
        # 放回解析缓冲（不丢失）
        self.frame_buffer.extend(collected)
        if self._debug_cfg.get("verbose"):
            tail = ' '.join(f"{b:02X}" for b in collected[-16:])
            print(f"[IR8062][RAW] done total={len(collected)} last16={tail}")
        
        
    def _connect(self):
        """连接传感器"""
        # 首先尝试配置的端口
        ports_to_try = [self.config["port"]]
        
        # 如果配置端口失败，尝试自动发现
        if list_ports:
            available_ports = [p.device for p in list_ports.comports()]
            for port in available_ports:
                if port not in ports_to_try:
                    ports_to_try.append(port)
                    
        for port in ports_to_try:
            try:
                if self._debug_cfg.get("verbose"):
                    print(f"[IR8062][CONN] 尝试连接端口: {port}")
                    
                self.serial = serial.Serial(
                    port=port,
                    baudrate=self.config["baudrate"],
                    timeout=self.config["timeout"]
                )
                
                # 测试连接是否工作
                time.sleep(0.1)
                if self.serial.is_open:
                    self.config["port"] = port  # 更新成功的端口
                    self.connected = True
                    if self._debug_cfg.get("verbose"):
                        print(f"[IR8062][CONN] 成功连接到: {port}")
                    return True
                    
            except Exception as e:
                if self._debug_cfg.get("verbose"):
                    print(f"[IR8062][CONN] 端口 {port} 连接失败: {e}")
                continue
                
        print(f"连接IR8062失败: 所有端口都无法连接")
        self.connected = False
        return False

    # ---------------- command helpers -----------------
    def _build_command(self, cmd_type: int, value: int) -> bytes:
        checksum = (0xA5 + cmd_type + value) & 0xFF
        return bytes([0xA5, cmd_type, value, checksum])

    def _send_command(self, cmd: bytes, wait: float = 0.05):
        if not self.serial or not self.serial.is_open:
            return
        self.serial.write(cmd)
        self.serial.flush()
        time.sleep(wait)
        if self._debug_cfg.get("verbose"):
            print(f"[IR8062][CMD] sent: {' '.join(f'{b:02X}' for b in cmd)}")

    def _set_output_mode(self, mode: str):
        if mode == 'auto':
            cmd = self._build_command(0x35, 0x02)
        elif mode == 'query':
            cmd = self._build_command(0x35, 0x01)
        else:
            raise ValueError("Unknown mode")
        self._send_command(cmd)
        self._last_mode = mode

    def query_once(self):
        self._set_output_mode('query')

    def force_auto(self):
        self._set_output_mode('auto')

    # 波特率设置 (01=115200 02=921600 03=1500000)
    def set_baud(self, code: int):
        if code not in (1,2,3):
            raise ValueError("baud code must be 1/2/3")
        cmd = self._build_command(0x15, code)
        self._send_command(cmd)

    # 更新频率设置 (00=1Hz 01=2Hz 02=5Hz 03=8Hz)
    def set_rate(self, code: int):
        if code not in (0,1,2,3):
            raise ValueError("rate code must be 0..3")
        cmd = self._build_command(0x25, code)
        self._send_command(cmd)

    # 保存设置 (波特率/频率/模式/镜像/发射率)
    def save_settings(self):
        cmd = self._build_command(0x65, 0x01)
        self._send_command(cmd, wait=0.15)

    def _attempt_auto_baud(self):
        if not self.serial:
            return
        candidates = self.config.get("baud_candidates") or [self.config.get("baudrate", 1500000), 1500000, 921600, 115200]
        seen = set()
        for b in candidates:
            if b in seen:
                continue
            seen.add(b)
            try:
                if self.serial.baudrate != b:
                    self.serial.baudrate = b
                self._set_output_mode('auto')
                start = time.time()
                got = False
                while time.time() - start < 0.4:
                    self._read_into_buffer()
                    if len(self.frame_buffer) > 0:
                        got = True
                        break
                    time.sleep(0.02)
                if got:
                    if self._debug_cfg.get("verbose"):
                        print(f"[IR8062][AUTOBAUD] using baud {b}")
                    self.config["baudrate"] = b
                    return
            except Exception as e:  # pragma: no cover
                if self._debug_cfg.get("verbose"):
                    print(f"[IR8062][AUTOBAUD] baud {b} failed: {e}")
        if self._debug_cfg.get("verbose"):
            print("[IR8062][AUTOBAUD] no data on tested baud rates.")
            
    def _get_sim_params(self):
        """获得模拟模式相关参数，兼容旧配置无 simulation 字段的情况"""
        sim_cfg = self.config.get("simulation") or {}
        mock_cfg = self.config.get("mock_mode", {})

        pattern = sim_cfg.get("pattern", "gradient")
        noise_level = sim_cfg.get("noise_level", mock_cfg.get("noise_level", 0.5))
        base_temp = mock_cfg.get("base_temp", 30.0)
        hot_temp = mock_cfg.get("hot_spot_temp", base_temp + 8)
        # 更新间隔：simulation.update_interval(秒) 优先，其次 display.update_interval(ms)
        update_interval = sim_cfg.get(
            "update_interval",
            self.config.get("display", {}).get("update_interval", 33) / 1000.0
        )
        return {
            "pattern": pattern,
            "noise_level": noise_level,
            "base_temp": base_temp,
            "hot_temp": hot_temp,
            "update_interval": update_interval
        }

    def _generate_simulation_data(self):
        """生成模拟温度数据 (梯度或随机 + 噪声 + 热点)"""
        params = self._get_sim_params()
        pattern = params["pattern"]
        base_temp = params["base_temp"]
        hot_temp = params["hot_temp"]

        if pattern == "gradient":
            x = np.linspace(0, 1, self.width)
            y = np.linspace(0, 1, self.height)
            X, Y = np.meshgrid(x, y)
            frame = (X + Y) / 2 * (hot_temp - base_temp) + base_temp
        else:
            frame = np.random.normal(base_temp, 2.5, (self.height, self.width))

        # 添加一个模拟热点
        cx, cy = self.width // 3, self.height // 2
        frame[cy-1:cy+2, cx-1:cx+2] = hot_temp

        # 噪声
        noise = np.random.normal(0, params["noise_level"], (self.height, self.width))
        frame += noise

        return frame.clip(self.config["temperature_range"]["min"],
                          self.config["temperature_range"]["max"])
    
    def _process_temperature_block(self, temp_bytes: bytes):
        try:
            temps_u16 = np.frombuffer(temp_bytes, dtype='<u2')
            if temps_u16.size != self.width * self.height:
                raise ValueError(f"像素数量不匹配: got {temps_u16.size}")
            temps_c = temps_u16.astype(np.float32) / 10.0
            frame = temps_c.reshape((self.height, self.width))
            return frame
        except Exception as e:
            if self._debug_cfg.get("verbose"):
                print(f"[IR8062][ERR] 温度块解析失败: {e}")
            return None
    
    def get_thermal_data(self):
        """获取温度数据 - 兼容thermal_panel接口"""
        return self.read_frame()
            
    def read_frame(self):
        """读取一帧温度数据"""
        if self.simulation_mode:
            frame = self._generate_simulation_data()
            # 使用统一的参数来源
            update_interval = self._get_sim_params()["update_interval"]
            time.sleep(update_interval)
            # 模拟帧也可参与自动范围
            self._maybe_update_range(frame)
            return frame
            
        if not self.connected:
            if self._debug_cfg.get("verbose"):
                print("[IR8062][WARN] 设备未连接，尝试重新连接...")
            if self._connect():
                self._init_hardware()
            else:
                return None
            
        try:
            self._read_into_buffer()
            frame = self._extract_one_frame()
            if frame is not None:
                self.last_frame = frame
                self._maybe_update_range(frame)
                self._empty_reads = 0
                return frame

            # 无帧情况
            self._empty_reads += 1
            if self._debug_cfg.get("verbose") and self._empty_reads % 10 == 0:
                print(f"[IR8062][DBG] waiting bytes={self.serial.in_waiting if self.serial else 0} buf={len(self.frame_buffer)} empty={self._empty_reads}")

            # 回退策略：若持续空读达到阈值，尝试发送查询帧获取一次数据
            fallback_threshold = self.config.get("query_fallback_threshold", 40)
            if self._empty_reads == fallback_threshold:
                if self._debug_cfg.get("verbose"):
                    print("[IR8062][FALLBACK] switching to query mode once")
                self.query_once()
            elif self._empty_reads > fallback_threshold and (self._empty_reads - fallback_threshold) % 50 == 0:
                # 每隔一段再查询一次
                if self._debug_cfg.get("verbose"):
                    print("[IR8062][FALLBACK] periodic query")
                self.query_once()
            return self.last_frame
        except Exception as e:
            if self._debug_cfg.get("verbose"):
                print(f"[IR8062][ERR] 读取数据帧失败: {e}")
            # 尝试重置连接
            try:
                if self.serial and self.serial.is_open:
                    self.serial.close()
                self.connected = False
            except:
                pass
            return self.last_frame
    
    def visualize_frame(self, frame: np.ndarray):
        """可视化温度数据"""
        if frame is None:
            return None
            
        # 动态范围归一化
        vmin = self._disp_min
        vmax = self._disp_max if self._disp_max > self._disp_min else self._disp_min + 1e-3
        normalized = (frame - vmin) / (vmax - vmin)
        normalized = normalized.clip(0, 1)
        
        # 应用颜色映射
        colormap = cv2.COLORMAP_JET
        colored = cv2.applyColorMap((normalized * 255).astype(np.uint8), 
                                  colormap)
        
        # 调整大小
        if self.config["display"]["enabled"]:
            display_size = (self.config["display"]["width"],
                          self.config["display"]["height"])
            colored = cv2.resize(colored, display_size)
            
        return colored

    # ---------------- serial frame handling -----------------
    def _read_into_buffer(self):
        """把串口可读字节全部读入缓冲"""
        if self.serial is None:
            return
        waiting = self.serial.in_waiting
        if waiting <= 0:
            return
        chunk = self.serial.read(waiting)
        self.frame_buffer.extend(chunk)
        # stats
        now = time.time()
        if self._first_read_time is None:
            self._first_read_time = now
        self._last_read_time = now
        self._total_bytes_read += len(chunk)
        self._read_calls += 1
        if self._debug_cfg.get("hex_head") and not self._debug_printed_intro:
            head_preview = ' '.join(f"{b:02X}" for b in self.frame_buffer[:32])
            print(f"[IR8062][DBG] First bytes: {head_preview}")
            self._debug_printed_intro = True
        # 限制最大缓冲，防止失控
        max_buf = self._debug_cfg.get("max_buffer", 200000)
        if len(self.frame_buffer) > max_buf:
            # 丢弃最旧部分
            self.frame_buffer = self.frame_buffer[-max_buf:]

    def _expected_payload_size(self):
        # 传感器像素数据大小
        return self.width * self.height * 2  # uint16

    def _extract_one_frame(self):
        buf = self.frame_buffer
        HEADER = b'\x5A\x5A'
        # 循环查找（允许缓冲里堆积多帧/噪声）
        while True:
            start = buf.find(HEADER)
            if start == -1:
                # 防止无限增长
                if len(buf) > 40000:
                    del buf[:-4]
                return None
            if start > 0:
                del buf[:start]
            if len(buf) < 4:
                return None
            length = buf[2] | (buf[3] << 8)
            total_len = 4 + length + 2
            if length <= 0 or length > 12000:
                # 异常长度，滑过一个字节继续
                if self._debug_cfg.get("verbose"):
                    print(f"[IR8062][DBG] invalid length={length} shift 1")
                del buf[0:1]
                continue
            if len(buf) < total_len:
                return None
            frame_bytes = bytes(buf[:total_len])
            del buf[:total_len]
            break
        data_for_sum = frame_bytes[:-2]
        checksum_word = frame_bytes[-2] | (frame_bytes[-1] << 8)
        words = struct.unpack('<' + 'H' * (len(data_for_sum)//2), data_for_sum)
        calc = sum(words) & 0xFFFF
        if calc != checksum_word and self._debug_cfg.get("verbose"):
            print(f"[IR8062][CHK] checksum mismatch calc=0x{calc:04X} frame=0x{checksum_word:04X}")
        if length < 12 + 2:
            return None
        meta_section = frame_bytes[4:16]
        temps_section = frame_bytes[16:-2]
        if (len(temps_section) % 2) != 0:
            if self._debug_cfg.get("verbose"):
                print(f"[IR8062][DBG] temps payload odd length={len(temps_section)}")
            return None
        emissivity = meta_section[0] / 100.0
        mirror_flag = meta_section[1]
        lens_temp = (meta_section[3] << 8 | meta_section[2]) / 10.0
        t_max = (meta_section[5] << 8 | meta_section[4]) / 10.0
        t_min = (meta_section[7] << 8 | meta_section[6]) / 10.0
        max_id = (meta_section[9] << 8 | meta_section[8])
        min_id = (meta_section[11] << 8 | meta_section[10])
        frame = self._process_temperature_block(temps_section)
        if frame is None:
            return None
        self.meta = {
            "emissivity": emissivity,
            "mirror": mirror_flag > 0,
            "lens_temp": lens_temp,
            "t_max": t_max,
            "t_min": t_min,
            "max_id": max_id,
            "min_id": min_id,
            "checksum_calc": calc,
            "checksum_frame": checksum_word,
            "length_field": length,
            "total_len": total_len
        }
        if self._debug_cfg.get("stats"):
            self._debug_frame_count += 1
            if self._debug_frame_count % self._debug_cfg.get("stats_interval", 30) == 0:
                print(f"[IR8062][DBG] frame#{self._debug_frame_count} Tmin={frame.min():.1f} Tmax={frame.max():.1f} lens={lens_temp:.1f}")
        return frame

    # ---------------- internal helpers -----------------
    def _maybe_update_range(self, frame: np.ndarray):
        ar = self.config.get("auto_range", {})
        if not ar.get("enabled", False):
            return
        alpha = ar.get("alpha", 0.1)
        pad = ar.get("padding", 2.0)
        cur_min = float(np.min(frame))
        cur_max = float(np.max(frame))
        target_min = cur_min - pad
        target_max = cur_max + pad
        self._disp_min = (1 - alpha) * self._disp_min + alpha * target_min
        self._disp_max = (1 - alpha) * self._disp_max + alpha * target_max

    @staticmethod
    def list_ports():
        """列出所有可用串口"""
        if list_ports is None:
            return []
        return [p.device for p in list_ports.comports()]
    
    @staticmethod
    def find_ir8062_ports():
        """自动发现可能的IR8062设备端口"""
        if list_ports is None:
            return []
        
        potential_ports = []
        for port in list_ports.comports():
            # 查找可能的红外摄像头设备
            desc = port.description.lower()
            if any(keyword in desc for keyword in ['usb', 'serial', 'ch340', 'ch341', 'cp210', 'ftdi']):
                potential_ports.append({
                    'device': port.device,
                    'description': port.description,
                    'vid': getattr(port, 'vid', None),
                    'pid': getattr(port, 'pid', None)
                })
        return potential_ports
    
    def close(self):
        """关闭连接"""
        if self.serial is not None and self.serial.is_open:
            self.serial.close()
            self.connected = False

    def get_meta(self):
        """返回最近帧的元数据 (发射率/镜头温度等)"""
        return self.meta

    # 运行状态/统计
    def get_stats(self):
        if self._first_read_time and self._last_read_time:
            dt = self._last_read_time - self._first_read_time
        else:
            dt = 0.0
        return {
            "bytes_total": self._total_bytes_read,
            "read_calls": self._read_calls,
            "duration": dt,
            "bytes_per_sec": (self._total_bytes_read / dt) if dt > 0 else 0.0,
            "empty_reads": self._empty_reads,
            "frames_parsed": self._debug_frame_count,
            "bootstrap_done": self._bootstrap_done,
        }