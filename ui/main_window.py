# ui/main_window.py

import sys
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any, Union
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGraphicsScene, QMenuBar, QToolBar, QFileDialog, QMessageBox, 
    QPushButton, QComboBox, QProgressBar, QCheckBox, QSlider, QLabel, QColorDialog, QSpinBox,
    QDialog, QListWidget, QListWidgetItem, QInputDialog
)
from PySide6.QtCore import Qt, QRectF, QPointF, QThreadPool, Signal, Slot, QSettings, QTimer
from PySide6.QtGui import (
    QPainter, QPixmap, QImage, QColor, QPen, QBrush, QPainterPath, 
    QAction, QKeySequence
)
from PySide6.QtWidgets import QApplication

# 导入自定义模块
from utils.constants import (
    APP_TITLE, FILE_DIALOG_FILTER, DEFAULT_WINDOW_SIZE, DEFAULT_WINDOW_POSITION,
    DEFAULT_OCR_LANGUAGES, PDF_QUALITY_OPTIONS, OCR_TEXT_TYPE_COLORS,
    OCR_TYPE_TO_STYLE, STYLE_NAME_MAP, STYLE_NAME_REVERSE_MAP,
    OCR_FILTER_OPTIONS, OCR_FILTER_TYPE_MAP, UI_COLORS, SUPPORTED_IMAGE_FORMATS,
    SUPPORTED_PDF_FORMATS, SUPPORTED_DXF_FORMATS,
    BUBBLE_SIZE_MIN_PERCENT, BUBBLE_SIZE_MAX_PERCENT, BUBBLE_SIZE_DEFAULT_PERCENT, BUBBLE_SIZE_STEP,
    BUBBLE_REORDER_GRID_SIZE
)
from utils.dependencies import HAS_OCR_SUPPORT, HAS_GPU_SUPPORT, HAS_PADDLE_OCR, get_requirements_message

# 只导入PaddleOCR工作器
if HAS_PADDLE_OCR:
    from core.paddle_ocr_worker import PaddleOCRWorker
from core.annotation_item import BubbleAnnotationItem
from core.file_loader import FileLoader

from ui.graphics_view import GraphicsView
from ui.annotation_list import AnnotationTable
from ui.property_editor import PropertyEditor

# 移除OCR框项导入

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment
    import pandas as pd
    HAS_EXCEL_SUPPORT = True
except ImportError:
    HAS_EXCEL_SUPPORT = False

if HAS_OCR_SUPPORT:
    import numpy as np

# 导入我们的命令类
# from core.undo_commands import (
#     AddAnnotationCommand, DeleteAnnotationCommand, MoveAnnotationCommand,
#     EditAnnotationTextCommand, EditAnnotationStyleCommand, EditAnnotationShapeCommand,
#     EditAnnotationColorCommand, EditAnnotationSizeCommand, ClearAnnotationsCommand
# )

