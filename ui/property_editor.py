#!/usr/bin/env python3
"""
属性编辑器模块
"""

from typing import Optional
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLabel, QTextEdit
from PySide6.QtCore import QPointF, Signal


class PropertyEditor(QWidget):
    """
    属性编辑器
    """
    text_changed = Signal(str)  # 文本改变信号
    
    def __init__(self):
        super().__init__()
        self.current_annotation = None
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
    
    def set_annotation(self, annotation):
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