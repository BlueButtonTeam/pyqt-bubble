from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QUndoCommand, QColor

class AddAnnotationCommand(QUndoCommand):
    """添加标注的撤销命令"""
    
    def __init__(self, main_window, annotation, description="添加标注"):
        super().__init__(description)
        self.main_window = main_window
        self.annotation = annotation
        self.annotation_data = annotation.get_data()  # 保存标注的初始数据
        self.index = None  # 将在redo中设置
        
    def redo(self):
        # 检查是否有相同ID的标注已存在
        existing_ids = [ann.annotation_id for ann in self.main_window.annotations]
        
        # 如果index不为None，说明这是撤销后的恢复操作
        if self.index is not None and self.index < len(self.main_window.annotations):
            # 确保与原来相同的ID，除非ID已被占用
            if self.annotation_data['id'] in existing_ids:
                # ID已被占用，分配新ID
                self.main_window.annotation_counter += 1
                self.annotation.annotation_id = self.main_window.annotation_counter
            else:
                self.annotation.annotation_id = self.annotation_data['id']
                
            self.main_window.graphics_scene.addItem(self.annotation)
            self.main_window.annotations.insert(self.index, self.annotation)
        else:
            # 首次执行，直接添加
            # 检查ID是否已存在
            if self.annotation.annotation_id in existing_ids:
                # ID已被占用，分配新ID
                self.main_window.annotation_counter += 1
                self.annotation.annotation_id = self.main_window.annotation_counter
                
            self.main_window.graphics_scene.addItem(self.annotation)
            self.main_window.annotations.append(self.annotation)
            self.index = len(self.main_window.annotations) - 1
        
        # 确保annotation_counter总是大于等于所有标注的最大ID
        self.main_window.annotation_counter = max(
            self.main_window.annotation_counter,
            self.annotation.annotation_id
        )
        
        self.main_window.refresh_annotation_list()
        
    def undo(self):
        # 从场景和列表中移除标注
        self.main_window.graphics_scene.removeItem(self.annotation)
        if self.annotation in self.main_window.annotations:
            self.index = self.main_window.annotations.index(self.annotation)
            self.main_window.annotations.remove(self.annotation)
        
        # 如果当前选中标注是被删除的标注，清除选择
        if self.main_window.current_annotation == self.annotation:
            self.main_window.current_annotation = None
            self.main_window.property_editor.set_annotation(None, None)
            
        self.main_window.refresh_annotation_list()

class DeleteAnnotationCommand(QUndoCommand):
    """删除标注的撤销命令"""
    
    def __init__(self, main_window, annotation, description="删除标注"):
        super().__init__(description)
        self.main_window = main_window
        self.annotation = annotation
        self.index = main_window.annotations.index(annotation)
        self.was_selected = main_window.current_annotation == annotation
        
    def redo(self):
        # 从场景和列表中移除标注
        self.main_window.graphics_scene.removeItem(self.annotation)
        if self.annotation in self.main_window.annotations:
            self.main_window.annotations.remove(self.annotation)
            
        # 如果当前选中标注是被删除的标注，清除选择
        if self.main_window.current_annotation == self.annotation:
            self.main_window.current_annotation = None
            self.main_window.property_editor.set_annotation(None, None)
            
        self.main_window.refresh_annotation_list()
        
    def undo(self):
        # 恢复标注
        if self.index <= len(self.main_window.annotations):
            self.main_window.annotations.insert(self.index, self.annotation)
        else:
            self.main_window.annotations.append(self.annotation)
            
        self.main_window.graphics_scene.addItem(self.annotation)
        
        # 恢复选择状态
        if self.was_selected:
            self.main_window.on_annotation_selected(self.annotation)
            
        self.main_window.refresh_annotation_list()

class MoveAnnotationCommand(QUndoCommand):
    """移动标注的撤销命令"""
    
    def __init__(self, main_window, annotation, old_pos, new_pos, description="移动标注"):
        super().__init__(description)
        self.main_window = main_window
        self.annotation = annotation
        self.old_pos = old_pos
        self.new_pos = new_pos
        
    def redo(self):
        self.annotation.setPos(self.new_pos)
        self.annotation.update()
        
    def undo(self):
        self.annotation.setPos(self.old_pos)
        self.annotation.update()

