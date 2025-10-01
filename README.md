# EvoNote - 可进化的笔记与自动化平台

[
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
](https://opensource.org/licenses/MIT)

EvoNote 是一个以 Python 为“第一公民 API”的个人知识与自动化工作台。它被设计成通过强大的插件架构实现无限扩展。

## 当前状态 (V0.2 - UI 骨架)

当前版本 (V0.2) 构建了一个功能完整的、完全由插件驱动的动态停靠 UI 系统。应用本身是一个“UI 空壳”，其所有可见的 UI 面板都由独立的插件提供和注册。

这为未来的功能开发提供了一个高度灵活和解耦的基础。

## 核心特性

- **微内核架构**: 内核极其轻量，只负责应用生命周期和插件管理。
- **插件驱动 UI**: 应用的所有 UI 组件都是由插件动态加载的。内核对具体插件一无所知。
- **高度解耦**: 插件之间、插件与内核之间通过稳定的 API 通信，确保系统的健壮性。
- **灵活的 UI 布局**: 基于 PySide6 的 `QDockWidget`，用户可以自由拖动、停靠、合并和浮动窗口。

## 技术栈

- **编程语言:** Python 3.10+
- **UI 框架:** PySide6

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
    pip install PySide6
    ```

3.  **运行应用:**
    ```bash
    python main.py
    ```

运行后，您应该能看到一个主窗口，左侧是“文件浏览器”面板，右侧是“编辑器”面板。您可以自由地与这些面板交互。

## 项目结构

```
EvoNote/
├── en_core/              # 包含核心微内核代码
│   ├── __init__.py
│   ├── app.py            # 主应用与窗口逻辑
│   ├── api.py            # 为插件提供的公共API (AppContext)
│   ├── plugin_manager.py # 插件发现与加载逻辑
│   └── ui_manager.py     # 插件与主窗口UI交互的管理器
├── plugins/              # 存放所有外部插件的目录
│   ├── file_browser_plugin.py
│   ├── editor_placeholder_plugin.py
│   └── statusbar_test_plugin.py
└── main.py               # 应用主入口文件
```

## 插件开发指南

EvoNote 的所有功能都由插件提供。创建一个新的插件非常简单。

### 1. 创建插件文件

在 `plugins/` 目录下创建一个新的 Python 文件 (例如 `my_awesome_plugin.py`)。

### 2. 实现 `register` 函数

每个插件都必须包含一个名为 `register` 的函数，它接收一个 `AppContext` 对象作为参数。这是插件的入口点。

```python
# my_awesome_plugin.py
from en_core.api import AppContext

def register(app_context: AppContext):
    print("My Awesome Plugin has been loaded!")
```

### 3. 与应用 UI 交互

`AppContext` 提供了访问核心功能的 API。最重要的一个是 `ui` 管理器。

#### 示例：添加一个可停靠的窗口

下面的例子展示了如何创建一个简单的 `QDockWidget` 并将其添加到主窗口的右侧。

```python
# my_awesome_plugin.py
from PySide6.QtWidgets import QDockWidget, QLabel
from PySide6.QtCore import Qt
from en_core.api import AppContext

def register(app_context: AppContext):
    # 1. 创建一个 QDockWidget
    my_dock = QDockWidget("My Awesome Plugin", app_context.main_window)
    
    # 2. 在其中放置一些控件
    my_label = QLabel("Hello from My Awesome Plugin!")
    my_dock.setWidget(my_label)
    
    # 3. 使用 UI 管理器将其添加到主窗口
    app_context.ui.add_dock_widget(my_dock, Qt.DockWidgetArea.RightDockWidgetArea)
```

将此文件放入 `plugins` 目录并重新启动 EvoNote，您就会看到新的停靠窗口出现。

## 更新日志

### V0.2 (2025-10-01) - UI 骨架
- **新功能**: 实现了完全由插件驱动的动态停靠 UI 系统。
- **新功能**: 添加了 `UIManager`，为插件提供稳定的 UI 交互 API。
- **改进**: `AppContext` API 扩展，以包含对 `UIManager` 的访问。
- **插件**: 创建了文件浏览器和编辑器占位符插件来构建基础 UI。

### V0.1 (2025-09-30) - 最小可行平台
- **项目初始化**: 建立了基于微内核 + 插件的核心架构。
- **新功能**: 实现了 `PluginManager`，能够动态发现和加载插件。
- **新功能**: 定义了初版的 `AppContext` API。
- **插件**: 创建了基础的 UI 和核心交互测试插件。
