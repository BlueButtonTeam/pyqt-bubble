# ui/main_window.py (支持调整大小版 - 真正完整)

import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGraphicsScene, QMenuBar, QToolBar, QFileDialog, QMessageBox, 
    QPushButton, QComboBox, QProgressBar, QCheckBox, QSlider, QLabel, QColorDialog
)
from PySide6.QtCore import Qt, QRectF, QPointF, QThreadPool
from PySide6.QtGui import QAction, QPainterPath, QColor, QPen, QBrush

# 导入自定义模块
from utils.constants import (
    APP_TITLE, FILE_DIALOG_FILTER, DEFAULT_WINDOW_SIZE, DEFAULT_WINDOW_POSITION,
    DEFAULT_OCR_LANGUAGES, PDF_QUALITY_OPTIONS, OCR_TEXT_TYPE_COLORS,
    OCR_TYPE_TO_STYLE, STYLE_NAME_MAP, STYLE_NAME_REVERSE_MAP,
    OCR_FILTER_OPTIONS, OCR_FILTER_TYPE_MAP, UI_COLORS, SUPPORTED_IMAGE_FORMATS,
    SUPPORTED_PDF_FORMATS, SUPPORTED_DXF_FORMATS
)
from utils.dependencies import HAS_OCR_SUPPORT, HAS_GPU_SUPPORT, get_requirements_message

from core.ocr_worker import OCRWorker
from core.annotation_item import BubbleAnnotationItem
from core.file_loader import FileLoader

from ui.graphics_view import GraphicsView
from ui.annotation_list import AnnotationList
from ui.property_editor import PropertyEditor

if HAS_OCR_SUPPORT:
    import numpy as np


