#!/usr/bin/env python3
"""
主窗口模块
"""

import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGraphicsScene, QMenuBar, QToolBar, QFileDialog, QMessageBox, 
    QPushButton, QComboBox, QProgressBar, QCheckBox, QSlider, QLabel
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
        self.resize(*DEFAULT_WINDOW_SIZE)
        
        # 添加状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪", 2000)
        
    def setup_ui(self):
        """设置用户界面"""
        self.setGeometry(*DEFAULT_WINDOW_POSITION, *DEFAULT_WINDOW_SIZE)
        
        # 设置窗口样式
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {UI_COLORS["background"]};
            }}
            QSplitter::handle {{
                background-color: {UI_COLORS["border"]};
                width: 3px;
                height: 3px;
            }}
            QSplitter::handle:hover {{
                background-color: #adb5bd;
            }}
            QLabel {{
                font-weight: bold;
                color: {UI_COLORS["text"]};
                padding: 5px;
                background-color: #e9ecef;
                border-bottom: 1px solid {UI_COLORS["border"]};
            }}
            QWidget {{
                font-family: "Microsoft YaHei", "Arial", sans-serif;
                color: {UI_COLORS["text"]};
                background-color: {UI_COLORS["white"]};
            }}
            QPushButton {{
                background-color: {UI_COLORS["white"]};
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px 15px;
                min-height: 20px;
                color: {UI_COLORS["text_secondary"]};
            }}
            QPushButton:hover {{
                background-color: {UI_COLORS["background"]};
                border-color: #6c757d;
                color: {UI_COLORS["text"]};
            }}
            QPushButton:pressed {{
                background-color: #e9ecef;
            }}
            QPushButton:disabled {{
                background-color: #e9ecef;
                color: #6c757d;
                border-color: {UI_COLORS["border"]};
            }}
            QComboBox {{
                background-color: {UI_COLORS["white"]};
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 4px 8px;
                color: {UI_COLORS["text_secondary"]};
            }}
            QComboBox:hover {{
                border-color: #6c757d;
            }}
            QCheckBox {{
                color: {UI_COLORS["text_secondary"]};
            }}
            QSlider::groove:horizontal {{
                background-color: {UI_COLORS["border"]};
                height: 8px;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background-color: #6c757d;
                border: 1px solid {UI_COLORS["text_secondary"]};
                width: 18px;
                border-radius: 9px;
                margin: -5px 0;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {UI_COLORS["text_secondary"]};
            }}
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
        graphics_title.setStyleSheet(f"""
            QLabel {{
                background-color: {UI_COLORS["primary"]};
                color: white;
                font-weight: bold;
                padding: 8px;
                margin: 0px;
                border: none;
            }}
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
        annotation_title.setStyleSheet(f"""
            QLabel {{
                background-color: {UI_COLORS["secondary"]};
                color: white;
                font-weight: bold;
                padding: 8px;
                margin: 0px;
                border: none;
            }}
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
        property_title.setStyleSheet(f"""
            QLabel {{
                background-color: {UI_COLORS["success"]};
                color: white;
                font-weight: bold;
                padding: 8px;
                margin: 0px;
                border: none;
            }}
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
        self.language_combo.addItems(list(DEFAULT_OCR_LANGUAGES.keys()))
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
        self.gpu_checkbox.setChecked(HAS_GPU_SUPPORT)
        self.gpu_checkbox.setEnabled(HAS_GPU_SUPPORT)
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
        self.filter_combo.addItems(OCR_FILTER_OPTIONS)
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
        
        # PDF质量设置
        toolbar.addWidget(QLabel("PDF质量:"))
        self.pdf_quality_combo = QComboBox()
        self.pdf_quality_combo.addItems(list(PDF_QUALITY_OPTIONS.keys()))
        self.pdf_quality_combo.setCurrentText("高清 (4x)")
        self.pdf_quality_combo.setToolTip(
            "选择PDF渲染质量:\n"
            "• 标准 (2x) - 快速加载，适合预览\n"
            "• 高清 (4x) - 推荐设置，平衡质量和速度\n"
            "• 超清 (6x) - 高质量，适合详细分析\n"
            "• 极清 (8x) - 最高质量，加载较慢\n\n"
            "注意：质量越高，文件加载越慢但图像越清晰"
        )
        toolbar.addWidget(self.pdf_quality_combo)
        
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
        self.style_combo.addItems(list(STYLE_NAME_MAP.values()))
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
        file_dialog.setNameFilter(FILE_DIALOG_FILTER)
        
        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            if file_paths:
                self.load_file(file_paths[0])
    
    def load_file(self, file_path: str):
        """加载文件"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        # 显示加载状态
        self.status_bar.showMessage(f"正在加载文件: {file_path.name}...")
        
        # 清除现有内容
        self.graphics_scene.clear()
        self.clear_annotations()
        self.clear_ocr_results()
        
        try:
            if extension in SUPPORTED_IMAGE_FORMATS:
                pixmap = FileLoader.load_image(str(file_path))
                if pixmap:
                    self.graphics_scene.addPixmap(pixmap)
                    self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(),
                                               Qt.KeepAspectRatio)
                    # 设置当前文件路径
                    self.current_file_path = str(file_path)
                    self.status_bar.showMessage(f"✅ 图像文件加载成功: {file_path.name} ({pixmap.width()}x{pixmap.height()})", 5000)
                else:
                    QMessageBox.warning(self, "错误", "无法加载图像文件")
                    self.status_bar.showMessage("❌ 图像文件加载失败", 3000)
                    return
                    
            elif extension in SUPPORTED_PDF_FORMATS:
                # 获取用户选择的PDF质量设置
                zoom_factor = PDF_QUALITY_OPTIONS.get(self.pdf_quality_combo.currentText(), 4.0)
                
                self.status_bar.showMessage(f"正在以 {self.pdf_quality_combo.currentText()} 质量加载PDF...")
                
                pixmap = FileLoader.load_pdf(str(file_path), zoom_factor=zoom_factor)
                if pixmap:
                    self.graphics_scene.addPixmap(pixmap)
                    self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(),
                                               Qt.KeepAspectRatio)
                    # 设置当前文件路径
                    self.current_file_path = str(file_path)
                    self.status_bar.showMessage(f"✅ PDF文件加载成功: {file_path.name} ({pixmap.width()}x{pixmap.height()}, {self.pdf_quality_combo.currentText()})", 5000)
                else:
                    QMessageBox.warning(self, "错误", "无法加载PDF文件")
                    self.status_bar.showMessage("❌ PDF文件加载失败", 3000)
                    return
                    
            elif extension in SUPPORTED_DXF_FORMATS:
                FileLoader.load_dxf(str(file_path), self.graphics_scene)
                self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(),
                                           Qt.KeepAspectRatio)
                # DXF文件不支持OCR，提示用户
                self.current_file_path = None
                self.status_bar.showMessage(f"✅ DXF文件加载成功: {file_path.name} (不支持OCR)", 5000)
                QMessageBox.information(self, "提示", "DXF文件已加载，但不支持OCR文字识别功能")
                
            elif extension == '.dwg':
                QMessageBox.information(self, "提示", "暂不支持DWG格式文件")
                self.status_bar.showMessage("❌ 不支持DWG格式", 3000)
                return
                
            else:
                QMessageBox.warning(self, "错误", f"不支持的文件格式: {extension}")
                self.status_bar.showMessage(f"❌ 不支持的文件格式: {extension}", 3000)
                return
                
            # 启用OCR按钮（仅对图像和PDF文件）
            self.ocr_button.setEnabled(self.current_file_path is not None)
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件时发生错误: {str(e)}")
            self.status_bar.showMessage(f"❌ 加载文件失败: {str(e)}", 5000)
            self.current_file_path = None

    def simulate_ai_recognition(self):
        """启动OCR识别（替换原有的模拟方法）"""
        self.start_ocr_recognition()

    def start_ocr_recognition(self):
        """开始OCR识别"""
        if not HAS_OCR_SUPPORT:
            QMessageBox.warning(self, "功能不可用", get_requirements_message())
            return
            
        if not self.current_file_path:
            QMessageBox.warning(self, "警告", "请先加载图纸文件!")
            return
        
        # 获取语言设置
        selected_languages = DEFAULT_OCR_LANGUAGES[self.language_combo.currentText()]
        
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
        if not HAS_OCR_SUPPORT:
            return
            
        bbox = ocr_result['bbox']
        bbox_array = np.array(bbox)
        
        # 创建边界框画路径
        path = QPainterPath()
        path.moveTo(bbox_array[0][0], bbox_array[0][1])
        for point in bbox_array[1:]:
            path.lineTo(point[0], point[1])
        path.closeSubpath()
        
        # 创建图形项
        from PySide6.QtWidgets import QGraphicsPathItem
        bbox_item = QGraphicsPathItem(path)
        
        # 根据文本类型设置不同颜色
        text_type = ocr_result['text_type']
        color = QColor(*OCR_TEXT_TYPE_COLORS.get(text_type, OCR_TEXT_TYPE_COLORS['annotation']))
        
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
            target_type = OCR_FILTER_TYPE_MAP.get(filter_type, "annotation")
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
        style = OCR_TYPE_TO_STYLE.get(ocr_result['text_type'], 'default')
        
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
        style_text = STYLE_NAME_MAP.get(annotation.style, "默认")
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
            style_text = STYLE_NAME_MAP.get(annotation.style, "默认")
            self.style_combo.blockSignals(True)
            self.style_combo.setCurrentText(style_text)
            self.style_combo.blockSignals(False)
    
    def change_current_annotation_style(self, style_text: str):
        """更改当前标注的样式"""
        if self.current_annotation:
            new_style = STYLE_NAME_REVERSE_MAP.get(style_text, "default")
            self.current_annotation.change_style(new_style)

    def clear_annotations(self):
        """清除所有标注"""
        for annotation in self.annotations[:]:  # 使用切片复制避免修改过程中列表变化
            if annotation.scene():
                self.graphics_scene.removeItem(annotation)
        
        self.annotations.clear()
        self.annotation_list.clear_annotations()
        self.property_editor.set_annotation(None) 