#!/usr/bin/env python3
"""
IntelliAnnotate 启动脚本
智能机械图纸标注工具 (集成EasyOCR)
"""

import sys
import os
from pathlib import Path

def check_dependencies():
    """检查最基本的依赖包"""
    required_packages = ['PySide6']
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ 缺少以下基本依赖包:")
        for pkg in missing_packages:
            print(f"   - {pkg}")
        print("\n请运行以下命令安装基本依赖:")
        print("pip install PySide6")
        return False
    
    print("✅ 基本依赖包已安装")
    return True

def main():
    """主函数"""
    print("🔍 IntelliAnnotate - 智能机械图纸标注工具")
    print("=" * 50)
    
    # 检查基本依赖
    if not check_dependencies():
        print("\n⚠️  部分功能可能不可用，建议安装完整依赖:")
        print("pip install -r requirements.txt")
        print("\n继续启动应用...")
    
    # 导入主程序
    try:
        from intelliannotate import main as run_app
        print("🚀 启动应用程序...")
        run_app()
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print("\n请检查是否安装了所有必要的依赖包:")
        print("pip install -r requirements.txt")
        sys.exit(1)

if __name__ == "__main__":
    main() 