class MainWindow(QMainWindow):
    """
    主窗口类
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.annotations = []
        self.annotation_counter = 0
        self.current_file_path = None
        self.ocr_results = []
        self.thread_pool = QThreadPool()
        self.current_annotation = None
        
        # --- 新增/修改属性 ---
        self.next_annotation_color: Optional[QColor] = None
        self.next_annotation_size: int = 15 # 新增：下一个标注的默认大小
        
        self.masked_regions = []
        self.is_selecting_mask = False
        
        self.setup_ui()
        self.setup_menu_bar()
        self.setup_toolbar()
        self.setup_connections()
        
        self.resize(*DEFAULT_WINDOW_SIZE)
        
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪", 2000)
        
    def setup_ui(self):
        self.setGeometry(*DEFAULT_WINDOW_POSITION, *DEFAULT_WINDOW_SIZE)
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {UI_COLORS["background"]}; }}
            QSplitter::handle {{ background-color: {UI_COLORS["border"]}; width: 3px; height: 3px; }}
            QSplitter::handle:hover {{ background-color: #adb5bd; }}
            QLabel {{ font-weight: bold; color: {UI_COLORS["text"]}; padding: 5px; background-color: #e9ecef; border-bottom: 1px solid {UI_COLORS["border"]}; }}
            QWidget {{ font-family: "Microsoft YaHei", "Arial", sans-serif; color: {UI_COLORS["text"]}; background-color: {UI_COLORS["white"]}; }}
            QPushButton {{ background-color: {UI_COLORS["white"]}; border: 1px solid #ced4da; border-radius: 4px; padding: 8px 15px; min-height: 20px; color: {UI_COLORS["text_secondary"]}; }}
            QPushButton:hover {{ background-color: {UI_COLORS["background"]}; border-color: #6c757d; color: {UI_COLORS["text"]}; }}
            QPushButton:pressed {{ background-color: #e9ecef; }}
            QPushButton:disabled {{ background-color: #e9ecef; color: #6c757d; border-color: {UI_COLORS["border"]}; }}
            QComboBox {{ background-color: {UI_COLORS["white"]}; border: 1px solid #ced4da; border-radius: 3px; padding: 4px 8px; color: {UI_COLORS["text_secondary"]}; }}
            QComboBox:hover {{ border-color: #6c757d; }}
            QCheckBox {{ color: {UI_COLORS["text_secondary"]}; }}
            QSlider::groove:horizontal {{ background-color: {UI_COLORS["border"]}; height: 8px; border-radius: 4px; }}
            QSlider::handle:horizontal {{ background-color: #6c757d; border: 1px solid {UI_COLORS["text_secondary"]}; width: 18px; border-radius: 9px; margin: -5px 0; }}
            QSlider::handle:horizontal:hover {{ background-color: {UI_COLORS["text_secondary"]}; }}
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        left_splitter = QSplitter(Qt.Vertical)
        
        graphics_panel = QWidget()
        graphics_layout = QVBoxLayout(graphics_panel)
        graphics_layout.setContentsMargins(0, 0, 0, 0)
        graphics_layout.setSpacing(0)
        
        graphics_title = QLabel("图纸视图 & OCR识别")
        graphics_title.setStyleSheet(f"QLabel {{ background-color: {UI_COLORS['primary']}; color: white; font-weight: bold; padding: 8px; margin: 0px; border: none; }}")
        graphics_layout.addWidget(graphics_title)
        
        self.setup_compact_ocr_panel(graphics_layout)
        
        self.graphics_view = GraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        graphics_layout.addWidget(self.graphics_view)
        
        annotation_panel = QWidget()
        annotation_layout = QVBoxLayout(annotation_panel)
        annotation_layout.setContentsMargins(0, 0, 0, 0)
        annotation_layout.setSpacing(0)
        
        annotation_title = QLabel("标注列表")
        annotation_title.setStyleSheet(f"QLabel {{ background-color: {UI_COLORS['secondary']}; color: white; font-weight: bold; padding: 8px; margin: 0px; border: none; }}")
        annotation_layout.addWidget(annotation_title)
        
        self.annotation_list = AnnotationList()
        annotation_layout.addWidget(self.annotation_list)
        
        left_splitter.addWidget(graphics_panel)
        left_splitter.addWidget(annotation_panel)
        
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 1)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        property_title = QLabel("属性编辑器")
        property_title.setStyleSheet(f"QLabel {{ background-color: {UI_COLORS['success']}; color: white; font-weight: bold; padding: 8px; margin: 0px; border: none; }}")
        right_layout.addWidget(property_title)
        
        self.property_editor = PropertyEditor()
        right_layout.addWidget(self.property_editor)
        
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_panel)
        
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)

    def setup_compact_ocr_panel(self, parent_layout):
        ocr_widget = QWidget()
        ocr_widget.setMaximumHeight(200)
        ocr_layout = QVBoxLayout(ocr_widget)
        ocr_layout.setContentsMargins(5, 5, 5, 5)
        ocr_layout.setSpacing(3)
        
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(QLabel("语言:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems(list(DEFAULT_OCR_LANGUAGES.keys()))
        self.language_combo.setCurrentText("中文+英文")
        row1_layout.addWidget(self.language_combo)
        
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
        
        row2_layout = QHBoxLayout()
        self.enhance_contrast_cb = QCheckBox("增强对比度"); self.enhance_contrast_cb.setChecked(True); row2_layout.addWidget(self.enhance_contrast_cb)
        self.denoise_cb = QCheckBox("降噪"); self.denoise_cb.setChecked(True); row2_layout.addWidget(self.denoise_cb)
        self.gpu_checkbox = QCheckBox("GPU"); self.gpu_checkbox.setChecked(HAS_GPU_SUPPORT); self.gpu_checkbox.setEnabled(HAS_GPU_SUPPORT); row2_layout.addWidget(self.gpu_checkbox)
        row2_layout.addStretch()
        ocr_layout.addLayout(row2_layout)
        
        row3_layout = QHBoxLayout()
        self.ocr_button = QPushButton("🔍 开始OCR识别" if HAS_OCR_SUPPORT else "❌ OCR不可用")
        if not HAS_OCR_SUPPORT: self.ocr_button.setEnabled(False); self.ocr_button.setToolTip("请安装完整依赖包以启用OCR功能")
        self.ocr_button.setStyleSheet(f"""QPushButton {{ background-color: {UI_COLORS["primary"]}; color: white; font-weight: bold; border: none; min-height: 25px; }} QPushButton:hover {{ background-color: {UI_COLORS["secondary"]}; }} QPushButton:disabled {{ background-color: #cccccc; color: #666666; }}""")
        row3_layout.addWidget(self.ocr_button)
        self.create_all_btn = QPushButton("全部标注"); self.create_all_btn.setMaximumWidth(80); row3_layout.addWidget(self.create_all_btn)
        self.clear_ocr_btn = QPushButton("清除OCR"); self.clear_ocr_btn.setMaximumWidth(80); row3_layout.addWidget(self.clear_ocr_btn)
        ocr_layout.addLayout(row3_layout)
        
        self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); self.progress_bar.setMaximumHeight(15); ocr_layout.addWidget(self.progress_bar)
        self.ocr_stats_label = QLabel("识别结果: 0个文本"); self.ocr_stats_label.setStyleSheet("QLabel { background-color: transparent; border: none; padding: 4px; color: #6c757d; font-size: 11px; }"); ocr_layout.addWidget(self.ocr_stats_label)
        
        filter_layout = QHBoxLayout(); filter_layout.addWidget(QLabel("筛选:")); self.filter_combo = QComboBox(); self.filter_combo.addItems(OCR_FILTER_OPTIONS); filter_layout.addWidget(self.filter_combo); filter_layout.addStretch(); ocr_layout.addLayout(filter_layout)
        
        parent_layout.addWidget(ocr_widget)

    def setup_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开...", self); open_action.setShortcut("Ctrl+O"); open_action.triggered.connect(self.open_file); file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("退出", self); exit_action.setShortcut("Ctrl+Q"); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
    
    def setup_toolbar(self):
        toolbar = self.addToolBar("主工具栏")
        
        open_action = QAction("打开文件", self); open_action.triggered.connect(self.open_file); toolbar.addAction(open_action)
        toolbar.addSeparator()
        
        toolbar.addWidget(QLabel("PDF质量:")); self.pdf_quality_combo = QComboBox(); self.pdf_quality_combo.addItems(list(PDF_QUALITY_OPTIONS.keys())); self.pdf_quality_combo.setCurrentText("高清 (4x)")
        self.pdf_quality_combo.setToolTip("选择PDF渲染质量:\n• 标准 (2x) - 快速加载，适合预览\n• 高清 (4x) - 推荐设置，平衡质量和速度\n• 超清 (6x) - 高质量，适合详细分析\n• 极清 (8x) - 最高质量，加载较慢\n\n注意：质量越高，文件加载越慢但图像越清晰")
        toolbar.addWidget(self.pdf_quality_combo)
        toolbar.addSeparator()
        
        ai_recognize_action = QAction("AI识别", self); ai_recognize_action.triggered.connect(self.simulate_ai_recognition); toolbar.addAction(ai_recognize_action)
        
        self.area_select_action = QAction("区域标注", self); self.area_select_action.setCheckable(True); self.area_select_action.setShortcut("Q"); self.area_select_action.setStatusTip("选择区域创建标注 (快捷键: Q)"); self.area_select_action.toggled.connect(self.toggle_area_selection); toolbar.addAction(self.area_select_action)
        
        self.mask_select_action = QAction("🚫 屏蔽区域", self); self.mask_select_action.setCheckable(True); self.mask_select_action.setStatusTip("选择不需要OCR识别的区域"); self.mask_select_action.toggled.connect(self.toggle_mask_selection); toolbar.addAction(self.mask_select_action)
        toolbar.addSeparator()
        
        clear_action = QAction("清除标注", self); clear_action.triggered.connect(self.clear_annotations); toolbar.addAction(clear_action)
        toolbar.addSeparator()

        # --- 新增：大小控制滑块 ---
        toolbar.addWidget(QLabel("大小:"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(8, 30) # 半径范围 8 到 30
        self.size_slider.setValue(self.next_annotation_size)
        self.size_slider.setFixedWidth(80)
        self.size_label = QLabel(str(self.next_annotation_size))
        self.size_label.setFixedWidth(25)
        toolbar.addWidget(self.size_slider)
        toolbar.addWidget(self.size_label)
        toolbar.addSeparator()
        # -------------------------

        self.color_button = QPushButton("颜色"); self.color_button.setToolTip("选择颜色..."); self.color_button.clicked.connect(self.select_annotation_color); toolbar.addWidget(self.color_button)
        
        toolbar.addWidget(QLabel("形状:")); self.shape_combo = QComboBox(); self.shape_combo.addItems(["空心圆", "实心圆", "五角星", "三角形"]); toolbar.addWidget(self.shape_combo)
        
        toolbar.addWidget(QLabel("快速样式:")); self.style_combo = QComboBox(); self.style_combo.addItems(["自定义"] + list(STYLE_NAME_MAP.values())); toolbar.addWidget(self.style_combo)
    
    def setup_connections(self):
        self.annotation_list.annotation_selected.connect(self.select_annotation_by_id)
        self.property_editor.text_changed.connect(self.update_annotation_text)
        self.graphics_view.area_selected.connect(self.handle_area_selection)
        
        self.size_slider.valueChanged.connect(self.change_annotation_size)
        self.shape_combo.currentTextChanged.connect(self.change_current_annotation_shape)
        self.style_combo.currentTextChanged.connect(self.change_current_annotation_style)
        
        self.confidence_slider.valueChanged.connect(lambda v: self.confidence_label.setText(f"{v/100:.2f}"))
        self.ocr_button.clicked.connect(self.start_ocr_recognition)
        self.create_all_btn.clicked.connect(self.create_annotations_from_ocr)
        self.clear_ocr_btn.clicked.connect(self.clear_ocr_results)
        self.filter_combo.currentTextChanged.connect(self.filter_ocr_results)

    def open_file(self, file_path: str):
        file_dialog = QFileDialog(self); file_dialog.setNameFilter(FILE_DIALOG_FILTER)
        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            if file_paths: self.load_file(file_paths[0])
    
    def load_file(self, file_path: str):
        file_path_obj = Path(file_path); extension = file_path_obj.suffix.lower()
        self.status_bar.showMessage(f"正在加载文件: {file_path_obj.name}...")
        self.graphics_scene.clear(); self.clear_annotations(); self.clear_ocr_results(); self.clear_masked_regions()
        try:
            pixmap = None
            if extension in SUPPORTED_IMAGE_FORMATS:
                pixmap = FileLoader.load_image(str(file_path))
                if pixmap: self.current_file_path = str(file_path)
            elif extension in SUPPORTED_PDF_FORMATS:
                zoom_factor = PDF_QUALITY_OPTIONS.get(self.pdf_quality_combo.currentText(), 4.0)
                self.status_bar.showMessage(f"正在以 {self.pdf_quality_combo.currentText()} 质量加载PDF...")
                pixmap = FileLoader.load_pdf(str(file_path), zoom_factor=zoom_factor)
                if pixmap: self.current_file_path = str(file_path)
            elif extension in SUPPORTED_DXF_FORMATS:
                FileLoader.load_dxf(str(file_path), self.graphics_scene)
                self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                self.current_file_path = None
                self.status_bar.showMessage(f"✅ DXF文件加载成功: {file_path_obj.name} (不支持OCR)", 5000)
                QMessageBox.information(self, "提示", "DXF文件已加载，但不支持OCR文字识别功能")
            else:
                QMessageBox.warning(self, "错误", f"不支持的文件格式: {extension}")
                self.status_bar.showMessage(f"❌ 不支持的文件格式: {extension}", 3000)
                return
            
            if pixmap:
                self.graphics_scene.addPixmap(pixmap)
                self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                self.status_bar.showMessage(f"✅ 文件加载成功: {file_path_obj.name} ({pixmap.width()}x{pixmap.height()})", 5000)
            elif self.current_file_path is None and extension not in SUPPORTED_DXF_FORMATS:
                 QMessageBox.warning(self, "错误", "无法加载文件")
                 self.status_bar.showMessage("❌ 文件加载失败", 3000)
            
            self.ocr_button.setEnabled(self.current_file_path is not None)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件时发生错误: {str(e)}")
            self.status_bar.showMessage(f"❌ 加载文件失败: {str(e)}", 5000)
            self.current_file_path = None

    def simulate_ai_recognition(self):
        self.start_ocr_recognition()

    def start_ocr_recognition(self):
        if not HAS_OCR_SUPPORT: QMessageBox.warning(self, "功能不可用", get_requirements_message()); return
        if not self.current_file_path: QMessageBox.warning(self, "警告", "请先加载图纸文件!"); return
        
        selected_languages = DEFAULT_OCR_LANGUAGES[self.language_combo.currentText()]
        masked_regions_data = [{'x': r.x(), 'y': r.y(), 'width': r.width(), 'height': r.height()} for r in self.masked_regions]
        
        self.ocr_worker = OCRWorker(self.current_file_path, selected_languages, masked_regions_data)
        self.ocr_worker.signals.finished.connect(self.on_ocr_finished)
        self.ocr_worker.signals.progress.connect(self.on_ocr_progress)
        self.ocr_worker.signals.error.connect(self.on_ocr_error)
        
        self.ocr_button.setEnabled(False); self.ocr_button.setText("🔄 识别中...")
        self.progress_bar.setVisible(True); self.progress_bar.setValue(0)
        self.status_bar.showMessage(f"正在进行OCR识别（已屏蔽 {len(self.masked_regions)} 个区域）..." if self.masked_regions else "正在进行OCR识别...")
        self.thread_pool.start(self.ocr_worker)

    def on_ocr_progress(self, progress):
        self.progress_bar.setValue(progress)

    def on_ocr_error(self, error_msg):
        self.ocr_button.setEnabled(True); self.ocr_button.setText("🔍 开始OCR识别")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "OCR识别错误", error_msg)

    def on_ocr_finished(self, results):
        self.ocr_button.setEnabled(True); self.ocr_button.setText("🔍 开始OCR识别")
        self.progress_bar.setVisible(False)
        if self.is_selecting_mask: self.toggle_mask_selection(False)
        self.ocr_results = results
        self.update_ocr_stats()
        self.display_ocr_results()
        QMessageBox.information(self, "OCR识别完成", f"成功识别出 {len(results)} 个文本区域。\n您可以选择创建标注或进一步筛选结果。")

    def update_ocr_stats(self):
        total_count = len(self.ocr_results)
        type_counts = {}
        for result in self.ocr_results: type_counts[result['text_type']] = type_counts.get(result['text_type'], 0) + 1
        stats_text = f"识别结果: {total_count}个文本"
        if type_counts: stats_text += f" ({', '.join([f'{k}({v})' for k, v in type_counts.items()])})"
        self.ocr_stats_label.setText(stats_text)

    def display_ocr_results(self):
        self.clear_ocr_display()
        for i, result in enumerate(self.ocr_results): self.create_ocr_bbox_item(result, i)

    def create_ocr_bbox_item(self, ocr_result, index):
        if not HAS_OCR_SUPPORT: return
        bbox = ocr_result['bbox']; bbox_array = np.array(bbox)
        path = QPainterPath(); path.moveTo(bbox_array[0][0], bbox_array[0][1])
        for point in bbox_array[1:]: path.lineTo(point[0], point[1])
        path.closeSubpath()
        from PySide6.QtWidgets import QGraphicsPathItem
        bbox_item = QGraphicsPathItem(path)
        text_type = ocr_result['text_type']; color = QColor(*OCR_TEXT_TYPE_COLORS.get(text_type, OCR_TEXT_TYPE_COLORS['annotation']))
        bbox_item.setPen(QPen(color, 2)); bbox_item.setBrush(QBrush(color))
        self.graphics_scene.addItem(bbox_item)
        bbox_item.ocr_result = ocr_result; bbox_item.ocr_index = index

    def clear_ocr_display(self):
        items_to_remove = [item for item in self.graphics_scene.items() if hasattr(item, 'ocr_result')]
        for item in items_to_remove: self.graphics_scene.removeItem(item)

    def clear_ocr_results(self):
        self.ocr_results = []; self.clear_ocr_display(); self.update_ocr_stats()

    def filter_ocr_results(self):
        filter_type = self.filter_combo.currentText()
        if filter_type == "全部": filtered_results = self.ocr_results
        else:
            target_type = OCR_FILTER_TYPE_MAP.get(filter_type, "annotation")
            filtered_results = [r for r in self.ocr_results if r['text_type'] == target_type]
        self.clear_ocr_display()
        for i, result in enumerate(filtered_results):
            if result in self.ocr_results:
                original_index = self.ocr_results.index(result)
                self.create_ocr_bbox_item(result, original_index)

    def create_annotations_from_ocr(self):
        if not self.ocr_results: QMessageBox.warning(self, "警告", "没有OCR识别结果!"); return
        created_count = 0
        confidence_threshold = self.confidence_slider.value() / 100.0
        for result in self.ocr_results:
            if result['confidence'] >= confidence_threshold:
                self.create_annotation_from_ocr_result(result)
                created_count += 1
        QMessageBox.information(self, "创建完成", f"成功创建了 {created_count} 个标注。")
        self.refresh_annotation_list()

    def create_annotation_from_ocr_result(self, ocr_result):
        self.annotation_counter += 1
        position = QPointF(ocr_result['center_x'], ocr_result['center_y'])
        style = OCR_TYPE_TO_STYLE.get(ocr_result['text_type'], 'default')
        annotation_text = f"{ocr_result['text']} (置信度: {ocr_result['confidence']:.2f})"
        shape_map = {"空心圆": "circle", "实心圆": "solid_circle", "五角星": "pentagram", "三角形": "triangle"}
        selected_shape = shape_map.get(self.shape_combo.currentText(), "circle")
        color = self.next_annotation_color
        size = self.next_annotation_size
        
        annotation = BubbleAnnotationItem(
            self.annotation_counter, position, annotation_text, style, selected_shape, color, size
        )
        
        if self.next_annotation_color: self.next_annotation_color = None
        
        annotation.selected.connect(self.on_annotation_selected)
        annotation.moved.connect(self.on_annotation_moved)
        annotation.delete_requested.connect(self.delete_annotation)
        annotation.style_change_requested.connect(self.on_annotation_style_changed)
        annotation.shape_change_requested.connect(self.on_annotation_shape_changed)
        annotation.color_change_requested.connect(self.on_annotation_color_changed)
        annotation.size_change_requested.connect(self.on_annotation_size_changed)
        
        self.graphics_scene.addItem(annotation)
        self.annotations.append(annotation)
        self.annotation_list.add_annotation(annotation)

    def on_annotation_selected(self, annotation: BubbleAnnotationItem):
        for ann in self.annotations: ann.set_highlighted(False)
        self.current_annotation = annotation
        annotation.set_highlighted(True)
        self.property_editor.set_annotation(annotation)
        self.annotation_list.highlight_annotation(annotation.annotation_id)
        
        style_text = "自定义" if annotation.custom_color else STYLE_NAME_MAP.get(annotation.style, "默认")
        self.style_combo.blockSignals(True); self.style_combo.setCurrentText(style_text); self.style_combo.blockSignals(False)
        
        shape_map_rev = {"circle": "空心圆", "solid_circle": "实心圆", "pentagram": "五角星", "triangle": "三角形"}
        shape_text = shape_map_rev.get(annotation.shape_type, "空心圆")
        self.shape_combo.blockSignals(True); self.shape_combo.setCurrentText(shape_text); self.shape_combo.blockSignals(False)

        self.size_slider.blockSignals(True)
        self.size_slider.setValue(annotation.radius)
        self.size_label.setText(str(annotation.radius))
        self.size_slider.blockSignals(False)
        
        self.update_color_button_display()
    
    def on_annotation_moved(self, annotation: BubbleAnnotationItem, position: QPointF):
        if annotation == self.current_annotation: self.property_editor.update_position(position)
    
    def select_annotation_by_id(self, annotation_id: int):
        for annotation in self.annotations:
            if annotation.annotation_id == annotation_id:
                self.graphics_view.centerOn(annotation)
                self.graphics_scene.clearSelection()
                annotation.setSelected(True)
                self.on_annotation_selected(annotation)
                break
    
    def update_annotation_text(self, new_text: str):
        if self.current_annotation:
            self.current_annotation.set_text(new_text)
            self.annotation_list.update_annotation_text(self.current_annotation.annotation_id, new_text)

    def toggle_area_selection(self, checked: bool):
        self.graphics_view.set_selection_mode(checked)
        self.area_select_action.setText("退出区域选择" if checked else "区域标注")
    
    def create_annotation_in_area(self, rect: QRectF):
        if self.is_selecting_mask: return
        self.annotation_counter += 1
        center = rect.center()
        shape_map = {"空心圆": "circle", "实心圆": "solid_circle", "五角星": "pentagram", "三角形": "triangle"}
        selected_shape = shape_map.get(self.shape_combo.currentText(), "circle")
        color = self.next_annotation_color
        size = self.next_annotation_size

        annotation = BubbleAnnotationItem(self.annotation_counter, center, f"区域标注 {self.annotation_counter}", shape=selected_shape, color=color, size=size)
        
        if self.next_annotation_color: self.next_annotation_color = None
        
        annotation.selected.connect(self.on_annotation_selected)
        annotation.moved.connect(self.on_annotation_moved)
        annotation.delete_requested.connect(self.delete_annotation)
        annotation.style_change_requested.connect(self.on_annotation_style_changed)
        annotation.shape_change_requested.connect(self.on_annotation_shape_changed)
        annotation.color_change_requested.connect(self.on_annotation_color_changed)
        annotation.size_change_requested.connect(self.on_annotation_size_changed)

        self.graphics_scene.addItem(annotation)
        self.annotations.append(annotation)
        self.annotation_list.add_annotation(annotation)
        
        self.area_select_action.setChecked(False); self.toggle_area_selection(False)
    
    def delete_annotation(self, annotation: BubbleAnnotationItem):
        if annotation in self.annotations:
            self.graphics_scene.removeItem(annotation)
            self.annotations.remove(annotation)
            self.refresh_annotation_list()
            if self.current_annotation == annotation:
                self.current_annotation = None
                self.property_editor.set_annotation(None)
    
    def refresh_annotation_list(self):
        self.annotation_list.clear_annotations()
        for annotation in self.annotations: self.annotation_list.add_annotation(annotation)
    
    def on_annotation_style_changed(self, annotation: BubbleAnnotationItem):
        if annotation == self.current_annotation: self.on_annotation_selected(annotation)

    def change_current_annotation_style(self, style_text: str):
        if self.current_annotation and style_text != "自定义":
            new_style = STYLE_NAME_REVERSE_MAP.get(style_text, "default")
            self.current_annotation.change_style(new_style)

    def on_annotation_shape_changed(self, annotation: BubbleAnnotationItem):
        if annotation == self.current_annotation: self.on_annotation_selected(annotation)

    def change_current_annotation_shape(self, shape_text: str):
        if self.current_annotation:
            shape_map = {"空心圆": "circle", "实心圆": "solid_circle", "五角星": "pentagram", "三角形": "triangle"}
            new_shape = shape_map.get(shape_text, "circle")
            self.current_annotation.change_shape(new_shape)

    def on_annotation_color_changed(self, annotation: BubbleAnnotationItem):
        if annotation == self.current_annotation:
            self.on_annotation_selected(annotation)

    def select_annotation_color(self):
        initial_color = QColor("blue")
        if self.current_annotation and self.current_annotation.custom_color: initial_color = self.current_annotation.custom_color
        elif self.next_annotation_color: initial_color = self.next_annotation_color
        
        color = QColorDialog.getColor(initial_color, self, "选择标注颜色")

        if color.isValid():
            if self.current_annotation: self.current_annotation.change_color(color)
            else: self.next_annotation_color = color; self.update_color_button_display(); self.status_bar.showMessage(f"下一个标注的颜色已设置为 {color.name()}", 3000)

    def update_color_button_display(self):
        color_to_show = None
        if self.current_annotation and self.current_annotation.custom_color: color_to_show = self.current_annotation.custom_color
        elif self.next_annotation_color: color_to_show = self.next_annotation_color

        if color_to_show and color_to_show.isValid():
            self.color_button.setStyleSheet(f"QPushButton {{ background-color: {color_to_show.name()}; color: {'white' if color_to_show.lightnessF() < 0.5 else 'black'}; border: 1px solid grey; font-weight: bold; }}")
        else: self.color_button.setStyleSheet(""); self.next_annotation_color = None

    def on_annotation_size_changed(self, annotation: BubbleAnnotationItem):
        if annotation == self.current_annotation:
            self.on_annotation_selected(annotation)

    def change_annotation_size(self, size: int):
        self.size_label.setText(str(size))
        if self.current_annotation:
            self.current_annotation.change_size(size)
        else:
            self.next_annotation_size = size
            self.status_bar.showMessage(f"下一个标注的大小已设置为 {size}", 3000)
    
    def clear_annotations(self):
        for annotation in self.annotations[:]:
            if annotation.scene(): self.graphics_scene.removeItem(annotation)
        self.annotations.clear()
        self.annotation_list.clear_annotations()
        self.property_editor.set_annotation(None)

    def toggle_mask_selection(self, checked: bool):
        self.is_selecting_mask = checked
        self.graphics_view.set_selection_mode(checked)
        if hasattr(self, 'mask_select_action'):
            self.mask_select_action.blockSignals(True); self.mask_select_action.setChecked(checked); self.mask_select_action.blockSignals(False)
        if checked and hasattr(self, 'area_select_action'):
            self.area_select_action.blockSignals(True); self.area_select_action.setChecked(False); self.area_select_action.blockSignals(False)
        self.status_bar.showMessage("屏蔽区域选择模式：拖拽鼠标选择要屏蔽的区域" if checked else "已退出屏蔽区域选择模式", 3000 if not checked else 0)
    
    def handle_area_selection(self, rect: QRectF):
        if self.is_selecting_mask: self.add_masked_region(rect)
        else: self.create_annotation_in_area(rect)
    
    def add_masked_region(self, rect: QRectF):
        self.masked_regions.append(rect)
        self.display_masked_region(rect, len(self.masked_regions) - 1)
        self.update_mask_count()
        self.status_bar.showMessage(f"已添加屏蔽区域 {len(self.masked_regions)}", 2000)
    
    def display_masked_region(self, rect: QRectF, index: int):
        from PySide6.QtWidgets import QGraphicsRectItem
        mask_item = QGraphicsRectItem(rect)
        mask_color = QColor(255, 0, 0, 80); border_color = QColor(255, 0, 0, 200)
        mask_item.setPen(QPen(border_color, 2, Qt.DashLine)); mask_item.setBrush(QBrush(mask_color))
        mask_item.mask_region_index = index; mask_item.setZValue(100)
        self.graphics_scene.addItem(mask_item)
    
    def clear_masked_regions(self):
        self.masked_regions.clear()
        items_to_remove = [item for item in self.graphics_scene.items() if hasattr(item, 'mask_region_index')]
        for item in items_to_remove: self.graphics_scene.removeItem(item)
        self.update_mask_count()
        self.status_bar.showMessage("已清除所有屏蔽区域", 2000)
    
    def update_mask_count(self):
        pass
    
    def is_point_in_masked_region(self, x: float, y: float) -> bool:
        point = QPointF(x, y)
        return any(region.contains(point) for region in self.masked_regions)
    
    def is_bbox_in_masked_region(self, bbox) -> bool:
        if not self.masked_regions: return False
        if hasattr(bbox, '__len__') and len(bbox) >= 4:
            if HAS_OCR_SUPPORT: x_min, y_min = np.min(bbox, axis=0); x_max, y_max = np.max(bbox, axis=0)
            else: x_coords,y_coords=[p[0] for p in bbox],[p[1] for p in bbox];x_min,x_max,y_min,y_max=min(x_coords),max(x_coords),min(y_coords),max(y_coords)
            bbox_rect = QRectF(x_min, y_min, x_max - x_min, y_max - y_min)
        else: bbox_rect = bbox
        return any(region.intersects(bbox_rect) for region in self.masked_regions)