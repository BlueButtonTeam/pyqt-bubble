#!/usr/bin/env python3
"""
自定义图形视图模块
"""

from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter

from utils.constants import MIN_SELECTION_AREA


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
            if (self._selection_rect.width() > MIN_SELECTION_AREA and 
                self._selection_rect.height() > MIN_SELECTION_AREA):  # 最小选择区域
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
            from PySide6.QtGui import QPainter, QPen, QBrush, QColor
            
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor(0, 120, 215), 2, Qt.DashLine))
            painter.setBrush(QBrush(QColor(0, 120, 215, 30)))
            
            # 转换场景坐标到视图坐标
            view_rect = self.mapFromScene(self._selection_rect).boundingRect()
            painter.drawRect(view_rect)
            painter.end() 