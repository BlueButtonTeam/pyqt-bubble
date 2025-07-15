#!/usr/bin/env python3
"""
常量定义文件
"""

# 应用信息
APP_NAME = "IntelliAnnotate"
APP_VERSION = "1.0"
APP_TITLE = "IntelliAnnotate - 智能图纸标注工具 (EasyOCR)"

# 文件格式支持
SUPPORTED_IMAGE_FORMATS = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.gif']
SUPPORTED_PDF_FORMATS = ['.pdf']
SUPPORTED_DXF_FORMATS = ['.dxf']
SUPPORTED_ALL_FORMATS = SUPPORTED_IMAGE_FORMATS + SUPPORTED_PDF_FORMATS + SUPPORTED_DXF_FORMATS

# 文件对话框过滤器
FILE_DIALOG_FILTER = (
    "所有支持的文件 (*.png *.jpg *.jpeg *.pdf *.dxf *.bmp *.tiff *.tif *.gif);;"
    "图像文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.gif);;"
    "PDF文件 (*.pdf);;"
    "DXF文件 (*.dxf)"
)

# GD&T符号映射
GDT_SYMBOL_MAP = {
    "线性": "⏤",
    "直线度": "⏤",
    "⏤": "⏤",
    "平面度": "⏥",
    "直径(Φ)": "⌀",
    "Φ": "⌀",
    "半径(R)": "R",
    "R": "R",
    "圆弧": "⌒",
    "线段": "⌓",
    "圆柱度": "⋭",
    "全周轮廓度": "⋮",
    "对称度": "⋯",
    "总跳动": "⌰",
    "尺寸原点": "⌱",
    "锥度": "⌲",
    "斜度": "⌳",
    "反锥孔": "⌴",
    "沉孔": "⌵",
    "角度(°)": "∠",
    "°": "∠",
    "∠": "∠",
    "螺纹": "M",
    "M": "M"
}

# 反向映射 (符号到文本)
GDT_TEXT_MAP = {
    "⏤": "直线度", 
    "⏥": "平面度", 
    "⌀": "直径", 
    "R": "半径", 
    "⌒": "圆弧", 
    "⌓": "线段", 
    "⋭": "圆柱度", 
    "⋮": "全周轮廓度", 
    "⋯": "对称度", 
    "⌰": "总跳动", 
    "⌱": "尺寸原点", 
    "⌲": "锥度", 
    "⌳": "斜度", 
    "⌴": "反锥孔", 
    "⌵": "沉孔", 
    "°": "角度",
    "∠": "角度", 
    "M": "螺纹"
}

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
    'thread_spec': (220, 20, 60, 120),        # 红色 - 螺纹规格(最重要)
    'diameter': (34, 139, 34, 120),           # 绿色 - 直径标注
    'dimension': (0, 100, 255, 120),          # 蓝色 - 尺寸标注
    'tolerance': (138, 43, 226, 120),         # 紫色 - 公差等级
    'surface_roughness': (255, 140, 0, 120),  # 深橙色 - 表面粗糙度
    'angle': (255, 215, 0, 120),              # 金色 - 角度标注
    'material': (0, 191, 255, 120),           # 深天蓝色 - 材料标记
    'surface_treatment': (255, 20, 147, 120), # 深粉色 - 表面处理
    'geometry': (50, 205, 50, 120),           # 酸橙绿色 - 几何特征
    'measurement': (70, 130, 180, 120),       # 钢蓝色 - 测量值
    'position': (255, 99, 71, 120),           # 番茄色 - 位置标记
    'number': (147, 112, 219, 120),           # 中紫色 - 数值
    'label': (169, 169, 169, 120),            # 暗灰色 - 标签
    'symbol': (255, 165, 0, 120),             # 橙色 - 符号
    'title': (25, 25, 112, 120),              # 午夜蓝色 - 标题
    'annotation': (91, 192, 235, 120)         # 淡蓝色 - 普通标注
}

# OCR文本类型到标注样式的映射
OCR_TYPE_TO_STYLE = {
    'thread_spec': 'error',         # 螺纹规格用红色
    'diameter': 'success',          # 直径标注用绿色
    'dimension': 'default',         # 尺寸标注用默认
    'tolerance': 'warning',         # 公差等级用警告色
    'surface_roughness': 'warning', # 表面粗糙度用警告色
    'angle': 'warning',             # 角度标注用警告色
    'material': 'success',          # 材料用绿色
    'surface_treatment': 'warning', # 表面处理用警告色
    'geometry': 'success',          # 几何特征用绿色
    'measurement': 'default',       # 测量值用默认
    'position': 'warning',          # 位置标记用警告色
    'number': 'default',            # 数值用默认
    'label': 'default',             # 标签用默认
    'symbol': 'warning',            # 符号用警告色
    'title': 'error'                # 标题用红色
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
    "全部", "螺纹规格", "直径标注", "尺寸标注", "公差等级", 
    "表面粗糙度", "角度标注", "材料标记", "表面处理", 
    "几何特征", "测量值", "位置标记", "数值", "标签", 
    "符号", "标题"
]

OCR_FILTER_TYPE_MAP = {
    "螺纹规格": "thread_spec",
    "直径标注": "diameter", 
    "尺寸标注": "dimension",
    "公差等级": "tolerance",
    "表面粗糙度": "surface_roughness",
    "角度标注": "angle",
    "材料标记": "material",
    "表面处理": "surface_treatment",
    "几何特征": "geometry",
    "测量值": "measurement",
    "位置标记": "position",
    "数值": "number",
    "标签": "label",
    "符号": "symbol",
    "标题": "title"
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

# 气泡大小滑块常量
BUBBLE_SIZE_MIN_PERCENT = 50    # 最小50%比例
BUBBLE_SIZE_MAX_PERCENT = 160   # 最大160%比例
BUBBLE_SIZE_DEFAULT_PERCENT = 100  # 默认100%比例
BUBBLE_SIZE_STEP = 10  # 步长10%

# 气泡排序常量
BUBBLE_REORDER_GRID_SIZE = 50  # 排序时使用的网格大小，用于从上到下从左到右的排序