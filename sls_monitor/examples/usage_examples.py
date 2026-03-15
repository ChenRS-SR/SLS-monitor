#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FOTRIC 628ch 增强版简单使用示例
基于C# DLDemo核心功能的Python实现

使用场景:
1. 实时温度监控
2. 温度数据采集
3. 热点检测
4. 温度分析
"""

import time
import numpy as np
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from devices.Fotric_628ch_enhanced import FotricEnhancedDevice

def simple_temperature_monitoring():
    """简单温度监控示例"""
    
    print("🌡️ FOTRIC 628ch 简单温度监控")
    print("=" * 50)
    
    # 方式1: 基础使用 - 设备不需要认证
    print("\n📊 方式1: 基础温度获取（无需认证）")
    
    device = FotricEnhancedDevice(
        ip="192.168.1.100",
        simulation_mode=False  # 连接真实设备
    )
    
    if device.connect():
        print("✅ 设备连接成功！")
        
        try:
            # 获取中心点温度
            center_temp = device.get_center_temperature()
            print(f"🎯 中心点温度: {center_temp:.2f}°C")
            
            # 获取特定点温度
            corner_temp = device.get_point_temperature(100, 100)
            print(f"📍 角落温度: {corner_temp:.2f}°C")
            
        except Exception as e:
            print(f"❌ 温度获取失败: {e}")
        finally:
            device.disconnect()
    else:
        print("❌ 设备连接失败")
        print("请检查: 1) 设备IP地址是否正确 2) 设备是否开机 3) 网络连接")
    
    # 方式2: 上下文管理器 (推荐)
    print(f"\n🔧 方式2: 上下文管理器使用 (推荐)")
    try:
        with FotricEnhancedDevice(
            ip="192.168.1.100",
            simulation_mode=False
        ) as device:
            print("✅ 自动连接设备")
            
            # 批量获取温度
            points = [(x, y) for x in range(0, 640, 128) for y in range(0, 480, 96)]
            temps = device.get_temperature_array(points)
            
            print(f"📈 获取到 {len(temps)} 个温度点")
            avg_temp = np.mean(list(temps.values()))
            print(f"📊 平均温度: {avg_temp:.2f}°C")
        print("✅ 自动断开连接")
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")

def temperature_analysis_example():
    """温度分析示例"""
    
    print(f"\n🔍 温度分析示例")
    print("=" * 50)
    
    with FotricEnhancedDevice(
        ip="192.168.1.100",
        username="admin",
        password="admin",
        simulation_mode=False
    ) as device:
        # 获取温度网格
        grid = device.get_temperature_grid(grid_size=8)
        
        if grid.size > 0:
            print(f"📐 温度网格: {grid.shape}")
            print(f"🌡️ 温度范围: {grid.min():.1f}°C ~ {grid.max():.1f}°C")
            print(f"📊 平均温度: {grid.mean():.2f}°C")
            print(f"📈 温度标准差: {grid.std():.2f}°C")
            
            # 找到最热点和最冷点
            hot_idx = np.unravel_index(np.argmax(grid), grid.shape)
            cold_idx = np.unravel_index(np.argmin(grid), grid.shape)
            
            print(f"🔥 最热点: 位置{hot_idx}, 温度{grid[hot_idx]:.2f}°C")
            print(f"❄️ 最冷点: 位置{cold_idx}, 温度{grid[cold_idx]:.2f}°C")

def real_time_monitoring():
    """实时监控示例"""
    
    print(f"\n⏱️ 实时温度监控示例 (5秒)")
    print("=" * 50)
    
    with FotricEnhancedDevice(
        ip="192.168.1.100",
        username="admin",
        password="admin",
        simulation_mode=False
    ) as device:
        monitor_points = [
            (320, 240, "中心"),
            (100, 100, "左上"),
            (540, 380, "右下")
        ]
        
        start_time = time.time()
        while time.time() - start_time < 5:
            print(f"\n⏰ {time.strftime('%H:%M:%S')}")
            
            for x, y, name in monitor_points:
                temp = device.get_point_temperature(x, y)
                print(f"  {name:4s}: {temp:6.2f}°C")
            
            time.sleep(1)

def hotspot_detection():
    """热点检测示例"""
    
    print(f"\n🔥 热点检测示例")
    print("=" * 50)
    
    with FotricEnhancedDevice(
        ip="192.168.1.100",
        username="admin",
        password="admin",
        simulation_mode=False
    ) as device:
        # 获取高分辨率网格
        grid = device.get_temperature_grid(grid_size=10)
        
        if grid.size > 0:
            # 定义热点阈值 (平均温度 + 1个标准差)
            threshold = grid.mean() + grid.std()
            print(f"🌡️ 热点阈值: {threshold:.2f}°C")
            
            # 找到所有热点
            hotspots = np.where(grid > threshold)
            num_hotspots = len(hotspots[0])
            
            print(f"🔥 检测到 {num_hotspots} 个热点:")
            
            for i in range(min(5, num_hotspots)):  # 显示前5个
                row, col = hotspots[0][i], hotspots[1][i]
                temp = grid[row, col]
                print(f"  热点 {i+1}: 位置({row}, {col}), 温度{temp:.2f}°C")

def performance_benchmark():
    """性能基准测试"""
    
    print(f"\n⚡ 性能基准测试")
    print("=" * 50)
    
    with FotricEnhancedDevice(
        ip="192.168.1.100",
        username="admin",
        password="admin",
        simulation_mode=False
    ) as device:
        # 测试单点温度获取性能
        test_point = (320, 240)
        iterations = 100
        
        start_time = time.time()
        for _ in range(iterations):
            device.get_point_temperature(*test_point, use_cache=False)
        no_cache_time = time.time() - start_time
        
        # 清除缓存后测试缓存性能
        device.clear_cache()
        start_time = time.time()
        for _ in range(iterations):
            device.get_point_temperature(*test_point, use_cache=True)
        with_cache_time = time.time() - start_time
        
        print(f"📊 性能测试结果 ({iterations} 次请求):")
        print(f"  无缓存: {no_cache_time:.3f}s ({no_cache_time/iterations*1000:.1f}ms/次)")
        print(f"  有缓存: {with_cache_time:.3f}s ({with_cache_time/iterations*1000:.1f}ms/次)")
        
        if no_cache_time > 0:
            speedup = no_cache_time / with_cache_time
            print(f"  缓存加速比: {speedup:.1f}x")

def integration_example():
    """集成应用示例"""
    
    print(f"\n🏗️ 集成应用示例")
    print("=" * 50)
    
    class TemperatureMonitor:
        """温度监控器类示例"""
        
        def __init__(self):
            self.device = FotricEnhancedDevice(
                ip="192.168.1.100",
                username="admin",
                password="admin",
                simulation_mode=False
            )
            self.alert_threshold = 35.0  # 报警阈值
        
        def start_monitoring(self):
            """开始监控"""
            if not self.device.connect():
                raise RuntimeError("设备连接失败")
            print("✅ 监控器启动成功")
        
        def check_temperature(self, x, y):
            """检查温度并报警"""
            temp = self.device.get_point_temperature(x, y)
            
            if temp is not None:
                if temp > self.alert_threshold:
                    print(f"🚨 温度报警! 位置({x}, {y}): {temp:.2f}°C > {self.alert_threshold}°C")
                    return "ALERT"
                else:
                    print(f"✅ 温度正常. 位置({x}, {y}): {temp:.2f}°C")
                    return "NORMAL"
            else:
                print(f"❌ 温度获取失败. 位置({x}, {y})")
                return "ERROR"
        
        def stop_monitoring(self):
            """停止监控"""
            self.device.disconnect()
            print("🛑 监控器已停止")
    
    # 使用示例
    monitor = TemperatureMonitor()
    
    try:
        monitor.start_monitoring()
        
        # 检查几个关键点
        critical_points = [(100, 100), (320, 240), (540, 380)]
        
        for x, y in critical_points:
            status = monitor.check_temperature(x, y)
            
        monitor.stop_monitoring()
        
    except Exception as e:
        print(f"❌ 监控过程出错: {e}")

def main():
    """主函数 - 运行所有示例"""
    
    print("🚀 FOTRIC 628ch 增强版使用示例集")
    print("基于C# DLDemo核心功能的Python实现")
    print("=" * 60)
    
    # 运行所有示例
    examples = [
        ("基础温度监控", simple_temperature_monitoring),
        ("温度分析", temperature_analysis_example),
        ("实时监控", real_time_monitoring),
        ("热点检测", hotspot_detection),
        ("性能测试", performance_benchmark),
        ("集成应用", integration_example)
    ]
    
    for name, func in examples:
        try:
            print(f"\n{'='*20} {name} {'='*20}")
            func()
        except Exception as e:
            print(f"❌ {name} 示例运行失败: {e}")
    
    print(f"\n🎉 所有示例运行完成!")
    print("=" * 60)
    print("💡 使用提示:")
    print("1. 已设置为连接真实设备模式")
    print("2. 使用默认认证信息: admin/admin")
    print("3. 如需要请根据实际情况调整IP地址和认证信息")
    print("3. 使用上下文管理器确保资源正确释放")
    print("4. 批量操作时使用专门的批量方法")
    print("5. 利用缓存机制提高性能")

if __name__ == "__main__":
    main()