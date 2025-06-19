# ui/property_editor.py (支持大小显示版)

from typing import Optional
from datetime import datetime

from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLabel, QTextEdit, QHBoxLayout
from PySide6.QtCore import QPointF, Signal
from PySide6.QtGui import QColor, QPalette

class PropertyEditor(QWidget):
    """
    属性编辑器 - 支持显示大小、颜色、形状
    """
    text_changed = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.current_annotation = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 基本信息组
        basic_group = QWidget()
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(8)
        
        self.id_label = QLabel("无")
        self.id_label.setStyleSheet("font-weight: bold; color: #0066cc; background-color: transparent; border: none;")
        basic_layout.addRow("标注编号:", self.id_label)
        
        self.position_label = QLabel("无")
        basic_layout.addRow("坐标位置:", self.position_label)
        
        # --- 新增/修改的显示行 ---
        self.shape_label = QLabel("无")
        basic_layout.addRow("形状:", self.shape_label)
        
        color_container = QWidget()
        color_layout = QHBoxLayout(color_container)
        color_layout.setContentsMargins(0, 0, 0, 0)
        self.color_swatch = QLabel()
        self.color_swatch.setFixedSize(16, 16)
        self.color_swatch.setAutoFillBackground(True)
        self.color_swatch.setStyleSheet("border: 1px solid #cccccc; border-radius: 3px;")
        self.color_label = QLabel("N/A")
        color_layout.addWidget(self.color_swatch)
        color_layout.addWidget(self.color_label)
        color_layout.addStretch()
        basic_layout.addRow("颜色/样式:", color_container)

        self.size_label = QLabel("无")
        basic_layout.addRow("大小 (半径):", self.size_label)
        # -------------------------

        layout.addWidget(basic_group)
        
        # 分隔线
        separator = QLabel(); separator.setFixedHeight(1); separator.setStyleSheet("background-color: #cccccc; margin: 10px 0;"); layout.addWidget(separator)
        
        # 文本编辑区域
        text_group = QWidget(); text_layout = QVBoxLayout(text_group)
        text_label = QLabel("标注描述:"); text_label.setStyleSheet("font-weight: bold; color: #495057; background-color: transparent; border: none;"); text_layout.addWidget(text_label)
        self.text_edit = QTextEdit(); self.text_edit.setMaximumHeight(120); self.text_edit.textChanged.connect(self._on_text_changed); text_layout.addWidget(self.text_edit)
        layout.addWidget(text_group)
        
        # 统计信息区域
        stats_group = QWidget(); stats_layout = QFormLayout(stats_group); stats_layout.setSpacing(5)
        self.char_count_label = QLabel("0"); stats_layout.addRow("字符数:", self.char_count_label)
        self.created_time_label = QLabel("无"); stats_layout.addRow("创建时间:", self.created_time_label)
        layout.addWidget(stats_group)
        
        layout.addStretch()
        
        self.setStyleSheet("""
            QWidget { font-size: 12px; color: #495057; background-color: #ffffff; }
            QLabel { color: #495057; background-color: transparent; border: none; padding: 2px; }
            QTextEdit { border: 1px solid #ced4da; border-radius: 4px; padding: 8px; background-color: #ffffff; color: #495057; font-family: "Microsoft YaHei", "Consolas", monospace; }
            QTextEdit:focus { border-color: #0066cc; box-shadow: 0 0 0 0.2rem rgba(0, 102, 204, 0.25); }
        """)
    
    def set_annotation(self, annotation):
        """【已修改】更新所有属性，包括大小"""
        self.current_annotation = annotation
        if annotation:
            # ID 和 位置
            self.id_label.setText(str(annotation.annotation_id))
            pos = annotation.pos()
            self.position_label.setText(f"({pos.x():.1f}, {pos.y():.1f})")
            
            # 形状
            shape_map = {"circle": "空心圆", "solid_circle": "实心圆", "pentagram": "五角星", "triangle": "三角形"}
            self.shape_label.setText(shape_map.get(getattr(annotation, 'shape_type', 'circle'), "未知形状"))

            # 颜色
            style_map = {"default": "默认", "warning": "警告", "error": "错误", "success": "成功", "custom": "自定义"}
            color_to_display = QColor("transparent")
            label_text = "N/A"
            if annotation.custom_color and annotation.custom_color.isValid():
                color_to_display = annotation.custom_color
                label_text = f"自定义 ({color_to_display.name()})"
            else:
                label_text = style_map.get(annotation.style, "未知样式")
                colors = annotation.get_style_colors()
                color_to_display = colors.get('normal_pen', QColor("transparent"))
            palette = self.color_swatch.palette(); palette.setColor(QPalette.Window, color_to_display); self.color_swatch.setPalette(palette)
            self.color_label.setText(label_text)

            # 大小
            self.size_label.setText(str(getattr(annotation, 'radius', '未知')))

            # 其他信息
            self.text_edit.blockSignals(True); self.text_edit.setPlainText(annotation.text); self.text_edit.blockSignals(False)
            self.char_count_label.setText(str(len(annotation.text)))
            self.created_time_label.setText(datetime.now().strftime("%H:%M:%S"))
            self.setEnabled(True)
        else:
            # 清空所有字段
            self.id_label.setText("无"); self.position_label.setText("无"); self.shape_label.setText("无"); self.size_label.setText("无")
            self.text_edit.clear(); self.char_count_label.setText("0"); self.created_time_label.setText("无")
            palette = self.color_swatch.palette(); palette.setColor(QPalette.Window, QColor("transparent")); self.color_swatch.setPalette(palette)
            self.color_label.setText("N/A")
            self.setEnabled(False)
    
    def _on_text_changed(self):
        if self.current_annotation:
            new_text = self.text_edit.toPlainText()
            self.text_changed.emit(new_text)
            self.char_count_label.setText(str(len(new_text)))
    
    def update_position(self, position: QPointF):
        self.position_label.setText(f"({position.x():.1f}, {position.y():.1f})")