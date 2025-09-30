# EvoNote - 可进化的笔记与自动化平台

EvoNote 是一个以 Python 为“第一公民 API”的个人知识与自动化工作台。它被设计成通过强大的插件架构实现无限扩展。

## V0.1 - 最小可行平台

当前版本 (V0.1) 是 EvoNote 的基础核心。其唯一目标是建立并验证项目的核心技术架构：一个极简的微内核和一个能够加载并运行基础插件的插件管理系统。

**此版本不包含任何面向最终用户的笔记功能。** V0.1 是一个坚实、可靠的平台，所有未来的功能都将在此之上构建。

## 技术栈

- **编程语言:** Python 3.10+
- **UI 框架:** PySide6

## 开始使用

### 环境要求

- Python 3.10 或更高版本
- `pip` 包管理器

### 安装与运行

1.  **克隆仓库 (或下载源码):**
    ```bash
    git clone https://github.com/msjsc001/EvoNote.git
    cd EvoNote
    ```

2.  **安装所需依赖:**
    ```bash
    pip install PySide6
    ```

3.  **运行应用:**
    ```bash
    python main.py
    ```

运行后，您应该能看到一个主窗口，左侧有一个标题为“UI插件”的停靠窗口，同时状态栏会显示“Core Plugin Loaded Successfully.”消息并持续5秒。

## 项目结构

```
EvoNote/
├── en_core/              # 包含核心微内核代码
│   ├── __init__.py
│   ├── app.py            # 主应用与窗口逻辑
│   ├── api.py            # 为插件提供的公共API (例如 AppContext)
│   └── plugin_manager.py # 插件发现与加载逻辑
├── plugins/              # 存放所有外部插件的目录
│   ├── core_test_plugin.py
│   ├── ui_test_plugin.py
│   └── broken_plugin.py  # 用于错误处理测试的损坏插件
└── main.py               # 应用主入口文件
```

## 核心架构

EvoNote 构建于 **微内核 + 插件** 架构之上。

-   **微内核 (`en_core`):** 内核极其轻量。其主要职责是管理应用生命周期和插件系统。它不应包含任何具体的插件实现。
-   **插件 (`plugins`):** 所有功能都应作为插件来实现。内核会发现、加载并注册在 `plugins` 目录中找到的任何有效的 Python 模块。这确保了系统的高度解耦和稳定性，因为单个插件的失败不会导致主应用崩溃。
