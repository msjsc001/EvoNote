# EvoNote - 可进化的笔记与自动化平台

[

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

](https://opensource.org/licenses/MIT)

EvoNote 是一个以 Python 为“第一公民 API”的、可无限生长的个人知识与自动化工作台。它被设计成通过强大的插件架构实现无限扩展。

## 当前状态 (V0.3.2 - 响应式编辑器内核)

当前版本实现了一个**绝对稳健、行为符合原生体验的**可编辑文本核心。

在经历了V0.3.x系列的多次探索后，我们最终确立了**“信任框架，被动响应”**的核心架构原则。我们彻底放弃了所有手动拦截和处理键盘输入的复杂逻辑，100%回归并利用Qt框架强大的原生文本编辑引擎。

现在的编辑器是一个纯粹的 `QPlainTextEdit` 控件，它提供了“开箱即用”的、无任何“怪异”bug的原生编辑体验。我们的代码只在后台被动监听文本变化（通过`contentsChanged`信号），以实时更新Markdown AST，为未来的功能（如实时预览、语义分析等）奠定了坚实可靠的基础。

您可以参考 [`docs/EvoNote_V1.0_Architecture_Final.md`](docs/EvoNote_V1.0_Architecture_Final.md) 获取关于这次架构决策的完整阐述。

## 核心架构

- **微内核架构**: 内核极其轻量，只负责应用生命周期和插件管理。
- **插件驱动 UI**: 应用的所有 UI 组件都是由插件动态加载的。
- **响应式编辑器**: 编辑器内核利用Qt的原生编辑引擎，并通过信号槽机制响应式地驱动后台逻辑，确保了编辑体验的绝对稳定。

## 技术栈

- **编程语言:** Python 3.10+
- **UI 框架:** PySide6
- **Markdown 解析:** `markdown-it-py`

## 开始使用

### 环境要求

- Python 3.10 或更高版本
- `pip` 包管理器

### 安装与运行

1.  **克隆仓库:**
    ```bash
    git clone https://github.com/msjsc001/EvoNote.git
    cd EvoNote
    ```

2.  **安装依赖:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **运行应用:**
    ```bash
    python main.py
    ```

## 项目结构 (V0.3.2)

```
EvoNote/
├── core/                   # 核心微内核代码
│   ├── __init__.py         # 包初始化文件
│   ├── api.py              # 为插件提供的公共API上下文 (AppContext)
│   ├── app.py              # 应用主类(App)和主窗口(MainWindow)的定义与管理
│   ├── parsing_service.py  # 提供Markdown到AST的解析功能
│   ├── plugin_manager.py   # 负责动态发现、加载和管理所有插件
│   ├── rendering_service.py# 提供AST到QTextDocument的渲染功能 (当前未使用，为未来保留)
│   └── ui_manager.py       # 管理插件UI与主窗口的交互 (如添加DockWidget)
│
├── docs/                   # 项目架构与设计文档
│   └── EvoNote_V1.0_Architecture_Final.md
│
├── plugins/                # 存放所有插件的目录
│   ├── editable_editor/    # [核心] 响应式编辑器插件
│   │   └── main.py         #   - 实现ReactiveEditor控件和插件入口
│   ├── editor_plugin_interface.py # 定义所有编辑器插件必须遵守的接口(ABC)
│   ├── file_browser_plugin.py     # 提供文件浏览器DockWidget的插件
│   ├── statusbar_test_plugin.py   # 在状态栏显示消息的简单示例插件
│   ├── _broken_plugin.py   # 用于测试插件加载器容错性的损坏插件示例
│   └── .gitkeep            # 确保空目录可以被git追踪
│
├── tests/                  # 单元测试目录 (当前为空)
│
├── main.py                 # 应用主入口点，负责启动App
└── requirements.txt        # 项目的所有Python依赖
```

## 更新日志

### V0.3.2 (2025-10-01) - 响应式编辑器内核
- **架构**: 实施了“信任框架，被动响应”的最终架构，将编辑器内核完全建立在Qt原生引擎之上。
- **修复**: 从根本上解决了之前版本中所有的底层输入问题（如Tab键、光标错位等）。
- **简化**: 彻底移除了自定义的 `Document` 模型和 `diff-match-patch` 依赖，大幅简化了代码库。
- **功能**: 编辑器现在是一个功能完整的 `QPlainTextEdit`，每次内容变更都会在后台触发AST的重新解析。

### V0.3.1 (2025-10-01) - AST 只读渲染器
- **新功能**: 实现了基于 AST 的 Markdown 只读渲染器。
- **改进**: 渲染器目前支持**标题**和**段落**的正确显示。

### V0.3.0 (2025-10-01) - AST Parser Integration
- **核心架构**: 成功集成了 `markdown-it-py` 解析库。

### V0.2 (2025-10-01) - UI 骨架
- **新功能**: 实现了完全由插件驱动的动态停靠 UI 系统。

### V0.1 (2025-09-30) - 最小可行平台
- **项目初始化**: 建立了基于微内核 + 插件的核心架构。
