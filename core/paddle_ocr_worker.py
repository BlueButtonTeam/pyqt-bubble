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
import time
from datetime import datetime
from PySide6.QtCore import QObject, QRunnable, Signal
from typing import List, Dict, Tuple, Optional, Any

# 配置日志记录器
logger = logging.getLogger('OCR_Performance')
logger.setLevel(logging.INFO)
# 创建一个文件处理器
ocr_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ocr_performance.log')
file_handler = logging.FileHandler(ocr_log_path, encoding='utf-8')
file_handler.setLevel(logging.INFO)
# 创建一个简洁的格式化器 - 只记录时间、文件名、大小和OCR时间
formatter = logging.Formatter('%(asctime)s - %(message)s')
file_handler.setFormatter(formatter)
# 将处理器添加到日志记录器
logger.addHandler(file_handler)

# 添加PaddleOCR路径 - 使用本地文件
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 设置与infer_tu2.py相同的GPU环境变量
os.environ["FLAGS_allocator_strategy"] = 'auto_growth'
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# 导入PaddleOCR相关模块
try:
    import paddle
    PADDLE_AVAILABLE = True
    
    # 检测GPU支持
    HAS_GPU_SUPPORT = False
    try:
        if paddle.is_compiled_with_cuda():
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
    finished = Signal(list)
    progress = Signal(int)
    error = Signal(str)


