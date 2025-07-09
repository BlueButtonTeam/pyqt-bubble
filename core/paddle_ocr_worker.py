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


# 全局OCR模型缓存
class OCRModelCache:
    """OCR模型缓存，用于存储已加载的OCR处理器实例，避免重复加载"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCRModelCache, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not OCRModelCache._initialized:
            self.ocr_processor = None
            self.config_hash = None
            self.force_cpu = None
            self.cpu_threads = None
            self.use_count = 0
            OCRModelCache._initialized = True
            print("✅ 创建OCR模型缓存实例")
    
    def get_processor(self, config_dict, force_cpu=False, cpu_threads=8):
        """获取OCR处理器实例，如果配置相同则复用已加载的实例"""
        # 创建配置哈希值，用于比较配置是否相同
        config_hash = f"{config_dict['ocr_det_config']}|{config_dict['ocr_rec_config']}|{force_cpu}|{cpu_threads}"
        
        # 如果已有实例且配置相同，则复用
        if self.ocr_processor and self.config_hash == config_hash:
            self.use_count += 1
            print(f"🔄 复用已加载的OCR模型，当前使用次数: {self.use_count}")
            return self.ocr_processor
        
        # 配置不同或首次使用，创建新实例
        print("🔧 配置已变更或首次使用，创建新的OCR处理器")
        from infer_tu2 import OCR_process
        self.ocr_processor = OCR_process(config_dict)
        
        # 设置CPU相关配置
        if force_cpu:
            self.ocr_processor.enable_mkldnn = True
            self.ocr_processor.mkldnn_cache_capacity = 10
            self.ocr_processor.cpu_threads = cpu_threads
            self.ocr_processor._apply_config_to_models()
        
        # 更新配置哈希和使用计数
        self.config_hash = config_hash
        self.force_cpu = force_cpu
        self.cpu_threads = cpu_threads
        self.use_count = 1
        print("✅ 成功创建并缓存新的OCR模型")
        
        return self.ocr_processor

# 创建全局模型缓存实例
ocr_model_cache = OCRModelCache()


class PaddleOCRWorker(QRunnable):
    """PaddleOCR识别工作线程 - 使用您训练的专用模型"""
    
    def __init__(self, image_path: str, languages: list = ['ch_sim', 'en'], masked_regions: list = None, force_cpu: bool = False, cpu_threads: int = 8, reuse_model: bool = True, direct_recognition: bool = False):
        super().__init__()
        self.image_path = image_path
        self.languages = languages
        self.masked_regions = masked_regions or []
        self.signals = PaddleOCRWorkerSignals()
        self.force_cpu = force_cpu
        self.cpu_threads = cpu_threads
        self.reuse_model = reuse_model  # 保存复用模型标志
        self.direct_recognition = direct_recognition  # 是否直接识别（跳过检测阶段）
        
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

            # 使用全局模型缓存获取OCR处理器实例
            if self.reuse_model:
                self.ocr_processor = ocr_model_cache.get_processor(
                    self.config_dict, self.force_cpu, self.cpu_threads
                )
                print(f"✅ {'复用' if ocr_model_cache.use_count > 1 else '加载'} OCR模型，使用次数: {ocr_model_cache.use_count}")
            else:
                # 传统方式，不复用模型
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

            # 直接处理整张图像，无论大小
            print("📄 使用整图单进程模式处理")
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
            # 如果是直接识别模式，跳过检测阶段
            if hasattr(self, 'direct_recognition') and self.direct_recognition:
                print("📝 使用直接识别模式（跳过检测阶段）")
                return self._direct_recognition(img_list)
            
            # 传统的两阶段识别模式
            print("🔍 使用标准检测+识别模式")
            boxes = self.ocr_processor.ocr_det.predict(img_list)
            if not boxes:
                return []
            
            results = []
            i_boxes = boxes[0]

            if i_boxes is None or len(i_boxes) == 0:
                return []

            # 合并竖排文本的检测框
            i_boxes = self._merge_vertical_text_boxes(i_boxes)
            
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
                        results.append({
                            'text': text,
                            'confidence': confidence,
                            'bbox': valid_boxes[idx].tolist() if idx < len(valid_boxes) else []
                        })
            
            return results
            
        except Exception as e:
            print(f"❌ OCR处理失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _merge_vertical_text_boxes(self, boxes):
        """
        合并可能属于同一竖排文本的检测框
        算法：
        1. 计算所有框的中心点、宽度和高度
        2. 对于每一个框，检查是否有其他框在其正上方或正下方，且水平位置接近
        3. 如果找到相邻的框，则合并它们
        """
        try:
            if not boxes or len(boxes) <= 1:
                return boxes
                
            import numpy as np
            
            # 将框转换为numpy数组以便处理
            np_boxes = []
            for box in boxes:
                if len(box) == 0:
                    continue
                np_boxes.append(np.array(box))
            
            if len(np_boxes) <= 1:
                return boxes
            
            # 计算每个框的中心点、宽度和高度
            centers = []
            dimensions = []
            for box in np_boxes:
                x_min, y_min = np.min(box, axis=0)
                x_max, y_max = np.max(box, axis=0)
                
                center_x = (x_min + x_max) / 2
                center_y = (y_min + y_max) / 2
                width = x_max - x_min
                height = y_max - y_min
                
                centers.append((center_x, center_y))
                dimensions.append((width, height))
            
            # 找出可能的竖排文本框
            vertical_candidates = []
            for i, (center, dim) in enumerate(zip(centers, dimensions)):
                # 如果高度是宽度的1.5倍以上，可能是竖排文本的一部分
                if dim[1] > dim[0] * 1.5:
                    vertical_candidates.append(i)
            
            # 如果没有找到竖排文本候选框，直接返回原始框
            if not vertical_candidates:
                return boxes
                
            print(f"🔍 找到 {len(vertical_candidates)} 个可能的竖排文本框")
            
            # 对候选框按y坐标排序
            vertical_candidates.sort(key=lambda i: centers[i][1])
            
            # 合并相邻的竖排文本框
            merged = [False] * len(np_boxes)
            merged_boxes = []
            
            for i in range(len(vertical_candidates)):
                if merged[vertical_candidates[i]]:
                    continue
                    
                current_idx = vertical_candidates[i]
                current_center = centers[current_idx]
                current_box = np_boxes[current_idx]
                
                # 寻找垂直相邻且水平位置接近的框
                group = [current_idx]
                
                for j in range(i + 1, len(vertical_candidates)):
                    neighbor_idx = vertical_candidates[j]
                    if merged[neighbor_idx]:
                        continue
                        
                    neighbor_center = centers[neighbor_idx]
                    neighbor_dim = dimensions[neighbor_idx]
                    
                    # 检查是否在垂直方向上相邻
                    x_diff = abs(current_center[0] - neighbor_center[0])
                    max_width = max(dimensions[current_idx][0], neighbor_dim[0])
                    
                    # 如果水平位置接近（中心点x差异小于最大宽度的一半）
                    if x_diff < max_width * 0.5:
                        group.append(neighbor_idx)
                        merged[neighbor_idx] = True
                
                if len(group) > 1:
                    # 合并这组框
                    all_points = np.vstack([np_boxes[idx] for idx in group])
                    x_min, y_min = np.min(all_points, axis=0)
                    x_max, y_max = np.max(all_points, axis=0)
                    
                    # 创建新的合并框
                    merged_box = np.array([
                        [x_min, y_min],  # 左上
                        [x_max, y_min],  # 右上
                        [x_max, y_max],  # 右下
                        [x_min, y_max]   # 左下
                    ])
                    
                    merged_boxes.append(merged_box)
                    merged[current_idx] = True
                    print(f"✅ 合并了 {len(group)} 个竖排文本框")
                else:
                    # 如果没有找到需要合并的框，保留原始框
                    merged_boxes.append(current_box)
            
            # 添加所有未合并的非竖排文本框
            for i, box in enumerate(np_boxes):
                if not merged[i]:
                    merged_boxes.append(box)
            
            return merged_boxes
            
        except Exception as e:
            print(f"⚠️ 合并竖排文本框出错: {e}")
            import traceback
            traceback.print_exc()
            return boxes

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

    def _direct_recognition(self, img_list):
        """直接对输入图像进行识别，跳过检测阶段"""
        try:
            results = []
            img = img_list[0]
            h, w = img.shape[:2]
            
            # 为直接识别生成一个覆盖整个图像的包围框
            # 使用四边形来表示包围框，顺序为左上、右上、右下、左下
            bbox = [[0, 0], [w, 0], [w, h], [0, h]]
            
            # 使用识别模型直接识别
            info_stream = list(self.ocr_processor.ocr_rec.predict([img]))
            
            for idx, info in enumerate(info_stream):
                if info and '\t' in info:
                    ocr_str = info.split("\t")
                    text = ocr_str[0]
                    confidence = float(ocr_str[1]) if len(ocr_str) > 1 else 0.9
                    
                    if '#' not in text and text.strip():
                        # 竖排文本时，调整bbox为竖向中心位置
                        if hasattr(self, 'is_vertical_text') and self.is_vertical_text:
                            # 竖排文本的中心点位置计算
                            center_x = w / 2
                            center_y = h / 2
                            
                            # 使用更窄的框来模拟竖排文本
                            narrow_w = w / 3
                            results.append({
                                'text': text,
                                'confidence': confidence,
                                'bbox': [
                                    [center_x - narrow_w/2, 0],  # 左上
                                    [center_x + narrow_w/2, 0],  # 右上
                                    [center_x + narrow_w/2, h],  # 右下
                                    [center_x - narrow_w/2, h]   # 左下
                                ],
                                'center_x': center_x,
                                'center_y': center_y,
                                'is_vertical': True
                            })
                        else:
                            # 普通文本，使用完整bbox
                            results.append({
                                'text': text,
                                'confidence': confidence,
                                'bbox': bbox
                            })
            
            if len(results) == 0:
                print("⚠️ 直接识别未返回任何结果")
                
            return results
            
        except Exception as e:
            print(f"❌ 直接识别处理失败: {e}")
            import traceback
            traceback.print_exc()
            return []
            
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
        text = text.upper().replace(" ", "")
        
        if re.match(r'^M\d+(\.\d+)?(X\d+(\.\d+)?)?', text):
            return "螺纹规格"
        if re.match(r'^(Φ|∅|Ø)\d+', text):
            return "直径标注"
        if re.search(r'\d', text) and not re.search(r'[A-Z]{2,}', text):
            return "尺寸标注"
        if re.match(r'^[A-Z0-9\s-]+$', text) and len(re.sub(r'[^A-Z]', '', text)) > 1:
            return "材料标记"
        
        return 'annotation'
