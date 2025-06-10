# IntelliAnnotate 项目结构说明

## 📁 项目重构概述

本项目已完成模块化重构，将原本单一的 `intelliannotate.py` 文件（1924行）拆分为多个独立模块，提高了代码的可维护性和可扩展性。

## 📂 目录结构

```
pyqt-bubble/
├── main.py                    # 🚀 主入口文件
├── run.py                     # 🔧 启动脚本
├── intelliannotate.py         # 📦 原始文件（保留备份）
│
├── utils/                     # 🛠️ 工具模块
│   ├── __init__.py
│   ├── constants.py           # ⚙️ 常量定义
│   └── dependencies.py       # 📋 依赖检查
│
├── core/                      # 🏗️ 核心功能模块
│   ├── __init__.py
│   ├── annotation_item.py     # 🎯 气泡标注项
│   ├── file_loader.py         # 📄 文件加载器
│   └── ocr_worker.py          # 🔍 OCR工作线程
│
├── ui/                        # 🎨 用户界面模块
│   ├── __init__.py
│   ├── main_window.py         # 🏠 主窗口
│   ├── graphics_view.py       # 🖼️ 图形视图
│   ├── annotation_list.py     # 📝 标注列表
│   └── property_editor.py     # ✏️ 属性编辑器
│
├── requirements.txt           # 📋 依赖清单
├── README.md                  # 📖 项目说明
└── 使用说明.md               # 📚 使用指南
```

## 🔧 模块详细说明

### 1. 主入口模块 (`main.py`)
- **作用**: 应用程序启动入口
- **功能**: 
  - 初始化QApplication
  - 创建并显示主窗口
  - 设置应用程序属性

### 2. 工具模块 (`utils/`)

#### 2.1 常量定义 (`constants.py`)
- **作用**: 集中管理应用常量
- **内容**:
  - 应用信息配置
  - 文件格式支持列表
  - OCR语言配置
  - 界面样式配置
  - 颜色主题定义

#### 2.2 依赖检查 (`dependencies.py`)
- **作用**: 检查和管理外部依赖
- **功能**:
  - 检测OCR相关依赖包
  - 检测GPU支持状态
  - 提供依赖状态信息

### 3. 核心功能模块 (`core/`)

#### 3.1 气泡标注项 (`annotation_item.py`)
- **作用**: 实现可交互的气泡标注图形项
- **功能**:
  - 绘制气泡标注样式
  - 处理鼠标交互事件
  - 支持多种标注样式
  - 右键上下文菜单

#### 3.2 文件加载器 (`file_loader.py`)
- **作用**: 处理多种文件格式的加载
- **支持格式**:
  - 图像文件 (PNG, JPG, JPEG)
  - PDF文件 (高清渲染优化)
  - DXF文件 (基础支持)
- **特性**: 
  - PDF高质量渲染
  - 图像后处理优化

#### 3.3 OCR工作线程 (`ocr_worker.py`)
- **作用**: 后台OCR文字识别处理
- **功能**:
  - EasyOCR集成
  - 机械图纸预处理优化
  - 智能文本类型分类
  - 多语言支持

### 4. 用户界面模块 (`ui/`)

#### 4.1 主窗口 (`main_window.py`)
- **作用**: 应用程序主界面
- **功能**:
  - 界面布局管理
  - 菜单和工具栏
  - OCR控制面板
  - 事件处理和协调

#### 4.2 图形视图 (`graphics_view.py`)
- **作用**: 自定义图形显示视图
- **功能**:
  - 图纸缩放和平移
  - 区域选择模式
  - 鼠标交互处理

#### 4.3 标注列表 (`annotation_list.py`)
- **作用**: 标注项目列表管理
- **功能**:
  - 标注项目显示
  - 列表选择和高亮
  - 工具提示信息

#### 4.4 属性编辑器 (`property_editor.py`)
- **作用**: 标注属性编辑面板
- **功能**:
  - 标注信息显示
  - 文本内容编辑
  - 实时统计信息

## 🔄 模块间依赖关系

```
main.py
└── ui.main_window
    ├── utils.constants
    ├── utils.dependencies
    ├── core.ocr_worker
    ├── core.annotation_item
    ├── core.file_loader
    ├── ui.graphics_view
    ├── ui.annotation_list
    └── ui.property_editor
```

## 📦 打包兼容性

重构后的模块结构完全兼容原有的打包配置：

1. **PyInstaller**: 可正常使用现有的 `IntelliAnnotate.spec` 文件
2. **模块发现**: 所有模块采用相对导入，确保打包后路径正确
3. **依赖管理**: 依赖检查模块确保运行时环境正确

## 🚀 启动方式

### 方式1: 使用启动脚本（推荐）
```bash
python run.py
```

### 方式2: 直接启动
```bash
python main.py
```

### 方式3: 使用原文件（备份）
```bash
python intelliannotate.py
```

## ✨ 重构优势

1. **代码组织**: 功能模块化，职责清晰
2. **可维护性**: 单个模块文件大小适中，易于维护
3. **可扩展性**: 新功能可独立开发测试
4. **可重用性**: 核心模块可在其他项目中重用
5. **调试友好**: 问题定位更精确
6. **团队协作**: 多人可并行开发不同模块

## 🔧 开发建议

1. **新功能开发**: 优先考虑在相应模块中添加
2. **跨模块功能**: 使用信号-槽机制进行通信
3. **常量添加**: 统一在 `utils/constants.py` 中定义
4. **依赖管理**: 新增外部依赖需要在 `utils/dependencies.py` 中检查

## 📝 注意事项

- 原始 `intelliannotate.py` 文件被保留作为备份
- 新结构向后兼容，不影响现有的使用方式
- 所有功能保持不变，仅改进了代码组织结构 