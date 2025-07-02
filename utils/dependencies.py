#!/usr/bin/env python3
"""
依赖检查和导入管理模块
"""

import sys

# 检查基础依赖
HAS_OCR_SUPPORT = True
HAS_PADDLE_OCR = False
OCR_IMPORT_ERROR = None

try:
    from PIL import Image
    import fitz  # PyMuPDF
    import ezdxf
    import cv2
    import numpy as np
except ImportError as e:
    print(f"⚠️  基础依赖库缺失: {e}")
    print("应用功能将受限")
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

# 检查PaddleOCR支持
try:
    import paddle
    from core.paddle_ocr_worker import PaddleOCRWorker
    HAS_PADDLE_OCR = True
    print("✅ PaddleOCR支持已启用")
except ImportError as e:
    print(f"❌ PaddleOCR不可用: {e}")
    print("OCR功能将被禁用")
    HAS_PADDLE_OCR = False
    HAS_OCR_SUPPORT = False

# 检查GPU支持 - 与infer_tu2.py保持一致
HAS_GPU_SUPPORT = False
if HAS_PADDLE_OCR:
    try:
        import paddle
        # 检查是否编译了CUDA支持
        HAS_GPU_SUPPORT = paddle.device.is_compiled_with_cuda()
        if HAS_GPU_SUPPORT:
            print("✅ GPU支持已启用，与infer_tu2.py配置一致")
        else:
            print("⚠️ GPU支持未启用，将使用CPU")
    except Exception as e:
        print(f"❌ GPU检查失败: {e}")
        HAS_GPU_SUPPORT = False

def check_dependencies():
    """检查所有依赖项并返回状态信息"""
    status = {
        'ocr_support': HAS_PADDLE_OCR,
        'gpu_support': HAS_GPU_SUPPORT,
        'error_message': OCR_IMPORT_ERROR,
        'missing_features': []
    }

    if not HAS_PADDLE_OCR:
        status['missing_features'].extend([
            'PaddleOCR文字识别',
            'PDF文件加载',
            'DXF文件加载',
            '图像预处理'
        ])

    if not HAS_GPU_SUPPORT and HAS_PADDLE_OCR:
        status['missing_features'].append('GPU加速')

    return status

def get_requirements_message():
    """获取依赖安装提示信息"""
    if not HAS_PADDLE_OCR:
        return (
            "PaddleOCR功能未启用！\n\n"
            "请检查PaddleOCR安装和模型文件配置。"
        )
    return None