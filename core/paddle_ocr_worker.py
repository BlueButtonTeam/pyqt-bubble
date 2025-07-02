#!/usr/bin/env python3
"""
PaddleOCR识别工作线程模块 - 使用您训练的专用模型
针对机械图纸进行深度优化的OCR识别系统
"""

import sys
import os
import cv2
import numpy as np
import logging
import re
from PySide6.QtCore import QObject, QRunnable, Signal
from typing import List, Dict, Tuple, Optional, Any

# 添加PaddleOCR路径 - 使用本地文件
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # pyqt-bubble2目录
sys.path.insert(0, parent_dir)  # 添加pyqt-bubble2到路径

# 设置与infer_tu2.py相同的GPU环境变量
os.environ["FLAGS_allocator_strategy"] = 'auto_growth'
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# 导入PaddleOCR相关模块
try:
    # 导入PaddleOCR核心模块
    from ppocr.data import create_operators, transform
    from ppocr.modeling.architectures import build_model
    from ppocr.postprocess import build_post_process
    from ppocr.utils.save_load import load_model
    from ppocr.utils.utility import get_image_file_list
    import paddle
    import yaml
    import copy
    import numpy as np
    import cv2
    PADDLE_AVAILABLE = True
    
    # 检测GPU支持
    HAS_GPU_SUPPORT = False
    try:
        if paddle.is_compiled_with_cuda():
            # 检查GPU是否实际可用
            gpu_count = paddle.device.cuda.device_count()
            HAS_GPU_SUPPORT = gpu_count > 0
            if HAS_GPU_SUPPORT:
                print(f"✅ 检测到{gpu_count}个可用GPU")
            else:
                print("⚠️ 已编译CUDA支持，但未检测到可用GPU设备")
        else:
            print("⚠️ PaddlePaddle未使用CUDA编译")
    except Exception as e:
        print(f"⚠️ 检测GPU支持时出错: {e}")
        HAS_GPU_SUPPORT = False
    
    print("✅ PaddleOCR模块导入成功")
except ImportError as e:
    logging.warning(f"PaddleOCR not available: {e}")
    PADDLE_AVAILABLE = False
    HAS_GPU_SUPPORT = False
    print(f"❌ PaddleOCR模块导入失败: {e}")


class PaddleOCRWorkerSignals(QObject):
    """PaddleOCR工作线程信号"""
    finished = Signal(list)  # OCR完成信号，传递识别结果列表
    progress = Signal(int)   # 进度信号
    error = Signal(str)      # 错误信号


