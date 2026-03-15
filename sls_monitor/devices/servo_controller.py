"""
ROBOIDE舵机控制板控制模块
通讯协议：ROBOIDE文本命令格式
波特率：9600
数据位：8
校验位：无
停止位：1

命令格式示例：
  #1P1500T100\r\n    - 舵机1移动到1500位置，耗时100ms
  #1P2500T500\r\n    - 舵机1移动到2500位置，耗时500ms
"""

import serial
import time
import json
import os
import gc  # 垃圾回收
import atexit  # 程序退出时清理
import sys  # 用于重启Python解释器
from typing import Optional

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config_servo.json')

# 全局串口实例列表，用于程序退出时强制清理
_global_servo_controllers = []

def _cleanup_all_servos():
    """程序退出时强制清理所有串口"""
    print("\n[CLEANUP] 程序退出，强制清理所有舵机串口...")
    for controller in _global_servo_controllers:
        try:
            controller.force_disconnect()
        except:
            pass
    # 强制垃圾回收
    gc.collect()
    time.sleep(0.5)
    print("[CLEANUP] 清理完成")

# 注册程序退出时的清理函数
atexit.register(_cleanup_all_servos)


def reset_serial_port_windows(port: str) -> bool:
    """
    尝试使用Windows命令重置串口
    
    Args:
        port: 串口号 (如 'COM13')
        
    Returns:
        bool: 是否成功
    """
    import subprocess
    import re
    
    try:
        # 提取数字部分
        port_num = re.search(r'\d+', port)
        if not port_num:
            return False
        port_num = port_num.group()
        
        print(f"[RESET] 尝试重置串口 {port}...")
        
        # 方法1: 使用 mode 命令重置串口
        try:
            result = subprocess.run(
                ['mode', port, 'BAUD=9600', 'PARITY=n', 'DATA=8', 'STOP=1'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"[RESET] mode 命令成功")
                return True
        except Exception as e:
            print(f"[RESET] mode 命令失败: {e}")
        
        return False
        
    except Exception as e:
        print(f"[RESET] 重置串口失败: {e}")
        return False


def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'port': 'COM13', 'baudrate': 9600}


def save_config(port: str, baudrate: int = 9600):
    """保存配置文件"""
    config = {'port': port, 'baudrate': baudrate}
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✓ 配置已保存: {CONFIG_FILE}")
    except Exception as e:
        print(f"⚠ 保存配置失败: {e}")


