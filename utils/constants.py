#!/usr/bin/env python3
"""
常量定义文件
"""

# 应用信息
APP_NAME = "IntelliAnnotate"
APP_VERSION = "1.0"
APP_TITLE = "IntelliAnnotate - 智能图纸标注工具 (EasyOCR)"

# 文件格式支持
SUPPORTED_IMAGE_FORMATS = ['.png', '.jpg', '.jpeg']
SUPPORTED_PDF_FORMATS = ['.pdf']
SUPPORTED_DXF_FORMATS = ['.dxf']
SUPPORTED_ALL_FORMATS = SUPPORTED_IMAGE_FORMATS + SUPPORTED_PDF_FORMATS + SUPPORTED_DXF_FORMATS

# 文件对话框过滤器
FILE_DIALOG_FILTER = (
    "所有支持的文件 (*.png *.jpg *.jpeg *.pdf *.dxf);;"
    "图像文件 (*.png *.jpg *.jpeg);;"
    "PDF文件 (*.pdf);;"
    "DXF文件 (*.dxf)"
)

# OCR设置
DEFAULT_OCR_LANGUAGES = {
    "中文+英文": ['ch_sim', 'en'],
    "仅中文": ['ch_sim'],
    "仅英文": ['en']
}

# PDF质量设置
PDF_QUALITY_OPTIONS = {
    "标准 (2x)": 2.0,
    "高清 (4x)": 4.0,
    "超清 (6x)": 6.0,
    "极清 (8x)": 8.0
}

# 标注样式配置
ANNOTATION_STYLES = {
    "default": {
        "normal_pen": (0, 0, 255),
        "normal_brush": (255, 255, 255, 200),
        "selected_pen": (255, 0, 0),
        "selected_brush": (255, 255, 0, 100)
    },
    "warning": {
        "normal_pen": (255, 165, 0),
        "normal_brush": (255, 248, 220, 200),
        "selected_pen": (255, 69, 0),
        "selected_brush": (255, 218, 185, 150)
    },
    "error": {
        "normal_pen": (220, 20, 60),
        "normal_brush": (255, 192, 203, 200),
        "selected_pen": (178, 34, 34),
        "selected_brush": (255, 160, 122, 150)
    },
    "success": {
        "normal_pen": (34, 139, 34),
        "normal_brush": (240, 255, 240, 200),
        "selected_pen": (0, 128, 0),
        "selected_brush": (144, 238, 144, 150)
    }
}

# OCR文本类型颜色映射
OCR_TEXT_TYPE_COLORS = {
    'thread_spec': (255, 0, 0, 100),      # 红色 - 螺纹规格
    'diameter': (0, 255, 0, 100),         # 绿色 - 直径标注
    'dimension': (0, 0, 255, 100),        # 蓝色 - 尺寸标注
    'angle': (255, 255, 0, 100),          # 黄色 - 角度标注
    'number': (255, 0, 255, 100),         # 紫色 - 数值
    'material': (0, 255, 255, 100),       # 青色 - 材料
    'surface_treatment': (255, 165, 0, 100),  # 橙色 - 表面处理
    'annotation': (128, 128, 128, 100)    # 灰色 - 普通标注
}

# OCR文本类型到标注样式的映射
OCR_TYPE_TO_STYLE = {
    'thread_spec': 'error',      # 螺纹规格用红色
    'diameter': 'success',       # 直径标注用绿色
    'dimension': 'default',      # 尺寸标注用默认
    'angle': 'warning',          # 角度标注用警告色
    'material': 'success',       # 材料用绿色
    'surface_treatment': 'warning'  # 表面处理用警告色
}

# 样式名称映射
STYLE_NAME_MAP = {
    "default": "默认",
    "warning": "警告", 
    "error": "错误",
    "success": "成功"
}

STYLE_NAME_REVERSE_MAP = {
    "默认": "default",
    "警告": "warning",
    "错误": "error",
    "成功": "success"
}

# OCR筛选选项
OCR_FILTER_OPTIONS = [
    "全部", "螺纹规格", "直径标注", "尺寸标注", 
    "角度标注", "数值", "材料标记", "表面处理"
]

OCR_FILTER_TYPE_MAP = {
    "螺纹规格": "thread_spec",
    "直径标注": "diameter", 
    "尺寸标注": "dimension",
    "角度标注": "angle",
    "数值": "number",
    "材料标记": "material",
    "表面处理": "surface_treatment"
}

# 界面样式常量
UI_COLORS = {
    "primary": "#6f7eac",
    "secondary": "#8a9bb8", 
    "success": "#7ba05b",
    "background": "#f8f9fa",
    "white": "#ffffff",
    "border": "#dee2e6",
    "text": "#212529",
    "text_secondary": "#495057"
}

# 默认窗口尺寸
DEFAULT_WINDOW_SIZE = (1400, 900)
DEFAULT_WINDOW_POSITION = (100, 100)

# 标注相关常量
DEFAULT_CIRCLE_RADIUS = 15
DEFAULT_LEADER_LENGTH = 30
MIN_SELECTION_AREA = 10  # 最小选择区域像素 