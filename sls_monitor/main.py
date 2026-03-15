"""
SLM监控系统主程序
启动整个监控系统
"""

import os
import sys
import atexit

# 强制实时输出，解决终端缓冲问题
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
os.environ['PYTHONUNBUFFERED'] = '1'

from datetime import datetime
from sls_monitor.ui.main_window import MainWindow
from sls_monitor.devices.camera import CameraDevice
from sls_monitor.devices.infrared import OptrisConnectSDK
from sls_monitor.devices.vibration import VibrationDevice
from sls_monitor.config.camera_config import CAMERA_CONFIG
from sls_monitor.core.powder_detector import PowderDetector
from sls_monitor.core.data_logger import DataLogger
from sls_monitor.utils.error_handler import setup_logger
from sls_monitor.utils.logger import init_logging, shutdown_logging, log_info, log_error, log_warning
from sls_monitor.config.system_config import THERMAL_CAMERA_CONFIG, OUTPUT_DIR, IMAGE_DIR, LOG_DIR, DATA_DIR, LOG_LEVEL, TIMESTAMP_FORMAT

def init_directories():
    """初始化必要的目录"""
    directories = [
        OUTPUT_DIR,
        os.path.join(OUTPUT_DIR, IMAGE_DIR),
        os.path.join(OUTPUT_DIR, LOG_DIR),
        os.path.join(OUTPUT_DIR, DATA_DIR)
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ 已创建目录: {directory}", flush=True)

def init_logger():
    """初始化日志系统"""
    log_file = os.path.join(
        OUTPUT_DIR,
        LOG_DIR,
        f"slm_monitor_{datetime.now().strftime(TIMESTAMP_FORMAT)}.log"
    )
    return setup_logger("SLM_Monitor", log_file, LOG_LEVEL)

def init_devices():
    """初始化所有设备"""
    devices = {}
    MAX_RETRIES = 3  # 最大重试次数
    RETRY_DELAY = 2  # 重试间隔（秒）
    
    try:
        # 扫描所有可用摄像头
        print("==扫描系统摄像头==", flush=True)
        available_cameras = CameraDevice.scan_available_cameras(max_index=6)
        
        if available_cameras:
            print("📷 可用摄像头列表:")
            for cam in available_cameras:
                print(f"  - 索引 {cam['index']}: {cam['width']}x{cam['height']} @{cam['fps']:.1f}fps ({cam['backend']})")
        else:
            print("⚠️ 未找到任何可用摄像头")
        print()
        
        # 初始化主摄像头
        if CAMERA_CONFIG["main_camera_enabled"]:
            print("==初始化主摄像头==", flush=True)
            main_camera_index = CAMERA_CONFIG["main_camera_index"]
            print(f"📋 配置文件指定主摄像头索引: {main_camera_index}", flush=True)
            main_camera = CameraDevice(main_camera_index, "主摄像头") # 使用配置文件索引
            if main_camera.connect():
                devices['camera'] = main_camera
                print(f"📷 主摄像头初始化成功（实际索引: {main_camera.camera_index}）", flush=True)
            else:
                print("⚠️ 主摄像头初始化失败", flush=True)
        else:
            print("⚠️ 主摄像头已在配置中禁用", flush=True)
        
        # 初始化副摄像头
        if CAMERA_CONFIG["secondary_camera_enabled"]:
            print("==初始化副摄像头==", flush=True)
            secondary_camera_index = CAMERA_CONFIG["secondary_camera_index"]
            print(f"📋 配置文件指定副摄像头索引: {secondary_camera_index}", flush=True)
            
            # 智能选择副摄像头索引
            main_camera_index = devices['camera'].camera_index if 'camera' in devices and devices['camera'] else -1
            secondary_candidates = [cam['index'] for cam in available_cameras if cam['index'] != main_camera_index]
            if secondary_candidates:
                print(f"🧠 可选的副摄像头索引: {secondary_candidates}")
                # 如果配置的索引不可用，选择除了主摄像头以外的第一个
                if secondary_camera_index not in secondary_candidates and secondary_candidates:
                    print(f"⚠️ 配置索引 {secondary_camera_index} 不可用，使用第一个可用索引: {secondary_candidates[0]}")
                    secondary_camera_index = secondary_candidates[0]
            
            secondary_camera = CameraDevice(secondary_camera_index, "副摄像头")
            if secondary_camera.connect():
                devices['secondary_camera'] = secondary_camera
                print(f"📷 副摄像头初始化成功（实际索引: {secondary_camera.camera_index}）", flush=True)
            else:
                print("⚠️ 副摄像头初始化失败，但系统可以继续运行", flush=True)
        else:
            print("⚠️ 副摄像头已在配置中禁用", flush=True)
        
        # 初始化红外热像仪
        thermal_camera_type = THERMAL_CAMERA_CONFIG.get("thermal_camera_type", 1)
        
        if thermal_camera_type == 0:
            # 使用IR8062
            print("==初始化IR8062红外热像仪==", flush=True)
            try:
                from sls_monitor.devices.ir8062_integrated import IR8062Device
                thermal = IR8062Device(
                    port=THERMAL_CAMERA_CONFIG.get("ir8062_port"),
                    simulation_mode=THERMAL_CAMERA_CONFIG.get("simulation_mode", False)
                )
                if thermal.connected or thermal.simulation_mode:
                    devices['thermal'] = thermal
                    print("✅ IR8062红外热像仪初始化成功", flush=True)
                else:
                    print("⚠️ IR8062连接失败，启用模拟模式", flush=True)
                    thermal = IR8062Device(simulation_mode=True)
                    devices['thermal'] = thermal
                    print("🔄 已启用IR8062模拟模式", flush=True)
            except Exception as e:
                print(f"❌ IR8062初始化失败: {e}", flush=True)
                # 启用模拟模式作为备选
                try:
                    from sls_monitor.devices.ir8062_integrated import IR8062Device
                    thermal = IR8062Device(simulation_mode=True)
                    devices['thermal'] = thermal
                    print("🔄 已启用IR8062模拟模式作为备选", flush=True)
                except Exception as e2:
                    print(f"❌ 模拟模式也失败: {e2}", flush=True)
        
        else:
            # 使用Fotric 628ch (默认)
            print("==初始化Fotric 628ch红外热像仪==", flush=True)
            try:
                from sls_monitor.devices.Fotric_628ch_enhanced import FotricEnhancedDevice
                thermal = FotricEnhancedDevice(
                    ip=THERMAL_CAMERA_CONFIG.get("fotric_ip", "192.168.1.100"),
                    port=THERMAL_CAMERA_CONFIG.get("fotric_port", 8080),
                    username=THERMAL_CAMERA_CONFIG.get("fotric_username", "admin"),
                    password=THERMAL_CAMERA_CONFIG.get("fotric_password", "admin"),
                    simulation_mode=THERMAL_CAMERA_CONFIG.get("simulation_mode", False),
                    high_resolution=THERMAL_CAMERA_CONFIG.get("fotric_high_resolution", True),
                    update_rate=THERMAL_CAMERA_CONFIG.get("fotric_update_rate", 2.0),
                    sample_density=THERMAL_CAMERA_CONFIG.get("fotric_sample_density", 40)
                )
                if thermal.is_connected or thermal.simulation_mode:
                    devices['thermal'] = thermal
                    mode_str = "模拟模式" if thermal.simulation_mode else "真实设备"
                    res_str = "640x480" if thermal.high_resolution else "320x240"
                    print(f"✅ Fotric 628ch红外热像仪初始化成功 ({mode_str}, {res_str})", flush=True)
                else:
                    print("⚠️ Fotric 628ch连接失败，启用模拟模式", flush=True)
                    thermal = FotricEnhancedDevice(
                        ip=THERMAL_CAMERA_CONFIG.get("fotric_ip", "192.168.1.100"),
                        port=THERMAL_CAMERA_CONFIG.get("fotric_port", 8080),
                        simulation_mode=True,
                        high_resolution=THERMAL_CAMERA_CONFIG.get("fotric_high_resolution", True),
                        update_rate=THERMAL_CAMERA_CONFIG.get("fotric_update_rate", 2.0),
                        sample_density=THERMAL_CAMERA_CONFIG.get("fotric_sample_density", 40)
                    )
                    devices['thermal'] = thermal
                    print("🔄 已启用Fotric 628ch模拟模式", flush=True)
            except Exception as e:
                print(f"❌ Fotric 628ch初始化失败: {e}", flush=True)
                # 启用模拟模式作为备选
                try:
                    from sls_monitor.devices.Fotric_628ch_enhanced import FotricEnhancedDevice
                    thermal = FotricEnhancedDevice(
                        simulation_mode=True,
                        high_resolution=THERMAL_CAMERA_CONFIG.get("fotric_high_resolution", True),
                        update_rate=THERMAL_CAMERA_CONFIG.get("fotric_update_rate", 2.0),
                        sample_density=THERMAL_CAMERA_CONFIG.get("fotric_sample_density", 40)
                    )
                    devices['thermal'] = thermal
                    print("🔄 已启用Fotric 628ch模拟模式作为备选", flush=True)
                except Exception as e2:
                    print(f"❌ Fotric模拟模式也失败: {e2}", flush=True)
        
        # 初始化振动传感器
        print("==初始化振动传感器==", flush=True)
        vibration = VibrationDevice()
        # 无论连接是否成功都添加到设备列表，支持调试模式
        devices['vibration'] = vibration
        if vibration.connect():
            vibration.start_monitoring()  # 开始监测振动数据
            print("✅ 振动传感器连接成功", flush=True)
        else:
            print("⚠️ 振动传感器连接失败，将使用调试模式", flush=True)
        
    except Exception as e:
        print(f"❌ 设备初始化失败: {str(e)}", flush=True)
        sys.exit(1)
    
    return devices

def init_modules(devices):
    """初始化功能模块"""
    modules = {}
    
    try:
        # 初始化扑粉检测器
        if 'vibration' in devices:
            modules['powder_detector'] = PowderDetector(devices['vibration'])
        
        # 初始化数据记录器
        modules['data_logger'] = DataLogger()
        
    except Exception as e:
        print(f"❌ 模块初始化失败: {str(e)}", flush=True)
        sys.exit(1)
    
    return modules

def cleanup_on_exit():
    """程序退出时的清理函数"""
    try:
        log_info("程序正在退出，保存调试日志...", "SYSTEM")
        shutdown_logging()
    except Exception as e:
        print(f"❌ 清理日志时出错: {e}")

def main():
    """主程序入口"""
    print("🚀 启动SLM监控系统...", flush=True)
    
    # 初始化目录
    init_directories()
    
    # 初始化新的日志系统（禁用控制台捕获避免递归）
    base_dir = os.path.join(os.getcwd(), "output")
    debug_logger = init_logging(base_dir, enable_console_capture=False)
    log_info("=== SLM监控系统启动 ===", "SYSTEM")
    
    # 注册程序退出时的清理函数
    atexit.register(cleanup_on_exit)
    
    # 初始化传统日志
    logger = init_logger()
    logger.info("系统启动")
    
    # 初始化设备
    log_info("开始初始化设备...", "SYSTEM")
    devices = init_devices()
    
    # 检查必要设备
    required_devices = ['camera', 'thermal', 'vibration']
    missing_devices = [dev for dev in required_devices if dev not in devices]
    if missing_devices:
        log_error(f"缺少必要设备: {', '.join(missing_devices)}", "SYSTEM")
        print(f"❌ 缺少必要设备: {', '.join(missing_devices)}", flush=True)
        sys.exit(1)
    
    # 初始化功能模块
    log_info("初始化功能模块...", "SYSTEM")
    modules = init_modules(devices)
    
    # 创建并运行主窗口
    log_info("启动用户界面...", "SYSTEM")
    try:
        app = MainWindow(devices)
        log_info("主窗口创建成功", "SYSTEM")
        
        # 启动振动监测（振动监测应该自动运行）
        if 'vibration' in devices:
            log_info("自动启动振动监测...", "VIBRATION")
            # 只启动振动监测，不启动相机面板
            if hasattr(app, 'vibration_panel'):
                app._start_vibration_monitoring()
                log_info("振动监测已自动启动", "VIBRATION")
            else:
                log_warning("振动面板未找到，无法启动监测", "VIBRATION")
        
        log_info("启动GUI主循环...", "SYSTEM")
        app.run()  # 这里会阻塞直到窗口关闭
        log_info("GUI主循环结束", "SYSTEM")
        
    except Exception as e:
        log_error(f"主窗口启动失败: {str(e)}", "SYSTEM")
        print(f"❌ 主窗口启动失败: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        logger.error(f"主窗口启动失败: {str(e)}")
    
    # 清理资源
    log_info("开始清理资源...", "SYSTEM")
    try:
        for device_name, device in devices.items():
            log_info(f"清理设备: {device_name}", "SYSTEM")
            try:
                if hasattr(device, 'stop_monitoring'):
                    device.stop_monitoring()
                if hasattr(device, 'disconnect'):
                    device.disconnect()
                log_info(f"设备 {device_name} 已清理", "SYSTEM")
            except Exception as device_error:
                log_warning(f"清理设备 {device_name} 时出错: {device_error}", "SYSTEM")
    except Exception as e:
        log_warning(f"清理资源时出现错误: {e}", "SYSTEM")
    
    logger.info("系统关闭")
    log_info("=== SLM监控系统关闭 ===", "SYSTEM")
    print("\n✨ 系统已关闭", flush=True)

if __name__ == "__main__":
    main()