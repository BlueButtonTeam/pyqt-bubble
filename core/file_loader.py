#!/usr/bin/env python3
"""
文件加载器模块
"""

from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainterPath, QPen, QBrush, QColor

from utils.dependencies import HAS_OCR_SUPPORT, Image

if HAS_OCR_SUPPORT:
    import fitz
    import ezdxf
    from PIL import ImageFilter, ImageEnhance
    import io


class FileLoader:
    """
    文件加载器，处理不同格式的文件
    """
    @staticmethod
    def load_image(file_path: str) -> Optional[QPixmap]:
        """加载图像文件"""
        try:
            if Image is None:
                # 如果PIL不可用，尝试使用QPixmap直接加载
                pixmap = QPixmap(file_path)
                return pixmap if not pixmap.isNull() else None
            
            pil_image = Image.open(file_path)
            # 转换为RGB模式以确保兼容性
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # 使用更简单的方法
            pixmap = QPixmap(file_path)
            return pixmap if not pixmap.isNull() else None
            
        except Exception as e:
            print(f"加载图像失败: {e}")
            return None
    
    @staticmethod
    def load_pdf(file_path: str, zoom_factor: float = 4.0, page_num: int = 0) -> Optional[QPixmap]:
        """加载PDF文件（高清晰度优化版）"""
        if not HAS_OCR_SUPPORT:
            return None
            
        try:
            print(f"正在以 {zoom_factor}x 分辨率加载PDF...")
            
            doc = fitz.open(file_path)
            if page_num >= len(doc):
                page_num = 0
            
            page = doc.load_page(page_num)
            
            # 设置高分辨率渲染参数
            mat = fitz.Matrix(zoom_factor, zoom_factor)
            
            print(f"开始渲染PDF页面 (分辨率倍数: {zoom_factor}x)...")
            
            # 使用高质量渲染选项
            pix = page.get_pixmap(
                matrix=mat,
                alpha=False,  # 不需要透明度通道，提高性能
                annots=True,  # 包含注释
                clip=None     # 不裁剪
            )
            
            # 获取图像数据
            img_data = pix.tobytes("png")
            
            print(f"PDF页面渲染完成，尺寸: {pix.width}x{pix.height}")
            
            # 如果有PIL支持，进行额外的图像优化
            if Image is not None:
                try:
                    print("正在进行图像后处理优化...")
                    # 使用PIL进行图像后处理优化
                    pil_image = Image.open(io.BytesIO(img_data))
                    
                    # 应用锐化滤镜提高文字清晰度
                    # 轻微锐化
                    pil_image = pil_image.filter(ImageFilter.UnsharpMask(
                        radius=1.0,      # 锐化半径
                        percent=120,     # 锐化强度
                        threshold=1      # 锐化阈值
                    ))
                    
                    # 增强对比度，让文字更清晰
                    enhancer = ImageEnhance.Contrast(pil_image)
                    pil_image = enhancer.enhance(1.1)  # 轻微增强对比度
                    
                    # 转换回QPixmap
                    buffer = io.BytesIO()
                    pil_image.save(buffer, format='PNG', quality=100, optimize=True)
                    buffer.seek(0)
                    
                    pixmap = QPixmap()
                    pixmap.loadFromData(buffer.getvalue())
                    
                    print("图像后处理优化完成")
                    
                except Exception as e:
                    print(f"PIL图像后处理失败，使用原始渲染: {e}")
                    # 如果PIL处理失败，回退到原始方法
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_data)
            else:
                # 没有PIL支持时的原始方法
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
            
            doc.close()
            
            # 检查是否成功加载
            if pixmap.isNull():
                print("警告: PDF渲染结果为空")
                return None
                
            print(f"✅ PDF加载成功 - 渲染尺寸: {pix.width}x{pix.height}, 最终尺寸: {pixmap.width()}x{pixmap.height()}")
            return pixmap
            
        except Exception as e:
            print(f"❌ 加载PDF失败: {e}")
            return None
    
    @staticmethod
    def load_dxf(file_path: str, scene: QGraphicsScene):
        """加载DXF文件"""
        if not HAS_OCR_SUPPORT:
            return
            
        try:
            doc = ezdxf.readfile(file_path)
            
            # 获取模型空间
            msp = doc.modelspace()
            
            # 简单地将DXF实体转换为Graphics项
            for entity in msp:
                if entity.dxftype() == 'LINE':
                    FileLoader._add_line_to_scene(entity, scene)
                elif entity.dxftype() == 'CIRCLE':
                    FileLoader._add_circle_to_scene(entity, scene)
                elif entity.dxftype() == 'ARC':
                    FileLoader._add_arc_to_scene(entity, scene)
                # 可以添加更多实体类型的处理
            
        except Exception as e:
            print(f"加载DXF失败: {e}")
    
    @staticmethod
    def _add_line_to_scene(line_entity, scene: QGraphicsScene):
        """将LINE实体添加到场景"""
        start = line_entity.dxf.start
        end = line_entity.dxf.end
        
        path = QPainterPath()
        path.moveTo(start.x, -start.y)  # DXF的Y轴与Qt相反
        path.lineTo(end.x, -end.y)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(0, 0, 0), 1))
        scene.addItem(item)
    
    @staticmethod
    def _add_circle_to_scene(circle_entity, scene: QGraphicsScene):
        """将CIRCLE实体添加到场景"""
        center = circle_entity.dxf.center
        radius = circle_entity.dxf.radius
        
        path = QPainterPath()
        path.addEllipse(center.x - radius, -center.y - radius, 
                       radius * 2, radius * 2)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(0, 0, 0), 1))
        item.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(item)
    
    @staticmethod
    def _add_arc_to_scene(arc_entity, scene: QGraphicsScene):
        """将ARC实体添加到场景"""
        center = arc_entity.dxf.center
        radius = arc_entity.dxf.radius
        start_angle = arc_entity.dxf.start_angle
        end_angle = arc_entity.dxf.end_angle
        
        path = QPainterPath()
        # 这里需要更复杂的弧线绘制逻辑
        # 简化版本：绘制为圆圈
        path.addEllipse(center.x - radius, -center.y - radius,
                       radius * 2, radius * 2)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(0, 0, 0), 1))
        item.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(item) 