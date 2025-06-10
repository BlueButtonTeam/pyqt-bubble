#!/usr/bin/env python3
"""
IntelliAnnotate - 智能图纸标注工具 (集成EasyOCR)

Requirements:
PySide6>=6.0.0
Pillow>=9.0.0
PyMuPDF>=1.20.0
ezdxf>=1.0.0
easyocr>=1.7.0
opencv-python>=4.8.0
numpy>=1.24.0
torch>=2.0.0
torchvision>=0.15.0

一个功能完备的2D机械图纸标注应用，支持多种图纸格式加载、
使用EasyOCR进行真实的图纸文字识别、可交互的气泡标注和实时属性编辑。
专为机械制造业紧固件图纸设计。
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QAction

from utils.constants import APP_NAME, APP_VERSION
from ui.main_window import MainWindow


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用属性
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("IntelliAnnotate Inc.")
    
    # 设置样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main()) 