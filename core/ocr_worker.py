#!/usr/bin/env python3
"""
OCR识别工作线程模块 - 增强版
针对机械图纸进行深度优化的OCR识别系统
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
    """OCR识别工作线程 - 增强版"""
    
    def __init__(self, image_path: str, languages: list = ['ch_sim', 'en'], masked_regions: list = None):
        super().__init__()
        self.image_path = image_path
        self.languages = languages
        self.masked_regions = masked_regions or []  # 屏蔽区域列表
        self.signals = OCRWorkerSignals()
        self._reader = None
        
    def run(self):
        """执行OCR识别 - 多策略增强版"""
        if not HAS_OCR_SUPPORT:
            self.signals.error.emit("OCR功能未启用，请安装完整依赖包")
            return
            
        try:
            # 初始化EasyOCR（优化版）
            if not self._reader:
                self.signals.progress.emit(5)
                print("🔧 正在初始化增强版EasyOCR...")
                
                # 配置EasyOCR参数以提高精度
                gpu_available = torch.cuda.is_available()
                print(f"🖥️  GPU可用: {gpu_available}")
                
                self._reader = easyocr.Reader(
                    self.languages, 
                    gpu=gpu_available,
                    verbose=False,          # 减少输出
                    quantize=True,          # 启用量化以提高性能
                    download_enabled=True   # 允许下载模型
                )
                print("✅ 增强版EasyOCR初始化完成")
            
            self.signals.progress.emit(15)
            
            # 读取并处理图像
            print(f"📖 正在处理文件: {self.image_path}")
            
            # 获取图像数据
            if self.image_path.lower().endswith('.pdf'):
                # PDF文件：先转换为图像
                image = self._extract_image_from_pdf_with_same_scale()
                if image is None:
                    raise Exception("无法从PDF提取图像")
                print(f"📄 PDF转换为图像成功，尺寸: {image.shape}")
            else:
                # 图像文件：直接读取
                image = cv2.imread(self.image_path)
                if image is None:
                    raise Exception(f"无法读取图像文件: {self.image_path}")
                print(f"🖼️ 图像读取成功，尺寸: {image.shape}")
            
            self.signals.progress.emit(25)
            
            print("🔍 开始OCR识别...")
            
            # 主识别策略：使用原始图像
            all_results = []
            try:
                print("  🎯 使用主识别策略...")
                results = self._reader.readtext(
                    image,
                    detail=1,
                    width_ths=0.7,      # 文本宽度阈值
                    height_ths=0.7,     # 文本高度阈值
                    paragraph=False,    # 不合并段落
                    min_size=8,         # 最小文本尺寸
                    text_threshold=0.6, # 文本置信度阈值
                    low_text=0.3,       # 低文本阈值
                    link_threshold=0.3, # 连接阈值
                    canvas_size=2560,   # 画布大小
                    mag_ratio=1.8       # 放大比例
                )
                
                print(f"  📝 主识别方法识别到 {len(results)} 个文本")
                
                # 为结果添加方法标识
                for result in results:
                    result_list = list(result)
                    result_list.append("primary_method")
                    all_results.append(result_list)
                    
            except Exception as e:
                print(f"  ⚠️ 主识别方法失败: {e}")
            
            self.signals.progress.emit(75)
            
            # 如果主方法结果太少，尝试备用方法
            if len(all_results) < 5:
                print("🔄 结果较少，尝试备用识别策略...")
                try:
                    # 简单的图像增强
                    processed_images = self._simple_preprocessing(image)
                    
                    for i, processed_img in enumerate(processed_images[:1]):  # 只使用第一种备用方法，避免内存问题
                        try:
                            backup_results = self._reader.readtext(
                                processed_img,
                                detail=1,
                                width_ths=0.7,
                                height_ths=0.7,
                                paragraph=False,
                                min_size=8,
                                text_threshold=0.5,  # 稍微降低阈值
                                low_text=0.3,
                                link_threshold=0.3,
                                canvas_size=1280,    # 减小画布大小避免内存问题
                                mag_ratio=1.5        # 减小放大比例
                            )
                            
                            for result in backup_results:
                                result_list = list(result)
                                result_list.append(f"backup_method_{i}")
                                all_results.append(result_list)
                            
                            print(f"  📝 备用方法{i+1}识别到 {len(backup_results)} 个文本")
                            break  # 成功后退出循环，避免过度处理
                            
                        except Exception as e:
                            print(f"  ⚠️ 备用方法{i+1}失败: {e}")
                            continue
                        
                except Exception as e:
                    print(f"  ⚠️ 备用识别策略失败: {e}")
            
            # 处理识别结果
            if all_results:
                print("🔧 正在处理识别结果...")
                processed_results = self._process_ocr_results(all_results, image.shape)
                
                self.signals.progress.emit(90)
                
                # 最终结果筛选和排序
                print("🎯 正在进行最终结果筛选...")
                final_results = self._final_result_filtering(processed_results)
                
                print(f"✅ OCR识别完成！最终识别到 {len(final_results)} 个有效文本")
            else:
                print("⚠️ 没有识别到任何文本")
                final_results = []
            
            self.signals.progress.emit(100)
            self.signals.finished.emit(final_results)
            
        except Exception as e:
            error_msg = f"OCR识别失败: {str(e)}"
            print(f"❌ {error_msg}")
            self.signals.error.emit(error_msg)
    
    def _extract_image_from_pdf_with_same_scale(self):
        """从PDF中提取图像 - 使用与显示相同的缩放比例"""
        try:
            # 重要：这个方法现在应该尽量与FileLoader.load_pdf保持一致的缩放
            doc = fitz.open(self.image_path)
            page = doc[0]  # 获取第一页
            
            # 使用标准4倍缩放（与默认PDF加载一致）
            mat = fitz.Matrix(4.0, 4.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_data = pix.tobytes("png")
            
            # 转换为OpenCV格式
            nparr = np.frombuffer(img_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            doc.close()
            return image
        except Exception as e:
            print(f"PDF图像提取失败: {e}")
            return None
    
    def _simple_preprocessing(self, image):
        """简单的图像预处理 - 内存优化版"""
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 只使用最有效的一种预处理方法，减少内存占用
        processed_images = []
        
        try:
            # 方法：基础CLAHE + 自适应阈值（经验证最有效且内存友好）
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # 使用轻量级的双边滤波
            denoised = cv2.bilateralFilter(enhanced, 5, 50, 50)  # 减小参数降低内存使用
            
            # 自适应阈值
            adaptive_thresh = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            processed_images.append(adaptive_thresh)
            
        except Exception as e:
            print(f"  ⚠️ 图像预处理失败: {e}")
            # 如果预处理失败，返回原始灰度图
            processed_images.append(gray)
        
        return processed_images
    
    def _process_ocr_results(self, results, image_shape):
        """处理OCR识别结果 - 智能合并和去重"""
        processed_results = []
        height, width = image_shape[:2]
        
        # 统计屏蔽过滤信息
        total_results = len(results)
        masked_count = 0
        
        # 第一轮：基础处理和筛选
        initial_results = []
        for result in results:
            # 解析结果格式 [bbox, text, confidence, method_id]
            if len(result) >= 3:
                bbox, text, confidence = result[0], result[1], result[2]
                method_id = result[3] if len(result) > 3 else "unknown"
            else:
                continue
            
            # 计算边界框信息
            bbox_array = np.array(bbox)
            center_x = int(np.mean(bbox_array[:, 0]))
            center_y = int(np.mean(bbox_array[:, 1]))
            bbox_width = int(np.max(bbox_array[:, 0]) - np.min(bbox_array[:, 0]))
            bbox_height = int(np.max(bbox_array[:, 1]) - np.min(bbox_array[:, 1]))
            
            # 屏蔽区域过滤 - 检查边界框是否在屏蔽区域内
            if self.masked_regions and self._is_bbox_in_masked_region(bbox):
                masked_count += 1
                continue  # 跳过屏蔽区域内的识别结果
            
            # 动态置信度阈值
            min_confidence = self._get_dynamic_confidence_threshold(text, bbox)
            if confidence < min_confidence:
                continue
                
            # 清理文本
            clean_text = self._clean_text(text)
            if not clean_text or len(clean_text.strip()) < 1:
                continue
            
            # 过滤太小的检测结果（可能是噪声）
            if bbox_width < 8 or bbox_height < 6:
                continue
            
            # 识别文本类型
            text_type = self._classify_mechanical_text(clean_text)
            
            initial_results.append({
                'text': clean_text,
                'confidence': confidence,
                'center_x': center_x,
                'center_y': center_y,
                'bbox_width': bbox_width,
                'bbox_height': bbox_height,
                'bbox': bbox,
                'text_type': text_type,
                'original_text': text,
                'method_id': method_id
            })
        
        # 打印屏蔽统计信息
        if self.masked_regions:
            print(f"🚫 屏蔽区域过滤: {masked_count}/{total_results} 个识别结果被屏蔽")
        
        # 第二轮：去重和合并
        processed_results = self._merge_duplicate_detections(initial_results)
        
        # 第三轮：上下文优化
        processed_results = self._apply_context_optimization(processed_results)
        
        return processed_results
    
    def _get_dynamic_confidence_threshold(self, text, bbox):
        """根据文本内容和框大小动态确定置信度阈值"""
        # 基础阈值
        base_threshold = 0.25
        
        # 根据文本长度调整
        text_length = len(text.strip())
        if text_length == 1:
            return 0.45  # 单字符需要更高置信度
        elif text_length == 2:
            return 0.35  # 双字符需要中等置信度
        elif text_length <= 4:
            return 0.3   # 短文本
        
        # 根据边界框大小调整
        bbox_array = np.array(bbox)
        bbox_area = (np.max(bbox_array[:, 0]) - np.min(bbox_array[:, 0])) * \
                   (np.max(bbox_array[:, 1]) - np.min(bbox_array[:, 1]))
        
        if bbox_area < 150:  # 小字体需要更高置信度
            return base_threshold + 0.1
        elif bbox_area > 1000:  # 大字体可以放宽要求
            return max(base_threshold - 0.05, 0.2)
        
        return base_threshold
    
    def _merge_duplicate_detections(self, results):
        """智能合并重复检测的文本 - 增强版去重"""
        if not results:
            return results
        
        print(f"🔄 开始去重处理，原始结果数量: {len(results)}")
        
        # 第一步：基于位置的粗略去重
        position_grouped = {}
        for result in results:
            # 使用网格化的位置作为键，减少微小偏移的影响
            grid_x = round(result['center_x'] / 20) * 20  # 20像素网格
            grid_y = round(result['center_y'] / 20) * 20  # 20像素网格
            grid_key = (grid_x, grid_y)
            
            if grid_key not in position_grouped:
                position_grouped[grid_key] = []
            position_grouped[grid_key].append(result)
        
        # 第二步：在每个网格内进行精细去重
        merged_results = []
        for grid_key, grid_results in position_grouped.items():
            if len(grid_results) == 1:
                # 网格内只有一个结果，直接添加
                merged_results.append(grid_results[0])
            else:
                # 网格内有多个结果，需要去重
                grid_merged = self._merge_grid_results(grid_results)
                merged_results.extend(grid_merged)
        
        print(f"✅ 去重完成，最终结果数量: {len(merged_results)}")
        return merged_results
    
    def _merge_grid_results(self, grid_results):
        """合并网格内的重复结果"""
        if len(grid_results) <= 1:
            return grid_results
        
        merged = []
        used_indices = set()
        
        for i, result1 in enumerate(grid_results):
            if i in used_indices:
                continue
            
            # 寻找与当前结果相似的其他结果
            similar_results = [result1]
            used_indices.add(i)
            
            for j, result2 in enumerate(grid_results[i+1:], i+1):
                if j in used_indices:
                    continue
                
                # 检查位置相似性（更严格的距离检查）
                distance = ((result1['center_x'] - result2['center_x']) ** 2 + 
                           (result1['center_y'] - result2['center_y']) ** 2) ** 0.5
                
                # 检查文本相似性
                text_similar = self._texts_similar(result1['text'], result2['text'])
                
                # 检查边界框重叠
                overlap_ratio = self._calculate_bbox_overlap(result1['bbox'], result2['bbox'])
                
                # 更严格的合并条件
                should_merge = False
                
                if distance < 15 and text_similar:
                    # 位置很近且文本相似
                    should_merge = True
                elif overlap_ratio > 0.5:
                    # 边界框大量重叠
                    should_merge = True
                elif distance < 25 and overlap_ratio > 0.3 and text_similar:
                    # 中等距离但有重叠且文本相似
                    should_merge = True
                
                if should_merge:
                    similar_results.append(result2)
                    used_indices.add(j)
            
            # 合并相似的结果
            if len(similar_results) == 1:
                merged.append(similar_results[0])
            else:
                merged_result = self._merge_similar_results(similar_results)
                merged.append(merged_result)
        
        return merged
    
    def _merge_similar_results(self, similar_results):
        """合并相似的结果"""
        # 选择置信度最高的作为基础
        best_result = max(similar_results, key=lambda x: x['confidence'])
        
        # 选择最长且有意义的文本
        best_text = best_result['text']
        for result in similar_results:
            if (len(result['text']) > len(best_text) and 
                result['confidence'] > 0.3 and
                result['confidence'] > best_result['confidence'] * 0.6):
                best_text = result['text']
        
        # 使用最高的置信度
        best_confidence = max(r['confidence'] for r in similar_results)
        
        # 使用平均位置（更稳定）
        avg_x = sum(r['center_x'] for r in similar_results) / len(similar_results)
        avg_y = sum(r['center_y'] for r in similar_results) / len(similar_results)
        
        # 创建合并后的结果
        merged = best_result.copy()
        merged['text'] = best_text
        merged['confidence'] = best_confidence
        merged['center_x'] = int(avg_x)
        merged['center_y'] = int(avg_y)
        
        return merged
    
    def _positions_close(self, result1, result2, threshold=50):
        """判断两个检测结果的位置是否相近"""
        distance = ((result1['center_x'] - result2['center_x']) ** 2 + 
                   (result1['center_y'] - result2['center_y']) ** 2) ** 0.5
        return distance < threshold
    
    def _calculate_bbox_overlap(self, bbox1, bbox2):
        """计算两个边界框的重叠比例"""
        bbox1_array = np.array(bbox1)
        bbox2_array = np.array(bbox2)
        
        x1_min, y1_min = np.min(bbox1_array, axis=0)
        x1_max, y1_max = np.max(bbox1_array, axis=0)
        
        x2_min, y2_min = np.min(bbox2_array, axis=0)
        x2_max, y2_max = np.max(bbox2_array, axis=0)
        
        # 计算交集
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        if inter_x_max <= inter_x_min or inter_y_max <= inter_y_min:
            return 0.0
        
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        
        # 计算并集
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = area1 + area2 - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def _texts_similar(self, text1, text2):
        """判断两个文本是否相似"""
        text1_clean = text1.strip().lower()
        text2_clean = text2.strip().lower()
        
        # 完全相同
        if text1_clean == text2_clean:
            return True
        
        # 一个是另一个的子串
        if text1_clean in text2_clean or text2_clean in text1_clean:
            return True
        
        # 编辑距离判断
        max_len = max(len(text1_clean), len(text2_clean))
        if max_len <= 3:
            return abs(len(text1_clean) - len(text2_clean)) <= 1
        
        distance = self._levenshtein_distance(text1_clean, text2_clean)
        similarity = 1 - distance / max_len
        
        return similarity > 0.75
    
    def _levenshtein_distance(self, s1, s2):
        """计算编辑距离"""
        if len(s1) > len(s2):
            s1, s2 = s2, s1
        
        distances = range(len(s1) + 1)
        for i2, c2 in enumerate(s2):
            distances_ = [i2 + 1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
            distances = distances_
        return distances[-1]
    
    def _apply_context_optimization(self, results):
        """应用上下文优化"""
        optimized_results = []
        
        for result in results:
            # 优化特定类型的文本
            if result['text_type'] == 'number':
                # 数字优化：移除非数字字符
                number_match = re.search(r'\d+\.?\d*', result['text'])
                if number_match:
                    result['text'] = number_match.group()
            
            elif result['text_type'] == 'thread_spec':
                # 螺纹规格优化
                result['text'] = self._optimize_thread_spec(result['text'])
            
            elif result['text_type'] == 'diameter':
                # 直径标注优化
                result['text'] = self._optimize_diameter_notation(result['text'])
            
            elif result['text_type'] == 'dimension':
                # 尺寸标注优化
                result['text'] = self._optimize_dimension_notation(result['text'])
            
            # 重新分类（可能因为优化而改变）
            result['text_type'] = self._classify_mechanical_text(result['text'])
            
            if result['text'].strip():  # 确保优化后仍有内容
                optimized_results.append(result)
        
        return optimized_results
    
    def _optimize_thread_spec(self, text):
        """优化螺纹规格识别"""
        # 常见的螺纹规格模式
        patterns = [
            r'M(\d+(?:\.\d+)?)',  # M8, M10, M12.5 等
            r'(\d+)M',            # 反向识别：8M -> M8
            r'M(\d+)[xX×](\d+(?:\.\d+)?)',  # M8×1.25
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if pattern.startswith('M'):
                    if len(match.groups()) == 2:
                        return f"M{match.group(1)}×{match.group(2)}"
                    else:
                        return f"M{match.group(1)}"
                else:
                    return f"M{match.group(1)}"
        
        return text
    
    def _optimize_diameter_notation(self, text):
        """优化直径标注识别"""
        # 提取数字部分
        numbers = re.findall(r'\d+\.?\d*', text)
        if numbers:
            return f"Φ{numbers[0]}"
        return text
    
    def _optimize_dimension_notation(self, text):
        """优化尺寸标注识别"""
        # 标准化乘号
        text = re.sub(r'[xX*]', '×', text)
        # 标准化正负号
        text = re.sub(r'[±+\-]', '±', text)
        return text
    
    def _final_result_filtering(self, results):
        """最终结果筛选和排序"""
        if not results:
            return results
        
        # 按置信度和文本类型重要性排序
        type_priority = {
            'thread_spec': 10,      # 螺纹规格最重要
            'diameter': 9,          # 直径标注
            'dimension': 8,         # 尺寸标注
            'tolerance': 7,         # 公差等级
            'surface_roughness': 6, # 表面粗糙度
            'angle': 5,             # 角度标注
            'material': 4,          # 材料标记
            'surface_treatment': 3, # 表面处理
            'geometry': 2,          # 几何特征
            'measurement': 1.5,     # 测量值
            'number': 1,            # 纯数值
            'position': 0.8,        # 位置标记
            'label': 0.6,           # 标签
            'annotation': 0.4       # 普通标注
        }
        
        # 计算综合得分
        for result in results:
            type_score = type_priority.get(result['text_type'], 0)
            confidence_score = result['confidence']
            
            # 文本长度奖励（适中长度的文本更可能是有效信息）
            text_len = len(result['text'])
            length_score = 1.0
            if 2 <= text_len <= 12:
                length_score = 1.3
            elif text_len == 1:
                length_score = 0.7
            elif text_len > 20:
                length_score = 0.8
            
            # 文本复杂度奖励（包含特殊符号的文本更重要）
            complexity_score = 1.0
            special_chars = ['Φ', '×', '°', '±', 'M', 'R']
            if any(char in result['text'] for char in special_chars):
                complexity_score = 1.2
            
            # 综合得分
            result['final_score'] = (type_score * 0.4 + confidence_score * 0.3 + 
                                   length_score * 0.2 + complexity_score * 0.1)
        
        # 按得分排序
        results.sort(key=lambda x: x['final_score'], reverse=True)
        
        # 过滤低分结果
        min_score = 0.4  # 降低阈值以保留更多可能有用的结果
        filtered_results = [r for r in results if r['final_score'] >= min_score]
        
        return filtered_results
    
    def _clean_text(self, text):
        """清理识别的文本 - 增强版"""
        # 移除多余空格和换行符
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 修正常见的OCR错误（针对机械图纸）
        corrections = {
            # 直径符号修正
            'Φ': 'Φ', '∅': 'Φ', 'ø': 'Φ', 'O': 'Φ', '0': 'Φ',
            '①': 'Φ', '◯': 'Φ', '○': 'Φ',
            
            # 螺纹标记修正
            'M': 'M', 'W': 'M', 'N': 'M', 'H': 'M',
            
            # 数字修正
            'I': '1', 'l': '1', '|': '1', 'S': '5', 'G': '6', 'B': '8', 'g': '9',
            'O': '0', 'o': '0', 'D': '0',
            
            # 符号修正
            '×': '×', 'x': '×', 'X': '×', '*': '×',
            '°': '°', 'o': '°', '˚': '°', '。': '°',
            
            # 小数点修正
            ',': '.', '·': '.', '｡': '.',
            
            # 连接符修正
            '-': '-', '—': '-', '–': '-', '_': '-',
        }
        
        # 应用修正
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        
        # 特殊处理：螺纹规格修正
        thread_patterns = [
            (r'(\d+)(\s*)[MmWwNnHh]', r'M\1'),  # 数字后跟字母
            (r'[MmWwNnHh](\s*)(\d+)', r'M\2'),  # 字母后跟数字
        ]
        
        for pattern, replacement in thread_patterns:
            text = re.sub(pattern, replacement, text)
        
        # 特殊处理：直径标注修正
        diameter_patterns = [
            (r'([ΦΦ∅ø○◯①OG0D])(\s*)(\d+\.?\d*)', r'Φ\3'),  # 符号后跟数字
            (r'(\d+\.?\d*)(\s*)([ΦΦ∅ø○◯①OG0D])', r'Φ\1'),  # 数字后跟符号
        ]
        
        for pattern, replacement in diameter_patterns:
            text = re.sub(pattern, replacement, text)
        
        # 清理多余的空格和标点
        text = re.sub(r'\s+', ' ', text.strip())
        text = re.sub(r'([a-zA-Z])(\d)', r'\1\2', text)  # 字母和数字之间不要空格
        text = re.sub(r'(\d)([a-zA-Z])', r'\1\2', text)  # 数字和字母之间不要空格
        
        return text
    
    def _classify_mechanical_text(self, text):
        """分类机械图纸文本类型 - 增强版"""
        clean_text = text.strip()
        
        # 1. 螺纹规格 (最高优先级)
        thread_patterns = [
            r'^M\d+(?:\.\d+)?(?:\s*[xX×]\s*\d+(?:\.\d+)?)?$',  # M8, M10, M12×1.5
            r'^M\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?$',          # M8-1.25
            r'^\d+M$',                                        # 8M格式
        ]
        for pattern in thread_patterns:
            if re.match(pattern, clean_text, re.IGNORECASE):
                return 'thread_spec'
        
        # 2. 直径标注
        diameter_patterns = [
            r'^Φ\d+(?:\.\d+)?$',           # Φ8, Φ10.5
            r'^∅\d+(?:\.\d+)?$',           # ∅8
            r'^ø\d+(?:\.\d+)?$',           # ø8
            r'^\d+(?:\.\d+)?Φ$',           # 8Φ格式
        ]
        for pattern in diameter_patterns:
            if re.match(pattern, clean_text):
                return 'diameter'
        
        # 3. 复合尺寸标注
        dimension_patterns = [
            r'^\d+(?:\.\d+)?\s*[×xX]\s*\d+(?:\.\d+)?$',                    # 20×30
            r'^\d+(?:\.\d+)?\s*[×xX]\s*\d+(?:\.\d+)?\s*[×xX]\s*\d+(?:\.\d+)?$',  # 20×30×40
            r'^\d+(?:\.\d+)?[-]\d+(?:\.\d+)?$',                              # 20-30
            r'^\d+(?:\.\d+)?\+\d+(?:\.\d+)?$',                             # 20+0.5
            r'^\d+(?:\.\d+)?±\d+(?:\.\d+)?$',                              # 20±0.1
        ]
        for pattern in dimension_patterns:
            if re.match(pattern, clean_text):
                return 'dimension'
        
        # 4. 角度标注
        angle_patterns = [
            r'^\d+(?:\.\d+)?°$',           # 30°, 45.5°
            r'^\d+(?:\.\d+)?\s*度$',       # 30度
            r'^\d+(?:\.\d+)?′$',           # 30′ (分)
            r'^\d+(?:\.\d+)?″$',           # 30″ (秒)
        ]
        for pattern in angle_patterns:
            if re.match(pattern, clean_text):
                return 'angle'
        
        # 5. 表面粗糙度
        roughness_patterns = [
            r'^Ra\d+(?:\.\d+)?$',          # Ra3.2
            r'^Rz\d+(?:\.\d+)?$',          # Rz12.5
            r'^R[aznqtpv]\d+(?:\.\d+)?$',  # 各种表面粗糙度
        ]
        for pattern in roughness_patterns:
            if re.match(pattern, clean_text, re.IGNORECASE):
                return 'surface_roughness'
        
        # 6. 公差等级
        tolerance_patterns = [
            r'^[ABCDEFGH]\d+$',            # A1, B2, H7等
            r'^[a-h]\d+$',                 # a1, b2, h7等
            r'^IT\d+$',                    # IT7, IT8等
        ]
        for pattern in tolerance_patterns:
            if re.match(pattern, clean_text):
                return 'tolerance'
        
        # 7. 纯数值
        number_patterns = [
            r'^\d+(?:\.\d+)?$',            # 20, 30.5
            r'^\d+(?:\.\d+)?mm$',          # 20mm, 30.5mm
        ]
        for pattern in number_patterns:
            if re.match(pattern, clean_text):
                return 'number'
        
        # 8. 材料标记
        material_keywords = [
            # 中文材料
            '钢', '铁', '铜', '铝', '不锈钢', '碳钢', '合金钢', '铸铁', '铸钢',
            '黄铜', '青铜', '紫铜', '锌合金', '镁合金', '钛合金',
            # 英文材料
            'steel', 'iron', 'copper', 'aluminum', 'aluminium', 'brass', 'bronze',
            'stainless', 'carbon', 'alloy', 'cast', 'zinc', 'magnesium', 'titanium',
            # 材料牌号
            'Q235', 'Q345', '45#', '20#', '16Mn', '304', '316', '201',
        ]
        for material in material_keywords:
            if material.lower() in clean_text.lower():
                return 'material'
        
        # 9. 表面处理
        surface_keywords = [
            # 中文表面处理
            '镀锌', '发黑', '阳极氧化', '喷涂', '电镀', '热处理', '淬火', '回火',
            '渗碳', '氮化', '磷化', '钝化', '抛光', '喷砂', '电泳', '粉末喷涂',
            # 英文表面处理
            'zinc', 'black', 'anodize', 'coating', 'plating', 'treatment',
            'hardening', 'tempering', 'carburizing', 'nitriding', 'phosphating',
            'passivation', 'polishing', 'sandblasting', 'powder', 'painting',
        ]
        for surface in surface_keywords:
            if surface.lower() in clean_text.lower():
                return 'surface_treatment'
        
        # 10. 几何特征
        geometry_keywords = [
            # 中文几何特征
            '孔', '槽', '台', '面', '边', '角', '圆', '方', '六角', '内六角',
            '外六角', '花键', '键槽', '螺纹', '锥度', '倒角', '圆角', '沉头',
            # 英文几何特征
            'hole', 'slot', 'face', 'edge', 'corner', 'round', 'square', 'hex',
            'hexagon', 'spline', 'keyway', 'thread', 'taper', 'chamfer', 'fillet',
        ]
        for geometry in geometry_keywords:
            if geometry.lower() in clean_text.lower():
                return 'geometry'
        
        # 11. 位置标记
        position_keywords = [
            '左', '右', '上', '下', '前', '后', '内', '外', '中心', '中央',
            'left', 'right', 'top', 'bottom', 'front', 'rear', 'inner', 'outer', 'center',
            'A', 'B', 'C', 'D', 'E', 'F',  # 常见的位置标记
        ]
        if len(clean_text) <= 3 and any(pos in clean_text for pos in position_keywords):
            return 'position'
        
        # 12. 标题和说明
        title_keywords = [
            '图', '视图', '剖面', '断面', '详图', '局部', '放大', '比例',
            'view', 'section', 'detail', 'scale', 'fig', 'figure',
            '标题', '说明', '备注', '注意', '要求',
            'title', 'note', 'remark', 'attention', 'requirement',
        ]
        for title in title_keywords:
            if title.lower() in clean_text.lower():
                return 'title'
        
        # 13. 检查是否为单个字符（可能是标记）
        if len(clean_text) == 1:
            if clean_text.isalpha():
                return 'label'
            elif clean_text.isdigit():
                return 'number'
            else:
                return 'symbol'
        
        # 14. 检查是否包含单位
        unit_patterns = [
            r'\d+(?:\.\d+)?\s*mm',  # 数字+mm
            r'\d+(?:\.\d+)?\s*cm',  # 数字+cm
            r'\d+(?:\.\d+)?\s*m',   # 数字+m
            r'\d+(?:\.\d+)?\s*°',   # 数字+度
        ]
        for pattern in unit_patterns:
            if re.search(pattern, clean_text, re.IGNORECASE):
                return 'measurement'
        
        # 默认分类
        return 'annotation'
    
    def _is_bbox_in_masked_region(self, bbox) -> bool:
        """检查边界框是否在屏蔽区域内"""
        if not self.masked_regions:
            return False
        
        # 计算边界框的矩形
        bbox_array = np.array(bbox)
        x_min, y_min = np.min(bbox_array, axis=0)
        x_max, y_max = np.max(bbox_array, axis=0)
        
        # 检查中心点是否在屏蔽区域内
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        
        # 处理字典格式的屏蔽区域数据
        for region in self.masked_regions:
            if isinstance(region, dict):
                # 字典格式: {'x': x, 'y': y, 'width': w, 'height': h}
                rx = region.get('x', 0)
                ry = region.get('y', 0)
                rw = region.get('width', 0)
                rh = region.get('height', 0)
                
                if rx <= center_x <= rx + rw and ry <= center_y <= ry + rh:
                    return True
            elif hasattr(region, 'contains'):
                # QRectF对象
                if region.contains(center_x, center_y):
                    return True
            elif hasattr(region, '__getitem__') and len(region) >= 4:
                # 坐标数组 [x, y, width, height]
                rx, ry, rw, rh = region[0], region[1], region[2], region[3]
                if rx <= center_x <= rx + rw and ry <= center_y <= ry + rh:
                    return True
        
        return False 