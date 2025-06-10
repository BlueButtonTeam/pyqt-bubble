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
import os
import random
import threading
import time
from typing import Optional, List, Tuple, Dict
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QGraphicsView, QGraphicsScene, QGraphicsObject, QGraphicsPixmapItem,
    QGraphicsPathItem, QListWidget, QListWidgetItem, QTextEdit, QLabel,
    QFormLayout, QMenuBar, QToolBar, QFileDialog, QMessageBox, QPushButton,
    QSpinBox, QComboBox, QProgressBar, QCheckBox, QGroupBox, QSlider
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QThread, QRunnable, QThreadPool, QObject
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath, QPixmap, QAction,
    QFont, QPalette
)

# 导入图像处理库
HAS_OCR_SUPPORT = True
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
        import re
        
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
        import re
        
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


class BubbleAnnotationItem(QGraphicsObject):
    """
    气泡标注图形项，包含引线和圆圈编号
    """
    selected = Signal(object)  # 被选中时发射信号
    moved = Signal(object, QPointF)  # 被移动时发射信号
    delete_requested = Signal(object)  # 删除请求信号
    style_change_requested = Signal(object)  # 样式改变请求信号
    
    def __init__(self, annotation_id: int, position: QPointF, text: str = "", style: str = "default"):
        super().__init__()
        self.annotation_id = annotation_id
        self.text = text or f"标注 {annotation_id}"
        self.circle_radius = 15
        self.leader_length = 30
        self.style = style  # 标注样式
        
        # 设置标志
        self.setFlags(
            QGraphicsObject.ItemIsSelectable |
            QGraphicsObject.ItemIsMovable |
            QGraphicsObject.ItemSendsGeometryChanges
        )
        
        # 设置位置
        self.setPos(position)
        
        # 选中状态
        self._is_highlighted = False
        
        # 设置接受右键菜单
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        
    def get_style_colors(self):
        """根据样式获取颜色"""
        styles = {
            "default": {
                "normal_pen": QColor(0, 0, 255),
                "normal_brush": QColor(255, 255, 255, 200),
                "selected_pen": QColor(255, 0, 0),
                "selected_brush": QColor(255, 255, 0, 100)
            },
            "warning": {
                "normal_pen": QColor(255, 165, 0),
                "normal_brush": QColor(255, 248, 220, 200),
                "selected_pen": QColor(255, 69, 0),
                "selected_brush": QColor(255, 218, 185, 150)
            },
            "error": {
                "normal_pen": QColor(220, 20, 60),
                "normal_brush": QColor(255, 192, 203, 200),
                "selected_pen": QColor(178, 34, 34),
                "selected_brush": QColor(255, 160, 122, 150)
            },
            "success": {
                "normal_pen": QColor(34, 139, 34),
                "normal_brush": QColor(240, 255, 240, 200),
                "selected_pen": QColor(0, 128, 0),
                "selected_brush": QColor(144, 238, 144, 150)
            }
        }
        return styles.get(self.style, styles["default"])
        
    def boundingRect(self) -> QRectF:
        """返回边界矩形"""
        padding = 5
        total_width = self.leader_length + self.circle_radius * 2 + padding * 2
        total_height = self.circle_radius * 2 + padding * 2
        return QRectF(-padding, -self.circle_radius - padding, 
                     total_width, total_height)
    
    def paint(self, painter: QPainter, option, widget=None):
        """绘制气泡标注"""
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # 获取样式颜色
        colors = self.get_style_colors()
        
        # 设置画笔和画刷
        if self.isSelected() or self._is_highlighted:
            pen = QPen(colors["selected_pen"], 2)
            brush = QBrush(colors["selected_brush"])
        else:
            pen = QPen(colors["normal_pen"], 1)
            brush = QBrush(colors["normal_brush"])
            
        painter.setPen(pen)
        painter.setBrush(brush)
        
        # 绘制引线
        leader_start = QPointF(0, 0)
        leader_end = QPointF(self.leader_length, 0)
        painter.drawLine(leader_start, leader_end)
        
        # 绘制圆圈
        circle_center = QPointF(self.leader_length + self.circle_radius, 0)
        painter.drawEllipse(circle_center, self.circle_radius, self.circle_radius)
        
        # 绘制编号文字
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont("Arial", 10, QFont.Bold)
        painter.setFont(font)
        text_rect = QRectF(circle_center.x() - self.circle_radius,
                          circle_center.y() - self.circle_radius,
                          self.circle_radius * 2,
                          self.circle_radius * 2)
        painter.drawText(text_rect, Qt.AlignCenter, str(self.annotation_id))
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            super().mousePressEvent(event)
            self.selected.emit(self)
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.screenPos())
            event.accept()
    
    def show_context_menu(self, global_pos):
        """显示右键菜单"""
        from PySide6.QtWidgets import QMenu
        
        menu = QMenu()
        
        # 删除动作
        delete_action = menu.addAction("删除标注")
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self))
        
        menu.addSeparator()
        
        # 样式子菜单
        style_menu = menu.addMenu("更改样式")
        
        styles = [
            ("默认", "default"),
            ("警告", "warning"), 
            ("错误", "error"),
            ("成功", "success")
        ]
        
        for style_name, style_key in styles:
            style_action = style_menu.addAction(style_name)
            if style_key != self.style:  # 当前样式不可选
                style_action.triggered.connect(
                    lambda checked, s=style_key: self.change_style(s)
                )
            else:
                style_action.setEnabled(False)
        
        menu.exec(global_pos.toPoint())
    
    def change_style(self, new_style: str):
        """改变标注样式"""
        self.style = new_style
        self.update()  # 重绘
        self.style_change_requested.emit(self)
    
    def itemChange(self, change, value):
        """项目变化时的回调"""
        if change == QGraphicsObject.ItemPositionChange:
            self.moved.emit(self, value)
        return super().itemChange(change, value)
    
    def set_highlighted(self, highlighted: bool):
        """设置高亮状态"""
        self._is_highlighted = highlighted
        self.update()
    
    def get_data(self) -> dict:
        """获取标注数据"""
        return {
            'id': self.annotation_id,
            'text': self.text,
            'position': self.pos(),
            'style': self.style
        }
    
    def set_text(self, text: str):
        """设置标注文本"""
        self.text = text