class ServoController:
    """ROBOIDE舵机控制类"""
    
    def __init__(self, port: str = 'COM13', baudrate: int = 9600):
        """
        初始化串口连接
        
        Args:
            port: 串口名称 (默认COM13)
            baudrate: 波特率 (ROBOIDE默认9600)
        """
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.is_connected = False
        
        # 注册到全局列表，确保程序退出时能被清理
        _global_servo_controllers.append(self)
        
    def connect(self, max_retries: int = 3) -> bool:
        """
        建立串口连接（带重试机制）
        
        Args:
            max_retries: 最大重试次数（默认3次）
            
        Returns:
            bool: 连接是否成功
        """
        # 如果已经连接，先断开
        if self.is_connected and self.ser:
            print(f"ℹ️ 已经连接，先断开再重新连接...")
            self.disconnect()
            time.sleep(1.0)  # 等待释放
        
        for attempt in range(max_retries):
            try:
                print(f"  连接尝试 {attempt + 1}/{max_retries}...")
                
                # 每次尝试前等待，确保资源释放
                if attempt > 0:
                    wait_time = 2.0 + attempt  # 递增等待时间
                    print(f"  等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    time.sleep(0.5)  # 首次连接前短暂等待
                
                # 强制垃圾回收，帮助释放系统资源
                gc.collect()
                
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1,
                    write_timeout=1  # 添加写超时
                )
                self.is_connected = True
                print(f"✓ 成功连接到 {self.port}，波特率: {self.baudrate}")
                return True
                
            except PermissionError as e:
                print(f"✗ 连接失败 (尝试 {attempt + 1}): 拒绝访问 - COM口被占用")
                if attempt == max_retries - 1:
                    print(f"\n  ❌ 无法连接到 {self.port}")
                    print(f"  可能的原因:")
                    print(f"  1. 前一个程序未正确释放串口")
                    print(f"  2. 需要重启 Python 解释器")
                    print(f"  3. 需要重启计算机")
                    print(f"  4. 尝试拔插USB设备")
                self.is_connected = False
                
            except serial.SerialException as e:
                error_msg = str(e)
                if "系统资源不足" in error_msg or "OSError(22" in error_msg:
                    print(f"✗ 连接失败 (尝试 {attempt + 1}): 系统资源不足")
                    
                    # 尝试重置串口
                    if attempt < max_retries - 1:
                        print(f"  尝试重置串口...")
                        reset_serial_port_windows(self.port)
                        time.sleep(2.0)  # 重置后等待
                    
                    if attempt == max_retries - 1:
                        print(f"\n  ❌ 系统资源未释放")
                        print(f"  这是 Windows + ROBOIDE 硬件的已知问题")
                        print(f"  解决方案（按优先级）:")
                        print(f"  1. [推荐] 使用 SLS 主程序，不要单独测试舵机")
                        print(f"  2. 重启 Python 解释器（关闭所有Python窗口）")
                        print(f"  3. 拔插USB设备")
                        print(f"  4. 重启计算机")
                else:
                    print(f"✗ 连接失败 (尝试 {attempt + 1}): {e}")
                    if attempt == max_retries - 1:
                        print(f"\n  请检查:")
                        print(f"  1. {self.port} 是否正确？")
                        print(f"  2. 设备是否已连接？")
                        print(f"  3. 驱动程序是否已安装？")
                self.is_connected = False
                
            except Exception as e:
                print(f"✗ 连接失败 (尝试 {attempt + 1}): 未知错误 - {e}")
                self.is_connected = False
        
        return False
    
    def disconnect(self) -> None:
        """断开串口连接 - 强制释放版本"""
        
        if not self.ser:
            print(f"ℹ️ 串口未初始化，无需断开")
            return
            
        port_name = self.port  # 保存端口名，因为后面要清空self.ser
        
        try:
            if self.ser.is_open:
                # 发送停止命令（让舵机停止当前动作）
                try:
                    #self.ser.write(b'#1P1500T100\r\n')  # 回到中间位置
                    time.sleep(0.1)
                except:
                    pass
                
                # 清空缓冲区
                try:
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                except:
                    pass
                
                time.sleep(0.1)
                
                # 关闭串口
                try:
                    self.ser.close()
                    print(f"✓ 串口已关闭 {port_name}")
                except Exception as e:
                    print(f"⚠️ 关闭串口时出错: {e}")
        except Exception as e:
            print(f"⚠️ 断开连接时出错: {e}")
        finally:
            # 强制清空所有引用
            self.ser = None
            self.is_connected = False
            
            # 强制垃圾回收，帮助释放系统资源
            gc.collect()
        
        # 关键：给Windows充足的时间释放串口资源
        print(f"⏳ 等待系统释放串口资源...")
        time.sleep(3.0)  # 增加到3秒
        print(f"✓ 断开完成")
    
    def force_disconnect(self) -> None:
        """强制断开连接 - 用于异常情况"""
        print(f"⚠️ 强制断开串口 {self.port}")
        try:
            if self.ser:
                if hasattr(self.ser, 'close'):
                    self.ser.close()
        except:
            pass
        finally:
            self.ser = None
            self.is_connected = False
            gc.collect()
    
    def send_command(self, command: str) -> bool:
        """
        发送命令到舵机
        
        Args:
            command: 要发送的命令字符串 (会自动添加\r\n)
            
        Returns:
            bool: 发送是否成功
        """
        if not self.is_connected or not self.ser:
            print("✗ 串口未连接")
            return False
        
        try:
            # ROBOIDE命令格式，例如：#1P1500T100
            if not command.endswith('\r\n'):
                command += '\r\n'
            
            self.ser.write(command.encode())
            print(f"→ 发送命令: {command.strip()}")
            return True
        except Exception as e:
            print(f"✗ 发送失败: {e}")
            return False
    
    def read_response(self, timeout: float = 0.5) -> Optional[bytes]:
        """
        读取舵机响应数据
        
        Args:
            timeout: 等待超时时间（秒）
            
        Returns:
            接收到的字节数据，或None
        """
        if not self.is_connected or not self.ser:
            return None
        
        try:
            self.ser.timeout = timeout
            data = self.ser.read(1024)
            if data:
                print(f"← 接收数据: {data.hex()}")
            return data if data else None
        except Exception as e:
            print(f"✗ 读取失败: {e}")
            return None
    
    def set_servo_position(self, servo_id: int, position: int, 
                          duration: int = 100) -> bool:
        """
        设置舵机位置 (ROBOIDE命令格式)
        
        命令格式: #<ID>P<POSITION>T<DURATION>\r\n
        
        Args:
            servo_id: 舵机ID (1-32)
            position: 目标位置 (500-2500)，对应0-180度
            duration: 动作耗时(毫秒), 默认100ms
            
        Returns:
            bool: 设置是否成功
        """
        # 限制位置范围
        position = max(500, min(2500, position))
        servo_id = max(1, min(32, servo_id))
        duration = max(1, duration)
        
        # 构建ROBOIDE命令
        command = f"#{servo_id}P{position}T{duration}"
        
        return self.send_command(command)
    
    def move_servo_to_position(self, servo_id: int, position: int, 
                              duration: int = 500, wait: bool = False) -> None:
        """
        让舵机移动到指定位置 (ROBOIDE命令格式)
        
        Args:
            servo_id: 舵机ID (1-32)
            position: 目标位置 (500-2500，1500为中间)
            duration: 动作耗时(毫秒), 默认500ms
            wait: 是否等待运动完成
        """
        print(f"\n→ 舵机{servo_id}移动到位置: {position} (耗时{duration}ms)")
        self.set_servo_position(servo_id, position, duration)
        
        if wait:
            time.sleep(duration / 1000.0)  # 等待运动完成


