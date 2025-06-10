#!/usr/bin/env python3
"""
OCR识别工作线程模块
"""

import re
from PySide6.QtCore import QObject, QRunnable, Signal
from utils.dependencies import HAS_OCR_SUPPORT

if HAS_OCR_SUPPORT:
    import cv2
    import numpy as np
    import torch
    import easyocr
    import fitz


class OCRWorkerSignals(QObject):
    """OCR工作线程信号"""
    finished = Signal(list)  # OCR完成信号，传递识别结果列表
    progress = Signal(int)   # 进度信号
    error = Signal(str)      # 错误信号


class OCRWorker(QRunnable):
    """OCR识别工作线程"""
    
    def __init__(self, image_path: str, languages: list = ['ch_sim', 'en']):
        super().__init__()
        self.image_path = image_path
        self.languages = languages
        self.signals = OCRWorkerSignals()
        self._reader = None
        
    def run(self):
        """执行OCR识别"""
        if not HAS_OCR_SUPPORT:
            self.signals.error.emit("OCR功能未启用，请安装完整依赖包")
            return
            
        try:
            # 初始化EasyOCR
            self.signals.progress.emit(10)
            self._reader = easyocr.Reader(self.languages, gpu=torch.cuda.is_available())
            
            self.signals.progress.emit(30)
            
            # 读取图像
            if self.image_path.lower().endswith('.pdf'):
                # 处理PDF文件
                image = self._extract_image_from_pdf()
            else:
                # 处理普通图像文件
                image = cv2.imread(self.image_path)
                
            if image is None:
                raise ValueError(f"无法读取图像文件: {self.image_path}")
                
            self.signals.progress.emit(50)
            
            # 图像预处理 - 针对机械图纸优化
            processed_image = self._preprocess_mechanical_drawing(image)
            
            self.signals.progress.emit(70)
            
            # 执行OCR识别
            results = self._reader.readtext(processed_image, detail=1)
            
            self.signals.progress.emit(90)
            
            # 处理识别结果
            processed_results = self._process_ocr_results(results, image.shape)
            
            self.signals.progress.emit(100)
            self.signals.finished.emit(processed_results)
            
        except Exception as e:
            self.signals.error.emit(f"OCR识别失败: {str(e)}")
    
    def _extract_image_from_pdf(self):
        """从PDF中提取图像"""
        doc = fitz.open(self.image_path)
        page = doc[0]  # 获取第一页
        mat = fitz.Matrix(2.0, 2.0)  # 2倍缩放提高质量
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        
        # 转换为OpenCV格式
        nparr = np.frombuffer(img_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        doc.close()
        return image
    
    def _preprocess_mechanical_drawing(self, image):
        """机械图纸预处理 - 专门针对紧固件图纸优化"""
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 增强对比度
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # 降噪
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        # 自适应阈值化 - 对机械图纸文字效果好
        adaptive_thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # 形态学操作 - 连接断开的文字
        kernel = np.ones((2,2), np.uint8)
        processed = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_CLOSE, kernel)
        
        return processed
    
    def _process_ocr_results(self, results, image_shape):
        """处理OCR识别结果"""
        processed_results = []
        height, width = image_shape[:2]
        
        for result in results:
            bbox, text, confidence = result
            
            # 过滤低置信度和无意义文本
            if confidence < 0.3:
                continue
                
            # 清理文本
            clean_text = self._clean_text(text)
            if not clean_text or len(clean_text.strip()) < 2:
                continue
            
            # 计算边界框中心点
            bbox_array = np.array(bbox)
            center_x = int(np.mean(bbox_array[:, 0]))
            center_y = int(np.mean(bbox_array[:, 1]))
            
            # 计算边界框尺寸
            bbox_width = int(np.max(bbox_array[:, 0]) - np.min(bbox_array[:, 0]))
            bbox_height = int(np.max(bbox_array[:, 1]) - np.min(bbox_array[:, 1]))
            
            # 识别文本类型（针对机械图纸）
            text_type = self._classify_mechanical_text(clean_text)
            
            processed_results.append({
                'text': clean_text,
                'confidence': confidence,
                'center_x': center_x,
                'center_y': center_y,
                'bbox_width': bbox_width,
                'bbox_height': bbox_height,
                'bbox': bbox,
                'text_type': text_type,
                'original_text': text
            })
        
        return processed_results
    
    def _clean_text(self, text):
        """清理识别的文本"""
        # 移除多余空格和特殊字符
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 修正常见的OCR错误（针对机械图纸）
        corrections = {
            'Φ': 'Φ',  # 直径符号
            '∅': 'Φ',
            'ø': 'Φ',
            'M': 'M',   # 螺纹标记
            '×': '×',   # 乘号
            '°': '°',   # 度数符号
        }
        
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        
        return text
    
    def _classify_mechanical_text(self, text):
        """分类机械图纸文本类型"""
        # 螺纹规格
        if re.match(r'M\d+', text, re.IGNORECASE):
            return 'thread_spec'
        
        # 直径标注
        if 'Φ' in text or '∅' in text or 'ø' in text:
            return 'diameter'
        
        # 尺寸标注
        if re.search(r'\d+\.?\d*\s*[×x]\s*\d+\.?\d*', text):
            return 'dimension'
        
        # 角度标注
        if '°' in text and any(c.isdigit() for c in text):
            return 'angle'
        
        # 数值
        if re.match(r'^\d+\.?\d*$', text):
            return 'number'
        
        # 材料标记
        material_keywords = ['钢', '铁', '铜', '铝', '不锈钢', 'steel', 'iron', 'copper', 'aluminum']
        if any(keyword.lower() in text.lower() for keyword in material_keywords):
            return 'material'
        
        # 表面处理
        surface_keywords = ['镀锌', '发黑', '阳极', '喷涂', 'zinc', 'black', 'anodize', 'coating']
        if any(keyword.lower() in text.lower() for keyword in surface_keywords):
            return 'surface_treatment'
        
        # 默认为标注文本
        return 'annotation' 