#!/usr/bin/env python3
"""
自定义图形视图模块
"""

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPathItem, 
    QGraphicsRectItem, QGraphicsObject, QGraphicsItem
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QEvent, QTimer
from PySide6.QtGui import QPainter, QTransform, QPainterPath, QPen, QBrush, QColor
import logging
import numpy as np
import time

from utils.constants import MIN_SELECTION_AREA

# 配置日志
logger = logging.getLogger("GraphicsView")

class ResizableGraphicsPathItem(QGraphicsObject):
    """
    可调整大小的路径图形项，用于OCR识别框
    支持通过拖拽边框的任意边调整大小
    """
    
    # 边缘检测的敏感范围（像素）
    EDGE_SENSITIVITY = 8
    
    # 添加信号用于通知框调整大小
    bbox_updated = Signal(object)
    
    def __init__(self, path=None, parent=None):
        super().__init__(parent)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.setAcceptHoverEvents(True)
        
        # 存储路径
        self._path = QPainterPath()
        if path:
            self._path = QPainterPath(path)
        
        # 初始化调整大小的状态变量
        self.edge_selected = None
        self.mouse_pressed = False
        self.original_path = None
        self.original_rect = None
        
        # 当前鼠标位置在哪个边
        # None: 不在边上
        # 'top', 'right', 'bottom', 'left': 四条边
        # 'top-left', 'top-right', 'bottom-right', 'bottom-left': 四个角
        self.current_edge = None
        
        # 如果初始化时有路径，保存原始矩形
        if path:
            self.original_rect = path.boundingRect()
            
        # 初始化关联气泡标注列表
        self.associated_annotations = []
        
        # 初始化pen和brush
        self._pen = QPen(QColor(91, 192, 235, 120), 2)
        self._brush = QBrush(QColor(91, 192, 235, 120))
        
        # 添加操作状态跟踪，防止同时调整大小和移动
        self._is_resizing = False
        self._is_moving = False
        
        # 防抖保护：上次发送信号的时间
        self._last_update_time = time.time()
        # 防抖延迟（毫秒）
        self._debounce_delay = 50  # 毫秒

    def boundingRect(self):
        """重写boundingRect方法"""
        return self._path.boundingRect()
        
    def paint(self, painter, option, widget):
        """重写paint方法，绘制路径"""
        painter.setPen(self._pen)
        painter.setBrush(self._brush)
        painter.drawPath(self._path)
        
    def path(self):
        """返回当前路径"""
        return self._path
        
    def setPath(self, path):
        """设置路径"""
        self._path = QPainterPath(path)
        self.original_rect = path.boundingRect()
        self.update()
        
    def setPen(self, pen):
        """设置画笔"""
        self._pen = pen
        self.update()
        
    def setBrush(self, brush):
        """设置画刷"""
        self._brush = brush
        self.update()
        
    def shape(self):
        """返回形状，用于碰撞检测"""
        return self._path
        
    def itemChange(self, change, value):
        """处理项目变化，包括位置变化"""
        # 当位置改变完成后，确保发送更新信号
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            # 发送通知信号
            if hasattr(self, 'ocr_result') and 'bbox' in self.ocr_result:
                try:
                    # 使用防抖保护发送信号
                    current_time = time.time()
                    if not hasattr(self, '_last_update_time'):
                        self._last_update_time = 0
                    if not hasattr(self, '_debounce_delay'):
                        self._debounce_delay = 50
                        
                    if (current_time - self._last_update_time) * 1000 > self._debounce_delay:
                        self.bbox_updated.emit(self)
                        self._last_update_time = current_time
                except Exception as e:
                    print(f"在itemChange中发送更新信号时出错: {e}")
                
        return super().itemChange(change, value)
    
    def hoverMoveEvent(self, event):
        """鼠标在项目上移动事件，检测是否靠近边缘并更新光标"""
        # 获取当前边界矩形
        rect = self.path().boundingRect()
        pos = event.pos()
        
        # 计算到各边的距离
        dist_left = abs(pos.x() - rect.left())
        dist_right = abs(pos.x() - rect.right())
        dist_top = abs(pos.y() - rect.top())
        dist_bottom = abs(pos.y() - rect.bottom())
        
        # 检查是否在边缘附近
        near_left = dist_left < self.EDGE_SENSITIVITY
        near_right = dist_right < self.EDGE_SENSITIVITY
        near_top = dist_top < self.EDGE_SENSITIVITY
        near_bottom = dist_bottom < self.EDGE_SENSITIVITY
        
        # 确定鼠标在哪个边或角
        if near_top and near_left:
            self.current_edge = 'top-left'
            self.setCursor(Qt.SizeFDiagCursor)
        elif near_top and near_right:
            self.current_edge = 'top-right'
            self.setCursor(Qt.SizeBDiagCursor)
        elif near_bottom and near_right:
            self.current_edge = 'bottom-right'
            self.setCursor(Qt.SizeFDiagCursor)
        elif near_bottom and near_left:
            self.current_edge = 'bottom-left'
            self.setCursor(Qt.SizeBDiagCursor)
        elif near_top:
            self.current_edge = 'top'
            self.setCursor(Qt.SizeVerCursor)
        elif near_right:
            self.current_edge = 'right'
            self.setCursor(Qt.SizeHorCursor)
        elif near_bottom:
            self.current_edge = 'bottom'
            self.setCursor(Qt.SizeVerCursor)
        elif near_left:
            self.current_edge = 'left'
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.current_edge = None
            self.setCursor(Qt.ArrowCursor)
        
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        """鼠标离开事件"""
        self.current_edge = None
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        self.mouse_pressed = True
        
        # 如果在边缘，准备调整大小
        if self.current_edge is not None:
            self._is_resizing = True
            self._is_moving = False
            self.edge_selected = self.current_edge
            self.original_path = self.path()
            self.original_rect = self.path().boundingRect()
            event.accept()
        else:
            # 否则调用父类处理拖动
            self._is_moving = True
            self._is_resizing = False
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._is_resizing and self.edge_selected is not None:
            # 调整大小
            self.resizeByEdge(event.pos())
            event.accept()
        elif self._is_moving:
            # 移动项目之前的位置
            old_pos = self.pos()
            
            # 移动项目
            super().mouseMoveEvent(event)
            
            # 计算位移
            new_pos = self.pos()
            delta_x = new_pos.x() - old_pos.x()
            delta_y = new_pos.y() - old_pos.y()
            
            # 如果是在拖动（而不是调整大小）且发生了实际移动
            if hasattr(self, 'ocr_result') and (delta_x != 0 or delta_y != 0):
                try:
                    # 更新OCR结果中心点
                    if 'center_x' in self.ocr_result and 'center_y' in self.ocr_result:
                        rect = self._path.boundingRect()
                        self.ocr_result['center_x'] = rect.center().x()
                        self.ocr_result['center_y'] = rect.center().y()
                    
                    # 更新OCR结果中的bbox
                    if 'bbox' in self.ocr_result:
                        # 创建一个新的bbox列表，更新每个点的坐标
                        new_bbox = []
                        for point in self.ocr_result['bbox']:
                            new_bbox.append([point[0] + delta_x, point[1] + delta_y])
                        
                        # 更新OCR结果中的bbox
                        self.ocr_result['bbox'] = new_bbox
                    
                    # 使用防抖保护发送信号
                    current_time = time.time()
                    if (current_time - self._last_update_time) * 1000 > self._debounce_delay:
                        self.bbox_updated.emit(self)
                        self._last_update_time = current_time
                except Exception as e:
                    print(f"在移动OCR框时更新数据时出错: {e}")
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        self.mouse_pressed = False
        
        if self._is_resizing and self.edge_selected is not None:
            self.edge_selected = None
            self._is_resizing = False
            event.accept()
            
            # 在释放时确保发送一次更新信号
            if hasattr(self, 'ocr_result') and 'bbox' in self.ocr_result:
                try:
                    # 强制更新一次，不考虑防抖
                    self._last_update_time = 0  # 重置上次更新时间
                    self.bbox_updated.emit(self)
                except Exception as e:
                    print(f"调整大小后发送更新信号时出错: {e}")
        else:
            # 处理拖拽移动后的释放
            was_moving = self._is_moving and event.button() == Qt.LeftButton
            self._is_moving = False
            super().mouseReleaseEvent(event)
            
            # 在释放时确保发送一次更新信号
            if was_moving and hasattr(self, 'ocr_result') and 'bbox' in self.ocr_result:
                try:
                    # 强制更新一次，不考虑防抖
                    self._last_update_time = 0  # 重置上次更新时间
                    self.bbox_updated.emit(self)
                except Exception as e:
                    print(f"移动后发送更新信号时出错: {e}")
    
    def resizeByEdge(self, pos):
        """根据边缘调整大小"""
        try:
            if not self.original_rect:
                return
                
            # 获取当前边界矩形
            rect = QRectF(self.original_rect)
            
            # 根据选中的边缘调整大小
            if self.edge_selected == 'top-left':
                rect.setTopLeft(pos)
            elif self.edge_selected == 'top-right':
                rect.setTopRight(pos)
            elif self.edge_selected == 'bottom-right':
                rect.setBottomRight(pos)
            elif self.edge_selected == 'bottom-left':
                rect.setBottomLeft(pos)
            elif self.edge_selected == 'top':
                rect.setTop(pos.y())
            elif self.edge_selected == 'right':
                rect.setRight(pos.x())
            elif self.edge_selected == 'bottom':
                rect.setBottom(pos.y())
            elif self.edge_selected == 'left':
                rect.setLeft(pos.x())
            else:
                # 未知边缘，不做处理
                return
            
            # 确保矩形不会太小
            if rect.width() < 10 or rect.height() < 10:
                return
            
            # 创建新的路径
            path = QPainterPath()
            path.moveTo(rect.topLeft())
            path.lineTo(rect.topRight())
            path.lineTo(rect.bottomRight())
            path.lineTo(rect.bottomLeft())
            path.closeSubpath()
            
            # 设置新路径
            self.setPath(path)
            
            try:
                # 更新OCR结果中的bbox
                if hasattr(self, 'ocr_result') and self.ocr_result:
                    # 获取新的bbox坐标 - 考虑图形项的位置
                    pos = self.pos()
                    self.ocr_result['bbox'] = [
                        [rect.left() + pos.x(), rect.top() + pos.y()],
                        [rect.right() + pos.x(), rect.top() + pos.y()],
                        [rect.right() + pos.x(), rect.bottom() + pos.y()],
                        [rect.left() + pos.x(), rect.bottom() + pos.y()]
                    ]
                    
                    # 更新中心点（如果存在）
                    if 'center_x' in self.ocr_result and 'center_y' in self.ocr_result:
                        self.ocr_result['center_x'] = rect.center().x() + pos.x()
                        self.ocr_result['center_y'] = rect.center().y() + pos.y()
                    
                    # 使用防抖保护发送信号
                    current_time = time.time()
                    if (current_time - self._last_update_time) * 1000 > self._debounce_delay:
                        if hasattr(self, 'associated_annotations') and self.associated_annotations:
                            # 设置一个标志，表示这是调整大小产生的更新
                            self._update_from_resize = True
                            self.bbox_updated.emit(self)
                            self._last_update_time = current_time
            except Exception as e:
                print(f"更新OCR结果数据时出错: {e}")
        except Exception as e:
            print(f"调整大小时出错: {e}")

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