# 接口函数
def create_servo_controller(port: str = 'COM13') -> ServoController:
    """
    创建并返回舵机控制器实例
    
    Args:
        port: 串口名称
        
    Returns:
        ServoController: 舵机控制器实例（连接可能成功或失败，请检查 is_connected）
    """
    controller = ServoController(port=port)
    # 尝试连接，但不强制要求成功
    # 调用者应该检查 controller.is_connected
    try:
        controller.connect()
    except Exception as e:
        print(f"⚠️ create_servo_controller: 连接失败 - {e}")
    return controller


def test_servo_motion(servo_id: int = 1, port: str = 'COM13') -> None:
    """
    测试舵机摆臂动作
    
    动作流程:
    1. 舵机返回中间位置 (1500)
    2. 舵机摆臂到位置 (2500)
    3. 舵机摆臂回到中间位置 (1500)
    
    Args:
        servo_id: 舵机ID (默认为1)
        port: 串口名称 (默认COM16)
    """
    import time
    
    print("=" * 50)
    print("ROBOIDE舵机摆臂测试 - 1500 → 2500 → 1500")
    print("=" * 50)
    
    controller = None
    
    try:
        # 创建控制器
        print(f"\n[连接] 正在连接舵机控制器: {port}")
        controller = ServoController(port=port)
        
        if not controller.connect():
            print("\n✗ 测试失败：无法连接到串口")
            print(f"\n可能的原因:")
            print(f"  1. COM口不正确 - 请在设备管理器中查看")
            print(f"  2. 驱动未安装 - 运行 CH341SER.exe 或 usc_driver.exe")
            print(f"  3. 设备未连接 - 检查USB连接")
            print(f"  4. 串口被占用 - 重启Python或检查其他程序")
            return
        
        # 初始位置1500 (耗时500ms)
        print("\n[阶段1] 舵机返回中间位置 (1500)")
        controller.move_servo_to_position(servo_id, 1500, duration=500, wait=True)
        time.sleep(0.5)  # 额外等待确保到位
        
        # 移动到2500 (耗时1000ms)
        print("\n[阶段2] 舵机摆臂到位置 (2500)")
        controller.move_servo_to_position(servo_id, 2500, duration=1000, wait=True)
        time.sleep(0.5)  # 额外等待确保到位
        
        print("\n✓ 测试完成！")
        
    except KeyboardInterrupt:
        print("\n✗ 测试被用户中断")
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保断开连接
        if controller:
            print("\n[清理] 正在断开舵机连接...")
            try:
                controller.disconnect()
                print("✓ 舵机连接已断开")
            except Exception as e:
                print(f"⚠️ 断开连接时出错: {e}")
        else:
            print("\nℹ️ 控制器未创建，无需断开")


if __name__ == '__main__':
    # 执行测试
    test_servo_motion()
