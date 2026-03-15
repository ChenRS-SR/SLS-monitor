#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速热像仪调试脚本
检查热像仪数据是否正常生成和更新
"""

import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sls_monitor.config.system_config import THERMAL_CAMERA_CONFIG

def debug_fotric_device():
    """调试Fotric设备的数据生成"""
    print("🔍 开始调试Fotric设备...")
    
    try:
        from sls_monitor.devices.Fotric_628ch_enhanced import FotricEnhancedDevice
        
        # 创建设备实例
        fotric = FotricEnhancedDevice(
            ip=THERMAL_CAMERA_CONFIG.get("fotric_ip", "192.168.1.100"),
            simulation_mode=True  # 强制使用模拟模式
        )
        
        print(f"✅ 设备创建成功")
        print(f"   连接状态: {fotric.is_connected}")
        print(f"   模拟模式: {fotric.simulation_mode}")
        print(f"   监控状态: {fotric.is_running}")
        
        # 等待数据生成
        print("\n⏳ 等待数据生成...")
        for i in range(10):
            time.sleep(0.5)
            
            # 检查latest_frame
            if fotric.latest_frame:
                frame = fotric.latest_frame
                print(f"✅ 第{i+1}次检查:")
                print(f"   帧ID: {frame['frame_id']}")
                print(f"   数据形状: {frame['frame'].shape}")
                print(f"   温度范围: {frame['temp_min']:.1f} - {frame['temp_max']:.1f}°C")
                print(f"   时间戳: {frame['timestamp']}")
                
                # 测试SLS接口
                thermal_data = fotric.get_thermal_data()
                temp_stats = fotric.get_temperature_stats()
                
                if thermal_data is not None:
                    print(f"   get_thermal_data(): ✅ {thermal_data.shape}")
                else:
                    print(f"   get_thermal_data(): ❌ None")
                
                if temp_stats:
                    print(f"   get_temperature_stats(): ✅ min={temp_stats['min_temp']:.1f}")
                else:
                    print(f"   get_temperature_stats(): ❌ None")
                    
                break
            else:
                print(f"❌ 第{i+1}次检查: latest_frame is None")
        
        # 最终状态检查
        print(f"\n📊 最终状态:")
        print(f"   连接状态: {fotric.is_connected}")
        print(f"   监控状态: {fotric.is_running}")
        print(f"   帧计数: {fotric.frame_count}")
        print(f"   latest_frame: {'有数据' if fotric.latest_frame else '无数据'}")
        
        # 清理
        fotric.stop_monitoring()
        fotric.disconnect()
        
        return fotric.latest_frame is not None
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def debug_ui_panel():
    """调试UI面板的数据显示"""
    print("\n🖥️ 开始调试UI面板...")
    
    try:
        # 模拟创建thermal_panel需要的组件
        import tkinter as tk
        from sls_monitor.devices.Fotric_628ch_enhanced import FotricEnhancedDevice
        from sls_monitor.ui.thermal_panel import ThermalPanel
        
        # 创建设备
        fotric = FotricEnhancedDevice(simulation_mode=True)
        
        # 等待设备准备
        time.sleep(1)
        
        # 创建简单的tkinter窗口
        root = tk.Tk()
        root.title("热像仪调试")
        root.geometry("400x300")
        
        # 创建thermal_panel
        thermal_panel = ThermalPanel(root, fotric, "Fotric 628ch 调试")
        thermal_panel.frame.pack(fill=tk.BOTH, expand=True)
        
        # 启动更新
        thermal_panel.start_update()
        
        print("✅ UI面板创建成功")
        print("✅ 已启动图像更新")
        print("✅ 窗口已显示，请查看是否显示热像图")
        print("📝 如果看到热像图而不是'No Data'，说明问题已解决")
        
        # 运行GUI（会阻塞）
        root.mainloop()
        
        return True
        
    except Exception as e:
        print(f"❌ UI调试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主调试函数"""
    print("🚀 热像仪数据流调试工具")
    print("=" * 50)
    
    # 显示当前配置
    print(f"📋 当前配置:")
    print(f"   设备类型: {THERMAL_CAMERA_CONFIG.get('thermal_camera_type')}")
    print(f"   模拟模式: {THERMAL_CAMERA_CONFIG.get('simulation_mode')}")
    
    # 调试设备数据生成
    device_ok = debug_fotric_device()
    
    if device_ok:
        print("\n🎉 设备数据生成正常！")
        
        # 询问是否继续UI测试
        try:
            choice = input("\n是否继续测试UI显示？(y/n): ").strip().lower()
            if choice == 'y':
                debug_ui_panel()
        except KeyboardInterrupt:
            print("\n👋 调试结束")
    else:
        print("\n❌ 设备数据生成异常，请检查错误信息")

if __name__ == "__main__":
    main()