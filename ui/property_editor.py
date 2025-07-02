# ui/property_editor.py

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox, QGroupBox, QPushButton
)
from PySide6.QtCore import Qt, QRectF, Signal, QEvent
from PySide6.QtGui import QPixmap, QColor, QPainter, QPen

# 导入我们的数据模型类，以便类型提示
from core.annotation_item import BubbleAnnotationItem

class PropertyEditor(QWidget):
    """
    属性编辑器 - 新版
    - 移除了预览图的十字准星
    - 支持在预览图上用鼠标滚轮缩放
    """
    
    audit_requested = Signal()
    delete_requested = Signal()

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.current_annotation: Optional[BubbleAnnotationItem] = None
        self.original_pixmap: Optional[QPixmap] = None
        # --- 新增：用于控制预览图的缩放系数 ---
        self.preview_zoom_factor = 1.0
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # 1. 区域预览组
        preview_group = QGroupBox("区域预览 (滚动滚轮缩放)") # 修改标题提示用户
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("未选择标注")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(120)
        self.preview_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #cccccc; border-radius: 4px;")
        preview_layout.addWidget(self.preview_label)
        main_layout.addWidget(preview_group)
        
        # --- 新增：为预览标签安装事件过滤器 ---
        self.preview_label.installEventFilter(self)

        # 2. 属性编辑组
        properties_group = QGroupBox("属性编辑")
        form_layout = QFormLayout(properties_group)
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.id_label = QLabel("无")
        form_layout.addRow("标注编号:", self.id_label)

        self.dimension_edit = QLineEdit()
        form_layout.addRow("尺寸:", self.dimension_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["", "线性", "直径(Φ)", "半径(R)", "螺纹", "角度(°)", "其他"])
        form_layout.addRow("尺寸类型:", self.type_combo)

        self.upper_tol_edit = QLineEdit()
        form_layout.addRow("上公差:", self.upper_tol_edit)

        self.lower_tol_edit = QLineEdit()
        form_layout.addRow("下公差:", self.lower_tol_edit)
        
        main_layout.addWidget(properties_group)

        self.audit_button = QPushButton("✅ 审核")
        self.audit_button.setToolTip("将当前项标记为已审核，并跳转到下一项 (F2)")
        self.audit_button.setStyleSheet(f"QPushButton {{ background-color: #28a745; color: white; font-weight: bold; padding: 8px; }} QPushButton:hover {{ background-color: #218838; }} QPushButton:disabled {{ background-color: #e9ecef; color: #6c757d; }}")
        main_layout.addWidget(self.audit_button)
        
        # 添加删除按钮
        self.delete_button = QPushButton("🗑️ 删除")
        self.delete_button.setToolTip("删除当前选中的标注项")
        self.delete_button.setStyleSheet(f"QPushButton {{ background-color: #dc3545; color: white; font-weight: bold; padding: 8px; }} QPushButton:hover {{ background-color: #c82333; }} QPushButton:disabled {{ background-color: #e9ecef; color: #6c757d; }}")
        main_layout.addWidget(self.delete_button)
        
        # 连接信号和槽
        self.dimension_edit.editingFinished.connect(self._on_dimension_changed)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.upper_tol_edit.editingFinished.connect(self._on_upper_tol_changed)
        self.lower_tol_edit.editingFinished.connect(self._on_lower_tol_changed)
        self.audit_button.clicked.connect(self.audit_requested.emit)
        self.delete_button.clicked.connect(self.delete_requested.emit)
        
        main_layout.addStretch()
        
        self.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; 
                border: 1px solid #cccccc; 
                border-radius: 5px; 
                margin-top: 10px; 
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                subcontrol-position: top center; 
                padding: 0 5px; 
                background-color: #f8f9fa; 
            }
            QWidget { 
                font-size: 12px; 
                color: #495057; 
            }
            QLabel { 
                color: #495057; 
                padding: 2px;
                background-color: transparent;
                border: none;
            }
            QLineEdit, QComboBox { 
                border: 1px solid #ced4da; 
                border-radius: 4px; 
                padding: 5px; 
                background-color: #ffffff; 
            }
            QLineEdit:focus, QComboBox:focus { 
                border-color: #0066cc; 
            }
            QLineEdit:disabled, QComboBox:disabled { 
                background-color: #e9ecef; 
            }
        """)

        self.setEnabled(False)

    def eventFilter(self, watched, event: QEvent) -> bool:
        """【新增】事件过滤器，用于处理预览标签上的鼠标滚轮事件"""
        if watched is self.preview_label and event.type() == QEvent.Type.Wheel:
            # 滚轮向上滚动，放大
            if event.angleDelta().y() > 0:
                self.preview_zoom_factor *= 1.2
            # 滚轮向下滚动，缩小
            else:
                self.preview_zoom_factor /= 1.2
            
            # 限制缩放范围，防止过大或过小
            self.preview_zoom_factor = max(0.2, min(self.preview_zoom_factor, 10.0))
            
            # 更新预览
            self.update_preview()
            return True # 事件已处理，不再传递
            
        return super().eventFilter(watched, event)

    def set_annotation(self, annotation: Optional[BubbleAnnotationItem], pixmap: Optional[QPixmap]):
        self.current_annotation = annotation
        self.original_pixmap = pixmap
        
        # --- 修改：每次选中新标注时，重置缩放系数 ---
        self.preview_zoom_factor = 1.0

        if annotation:
            self.block_signals(True)
            self.id_label.setText(str(annotation.annotation_id))
            self.dimension_edit.setText(annotation.dimension)
            self.type_combo.setCurrentText(annotation.dimension_type)
            self.upper_tol_edit.setText(annotation.upper_tolerance)
            self.lower_tol_edit.setText(annotation.lower_tolerance)
            self.block_signals(False)

            self.update_preview()
            self.setEnabled(True)
        else:
            self.block_signals(True)
            self.id_label.setText("无")
            self.dimension_edit.clear()
            self.type_combo.setCurrentIndex(0)
            self.upper_tol_edit.clear()
            self.lower_tol_edit.clear()
            self.preview_label.setText("未选择标注")
            self.preview_label.setPixmap(QPixmap())
            self.block_signals(False)
            self.setEnabled(False)

    def update_preview(self):
        if not self.current_annotation or not self.original_pixmap:
            self.preview_label.setText("无预览可用")
            self.preview_label.setPixmap(QPixmap())
            return

        # 定义预览区域的基础大小
        base_preview_width = 200
        base_preview_height = 150
        
        # --- 修改：根据缩放系数计算实际要截取的区域大小 ---
        crop_width = base_preview_width / self.preview_zoom_factor
        crop_height = base_preview_height / self.preview_zoom_factor
        
        anchor_pos = self.current_annotation.anchor_point
        
        crop_rect = QRectF(
            anchor_pos.x() - crop_width / 2,
            anchor_pos.y() - crop_height / 2,
            crop_width,
            crop_height
        ).toRect().intersected(self.original_pixmap.rect())

        if crop_rect.isEmpty():
            self.preview_label.setText("预览区域无效")
            self.preview_label.setPixmap(QPixmap())
            return
        
        cropped_pixmap = self.original_pixmap.copy(crop_rect)
        
        # --- 移除：绘制十字准星的代码 ---
        # painter = QPainter(cropped_pixmap)
        # ...
        # painter.end()
        
        scaled_pixmap = cropped_pixmap.scaled(
            self.preview_label.width() - 10,
            self.preview_label.height() - 10,
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled_pixmap)

    def block_signals(self, block: bool):
        self.dimension_edit.blockSignals(block)
        self.type_combo.blockSignals(block)
        self.upper_tol_edit.blockSignals(block)
        self.lower_tol_edit.blockSignals(block)
        self.audit_button.blockSignals(block)
        self.delete_button.blockSignals(block)

    def _on_dimension_changed(self):
        if self.current_annotation:
            new_dimension = self.dimension_edit.text()
            if new_dimension != self.current_annotation.dimension:
                self.current_annotation.set_dimension(new_dimension)

    def _on_type_changed(self, text: str):
        if self.current_annotation:
            if text != self.current_annotation.dimension_type:
                self.current_annotation.set_dimension_type(text)

    def _on_upper_tol_changed(self):
        if self.current_annotation:
            new_value = self.upper_tol_edit.text()
            if new_value != self.current_annotation.upper_tolerance:
                self.current_annotation.set_upper_tolerance(new_value)
    
    def _on_lower_tol_changed(self):
        if self.current_annotation:
            new_value = self.lower_tol_edit.text()
            if new_value != self.current_annotation.lower_tolerance:
                self.current_annotation.set_lower_tolerance(new_value)