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
from typing import Optional

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config_servo.json')


def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'port': 'COM16', 'baudrate': 9600}


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
    
    def __init__(self, port: str = 'COM16', baudrate: int = 9600):
        """
        初始化串口连接
        
        Args:
            port: 串口名称 (默认COM8)
            baudrate: 波特率 (ROBOIDE默认9600)
        """
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.is_connected = False
        
    def connect(self) -> bool:
        """
        建立串口连接
        
        Returns:
            bool: 连接是否成功
        """
        import time
        try:
            # 在连接前延迟，确保个上一次接口完全四惶
            time.sleep(0.5)
            
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,      # 8位数据位
                parity=serial.PARITY_NONE,      # 无校验位
                stopbits=serial.STOPBITS_ONE,   # 1位停止位
                timeout=1
            )
            self.is_connected = True
            print(f"✓ 成功连接到 {self.port}，波特率: {self.baudrate}")
            return True
        except PermissionError as e:
            print(f"✗ 连接失败: {e}")
            print(f"  ❌ 拒绝访问 - COM口已被占用")
            print(f"  请检查:")
            print(f"  1. 是否有其他程序占用 {self.port}？(test_servo.py, 串口工具等)")
            print(f"  2. 前一个连接是否未正确关闭？")
            print(f"  3. 需要重启 USB 设备或重启计算机")
            self.is_connected = False
            return False
        except serial.SerialException as e:
            print(f"✗ 连接失败: {e}")
            print(f"  请检查:")
            print(f"  1. {self.port} 是否正确？")
            print(f"  2. 设备是否已连接？")
            print(f"  3. 驱动程序是否已安装？(CH341SER.exe或usc_driver.exe)")
            self.is_connected = False
            return False
    
    def disconnect(self) -> None:
        """断开串口连接"""
        import time
        try:
            if self.ser:
                if self.ser.is_open:
                    # 多次尝试清空缓冲区
                    for attempt in range(3):
                        try:
                            self.ser.reset_input_buffer()
                            self.ser.reset_output_buffer()
                            time.sleep(0.1)
                        except Exception as e:
                            if attempt == 0:
                                print(f"  清空缓冲区尝试{attempt+1}: {e}")
                    
                    # 等待一下，让数据完全发送
                    time.sleep(0.2)
                    self.ser.close()
                    
                self.ser = None  # 清空引用，确保完全释放
            self.is_connected = False
            print(f"✓ 已断开 {self.port}")
        except Exception as e:
            print(f"✗ 断开连接时出错: {e}")
            self.ser = None
            self.is_connected = False
        
        # 关键：给Windows充足的时间释放串口资源
        time.sleep(1.5)  # 1.5秒平衡：避免卡顿但给COM完整释放时间
    
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
def create_servo_controller(port: str = 'COM16') -> ServoController:
    """
    创建并返回舵机控制器实例
    
    Args:
        port: 串口名称
        
    Returns:
        ServoController: 舵机控制器实例
    """
    controller = ServoController(port=port)
    controller.connect()
    return controller


def test_servo_motion(servo_id: int = 1, port: str = 'COM16') -> None:
    """
    测试舵机摆臂动作
    
    动作流程:
    1. 舵机返回中间位置 (1500)
    2. 舵机摆臂到位置 (2500)
    3. 舵机摆臂回到中间位置 (1500)
    
    Args:
        servo_id: 舵机ID (默认为1)
        port: 串口名称 (默认COM8)
    """
    print("=" * 50)
    print("ROBOIDE舵机摆臂测试 - 1500 → 2500 → 1500")
    print("=" * 50)
    
    # 创建控制器
    controller = create_servo_controller(port)
    
    if not controller.is_connected:
        print("\n✗ 测试失败：无法连接到串口")
        print(f"\n可能的原因:")
        print(f"  1. COM口不正确 - 请在设备管理器中查看")
        print(f"  2. 驱动未安装 - 运行 CH341SER.exe 或 usc_driver.exe")
        print(f"  3. 设备未连接 - 检查USB连接")
        return
    
    try:
        # 初始位置1500 (耗时500ms)
        print("\n[阶段1] 舵机返回中间位置 (1500)")
        controller.move_servo_to_position(servo_id, 1500, duration=500, wait=True)
        
        # 移动到2500 (耗时1000ms)
        print("\n[阶段2] 舵机摆臂到位置 (2500)")
        controller.move_servo_to_position(servo_id, 2500, duration=1000, wait=True)
        
        # 回到1500 (耗时1000ms)
        #print("\n[阶段3] 舵机摆臂回到中间位置 (1500)")
        #controller.move_servo_to_position(servo_id, 1500, duration=1000, wait=True)
        
        print("\n✓ 测试完成！")
        
    except KeyboardInterrupt:
        print("\n✗ 测试被中断")
    finally:
        controller.disconnect()


if __name__ == '__main__':
    # 执行测试
    test_servo_motion()
