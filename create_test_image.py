#!/usr/bin/env python3
"""
创建测试图片脚本
用于测试IntelliAnnotate应用
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_test_image():
    """创建一个包含机械图纸文本的测试图像"""
    # 创建白色背景
    width, height = 800, 600
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    # 尝试使用系统字体
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        small_font = ImageFont.truetype("arial.ttf", 18)
    except:
        try:
            font = ImageFont.load_default()
            small_font = font
        except:
            font = None
            small_font = None
    
    # 绘制标题
    draw.text((300, 50), "机械图纸测试", fill='black', font=font)
    
    # 绘制一些机械图纸常见的文本
    texts = [
        ("M8x1.25", (100, 150)),
        ("Φ20±0.1", (300, 150)),
        ("45°", (500, 150)),
        ("100×50", (100, 250)),
        ("Ra3.2", (300, 250)),
        ("304不锈钢", (500, 250)),
        ("表面镀锌", (100, 350)),
        ("±0.05", (300, 350)),
        ("R5", (500, 350))
    ]
    
    # 绘制文本
    for text, pos in texts:
        draw.text(pos, text, fill='black', font=small_font)
    
    # 绘制一些简单的几何图形
    # 矩形
    draw.rectangle([150, 400, 250, 500], outline='black', width=2)
    
    # 圆形
    draw.ellipse([350, 400, 450, 500], outline='black', width=2)
    
    # 线条
    draw.line([550, 400, 650, 500], fill='black', width=2)
    
    # 保存图片
    img.save('test_mechanical_drawing.png')
    print("✅ 测试图片已创建: test_mechanical_drawing.png")

if __name__ == "__main__":
    try:
        create_test_image()
    except ImportError:
        print("⚠️  PIL库未安装，无法创建测试图片")
        print("可以使用任何PNG/JPG图片进行测试")
    except Exception as e:
        print(f"❌ 创建测试图片失败: {e}") 