class MainWindow(QMainWindow):
    """
    主窗口类
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.annotations: List[BubbleAnnotationItem] = []
        self.annotation_counter = 0
        self.current_file_path: Optional[str] = None
        self.current_pixmap: Optional[QPixmap] = None
        self.ocr_results: List[dict] = []
        self.thread_pool = QThreadPool()
        self.current_annotation: Optional[BubbleAnnotationItem] = None
        
        self.next_annotation_color: Optional[QColor] = None
        self.next_annotation_size: int = -1  # -1表示自动大小
        self.next_annotation_scale: float = 1.0  # 默认比例为100%
        
        self.masked_regions: List[QRectF] = []
        self.is_selecting_mask = False
        
        # 添加多页PDF相关属性
        self.pdf_file_path: Optional[str] = None  # 原始PDF文件路径
        self.pdf_page_count: int = 0  # PDF总页数
        self.current_pdf_page: int = 0  # 当前显示页码 (0-indexed)
        self.pdf_pages_cache: Dict[int, str] = {}  # 缓存已经转换的PDF页面 {页码: 临时文件路径}
        self.annotations_by_page: Dict[int, List[BubbleAnnotationItem]] = {}  # 每页的标注 {页码: 标注列表}
        self.ocr_results_by_page: Dict[int, List[dict]] = {}  # 每页的OCR结果 {页码: OCR结果列表}
        
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
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget); layout.setContentsMargins(5, 5, 5, 5); layout.setSpacing(5)
        main_splitter = QSplitter(Qt.Horizontal); layout.addWidget(main_splitter)
        left_splitter = QSplitter(Qt.Vertical)
        graphics_panel = QWidget(); graphics_layout = QVBoxLayout(graphics_panel); graphics_layout.setContentsMargins(0, 0, 0, 0); graphics_layout.setSpacing(0)
        graphics_title = QLabel("图纸视图 & OCR识别"); graphics_title.setStyleSheet(f"QLabel {{ background-color: {UI_COLORS['primary']}; color: white; font-weight: bold; padding: 8px; margin: 0px; border: none; }}"); graphics_layout.addWidget(graphics_title)
        self.setup_compact_ocr_panel(graphics_layout)
        self.graphics_view = GraphicsView(); self.graphics_scene = QGraphicsScene(); self.graphics_view.setScene(self.graphics_scene); graphics_layout.addWidget(self.graphics_view)
        
        # --- 修改：移除旧的审核按钮布局 ---
        annotation_panel = QWidget()
        annotation_layout = QVBoxLayout(annotation_panel)
        annotation_layout.setContentsMargins(0, 0, 0, 0); annotation_layout.setSpacing(0)
        annotation_title = QLabel("标注列表"); annotation_title.setStyleSheet(f"QLabel {{ background-color: {UI_COLORS['secondary']}; color: white; font-weight: bold; padding: 8px; margin: 0px; border: none; }}"); annotation_layout.addWidget(annotation_title)
        self.annotation_table = AnnotationTable(); annotation_layout.addWidget(self.annotation_table)
        
        left_splitter.addWidget(graphics_panel); left_splitter.addWidget(annotation_panel)
        left_splitter.setStretchFactor(0, 3); left_splitter.setStretchFactor(1, 1)
        
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel); right_layout.setContentsMargins(0, 0, 0, 0); right_layout.setSpacing(0)
        property_title = QLabel("属性编辑器"); property_title.setStyleSheet(f"QLabel {{ background-color: {UI_COLORS['success']}; color: white; font-weight: bold; padding: 8px; margin: 0px; border: none; }}"); right_layout.addWidget(property_title)
        self.property_editor = PropertyEditor(self); right_layout.addWidget(self.property_editor)
        main_splitter.addWidget(left_splitter); main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 3); main_splitter.setStretchFactor(1, 1)

        # 创建状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪", 2000)
        
        # 为状态栏创建PDF导航控件
        self.setup_pdf_navigation_controls()
        
    def setup_pdf_navigation_controls(self):
        """设置PDF导航控件（放在状态栏右侧）"""
        # 创建一个小部件来容纳导航控件
        self.pdf_nav_widget = QWidget()
        self.pdf_nav_layout = QHBoxLayout(self.pdf_nav_widget)
        self.pdf_nav_layout.setContentsMargins(0, 0, 5, 0)
        self.pdf_nav_layout.setSpacing(5)
        
        # 创建导航按钮和标签
        self.prev_page_btn = QPushButton("◀ 上一页")
        self.prev_page_btn.setMaximumWidth(80)
        self.prev_page_btn.setToolTip("显示上一页 (快捷键: 左方向键)")
        self.prev_page_btn.setEnabled(False)
        self.prev_page_btn.clicked.connect(self.go_to_prev_page)
        self.pdf_nav_layout.addWidget(self.prev_page_btn)
        
        self.page_label = QLabel("页码: 0 / 0")
        self.page_label.setFixedWidth(80)
        self.page_label.setAlignment(Qt.AlignCenter)
        self.pdf_nav_layout.addWidget(self.page_label)
        
        self.next_page_btn = QPushButton("下一页 ▶")
        self.next_page_btn.setMaximumWidth(80)
        self.next_page_btn.setToolTip("显示下一页 (快捷键: 右方向键)")
        self.next_page_btn.setEnabled(False)
        self.next_page_btn.clicked.connect(self.go_to_next_page)
        self.pdf_nav_layout.addWidget(self.next_page_btn)
        
        self.go_to_page_btn = QPushButton("前往...")
        self.go_to_page_btn.setMaximumWidth(60)
        self.go_to_page_btn.setToolTip("跳转到指定页面")
        self.go_to_page_btn.setEnabled(False)
        self.go_to_page_btn.clicked.connect(self.show_go_to_page_dialog)
        self.pdf_nav_layout.addWidget(self.go_to_page_btn)
        
        # 将导航小部件添加到状态栏右侧
        self.status_bar.addPermanentWidget(self.pdf_nav_widget)
        
        # 默认隐藏导航控件
        self.pdf_nav_widget.setVisible(False)
        
    def setup_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开...", self); open_action.setShortcut("Ctrl+O"); open_action.triggered.connect(self.open_file); file_menu.addAction(open_action)
        
        # 添加PDF转换功能
        convert_pdf_action = QAction("PDF转换为PNG...", self); convert_pdf_action.triggered.connect(self.convert_pdf_to_images); file_menu.addAction(convert_pdf_action)
        
        if HAS_EXCEL_SUPPORT:
            export_action = QAction("导出为Excel...", self); export_action.setShortcut("Ctrl+E"); export_action.triggered.connect(self.export_to_excel); file_menu.addAction(export_action)
        file_menu.addSeparator()
        
        # --- 新增：创建全局快捷键动作 ---
        self.audit_action = QAction("审核", self)
        self.audit_action.setShortcut(QKeySequence("F2"))
        self.audit_action.triggered.connect(self.audit_current_annotation)
        self.addAction(self.audit_action) # 添加到主窗口，使其全局有效
        # -----------------------------

        exit_action = QAction("退出", self); exit_action.setShortcut("Ctrl+Q"); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
    
    def setup_toolbar(self):
        toolbar = self.addToolBar("主工具栏")
        open_action = QAction("打开文件", self); open_action.triggered.connect(self.open_file); toolbar.addAction(open_action)
        if HAS_EXCEL_SUPPORT:
            export_btn = QPushButton("导出Excel"); export_btn.setToolTip("将当前标注列表导出为Excel文件"); export_btn.clicked.connect(self.export_to_excel); toolbar.addWidget(export_btn)
        
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("PDF质量:")); self.pdf_quality_combo = QComboBox(); self.pdf_quality_combo.addItems(list(PDF_QUALITY_OPTIONS.keys())); self.pdf_quality_combo.setCurrentText("高清 (4x)"); self.pdf_quality_combo.setToolTip("渲染PDF时的清晰度，越高越清晰但加载越慢"); toolbar.addWidget(self.pdf_quality_combo)
        
        toolbar.addSeparator()
        ai_recognize_action = QAction("AI识别", self); ai_recognize_action.triggered.connect(self.simulate_ai_recognition); toolbar.addAction(ai_recognize_action)
        self.area_select_action = QAction("区域OCR标注", self); self.area_select_action.setCheckable(True); self.area_select_action.setShortcut("Q"); self.area_select_action.setStatusTip("激活后，在图纸上拖拽鼠标以框选区域进行OCR识别"); self.area_select_action.toggled.connect(self.toggle_area_selection); toolbar.addAction(self.area_select_action)
        self.mask_select_action = QAction("🚫 屏蔽区域", self); self.mask_select_action.setCheckable(True); self.mask_select_action.setStatusTip("激活后，在图纸上拖拽鼠标以选择要忽略OCR的区域"); self.mask_select_action.toggled.connect(self.toggle_mask_selection); toolbar.addAction(self.mask_select_action)
        toolbar.addSeparator()
        # 添加重新排序按钮
        reorder_action = QAction("🔄 重新排序", self)
        reorder_action.setToolTip("重新给所有气泡标注排序编号(从左到右，从上到下)")
        reorder_action.triggered.connect(self.reorder_annotations)
        toolbar.addAction(reorder_action)
        clear_action = QAction("清除标注", self); clear_action.triggered.connect(self.clear_annotations); toolbar.addAction(clear_action)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("气泡大小:")); 
        # 使用常量定义比例滑块参数
        self.size_slider = QSlider(Qt.Horizontal)
        # 使用常量定义，但强制转换为整数类型
        self.size_slider.setRange(int(BUBBLE_SIZE_MIN_PERCENT), int(BUBBLE_SIZE_MAX_PERCENT))
        self.size_slider.setSingleStep(int(BUBBLE_SIZE_STEP))
        self.size_slider.setPageStep(int(BUBBLE_SIZE_STEP * 2))
        self.size_slider.setTickPosition(QSlider.TicksBelow)
        self.size_slider.setTickInterval(int(BUBBLE_SIZE_STEP*2))
        # 设置默认值
        self.size_slider.setValue(int(BUBBLE_SIZE_DEFAULT_PERCENT))
        # 调试信息
        print(f"滑块初始设置: 范围{BUBBLE_SIZE_MIN_PERCENT}-{BUBBLE_SIZE_MAX_PERCENT}, 步长{BUBBLE_SIZE_STEP}, 当前值{BUBBLE_SIZE_DEFAULT_PERCENT}")
        self.size_slider.setFixedWidth(120)  # 增加宽度，使滑块更容易拖动
        # 显示比例而不是绝对值
        self.size_label = QLabel(f"{BUBBLE_SIZE_DEFAULT_PERCENT}%")
        self.size_label.setFixedWidth(40)
        toolbar.addWidget(self.size_slider)
        toolbar.addWidget(self.size_label)
        toolbar.addSeparator()
        self.color_button = QPushButton("颜色"); self.color_button.setToolTip("选择下一个标注的颜色，或修改当前选中标注的颜色"); self.color_button.clicked.connect(self.select_annotation_color); toolbar.addWidget(self.color_button)
        toolbar.addWidget(QLabel("形状:")); self.shape_combo = QComboBox(); self.shape_combo.addItems(["空心圆", "实心圆", "五角星", "三角形"]); toolbar.addWidget(self.shape_combo)
        toolbar.addWidget(QLabel("快速样式:")); self.style_combo = QComboBox(); self.style_combo.addItems(["自定义"] + list(STYLE_NAME_MAP.values())); toolbar.addWidget(self.style_combo)
    
    def setup_connections(self):
        self.annotation_table.annotation_selected.connect(self.select_annotation_by_id)
        self.graphics_view.area_selected.connect(self.handle_area_selection)
        self.size_slider.valueChanged.connect(self.change_annotation_size)
        self.shape_combo.currentTextChanged.connect(self.change_current_annotation_shape)
        self.style_combo.currentTextChanged.connect(self.change_current_annotation_style)
        self.confidence_slider.valueChanged.connect(lambda v: self.confidence_label.setText(f"{v/100:.2f}"))
        self.ocr_button.clicked.connect(self.start_ocr_recognition)
        self.create_all_btn.clicked.connect(self.create_annotations_from_ocr)
        self.clear_ocr_btn.clicked.connect(self.clear_ocr_results)
        self.filter_combo.currentTextChanged.connect(self.filter_ocr_results)
        # --- 新增连接：连接新按钮的信号 ---
        self.property_editor.audit_requested.connect(self.audit_current_annotation)
        self.property_editor.delete_requested.connect(self.delete_current_annotation)
        
        # GPU和CPU选项互斥
        self.gpu_checkbox.toggled.connect(self.on_gpu_checkbox_toggled)
        self.cpu_checkbox.toggled.connect(self.on_cpu_checkbox_toggled)
        
        # 添加PDF导航快捷键
        self.left_action = QAction("左方向键", self)
        self.left_action.setShortcut("Left")
        self.left_action.triggered.connect(self.go_to_prev_page)
        self.addAction(self.left_action)
        
        self.right_action = QAction("右方向键", self)
        self.right_action.setShortcut("Right")
        self.right_action.triggered.connect(self.go_to_next_page)
        self.addAction(self.right_action)

    def keyPressEvent(self, event):
        """处理键盘事件"""
        # 处理方向键事件（如果有PDF打开）
        if self.pdf_file_path:
            if event.key() == Qt.Key_Left:
                self.go_to_prev_page()
                return
            elif event.key() == Qt.Key_Right:
                self.go_to_next_page()
                return
        
        super().keyPressEvent(event)

    def audit_current_annotation(self):
        if not self.current_annotation:
            # 如果没有选中的，尝试选中第一个未审核的
            sorted_annotations = sorted(self.annotations, key=lambda ann: ann.annotation_id)
            first_unaudited = next((ann for ann in sorted_annotations if not ann.is_audited), None)
            if first_unaudited:
                self.select_annotation_by_id(first_unaudited.annotation_id)
            else:
                QMessageBox.warning(self, "提示", "没有需要审核的标注。")
            return

        # 1. 审核当前项
        self.current_annotation.set_audited(True)

        # 2. 寻找下一个未审核项
        sorted_annotations = sorted(self.annotations, key=lambda ann: ann.annotation_id)
        current_index = -1
        for i, ann in enumerate(sorted_annotations):
            if ann.annotation_id == self.current_annotation.annotation_id:
                current_index = i
                break

        next_annotation_to_select = None
        
        # 从当前项之后开始寻找
        if current_index != -1:
            for i in range(current_index + 1, len(sorted_annotations)):
                if not sorted_annotations[i].is_audited:
                    next_annotation_to_select = sorted_annotations[i]
                    break
        
        # 如果后面没有，就从头开始找
        if not next_annotation_to_select:
            for ann in sorted_annotations:
                if not ann.is_audited:
                    next_annotation_to_select = ann
                    break
        
        # 3. 跳转
        if next_annotation_to_select:
            self.select_annotation_by_id(next_annotation_to_select.annotation_id)
        else:
            QMessageBox.information(self, "审核完成", "所有标注均已审核！")

    def export_to_excel(self):
        if not HAS_EXCEL_SUPPORT:
            QMessageBox.warning(self, "功能缺失", "缺少 'openpyxl' 库，无法导出Excel。\n请运行: pip install openpyxl"); return
        if not self.annotations:
            QMessageBox.information(self, "提示", "标注列表为空，无需导出。"); return
        
        default_filename = f"{Path(self.current_file_path).stem}_标注列表.xlsx" if self.current_file_path else "标注列表.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为Excel文件", default_filename, "Excel 文件 (*.xlsx)")
        
        if not file_path: return
        
        try:
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "标注数据"
            headers = [self.annotation_table.horizontalHeaderItem(i).text() for i in range(self.annotation_table.columnCount())]
            ws.append(headers)
            
            header_font = Font(bold=True)
            for cell in ws[1]: 
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            for ann in self.annotations:
                row_data = [
                    str(ann.annotation_id),
                    ann.dimension_type,
                    ann.dimension,
                    ann.upper_tolerance,
                    ann.lower_tolerance,
                    "是" if ann.is_audited else "否"
                ]
                ws.append(row_data)

            for col_idx, column in enumerate(ws.columns):
                max_length = 0
                column_letter = openpyxl.utils.get_column_letter(col_idx + 1)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = max(max_length + 2, len(headers[col_idx]) + 2)
                ws.column_dimensions[column_letter].width = adjusted_width if adjusted_width < 50 else 50
            ws.column_dimensions[openpyxl.utils.get_column_letter(6)].width = 10


            wb.save(file_path)
            QMessageBox.information(self, "导出成功", f"标注列表已成功导出到:\n{file_path}")
            self.status_bar.showMessage(f"成功导出到 {Path(file_path).name}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出到Excel时发生错误:\n{e}")
            self.status_bar.showMessage("导出失败", 3000)

    def open_file(self):
        file_dialog = QFileDialog(self); file_dialog.setNameFilter(FILE_DIALOG_FILTER)
        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            if file_paths: self.load_file(file_paths[0])
    
    def load_file(self, file_path: str):
        """加载文件"""
        file_path_obj = Path(file_path); extension = file_path_obj.suffix.lower()
        self.status_bar.showMessage(f"正在加载文件: {file_path_obj.name}...")
        
        # 检查文件路径是否包含中文或特殊字符
        has_non_ascii = any(ord(c) > 127 for c in file_path)
        if has_non_ascii:
            print(f"警告: 文件路径包含非ASCII字符，可能导致兼容性问题: {file_path}")
        
        # 清除现有内容 - 重要：先清空self.annotations列表，再清场景
        self.annotations = []  # 直接清空标注列表，避免引用已删除的对象
        self.graphics_scene.clear()  # 清除场景会删除所有图形项
        self.clear_ocr_results()
        self.clear_masked_regions()
        self.current_pixmap = None
        self.current_annotation = None
        self.property_editor.set_annotation(None, None, None)
        self.annotation_table.clear_annotations()
        self.annotation_counter = 0  # 重置标注计数器
        
        # 重置PDF相关属性
        self.pdf_file_path = None
        self.pdf_page_count = 0
        self.current_pdf_page = 0
        self.pdf_pages_cache.clear()
        self.annotations_by_page.clear()
        self.ocr_results_by_page.clear()
        self.pdf_nav_widget.setVisible(False)
        
        try:
            pixmap = None
            if extension in SUPPORTED_IMAGE_FORMATS:
                pixmap = FileLoader.load_image(str(file_path))
                if pixmap: self.current_file_path = str(file_path)
            elif extension in SUPPORTED_PDF_FORMATS:
                # 获取PDF页数
                page_count = FileLoader.get_pdf_page_count(str(file_path))
                if page_count == 0:
                    QMessageBox.warning(self, "错误", "无法读取PDF文件或PDF文件不包含任何页面")
                    self.status_bar.clearMessage()
                    return
                
                # 设置PDF相关属性
                self.pdf_file_path = str(file_path)
                self.pdf_page_count = page_count
                self.current_pdf_page = 0  # 从第一页开始
                
                # 如果是多页PDF，显示导航控件
                if page_count > 1:
                    self.update_pdf_navigation_controls()
                    
                    # 显示提示消息
                    QMessageBox.information(
                        self, 
                        "多页PDF", 
                        f"检测到多页PDF文件，共 {page_count} 页。\n您可以使用右下角导航控件或键盘方向键切换页面。"
                    )
                
                # 加载第一页
                self.load_pdf_page(0)
                return  # 已经完成加载，直接返回
                
            elif extension in SUPPORTED_DXF_FORMATS:
                FileLoader.load_dxf(str(file_path), self.graphics_scene)
                self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                self.current_file_path = None
                self.status_bar.showMessage(f"✅ DXF文件加载成功: {file_path_obj.name} (不支持OCR)", 5000)
                QMessageBox.information(self, "提示", "DXF文件已加载，但不支持OCR文字识别功能")
            else:
                QMessageBox.warning(self, "错误", f"不支持的文件格式: {extension}")
                self.status_bar.showMessage(f"❌ 不支持的文件格式: {extension}", 3000); return
            
            if pixmap:
                self.current_pixmap = pixmap
                if extension not in SUPPORTED_PDF_FORMATS:  # PDF已经在load_pdf中添加到scene了
                    self.graphics_scene.addPixmap(pixmap)
                
                # 确保图像居中显示
                QTimer.singleShot(100, lambda: self.center_view())
                
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
        """启动OCR识别过程"""
        if not HAS_OCR_SUPPORT:
            QMessageBox.warning(self, "功能缺失", "OCR功能需要PaddleOCR和依赖包。请安装所需依赖。")
            return
        
        if not self.current_pixmap:
            QMessageBox.information(self, "提示", "请先打开图片文件。")
            return
            
        # 保存已有的OCR结果，而不是清除
        existing_results = self.ocr_results.copy()
        # 只清除显示，不清除结果数据
        self.clear_ocr_display()
        
        # 获取语言配置
        lang_text = self.language_combo.currentText()
        lang_code = DEFAULT_OCR_LANGUAGES.get(lang_text, ["ch_sim"])
        
        # 获取环境配置
        force_cpu = self.cpu_checkbox.isChecked()
        use_gpu = self.gpu_checkbox.isChecked() and not force_cpu
        
        # 获取CPU线程数
        cpu_threads = self.threads_spinbox.value()
        
        # 显示设备模式
        device_mode = "CPU" if force_cpu else ("GPU" if use_gpu else "自动")
        self.status_bar.showMessage(f"正在进行OCR文本识别... (使用{device_mode}模式)")
        
        # 获取屏蔽区域数据
        masked_regions_data = [{'x': r.x(), 'y': r.y(), 'width': r.width(), 'height': r.height()} for r in self.masked_regions]
        
        # 创建OCR工作器
        self.ocr_worker = PaddleOCRWorker(
            self.current_file_path, 
            lang_code, 
            masked_regions_data,
            force_cpu=force_cpu,
            cpu_threads=cpu_threads  # 传递线程数
        )
        
        # 连接信号
        self.ocr_worker.signals.progress.connect(self.on_ocr_progress)
        self.ocr_worker.signals.error.connect(self.on_ocr_error)
        
        # 修改on_ocr_finished连接，合并现有结果
        self.ocr_worker.signals.finished.connect(
            lambda results: self.on_ocr_finished(results, existing_results)
        )
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动线程
        self.thread_pool.start(self.ocr_worker)

    def on_ocr_progress(self, progress: int):
        self.progress_bar.setValue(progress)

    def on_ocr_error(self, error_msg: str):
        self.ocr_button.setEnabled(True); self.ocr_button.setText("🔍 开始OCR识别")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "OCR识别错误", error_msg)

    def on_ocr_finished(self, results: List[dict], existing_results: List[dict] = None):
        self.ocr_button.setEnabled(True); self.ocr_button.setText("🔍 开始OCR识别")
        self.progress_bar.setVisible(False)
        if self.is_selecting_mask: self.toggle_mask_selection(False)
        
        # 合并现有的OCR结果和新的结果
        if existing_results:
            # 创建一个集合来检查重复项
            existing_boxes = set()
            for r in existing_results:
                if 'bbox' in r:
                    # 将bbox转换为可哈希格式以检查重复
                    bbox_tuple = tuple(tuple(point) for point in r['bbox'])
                    existing_boxes.add(bbox_tuple)
            
            # 过滤掉重叠的新结果
            new_results = []
            for r in results:
                if 'bbox' in r:
                    bbox_tuple = tuple(tuple(point) for point in r['bbox'])
                    if bbox_tuple not in existing_boxes:
                        new_results.append(r)
                else:
                    new_results.append(r)
            
            # 合并结果
            self.ocr_results = existing_results + new_results
        else:
            self.ocr_results = results
        
        # 如果是多页PDF，保存当前页的OCR结果
        if self.pdf_file_path and self.current_pdf_page in range(self.pdf_page_count):
            self.ocr_results_by_page[self.current_pdf_page] = self.ocr_results.copy()
            
        self.update_ocr_stats()
        self.display_ocr_results()
        
        # 显示带有时间信息的完成消息
        message = f"成功识别出 {len(results)} 个文本区域。\n您可以选择创建标注或进一步筛选结果。"
        
        # 添加文件名
        if self.current_file_path:
            message += f"\n\n文件: {Path(self.current_file_path).name}"
        
        # 添加日期时间
        now = datetime.now()
        message += f"\n完成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
        
        QMessageBox.information(self, "OCR识别完成", message)

    def update_ocr_stats(self):
        total_count = len(self.ocr_results)
        type_counts = {}
        for result in self.ocr_results: 
            result_type = result.get('type', 'unknown')
            type_counts[result_type] = type_counts.get(result_type, 0) + 1
        stats_text = f"识别结果: {total_count}个文本"
        if type_counts: 
            stats_text += f" ({', '.join([f'{k}({v})' for k, v in type_counts.items()])})"
        self.ocr_stats_label.setText(stats_text)

    def display_ocr_results(self):
        self.clear_ocr_display()
        for i, result in enumerate(self.ocr_results): 
            self.create_ocr_bbox_item(result, i)

    def create_ocr_bbox_item(self, ocr_result, index):
        if not HAS_OCR_SUPPORT: return
        bbox = ocr_result['bbox']
        
        bbox_array = np.array(bbox)
        path = QPainterPath()
        path.moveTo(bbox_array[0][0], bbox_array[0][1])
        for point in bbox_array[1:]: 
            path.lineTo(point[0], point[1])
        path.closeSubpath()
        from PySide6.QtWidgets import QGraphicsPathItem
        bbox_item = QGraphicsPathItem(path)
        text_type = ocr_result.get('type', 'annotation')
        color = QColor(*OCR_TEXT_TYPE_COLORS.get(text_type, OCR_TEXT_TYPE_COLORS['annotation']))
        color.setAlpha(80)  # 设置透明度
        bbox_item.setPen(QPen(color, 2))
        bbox_item.setBrush(QBrush(color))
        
        # 设置自定义属性以便识别
        bbox_item.setData(Qt.UserRole, 10000 + index)  # 使用10000+索引作为标识
        bbox_item.setData(Qt.UserRole + 1, ocr_result)  # 存储OCR结果
        
        self.graphics_scene.addItem(bbox_item)
        return bbox_item

    def clear_ocr_display(self):
        """清除OCR结果的可视化显示"""
        try:
            # 找出所有OCR边界框项目并移除
            bbox_items = []
            for item in self.graphics_scene.items():
                # 检查是否为OCR边界框类型的项目
                if item.data(Qt.UserRole) is not None and isinstance(item.data(Qt.UserRole), int) and item.data(Qt.UserRole) >= 10000:
                    bbox_items.append(item)
            
            # 从场景中删除找到的边界框项目
            for item in bbox_items:
                try:
                    self.graphics_scene.removeItem(item)
                except Exception as e:
                    print(f"移除OCR边界框时出错: {e}")
        except Exception as e:
            print(f"清除OCR显示时出错: {e}")

    def clear_ocr_results(self):
        """清除OCR结果"""
        try:
            self.clear_ocr_display()
            self.ocr_results = []
            
            # 如果是多页PDF，清除当前页的OCR结果缓存
            if self.pdf_file_path and self.current_pdf_page in range(self.pdf_page_count):
                if self.current_pdf_page in self.ocr_results_by_page:
                    self.ocr_results_by_page[self.current_pdf_page] = []
                    
            self.update_ocr_stats()
        except Exception as e:
            print(f"清除OCR结果时出错: {e}")
            # 确保OCR结果被清空
            self.ocr_results = []

    def filter_ocr_results(self):
        """筛选OCR结果，仅显示符合条件的结果"""
        try:
            # 获取筛选条件
            filter_type = self.filter_combo.currentText()
            
            # 根据筛选条件获取结果
            if filter_type == "全部": 
                filtered_results = self.ocr_results
            else:
                target_type = OCR_FILTER_TYPE_MAP.get(filter_type, "annotation")
                filtered_results = [r for r in self.ocr_results if r.get('type', 'annotation') == target_type]
            
            # 清除当前OCR显示
            self.clear_ocr_display()
            
            # 显示过滤后的结果
            for i, result in enumerate(filtered_results):
                if result in self.ocr_results:
                    original_index = self.ocr_results.index(result)
                    self.create_ocr_bbox_item(result, original_index)
                    
            # 更新状态
            self.status_bar.showMessage(f"筛选后显示 {len(filtered_results)}/{len(self.ocr_results)} 个OCR结果", 3000)
        except Exception as e:
            print(f"筛选OCR结果时出错: {e}")
            # 出错时显示全部结果
            self.display_ocr_results()

    def create_annotations_from_ocr(self):
        """从OCR结果创建标注"""
        if not self.ocr_results:
            QMessageBox.information(self, "提示", "请先进行OCR识别")
            return
            
        # 获取设置的置信度阈值
        confidence_threshold = self.confidence_slider.value() / 100.0
        
        # 统计创建了多少个新标注
        created_count = 0
        for result in self.ocr_results:
            # 只处理置信度高于阈值的结果
            if result.get('confidence', 0) >= confidence_threshold:
                self.create_annotation_from_ocr_result(result)
                created_count += 1
                
        if created_count > 0:
            # 如果是多页PDF模式，更新当前页面的标注缓存
            if self.pdf_file_path and self.current_pdf_page in range(self.pdf_page_count):
                # 使用新的保存方法更新当前页的标注数据
                self.save_current_page_data()
                
            QMessageBox.information(self, "完成", f"已创建 {created_count} 个标注")
        else:
            QMessageBox.information(self, "提示", "没有符合置信度要求的OCR结果可创建标注")
            
        # 刷新标注列表
        self.refresh_annotation_list()

    def _parse_annotation_text(self, text: str) -> dict:
        text_main = re.sub(r'\s*\(.*\)', '', text).strip()
        match = re.match(r'([Φ∅øMR])\s*(\d+\.?\d*)', text_main, re.IGNORECASE)
        if match: return {'type': '直径(Φ)', 'dimension': match.group(2)}
        return {'type': '线性', 'dimension': text_main}
        
    def create_annotation_from_ocr_result(self, ocr_result: dict):
        parsed_data = self._parse_annotation_text(ocr_result['text'])
        annotation_text = f"原始文本: {ocr_result['text']}"
        
        # 更改锚点位置计算
        if 'bbox' in ocr_result:
            bbox = ocr_result['bbox']
            bbox_array = np.array(bbox)
            
            # 计算边界框的中心点
            center_x = np.mean(bbox_array[:, 0])
            center_y = np.mean(bbox_array[:, 1])
            
            # 计算边界框宽度
            x_min, x_max = np.min(bbox_array[:, 0]), np.max(bbox_array[:, 0])
            width = x_max - x_min
            
            # 设置锚点在文本框右侧中间位置
            anchor_x = x_max + width * 0.2  # 向右偏移宽度的20%
            anchor_y = center_y
            anchor_point = QPointF(anchor_x, anchor_y)
        else:
            # 如果没有边界框，使用center字段
            center = ocr_result.get('center', (0, 0))
            anchor_point = QPointF(center[0], center[1])
        
        # 创建标注
        annotation = self._create_new_annotation(
            anchor_point=anchor_point,
            text=annotation_text,
            dimension=parsed_data.get('dimension', ''),
            dimension_type=parsed_data.get('type', ''),
            style=OCR_TYPE_TO_STYLE.get(ocr_result.get('type', 'annotation'), 'default')
        )
        
        # 如果存在边界框信息，保存到标注项中
        if 'bbox' in ocr_result:
            bbox = ocr_result['bbox']
            # 将numpy数组转换为QPointF列表
            points = [QPointF(point[0], point[1]) for point in bbox]
            # 调试输出
            # print(f"OCR Text: {ocr_result['text']}, Points: {[(p.x(), p.y()) for p in points]}")
            # 存储边界框信息
            annotation.set_bbox_points(points)
        
        return annotation

    def _create_new_annotation(self, anchor_point: QPointF, text: str = "", dimension: str = "", dimension_type: str = "", style: str = "default"):
        # 在创建新标注前，先确定全局最大ID
        if self.pdf_file_path and self.pdf_page_count > 1:
            # 多页PDF模式，计算所有页面中的最大ID
            max_id_across_pages = self.annotation_counter
            
            # 遍历所有页面的标注数据
            for page_idx in range(self.pdf_page_count):
                if page_idx in self.annotations_by_page and self.annotations_by_page[page_idx]:
                    page_annotations = self.annotations_by_page[page_idx]
                    if page_annotations:
                        page_max_id = max(annotation_data['annotation_id'] for annotation_data in page_annotations)
                        max_id_across_pages = max(max_id_across_pages, page_max_id)
            
            # 更新计数器为全局最大值
            self.annotation_counter = max_id_across_pages
            
        # 递增标注计数器
        self.annotation_counter += 1
        
        shape_map = {"空心圆": "circle", "实心圆": "solid_circle", "五角星": "pentagram", "三角形": "triangle"}
        selected_shape = shape_map.get(self.shape_combo.currentText(), "circle")
        
        # 创建标注项（初始大小为15，后续会调整）
        annotation = BubbleAnnotationItem(
            annotation_id=self.annotation_counter,
            anchor_point=anchor_point,
            text=text,
            style=style,
            shape=selected_shape,
            color=self.next_annotation_color,
            size=15,  # 临时大小，会基于scale_factor调整
            dimension=dimension,
            dimension_type=dimension_type
        )
        
        # 设置比例因子并触发大小自动计算
        annotation.auto_radius = True
        annotation.scale_factor = self.next_annotation_scale
        
        # 使用-1触发自动计算大小
        annotation.change_size(-1)
        
        # 清除颜色设置（一次性的）
        if self.next_annotation_color: self.next_annotation_color = None
        
        annotation.data_updated.connect(self.annotation_table.update_annotation_data)
        annotation.selected.connect(self.on_annotation_selected)
        annotation.moved.connect(self.on_annotation_moved)
        annotation.delete_requested.connect(self.delete_annotation)
        annotation.style_change_requested.connect(self.on_annotation_style_changed)
        annotation.shape_change_requested.connect(self.on_annotation_shape_changed)
        annotation.color_change_requested.connect(self.on_annotation_color_changed)
        annotation.size_change_requested.connect(self.on_annotation_size_changed)
        
        self.graphics_scene.addItem(annotation)
        self.annotations.append(annotation)
        self.annotation_table.add_annotation(annotation, {})
        
        return annotation

    def on_annotation_selected(self, annotation: BubbleAnnotationItem):
        for ann in self.annotations: ann.set_highlighted(False)
        self.current_annotation = annotation; annotation.set_highlighted(True)
        
        # 获取真实图像位置预览区域
        preview_rect = self.get_annotation_preview_rect(annotation)
        self.property_editor.set_annotation(annotation, self.current_pixmap, preview_rect)
        
        self.annotation_table.highlight_annotation(annotation.annotation_id)
        style_text = "自定义" if annotation.custom_color else STYLE_NAME_MAP.get(annotation.style, "默认")
        self.style_combo.blockSignals(True); self.style_combo.setCurrentText(style_text); self.style_combo.blockSignals(False)
        shape_map_rev = {"circle": "空心圆", "solid_circle": "实心圆", "pentagram": "五角星", "triangle": "三角形"}
        shape_text = shape_map_rev.get(annotation.shape_type, "空心圆")
        self.shape_combo.blockSignals(True); self.shape_combo.setCurrentText(shape_text); self.shape_combo.blockSignals(False)
        
        # 更新滑块为当前比例
        self.size_slider.blockSignals(True)
        scale_percent = int(annotation.scale_factor * 100)
        self.size_slider.setValue(scale_percent)
        self.size_label.setText(f"{scale_percent}%")
        self.size_slider.blockSignals(False)
        
        self.update_color_button_display()
        
    def get_annotation_preview_rect(self, annotation: BubbleAnnotationItem):
        """获取标注预览区域的矩形"""
        # 尝试查找关联的OCR结果
        if hasattr(annotation, 'bbox_points') and annotation.bbox_points:
            # 如果标注有bbox信息，直接使用
            bbox_points = annotation.bbox_points
            x_values = [p.x() for p in bbox_points]
            y_values = [p.y() for p in bbox_points]
            min_x = min(x_values)
            min_y = min(y_values)
            max_x = max(x_values)
            max_y = max(y_values)
            width = max_x - min_x
            height = max_y - min_y
            
            # 稍微扩大一点区域，方便查看
            padding = max(width, height) * 0.2
            preview_rect = QRectF(
                min_x - padding,
                min_y - padding,
                width + padding * 2,
                height + padding * 2
            )
            print(f"从bbox获取预览区域: {preview_rect}")
            return preview_rect
        
        # 如果没有bbox，尝试根据OCR结果查找
        ocr_results = self._find_matching_ocr_results(annotation.anchor_point, annotation.text)
        if ocr_results:
            # 使用OCR边界框
            best_match = ocr_results[0]
            bbox = best_match['bbox']
            # 计算边界框的边界
            x_values = [point[0] for point in bbox]
            y_values = [point[1] for point in bbox]
            min_x = min(x_values)
            min_y = min(y_values)
            max_x = max(x_values)
            max_y = max(y_values)
            width = max_x - min_x
            height = max_y - min_y
            
            # 稍微扩大一点区域，方便查看
            padding = max(width, height) * 0.2
            preview_rect = QRectF(
                min_x - padding,
                min_y - padding,
                width + padding * 2,
                height + padding * 2
            )
            print(f"从OCR结果获取预览区域: {preview_rect}")
            return preview_rect
        
        # 如果没有关联OCR结果，使用锚点为中心的默认区域
        anchor_pos = annotation.anchor_point
        default_size = 100  # 默认区域大小
        preview_rect = QRectF(
            anchor_pos.x() - default_size / 2,
            anchor_pos.y() - default_size / 2,
            default_size,
            default_size
        )
        print(f"使用默认区域: {preview_rect}")
        return preview_rect
    
    def on_annotation_moved(self, annotation: BubbleAnnotationItem, position: QPointF):
        if annotation == self.current_annotation:
            # 获取新的预览区域并更新
            preview_rect = self.get_annotation_preview_rect(annotation)
            self.property_editor.preview_rect = preview_rect
            self.property_editor.update_preview()
    
    def select_annotation_by_id(self, annotation_id: int):
        """根据ID选中标注
        
        Args:
            annotation_id: 要选中的标注ID
        """
        try:
            # 首先确保annotations列表有效
            if not self.annotations:
                return
                
            # 查找对应ID的标注
            found_annotation = None
            for annotation in self.annotations:
                if annotation.annotation_id == annotation_id:
                    found_annotation = annotation
                    break
                    
            # 如果找不到对应ID的标注，直接返回
            if not found_annotation:
                return
                
            # 添加安全检查，确保对象仍然有效
            try:
                # 尝试访问对象的一个属性，如果对象已删除会抛出异常
                _ = found_annotation.isVisible()
            except RuntimeError:
                print(f"警告: 标注 #{annotation_id} 对象已被删除，无法选中")
                return
                
            # 将视图中心对准标注
            self.graphics_view.centerOn(found_annotation)
            self.graphics_scene.clearSelection()
            found_annotation.setSelected(True)
            self.on_annotation_selected(found_annotation)
        except Exception as e:
            print(f"选中标注时出错: {e}")
            # 不向用户显示错误，静默失败
    
    def toggle_area_selection(self, checked: bool):
        self.graphics_view.set_selection_mode(checked)
        self.area_select_action.setText("退出区域OCR" if checked else "区域OCR标注")
        
        # 禁用或启用其他可能冲突的功能
        if checked:
            # 如果启用区域选择，禁用屏蔽区域选择
            if self.mask_select_action.isChecked():
                self.mask_select_action.blockSignals(True)
                self.mask_select_action.setChecked(False)
                self.mask_select_action.blockSignals(False)
                self.is_selecting_mask = False
            
            # 显示提示信息
            self.status_bar.showMessage("区域OCR识别模式：请在图纸上拖拽选择要识别的区域...", 5000)
        else:
            self.status_bar.showMessage("已退出区域OCR识别模式", 3000)
    
    def create_annotation_in_area(self, rect: QRectF):
        if self.is_selecting_mask: return
        self._create_new_annotation(
            anchor_point=rect.center(),
            text=f"区域标注 {self.annotation_counter + 1}"
        )
        self.area_select_action.setChecked(False)
    
    def delete_annotation(self, annotation: BubbleAnnotationItem):
        """删除标注"""
        try:
            self.graphics_scene.removeItem(annotation)
            self.annotations.remove(annotation)
            
            if self.current_annotation == annotation:
                self.current_annotation = None
                self.property_editor.set_annotation(None, None, None)
            
            # 更新标注列表
            self.refresh_annotation_list()
            
            # 如果是多页PDF模式，更新当前页的标注缓存
            if self.pdf_file_path and self.current_pdf_page in range(self.pdf_page_count):
                self.save_current_page_data()
                
            self.status_bar.showMessage(f"已删除标注 #{annotation.annotation_id}", 2000)
        except Exception as e:
            print(f"删除标注时出错: {e}")
            self.status_bar.showMessage(f"删除标注失败: {str(e)}", 2000)
    
    def refresh_annotation_list(self):
        # 使用新的排序方法，直接将所有标注传递给表格进行排序和显示
        self.annotation_table.sort_annotations(self.annotations)
    
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
        if annotation == self.current_annotation: self.on_annotation_selected(annotation)
        
    def reorder_annotations(self):
        """重新排序所有气泡标注
        
        按照从左到右，从上到下的顺序重新对所有气泡标注进行编号
        在多页PDF模式下，考虑前面页面的标注数量，保持连续编号
        """
        if not self.annotations:
            QMessageBox.information(self, "提示", "没有标注可以重新排序")
            return
            
        # 确认对话框
        confirm_message = "确定要重新排序当前页面的气泡标注吗？"
        
        # 判断是否为多页PDF模式
        if self.pdf_file_path and self.pdf_page_count > 1:
            confirm_message = "检测到多页PDF，请选择重新排序方式：\n\n" \
                             "【是】: 从页面1开始全局重排序（跨页面重新从1开始编号）\n" \
                             "【否】: 仅重排序当前页面（考虑前面页面的标注数量）\n" \
                             "【取消】: 取消操作"
                             
            confirm = QMessageBox.question(
                self, 
                "确认重新排序", 
                confirm_message,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No
            )
            
            if confirm == QMessageBox.Cancel:
                return
                
            if confirm == QMessageBox.Yes:
                # 全局重排序 - 从页面1开始重新编号
                return self._reorder_all_pdf_pages()
                
            # 否则继续当前页面排序，但考虑前面页面的标注数量
            return self._reorder_current_page_with_continuity()
        else:
            # 非PDF模式，或单页PDF
            confirm = QMessageBox.question(
                self, 
                "确认重新排序", 
                confirm_message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if confirm != QMessageBox.Yes:
                return
                
            # 普通排序
            self._reorder_current_page(start_id=1)
            
    def _reorder_current_page(self, start_id=1):
        """重排序当前页面的标注
        
        Args:
            start_id: 起始ID
        """
        # 改进的排序方法：使用精确的Y坐标而非网格，确保更准确的从上到下排序
        sorted_annotations = sorted(
            self.annotations,
            key=lambda ann: (ann.scenePos().y(), ann.scenePos().x())
        )
        
        # 保存当前选中的标注
        current_annotation_id = self.current_annotation.annotation_id if self.current_annotation else None
        
        # 重新分配ID
        new_id = start_id
        for annotation in sorted_annotations:
            old_id = annotation.annotation_id
            annotation.annotation_id = new_id
            
            # 更新文本（如果文本中包含ID）
            if str(old_id) in annotation.text:
                annotation.text = annotation.text.replace(str(old_id), str(new_id))
                
            # 更新气泡显示
            annotation.update_annotation_id_display()
            
            # 发送数据更新信号
            annotation.data_updated.emit(annotation)
            
            new_id += 1
        
        # 更新标注计数器
        self.annotation_counter = max(self.annotation_counter, new_id - 1)
        
        # 刷新标注列表
        self.refresh_annotation_list()
        
        # 更新当前页面的缓存
        if self.pdf_file_path and self.current_pdf_page in range(self.pdf_page_count):
            self.save_current_page_data()
        
        # 恢复选中的标注（如果可能）
        if current_annotation_id is not None:
            # 尝试找到原来的标注
            for annotation in self.annotations:
                if annotation.annotation_id == current_annotation_id:
                    self.select_annotation_by_id(annotation.annotation_id)
                    break
        
        self.status_bar.showMessage(f"已成功重新排序 {len(sorted_annotations)} 个气泡标注（从上到下，从左到右）", 3000)
            
    def _reorder_current_page_with_continuity(self):
        """重新排序当前页面，保持与前面页面的连续性"""
        # 计算前面页面的标注数量总和
        previous_annotations_count = 0
        
        if self.pdf_file_path and self.current_pdf_page > 0:
            for page_idx in range(self.current_pdf_page):
                if page_idx in self.annotations_by_page:
                    previous_annotations_count += len(self.annotations_by_page[page_idx])
        
        # 从前面页面标注数量+1开始编号
        start_id = previous_annotations_count + 1
        
        # 执行排序
        self._reorder_current_page(start_id=start_id)
        
        self.status_bar.showMessage(f"已重新排序当前页面标注，起始编号: {start_id}，保持与前面页面的连续性", 3000)
        
    def _reorder_all_pdf_pages(self):
        """全局重排序所有PDF页面"""
        if not self.pdf_file_path:
            return
            
        # 保存当前页
        current_page = self.current_pdf_page
        
        # 先保存当前页数据
        self.save_current_page_data()
        
        try:
            # 重新加载第一页，并从第一页开始排序
            if current_page != 0:
                self.load_pdf_page(0)
                
            # 强制从1开始编号所有标注
            next_id = 1
            
            # 处理所有页面
            for page_idx in range(self.pdf_page_count):
                # 确保我们加载了正确的页面
                if page_idx != self.current_pdf_page:
                    self.load_pdf_page(page_idx)
                
                # 如果当前页面有标注
                if self.annotations:
                    # 对当前页标注按照Y坐标（然后是X坐标）排序
                    sorted_annotations = sorted(
                        self.annotations,
                        key=lambda ann: (ann.scenePos().y(), ann.scenePos().x())
                    )
                    
                    # 重新分配ID
                    for annotation in sorted_annotations:
                        old_id = annotation.annotation_id
                        annotation.annotation_id = next_id
                        
                        # 更新文本（如果文本中包含ID）
                        if str(old_id) in annotation.text:
                            annotation.text = annotation.text.replace(str(old_id), str(next_id))
                            
                        # 更新气泡显示
                        annotation.update_annotation_id_display()
                        
                        next_id += 1
                    
                    # 保存更新后的数据
                    self.save_current_page_data()
                    
                    # 刷新标注列表
                    self.refresh_annotation_list()
            
            # 更新全局计数器
            self.annotation_counter = next_id - 1
            
            # 返回到原始页面
            if current_page != self.current_pdf_page:
                self.load_pdf_page(current_page)
                
            QMessageBox.information(self, "全局重排序完成", f"已完成所有{self.pdf_page_count}页PDF的标注重排序，总标注数量: {next_id-1}")
            
        except Exception as e:
            QMessageBox.warning(self, "重排序出错", f"全局重排序过程中出错: {str(e)}")
            print(f"全局重排序出错: {e}")
            # 确保返回原始页面
            if current_page != self.current_pdf_page:
                self.load_pdf_page(current_page)

    def select_annotation_color(self):
        initial_color = QColor("blue")
        if self.current_annotation and self.current_annotation.custom_color:
            initial_color = self.current_annotation.custom_color
        elif self.next_annotation_color:
            initial_color = self.next_annotation_color
        color = QColorDialog.getColor(initial_color, self, "选择标注颜色")
        if color.isValid():
            if self.current_annotation:
                self.current_annotation.change_color(color)
            else:
                self.next_annotation_color = color
                self.update_color_button_display()
                self.status_bar.showMessage(f"下一个标注的颜色已设置为 {color.name()}", 3000)

    def update_color_button_display(self):
        color_to_show = None
        if self.current_annotation and self.current_annotation.custom_color:
            color_to_show = self.current_annotation.custom_color
        elif self.next_annotation_color:
            color_to_show = self.next_annotation_color
        if color_to_show and color_to_show.isValid():
            self.color_button.setStyleSheet(f"QPushButton {{ background-color: {color_to_show.name()}; color: {'white' if color_to_show.lightnessF() < 0.5 else 'black'}; border: 1px solid grey; font-weight: bold; }}")
        else:
            self.color_button.setStyleSheet("")
            self.next_annotation_color = None

    def on_annotation_size_changed(self, annotation: BubbleAnnotationItem):
        if annotation == self.current_annotation: self.on_annotation_selected(annotation)

    def change_annotation_size(self, percent: int):
        """更改注释大小（基于比例）
        
        Args:
            percent: 大小比例，范围50-160（对应50%-160%）
        """
        # 调试信息，帮助追踪滑块问题
        print(f"滑块值变化: {percent}%")
        
        # 显示百分比文本
        self.size_label.setText(f"{percent}%")
        
        # 将百分比转换为比例因子，比如100%=1.0，50%=0.5
        scale_factor = percent / 100.0
        
        if self.current_annotation:
            print(f"应用比例 {scale_factor} 到当前选中的气泡 ID: {self.current_annotation.annotation_id}")
            # 首先设置比例因子
            self.current_annotation.scale_factor = scale_factor
            # 确保auto_radius设置为True，这样才会使用比例因子
            self.current_annotation.auto_radius = True
            # 强制重新计算气泡尺寸并更新显示
            self.current_annotation.change_size(-1)
            # 刷新属性编辑器
            self.property_editor.update_preview()
        else:
            # 保存为下一个标注的默认比例
            self.next_annotation_size = -1  # 标记为自动
            self.next_annotation_scale = scale_factor
            self.status_bar.showMessage(f"下一个标注的大小已设置为 {percent}%", 3000)
    
    def clear_annotations(self, show_empty_message=True):
        """清除所有标注"""
        if not self.annotations:
            if show_empty_message:
                self.status_bar.showMessage("没有标注可清除", 2000)
            return

        confirm = QMessageBox.question(
            self, "确认清除", "确定要删除所有标注吗？这个操作不能撤销。", 
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) if show_empty_message else QMessageBox.Yes

        if confirm == QMessageBox.Yes:
            # 先清空标注表，避免引用已删除对象
            self.annotation_table.clear_annotations()
            
            # 清除当前选中状态
            self.current_annotation = None
            self.property_editor.set_annotation(None, None, None)
            
            # 创建一个临时副本，避免在迭代时修改列表
            annotations_to_remove = list(self.annotations)
            
            # 清空标注列表先，这样我们在删除场景项时就不会尝试访问self.annotations中的对象了
            self.annotations.clear()
            
            # 从场景中删除标注
            for annotation in annotations_to_remove:
                try:
                    self.graphics_scene.removeItem(annotation)
                except Exception as e:
                    print(f"删除标注时出错: {e}")
                    # 继续处理其他标注
            
            # 清空副本以释放引用
            annotations_to_remove.clear()
            
            # 当前是否为多页PDF模式
            if self.pdf_file_path and self.current_pdf_page in range(self.pdf_page_count):
                # 清除当前页面的缓存标注
                if self.current_pdf_page in self.annotations_by_page:
                    self.annotations_by_page[self.current_pdf_page] = []
            
            if show_empty_message:
                self.status_bar.showMessage("已清除所有标注", 2000)

    def toggle_mask_selection(self, checked: bool):
        self.is_selecting_mask = checked; self.graphics_view.set_selection_mode(checked)
        if hasattr(self, 'mask_select_action'):
            self.mask_select_action.blockSignals(True); self.mask_select_action.setChecked(checked); self.mask_select_action.blockSignals(False)
        if checked and hasattr(self, 'area_select_action'):
            self.area_select_action.blockSignals(True); self.area_select_action.setChecked(False); self.area_select_action.blockSignals(False)
        self.status_bar.showMessage("屏蔽区域选择模式：拖拽鼠标选择要屏蔽的区域" if checked else "已退出屏蔽区域选择模式", 3000 if not checked else 0)
    
    def handle_area_selection(self, rect: QRectF):
        if self.is_selecting_mask:
            self.add_masked_region(rect)
        else:
            # 修改为对选中区域进行OCR识别
            self.run_ocr_on_selected_area(rect)
    
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
        for item in items_to_remove:
            self.graphics_scene.removeItem(item)
        self.update_mask_count()
        self.status_bar.showMessage("已清除所有屏蔽区域", 2000)
    
    def update_mask_count(self): pass
    
    def is_point_in_masked_region(self, x: float, y: float) -> bool:
        return any(region.contains(QPointF(x, y)) for region in self.masked_regions)
    
    def is_bbox_in_masked_region(self, bbox) -> bool:
        if not self.masked_regions: return False
        if hasattr(bbox, '__len__') and len(bbox) >= 4:
            if HAS_OCR_SUPPORT:
                x_min, y_min = np.min(bbox, axis=0)
                x_max, y_max = np.max(bbox, axis=0)
            else:
                x_coords, y_coords = [p[0] for p in bbox], [p[1] for p in bbox]
                x_min, x_max, y_min, y_max = min(x_coords), max(x_coords), min(y_coords), max(y_coords)
            bbox_rect = QRectF(x_min, y_min, x_max - x_min, y_max - y_min)
        else:
            bbox_rect = bbox
        return any(region.intersects(bbox_rect) for region in self.masked_regions)

    def on_gpu_checkbox_toggled(self, checked):
        """当GPU复选框状态变化时，更新CPU复选框状态"""
        if checked and self.cpu_checkbox.isChecked():
            self.cpu_checkbox.blockSignals(True)
            self.cpu_checkbox.setChecked(False)
            self.cpu_checkbox.blockSignals(False)
            # 禁用线程数输入框
            self.threads_spinbox.setEnabled(False)

    def on_cpu_checkbox_toggled(self, checked):
        """当CPU复选框状态变化时，更新GPU复选框状态"""
        if checked and self.gpu_checkbox.isChecked():
            self.gpu_checkbox.blockSignals(True)
            self.gpu_checkbox.setChecked(False)
            self.gpu_checkbox.blockSignals(False)
        # 根据CPU选择状态启用/禁用线程数输入框    
        self.threads_spinbox.setEnabled(checked)

    def change_current_annotation_text(self, new_text: str):
        """修改当前选中标注的文本内容"""
        if self.current_annotation and self.current_annotation.text != new_text:
            self.current_annotation.set_text(new_text)
            return True
        return False

    def run_ocr_on_selected_area(self, rect: QRectF):
        """对选中区域进行OCR识别"""
        if not HAS_OCR_SUPPORT:
            QMessageBox.warning(self, "功能缺失", "OCR功能需要PaddleOCR和依赖包。请安装所需依赖。")
            self.create_annotation_in_area(rect)  # 仍然创建区域标注
            return
        
        if not self.current_pixmap:
            QMessageBox.information(self, "提示", "请先打开图片文件。")
            return
            
        # 从当前图像中截取选定区域
        x, y, width, height = rect.x(), rect.y(), rect.width(), rect.height()
        
        # 确保坐标在有效范围内
        x = max(0, int(x))
        y = max(0, int(y))
        width = min(int(width), self.current_pixmap.width() - x)
        height = min(int(height), self.current_pixmap.height() - y)
        
        # 创建临时文件保存选定区域
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # 截取并保存区域图像
        cropped_pixmap = self.current_pixmap.copy(x, y, width, height)
        cropped_pixmap.save(temp_path)
        
        self.status_bar.showMessage("正在对选中区域进行OCR识别...")
        
        # 获取语言配置
        lang_text = self.language_combo.currentText()
        lang_code = DEFAULT_OCR_LANGUAGES.get(lang_text, ["ch_sim"])
        
        # 获取环境配置
        force_cpu = self.cpu_checkbox.isChecked()
        use_gpu = self.gpu_checkbox.isChecked() and not force_cpu
        
        # 获取CPU线程数
        cpu_threads = self.threads_spinbox.value()
        
        # 创建区域OCR工作器
        self.area_ocr_worker = PaddleOCRWorker(
            temp_path, 
            lang_code, 
            [],  # 区域识别不需要屏蔽区域
            force_cpu=force_cpu,
            cpu_threads=cpu_threads
        )
        
        # 连接信号
        self.area_ocr_worker.signals.progress.connect(lambda p: self.progress_bar.setValue(p))
        self.area_ocr_worker.signals.error.connect(self.on_area_ocr_error)
        
        # 使用lambda捕获rect参数，传递给回调函数
        self.area_ocr_worker.signals.finished.connect(
            lambda results: self.on_area_ocr_finished(results, rect, temp_path, x, y)
        )
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动线程
        self.thread_pool.start(self.area_ocr_worker)
        
    def on_area_ocr_error(self, error_msg: str):
        """区域OCR错误处理"""
        self.progress_bar.setVisible(False)
        QMessageBox.warning(self, "区域OCR识别错误", error_msg)
        self.area_select_action.setChecked(False)
    
    def on_area_ocr_finished(self, results: List[dict], rect: QRectF, temp_path: str, offset_x: int, offset_y: int):
        """区域OCR完成处理"""
        self.progress_bar.setVisible(False)
        
        # 删除临时文件
        try:
            os.unlink(temp_path)
        except:
            pass
        
        # 如果没有识别结果，创建空白标注
        if not results:
            QMessageBox.information(self, "区域OCR", "选中区域未识别到文字，将创建空白标注。")
            self.create_annotation_in_area(rect)
            self.area_select_action.setChecked(False)
            return
        
        # 调整结果坐标（添加偏移量）
        for result in results:
            if 'bbox' in result:
                adjusted_bbox = []
                for point in result['bbox']:
                    adjusted_bbox.append([point[0] + offset_x, point[1] + offset_y])
                result['bbox'] = adjusted_bbox
            
            if 'center_x' in result and 'center_y' in result:
                result['center_x'] += offset_x
                result['center_y'] += offset_y
        
        # 创建底色显示区域 - 与全局OCR一样显示识别区域
        for i, result in enumerate(results):
            self.create_ocr_bbox_item(result, i)
                
        # 为每个OCR结果创建标注
        confidence_threshold = self.confidence_slider.value() / 100.0
        created_count = 0
        
        for result in results:
            if result.get('confidence', 0) >= confidence_threshold:
                # 修改为使用相对于场景的正确坐标创建标注
                self.create_annotation_from_ocr_result(result)
                created_count += 1
        
        # 将识别结果添加到全局OCR结果中，以便筛选和管理
        self.ocr_results.extend(results)
        self.update_ocr_stats()
        
        if created_count > 0:
            QMessageBox.information(self, "区域OCR完成", f"在选中区域内识别出 {len(results)} 个文本，创建了 {created_count} 个标注。")
            self.refresh_annotation_list()
        else:
            QMessageBox.information(self, "区域OCR", "选中区域的识别结果未达到置信度阈值，将创建空白标注。")
            self.create_annotation_in_area(rect)
        
        self.area_select_action.setChecked(False)

    def delete_current_annotation(self):
        """删除当前选中的标注"""
        if not self.current_annotation:
            QMessageBox.information(self, "提示", "请先选择一个标注")
            return
            
        confirm = QMessageBox.question(
            self, "确认删除", f"确定要删除标注 #{self.current_annotation.annotation_id} 吗？", 
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            # 保存当前标注引用，以便删除
            annotation_to_delete = self.current_annotation
            self.current_annotation = None
            self.property_editor.set_annotation(None, None, None)
            
            # 删除标注及其关联的OCR结果
            self.delete_annotation(annotation_to_delete)

    def _find_matching_ocr_results(self, anchor_point, annotation_text):
        """多策略匹配OCR结果 - 优化版，更严格的标准避免误匹配"""
        matching_indices = []
        
        # 从文本中提取原始OCR文本（如果有）
        original_ocr_text = None
        if annotation_text and "原始文本:" in annotation_text:
            parts = annotation_text.split("原始文本:")
            if len(parts) > 1:
                original_ocr_text = parts[1].strip()
        
        # 确保只找到最匹配的一个OCR结果
        best_match_index = -1
        best_match_score = float('inf')  # 分数越小越匹配
        
        # 遍历所有OCR结果
        for i, ocr_result in enumerate(self.ocr_results):
            current_score = float('inf')  # 初始化为最大值
            
            # 策略1: 精确文本匹配 - 如果标注中包含原始OCR文本，则检查是否完全匹配
            if original_ocr_text and 'text' in ocr_result:
                ocr_text = ocr_result['text']
                if ocr_text == original_ocr_text:
                    # 完全匹配，这是最优先级
                    matching_indices = [i]
                    return matching_indices
                elif ocr_text.strip() == original_ocr_text.strip():
                    # 除了空格外完全匹配
                    matching_indices = [i]
                    return matching_indices
            
            # 策略2: 位置匹配 - 当没有完全文本匹配时，计算最近的一个
            if 'bbox' in ocr_result:
                bbox = ocr_result['bbox']
                if len(bbox) >= 4:
                    # 计算OCR框的中心点和边界
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    center_x = sum(x_coords) / len(bbox)
                    center_y = sum(y_coords) / len(bbox)
                    ocr_center = QPointF(center_x, center_y)
                    
                    # 计算OCR中心到标注锚点的距离作为分数
                    distance = ((ocr_center.x() - anchor_point.x())**2 + 
                                (ocr_center.y() - anchor_point.y())**2)**0.5
                    
                    # 也考虑特殊的右侧位置关系（加权）
                    right_edge = max(x_coords)
                    if anchor_point.x() > right_edge and abs(anchor_point.y() - center_y) < 20:
                        # 如果位置关系很明确（标注在OCR右侧），距离分数减半
                        distance *= 0.5
                    
                    # 更新得分
                    current_score = distance
            
            # 如果这个OCR结果比之前找到的更匹配，更新最佳匹配
            if current_score < best_match_score:
                best_match_score = current_score
                best_match_index = i
        
        # 只有当最佳匹配的距离小于阈值时才返回结果
        # 使用固定阈值80像素，更严格的匹配标准
        if best_match_index >= 0 and best_match_score < 80:
            matching_indices.append(best_match_index)
        
        return matching_indices

    def convert_pdf_to_images(self):
        """将PDF文件批量转换为PNG图片"""
        if not HAS_OCR_SUPPORT:
            QMessageBox.warning(self, "功能缺失", "PDF转换功能需要PyMuPDF支持。请安装所需依赖。")
            return
            
        # 打开文件选择对话框，仅选择PDF文件
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("PDF文件 (*.pdf)")
        if not file_dialog.exec():
            return
            
        pdf_paths = file_dialog.selectedFiles()
        if not pdf_paths:
            return
            
        pdf_path = pdf_paths[0]
        pdf_filename = Path(pdf_path).name
        
        # 获取质量设置
        zoom_factor = PDF_QUALITY_OPTIONS.get(self.pdf_quality_combo.currentText(), 4.0)
        
        # 显示正在处理的消息
        self.status_bar.showMessage(f"正在处理PDF: {pdf_filename}...")
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        try:
            # 调用转换函数
            png_paths, error = FileLoader.convert_pdf_to_pngs(pdf_path, zoom_factor=zoom_factor)
            
            # 隐藏进度条
            self.progress_bar.setVisible(False)
            
            if error:
                QMessageBox.warning(self, "转换失败", f"PDF转换失败: {error}")
                self.status_bar.showMessage(f"❌ PDF转换失败: {error}", 5000)
                return
                
            if not png_paths:
                QMessageBox.warning(self, "转换失败", "未能生成PNG文件。")
                self.status_bar.showMessage("❌ PDF转换失败: 未能生成PNG文件", 5000)
                return
                
            # 转换成功，显示成功消息
            success_message = f"PDF成功转换为{len(png_paths)}个PNG文件：\n\n"
            for i, path in enumerate(png_paths[:5]):  # 只显示前5个文件路径
                success_message += f"{i+1}. {path}\n"
                
            if len(png_paths) > 5:
                success_message += f"\n... 以及另外 {len(png_paths) - 5} 个文件"
                
            # 询问是否打开第一个生成的PNG文件
            result = QMessageBox.information(
                self, 
                "转换成功", 
                success_message + "\n\n是否打开第一个PNG文件？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if result == QMessageBox.Yes and png_paths:
                # 加载第一个PNG文件
                self.load_file(png_paths[0])
            else:
                self.status_bar.showMessage(f"✅ PDF转换完成: {len(png_paths)}个文件", 5000)
                
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "错误", f"转换过程中发生错误: {str(e)}")
            self.status_bar.showMessage(f"❌ PDF转换错误: {str(e)}", 5000)

    def load_pdf_page(self, page_index: int):
        """加载指定页码的PDF页面
        
        Args:
            page_index: 页码（从0开始）
            
        Returns:
            bool: 是否成功加载
        """
        if not self.pdf_file_path or page_index not in range(self.pdf_page_count):
            return False
            
        # 记录之前的页码，以便加载失败时可以恢复
        previous_page = self.current_pdf_page
            
        # 清除当前选择状态，防止引用已删除的对象
        self.graphics_scene.clearSelection()
        self.current_annotation = None
        self.property_editor.set_annotation(None, None, None)
            
        # 保存当前页面的标注和OCR结果
        if self.current_pdf_page in range(self.pdf_page_count):
            self.save_current_page_data()
            
        try:
            # 更新当前页码
            self.current_pdf_page = page_index
            
            # 更新导航按钮状态
            self.update_pdf_navigation_controls()
                
            # 检查是否已经缓存了该页面
            if page_index in self.pdf_pages_cache:
                temp_path = self.pdf_pages_cache[page_index]
                # 检查临时文件是否仍然存在
                if Path(temp_path).exists():
                    self.status_bar.showMessage(f"从缓存加载PDF页面 {page_index+1}/{self.pdf_page_count}...")
                    pixmap = QPixmap(temp_path)
                    if not pixmap.isNull():
                        # 清除当前场景
                        self.graphics_scene.clear()
                        self.graphics_scene.addPixmap(pixmap)
                        self.current_pixmap = pixmap
                        self.current_file_path = temp_path
                        
                        # 使用延迟调用确保图像居中显示
                        QTimer.singleShot(100, self.center_view)
                        
                        self.restore_page_data(page_index)
                        self.status_bar.showMessage(f"✅ 页面加载成功: {page_index+1}/{self.pdf_page_count}", 3000)
                        return True
            
            # 缓存中没有或临时文件已被删除，重新转换
            zoom_factor = PDF_QUALITY_OPTIONS.get(self.pdf_quality_combo.currentText(), 4.0)
            self.status_bar.showMessage(f"正在转换PDF页面 {page_index+1}/{self.pdf_page_count}...")
            
            # 清除当前场景
            self.graphics_scene.clear()
            
            # 转换PDF页面
            pixmap, temp_path = FileLoader.load_pdf(
                self.pdf_file_path, self.graphics_scene, page_index, quality=zoom_factor
            )
            
            if pixmap and not pixmap.isNull() and temp_path:
                # 缓存此页面
                self.pdf_pages_cache[page_index] = temp_path
                self.current_pixmap = pixmap
                self.current_file_path = temp_path
                
                # 使用延迟调用确保图像居中显示
                QTimer.singleShot(100, self.center_view)
                
                # 恢复此页面的数据
                self.restore_page_data(page_index)
                
                self.status_bar.showMessage(f"✅ 页面加载成功: {page_index+1}/{self.pdf_page_count}", 3000)
                return True
            else:
                # 加载失败，恢复到之前的页面
                self.current_pdf_page = previous_page
                self.update_pdf_navigation_controls()
                self.status_bar.showMessage(f"❌ 页面 {page_index+1} 加载失败", 3000)
                return False
                
        except Exception as e:
            # 发生异常，恢复到之前的页面
            self.current_pdf_page = previous_page
            self.update_pdf_navigation_controls()
            
            # 如果当前场景是空的，尝试恢复之前的页面内容
            if len(self.graphics_scene.items()) == 0 and previous_page in self.pdf_pages_cache:
                prev_temp_path = self.pdf_pages_cache[previous_page]
                if Path(prev_temp_path).exists():
                    try:
                        prev_pixmap = QPixmap(prev_temp_path)
                        self.graphics_scene.addPixmap(prev_pixmap)
                        self.current_pixmap = prev_pixmap
                        self.current_file_path = prev_temp_path
                        
                        # 使用延迟调用确保图像居中显示
                        QTimer.singleShot(100, self.center_view)
                        
                        self.restore_page_data(previous_page)
                    except:
                        pass  # 如果恢复失败，至少保持当前状态
            
            QMessageBox.warning(self, "错误", f"加载PDF页面失败: {str(e)}")
            self.status_bar.showMessage(f"❌ 页面加载失败: {str(e)}", 3000)
            return False

    def update_pdf_navigation_controls(self):
        """更新PDF导航控件的状态"""
        if not self.pdf_file_path:
            self.pdf_nav_widget.setVisible(False)
            return
            
        self.pdf_nav_widget.setVisible(self.pdf_page_count > 1)
        
        # 更新页码显示
        self.page_label.setText(f"{self.current_pdf_page+1}/{self.pdf_page_count}")
        
        # 更新导航按钮状态
        self.prev_page_btn.setEnabled(self.current_pdf_page > 0)
        self.next_page_btn.setEnabled(self.current_pdf_page < self.pdf_page_count - 1)
        self.go_to_page_btn.setEnabled(self.pdf_page_count > 1)
            
    def save_current_page_data(self):
        """保存当前页面的标注和OCR结果"""
        if self.current_pdf_page not in range(self.pdf_page_count):
            return
            
        # 保存当前页的OCR结果
        try:
            self.ocr_results_by_page[self.current_pdf_page] = self.ocr_results.copy()
        except Exception as e:
            print(f"保存OCR结果时出错: {e}")
            # 确保有一个空列表
            self.ocr_results_by_page[self.current_pdf_page] = []
        
        # 保存当前页的标注数据（不是对象引用）
        annotation_data_list = []
        
        # 安全地获取标注数据
        for annotation in list(self.annotations):  # 使用列表副本进行迭代
            try:
                # 检查对象是否有效
                if not annotation.scene():
                    print(f"警告: 标注 #{getattr(annotation, 'annotation_id', 'unknown')} 不在场景中，跳过保存")
                    continue
                
                # 提取标注的基本属性
                annotation_data = {
                    'annotation_id': annotation.annotation_id,
                    'text': annotation.text,
                    'style': annotation.style,
                    'shape_type': annotation.shape_type,
                    'radius': annotation.radius,
                    'base_radius': annotation.base_radius,
                    'scale_factor': annotation.scale_factor,
                    'dimension': annotation.dimension,
                    'dimension_type': annotation.dimension_type,
                    'upper_tolerance': annotation.upper_tolerance,
                    'lower_tolerance': annotation.lower_tolerance,
                    'is_audited': annotation.is_audited,
                    'auto_radius': annotation.auto_radius,
                    'pos_x': annotation.pos().x(),
                    'pos_y': annotation.pos().y(),
                    'anchor_x': annotation.anchor_point.x(),
                    'anchor_y': annotation.anchor_point.y(),
                }
                
                # 保存颜色信息
                if annotation.custom_color and annotation.custom_color.isValid():
                    annotation_data['color'] = {
                        'r': annotation.custom_color.red(),
                        'g': annotation.custom_color.green(),
                        'b': annotation.custom_color.blue(),
                        'a': annotation.custom_color.alpha(),
                    }
                else:
                    annotation_data['color'] = None
                    
                # 保存边界框点信息
                if hasattr(annotation, 'bbox_points') and annotation.bbox_points:
                    bbox_points_data = []
                    for point in annotation.bbox_points:
                        bbox_points_data.append((point.x(), point.y()))
                    annotation_data['bbox_points'] = bbox_points_data
                else:
                    annotation_data['bbox_points'] = []
                    
                annotation_data_list.append(annotation_data)
            except Exception as e:
                print(f"保存标注数据时出错: {e}")
                # 继续处理下一个标注
            
        # 存储数据字典而不是对象引用
        self.annotations_by_page[self.current_pdf_page] = annotation_data_list

    def restore_page_data(self, page_index: int):
        """恢复指定页面的标注和OCR结果"""
        # 先清空标注表，避免引用已删除对象
        self.annotation_table.clear_annotations()
        
        # 清除当前选中状态
        self.current_annotation = None
        self.property_editor.set_annotation(None, None, None)
        
        # 清理场景中的所有标注对象和OCR边界框
        items_to_remove = []
        for item in self.graphics_scene.items():
            # 删除标注对象和OCR边界框
            if isinstance(item, BubbleAnnotationItem) or \
               (item.data(Qt.UserRole) is not None and isinstance(item.data(Qt.UserRole), int) and item.data(Qt.UserRole) >= 10000):
                items_to_remove.append(item)
        
        # 从场景中移除所有标注和OCR边界框
        for item in items_to_remove:
            try:
                self.graphics_scene.removeItem(item)
            except Exception as e:
                print(f"移除项目时出错: {e}")
                # 继续处理
        
        # 清空当前标注列表和OCR结果
        self.annotations = []
        self.ocr_results = []
        
        # 恢复标注
        if page_index in self.annotations_by_page and self.annotations_by_page[page_index]:
            annotation_data_list = self.annotations_by_page[page_index]
            
            # 根据保存的数据重新创建标注对象
            for annotation_data in annotation_data_list:
                try:
                    # 创建位置
                    position = QPointF(annotation_data['pos_x'], annotation_data['pos_y'])
                    anchor_point = QPointF(annotation_data['anchor_x'], annotation_data['anchor_y'])
                    
                    # 创建颜色对象
                    color = None
                    if annotation_data['color']:
                        color_data = annotation_data['color']
                        color = QColor(
                            color_data['r'],
                            color_data['g'],
                            color_data['b'],
                            color_data['a']
                        )
                    
                    # 创建新的标注对象
                    annotation = BubbleAnnotationItem(
                        annotation_id=annotation_data['annotation_id'],
                        anchor_point=anchor_point,
                        text=annotation_data['text'],
                        style=annotation_data['style'],
                        shape=annotation_data['shape_type'],
                        color=color,
                        size=annotation_data['radius'],
                        dimension=annotation_data['dimension'],
                        dimension_type=annotation_data['dimension_type'],
                        upper_tolerance=annotation_data['upper_tolerance'],
                        lower_tolerance=annotation_data['lower_tolerance'],
                        is_audited=annotation_data['is_audited']
                    )
                    
                    # 设置其他属性
                    annotation.setPos(position)
                    annotation.base_radius = annotation_data['base_radius']
                    annotation.scale_factor = annotation_data['scale_factor']
                    annotation.auto_radius = annotation_data['auto_radius']
                    
                    # 恢复边界框点
                    if annotation_data['bbox_points']:
                        bbox_points = []
                        for point_tuple in annotation_data['bbox_points']:
                            bbox_points.append(QPointF(point_tuple[0], point_tuple[1]))
                        annotation.set_bbox_points(bbox_points)
                    
                    # 连接信号
                    self._connect_annotation_signals(annotation)
                    
                    # 添加到场景和列表
                    self.graphics_scene.addItem(annotation)
                    self.annotations.append(annotation)
                except Exception as e:
                    print(f"恢复标注时出错: {e}")
                    # 继续处理下一个标注
                
            # 更新标注计数器
            if self.annotations:
                self.annotation_counter = max(annotation.annotation_id for annotation in self.annotations)
                
        # 恢复OCR结果
        if page_index in self.ocr_results_by_page and self.ocr_results_by_page[page_index]:
            self.ocr_results = self.ocr_results_by_page[page_index].copy()
            
            # 重新显示OCR边界框
            self.display_ocr_results()
            self.update_ocr_stats()
        
        # 最后再刷新标注列表，确保使用的是当前页面的标注
        self.refresh_annotation_list()

    def _connect_annotation_signals(self, annotation):
        """连接标注对象的所有信号"""
        annotation.selected.connect(self.on_annotation_selected)
        annotation.moved.connect(self.on_annotation_moved)
        annotation.delete_requested.connect(self.delete_annotation)
        annotation.size_change_requested.connect(self.on_annotation_size_changed)
        annotation.shape_change_requested.connect(self.on_annotation_shape_changed)
        annotation.style_change_requested.connect(self.on_annotation_style_changed)
        annotation.color_change_requested.connect(self.on_annotation_color_changed)
        annotation.data_updated.connect(lambda: self.refresh_annotation_list())

    def go_to_prev_page(self):
        """转到上一页"""
        if self.pdf_file_path and self.current_pdf_page > 0:
            self.load_pdf_page(self.current_pdf_page - 1)
            
    def go_to_next_page(self):
        """转到下一页"""
        if self.pdf_file_path and self.current_pdf_page < self.pdf_page_count - 1:
            self.load_pdf_page(self.current_pdf_page + 1)
            
    def show_go_to_page_dialog(self):
        """显示页面跳转对话框"""
        if not self.pdf_file_path or self.pdf_page_count <= 1:
            return
            
        page, ok = QInputDialog.getInt(
            self, 
            "跳转到页面", 
            f"请输入要跳转的页码 (1-{self.pdf_page_count}):", 
            self.current_pdf_page + 1,  # 当前页码（从1开始）
            1, self.pdf_page_count, 1
        )
        
        if ok:
            self.load_pdf_page(page - 1)  # 转换为从0开始的索引

    def setup_compact_ocr_panel(self, parent_layout):
        ocr_widget = QWidget(); ocr_widget.setMaximumHeight(200); ocr_layout = QVBoxLayout(ocr_widget); ocr_layout.setContentsMargins(5, 5, 5, 5); ocr_layout.setSpacing(3)
        row1_layout = QHBoxLayout(); row1_layout.addWidget(QLabel("语言:")); self.language_combo = QComboBox(); self.language_combo.addItems(list(DEFAULT_OCR_LANGUAGES.keys())); self.language_combo.setCurrentText("中文+英文"); row1_layout.addWidget(self.language_combo)
        row1_layout.addWidget(QLabel("置信度:")); self.confidence_slider = QSlider(Qt.Horizontal); self.confidence_slider.setRange(10, 90); self.confidence_slider.setValue(30); self.confidence_slider.setMaximumWidth(80); self.confidence_label = QLabel("0.30"); self.confidence_label.setMinimumWidth(40); row1_layout.addWidget(self.confidence_slider); row1_layout.addWidget(self.confidence_label); ocr_layout.addLayout(row1_layout)
        row2_layout = QHBoxLayout()
        self.enhance_contrast_cb = QCheckBox("增强对比度"); self.enhance_contrast_cb.setChecked(True); row2_layout.addWidget(self.enhance_contrast_cb)
        self.denoise_cb = QCheckBox("降噪"); self.denoise_cb.setChecked(True); row2_layout.addWidget(self.denoise_cb)
        self.gpu_checkbox = QCheckBox("GPU"); self.gpu_checkbox.setChecked(HAS_GPU_SUPPORT); self.gpu_checkbox.setEnabled(HAS_GPU_SUPPORT); row2_layout.addWidget(self.gpu_checkbox)
        self.cpu_checkbox = QCheckBox("CPU"); self.cpu_checkbox.setChecked(not HAS_GPU_SUPPORT); row2_layout.addWidget(self.cpu_checkbox)
        row2_layout.addWidget(QLabel("线程数:"))
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setMinimum(1)
        self.threads_spinbox.setMaximum(32)
        self.threads_spinbox.setValue(8)  # 默认8线程
        self.threads_spinbox.setToolTip("CPU模式下使用的线程数")
        self.threads_spinbox.setEnabled(not HAS_GPU_SUPPORT)  # 初始状态根据CPU选择框状态
        row2_layout.addWidget(self.threads_spinbox)
        row2_layout.addStretch(); ocr_layout.addLayout(row2_layout)
        row3_layout = QHBoxLayout(); self.ocr_button = QPushButton("🔍 开始OCR识别" if HAS_OCR_SUPPORT else "❌ OCR不可用");
        if not HAS_OCR_SUPPORT: self.ocr_button.setEnabled(False); self.ocr_button.setToolTip("请安装完整依赖包以启用OCR功能")
        self.ocr_button.setStyleSheet(f"""QPushButton {{ background-color: {UI_COLORS["primary"]}; color: white; font-weight: bold; border: none; min-height: 25px; }} QPushButton:hover {{ background-color: {UI_COLORS["secondary"]}; }} QPushButton:disabled {{ background-color: #cccccc; color: #666666; }}""")
        row3_layout.addWidget(self.ocr_button); self.create_all_btn = QPushButton("全部标注"); self.create_all_btn.setMaximumWidth(80); row3_layout.addWidget(self.create_all_btn); self.clear_ocr_btn = QPushButton("清除OCR"); self.clear_ocr_btn.setMaximumWidth(80); row3_layout.addWidget(self.clear_ocr_btn); ocr_layout.addLayout(row3_layout)
        self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); self.progress_bar.setMaximumHeight(15); ocr_layout.addWidget(self.progress_bar); self.ocr_stats_label = QLabel("识别结果: 0个文本"); self.ocr_stats_label.setStyleSheet("QLabel { background-color: transparent; border: none; padding: 4px; color: #6c757d; font-size: 11px; }"); ocr_layout.addWidget(self.ocr_stats_label)
        filter_layout = QHBoxLayout(); filter_layout.addWidget(QLabel("筛选:")); self.filter_combo = QComboBox(); self.filter_combo.addItems(OCR_FILTER_OPTIONS); filter_layout.addWidget(self.filter_combo); filter_layout.addStretch(); ocr_layout.addLayout(filter_layout)
        parent_layout.addWidget(ocr_widget)

    def center_view(self):
        """确保图像在视图中居中显示"""
        if self.graphics_scene.items():
            # 计算场景中所有项目的边界矩形
            rect = self.graphics_scene.itemsBoundingRect()
            # 确保矩形有效
            if not rect.isEmpty():
                # 调整视图以适应并居中显示场景内容
                self.graphics_view.fitInView(rect, Qt.KeepAspectRatio)
                print("已将图像居中显示")
    
    def resizeEvent(self, event):
        """窗口大小调整时重新居中图像"""
        super().resizeEvent(event)
        # 使用延迟调用，确保在UI更新后执行
        QTimer.singleShot(100, self.center_view)