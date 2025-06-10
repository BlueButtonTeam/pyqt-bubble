#!/usr/bin/env python3
"""
IntelliAnnotate 调试打包脚本

创建目录式分发版本，便于调试
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

def build_application():
    """构建应用程序（目录版本）"""
    print("🔨 开始构建 IntelliAnnotate 应用（调试版本）...")
    
    # PyInstaller 命令（目录版本）
    cmd = [
        'pyinstaller',
        '--name=IntelliAnnotate',  # 设置应用名称
        '--windowed',  # 无控制台窗口
        '--clean',     # 清理临时文件
        '--noconfirm', # 不要确认覆盖
        
        # 详细的PySide6模块导入
        '--hidden-import=PySide6',
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui', 
        '--hidden-import=PySide6.QtWidgets',
        
        # 其他依赖库
        '--hidden-import=PIL',
        '--hidden-import=fitz',
        '--hidden-import=ezdxf',
        
        # 收集数据文件
        '--collect-all=PySide6',
        
        # 主程序文件
        'intelliannotate.py'
    ]
    
    print("🚀 执行打包命令...")
    print("   " + " ".join(cmd))
    
    try:
        # 执行打包命令，显示实时输出
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 universal_newlines=True, bufsize=1)
        
        # 实时显示输出
        for line in process.stdout:
            print(line.rstrip())
        
        process.wait()
        
        if process.returncode == 0:
            print("✅ 打包完成！")
            return True
        else:
            print("❌ 打包失败！")
            return False
        
    except Exception as e:
        print(f"❌ 打包过程出错: {e}")
        return False

def create_portable_version():
    """创建便携版本"""
    print("📦 创建便携版本...")
    
    # 检查dist目录
    dist_dir = Path("dist/IntelliAnnotate")
    if not dist_dir.exists():
        print("   ❌ 未找到构建输出目录")
        return False
    
    # 创建发布目录
    release_dir = Path("release")
    if release_dir.exists():
        shutil.rmtree(release_dir)
    
    # 复制整个应用目录
    shutil.copytree(dist_dir, release_dir)
    print(f"   ✅ 复制应用到: {release_dir}")
    
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

## 重要提示

- 请保持整个文件夹完整，不要移动或删除任何文件
- 如需复制到其他电脑，请复制整个文件夹

## 技术支持

如有问题，请联系开发者。
"""
    
    with open(release_dir / "使用说明.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print(f"   ✅ 创建使用说明: {release_dir}/使用说明.txt")
    
    # 计算目录大小
    total_size = sum(f.stat().st_size for f in release_dir.rglob('*') if f.is_file())
    total_size_mb = total_size / (1024 * 1024)
    print(f"   📊 应用总大小: {total_size_mb:.1f} MB")
    
    return True

def main():
    """主函数"""
    print("🎯 IntelliAnnotate 调试打包工具")
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
        print("   - dist/IntelliAnnotate/ (PyInstaller输出目录)")
        print("   - release/ (便携版目录)")
        print("   - release/使用说明.txt (用户指南)")
        
        print("\n💡 提示:")
        print("   - 可以直接分发 release 文件夹")
        print("   - 双击 release/IntelliAnnotate.exe 启动应用")
        print("   - 目录版本更稳定，推荐使用")
        
        return True
    else:
        print("\n❌ 打包失败，请检查错误信息")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 