class PaddleOCRWorker(QRunnable):
    """PaddleOCR识别工作线程 - 使用您训练的专用模型"""
    
    def __init__(self, image_path: str, languages: list = ['ch_sim', 'en'], masked_regions: list = None, force_cpu: bool = False, cpu_threads: int = 8):
        super().__init__()
        self.image_path = image_path
        self.languages = languages  # 保持兼容性，但PaddleOCR不使用这个参数
        self.masked_regions = masked_regions or []
        self.signals = PaddleOCRWorkerSignals()
        self.force_cpu = force_cpu  # 是否强制使用CPU
        self.cpu_threads = cpu_threads  # CPU线程数
        
        # 配置字典 - 使用本地文件
        self.config_dict = {
            "ocr_det_config": os.path.join(parent_dir, "model", "det_best_model", "config.yml"),
            "ocr_rec_config": os.path.join(parent_dir, "configs", "rec", "PP-OCRv4", "ch_PP-OCRv4_rec_hgnet.yml")
        }
        
        # OCR处理器
        self.ocr_processor = None
    
    def run(self):
        """执行PaddleOCR识别 - 使用与infer_tu2.py相同的GPU配置"""
        if not PADDLE_AVAILABLE:
            self.signals.error.emit("PaddleOCR功能未启用，请安装PaddlePaddle")
            return

        try:
            # 记录开始时间
            import time
            from datetime import datetime
            start_time = time.time()
            start_datetime = datetime.now()
            print(f"\n📋 OCR任务开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📄 处理文件: {os.path.basename(self.image_path)}")

            # 设置优化环境变量
            os.environ["OMP_NUM_THREADS"] = str(self.cpu_threads)  # 使用用户指定的OpenMP线程数
            os.environ["KMP_AFFINITY"] = "granularity=fine,compact,1,0"  # 线程亲和性

            # 确定使用设备
            use_gpu = HAS_GPU_SUPPORT and not self.force_cpu
            if use_gpu:
                print("🚀 使用GPU进行PaddleOCR识别")
            else:
                print(f"🚀 使用CPU进行PaddleOCR识别 ({self.cpu_threads}线程)" + (" (强制CPU模式)" if self.force_cpu else " (未检测到GPU)"))

            # 初始化OCR处理器
            self.signals.progress.emit(10)
            print("🔧 正在初始化PaddleOCR模型...")
            init_start = time.time()

            # 导入您的OCR处理类 - 从本地文件
            from infer_tu2 import OCR_process

            self.ocr_processor = OCR_process(self.config_dict)
            
            # 配置CPU优化 (当使用CPU时启用MKLDNN)
            if not use_gpu:
                self.ocr_processor.enable_mkldnn = True
                self.ocr_processor.mkldnn_cache_capacity = 10
                self.ocr_processor.cpu_threads = self.cpu_threads  # 使用用户指定的线程数
                # 重新应用配置
                self.ocr_processor._apply_config_to_models()
                print(f"✅ 已启用MKLDNN加速，线程数: {self.cpu_threads}")
            
            init_time = time.time() - init_start
            print(f"✅ 模型初始化完成，耗时: {init_time:.2f}秒")
            self.signals.progress.emit(30)
            
            # 读取图像
            print(f"📖 正在处理文件: {self.image_path}")
            image_start = time.time()
            
            # 检查文件是否存在
            if not os.path.exists(self.image_path):
                raise Exception(f"文件不存在: {self.image_path}")
                
            # 检查路径中是否包含非ASCII字符
            has_non_ascii = any(ord(c) > 127 for c in self.image_path)
            if has_non_ascii:
                print(f"⚠️ 警告: 文件路径包含非ASCII字符，可能导致读取问题: {self.image_path}")
                
                # 尝试创建符号链接到临时目录的ASCII文件名
                try:
                    import tempfile
                    import uuid
                    import shutil
                    temp_dir = tempfile.gettempdir()
                    temp_filename = f"ocr_temp_{uuid.uuid4().hex[:8]}{os.path.splitext(self.image_path)[1]}"
                    temp_path = os.path.join(temp_dir, temp_filename)
                    
                    # 复制文件到临时路径
                    print(f"⚙️ 复制文件到临时ASCII路径: {temp_path}")
                    shutil.copy2(self.image_path, temp_path)
                    
                    # 使用新的临时路径
                    self.image_path = temp_path
                    print(f"✅ 成功创建临时文件: {self.image_path}")
                except Exception as e:
                    print(f"⚠️ 创建临时文件失败: {e}, 继续使用原路径")
            
            # 使用OpenCV读取图像
            image = cv2.imread(self.image_path)
            if image is None:
                # 尝试使用备用方法读取
                try:
                    print("⚠️ OpenCV无法读取图像，尝试使用PIL...")
                    from PIL import Image as PILImage
                    pil_img = PILImage.open(self.image_path)
                    # 将PIL图像转换为OpenCV格式
                    if pil_img.mode == 'RGBA':
                        pil_img = pil_img.convert('RGB')
                    image = np.array(pil_img)
                    # 转换RGB到BGR (OpenCV使用BGR)
                    image = image[:, :, ::-1].copy()
                    print("✅ 使用PIL成功读取图像")
                except Exception as pil_error:
                    raise Exception(f"无法读取图像文件: {self.image_path}\nOpenCV错误: 无法解码图像\nPIL错误: {str(pil_error)}")
            
            image_time = time.time() - image_start
            print(f"🖼️ 图像读取成功，尺寸: {image.shape}，耗时: {image_time:.2f}秒")
            self.signals.progress.emit(50)
            
            # 使用您的OCR处理器进行识别
            print("🔍 开始OCR识别...")
            ocr_start = time.time()
            img_list = [image]
            
            # 调用您的process_imgs方法
            ocr_results = self._process_with_your_ocr(img_list)
            
            ocr_time = time.time() - ocr_start
            print(f"✅ 识别完成，共识别 {len(ocr_results)} 个文本，OCR处理耗时: {ocr_time:.2f}秒")
            self.signals.progress.emit(90)
            
            # 处理结果为PyQt需要的格式
            post_start = time.time()
            final_results = self._format_results_for_pyqt(ocr_results, image.shape)
            post_time = time.time() - post_start
            print(f"✅ 后处理完成，耗时: {post_time:.2f}秒")
            
            # 计算总耗时
            total_time = time.time() - start_time
            end_datetime = datetime.now()
            
            # 显示详细的时间统计
            print("\n⏱️ 时间统计:")
            print(f"  模型初始化: {init_time:.2f}秒 ({(init_time/total_time*100):.1f}%)")
            print(f"  图像读取: {image_time:.2f}秒 ({(image_time/total_time*100):.1f}%)")
            print(f"  OCR处理: {ocr_time:.2f}秒 ({(ocr_time/total_time*100):.1f}%)")
            print(f"  后处理: {post_time:.2f}秒 ({(post_time/total_time*100):.1f}%)")
            print(f"  总耗时: {total_time:.2f}秒")
            print(f"📋 OCR任务结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            
            self.signals.progress.emit(100)
            self.signals.finished.emit(final_results)
            
        except Exception as e:
            error_msg = f"PaddleOCR识别失败: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            self.signals.error.emit(error_msg)
    
    def _process_with_your_ocr(self, img_list):
        """使用您的OCR处理器进行识别"""
        try:
            # 获取检测框
            boxes = self.ocr_processor.ocr_det.predict(img_list)
            if len(boxes) == 0:
                return []
            
            results = []
            for i, i_boxes in enumerate(boxes):
                crop_img_list = []
                sortboxes = self.ocr_processor.sort_boxes(i_boxes)
                
                for box in sortboxes:
                    bbox_info = self.ocr_processor.get_bbox_info(box)
                    crop_img = self.ocr_processor.rectify_crop(img_list[i], bbox_info)
                    crop_img_list.append(crop_img)
                
                # 获取识别结果
                info_stream = self.ocr_processor.ocr_rec.predict(crop_img_list)
                
                for idx, info in enumerate(info_stream):
                    if info and '\t' in info:
                        ocr_str = info.split("\t")
                        text = ocr_str[0]
                        confidence = float(ocr_str[1]) if len(ocr_str) > 1 else 0.9
                        
                        # 过滤掉包含#的文本
                        if '#' not in text and text.strip():
                            results.append({
                                'text': text,
                                'confidence': confidence,
                                'bbox': sortboxes[idx].tolist() if idx < len(sortboxes) else []
                            })
            
            return results
            
        except Exception as e:
            print(f"❌ OCR处理失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _format_results_for_pyqt(self, ocr_results, image_shape):
        """将OCR结果格式化为PyQt需要的格式"""
        formatted_results = []
        
        for result in ocr_results:
            bbox = result['bbox']
            text = result['text']
            confidence = result['confidence']
            
            if not bbox or len(bbox) < 4:
                continue
            
            # 检查bbox是否在屏蔽区域内
            if self._is_bbox_in_masked_region(bbox):
                continue
            
            # 计算中心点和边界框尺寸
            bbox_array = np.array(bbox)
            center_x = int(np.mean(bbox_array[:, 0]))
            center_y = int(np.mean(bbox_array[:, 1]))
            
            # 清理文本
            cleaned_text = self._clean_text(text)
            if not cleaned_text:
                continue
                
            # 计算信息类型（工程图纸文字分类）
            info_type = self._classify_mechanical_text(cleaned_text)
            
            # 创建格式化结果
            formatted_results.append({
                'text': cleaned_text,
                'confidence': confidence,
                'bbox': bbox,
                'center': (center_x, center_y),
                'type': info_type,
                'color': None  # 颜色由UI处理
            })
        
        return formatted_results
    
    def _is_bbox_in_masked_region(self, bbox):
        """检查bbox是否在屏蔽区域内"""
        if not self.masked_regions:
            return False
            
        # 计算bbox的中心点
        bbox_array = np.array(bbox)
        center_x = np.mean(bbox_array[:, 0])
        center_y = np.mean(bbox_array[:, 1])
        
        # 检查是否在任何屏蔽区域内
        for region in self.masked_regions:
            # 支持两种格式的屏蔽区域
            if isinstance(region, dict):  # 字典格式 {'x': x, 'y': y, 'width': w, 'height': h}
                x, y = region.get('x', 0), region.get('y', 0)
                width, height = region.get('width', 0), region.get('height', 0)
                
                if (x <= center_x <= x + width) and (y <= center_y <= y + height):
                    return True
            else:  # QRectF格式
                try:
                    if region.contains(center_x, center_y):
                        return True
                except AttributeError:
                    pass  # 不是QRectF对象，跳过
                    
        return False
    
    def _clean_text(self, text):
        """清理识别的文本"""
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 修正常见的OCR错误
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
