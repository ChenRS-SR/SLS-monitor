"""
文件操作工具函数
提供文件和目录处理的辅助功能
"""

import os
import shutil
from datetime import datetime
import csv
import json

def ensure_directory(directory):
    """
    确保目录存在，如果不存在则创建
    
    Args:
        directory: 目录路径
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"✅ Created directory: {directory}")

def backup_file(file_path, backup_dir="backups"):
    """
    创建文件备份
    
    Args:
        file_path: 要备份的文件路径
        backup_dir: 备份目录名称
    
    Returns:
        备份文件路径，失败则返回None
    """
    if not os.path.exists(file_path):
        print(f"❌ Source file does not exist: {file_path}")
        return None
    
    # Create backup directory
    ensure_directory(backup_dir)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(file_path)
    backup_name = f"{os.path.splitext(base_name)[0]}_{timestamp}{os.path.splitext(base_name)[1]}"
    backup_path = os.path.join(backup_dir, backup_name)
    
    try:
        shutil.copy2(file_path, backup_path)
        print(f"✅ Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None

def save_csv(data, file_path, headers=None, append=False):
    """
    保存数据到CSV文件
    
    Args:
        data: 字典列表或二维列表
        file_path: CSV文件保存路径
        headers: 列标题列表（可选）
        append: 是否追加到现有文件
    
    Returns:
        bool: 成功返回True，失败返回False
    """
    mode = 'a' if append else 'w'
    try:
        with open(file_path, mode, newline='', encoding='utf-8') as f:
            if isinstance(data[0], dict):
                if headers is None:
                    headers = data[0].keys()
                writer = csv.DictWriter(f, fieldnames=headers)
                if not append:
                    writer.writeheader()
                writer.writerows(data)
            else:
                writer = csv.writer(f)
                if headers and not append:
                    writer.writerow(headers)
                writer.writerows(data)
        print(f"✅ {'Appended to' if append else 'Saved'} CSV file: {file_path}")
        return True
    except Exception as e:
        print(f"❌ CSV save failed: {e}")
        return False

def save_json(data, file_path, pretty=True):
    """
    保存数据到JSON文件
    
    Args:
        data: 要保存的数据
        file_path: JSON文件保存路径
        pretty: 是否格式化JSON（使用缩进）
    
    Returns:
        bool: 成功返回True，失败返回False
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(data, f, indent=4, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)
        print(f"✅ Saved JSON file: {file_path}")
        return True
    except Exception as e:
        print(f"❌ JSON save failed: {e}")
        return False

def load_json(file_path):
    """
    从JSON文件加载数据
    
    Args:
        file_path: JSON文件路径
    
    Returns:
        加载的数据，失败则返回None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"❌ JSON load failed: {e}")
        return None