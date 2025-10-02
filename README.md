# EvoNote - 可进化的笔记与自动化平台


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

EvoNote 是一个以 Python 为“第一公民 API”的、可无限生长的个人知识与自动化工作台。它被设计成通过强大的插件架构实现无限扩展。

## 当前状态 (V0.4.2b - 反向链接面板)

本版本在 V0.4.2a 的“链接可点击”基础上，新增异步“反向链接”功能：右侧提供“反向链接”面板，监听当前激活页面，后台线程查询 .enotes/index.db 的 links 表并列出所有指向该页面的来源笔记。点击任一来源项会触发全局导航请求日志。

快速体验：
1) 启动应用后，右侧可见“反向链接”面板；
2) 焦点进入编辑器或应用启动后默认激活 “Note A.md”，面板将异步展示其反链来源；
3) 点击列表项（如 “Note B.md”）观察控制台 INFO 日志。

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

## 项目结构 (V0.4.2b)

- [_temp_query.py](_temp_query.py) — 临时查询/调试脚本
- [_temp_test_completion.py](_temp_test_completion.py) — 后端补全服务验收脚本（无 UI 验证信号链路与检索）
- [.gitignore](.gitignore) — Git 忽略配置
- [acceptance_plan.md](acceptance_plan.md) — V0.4.1 验收执行计划
- [Another Note C.md](Another Note C.md) — 测试笔记（用于补全与索引验证）
- [main.py](main.py) — 应用主入口
- [Note A.md](Note A.md) — 测试笔记
- [Note B.md](Note B.md) — 测试笔记
- [pressure_test.py](pressure_test.py) — UI 响应性压力测试脚本
- [README.md](README.md) — 项目说明
- [renamed_target.md](renamed_target.md) — 重命名/链接更新流程测试文件
- [requirements.txt](requirements.txt) — 依赖清单
- [source.md](source.md) — 示例/测试源笔记
- [V0.4.1_Acceptance_Report.md](V0.4.1_Acceptance_Report.md) — 本版本最终验收报告

目录与子项
- [.enotes/](.enotes) — 运行时生成的数据目录（数据库与全文索引）
  - [.enotes/index.db](.enotes/index.db) — SQLite 数据库：文件元数据与链接关系
  - [.enotes/whoosh_index/](.enotes/whoosh_index) — Whoosh 全文索引目录
    - [.enotes/whoosh_index/_MAIN_223.toc](.enotes/whoosh_index/_MAIN_223.toc) — 当前主段 TOC
    - [.enotes/whoosh_index/MAIN_5t9n0crqjm363ocf.seg](.enotes/whoosh_index/MAIN_5t9n0crqjm363ocf.seg) — 索引段文件
    - [.enotes/whoosh_index/MAIN_dwrvkco24nn7mvu9.seg](.enotes/whoosh_index/MAIN_dwrvkco24nn7mvu9.seg) — 索引段文件
    - [.enotes/whoosh_index/MAIN_sgham1d7jr2cavpo.seg](.enotes/whoosh_index/MAIN_sgham1d7jr2cavpo.seg) — 索引段文件
    - [.enotes/whoosh_index/MAIN_WRITELOCK](.enotes/whoosh_index/MAIN_WRITELOCK) — 索引写锁

- [core/](core) — 应用微内核
  - [core/__init__.py](core/__init__.py) — 包初始化
  - [core/api.py](core/api.py) — 插件公共 API（预留）
  - [core/app.py](core/app.py) — 应用主类和主窗口（负责启动、服务与插件装配）
  - [core/parsing_service.py](core/parsing_service.py) — Markdown 解析服务
  - [core/plugin_manager.py](core/plugin_manager.py) — 插件发现、加载与注册
  - [core/rendering_service.py](core/rendering_service.py) — 渲染服务（预留）
  - [core/signals.py](core/signals.py) — 全局信号总线（UI/服务解耦通信；包含 page_navigation_requested、active_page_changed、backlink_query_requested、backlink_results_ready）
  - [core/ui_manager.py](core/ui_manager.py) — UI 管理与 Dock 布局

