# EvoNote - 可进化的笔记与自动化平台


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

EvoNote 是一个以 Python 为“第一公民 API”的、可无限生长的个人知识与自动化工作台。它被设计成通过强大的插件架构实现无限扩展。

## 当前状态 (V0.4.0 - 索引与链接基础)

此版本完成了 EvoNote 的**后台数据处理核心**。我们构建了一个能够监控文件系统、建立和维护 SQLite 数据库与 Whoosh 全文索引的异步服务。

这个版本是一个“无头(Headless)”的功能版本，**不包含任何新的面向用户的UI功能**，其所有成果都通过后台日志和数据库文件的变化来验证。它为未来的链接补全、反向链接面板和全文搜索等功能奠定了坚实的数据基础。

## 核心架构

- **微内核架构**: 内核极其轻量，只负责应用生命周期和插件管理。
- **插件驱动 UI**: 应用的所有 UI 组件都是由插件动态加载的。
- **响应式编辑器**: 编辑器内核利用Qt的原生编辑引擎，并通过信号槽机制响应式地驱动后台逻辑。
- **异步索引服务**: 一个独立的后台服务，负责监控文件变化，并异步地更新数据库和全文搜索引擎，确保UI的绝对流畅。

## 技术栈

- **编程语言:** Python 3.10+
- **UI 框架:** PySide6
- **Markdown 解析:** `markdown-it-py`
- **文件监控:** `watchdog`
- **全文搜索:** `whoosh`
- **数据库:** `sqlite3`

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

## 项目结构 (V0.4.0)

```
EvoNote/
├── .enotes/                # [运行时生成] 存放索引、数据库等缓存文件
├── core/                   # 核心微内核代码
│   ├── __init__.py         # 包初始化文件
│   ├── api.py              # 为插件提供的公共API上下文 (未使用)
│   ├── app.py              # 应用主类(EvoNoteApp)和主窗口(MainWindow)
│   ├── parsing_service.py  # 提供Markdown到AST的解析功能
│   ├── plugin_manager.py   # 负责动态发现、加载和管理所有插件
│   ├── rendering_service.py# 提供AST到QTextDocument的渲染功能 (为未来保留)
│   └── ui_manager.py       # 管理插件UI与主窗口的交互
│
├── plugins/                # 存放所有插件的目录
│   ├── editable_editor/    # [核心] 响应式编辑器插件
│   │   └── main.py         #   - 实现ReactiveEditor控件和插件入口
│   ├── editor_plugin_interface.py # 定义所有编辑器插件必须遵守的接口
│   ├── file_browser_plugin.py     # 提供文件浏览器DockWidget的插件 (未使用)
│   ├── statusbar_test_plugin.py   # 在状态栏显示消息的简单示例插件
│   ├── _broken_plugin.py   # 用于测试插件加载器容错性的损坏插件示例
│   └── .gitkeep            # 确保空目录可以被git追踪
│
├── services/               # 后台服务目录
│   ├── __init__.py         # 包初始化文件
│   └── file_indexer_service.py # 核心文件索引与监控服务
│
├── tests/                  # 单元测试目录
│
├── .gitignore              # Git忽略文件配置
├── main.py                 # 应用主入口点
├── README.md               # 项目说明文件
└── requirements.txt        # 项目的所有Python依赖
```

## 更新日志

### V0.4.0 (2025-10-02) - 索引与链接基础
- **新功能**: 实现了完整的后台文件监控、数据库和全文索引服务。
- **架构**: 引入了基于任务队列的异步处理模型，确保UI流畅。
- **依赖**: 添加了 `watchdog` 和 `whoosh`。

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