class EditAnnotationTextCommand(QUndoCommand):
    """编辑标注文本的撤销命令"""
    
    def __init__(self, main_window, annotation, old_text, new_text, attribute_type="text", description="编辑文本"):
        super().__init__(description)
        self.main_window = main_window
        self.annotation = annotation
        self.old_text = old_text
        self.new_text = new_text
        self.attribute_type = attribute_type  # 新增：属性类型参数
        
    def redo(self):
        if self.attribute_type == "text":
            self.annotation.set_text(self.new_text)
        elif self.attribute_type == "dimension":
            self.annotation.set_dimension(self.new_text)
        elif self.attribute_type == "dimension_type":
            self.annotation.set_dimension_type(self.new_text)
        elif self.attribute_type == "upper_tolerance":
            self.annotation.set_upper_tolerance(self.new_text)
        elif self.attribute_type == "lower_tolerance":
            self.annotation.set_lower_tolerance(self.new_text)
        else:
            # 默认情况
            self.annotation.set_text(self.new_text)
            
        self.main_window.refresh_annotation_list()
        
    def undo(self):
        if self.attribute_type == "text":
            self.annotation.set_text(self.old_text)
        elif self.attribute_type == "dimension":
            self.annotation.set_dimension(self.old_text)
        elif self.attribute_type == "dimension_type":
            self.annotation.set_dimension_type(self.old_text)
        elif self.attribute_type == "upper_tolerance":
            self.annotation.set_upper_tolerance(self.old_text)
        elif self.attribute_type == "lower_tolerance":
            self.annotation.set_lower_tolerance(self.old_text)
        else:
            # 默认情况
            self.annotation.set_text(self.old_text)
            
        self.main_window.refresh_annotation_list()

class EditAnnotationStyleCommand(QUndoCommand):
    """编辑标注样式的撤销命令"""
    
    def __init__(self, main_window, annotation, old_style, new_style, description="更改样式"):
        super().__init__(description)
        self.main_window = main_window
        self.annotation = annotation
        self.old_style = old_style
        self.new_style = new_style
        
    def redo(self):
        self.annotation.change_style(self.new_style)
        
    def undo(self):
        self.annotation.change_style(self.old_style)

class EditAnnotationShapeCommand(QUndoCommand):
    """编辑标注形状的撤销命令"""
    
    def __init__(self, main_window, annotation, old_shape, new_shape, description="更改形状"):
        super().__init__(description)
        self.main_window = main_window
        self.annotation = annotation
        self.old_shape = old_shape
        self.new_shape = new_shape
        
    def redo(self):
        self.annotation.change_shape(self.new_shape)
        
    def undo(self):
        self.annotation.change_shape(self.old_shape)

class EditAnnotationColorCommand(QUndoCommand):
    """编辑标注颜色的撤销命令"""
    
    def __init__(self, main_window, annotation, old_color, new_color, description="更改颜色"):
        super().__init__(description)
        self.main_window = main_window
        self.annotation = annotation
        self.old_color = old_color
        self.new_color = new_color
        
    def redo(self):
        self.annotation.change_color(self.new_color)
        
    def undo(self):
        self.annotation.change_color(self.old_color)

class EditAnnotationSizeCommand(QUndoCommand):
    """编辑标注大小的撤销命令"""
    
    def __init__(self, main_window, annotation, old_size, new_size, description="调整大小"):
        super().__init__(description)
        self.main_window = main_window
        self.annotation = annotation
        self.old_size = old_size
        self.new_size = new_size
        
    def redo(self):
        self.annotation.change_size(self.new_size)
        
    def undo(self):
        self.annotation.change_size(self.old_size)

class ClearAnnotationsCommand(QUndoCommand):
    """清除所有标注的撤销命令"""
    
    def __init__(self, main_window, annotations, description="清除所有标注"):
        super().__init__(description)
        self.main_window = main_window
        # 深拷贝标注列表和数据
        self.annotations = annotations.copy()
        self.current_annotation = main_window.current_annotation
        
    def redo(self):
        # 移除所有标注
        for annotation in self.annotations:
            if annotation.scene():
                self.main_window.graphics_scene.removeItem(annotation)
                
        self.main_window.annotations.clear()
        self.main_window.annotation_table.clear_annotations()
        self.main_window.property_editor.set_annotation(None, None)
        self.main_window.current_annotation = None
        
    def undo(self):
        # 恢复所有标注
        for annotation in self.annotations:
            self.main_window.graphics_scene.addItem(annotation)
            self.main_window.annotations.append(annotation)
            
            # 更新annotation_counter
            self.main_window.annotation_counter = max(
                self.main_window.annotation_counter,
                annotation.annotation_id
            )
            
        # 恢复当前选中的标注
        if self.current_annotation and self.current_annotation in self.annotations:
            self.main_window.on_annotation_selected(self.current_annotation)
            
        self.main_window.refresh_annotation_list() 