class GraphicsView(QGraphicsView):
    """
    自定义图形视图，支持缩放和平移
    """
    # 添加信号
    area_selected = Signal(QRectF)  # 区域选择信号
    
    def __init__(self):
        super().__init__()
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # 添加拖拽状态跟踪
        self._is_dragging = False
        self._drag_start_pos = None
        
        # 添加选择模式
        self._selection_mode = False  # 是否处于区域选择模式
        self._selection_start = None
        self._selection_rect = None
        
    def set_selection_mode(self, enabled: bool):
        """设置区域选择模式"""
        self._selection_mode = enabled
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
            
    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        scale_factor = 1.15
        if event.angleDelta().y() < 0:
            scale_factor = 1.0 / scale_factor
        
        self.scale(scale_factor, scale_factor)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if self._selection_mode and event.button() == Qt.LeftButton:
            # 区域选择模式
            self._selection_start = self.mapToScene(event.position().toPoint())
            self._selection_rect = QRectF(self._selection_start, self._selection_start)
            event.accept()
            return
        elif event.button() == Qt.MiddleButton:
            # 中键拖拽（原有功能）
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif event.button() == Qt.RightButton:
            # 右键拖拽（新增功能）
            self._is_dragging = True
            self._drag_start_pos = event.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._selection_mode and event.buttons() & Qt.LeftButton and self._selection_start:
            # 更新选择矩形
            current_pos = self.mapToScene(event.position().toPoint())
            self._selection_rect = QRectF(self._selection_start, current_pos).normalized()
            self.viewport().update()  # 重绘视图
            event.accept()
            return
        elif self._is_dragging and event.buttons() & Qt.RightButton:
            # 处理右键拖拽
            if self._drag_start_pos is not None:
                delta = event.position() - self._drag_start_pos
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - int(delta.x())
                )
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - int(delta.y())
                )
                self._drag_start_pos = event.position()
            event.accept()
            return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if self._selection_mode and event.button() == Qt.LeftButton and self._selection_rect:
            # 完成区域选择
            if self._selection_rect.width() > 10 and self._selection_rect.height() > 10:  # 最小选择区域
                self.area_selected.emit(self._selection_rect)
            self._selection_start = None
            self._selection_rect = None
            self.viewport().update()
            event.accept()
            return
        elif event.button() == Qt.MiddleButton:
            # 中键释放
            self.setDragMode(QGraphicsView.RubberBandDrag)
        elif event.button() == Qt.RightButton:
            # 右键释放
            self._is_dragging = False
            self._drag_start_pos = None
            self.viewport().setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
    
    def paintEvent(self, event):
        """绘制事件"""
        super().paintEvent(event)
        
        # 绘制选择矩形
        if self._selection_mode and self._selection_rect:
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor(0, 120, 215), 2, Qt.DashLine))
            painter.setBrush(QBrush(QColor(0, 120, 215, 30)))
            
            # 转换场景坐标到视图坐标
            view_rect = self.mapFromScene(self._selection_rect).boundingRect()
            painter.drawRect(view_rect)
            painter.end()


