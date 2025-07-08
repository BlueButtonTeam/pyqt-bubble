#!/usr/bin/env python3
"""
文件加载器模块
"""

from typing import Optional, List, Tuple, Any, Dict
from pathlib import Path
import os
import tempfile
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainterPath, QPen, QBrush, QColor, QImageReader
import sys
import time  # 导入time模块用于计时
import logging  # 导入logging模块用于日志记录
import threading
import math

from utils.dependencies import HAS_OCR_SUPPORT, Image, HAS_PADDLE_OCR

if HAS_OCR_SUPPORT:
    import fitz
    import ezdxf
    from PIL import ImageFilter, ImageEnhance
    import io

# 获取已配置的logger
logger = logging.getLogger('PyQtBubble.FileLoader')

# 线程本地存储，用于保存每个线程的调试标记
_debug_marks = threading.local()

# 获取系统设置的内存限制 - 默认为256MB，但可能在应用程序启动时被修改
try:
    MEMORY_LIMIT = QImageReader.allocationLimit()  # 获取当前设置的限制
    if MEMORY_LIMIT <= 0:  # 如果没有设置，使用默认值
        MEMORY_LIMIT = 2048  # 默认使用2048MB，与main.py中的设置一致
    logger.debug(f"系统图像内存限制: {MEMORY_LIMIT}MB")
except:
    MEMORY_LIMIT = 2048  # 默认使用2048MB
    logger.debug(f"无法获取系统图像内存限制，使用默认值: {MEMORY_LIMIT}MB")

def mark_debug_point(name: str):
    """设置调试标记点，用于计算执行时间
    
    Args:
        name: 标记点名称
    """
    if not hasattr(_debug_marks, 'points'):
        _debug_marks.points = {}
        _debug_marks.start_time = time.time()
    
    current_time = time.time()
    elapsed = current_time - _debug_marks.start_time
    _debug_marks.points[name] = elapsed
    logger.debug(f"DEBUG MARK: {name} - {elapsed:.3f}秒")

def get_debug_report():
    """获取从第一个标记点到现在的所有时间点报告"""
    if not hasattr(_debug_marks, 'points'):
        return "没有调试标记点"
    
    report = ["调试标记点报告:"]
    prev_time = 0.0
    
    for i, (name, time_point) in enumerate(sorted(_debug_marks.points.items(), key=lambda x: x[1])):
        if i == 0:
            report.append(f"{i+1}. {name}: {time_point:.3f}秒")
        else:
            interval = time_point - prev_time
            report.append(f"{i+1}. {name}: {time_point:.3f}秒 (+{interval:.3f}秒)")
        prev_time = time_point
    
    # 添加到当前时间的耗时
    total_time = time.time() - _debug_marks.start_time
    report.append(f"总耗时: {total_time:.3f}秒")
    
    return "\n".join(report)

def reset_debug_marks():
    """重置所有调试标记点"""
    if hasattr(_debug_marks, 'points'):
        _debug_marks.points = {}
        _debug_marks.start_time = time.time()
        logger.debug("已重置调试标记点")
    
# 尝试导入高级图像处理依赖
try:
    from PIL import Image, ImageFilter, ImageEnhance
except ImportError:
    Image = None
    logger.warning("PIL库未安装，图像优化功能不可用")

