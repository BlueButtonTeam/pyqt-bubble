#!/usr/bin/env python3
"""
自定义图形视图模块
"""

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QEvent
from PySide6.QtGui import QPainter, QTransform
import logging

from utils.constants import MIN_SELECTION_AREA

# 配置日志
logger = logging.getLogger("GraphicsView")

class GraphicsView(QGraphicsView):
    """
    自定义图形视图，支持缩放、平移和强制居中
    """
    # 添加信号
    area_selected = Signal(QRectF)  # 区域选择信号
    
    def __init__(self):
        super().__init__()
        # 设置更优的图像渲染选项
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        
        # 关键：设置转换锚点，确保缩放基于鼠标位置而不是视图中心
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        
        # 设置拖拽模式
        self.setDragMode(QGraphicsView.RubberBandDrag)
        
        # 设置视口更新模式，确保正确更新
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # 使用最佳适应大小策略，并保持滚动条可用
        self.setSizeAdjustPolicy(QGraphicsView.AdjustToContents)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 添加拖拽状态跟踪
        self._is_dragging = False
        self._drag_start_pos = None
        
        # 添加选择模式
        self._selection_mode = False
        self._selection_start = None
        self._selection_rect = None
        
        # 创建一个默认场景
        empty_scene = QGraphicsScene(self)
        self.setScene(empty_scene)
        
        # 安装事件过滤器，用于处理额外的事件
        self.viewport().installEventFilter(self)
        
    def centerContent(self):
        """强制居中显示场景内容"""
        if not self.scene() or not self.scene().items():
            logger.debug("场景为空，不执行居中")
            return
        
        # 获取场景的所有项目的边界矩形
        scene_rect = self.scene().itemsBoundingRect()
        if scene_rect.isEmpty():
            logger.debug("场景矩形为空，不执行居中")
            return
        
        # 记录原始变换和中心点
        logger.debug(f"执行centerContent: 场景尺寸={scene_rect.width()}x{scene_rect.height()}, 视图尺寸={self.viewport().width()}x{self.viewport().height()}")
        
        # 重置变换以确保从干净状态开始
        self.resetTransform()
        
        # 应用适合视图的变换，保持纵横比
        self.fitInView(scene_rect, Qt.KeepAspectRatio)
        
        # 确保使用准确的场景中心点进行居中
        exact_center = scene_rect.center()
        self.centerOn(exact_center)
        
        # 强制立即更新
        self.viewport().update()
        
        logger.debug(f"居中完成: 场景中心={exact_center.x()},{exact_center.y()}")
    
    def showEvent(self, event):
        """窗口显示时居中内容"""
        super().showEvent(event)
        self.centerContent()
    
    def resizeEvent(self, event):
        """窗口大小变化时居中内容"""
        super().resizeEvent(event)
        
        # 如果没有内容，不需要处理
        if not self.scene() or not self.scene().items():
            return
            
        # 我们不希望在每次调整窗口大小时都重置缩放和居中
        # 这会干扰用户的缩放操作
        
        # 因此这里不再调用centerContent或使用定时器
        logger.debug("窗口大小已改变，但不自动重置缩放以避免干扰用户操作")
    
    def set_selection_mode(self, enabled: bool):
        """设置区域选择模式"""
        self._selection_mode = enabled
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if self._selection_mode and event.button() == Qt.LeftButton:
            # 区域选择模式
            self._selection_start = self.mapToScene(event.position().toPoint())
            self._selection_rect = QRectF(self._selection_start, self._selection_start)
            event.accept()
            return
        elif event.button() == Qt.MiddleButton:
            # 中键拖拽
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif event.button() == Qt.RightButton:
            # 右键拖拽
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
            self.viewport().update()
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
                self._selection_rect.height() > MIN_SELECTION_AREA):
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
            
    def eventFilter(self, obj, event):
        """事件过滤器，用于捕获其他可能影响居中的事件"""
        if obj is self.viewport():
            if event.type() == QEvent.UpdateRequest:
                # 视口请求更新时，检查是否需要重新居中
                pass
        return super().eventFilter(obj, event)
    
    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        if not self.scene() or not self.scene().items():
            event.accept()
            return
        
        # 添加日志
        delta = event.angleDelta().y()
        logger.debug(f"收到滚轮事件，delta={delta}，应用缩放")
        
        # 计算缩放因子，使用较小的值以获得更平滑的缩放
        factor = 1.1
        if delta < 0:
            factor = 1.0 / factor
        
        # 获取鼠标位置
        mouse_pos = event.position()
        
        # 保存鼠标在场景中的位置
        scene_pos = self.mapToScene(mouse_pos.toPoint())
        
        # 应用缩放
        self.scale(factor, factor)
        
        # 确保鼠标位置在场景中不变
        new_pos = self.mapFromScene(scene_pos)
        delta = new_pos - mouse_pos.toPoint()
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + delta.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta.y())
        
        # 阻止事件继续传递
        event.accept()
        logger.debug(f"完成缩放操作，阻止事件传递") 