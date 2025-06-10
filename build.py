#!/usr/bin/env python3
"""
IntelliAnnotate 应用打包脚本

使用 PyInstaller 将应用打包为独立的可执行文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def clean_build_directories():
    """清理之前的构建目录"""
    print("🧹 清理之前的构建文件...")
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.spec']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   删除目录: {dir_name}")
    
    import glob
    for pattern in files_to_clean:
        for file in glob.glob(pattern):
            os.remove(file)
            print(f"   删除文件: {file}")

def create_app_icon():
    """创建应用图标（如果不存在）"""
    icon_path = "icon.ico"
    if not os.path.exists(icon_path):
        print("ℹ️  未找到图标文件，将使用默认设置")
        return None
    return icon_path

def build_application():
    """构建应用程序"""
    print("🔨 开始构建 IntelliAnnotate 应用...")
    
    # 基本的 PyInstaller 命令
    cmd = [
        'pyinstaller',
        '--name=IntelliAnnotate',  # 设置应用名称
        '--windowed',  # 无控制台窗口
        '--onefile',   # 打包成单个文件
        '--clean',     # 清理临时文件
        '--noconfirm', # 不要确认覆盖
        
        # 详细的PySide6模块导入
        '--hidden-import=PySide6',
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui', 
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=PySide6.QtOpenGL',
        '--hidden-import=PySide6.QtOpenGLWidgets',
        '--hidden-import=PySide6.QtPrintSupport',
        
        # 其他依赖库
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        '--hidden-import=fitz',
        '--hidden-import=ezdxf',
        '--hidden-import=shiboken6',
        
        # 收集所有数据文件
        '--collect-all=PySide6',
        '--collect-data=PySide6',
        '--collect-binaries=PySide6',
        
        # 添加路径
        '--paths=.',
        
        # 主程序文件
        'intelliannotate.py'
    ]
    
    # 添加图标（如果存在）
    icon_path = create_app_icon()
    if icon_path:
        cmd.extend(['--icon', icon_path])
    
    print("🚀 执行打包命令...")
    print("   " + " ".join(cmd))
    
    try:
        # 执行打包命令
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ 打包完成！")
        return True
        
    except subprocess.CalledProcessError as e:
        print("❌ 打包失败！")
        print("错误输出:")
        print(e.stderr)
        print("\n标准输出:")
        print(e.stdout)
        return False

def create_portable_version():
    """创建便携版本"""
    print("📦 创建便携版本...")
    
    # 创建发布目录
    release_dir = Path("release")
    release_dir.mkdir(exist_ok=True)
    
    # 复制可执行文件
    exe_path = Path("dist/IntelliAnnotate.exe")
    if exe_path.exists():
        shutil.copy2(exe_path, release_dir / "IntelliAnnotate.exe")
        print(f"   ✅ 复制可执行文件到: {release_dir}/IntelliAnnotate.exe")
        
        # 创建使用说明
        readme_content = """# IntelliAnnotate - 智能图纸标注工具

## 使用方法

1. 双击 IntelliAnnotate.exe 启动应用
2. 点击"打开文件"加载图纸（支持PNG、JPG、PDF、DXF格式）
3. 点击"AI识别"自动生成标注
4. 点击"区域标注"手动添加标注
5. 右键点击标注可以删除或更改样式

## 快捷操作

- 鼠标滚轮：缩放图纸
- 鼠标中键/右键拖拽：平移图纸
- 左键点击：选择标注
- 右键点击标注：显示操作菜单

## 系统要求

- Windows 10 或更高版本
- 无需安装Python环境

## 技术支持

如有问题，请联系开发者。
"""
        
        with open(release_dir / "使用说明.txt", "w", encoding="utf-8") as f:
            f.write(readme_content)
        
        print(f"   ✅ 创建使用说明: {release_dir}/使用说明.txt")
        
        # 计算文件大小
        exe_size = exe_path.stat().st_size / (1024 * 1024)  # MB
        print(f"   📊 可执行文件大小: {exe_size:.1f} MB")
        
        return True
    else:
        print("   ❌ 未找到可执行文件")
        return False

def main():
    """主函数"""
    print("🎯 IntelliAnnotate 应用打包工具")
    print("=" * 50)
    
    # 检查主文件是否存在
    if not os.path.exists("intelliannotate.py"):
        print("❌ 错误: 未找到 intelliannotate.py 文件")
        print("   请确保在正确的目录中运行此脚本")
        return False
    
    # 清理构建目录
    clean_build_directories()
    
    # 构建应用
    success = build_application()
    
    if success:
        # 创建便携版本
        create_portable_version()
        
        print("\n🎉 打包完成！")
        print("📁 输出文件:")
        print("   - dist/IntelliAnnotate.exe (PyInstaller输出)")
        print("   - release/IntelliAnnotate.exe (便携版)")
        print("   - release/使用说明.txt (用户指南)")
        
        print("\n💡 提示:")
        print("   - 可以直接分发 release 文件夹中的内容")
        print("   - 单个可执行文件，无需安装Python环境")
        print("   - 首次启动可能较慢，属于正常现象")
        
        return True
    else:
        print("\n❌ 打包失败，请检查错误信息")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 