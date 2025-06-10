#!/usr/bin/env python3
"""
气泡标注项模块
"""

from typing import Dict
from PySide6.QtWidgets import QGraphicsObject, QMenu
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont

from utils.constants import (
    ANNOTATION_STYLES, DEFAULT_CIRCLE_RADIUS, DEFAULT_LEADER_LENGTH
)


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
        self.circle_radius = DEFAULT_CIRCLE_RADIUS
        self.leader_length = DEFAULT_LEADER_LENGTH
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
        
    def get_style_colors(self) -> Dict[str, QColor]:
        """根据样式获取颜色"""
        style_config = ANNOTATION_STYLES.get(self.style, ANNOTATION_STYLES["default"])
        
        colors = {}
        for key, rgba in style_config.items():
            if len(rgba) == 3:
                colors[key] = QColor(*rgba)
            else:
                colors[key] = QColor(*rgba)
        
        return colors
        
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