class PaddleOCRWorker(QRunnable):
    """PaddleOCR识别工作线程 - 使用您训练的专用模型"""
    
    def __init__(self, image_path: str, languages: list = ['ch_sim', 'en'], masked_regions: list = None, force_cpu: bool = False, cpu_threads: int = 8, direct_recognition: bool = False):
        super().__init__()
        self.image_path = image_path
        self.languages = languages
        self.masked_regions = masked_regions or []
        self.signals = PaddleOCRWorkerSignals()
        self.force_cpu = force_cpu
        self.cpu_threads = cpu_threads
        self.direct_recognition = direct_recognition
        self.is_vertical_text = False  # 添加竖排文本标志
        
        self.config_dict = {
            "ocr_det_config": os.path.join(parent_dir, "model", "det_best_model", "config.yml"),
            "ocr_rec_config": os.path.join(parent_dir, "configs", "rec", "PP-OCRv4", "ch_PP-OCRv4_rec_hgnet.yml")
        }
        
        self.ocr_processor = None
    
    def run(self):
        """执行PaddleOCR识别"""
        if not PADDLE_AVAILABLE:
            self.signals.error.emit("PaddleOCR功能未启用，请安装PaddlePaddle")
            return

        try:
            start_time = time.time()
            start_datetime = datetime.now()
            print(f"\n📋 OCR任务开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📄 处理文件: {os.path.basename(self.image_path)}")
            # 仅记录处理文件路径
            # logger.info(f"OCR任务开始 - 文件: {self.image_path}")

            os.environ["OMP_NUM_THREADS"] = str(self.cpu_threads)
            os.environ["KMP_AFFINITY"] = "granularity=fine,compact,1,0"

            use_gpu = HAS_GPU_SUPPORT and not self.force_cpu
            if use_gpu:
                print("🚀 使用GPU进行PaddleOCR识别")
                # logger.info("使用GPU进行OCR识别")
            else:
                print(f"🚀 使用CPU进行PaddleOCR识别 ({self.cpu_threads}线程)" + (" (强制CPU模式)" if self.force_cpu else " (未检测到GPU)"))
                # logger.info(f"使用CPU进行OCR识别 ({self.cpu_threads}线程)" + (" (强制CPU模式)" if self.force_cpu else " (未检测到GPU)"))

            self.signals.progress.emit(10)
            print("🔧 正在初始化PaddleOCR模型...")
            init_start = time.time()

            from infer_tu2 import OCR_process
            self.ocr_processor = OCR_process(self.config_dict)
            
            if not use_gpu:
                self.ocr_processor.enable_mkldnn = True
                self.ocr_processor.mkldnn_cache_capacity = 10
                self.ocr_processor.cpu_threads = self.cpu_threads
                self.ocr_processor._apply_config_to_models()
                print(f"✅ 已启用MKLDNN加速，线程数: {self.cpu_threads}")
            
            init_time = time.time() - init_start
            print(f"✅ 模型初始化完成，耗时: {init_time:.2f}秒")
            # logger.info(f"模型初始化耗时: {init_time:.2f}秒")
            self.signals.progress.emit(30)
            
            print(f"📖 正在处理文件: {self.image_path}")
            image_start = time.time()
            
            image = cv2.imread(self.image_path)
            if image is None:
                raise Exception(f"无法读取图像文件: {self.image_path}")
            
            image_time = time.time() - image_start
            img_height, img_width = image.shape[:2]
            img_size_mb = (image.nbytes / (1024 * 1024))
            
            print(f"🖼️ 图像读取成功，尺寸: {image.shape}，耗时: {image_time:.2f}秒")
            # logger.info(f"图像尺寸: {img_width}x{img_height}，大小: {img_size_mb:.2f}MB，读取耗时: {image_time:.2f}秒")
            self.signals.progress.emit(50)
            
            print("🔍 开始OCR识别...")
            ocr_start = time.time()

            # 根据是否使用直接识别模式选择处理方法
            if self.direct_recognition:
                print("📄 使用直接识别模式处理（跳过检测模型）")
                img_list = [image]
                ocr_results = self._process_with_direct_recognition(img_list)
            else:
                # 直接处理整张图像，无论大小
                print("📄 使用完整OCR流程处理（检测+识别）")
                img_list = [image]
                ocr_results = self._process_with_your_ocr(img_list)

            ocr_time = time.time() - ocr_start
            print(f"✅ 识别完成，共识别 {len(ocr_results)} 个文本，OCR处理耗时: {ocr_time:.2f}秒")
            # logger.info(f"OCR处理完成，识别到 {len(ocr_results)} 个文本，处理耗时: {ocr_time:.2f}秒")
            self.signals.progress.emit(90)
            
            post_start = time.time()
            final_results = self._format_results_for_pyqt(ocr_results, image.shape)
            post_time = time.time() - post_start
            print(f"✅ 后处理完成，耗时: {post_time:.2f}秒")
            
            total_time = time.time() - start_time
            end_datetime = datetime.now()
            
            print("\n⏱️ 时间统计:")
            print(f"  模型初始化: {init_time:.2f}秒 ({(init_time/total_time*100):.1f}%)")
            print(f"  图像读取: {image_time:.2f}秒 ({(image_time/total_time*100):.1f}%)")
            print(f"  OCR处理: {ocr_time:.2f}秒 ({(ocr_time/total_time*100):.1f}%)")
            print(f"  后处理: {post_time:.2f}秒 ({(post_time/total_time*100):.1f}%)")
            print(f"  总耗时: {total_time:.2f}秒")
            print(f"📋 OCR任务结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 只记录图像大小和OCR识别时间
            logger.info(f"文件: {os.path.basename(self.image_path)}, 尺寸: {img_width}x{img_height}, 大小: {img_size_mb:.2f}MB, OCR识别时间: {ocr_time:.2f}秒")
            
            self.signals.progress.emit(100)
            self.signals.finished.emit(final_results)
            
        except Exception as e:
            error_msg = f"PaddleOCR识别失败: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(f"文件: {os.path.basename(self.image_path)}, OCR识别失败: {str(e)}")
            import traceback
            traceback.print_exc()
            self.signals.error.emit(error_msg)
            
    def _process_with_your_ocr(self, img_list):
        """使用您的OCR处理器进行识别 (稳定基准版)"""
        try:
            boxes = self.ocr_processor.ocr_det.predict(img_list)
            if not boxes:
                return []
            
            results = []
            i_boxes = boxes[0]

            if i_boxes is None or len(i_boxes) == 0:
                return []

            crop_img_list = []
            sortboxes = self.ocr_processor.sort_boxes(i_boxes)
            
            img_h, img_w = img_list[0].shape[:2]
            max_box_area = img_h * img_w * 0.3
            
            valid_boxes = []
            
            for box in sortboxes:
                try:
                    box_array = np.array(box)
                    x_min, y_min = np.min(box_array, axis=0)
                    x_max, y_max = np.max(box_array, axis=0)
                    box_area = (x_max - x_min) * (y_max - y_min)

                    if box_area > max_box_area:
                        print(f"⚠️ 过滤掉一个异常大的检测框，面积: {box_area:.0f} > 阈值: {max_box_area:.0f}")
                        continue
                except Exception:
                    continue

                bbox_info = self.ocr_processor.get_bbox_info(box)
                
                # 处理竖排文本 - 如果设置了竖排文本标志
                if self.is_vertical_text:
                    # 旋转图像以处理竖排文本
                    crop_img = self.ocr_processor.rectify_crop(img_list[0], bbox_info)
                    # 旋转90度
                    crop_img = cv2.rotate(crop_img, cv2.ROTATE_90_CLOCKWISE)
                else:
                    crop_img = self.ocr_processor.rectify_crop(img_list[0], bbox_info)
                
                crop_img_list.append(crop_img)
                valid_boxes.append(box)
            
            if not crop_img_list:
                return []
            
            info_stream = list(self.ocr_processor.ocr_rec.predict(crop_img_list))
            
            for idx, info in enumerate(info_stream):
                if info and '\t' in info:
                    ocr_str = info.split("\t")
                    text = ocr_str[0]
                    confidence = float(ocr_str[1]) if len(ocr_str) > 1 else 0.9
                    
                    if '#' not in text and text.strip():
                        # 对文本进行分类
                        clean_text = text.strip()
                        text_type = self._classify_mechanical_text(clean_text)
                        
                        result = {
                            'text': text,
                            'confidence': confidence,
                            'bbox': valid_boxes[idx].tolist() if idx < len(valid_boxes) else [],
                            'type': text_type  # 添加文本类型
                        }
                        
                        # 标记是否为竖排文本
                        if self.is_vertical_text:
                            result['is_vertical'] = True
                            
                        results.append(result)
            
            return results
            
        except Exception as e:
            print(f"❌ OCR处理失败: {e}")
            import traceback
            traceback.print_exc()
            return []
            
    def _process_with_direct_recognition(self, img_list):
        """直接使用识别模型进行识别（跳过检测模型）"""
        try:
            # 直接使用识别模型，跳过检测模型
            print("✅ 使用直接识别模式，跳过检测模型")
            
            # 处理竖排文本 - 如果设置了竖排文本标志
            if self.is_vertical_text:
                # 旋转图像以处理竖排文本
                img_list[0] = cv2.rotate(img_list[0], cv2.ROTATE_90_CLOCKWISE)
                print("✅ 已旋转图像以适应竖排文本")
            
            # 直接将整个图像作为一个文本区域进行识别
            crop_img_list = [img_list[0]]
            
            # 调用识别模型
            info_stream = list(self.ocr_processor.ocr_rec.predict(crop_img_list))
            
            results = []
            
            # 处理识别结果
            for idx, info in enumerate(info_stream):
                if info and '\t' in info:
                    ocr_str = info.split("\t")
                    text = ocr_str[0]
                    confidence = float(ocr_str[1]) if len(ocr_str) > 1 else 0.9
                    
                    if '#' not in text and text.strip():
                        # 创建一个虚拟的边界框，覆盖整个图像
                        img_h, img_w = img_list[0].shape[:2]
                        virtual_bbox = [[0, 0], [img_w, 0], [img_w, img_h], [0, img_h]]
                        
                        # 对文本进行分类
                        clean_text = text.strip()
                        text_type = self._classify_mechanical_text(clean_text)
                        
                        result = {
                            'text': text,
                            'confidence': confidence,
                            'bbox': virtual_bbox,
                            'type': text_type  # 添加文本类型
                        }
                        
                        # 标记是否为竖排文本
                        if self.is_vertical_text:
                            result['is_vertical'] = True
                            
                        results.append(result)
            
            return results
            
        except Exception as e:
            print(f"❌ 直接识别模式失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _format_results_for_pyqt(self, ocr_results: List[Dict], image_shape: Tuple[int, int, int]) -> List[Dict]:
        """将OCR结果格式化为PyQt应用程序所需的格式"""
        formatted_results = []
        total_results = len(ocr_results)
        masked_count = 0
        
        for result in ocr_results:
            bbox = result.get('bbox')
            text = result.get('text', '')
            
            if not bbox or len(bbox) < 4:
                continue

            bbox_array = np.array(bbox)
            center_x = int(np.mean(bbox_array[:, 0]))
            center_y = int(np.mean(bbox_array[:, 1]))
            bbox_width = int(np.max(bbox_array[:, 0]) - np.min(bbox_array[:, 0]))
            bbox_height = int(np.max(bbox_array[:, 1]) - np.min(bbox_array[:, 1]))
            
            if self.masked_regions and self._is_bbox_in_masked_region(bbox):
                masked_count += 1
                continue
                
            clean_text = self._clean_text(text)
            if not clean_text:
                continue
            
            text_type = self._classify_mechanical_text(clean_text)
            
            formatted_results.append({
                'text': clean_text,
                'confidence': result.get('confidence', 0.0),
                'center_x': center_x,
                'center_y': center_y,
                'bbox_width': bbox_width,
                'bbox_height': bbox_height,
                'bbox': bbox,
                'type': text_type,
                'original_text': text
            })
        
        if masked_count > 0:
            print(f"🚫 已根据屏蔽区域过滤掉 {masked_count}/{total_results} 个结果。")
            
        return formatted_results

    def _is_bbox_in_masked_region(self, bbox: List[Tuple[int, int]]) -> bool:
        """检查给定的边界框是否完全位于任何一个屏蔽区域内"""
        bbox_center = np.mean(np.array(bbox), axis=0)
        
        for region in self.masked_regions:
            if (region['x'] <= bbox_center[0] <= region['x'] + region['width'] and
                region['y'] <= bbox_center[1] <= region['y'] + region['height']):
                return True
        return False

    def _clean_text(self, text: str) -> str:
        """清理OCR识别出的原始文本"""
        return text.strip()
    
    def _classify_mechanical_text(self, text: str) -> str:
        """根据文本内容对机械图纸中的文本进行分类"""
        # 保存原始文本，便于调试
        original_text = text
        
        # 标准化处理
        text = text.upper().replace(" ", "")
        
        # 调试输出
        print(f"🔍 分类文本: '{original_text}' -> '{text}'")
        
        # 螺纹规格匹配 - 例如 M10, M8x1.25
        if re.match(r'^M\d+(\.\d+)?(X\d+(\.\d+)?)?', text):
            print(f"✅ 识别为螺纹规格: {text}")
            return "thread_spec"  # 使用英文类型名
            
        # 直径标注匹配 - 例如 Φ10, ∅20
        if re.match(r'^(Φ|∅|Ø)\d+', text):
            print(f"✅ 识别为直径标注: {text}")
            return "diameter"  # 使用英文类型名
            
        # 角度标注匹配 - 例如 30°, 45.5°
        if '°' in original_text or '度' in original_text or re.match(r'^\d+(\.\d+)?°?$', original_text) and int(float(re.match(r'^\d+(\.\d+)?°?$', original_text).group().replace('°', ''))) in [15, 30, 45, 60, 75, 90]:
            print(f"✅ 识别为角度标注: {text}")
            return "angle"  # 使用英文类型名
        
        # 尺寸标注匹配 (更宽松的规则)
        # 1. 包含数字
        # 2. 可能包含小数点、加减符号、公差等
        # 3. 可能是纯数字 如 "54" "0.01" "±0.1" "45±1"
        if re.search(r'\d', text):
            # 排除明显的材料标记 (通常是大写字母+数字的组合)
            if not (re.match(r'^[A-Z][A-Z0-9]{2,}$', text) or re.match(r'^[A-Z]-\d+$', text)):
                print(f"✅ 识别为尺寸标注: {text}")
                return "dimension"  # 使用英文类型名
        
        # 材料标记匹配 - 例如 Q235, 45#, GCr15
        if re.match(r'^[A-Z0-9\s\-#]+$', text) and len(re.sub(r'[^A-Z]', '', text)) > 0:
            print(f"✅ 识别为材料标记: {text}")
            return "material"  # 使用英文类型名
        
        # 默认为普通标注
        print(f"⚠️ 未能明确分类，设为普通标注: {text}")
        return 'annotation'
