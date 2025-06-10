#!/usr/bin/env python3
"""
OCR功能测试脚本
用于验证EasyOCR在机械图纸上的识别效果
"""

import sys
import cv2
import numpy as np
from pathlib import Path

def test_dependencies():
    """测试依赖包是否正确安装"""
    print("🔍 测试依赖包...")
    
    try:
        import easyocr
        print("✅ EasyOCR 已安装")
    except ImportError:
        print("❌ EasyOCR 未安装")
        return False
    
    try:
        import torch
        print(f"✅ PyTorch 已安装，版本: {torch.__version__}")
        if torch.cuda.is_available():
            print(f"✅ CUDA 可用，GPU数量: {torch.cuda.device_count()}")
        else:
            print("⚠️  CUDA 不可用，将使用CPU模式")
    except ImportError:
        print("❌ PyTorch 未安装")
        return False
    
    try:
        import cv2
        print(f"✅ OpenCV 已安装，版本: {cv2.__version__}")
    except ImportError:
        print("❌ OpenCV 未安装")
        return False
    
    return True

def create_test_image():
    """创建一个包含机械图纸文本的测试图像"""
    # 创建白色背景
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    
    # 添加一些机械图纸常见的文本
    texts = [
        ("M8x1.25", (50, 50)),
        ("Φ20±0.1", (200, 50)),
        ("45°", (350, 50)),
        ("100×50", (50, 150)),
        ("Ra3.2", (200, 150)),
        ("304不锈钢", (350, 150)),
        ("表面镀锌", (50, 250)),
        ("±0.05", (200, 250)),
        ("R5", (350, 250))
    ]
    
    # 在图像上绘制文本
    font = cv2.FONT_HERSHEY_SIMPLEX
    for text, pos in texts:
        cv2.putText(img, text, pos, font, 1, (0, 0, 0), 2)
    
    return img

def test_ocr_recognition(image_path=None):
    """测试OCR识别功能"""
    print("\n🔍 测试OCR识别...")
    
    try:
        # 初始化EasyOCR
        print("正在初始化EasyOCR...")
        reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)  # 使用CPU模式避免GPU问题
        
        if image_path:
            # 读取指定图像
            if not Path(image_path).exists():
                print(f"❌ 图像文件不存在: {image_path}")
                return False
            image = cv2.imread(image_path)
        else:
            # 使用测试图像
            print("使用测试图像...")
            image = create_test_image()
            # 保存测试图像
            cv2.imwrite("test_mechanical_drawing.png", image)
            print("✅ 测试图像已保存为 test_mechanical_drawing.png")
        
        if image is None:
            print("❌ 无法读取图像")
            return False
        
        print("开始OCR识别...")
        # 执行OCR识别
        results = reader.readtext(image, detail=1)
        
        print(f"\n🎯 识别结果 (共{len(results)}个):")
        print("-" * 60)
        
        for i, (bbox, text, confidence) in enumerate(results, 1):
            print(f"{i:2d}. 文本: '{text}' | 置信度: {confidence:.3f}")
            
            # 计算边界框中心
            bbox_array = np.array(bbox)
            center_x = int(np.mean(bbox_array[:, 0]))
            center_y = int(np.mean(bbox_array[:, 1]))
            print(f"     位置: ({center_x}, {center_y})")
            
            # 分类文本类型
            text_type = classify_text(text)
            print(f"     类型: {text_type}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ OCR识别失败: {e}")
        return False

def classify_text(text):
    """简单的文本分类"""
    import re
    
    if re.match(r'M\d+', text, re.IGNORECASE):
        return "螺纹规格"
    elif 'Φ' in text or '∅' in text or 'ø' in text:
        return "直径标注"
    elif '°' in text:
        return "角度标注"
    elif '×' in text or 'x' in text:
        return "尺寸标注"
    elif '±' in text:
        return "公差标注"
    elif 'Ra' in text or 'Rz' in text:
        return "表面粗糙度"
    elif any(keyword in text for keyword in ['钢', '铜', '铝', '铁']):
        return "材料标记"
    elif any(keyword in text for keyword in ['镀', '涂', '处理']):
        return "表面处理"
    else:
        return "普通文本"

def main():
    """主函数"""
    print("=" * 60)
    print("🔧 IntelliAnnotate OCR 功能测试")
    print("=" * 60)
    
    # 测试依赖包
    if not test_dependencies():
        print("\n❌ 依赖包测试失败，请先安装必要的依赖包")
        sys.exit(1)
    
    # 测试OCR识别
    if len(sys.argv) > 1:
        # 使用命令行指定的图像文件
        image_path = sys.argv[1]
        print(f"\n使用图像文件: {image_path}")
        success = test_ocr_recognition(image_path)
    else:
        # 使用测试图像
        success = test_ocr_recognition()
    
    if success:
        print("✅ OCR功能测试通过!")
        print("\n📝 提示:")
        print("- 如果识别效果不理想，可以尝试调整图像质量")
        print("- 确保文字清晰、对比度良好")
        print("- 避免图像倾斜或模糊")
    else:
        print("❌ OCR功能测试失败!")
        sys.exit(1)

if __name__ == "__main__":
    main() 