#!/usr/bin/env python3
"""
标注列表模块
"""

from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal


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
        
    def add_annotation(self, annotation):
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