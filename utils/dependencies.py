#!/usr/bin/env python3
"""
依赖检查和导入管理模块
"""

import sys

# 检查OCR相关依赖
HAS_OCR_SUPPORT = True
OCR_IMPORT_ERROR = None

try:
    from PIL import Image
    import fitz  # PyMuPDF
    import ezdxf
    import easyocr
    import cv2
    import numpy as np
    import torch
except ImportError as e:
    print(f"⚠️  OCR相关依赖库缺失: {e}")
    print("OCR功能将被禁用，应用仍可正常使用其他功能")
    HAS_OCR_SUPPORT = False
    OCR_IMPORT_ERROR = str(e)
    
    # 创建基本的numpy和PIL替代品
    try:
        from PIL import Image
    except ImportError:
        Image = None
    
    try:
        import numpy as np
    except ImportError:
        # 创建基本的numpy替代
        class np:
            @staticmethod
            def array(data):
                return data
            
            @staticmethod
            def mean(data, axis=None):
                return sum(data) / len(data) if data else 0

# 检查GPU支持
HAS_GPU_SUPPORT = False
if HAS_OCR_SUPPORT:
    try:
        HAS_GPU_SUPPORT = torch.cuda.is_available()
    except:
        HAS_GPU_SUPPORT = False

def check_dependencies():
    """检查所有依赖项并返回状态信息"""
    status = {
        'ocr_support': HAS_OCR_SUPPORT,
        'gpu_support': HAS_GPU_SUPPORT,
        'error_message': OCR_IMPORT_ERROR,
        'missing_features': []
    }
    
    if not HAS_OCR_SUPPORT:
        status['missing_features'].extend([
            'OCR文字识别',
            'PDF文件加载',
            'DXF文件加载',
            '图像预处理'
        ])
    
    if not HAS_GPU_SUPPORT and HAS_OCR_SUPPORT:
        status['missing_features'].append('GPU加速')
    
    return status

def get_requirements_message():
    """获取依赖安装提示信息"""
    if not HAS_OCR_SUPPORT:
        return (
            "OCR功能未启用！\n\n"
            "请安装完整的依赖包以启用OCR功能:\n"
            "pip install -r requirements.txt"
        )
    return None 