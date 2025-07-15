# ui/property_editor.py

from typing import Optional
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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
        self.preview_rect: Optional[QRectF] = None
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
        self.type_combo.addItem("⏤")  # 直线度 (Straightness) - 默认
        self.type_combo.addItem("⌀")  # 直径符号 (Diameter)
        self.type_combo.addItem("R")  # 半径 (Radius)
        self.type_combo.addItem("M")  # 公制螺纹 (Metric Thread)
        self.type_combo.addItem("⏥")  # 平面度 (Flatness)
        self.type_combo.addItem("⌒")  # 圆弧 (Arc)
        self.type_combo.addItem("⌓")  # 线段 (Segment)
        self.type_combo.addItem("⋭")  # 圆柱度 (Cylindricity)
        self.type_combo.addItem("⋮")  # 全周轮廓度 (All Around-Profile)
        self.type_combo.addItem("⋯")  # 对称度 (Symmetry)
        self.type_combo.addItem("⌰")  # 总跳动 (Total Runout)
        self.type_combo.addItem("⌱")  # 尺寸原点 (Dimension Origin)
        self.type_combo.addItem("⌲")  # 锥度 (Conical Taper)
        self.type_combo.addItem("⌳")  # 斜度 (Slope)
        self.type_combo.addItem("⌴")  # 反锥孔 (Counterbore)
        self.type_combo.addItem("⌵")  # 沉孔 (Countersink)
        self.type_combo.addItem("∠")  # 角度 (Angle)
        
        # 设置符号下拉框样式
        self.type_combo.setStyleSheet("""
            QComboBox { 
                font-size: 16px;
                font-weight: bold;
                padding: 4px;
                min-height: 30px;
            }
            QComboBox QAbstractItemView {
                font-size: 16px;
                font-weight: bold;
                padding: 4px;
            }
        """)
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

    def set_annotation(self, annotation: Optional[BubbleAnnotationItem], pixmap: Optional[QPixmap], preview_rect: Optional[QRectF] = None):
        self.current_annotation = annotation
        self.original_pixmap = pixmap
        self.preview_rect = preview_rect
        
        # --- 修改：每次选中新标注时，重置缩放系数 ---
        self.preview_zoom_factor = 1.0

        if annotation:
            self.block_signals(True)
            self.id_label.setText(str(annotation.annotation_id))
            self.dimension_edit.setText(annotation.dimension)
            
            # 处理尺寸类型 - 转换旧的文本格式到新的符号格式
            dim_type = annotation.dimension_type
            if dim_type == "直径(Φ)" or dim_type == "Φ":
                self.type_combo.setCurrentText("⌀")
            elif dim_type == "半径(R)" or dim_type == "R":
                self.type_combo.setCurrentText("R")
            elif dim_type == "角度(°)" or dim_type == "°" or dim_type == "∠":
                self.type_combo.setCurrentText("∠")
            elif dim_type == "线性":
                self.type_combo.setCurrentText("⏤")
            elif dim_type == "螺纹":
                self.type_combo.setCurrentText("M")
            else:
                # 尝试直接匹配符号
                index = self.type_combo.findText(dim_type)
                if index >= 0:
                    self.type_combo.setCurrentIndex(index)
                else:
                    self.type_combo.setCurrentIndex(0)  # 默认为空
            
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
        
        try:
            # 使用从主窗口传递的预览区域（如果有的话）
            if hasattr(self, 'preview_rect') and self.preview_rect:
                # 应用缩放系数
                center_x = self.preview_rect.center().x()
                center_y = self.preview_rect.center().y()
                
                # 根据缩放因子调整宽高
                scaled_width = self.preview_rect.width() / self.preview_zoom_factor
                scaled_height = self.preview_rect.height() / self.preview_zoom_factor
                
                # 计算新的预览区域
                left = max(0, int(center_x - scaled_width / 2))
                top = max(0, int(center_y - scaled_height / 2))
                width = min(self.original_pixmap.width() - left, int(scaled_width))
                height = min(self.original_pixmap.height() - top, int(scaled_height))
                
                crop_rect = QRectF(left, top, width, height).toRect()
                
                print(f"使用传递的预览区域: ({left}, {top}, {width}, {height})")
            else:
                # 如果没有预览区域，回退到默认方法
                print("没有预览区域，使用默认计算方法")
                # --- 修改：根据缩放系数计算实际要截取的区域大小 ---
                crop_width = int(base_preview_width / self.preview_zoom_factor)
                crop_height = int(base_preview_height / self.preview_zoom_factor)
                
                # 获取锚点在场景中的坐标
                anchor_pos = self.current_annotation.anchor_point
                
                # 检查锚点的bbox_points，如果有的话使用bbox中心点
                if hasattr(self.current_annotation, 'bbox_points') and self.current_annotation.bbox_points:
                    # 如果有边界框信息，使用边界框中心
                    bbox_points = self.current_annotation.bbox_points
                    sum_x = sum(p.x() for p in bbox_points)
                    sum_y = sum(p.y() for p in bbox_points)
                    center_x = sum_x / len(bbox_points)
                    center_y = sum_y / len(bbox_points)
                    # 使用边界框中心点作为预览中心
                    anchor_x = int(center_x)
                    anchor_y = int(center_y)
                    print(f"使用bbox中心点: ({anchor_x}, {anchor_y})")
                else:
                    # 使用锚点坐标
                    anchor_x = int(anchor_pos.x())
                    anchor_y = int(anchor_pos.y())
                    print(f"使用锚点: ({anchor_x}, {anchor_y})")
                
                # 确保坐标在图像范围内
                anchor_x = max(0, min(anchor_x, self.original_pixmap.width() - 1))
                anchor_y = max(0, min(anchor_y, self.original_pixmap.height() - 1))
                
                # 计算裁剪区域，确保不会超出图像边界
                left = max(0, anchor_x - crop_width // 2)
                top = max(0, anchor_y - crop_height // 2)
                right = min(self.original_pixmap.width(), left + crop_width)
                bottom = min(self.original_pixmap.height(), top + crop_height)
                
                # 最终的裁剪区域
                crop_rect = QRectF(left, top, right - left, bottom - top).toRect()
            
            # 调试输出
            print(f"原始图像尺寸: {self.original_pixmap.width()}x{self.original_pixmap.height()}")
            print(f"裁剪区域: {crop_rect}")
            
            if crop_rect.isEmpty() or crop_rect.width() <= 0 or crop_rect.height() <= 0:
                self.preview_label.setText("预览区域无效")
                self.preview_label.setPixmap(QPixmap())
                return
            
            # 裁剪图像
            cropped_pixmap = self.original_pixmap.copy(crop_rect)
            
            # 缩放到预览区域大小
            scaled_pixmap = cropped_pixmap.scaled(
                self.preview_label.width() - 10,
                self.preview_label.height() - 10,
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled_pixmap)
        
        except Exception as e:
            self.preview_label.setText(f"预览错误: {str(e)}")
            print(f"预览错误: {str(e)}")
            import traceback
            traceback.print_exc()

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
        """当尺寸类型改变时调用"""
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