class AnnotationList(QListWidget):
    """
    标注列表窗口
    """
    annotation_selected = Signal(int)  # 标注被选中信号
    
    def __init__(self):
        super().__init__()
        self.itemClicked.connect(self._on_item_clicked)
        self.setup_style()
        
    def setup_style(self):
        """设置样式"""
        self.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 3px;
                font-size: 12px;
                color: #495057;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f3f4;
                background-color: #ffffff;
                color: #495057;
                font-weight: 500;
            }
            QListWidget::item:selected {
                background-color: #e7f3ff;
                color: #0066cc;
                border-left: 3px solid #0066cc;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                color: #212529;
            }
        """)
        
    def add_annotation(self, annotation: BubbleAnnotationItem):
        """添加标注到列表"""
        # 创建更详细的显示文本
        pos = annotation.pos()
        text = f"● {annotation.annotation_id} - {annotation.text[:20]}..." if len(annotation.text) > 20 else f"● {annotation.annotation_id} - {annotation.text}"
        
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, annotation.annotation_id)
        
        # 设置工具提示
        tooltip = f"标注 {annotation.annotation_id}\n位置: ({pos.x():.1f}, {pos.y():.1f})\n描述: {annotation.text}"
        item.setToolTip(tooltip)
        
        self.addItem(item)
    
    def clear_annotations(self):
        """清除所有标注"""
        self.clear()
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """列表项被点击"""
        annotation_id = item.data(Qt.UserRole)
        self.annotation_selected.emit(annotation_id)
    
    def highlight_annotation(self, annotation_id: int):
        """高亮指定标注"""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.UserRole) == annotation_id:
                self.setCurrentItem(item)
                break
    
    def update_annotation_text(self, annotation_id: int, new_text: str):
        """更新列表中标注的显示文本"""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.UserRole) == annotation_id:
                display_text = f"● {annotation_id} - {new_text[:20]}..." if len(new_text) > 20 else f"● {annotation_id} - {new_text}"
                item.setText(display_text)
                break


class PropertyEditor(QWidget):
    """
    属性编辑器
    """
    text_changed = Signal(str)  # 文本改变信号
    
    def __init__(self):
        super().__init__()
        self.current_annotation: Optional[BubbleAnnotationItem] = None
        self.setup_ui()
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建分组框 - 基本信息
        basic_group = QWidget()
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(8)
        
        # ID标签
        self.id_label = QLabel("无")
        self.id_label.setStyleSheet("font-weight: bold; color: #0066cc; background-color: transparent; border: none;")
        basic_layout.addRow("标注编号:", self.id_label)
        
        # 位置标签
        self.position_label = QLabel("无")
        basic_layout.addRow("坐标位置:", self.position_label)
        
        # 类型标签
        self.type_label = QLabel("气泡标注")
        basic_layout.addRow("标注类型:", self.type_label)
        
        layout.addWidget(basic_group)
        
        # 分隔线
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #cccccc; margin: 10px 0;")
        layout.addWidget(separator)
        
        # 文本编辑区域
        text_group = QWidget()
        text_layout = QVBoxLayout(text_group)
        
        text_label = QLabel("标注描述:")
        text_label.setStyleSheet("font-weight: bold; color: #495057; background-color: transparent; border: none;")
        text_layout.addWidget(text_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(120)  # 限制高度
        self.text_edit.textChanged.connect(self._on_text_changed)
        text_layout.addWidget(self.text_edit)
        
        layout.addWidget(text_group)
        
        # 统计信息区域
        stats_group = QWidget()
        stats_layout = QFormLayout(stats_group)
        stats_layout.setSpacing(5)
        
        self.char_count_label = QLabel("0")
        stats_layout.addRow("字符数:", self.char_count_label)
        
        self.created_time_label = QLabel("无")
        stats_layout.addRow("创建时间:", self.created_time_label)
        
        layout.addWidget(stats_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 设置整体样式
        self.setStyleSheet("""
            QWidget {
                font-size: 12px;
                color: #495057;
                background-color: #ffffff;
            }
            QLabel {
                color: #495057;
                background-color: transparent;
                border: none;
                padding: 2px;
            }
            QTextEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: #ffffff;
                color: #495057;
                font-family: "Microsoft YaHei", "Consolas", monospace;
            }
            QTextEdit:focus {
                border-color: #0066cc;
                box-shadow: 0 0 0 0.2rem rgba(0, 102, 204, 0.25);
            }
        """)
    
    def set_annotation(self, annotation: Optional[BubbleAnnotationItem]):
        """设置当前编辑的标注"""
        self.current_annotation = annotation
        if annotation:
            self.id_label.setText(str(annotation.annotation_id))
            pos = annotation.pos()
            self.position_label.setText(f"({pos.x():.1f}, {pos.y():.1f})")
            
            # 更新类型标签以显示样式
            style_map = {"default": "气泡标注 (默认)", "warning": "气泡标注 (警告)", 
                        "error": "气泡标注 (错误)", "success": "气泡标注 (成功)"}
            self.type_label.setText(style_map.get(annotation.style, "气泡标注"))
            
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(annotation.text)
            self.text_edit.blockSignals(False)
            
            # 更新字符数
            self.char_count_label.setText(str(len(annotation.text)))
            
            # 设置创建时间（这里使用当前时间作为示例）
            from datetime import datetime
            self.created_time_label.setText(datetime.now().strftime("%H:%M:%S"))
            
            self.setEnabled(True)
        else:
            self.id_label.setText("无")
            self.position_label.setText("无")
            self.type_label.setText("气泡标注")
            self.text_edit.clear()
            self.char_count_label.setText("0")
            self.created_time_label.setText("无")
            self.setEnabled(False)
    
    def _on_text_changed(self):
        """文本改变处理"""
        if self.current_annotation:
            new_text = self.text_edit.toPlainText()
            self.text_changed.emit(new_text)
            # 更新字符数
            self.char_count_label.setText(str(len(new_text)))
    
    def update_position(self, position: QPointF):
        """更新位置显示"""
        self.position_label.setText(f"({position.x():.1f}, {position.y():.1f})")


class MainWindow(QMainWindow):
    """
    主窗口类
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IntelliAnnotate - 智能图纸标注工具 (EasyOCR)")
        self.setWindowIcon(QAction("🔍", self).icon())
        self.annotations = []  # 存储所有标注
        self.annotation_counter = 0  # 标注计数器
        self.current_file_path = None  # 当前文件路径
        self.ocr_results = []  # OCR识别结果
        self.thread_pool = QThreadPool()  # 线程池
        self.current_annotation = None  # 当前选中的标注
        self.setup_ui()
        self.setup_menu_bar()
        self.setup_toolbar()
        self.setup_connections()
        
        # 设置窗口大小
        self.resize(1400, 900)
        
    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("IntelliAnnotate - 智能图纸标注工具 (EasyOCR)")
        self.setGeometry(100, 100, 1400, 800)
        
        # 设置窗口图标和样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QSplitter::handle {
                background-color: #dee2e6;
                width: 3px;
                height: 3px;
            }
            QSplitter::handle:hover {
                background-color: #adb5bd;
            }
            QLabel {
                font-weight: bold;
                color: #212529;
                padding: 5px;
                background-color: #e9ecef;
                border-bottom: 1px solid #dee2e6;
            }
            QWidget {
                font-family: "Microsoft YaHei", "Arial", sans-serif;
                color: #212529;
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px 15px;
                min-height: 20px;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #6c757d;
                color: #212529;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #6c757d;
                border-color: #dee2e6;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 4px 8px;
                color: #495057;
            }
            QComboBox:hover {
                border-color: #6c757d;
            }
            QCheckBox {
                color: #495057;
            }
            QSlider::groove:horizontal {
                background-color: #dee2e6;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background-color: #6c757d;
                border: 1px solid #495057;
                width: 18px;
                border-radius: 9px;
                margin: -5px 0;
            }
            QSlider::handle:horizontal:hover {
                background-color: #495057;
            }
        """)

        # 创建中央部件和主分割器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # 左侧区域 - 使用垂直分割器分为上下两部分
        left_splitter = QSplitter(Qt.Vertical)
        
        # 左上方 - 图纸显示区域 + OCR控制
        graphics_panel = QWidget()
        graphics_layout = QVBoxLayout(graphics_panel)
        graphics_layout.setContentsMargins(0, 0, 0, 0)
        graphics_layout.setSpacing(0)
        
        graphics_title = QLabel("图纸视图 & OCR识别")
        graphics_title.setStyleSheet("""
            QLabel {
                background-color: #6f7eac;
                color: white;
                font-weight: bold;
                padding: 8px;
                margin: 0px;
                border: none;
            }
        """)
        graphics_layout.addWidget(graphics_title)
        
        # OCR控制面板（紧凑版）
        self.setup_compact_ocr_panel(graphics_layout)
        
        # 图形视图
        self.graphics_view = GraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        graphics_layout.addWidget(self.graphics_view)
        
        # 左下方 - 标注列表
        annotation_panel = QWidget()
        annotation_layout = QVBoxLayout(annotation_panel)
        annotation_layout.setContentsMargins(0, 0, 0, 0)
        annotation_layout.setSpacing(0)
        
        annotation_title = QLabel("标注列表")
        annotation_title.setStyleSheet("""
            QLabel {
                background-color: #8a9bb8;
                color: white;
                font-weight: bold;
                padding: 8px;
                margin: 0px;
                border: none;
            }
        """)
        annotation_layout.addWidget(annotation_title)
        
        self.annotation_list = AnnotationList()
        annotation_layout.addWidget(self.annotation_list)
        
        # 添加到左侧垂直分割器
        left_splitter.addWidget(graphics_panel)
        left_splitter.addWidget(annotation_panel)
        
        # 设置左侧分割器比例 (图纸区域占3，列表区域占1)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 1)
        
        # 右侧面板 - 属性编辑器
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        property_title = QLabel("属性编辑器")
        property_title.setStyleSheet("""
            QLabel {
                background-color: #7ba05b;
                color: white;
                font-weight: bold;
                padding: 8px;
                margin: 0px;
                border: none;
            }
        """)
        right_layout.addWidget(property_title)
        
        self.property_editor = PropertyEditor()
        right_layout.addWidget(self.property_editor)
        
        # 添加到主分割器
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_panel)
        
        # 设置主分割器比例 (左侧占3，右侧占1)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)

    def setup_compact_ocr_panel(self, parent_layout):
        """设置紧凑的OCR控制面板"""
        ocr_widget = QWidget()
        ocr_widget.setMaximumHeight(200)
        ocr_layout = QVBoxLayout(ocr_widget)
        ocr_layout.setContentsMargins(5, 5, 5, 5)
        ocr_layout.setSpacing(3)
        
        # 第一行：语言选择和置信度
        row1_layout = QHBoxLayout()
        
        # 语言选择
        row1_layout.addWidget(QLabel("语言:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems(["中文+英文", "仅中文", "仅英文"])
        self.language_combo.setCurrentText("中文+英文")
        row1_layout.addWidget(self.language_combo)
        
        # 置信度
        row1_layout.addWidget(QLabel("置信度:"))
        self.confidence_slider = QSlider(Qt.Horizontal)
        self.confidence_slider.setRange(10, 90)
        self.confidence_slider.setValue(30)
        self.confidence_slider.setMaximumWidth(80)
        self.confidence_label = QLabel("0.30")
        self.confidence_label.setMinimumWidth(40)
        row1_layout.addWidget(self.confidence_slider)
        row1_layout.addWidget(self.confidence_label)
        
        ocr_layout.addLayout(row1_layout)
        
        # 第二行：预处理选项
        row2_layout = QHBoxLayout()
        
        self.enhance_contrast_cb = QCheckBox("增强对比度")
        self.enhance_contrast_cb.setChecked(True)
        row2_layout.addWidget(self.enhance_contrast_cb)
        
        self.denoise_cb = QCheckBox("降噪")
        self.denoise_cb.setChecked(True)
        row2_layout.addWidget(self.denoise_cb)
        
        self.gpu_checkbox = QCheckBox("GPU")
        if HAS_OCR_SUPPORT:
            self.gpu_checkbox.setChecked(torch.cuda.is_available())
            self.gpu_checkbox.setEnabled(torch.cuda.is_available())
        else:
            self.gpu_checkbox.setChecked(False)
            self.gpu_checkbox.setEnabled(False)
        row2_layout.addWidget(self.gpu_checkbox)
        
        row2_layout.addStretch()
        ocr_layout.addLayout(row2_layout)
        
        # 第三行：按钮和进度条
        row3_layout = QHBoxLayout()
        
        self.ocr_button = QPushButton("🔍 开始OCR识别" if HAS_OCR_SUPPORT else "❌ OCR不可用")
        if not HAS_OCR_SUPPORT:
            self.ocr_button.setEnabled(False)
            self.ocr_button.setToolTip("请安装完整依赖包以启用OCR功能")
        self.ocr_button.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                font-weight: bold;
                border: none;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        row3_layout.addWidget(self.ocr_button)
        
        self.create_all_btn = QPushButton("全部标注")
        self.create_all_btn.setMaximumWidth(80)
        row3_layout.addWidget(self.create_all_btn)
        
        self.clear_ocr_btn = QPushButton("清除OCR")
        self.clear_ocr_btn.setMaximumWidth(80)
        row3_layout.addWidget(self.clear_ocr_btn)
        
        ocr_layout.addLayout(row3_layout)
        
        # 进度条和统计信息
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(15)
        ocr_layout.addWidget(self.progress_bar)
        
        self.ocr_stats_label = QLabel("识别结果: 0个文本")
        self.ocr_stats_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                padding: 4px;
                color: #6c757d;
                font-size: 11px;
            }
        """)
        ocr_layout.addWidget(self.ocr_stats_label)
        
        # 筛选下拉框
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "全部", "螺纹规格", "直径标注", "尺寸标注", 
            "角度标注", "数值", "材料标记", "表面处理"
        ])
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        ocr_layout.addLayout(filter_layout)
        
        parent_layout.addWidget(ocr_widget)
        
        # 连接信号
        self.confidence_slider.valueChanged.connect(
            lambda v: self.confidence_label.setText(f"{v/100:.2f}")
        )
        self.ocr_button.clicked.connect(self.start_ocr_recognition)
        self.create_all_btn.clicked.connect(self.create_annotations_from_ocr)
        self.clear_ocr_btn.clicked.connect(self.clear_ocr_results)
        self.filter_combo.currentTextChanged.connect(self.filter_ocr_results)

    def setup_menu_bar(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        open_action = QAction("打开...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
    
    def setup_toolbar(self):
        """设置工具栏"""
        toolbar = self.addToolBar("主工具栏")
        
        # 打开文件按钮
        open_action = QAction("打开文件", self)
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)
        
        toolbar.addSeparator()
        
        # AI识别按钮
        ai_recognize_action = QAction("AI识别", self)
        ai_recognize_action.triggered.connect(self.simulate_ai_recognition)
        toolbar.addAction(ai_recognize_action)
        
        # 区域选择标注按钮
        self.area_select_action = QAction("区域标注", self)
        self.area_select_action.setCheckable(True)
        self.area_select_action.toggled.connect(self.toggle_area_selection)
        toolbar.addAction(self.area_select_action)
        
        toolbar.addSeparator()
        
        # 清除标注按钮
        clear_action = QAction("清除标注", self)
        clear_action.triggered.connect(self.clear_annotations)
        toolbar.addAction(clear_action)
        
        toolbar.addSeparator()
        
        # 样式快速选择按钮
        style_group = toolbar.addWidget(QLabel("快速样式:"))
        
        self.style_combo = QComboBox()
        self.style_combo.addItems(["默认", "警告", "错误", "成功"])
        self.style_combo.currentTextChanged.connect(self.change_current_annotation_style)
        toolbar.addWidget(self.style_combo)
    
    def setup_connections(self):
        """设置信号连接"""
        # 标注列表选择
        self.annotation_list.annotation_selected.connect(self.select_annotation_by_id)
        
        # 属性编辑器文本改变
        self.property_editor.text_changed.connect(self.update_annotation_text)
        
        # 图形视图区域选择
        self.graphics_view.area_selected.connect(self.create_annotation_in_area)
    
    def open_file(self):
        """打开文件对话框"""
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter(
            "所有支持的文件 (*.png *.jpg *.jpeg *.pdf *.dxf);;"
            "图像文件 (*.png *.jpg *.jpeg);;"
            "PDF文件 (*.pdf);;"
            "DXF文件 (*.dxf)"
        )
        
        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            if file_paths:
                self.load_file(file_paths[0])
    
    def load_file(self, file_path: str):
        """加载文件"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        # 清除现有内容
        self.graphics_scene.clear()
        self.clear_annotations()
        self.clear_ocr_results()
        
        try:
            if extension in ['.png', '.jpg', '.jpeg']:
                pixmap = FileLoader.load_image(str(file_path))
                if pixmap:
                    self.graphics_scene.addPixmap(pixmap)
                    self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(),
                                               Qt.KeepAspectRatio)
                    # 设置当前文件路径
                    self.current_file_path = str(file_path)
                else:
                    QMessageBox.warning(self, "错误", "无法加载图像文件")
                    return
                    
            elif extension == '.pdf':
                pixmap = FileLoader.load_pdf(str(file_path))
                if pixmap:
                    self.graphics_scene.addPixmap(pixmap)
                    self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(),
                                               Qt.KeepAspectRatio)
                    # 设置当前文件路径
                    self.current_file_path = str(file_path)
                else:
                    QMessageBox.warning(self, "错误", "无法加载PDF文件")
                    return
                    
            elif extension == '.dxf':
                FileLoader.load_dxf(str(file_path), self.graphics_scene)
                self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(),
                                           Qt.KeepAspectRatio)
                # DXF文件不支持OCR，提示用户
                self.current_file_path = None
                QMessageBox.information(self, "提示", "DXF文件已加载，但不支持OCR文字识别功能")
                
            elif extension == '.dwg':
                QMessageBox.information(self, "提示", "暂不支持DWG格式文件")
                return
                
            else:
                QMessageBox.warning(self, "错误", f"不支持的文件格式: {extension}")
                return
                
            # 启用OCR按钮（仅对图像和PDF文件）
            self.ocr_button.setEnabled(self.current_file_path is not None)
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件时发生错误: {str(e)}")
            self.current_file_path = None

    def simulate_ai_recognition(self):
        """启动OCR识别（替换原有的模拟方法）"""
        self.start_ocr_recognition()

    def start_ocr_recognition(self):
        """开始OCR识别"""
        if not HAS_OCR_SUPPORT:
            QMessageBox.warning(self, "功能不可用", 
                              "OCR功能未启用！\n\n"
                              "请安装完整的依赖包以启用OCR功能:\n"
                              "pip install -r requirements.txt")
            return
            
        if not self.current_file_path:
            QMessageBox.warning(self, "警告", "请先加载图纸文件!")
            return
        
        # 获取语言设置
        language_map = {
            "中文+英文": ['ch_sim', 'en'],
            "仅中文": ['ch_sim'],
            "仅英文": ['en']
        }
        selected_languages = language_map[self.language_combo.currentText()]
        
        # 创建OCR工作线程
        self.ocr_worker = OCRWorker(self.current_file_path, selected_languages)
        self.ocr_worker.signals.finished.connect(self.on_ocr_finished)
        self.ocr_worker.signals.progress.connect(self.on_ocr_progress)
        self.ocr_worker.signals.error.connect(self.on_ocr_error)
        
        # 更新UI状态
        self.ocr_button.setEnabled(False)
        self.ocr_button.setText("🔄 识别中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动线程
        self.thread_pool.start(self.ocr_worker)

    def on_ocr_progress(self, progress):
        """OCR进度更新"""
        self.progress_bar.setValue(progress)

    def on_ocr_error(self, error_msg):
        """OCR错误处理"""
        self.ocr_button.setEnabled(True)
        self.ocr_button.setText("🔍 开始OCR识别")
        self.progress_bar.setVisible(False)
        
        QMessageBox.critical(self, "OCR识别错误", error_msg)

    def on_ocr_finished(self, results):
        """OCR识别完成"""
        self.ocr_button.setEnabled(True)
        self.ocr_button.setText("🔍 开始OCR识别")
        self.progress_bar.setVisible(False)
        
        # 存储结果
        self.ocr_results = results
        
        # 更新统计信息
        self.update_ocr_stats()
        
        # 在场景中显示OCR结果
        self.display_ocr_results()
        
        QMessageBox.information(
            self, "OCR识别完成", 
            f"成功识别出 {len(results)} 个文本区域。\n"
            f"您可以选择创建标注或进一步筛选结果。"
        )

    def update_ocr_stats(self):
        """更新OCR统计信息"""
        total_count = len(self.ocr_results)
        
        # 统计不同类型的数量
        type_counts = {}
        for result in self.ocr_results:
            text_type = result['text_type']
            type_counts[text_type] = type_counts.get(text_type, 0) + 1
        
        stats_text = f"识别结果: {total_count}个文本"
        if type_counts:
            type_info = ", ".join([f"{k}({v})" for k, v in type_counts.items()])
            stats_text += f" ({type_info})"
        
        self.ocr_stats_label.setText(stats_text)

    def display_ocr_results(self):
        """在场景中显示OCR结果"""
        # 清除之前的OCR显示
        self.clear_ocr_display()
        
        # 为每个OCR结果创建可视化边界框
        for i, result in enumerate(self.ocr_results):
            self.create_ocr_bbox_item(result, i)

    def create_ocr_bbox_item(self, ocr_result, index):
        """创建OCR边界框显示项"""
        bbox = ocr_result['bbox']
        bbox_array = np.array(bbox)
        
        # 创建边界框画路径
        path = QPainterPath()
        path.moveTo(bbox_array[0][0], bbox_array[0][1])
        for point in bbox_array[1:]:
            path.lineTo(point[0], point[1])
        path.closeSubpath()
        
        # 创建图形项
        bbox_item = QGraphicsPathItem(path)
        
        # 根据文本类型设置不同颜色
        color_map = {
            'thread_spec': QColor(255, 0, 0, 100),      # 红色 - 螺纹规格
            'diameter': QColor(0, 255, 0, 100),         # 绿色 - 直径标注
            'dimension': QColor(0, 0, 255, 100),        # 蓝色 - 尺寸标注
            'angle': QColor(255, 255, 0, 100),          # 黄色 - 角度标注
            'number': QColor(255, 0, 255, 100),         # 紫色 - 数值
            'material': QColor(0, 255, 255, 100),       # 青色 - 材料
            'surface_treatment': QColor(255, 165, 0, 100),  # 橙色 - 表面处理
            'annotation': QColor(128, 128, 128, 100)    # 灰色 - 普通标注
        }
        
        text_type = ocr_result['text_type']
        color = color_map.get(text_type, QColor(128, 128, 128, 100))
        
        bbox_item.setPen(QPen(color, 2))
        bbox_item.setBrush(QBrush(color))
        
        # 添加到场景
        self.graphics_scene.addItem(bbox_item)
        
        # 存储OCR信息到图形项
        bbox_item.ocr_result = ocr_result
        bbox_item.ocr_index = index

    def clear_ocr_display(self):
        """清除OCR显示"""
        # 移除所有OCR边界框
        items_to_remove = []
        for item in self.graphics_scene.items():
            if hasattr(item, 'ocr_result'):
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.graphics_scene.removeItem(item)

    def clear_ocr_results(self):
        """清除OCR结果"""
        self.ocr_results = []
        self.clear_ocr_display()
        self.update_ocr_stats()

    def filter_ocr_results(self):
        """筛选OCR结果"""
        filter_type = self.filter_combo.currentText()
        
        if filter_type == "全部":
            filtered_results = self.ocr_results
        else:
            type_map = {
                "螺纹规格": "thread_spec",
                "直径标注": "diameter", 
                "尺寸标注": "dimension",
                "角度标注": "angle",
                "数值": "number",
                "材料标记": "material",
                "表面处理": "surface_treatment"
            }
            target_type = type_map.get(filter_type, "annotation")
            filtered_results = [r for r in self.ocr_results if r['text_type'] == target_type]
        
        # 更新显示
        self.clear_ocr_display()
        for i, result in enumerate(filtered_results):
            if result in self.ocr_results:
                original_index = self.ocr_results.index(result)
                self.create_ocr_bbox_item(result, original_index)

    def create_annotations_from_ocr(self):
        """从所有OCR结果创建标注"""
        if not self.ocr_results:
            QMessageBox.warning(self, "警告", "没有OCR识别结果!")
            return
        
        created_count = 0
        for result in self.ocr_results:
            # 应用置信度筛选
            confidence_threshold = self.confidence_slider.value() / 100.0
            if result['confidence'] >= confidence_threshold:
                self.create_annotation_from_ocr_result(result)
                created_count += 1
        
        QMessageBox.information(
            self, "创建完成", 
            f"成功创建了 {created_count} 个标注。"
        )
        
        # 刷新标注列表
        self.refresh_annotation_list()

    def create_annotation_from_ocr_result(self, ocr_result):
        """从OCR结果创建单个标注"""
        self.annotation_counter += 1
        
        # 创建标注位置
        position = QPointF(ocr_result['center_x'], ocr_result['center_y'])
        
        # 根据文本类型选择样式
        style_map = {
            'thread_spec': 'error',      # 螺纹规格用红色
            'diameter': 'success',       # 直径标注用绿色
            'dimension': 'default',      # 尺寸标注用默认
            'angle': 'warning',          # 角度标注用警告色
            'material': 'success',       # 材料用绿色
            'surface_treatment': 'warning'  # 表面处理用警告色
        }
        style = style_map.get(ocr_result['text_type'], 'default')
        
        # 创建标注文本
        annotation_text = f"{ocr_result['text']} (置信度: {ocr_result['confidence']:.2f})"
        
        # 创建气泡标注
        annotation = BubbleAnnotationItem(
            self.annotation_counter,
            position,
            annotation_text,
            style
        )
        
        # 连接信号
        annotation.selected.connect(self.on_annotation_selected)
        annotation.moved.connect(self.on_annotation_moved)
        annotation.delete_requested.connect(self.delete_annotation)
        annotation.style_change_requested.connect(self.on_annotation_style_changed)
        
        # 添加到场景和列表
        self.graphics_scene.addItem(annotation)
        self.annotations.append(annotation)
        self.annotation_list.add_annotation(annotation)

    def on_annotation_selected(self, annotation: BubbleAnnotationItem):
        """标注被选中"""
        # 清除其他标注的高亮
        for ann in self.annotations:
            ann.set_highlighted(False)
        
        # 设置当前标注
        self.current_annotation = annotation
        annotation.set_highlighted(True)
        
        # 更新属性编辑器
        self.property_editor.set_annotation(annotation)
        
        # 更新列表选择
        self.annotation_list.highlight_annotation(annotation.annotation_id)
        
        # 更新样式组合框
        style_map = {"default": "默认", "warning": "警告", "error": "错误", "success": "成功"}
        style_text = style_map.get(annotation.style, "默认")
        self.style_combo.blockSignals(True)
        self.style_combo.setCurrentText(style_text)
        self.style_combo.blockSignals(False)
    
    def on_annotation_moved(self, annotation: BubbleAnnotationItem, position: QPointF):
        """标注被移动"""
        if annotation == self.current_annotation:
            self.property_editor.update_position(position)
    
    def select_annotation_by_id(self, annotation_id: int):
        """根据ID选择标注"""
        for annotation in self.annotations:
            if annotation.annotation_id == annotation_id:
                # 居中显示
                self.graphics_view.centerOn(annotation)
                
                # 选择标注
                self.graphics_scene.clearSelection()
                annotation.setSelected(True)
                self.on_annotation_selected(annotation)
                break
    
    def update_annotation_text(self, new_text: str):
        """更新标注文本"""
        if self.current_annotation:
            self.current_annotation.set_text(new_text)
            # 同时更新列表中的显示文本
            self.annotation_list.update_annotation_text(
                self.current_annotation.annotation_id, 
                new_text
            )

    def toggle_area_selection(self, checked: bool):
        """切换区域选择模式"""
        self.graphics_view.set_selection_mode(checked)
        if checked:
            self.area_select_action.setText("退出区域选择")
        else:
            self.area_select_action.setText("区域标注")
    
    def create_annotation_in_area(self, rect: QRectF):
        """在选定区域创建标注"""
        self.annotation_counter += 1
        
        # 在矩形中心创建标注
        center = rect.center()
        
        # 创建标注
        annotation = BubbleAnnotationItem(
            self.annotation_counter,
            center,
            f"区域标注 {self.annotation_counter}"
        )
        
        # 连接信号
        annotation.selected.connect(self.on_annotation_selected)
        annotation.moved.connect(self.on_annotation_moved)
        annotation.delete_requested.connect(self.delete_annotation)
        annotation.style_change_requested.connect(self.on_annotation_style_changed)
        
        # 添加到场景和列表
        self.graphics_scene.addItem(annotation)
        self.annotations.append(annotation)
        self.annotation_list.add_annotation(annotation)
        
        # 退出区域选择模式
        self.area_select_action.setChecked(False)
    
    def delete_annotation(self, annotation: BubbleAnnotationItem):
        """删除标注"""
        if annotation in self.annotations:
            # 从场景移除
            self.graphics_scene.removeItem(annotation)
            
            # 从列表移除
            self.annotations.remove(annotation)
            
            # 更新列表显示
            self.refresh_annotation_list()
            
            # 如果删除的是当前选中的标注，清空属性编辑器
            if self.current_annotation == annotation:
                self.current_annotation = None
                self.property_editor.set_annotation(None)
    
    def refresh_annotation_list(self):
        """刷新标注列表显示"""
        self.annotation_list.clear_annotations()
        for annotation in self.annotations:
            self.annotation_list.add_annotation(annotation)
    
    def on_annotation_style_changed(self, annotation: BubbleAnnotationItem):
        """标注样式改变时的处理"""
        # 更新样式组合框显示
        if annotation == self.current_annotation:
            style_map = {"default": "默认", "warning": "警告", "error": "错误", "success": "成功"}
            style_text = style_map.get(annotation.style, "默认")
            self.style_combo.blockSignals(True)
            self.style_combo.setCurrentText(style_text)
            self.style_combo.blockSignals(False)
    
    def change_current_annotation_style(self, style_text: str):
        """更改当前标注的样式"""
        if self.current_annotation:
            style_map = {"默认": "default", "警告": "warning", "错误": "error", "成功": "success"}
            new_style = style_map.get(style_text, "default")
            self.current_annotation.change_style(new_style)

    def clear_annotations(self):
        """清除所有标注"""
        for annotation in self.annotations[:]:  # 使用切片复制避免修改过程中列表变化
            if annotation.scene():
                self.graphics_scene.removeItem(annotation)
        
        self.annotations.clear()
        self.annotation_list.clear_annotations()
        self.property_editor.set_annotation(None)


class FileLoader:
    """
    文件加载器，处理不同格式的文件
    """
    @staticmethod
    def load_image(file_path: str) -> Optional[QPixmap]:
        """加载图像文件"""
        try:
            if Image is None:
                # 如果PIL不可用，尝试使用QPixmap直接加载
                pixmap = QPixmap(file_path)
                return pixmap if not pixmap.isNull() else None
            
            pil_image = Image.open(file_path)
            # 转换为RGB模式以确保兼容性
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # 使用更简单的方法
            pixmap = QPixmap(file_path)
            return pixmap if not pixmap.isNull() else None
            
        except Exception as e:
            print(f"加载图像失败: {e}")
            return None
    
    @staticmethod
    def load_pdf(file_path: str, page_num: int = 0) -> Optional[QPixmap]:
        """加载PDF文件"""
        if not HAS_OCR_SUPPORT:
            return None
            
        try:
            import fitz
            doc = fitz.open(file_path)
            if page_num >= len(doc):
                page_num = 0
            
            page = doc.load_page(page_num)
            
            # 设置合适的分辨率
            zoom = 2.0  # 增加分辨率
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为QPixmap
            img_data = pix.pil_tobytes(format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(img_data)
            
            doc.close()
            return pixmap
            
        except Exception as e:
            print(f"加载PDF失败: {e}")
            return None
    
    @staticmethod
    def load_dxf(file_path: str, scene: QGraphicsScene):
        """加载DXF文件"""
        if not HAS_OCR_SUPPORT:
            return
            
        try:
            import ezdxf
            doc = ezdxf.readfile(file_path)
            
            # 获取模型空间
            msp = doc.modelspace()
            
            # 简单地将DXF实体转换为Graphics项
            for entity in msp:
                if entity.dxftype() == 'LINE':
                    FileLoader._add_line_to_scene(entity, scene)
                elif entity.dxftype() == 'CIRCLE':
                    FileLoader._add_circle_to_scene(entity, scene)
                elif entity.dxftype() == 'ARC':
                    FileLoader._add_arc_to_scene(entity, scene)
                # 可以添加更多实体类型的处理
            
        except Exception as e:
            print(f"加载DXF失败: {e}")
    
    @staticmethod
    def _add_line_to_scene(line_entity, scene: QGraphicsScene):
        """将LINE实体添加到场景"""
        start = line_entity.dxf.start
        end = line_entity.dxf.end
        
        path = QPainterPath()
        path.moveTo(start.x, -start.y)  # DXF的Y轴与Qt相反
        path.lineTo(end.x, -end.y)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(0, 0, 0), 1))
        scene.addItem(item)
    
    @staticmethod
    def _add_circle_to_scene(circle_entity, scene: QGraphicsScene):
        """将CIRCLE实体添加到场景"""
        center = circle_entity.dxf.center
        radius = circle_entity.dxf.radius
        
        path = QPainterPath()
        path.addEllipse(center.x - radius, -center.y - radius, 
                       radius * 2, radius * 2)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(0, 0, 0), 1))
        item.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(item)
    
    @staticmethod
    def _add_arc_to_scene(arc_entity, scene: QGraphicsScene):
        """将ARC实体添加到场景"""
        center = arc_entity.dxf.center
        radius = arc_entity.dxf.radius
        start_angle = arc_entity.dxf.start_angle
        end_angle = arc_entity.dxf.end_angle
        
        path = QPainterPath()
        # 这里需要更复杂的弧线绘制逻辑
        # 简化版本：绘制为圆圈
        path.addEllipse(center.x - radius, -center.y - radius,
                       radius * 2, radius * 2)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(0, 0, 0), 1))
        item.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(item)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用属性
    app.setApplicationName("IntelliAnnotate")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("IntelliAnnotate Inc.")
    
    # 设置样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main()) 