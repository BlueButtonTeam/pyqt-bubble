# ui/annotation_list.py

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

# 导入我们的数据模型类
from core.annotation_item import BubbleAnnotationItem

class AnnotationTable(QTableWidget):
    """
    一个用于显示结构化标注数据的表格视图。
    - 调整了审核状态列的宽度
    - 显示审核状态的勾号
    """
    annotation_selected = Signal(int)

    def __init__(self):
        super().__init__()
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(["序号", "类型", "尺寸", "上公差", "下公差", "审核"]) # Header文字改短
        
        self.setup_style()
        self.setup_behavior()

        self.itemClicked.connect(self._on_item_clicked)

    def setup_style(self):
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        
        header = self.horizontalHeader()
        # --- 核心修改：调整列宽 ---
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        # 将最后一列（审核状态）设置为固定宽度，使其变窄
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed) 
        self.setColumnWidth(5, 50) # 设置一个合适的宽度，例如50像素
        # ---------------------------
        
        self.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 3px;
                font-size: 12px;
                gridline-color: #e9ecef;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 4px;
                border: 1px solid #dee2e6;
                font-weight: bold;
                color: #495057;
            }
            QTableWidget::item {
                padding-left: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e7f3ff;
                color: #005cbf;
            }
        """)

    def setup_behavior(self):
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def add_annotation(self, annotation: BubbleAnnotationItem, parsed_data: dict):
        row_position = self.rowCount()
        self.insertRow(row_position)

        id_item = QTableWidgetItem(str(annotation.annotation_id))
        id_item.setData(Qt.ItemDataRole.UserRole, annotation.annotation_id)
        self.setItem(row_position, 0, id_item)
        
        self.setItem(row_position, 1, QTableWidgetItem(annotation.dimension_type))
        self.setItem(row_position, 2, QTableWidgetItem(annotation.dimension))
        self.setItem(row_position, 3, QTableWidgetItem(annotation.upper_tolerance))
        self.setItem(row_position, 4, QTableWidgetItem(annotation.lower_tolerance))
        
        # --- 新增：处理审核状态列 ---
        audit_text = "✅" if annotation.is_audited else ""
        audit_item = QTableWidgetItem(audit_text)
        audit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter) # 居中显示勾号
        self.setItem(row_position, 5, audit_item)
        # ---------------------------

        tooltip_text = f"标注 {annotation.annotation_id}\n原始文本: {annotation.text}"
        for col in range(self.columnCount()):
            self.item(row_position, col).setToolTip(tooltip_text)

    def clear_annotations(self):
        self.setRowCount(0)

    def _on_item_clicked(self, item: QTableWidgetItem):
        id_item = self.item(item.row(), 0)
        if id_item:
            annotation_id = id_item.data(Qt.ItemDataRole.UserRole)
            if annotation_id is not None:
                self.annotation_selected.emit(annotation_id)

    def highlight_annotation(self, annotation_id: int):
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == annotation_id:
                self.selectRow(row)
                break

    def update_annotation_data(self, annotation: BubbleAnnotationItem):
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == annotation.annotation_id:
                # 更新这一行的所有相关数据
                self.item(row, 1).setText(annotation.dimension_type)
                self.item(row, 2).setText(annotation.dimension)
                self.item(row, 3).setText(annotation.upper_tolerance)
                self.item(row, 4).setText(annotation.lower_tolerance)
                
                # --- 新增：更新审核状态列 ---
                audit_text = "✅" if annotation.is_audited else ""
                self.item(row, 5).setText(audit_text)
                self.item(row, 5).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # ---------------------------
                
                self.item(row,0).setToolTip(f"标注 {annotation.annotation_id}\n原始文本: {annotation.text}")
                break   