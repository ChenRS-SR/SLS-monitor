#!/usr/bin/env python3
"""
SLS项目部署验证脚本
验证所有依赖和核心功能是否正常
"""

import sys
import os
import importlib.util

def check_python_version():
    """检查Python版本"""
    print("1. 检查Python版本...")
    version = sys.version_info
    print(f"   当前版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major >= 3 and version.minor >= 8:
        print("   ✅ Python版本符合要求 (3.8+)")
        return True
    else:
        print("   ❌ Python版本过低，需要3.8+")
        return False

def check_dependencies():
    """检查依赖包"""
    print("\n2. 检查Python依赖...")
    
    required_packages = [
        'cv2',           # opencv-python
        'numpy',         # numpy
        'serial',        # pyserial
        'crcmod',        # crcmod
        'cmapy',         # cmapy
        'matplotlib',    # matplotlib
        'tkinter'        # tkinter
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (缺失)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n   需要安装: pip install -r requirements.txt")
        return False
    else:
        print("   ✅ 所有依赖包完整")
        return True

def check_pysenxor():
    """检查pysenxor库"""
    print("\n3. 检查pysenxor库...")
    
    pysenxor_path = os.path.join(os.path.dirname(__file__), 'pysenxor-master')
    
    if not os.path.exists(pysenxor_path):
        print("   ❌ pysenxor-master目录缺失")
        return False
    
    # 检查关键文件
    key_files = [
        'senxor/__init__.py',
        'senxor/mi48.py',
        'senxor/utils.py'
    ]
    
    for file in key_files:
        file_path = os.path.join(pysenxor_path, file)
        if os.path.exists(file_path):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (缺失)")
            return False
    
    # 尝试导入
    sys.path.insert(0, pysenxor_path)
    try:
        from senxor.mi48 import MI48
        from senxor.utils import data_to_frame, connect_senxor
        print("   ✅ pysenxor模块导入成功")
        return True
    except ImportError as e:
        print(f"   ❌ pysenxor导入失败: {e}")
        return False

def check_sls_monitor():
    """检查SLS监控系统"""
    print("\n4. 检查SLS监控系统...")
    
    sls_path = os.path.join(os.path.dirname(__file__), 'sls_monitor')
    
    if not os.path.exists(sls_path):
        print("   ❌ sls_monitor目录缺失")
        return False
    
    # 检查关键模块
    key_modules = [
        'main.py',
        'ui/main_window.py',
        'devices/ir8062_integrated.py',
        'devices/camera.py',
        'config/system_config.py'
    ]
    
    for module in key_modules:
        module_path = os.path.join(sls_path, module)
        if os.path.exists(module_path):
            print(f"   ✅ {module}")
        else:
            print(f"   ❌ {module} (缺失)")
            return False
    
    # 尝试导入核心模块
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from sls_monitor.devices.ir8062_integrated import IR8062Device
        print("   ✅ IR8062设备模块导入成功")
        return True
    except ImportError as e:
        print(f"   ❌ SLS模块导入失败: {e}")
        return False

def check_directories():
    """检查目录结构"""
    print("\n5. 检查目录结构...")
    
    required_dirs = [
        'output',
        'logs', 
        'captures'
    ]
    
    for dir_name in required_dirs:
        dir_path = os.path.join(os.path.dirname(__file__), dir_name)
        if os.path.exists(dir_path):
            print(f"   ✅ {dir_name}/")
        else:
            print(f"   ⚠️ {dir_name}/ (将自动创建)")
            os.makedirs(dir_path, exist_ok=True)
            print(f"   ✅ {dir_name}/ (已创建)")
    
    return True

def test_ir8062_integration():
    """测试IR8062集成"""
    print("\n6. 测试IR8062集成...")
    
    try:
        from sls_monitor.devices.ir8062_integrated import IR8062Device
        
        # 创建设备实例 (模拟模式)
        device = IR8062Device(simulation_mode=True)
        
        if device.connected:
            print("   ✅ IR8062设备创建成功")
            
            # 获取一帧数据
            import time
            time.sleep(1)
            
            thermal_data = device.get_thermal_data()
            if thermal_data is not None:
                print(f"   ✅ 热像数据获取成功: {thermal_data.shape}")
                device.disconnect()
                return True
            else:
                print("   ❌ 无法获取热像数据")
                device.disconnect()
                return False
        else:
            print("   ❌ IR8062设备连接失败")
            return False
            
    except Exception as e:
        print(f"   ❌ IR8062测试失败: {e}")
        return False

def main():
    """主验证流程"""
    print("🔍 SLS项目部署验证")
    print("=" * 50)
    
    checks = [
        check_python_version,
        check_dependencies, 
        check_pysenxor,
        check_sls_monitor,
        check_directories,
        test_ir8062_integration
    ]
    
    results = []
    for check in checks:
        result = check()
        results.append(result)
    
    print("\n" + "=" * 50)
    print("📊 验证结果汇总:")
    
    if all(results):
        print("🎉 所有检查通过！SLS项目可以正常运行。")
        print("\n🚀 启动命令: python run.py")
        return True
    else:
        print("❌ 部分检查失败，请根据上述提示修复问题。")
        return False

if __name__ == "__main__":
    main()