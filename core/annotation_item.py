# core/annotation_item.py

import math
from typing import Optional

from PySide6.QtWidgets import QGraphicsObject, QMenu, QColorDialog
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath, QFont, QPolygonF, QPainterPathStroker
)

class BubbleAnnotationItem(QGraphicsObject):
    """
    【功能增强版】气泡标注图形项
    - 新增审核状态属性
    """
    # --- 已有信号 ---
    size_change_requested = Signal(object)
    shape_change_requested = Signal(object)
    style_change_requested = Signal(object)
    color_change_requested = Signal(object)
    selected = Signal(object)
    moved = Signal(object, QPointF)
    delete_requested = Signal(object)
    data_updated = Signal(object)

    def __init__(self, annotation_id: int, anchor_point: QPointF, text: str = "", style: str = "default", 
                 shape: str = "circle", color: Optional[QColor] = None, size: int = 15,
                 dimension: str = "", dimension_type: str = "", 
                 upper_tolerance: str = "", lower_tolerance: str = "",
                 # --- 新增属性 ---
                 is_audited: bool = False):
        super().__init__()
        self.annotation_id = annotation_id
        self.text = text or f"标注 {annotation_id}"
        self.style = style
        self.arrow_head_size = 10
        self.shape_type = shape
        self.custom_color = color
        self.radius = size
        
        self.dimension = dimension
        self.dimension_type = dimension_type
        self.upper_tolerance = upper_tolerance
        self.lower_tolerance = lower_tolerance
        
        # --- 初始化新增属性 ---
        self.is_audited = is_audited
        
        self.anchor_point = anchor_point
        self._is_highlighted = False
        self._cached_shape_path = QPainterPath()

        self.setFlags(
            QGraphicsObject.ItemIsSelectable | QGraphicsObject.ItemIsMovable | QGraphicsObject.ItemSendsGeometryChanges
        )
        self.setCacheMode(QGraphicsObject.DeviceCoordinateCache)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)

        initial_bubble_position = anchor_point + QPointF(50, 0)
        self.setPos(initial_bubble_position)
        
        self._update_geometry()

    # --- Setter 方法 ---
    def set_dimension(self, value: str):
        if self.dimension != value:
            self.dimension = value
            self.data_updated.emit(self)

    def set_dimension_type(self, value: str):
        if self.dimension_type != value:
            self.dimension_type = value
            self.data_updated.emit(self)

    def set_upper_tolerance(self, value: str):
        if self.upper_tolerance != value:
            self.upper_tolerance = value
            self.data_updated.emit(self)

    def set_lower_tolerance(self, value: str):
        if self.lower_tolerance != value:
            self.lower_tolerance = value
            self.data_updated.emit(self)

    def set_text(self, text: str):
        if self.text != text:
            self.text = text
            self.data_updated.emit(self)
            
    def set_audited(self, audited: bool):
        """【新增】设置审核状态的方法"""
        if self.is_audited != audited:
            self.is_audited = audited
            self.data_updated.emit(self) # 发射信号，通知UI更新
    
    def get_style_colors(self):
        if self.custom_color and self.custom_color.isValid():
            return {
                "normal_pen": self.custom_color, "normal_brush": QColor(self.custom_color.red(), self.custom_color.green(), self.custom_color.blue(), 100),
                "selected_pen": self.custom_color.darker(150), "selected_brush": QColor(self.custom_color.red(), self.custom_color.green(), self.custom_color.blue(), 150)
            }
        styles = {
            "default": {"normal_pen": QColor(0, 0, 255), "normal_brush": QColor(255, 255, 255, 200), "selected_pen": QColor(255, 0, 0), "selected_brush": QColor(255, 255, 0, 100)},
            "warning": {"normal_pen": QColor(255, 165, 0), "normal_brush": QColor(255, 248, 220, 200), "selected_pen": QColor(255, 69, 0), "selected_brush": QColor(255, 218, 185, 150)},
            "error": {"normal_pen": QColor(220, 20, 60), "normal_brush": QColor(255, 192, 203, 200), "selected_pen": QColor(178, 34, 34), "selected_brush": QColor(255, 160, 122, 150)},
            "success": {"normal_pen": QColor(34, 139, 34), "normal_brush": QColor(240, 255, 240, 200), "selected_pen": QColor(0, 128, 0), "selected_brush": QColor(144, 238, 144, 150)}
        }
        return styles.get(self.style, styles["default"])

    def _update_geometry(self):
        path = QPainterPath()
        if self.shape_type in ["circle", "solid_circle"]:
            path.addEllipse(QPointF(0, 0), self.radius, self.radius)
        elif self.shape_type == "pentagram":
            path.addPolygon(self._create_star_polygon())
        elif self.shape_type == "triangle":
            path.addPolygon(self._create_triangle_polygon())
        else: # 默认圆形
            path.addEllipse(QPointF(0, 0), self.radius, self.radius)

        bubble_center_local = QPointF(0, 0)
        anchor_local = self.mapFromScene(self.anchor_point)
        line_vector = anchor_local - bubble_center_local
        distance = math.hypot(line_vector.x(), line_vector.y())

        if distance > self.radius:
            line_path = QPainterPath()
            start_point = bubble_center_local + line_vector * (self.radius / distance)
            line_path.moveTo(start_point)
            line_path.lineTo(anchor_local)
            
            stroker = QPainterPathStroker()
            stroker.setWidth(self.arrow_head_size)
            path.addPath(stroker.createStroke(line_path))
        
        self._cached_shape_path = path

    def shape(self) -> QPainterPath:
        return self._cached_shape_path

    def boundingRect(self) -> QRectF:
        return self._cached_shape_path.controlPointRect()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        colors = self.get_style_colors()
        pen = QPen(colors["selected_pen"], 2) if self.isSelected() or self._is_highlighted else QPen(colors["normal_pen"], 1)
        brush = QBrush(colors["selected_brush"]) if self.isSelected() or self._is_highlighted else QBrush(colors["normal_brush"])
        painter.setPen(pen)
        
        bubble_center_local = QPointF(0, 0)
        anchor_local = self.mapFromScene(self.anchor_point)
        line_vector = anchor_local - bubble_center_local
        distance = math.hypot(line_vector.x(), line_vector.y())
        if distance > self.radius:
            start_point = bubble_center_local + line_vector * (self.radius / distance)
            painter.drawLine(start_point, anchor_local)
            self._draw_arrowhead(painter, start_point, anchor_local)

        if self.shape_type == "solid_circle":
            painter.setBrush(pen.color())
        else:
            painter.setBrush(brush)
            
        if self.shape_type in ["circle", "solid_circle"]:
            painter.drawEllipse(bubble_center_local, self.radius, self.radius)
        elif self.shape_type == "pentagram":
            painter.drawPolygon(self._create_star_polygon())
        elif self.shape_type == "triangle":
            painter.drawPolygon(self._create_triangle_polygon())
        else:
            painter.drawEllipse(bubble_center_local, self.radius, self.radius)

        painter.setPen(QPen(QColor(0, 0, 0)))
        font_size = max(int(self.radius * 0.6), 6)
        font = QFont("Arial", font_size, QFont.Bold)
        painter.setFont(font)
        text_rect = QRectF(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        painter.drawText(text_rect, Qt.AlignCenter, str(self.annotation_id))

    def _draw_arrowhead(self, painter: QPainter, line_start: QPointF, line_end: QPointF):
        angle = math.atan2(-(line_start.y() - line_end.y()), line_start.x() - line_end.x())
        wing_angle = math.pi / 6 
        arrow_p1 = line_end + QPointF(self.arrow_head_size * math.cos(angle - wing_angle), -self.arrow_head_size * math.sin(angle - wing_angle))
        arrow_p2 = line_end + QPointF(self.arrow_head_size * math.cos(angle + wing_angle), -self.arrow_head_size * math.sin(angle + wing_angle))
        painter.drawLine(line_end, arrow_p1)
        painter.drawLine(line_end, arrow_p2)

    def _create_star_polygon(self) -> QPolygonF:
        polygon = QPolygonF()
        for i in range(5):
            angle_deg = -90 + i * 72; angle_rad = math.radians(angle_deg)
            outer_point = QPointF(self.radius * math.cos(angle_rad), self.radius * math.sin(angle_rad)); polygon.append(outer_point)
            angle_deg += 36; angle_rad = math.radians(angle_deg)
            inner_point = QPointF(self.radius * 0.4 * math.cos(angle_rad), self.radius * 0.4 * math.sin(angle_rad)); polygon.append(inner_point)
        return polygon

    def _create_triangle_polygon(self) -> QPolygonF:
        polygon = QPolygonF()
        for i in range(3):
            angle_deg = -90 + i * 120; angle_rad = math.radians(angle_deg)
            point = QPointF(self.radius * math.cos(angle_rad), self.radius * math.sin(angle_rad)); polygon.append(point)
        return polygon

    def itemChange(self, change, value):
        if change == QGraphicsObject.ItemPositionChange and self.scene():
            self.prepareGeometryChange()
            self._update_geometry()
            self.moved.emit(self, value)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: super().mousePressEvent(event); self.selected.emit(self)
        elif event.button() == Qt.RightButton: self.show_context_menu(event.screenPos()); event.accept()

    def show_context_menu(self, global_pos):
        menu = QMenu()
        
        delete_action = menu.addAction("删除标注")
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self))
        menu.addSeparator()

        color_action = menu.addAction("选择颜色...")
        color_action.triggered.connect(self._open_color_dialog)
        
        shape_menu = menu.addMenu("更改形状")
        shapes = [("空心圆", "circle"), ("实心圆", "solid_circle"), ("五角星", "pentagram"), ("三角形", "triangle")]
        for shape_name, shape_key in shapes:
            shape_action = shape_menu.addAction(shape_name)
            shape_action.setEnabled(shape_key != self.shape_type)
            if shape_key != self.shape_type:
                shape_action.triggered.connect(lambda checked, s=shape_key: self.change_shape(s))
        
        size_menu = menu.addMenu("调整大小")
        sizes = [("小 (10)", 10), ("中 (15)", 15), ("大 (20)", 20), ("特大 (25)", 25)]
        for size_name, size_val in sizes:
            size_action = size_menu.addAction(size_name)
            size_action.setEnabled(size_val != self.radius)
            if size_val != self.radius:
                size_action.triggered.connect(lambda checked, s=size_val: self.change_size(s))
        
        style_menu = menu.addMenu("更改样式")
        styles = [("默认", "default"), ("警告", "warning"), ("错误", "error"), ("成功", "success")]
        for style_name, style_key in styles:
            style_action = style_menu.addAction(style_name)
            style_action.setEnabled(self.style != style_key or self.custom_color is not None)
            if self.style != style_key or self.custom_color is not None:
                style_action.triggered.connect(lambda checked, s=style_key: self.change_style(s))
        
        menu.exec(global_pos.toPoint())

    def _open_color_dialog(self):
        initial_color = self.custom_color if self.custom_color and self.custom_color.isValid() else QColor("blue")
        color = QColorDialog.getColor(initial_color, None, "选择标注颜色")
        if color.isValid():
            self.change_color(color)

    def change_size(self, new_size: int):
        self.radius = new_size
        self.prepareGeometryChange()
        self._update_geometry()
        self.update()
        self.size_change_requested.emit(self)

    def change_color(self, new_color: QColor):
        self.custom_color = new_color
        self.style = 'custom'
        self.update()
        self.color_change_requested.emit(self)

    def change_shape(self, new_shape: str):
        self.shape_type = new_shape
        self.prepareGeometryChange()
        self._update_geometry()
        self.update()
        self.shape_change_requested.emit(self)

    def change_style(self, new_style: str):
        self.custom_color = None
        self.style = new_style
        self.update()
        self.style_change_requested.emit(self)
    
    def set_highlighted(self, highlighted: bool):
        self._is_highlighted = highlighted
        self.update()
    
    def get_data(self) -> dict:
        color_hex = self.custom_color.name() if self.custom_color and self.custom_color.isValid() else None
        return {
            'id': self.annotation_id, 'text': self.text, 'bubble_position': self.pos(), 
            'anchor_point': self.anchor_point, 'style': self.style, 
            'shape': self.shape_type, 'color': color_hex, 'size': self.radius,
            'dimension': self.dimension, 'dimension_type': self.dimension_type,
            'upper_tolerance': self.upper_tolerance, 'lower_tolerance': self.lower_tolerance,
            'is_audited': self.is_audited # <-- 新增
        }