- [plugins/](plugins) — 插件集合
  - [plugins/.gitkeep](plugins/.gitkeep) — 空目录占位
  - [plugins/_broken_plugin.py](plugins/_broken_plugin.py) — 容错测试用损坏插件
  - [plugins/editor_plugin_interface.py](plugins/editor_plugin_interface.py) — 插件接口定义
  - [plugins/file_browser_plugin.py](plugins/file_browser_plugin.py) — 文件浏览器 Dock 插件
  - [plugins/statusbar_test_plugin.py](plugins/statusbar_test_plugin.py) — 状态栏演示插件
  - [plugins/completion_service.py](plugins/completion_service.py) — 无 UI 补全服务插件（异步后台线程、信号驱动）
  - [plugins/backlink_service.py](plugins/backlink_service.py) — 无 UI 反向链接服务插件（QThread/Worker，异步 SQLite 查询）
  - [plugins/backlink_panel.py](plugins/backlink_panel.py) — 反向链接 Dock 面板插件（监听 active_page_changed/backlink_results_ready，点击触发导航）
  - [plugins/editable_editor/](plugins/editable_editor) — 编辑器插件目录
    - [plugins/editable_editor/main.py](plugins/editable_editor/main.py) — ReactiveEditor：补全弹窗 UI + [[链接]] 实时渲染/悬停/点击发信号

- [services/](services) — 后台服务
  - [services/__init__.py](services/__init__.py) — 包初始化
  - [services/file_indexer_service.py](services/file_indexer_service.py) — 文件监控、数据库与 Whoosh 索引维护

- [tests/](tests) — 测试目录（当前为空，预留单元测试）

## 更新日志

### V0.4.2b (2025-10-02) - 反向链接面板 (Backlink Panel)
- 新功能: 右侧“反向链接”面板（QDockWidget + QListWidget），可点击来源项发起全局导航请求。
- 服务: 新增无 UI 的 Backlink Service 插件，后台线程查询 .enotes/index.db 的 links/files，并通过总线回传结果。
- 信号: 新增 GlobalSignalBus.active_page_changed、backlink_query_requested、backlink_results_ready；沿用 page_navigation_requested。
- 性能: 查询在后台线程执行，UI 仅清空/填充列表，切换数千条反链无卡顿（符合 NFR-1）。
- 解耦: 面板与服务之间仅通过全局信号通信，无直接 import（符合 NFR-2）。
- 验收: 所有验收项均通过。

### V0.4.2a (2025-10-02) - 链接可点击 (Clickable Links)
- 新功能: 编辑器内 `[[页面链接]]` 实时语义渲染（颜色+下划线）、悬停手形、左键点击发出全局导航信号。
- 架构: 严格遵循信号驱动导航，编辑器仅发射 GlobalSignalBus.page_navigation_requested，不承担打开页面等应用逻辑；应用核心记录 INFO 日志验证链路。
- 性能: 为 setExtraSelections 渲染更新引入 80ms 防抖，确保快速输入零卡顿。
- 兼容: 与 V0.4.1 的补全 UI 完全兼容，可并行工作。
- 验收: 4 项标准全部通过。

### V0.4.1 (2025-10-02) - 链接补全 UI
- 新功能: 页面链接 `[[...]]` 搜索补全，异步弹窗，键盘交互（↑/↓/Enter/Tab/Esc）。
- 架构: 全局信号总线解耦 UI 与服务；补全服务为无 UI 插件，采用单常驻线程处理查询。
- 修复: Whoosh 索引初始化赋值、线程竞争与等待时机问题。
- 验收: 详见 [V0.4.1_Acceptance_Report.md](V0.4.1_Acceptance_Report.md)。

### V0.4.0.1 (2025-10-02) - 索引与链接基础 (验收完成)
- **修复**: 解决了文件修改时链接重复索引的 Bug。
- **修复**: 解决了文件删除时链接数据残留的 Bug。
- **修复**: 彻底重构了文件重命名逻辑，确保了 `files` 表和 `links` 表的数据原子性更新。
- **验收**: 所有功能性 (FR) 和非功能性 (NFR) 需求均已通过验收测试。
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
