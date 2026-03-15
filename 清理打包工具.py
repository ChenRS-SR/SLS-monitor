#!/usr/bin/env python3
"""
SLS项目清理和打包工具
清理不必要的文件，准备部署包
"""

import os
import shutil
import glob
from datetime import datetime

def clean_pycache():
    """清理Python缓存文件"""
    print("清理Python缓存文件...")
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                cache_path = os.path.join(root, dir_name)
                print(f"  删除: {cache_path}")
                shutil.rmtree(cache_path)

def clean_logs():
    """清理日志文件"""
    print("清理日志文件...")
    log_dirs = ['logs', 'output/logs']
    for log_dir in log_dirs:
        if os.path.exists(log_dir):
            for log_file in glob.glob(os.path.join(log_dir, '*.log')):
                print(f"  删除: {log_file}")
                os.remove(log_file)

def clean_outputs():
    """清理输出文件"""
    print("清理输出文件...")
    output_patterns = [
        'output/*.png',
        'output/*.npy', 
        'output/*.csv',
        'captures/*.jpg',
        'captures/*.png',
        'data/*.tmp'
    ]
    
    for pattern in output_patterns:
        for file_path in glob.glob(pattern):
            print(f"  删除: {file_path}")
            os.remove(file_path)

def clean_test_files():
    """清理测试和调试文件"""
    print("清理测试文件...")
    test_patterns = [
        'test_*.py',
        'debug_*.py',
        '*_test.py'
    ]
    
    # 但保留重要的测试文件
    important_tests = [
        'test_new_ir8062_integration.py'  # 这个用于验证部署
    ]
    
    for pattern in test_patterns:
        for file_path in glob.glob(pattern):
            if os.path.basename(file_path) not in important_tests:
                print(f"  删除: {file_path}")
                os.remove(file_path)

def create_deploy_package():
    """创建部署包清单"""
    print("创建部署包清单...")
    
    deploy_files = []
    
    # 核心文件
    core_files = [
        'run.py',
        'requirements.txt', 
        '部署指南.md'
    ]
    
    # 核心目录
    core_dirs = [
        'sls_monitor',
        'pysenxor-master'
    ]
    
    # 输出目录 (保留结构但清空内容)
    output_dirs = [
        'output',
        'logs', 
        'captures',
        'data'
    ]
    
    # 检查文件存在性
    print("\n=== 部署包清单 ===")
    print("✅ 核心文件:")
    for file in core_files:
        if os.path.exists(file):
            deploy_files.append(file)
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} (缺失)")
    
    print("✅ 核心目录:")
    for dir in core_dirs:
        if os.path.exists(dir):
            deploy_files.append(dir)
            print(f"  ✅ {dir}")
        else:
            print(f"  ❌ {dir} (缺失)")
    
    print("✅ 输出目录:")
    for dir in output_dirs:
        if not os.path.exists(dir):
            os.makedirs(dir)
            print(f"  ✅ {dir} (已创建)")
        else:
            print(f"  ✅ {dir}")
    
    # 生成打包脚本
    package_script = f"""
# SLS项目打包脚本
# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# 压缩命令 (使用7zip或其他工具)
# 7z a SLS_v2.0_{datetime.now().strftime('%Y%m%d')}.zip SLS/

# 或使用PowerShell压缩
# Compress-Archive -Path SLS -DestinationPath SLS_v2.0_{datetime.now().strftime('%Y%m%d')}.zip

echo "SLS项目打包完成！"
echo "包含的文件和目录:"
"""
    
    for item in deploy_files:
        package_script += f"echo \"  - {item}\"\n"
    
    with open('打包脚本.bat', 'w', encoding='utf-8') as f:
        f.write(package_script)
    
    print(f"\n✅ 打包脚本已生成: 打包脚本.bat")

def main():
    """主清理流程"""
    print("🧹 SLS项目清理工具")
    print("=" * 50)
    
    # 确认操作
    response = input("是否开始清理？(y/N): ")
    if response.lower() != 'y':
        print("取消清理")
        return
    
    # 执行清理
    clean_pycache()
    clean_logs()
    clean_outputs()
    
    # 询问是否删除测试文件
    response = input("\n是否删除测试文件？(y/N): ")
    if response.lower() == 'y':
        clean_test_files()
    
    # 创建部署包
    create_deploy_package()
    
    print("\n🎉 清理完成！")
    print("现在可以压缩SLS文件夹进行部署了。")
    print("参考文件: 部署指南.md")

if __name__ == "__main__":
    main()