# 尝试导入PDF处理库
if HAS_OCR_SUPPORT:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) 库未安装，PDF处理功能不可用")


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
    def get_pdf_page_count(file_path: str) -> int:
        """获取PDF文件的页数"""
        if not HAS_OCR_SUPPORT:
            return 0
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            doc.close()
            return page_count
        except Exception as e:
            print(f"获取PDF页数失败: {e}")
            return 0
            
    @staticmethod
    def load_pdf(file_path: str, scene: QGraphicsScene, page_num: int = 0, quality: float = 2.0, force_resolution: bool = False) -> Tuple[QPixmap, str]:
        """加载PDF文件并转换为临时图像
        
        Args:
            file_path: PDF文件路径
            scene: 要添加图像的场景
            page_num: 页码
            quality: 渲染质量
            force_resolution: 是否强制使用原始分辨率
            
        Returns:
            Tuple[QPixmap, str]: (图像, 临时文件路径)
        """
        if not HAS_OCR_SUPPORT:
            logger.error("缺少OCR支持，无法加载PDF")
            return QPixmap(), ""
        
        start_time = time.time()
        logger.info(f"开始加载PDF: {file_path}, 页码: {page_num}, 质量: {quality}")
        
        try:
            # 先将PDF转为PNG
            logger.debug("调用convert_pdf_to_png方法转换PDF...")
            convert_start = time.time()
            png_path, error = FileLoader.convert_pdf_to_png(
                file_path, quality, page_num, force_resolution
            )
            logger.debug(f"PDF转换耗时: {time.time() - convert_start:.3f}秒")
            
            if error or not png_path:
                logger.error(f"PDF转换失败: {error}")
                # 如果质量较高，尝试降低质量重试
                if quality > 1.5 and not force_resolution:
                    retry_quality = max(1.0, quality / 2)
                    logger.warning(f"尝试降低质量至 {retry_quality} 重新转换...")
                    return FileLoader.load_pdf(file_path, scene, page_num, retry_quality, force_resolution)
                else:
                    raise Exception(f"PDF转换失败: {error}")
            
            # 加载PNG
            logger.debug(f"加载PNG图像: {png_path}")
            load_start = time.time()
            pixmap = QPixmap(png_path)
            logger.debug(f"加载图像耗时: {time.time() - load_start:.3f}秒")
            
            if pixmap.isNull():
                logger.error("图像加载失败，pixmap为空")
                # 可能是图像太大，尝试降低质量重试
                if quality > 1.5 and not force_resolution:
                    retry_quality = max(1.0, quality / 2)
                    logger.warning(f"加载失败，可能图像太大。尝试降低质量至 {retry_quality} 重新转换...")
                    return FileLoader.load_pdf(file_path, scene, page_num, retry_quality, force_resolution)
                else:
                    raise Exception("图像加载失败")
            
            # 添加到场景
            logger.debug(f"添加图像到场景，尺寸: {pixmap.width()}x{pixmap.height()}")
            scene_start = time.time()
            scene.addPixmap(pixmap)
            logger.debug(f"添加图像到场景耗时: {time.time() - scene_start:.3f}秒")
            
            total_time = time.time() - start_time
            logger.info(f"PDF加载完成，总耗时: {total_time:.3f}秒")
            
            return pixmap, png_path
            
        except Exception as e:
            logger.exception(f"加载PDF失败: {str(e)}")
            return QPixmap(), ""
    
    @staticmethod
    def convert_pdf_to_png(pdf_path: str, zoom_factor: float = 4.0, page_num: int = 0, force_resolution: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """
        将PDF文件转换为PNG图片并保存到临时目录
        
        Args:
            pdf_path: PDF文件路径
            zoom_factor: 缩放因子，默认为4.0
            page_num: 要转换的页面索引，默认为0
            force_resolution: 是否强制使用原始分辨率
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (临时PNG文件路径, 错误信息)
            如果转换成功，返回(png_path, None)，否则返回(None, error_msg)
        """
        if not HAS_OCR_SUPPORT:
            logger.error("缺少OCR支持，无法转换PDF")
            return None, "缺少OCR支持，无法转换PDF"
        
        start_time = time.time()
        reset_debug_marks()  # 重置调试标记
        mark_debug_point("开始")
        logger.info(f"开始将PDF转换为PNG，文件: {pdf_path}, 页码: {page_num}, 缩放比例: {zoom_factor}")
        
        try:
            # 创建临时目录用于存储转换后的图片
            temp_dir = tempfile.gettempdir()
            logger.debug(f"使用临时目录: {temp_dir}")
            
            # 使用uuid生成唯一的文件名，避免中文或特殊字符问题
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            temp_png_path = os.path.join(temp_dir, f"pdf_convert_{unique_id}_page{page_num}.png")
            
            mark_debug_point("准备打开PDF")
            logger.debug(f"开始打开PDF文件: {pdf_path}")
            open_start = time.time()
            # 打开PDF文件
            doc = fitz.open(pdf_path)
            mark_debug_point("PDF文件打开完成")
            logger.debug(f"PDF文件打开耗时: {time.time() - open_start:.3f}秒")
            
            if page_num >= len(doc):
                page_num = 0
                logger.warning(f"页面索引超出范围，使用第一页，总页数: {len(doc)}")
            
            # 加载指定页面
            logger.debug(f"开始加载PDF页面 {page_num+1}/{len(doc)}")
            load_start = time.time()
            page = doc.load_page(page_num)
            mark_debug_point("PDF页面加载完成")
            logger.debug(f"加载PDF页面耗时: {time.time() - load_start:.3f}秒")
            
            # 如果未强制分辨率，则自动调整缩放比例以避免内存溢出
            if not force_resolution:
                rect = page.rect
                # 估算图像大小（字节）
                img_width = rect.width * zoom_factor
                img_height = rect.height * zoom_factor
                
                # 估算内存占用（假设每个像素4字节，RGBA）
                img_size_mb = (img_width * img_height * 4) / (1024 * 1024)
                
                # 如果估算大小超过内存限制的90%，则降低缩放比例
                if img_size_mb > MEMORY_LIMIT * 0.9:
                    # 计算允许的最大缩放比例
                    max_img_size_bytes = MEMORY_LIMIT * 0.9 * 1024 * 1024
                    # (rect.width * z) * (rect.height * z) * 4 = max_bytes
                    # z^2 = max_bytes / (rect.width * rect.height * 4)
                    max_zoom_factor = math.sqrt(max_img_size_bytes / (rect.width * rect.height * 4))
                    
                    # 记录警告并更新缩放比例
                    logger.warning(f"原始缩放因子 {zoom_factor:.2f} 可能导致图像过大({img_size_mb:.1f}MB)，自动调整为 {max_zoom_factor:.2f}")
                    zoom_factor = max_zoom_factor
            else:
                logger.info("已启用强制原始分辨率，跳过自动缩放调整。")

            # 获取页面pixmap
            mark_debug_point("开始获取pixmap")
            logger.debug(f"使用最终缩放比例: {zoom_factor:.2f}")
            pix = page.get_pixmap(
                matrix=fitz.Matrix(zoom_factor, zoom_factor),
                alpha=False,  # 不需要透明度通道
                annots=True,  # 包含注释
                clip=None     # 不裁剪
            )
            mark_debug_point("PDF渲染为像素图完成")
            render_time = time.time() - load_start
            logger.debug(f"渲染PDF页面耗时: {render_time:.3f}秒，图像尺寸: {pix.width}x{pix.height}")
            
            # 估算图像大小
            img_size_mb = (pix.width * pix.height * 4) / (1024 * 1024)  # 4 bytes per pixel (RGBA)
            logger.debug(f"估算图像大小: {img_size_mb:.2f} MB")
            
            # 检查图像是否可能超过Qt限制
            if img_size_mb > MEMORY_LIMIT * 0.95:  # 接近内存限制
                logger.warning(f"图像尺寸({img_size_mb:.2f}MB)接近内存限制({MEMORY_LIMIT}MB)，可能会导致加载失败")
            
            # 优化图像质量（增强对比度、去噪等）
            mark_debug_point("开始图像优化")
            optimize_start = time.time()
            
            # 检查图像尺寸，如果过大，则分块处理
            size_in_mb = pix.width * pix.height * 4 / (1024 * 1024) # 估算内存占用（RGBA）
            
            # 使用更合理的阈值，例如系统内存限制的25%
            # 避免因单个图像占用过多内存导致程序不稳定
            processing_threshold_mb = MEMORY_LIMIT * 0.25 
            
            if size_in_mb > processing_threshold_mb:
                logger.warning(f"图像尺寸较大({size_in_mb:.2f}MB > {processing_threshold_mb:.2f}MB)，将进行分块优化处理以节省内存。")
                
                try:
                    # 分块处理
                    optimized_image = FileLoader.process_image_in_tiles(pix)
                    # 将优化后的PIL图像转换回QPixmap
                    buffer = io.BytesIO()
                    optimized_image.save(buffer, format="PNG")
                    buffer.seek(0)
                    
                    pixmap = QPixmap()
                    pixmap.loadFromData(buffer.getvalue())
                    
                    # 保存优化后的图像
                    pixmap.save(temp_png_path, "PNG", 100)
                    
                except Exception as tile_e:
                    logger.error(f"分块处理图像时出错: {tile_e}，将使用未优化的原始图像。")
                    # 如果分块处理失败，回退到原始图像
                    pix.save(temp_png_path, "PNG")
            else:
                # 对小图直接进行优化
                try:
                    # 将pixmap数据转换为PIL Image
                    buffer = io.BytesIO(pix.samples)
                    pil_image = Image.open(buffer)
                    
                    # 增强对比度
                    enhancer = ImageEnhance.Contrast(pil_image)
                    pil_image = enhancer.enhance(1.5)
                    
                    # 轻微降噪
                    pil_image = pil_image.filter(ImageFilter.MedianFilter(size=3))
                    
                    # 将优化后的PIL图像转换回QPixmap
                    buffer_out = io.BytesIO()
                    pil_image.save(buffer_out, format="PNG")
                    buffer_out.seek(0)
                    
                    pixmap_optimized = QPixmap()
                    pixmap_optimized.loadFromData(buffer_out.getvalue())
                    
                    # 保存优化后的图像
                    pixmap_optimized.save(temp_png_path, "PNG", 100)
                    
                except Exception as e:
                    logger.warning(f"直接优化图像时出错: {e}，将保存未优化的图像。")
                    pix.save(temp_png_path, "PNG")

            mark_debug_point("图像优化完成")
            logger.debug(f"图像优化耗时: {time.time() - optimize_start:.3f}秒")
            
            logger.debug("关闭PDF文档...")
            doc.close()
            mark_debug_point("PDF文档关闭")
            
            # 检查文件是否生成
            if not os.path.exists(temp_png_path):
                logger.error("PNG文件保存失败，文件不存在")
                return None, "PNG文件保存失败"
                
            total_time = time.time() - start_time
            mark_debug_point("完成")
            logger.info(f"✅ PDF转PNG成功，总耗时: {total_time:.3f}秒，路径: {temp_png_path}")
            
            # 输出完整的调试报告
            debug_report = get_debug_report()
            logger.info(f"PDF转换过程调试报告:\n{debug_report}")
            
            # 检查是否超过5秒，这可能是导致UI卡顿的问题
            if render_time > 5.0:
                logger.warning(f"⚠️ PDF渲染耗时较长: {render_time:.3f}秒，可能导致UI卡顿")
            if total_time > 10.0:
                logger.warning(f"⚠️ PDF转换总耗时较长: {total_time:.3f}秒，可能导致UI卡顿")
            
            return temp_png_path, None
            
        except Exception as e:
            error_msg = f"PDF转PNG失败: {str(e)}"
            logger.exception(f"❌ {error_msg}")
            return None, error_msg
            
    @staticmethod
    def process_image_in_tiles(pix: 'fitz.Pixmap', tile_size: int = 1024) -> 'Image':
        """
        对大图像进行分块处理，以节省内存。
        
        Args:
            pix: fitz.Pixmap 对象
            tile_size: 每个图块的尺寸（像素）
            
        Returns:
            PIL.Image: 经过优化处理的完整图像
        """
        width, height = pix.width, pix.height
        
        # 创建一个新的空白PIL图像用于存放结果
        final_image = Image.new('RGB', (width, height))
        
        logger.debug(f"开始分块处理: 图像尺寸={width}x{height}, 块尺寸={tile_size}x{tile_size}")
        
        # 遍历所有图块
        for y in range(0, height, tile_size):
            for x in range(0, width, tile_size):
                # 计算当前图块的边界
                tile_w = min(tile_size, width - x)
                tile_h = min(tile_size, height - y)
                
                # 从原始Pixmap中提取图块的像素数据
                # 注意：fitz.Pixmap 的 sample 提取方式较为复杂，这里我们先转为PIL图像再操作
                if 'pil_image' not in locals():
                    pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # 裁剪出图块
                tile = pil_image.crop((x, y, x + tile_w, y + tile_h))
                
                # --- 在这里对每个图块应用优化 ---
                # 增强对比度
                enhancer = ImageEnhance.Contrast(tile)
                tile = enhancer.enhance(1.5)
                
                # 轻微降噪
                tile = tile.filter(ImageFilter.MedianFilter(size=3))
                # ---------------------------------
                
                # 将处理完的图块粘贴回最终图像
                final_image.paste(tile, (x, y))

        logger.debug("分块处理完成。")
        return final_image

    @staticmethod
    def convert_pdf_to_pngs(pdf_path: str, zoom_factor: float = 4.0) -> Tuple[List[str], Optional[str]]:
        """
        将PDF文件的所有页面转换为PNG图片并保存到临时目录
        
        Args:
            pdf_path: PDF文件路径
            zoom_factor: 缩放因子，默认为4.0
            
        Returns:
            Tuple[List[str], Optional[str]]: (临时PNG文件路径列表, 错误信息)
            如果转换成功，返回([png_paths...], None)，否则返回([], error_msg)
        """
        if not HAS_OCR_SUPPORT:
            return [], "缺少OCR支持，无法转换PDF"
        
        try:
            print(f"开始将PDF转换为多个PNG，缩放比例: {zoom_factor}...")
            
            # 创建临时目录用于存储转换后的图片
            temp_dir = tempfile.gettempdir()
            
            # 使用uuid生成唯一的文件名前缀，避免中文或特殊字符问题
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            png_paths = []
            
            # 打开PDF文件
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            
            print(f"PDF有 {page_count} 页，开始转换...")
            
            # 转换每一页
            for page_num in range(page_count):
                # 生成PNG文件路径
                temp_png_path = os.path.join(temp_dir, f"pdf_convert_{unique_id}_page{page_num}.png")
                
                # 加载页面
                page = doc.load_page(page_num)
                
                # 设置高分辨率渲染参数
                mat = fitz.Matrix(zoom_factor, zoom_factor)
                
                print(f"渲染第 {page_num+1}/{page_count} 页...")
                
                # 渲染为像素图
                pix = page.get_pixmap(
                    matrix=mat,
                    alpha=False,  # 不需要透明度通道
                    annots=True,  # 包含注释
                    clip=None     # 不裁剪
                )
                
                # 保存为PNG
                pix.save(temp_png_path)
                
                # 如果有PIL支持，进行图像优化
                if Image is not None:
                    try:
                        pil_image = Image.open(temp_png_path)
                        
                        # 应用锐化滤镜提高文字清晰度
                        pil_image = pil_image.filter(ImageFilter.UnsharpMask(
                            radius=1.0,      # 锐化半径
                            percent=120,     # 锐化强度
                            threshold=1      # 锐化阈值
                        ))
                        
                        # 增强对比度
                        enhancer = ImageEnhance.Contrast(pil_image)
                        pil_image = enhancer.enhance(1.1)
                        
                        # 保存优化后的图像
                        pil_image.save(temp_png_path, format='PNG', optimize=True)
                        
                    except Exception as e:
                        print(f"第 {page_num+1} 页PIL图像处理失败: {e}")
                        # 继续使用基本PNG
                
                # 添加到结果列表
                png_paths.append(temp_png_path)
            
            doc.close()
            
            print(f"✅ PDF成功转换为 {len(png_paths)} 个PNG文件")
            return png_paths, None
            
        except Exception as e:
            error_msg = f"PDF转PNG失败: {str(e)}"
            print(f"❌ {error_msg}")
            return [], error_msg
    
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