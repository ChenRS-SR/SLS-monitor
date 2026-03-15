"""
红外防护系统 - ROBOIDE舵机控制集成
使用ROBOIDE舵机控制板，波特率9600
"""

from servo_controller import ServoController, test_servo_motion

# 全局配置
SERIAL_PORT = 'COM13'  # 默认串口，可通过参数修改


# ============ 快速使用示例 ============

def example_1_basic_control(port=None):
    """示例1: 基础舵机控制"""
    print("\n【示例1】基础舵机控制")
    print("-" * 40)
    
    port = port or SERIAL_PORT
    controller = ServoController(port=port)
    if controller.connect():
        # 控制舵机移动到不同位置 (位置, 耗时ms)
        controller.move_servo_to_position(servo_id=1, position=1500, duration=500)
        controller.move_servo_to_position(servo_id=1, position=2000, duration=500)
        controller.move_servo_to_position(servo_id=1, position=1000, duration=500)
        
        controller.disconnect()


def example_2_multi_servo(port=None):
    """示例2: 多舵机控制"""
    print("\n【示例2】多舵机控制")
    print("-" * 40)
    
    port = port or SERIAL_PORT
    controller = ServoController(port=port)
    if controller.connect():
        # 控制多个舵机
        for servo_id in [1, 2, 3]:
            controller.move_servo_to_position(servo_id=servo_id, position=1500, duration=500)
        
        controller.disconnect()


def example_3_sweep_motion(port=None):
    """示例3: 舵机扫描动作"""
    print("\n【示例3】舵机扫描动作")
    print("-" * 40)
    
    port = port or SERIAL_PORT
    controller = ServoController(port=port)
    if controller.connect():
        # 舵机在500-2500之间扫描
        positions = [500, 1000, 1500, 2000, 2500, 2000, 1500, 1000, 500]
        
        for pos in positions:
            controller.move_servo_to_position(servo_id=1, position=pos)
            controller.read_response()  # 读取反馈
        
        controller.disconnect()


# ============ 供其他函数调用的接口 ============

def move_servo_to_1500(servo_id=1, port=None, retry=False):
    """
    让舵机运动到1500位置（中间位置90度）
    
    Args:
        servo_id: 舵机ID (默认为1)
        port: 串口名称 (默认使用全局SERIAL_PORT)
        retry: 是否启用重试机制 (默认False，仅在关键操作时使用)
    
    Returns:
        bool: 操作是否成功
    """
    import time
    port = port or SERIAL_PORT
    
    # 重试机制：仅在需要时启用（如手动控制）
    max_attempts = 5 if retry else 1
    
    for attempt in range(max_attempts):
        try:
            controller = ServoController(port=port)
            if controller.connect():
                try:
                    controller.move_servo_to_position(servo_id=servo_id, position=1500, duration=500, wait=True)
                    return True
                finally:
                    controller.disconnect()  # 确保连接成功时才断开
            else:
                # 连接失败，不调用 disconnect() 避免额外延迟
                if attempt < max_attempts - 1:  # 如果不是最后一次尝试
                    time.sleep(2.0)  # 等待2秒再重试（给COM完整释放时间）
        except Exception as e:
            print(f"  第{attempt+1}次尝试失败: {str(e)[:50]}")
            if attempt < max_attempts - 1:
                time.sleep(2.0)  # 等待2秒再重试
    
    return False


def move_servo_to_2500(servo_id=1, port=None, retry=False):
    """
    让舵机运动到2500位置（最大位置180度）
    
    Args:
        servo_id: 舵机ID (默认为1)
        port: 串口名称 (默认使用全局SERIAL_PORT)
        retry: 是否启用重试机制 (默认False，仅在关键操作时使用)
    
    Returns:
        bool: 操作是否成功
    """
    import time
    port = port or SERIAL_PORT
    
    # 重试机制：仅在需要时启用（如手动控制）
    max_attempts = 5 if retry else 1
    
    for attempt in range(max_attempts):
        try:
            controller = ServoController(port=port)
            if controller.connect():
                try:
                    controller.move_servo_to_position(servo_id=servo_id, position=2500, duration=500, wait=True)
                    return True
                finally:
                    controller.disconnect()  # 确保连接成功时才断开
            else:
                # 连接失败，不调用 disconnect() 避免额外延迟
                if attempt < max_attempts - 1:  # 如果不是最后一次尝试
                    time.sleep(2.0)  # 等待2秒再重试（给COM完整释放时间）
        except Exception as e:
            print(f"  第{attempt+1}次尝试失败: {str(e)[:50]}")
            if attempt < max_attempts - 1:
                time.sleep(2.0)  # 等待2秒再重试
    
    return False


if __name__ == '__main__':
    import sys
    
    print("=" * 50)
    print("红外防护系统 - 舵机控制")
    print("=" * 50)
    
    # 解析命令行参数
    port = SERIAL_PORT  # 默认COM口
    #cmd = None
    cmd = 'test'  # 默认执行测试程序
    
    if len(sys.argv) > 1:
        # 检查是否指定了端口
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg.startswith('--port=') or arg.startswith('-p='):
                port = arg.split('=')[1]
                print(f"\n📍 使用串口: {port}")
            elif arg.startswith('--port') or arg == '-p':
                if i < len(sys.argv) - 1:
                    port = sys.argv[i + 1]
                    print(f"\n📍 使用串口: {port}")
            elif not arg.startswith('-'):
                cmd = arg.lower()
    
    if cmd:
        if cmd == 'test':
            # 运行标准测试
            #test_servo_motion(port=port)
            move_servo_to_2500()
        elif cmd == 'example1':
            example_1_basic_control(port=port)
        elif cmd == 'example2':
            example_2_multi_servo(port=port)
        elif cmd == 'example3':
            example_3_sweep_motion(port=port)
        else:
            print(f"✗ 未知命令: {cmd}")
    else:
        # 显示帮助信息
        print("\n使用方法:")
        print("  python IR_protection.py test                   - 运行摆臂测试")
        print("  python IR_protection.py example1               - 基础控制示例")
        print("  python IR_protection.py example2               - 多舵机控制示例")
        print("  python IR_protection.py example3               - 扫描动作示例")
        print("\n端口参数:")
        print("  python IR_protection.py test --port=COM8       - 指定COM8")
        print("  python IR_protection.py test -p COM9           - 指定COM9")
        print(f"\n当前默认串口: {SERIAL_PORT}")
        print("\n默认执行测试程序...\n")
        test_servo_motion(port=port)
