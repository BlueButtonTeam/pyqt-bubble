#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PDF转换性能调试工具

此脚本用于测试PDF转换过程中的性能瓶颈，以便优化程序性能。
"""

import sys
import os
import time
import logging
import argparse
from pathlib import Path

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_pdf.log', 'w', 'utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('PdfDebugger')

# 设置PyQt环境
from PySide6.QtWidgets import QApplication, QGraphicsScene
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

# 导入文件加载器
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.file_loader import FileLoader, mark_debug_point, get_debug_report, reset_debug_marks

def test_pdf_conversion(pdf_path, page_index=0, quality=4.0):
    """测试PDF转换性能
    
    Args:
        pdf_path: PDF文件路径
        page_index: 页面索引
        quality: 转换质量
        
    Returns:
        tuple: (成功标志, 耗时, 临时文件路径)
    """
    logger.info(f"开始测试PDF转换: {pdf_path}, 页码: {page_index}, 质量: {quality}")
    
    scene = QGraphicsScene()
    start_time = time.time()
    
    try:
        # 测试转换
        pixmap, temp_path = FileLoader.load_pdf(pdf_path, scene, page_index, quality)
        
        if pixmap and not pixmap.isNull() and temp_path:
            elapsed = time.time() - start_time
            logger.info(f"转换成功，耗时: {elapsed:.3f}秒")
            logger.info(f"图像尺寸: {pixmap.width()}x{pixmap.height()}")
            logger.info(f"临时文件: {temp_path}")
            return True, elapsed, temp_path
        else:
            logger.error("转换失败，返回值无效")
            return False, time.time() - start_time, None
            
    except Exception as e:
        logger.exception(f"转换过程中发生异常: {e}")
        return False, time.time() - start_time, None

def compare_quality_settings(pdf_path, page_index=0):
    """比较不同质量设置下的性能
    
    Args:
        pdf_path: PDF文件路径
        page_index: 页面索引
    """
    logger.info(f"开始比较不同质量设置下的PDF转换性能: {pdf_path}")
    
    quality_options = [1.0, 2.0, 4.0, 6.0, 8.0]
    results = []
    
    for quality in quality_options:
        logger.info(f"测试质量 {quality}...")
        success, elapsed, temp_path = test_pdf_conversion(pdf_path, page_index, quality)
        results.append((quality, success, elapsed, temp_path))
        
    # 打印比较结果
    logger.info("\n性能比较结果:")
    logger.info("-" * 60)
    logger.info(f"{'质量':^10} | {'成功':^8} | {'耗时(秒)':^15} | {'临时文件':^25}")
    logger.info("-" * 60)
    
    for quality, success, elapsed, temp_path in results:
        status = "✅" if success else "❌"
        temp_file = os.path.basename(temp_path) if temp_path else "N/A"
        logger.info(f"{quality:^10.1f} | {status:^8} | {elapsed:^15.3f} | {temp_file:^25}")
    
    logger.info("-" * 60)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="PDF转换性能调试工具")
    parser.add_argument("pdf_path", help="PDF文件路径")
    parser.add_argument("-p", "--page", type=int, default=0, help="页码，从0开始计算")
    parser.add_argument("-q", "--quality", type=float, default=4.0, help="转换质量")
    parser.add_argument("-c", "--compare", action="store_true", help="比较不同质量设置")
    
    args = parser.parse_args()
    
    # 创建QApplication实例
    app = QApplication(sys.argv)
    
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF文件不存在: {args.pdf_path}")
        return 1
        
    if args.compare:
        compare_quality_settings(args.pdf_path, args.page)
    else:
        success, elapsed, temp_path = test_pdf_conversion(args.pdf_path, args.page, args.quality)
        
        if success:
            logger.info(f"测试完成，PDF转换成功，耗时: {elapsed:.3f}秒")
        else:
            logger.error(f"测试失败，PDF转换失败，耗时: {elapsed:.3f}秒")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 