# EvoNote - 可进化的笔记与自动化平台

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

EvoNote 是一个以 Python 为“第一公民 API”的、可无限生长的个人知识与自动化工作台。通过微内核 + 插件架构，持续演进能力强。

## 当前状态 (V0.4.4 - 内容块引擎·基础)

本版本在 V0.4.3“命令面板”基础上，新增“内容块引擎（基础）”能力，围绕 `{{内容块}}` 实现了完整后台链路：
- 内容即地址：任何 `{{...}}` 被视为内容块，其身份由内容字符串的 SHA-256 哈希标识（严格不做 strip）。
- 后台索引：在文件变更时自动识别并写入 SQLite 的 `blocks` 表，并建立 FTS5 搜索索引。
  - 表创建与初始化见 [FileIndexerService._init_storage()](services/file_indexer_service.py:82)
  - 内容块提取、哈希与入库见 [FileIndexerService._index_content_blocks()](services/file_indexer_service.py:352)
- 补全服务：新增 `completion_type='content_block'`，基于 `blocks_fts` 实时前缀搜索；若 FTS5 不可用则回退 `LIKE`。
  - 类型分流见 [CompletionWorker.search()](plugins/completion_service.py:30)
- 编辑器交互：在输入 `{{` 后复用已有补全 UI 弹出候选，选中后插入 `{{候选内容}}`。
  - 触发逻辑见 [ReactiveEditor._check_for_completion_trigger()](plugins/editable_editor/main.py:101)
  - 结果填充见 [ReactiveEditor._on_completion_results_ready()](plugins/editable_editor/main.py:145)
  - 插入逻辑见 [ReactiveEditor.insert_completion()](plugins/editable_editor/main.py:157)

V0.4.4 明确不包含“同步修改”等高级能力，后续版本实现。

## 快速开始

1) 安装依赖
```bash
pip install -r requirements.txt
```

2) 运行应用
```bash
python main.py
```

3) 体验要点
- 在编辑器任一笔记中输入：`{{Hello World}}`，稍候后台会将该内容哈希写入数据库。
- 在新笔记中输入：`{{He`，应弹出补全列表，包含“Hello World”；选择后会插入 `{{Hello World}}`。
- 再将其改成 `{{Hello EvoNote}}`，数据库将新增一条新内容块记录，旧记录仍在。

提示：首次运行会在仓库根创建运行时目录 `.enotes/`（包含 `index.db` 与 Whoosh 索引）。该目录属于运行产物，默认不应提交到版本库。

## 架构概览

- 微内核
  - 应用入口与主窗口： [EvoNoteApp.run()](core/app.py:185)
  - 插件系统： [PluginManager](core/plugin_manager.py)
  - UI 容器： [UIManager](core/ui_manager.py)
  - 全局总线： [GlobalSignalBus](core/signals.py)

- 后台服务
  - 文件与索引服务： [FileIndexerService](services/file_indexer_service.py)
    - 数据库表：`files`, `links`, 新增 `blocks`；FTS5 虚表：`blocks_fts`
    - Whoosh 全文索引用于页面/路径搜索（与内容块索引互不干扰）

- 插件
  - 编辑器（可编辑 + 补全 UI）： [ReactiveEditor](plugins/editable_editor/main.py)
  - 补全服务（无 UI）： [CompletionServicePlugin](plugins/completion_service.py)

## 功能要点 (V0.4.4)

- 内容即地址（Content-Addressable）
  - 对 `{{...}}` 的纯文本内容计算 `hashlib.sha256(content).hexdigest()`，作为唯一身份 ID。
- 去重入库
  - 使用 `INSERT OR IGNORE` 保证相同内容仅有一条 `blocks` 记录。
- 实时补全
  - `completion_type='content_block'` 触发后，优先查询 `blocks_fts`，否则回退 `LIKE` 前缀。
- UI 解耦
  - UI 通过总线发射与接收补全请求/结果：详见 [CompletionWorker.search()](plugins/completion_service.py:30)、[ReactiveEditor._on_completion_results_ready()](plugins/editable_editor/main.py:145)

## 版本升级小抄 (从 V0.4.3 升级到 V0.4.4)

无需手动迁移。首次启动会自动：
- 确保 `.enotes/` 与子目录存在
- 自动在 `index.db` 中创建/迁移 `blocks` 与 `blocks_fts`（若 FTS5 不可用会继续正常运行，改为 LIKE 查询）

## 验收摘要 (SRS V0.4.4 第7节)

以下五条标准均已通过，详见报告：
- 在笔记中输入 `{{Hello World}}`，`blocks` 表新增以其哈希为键的记录。
- 在另一笔记重复 `{{Hello World}}`，记录数不增加（去重生效）。
- 输入 `{{He` 出现补全，其中包含“Hello World”。
- 选择补全项后插入 `{{Hello World}}`。
- 修改为 `{{Hello EvoNote}}` 后，数据库新增新块记录，旧记录保留。

报告文档： [acceptance_report_v0.4.4.md](acceptance_report_v0.4.4.md)

## 项目结构（简要）

- 核心与服务
  - [core/](core)
  - [services/file_indexer_service.py](services/file_indexer_service.py)
- 插件
  - [plugins/editable_editor/](plugins/editable_editor)
  - [plugins/completion_service.py](plugins/completion_service.py)
- 运行时（不提交）
  - [.enotes/](.enotes) 运行时数据库与索引（已列入 .gitignore）

仓库保留了少量示例/测试笔记（如 `Note A.md`、`Note B.md`）以便快速体验；它们不影响程序功能，可按需删除或替换为你的笔记。

## 故障排查

- 没有看到补全
  - 确认已输入 `{{` 且有前缀（如 `{{He`）
  - 查看启动日志，若见 “Falling back to LIKE…” 也属正常（FTS5 不可用时的回退）
- 数据未入库
  - 等待 1~2 秒后台索引；或查看控制台是否有异常堆栈
- Windows 中文输入法导致快捷键冲突
  - 已通过全局事件过滤兜底逻辑降低冲突概率，详见 [EvoNoteApp](core/app.py)

## 更新日志

### V0.4.4 (2025-10-02) - 内容块引擎（基础）
- 数据库：
  - 新增 `blocks` 表与 `blocks_fts` 虚表，触发器保持同步（见 [FileIndexerService._init_storage()](services/file_indexer_service.py:82)）
- 索引：
  - 在文件创建/修改时识别 `{{...}}`，计算 SHA-256 并去重入库（见 [FileIndexerService._index_content_blocks()](services/file_indexer_service.py:352)）
- 补全：
  - 新增 `content_block` 类型，FTS5 前缀搜索，回退 LIKE（见 [CompletionWorker.search()](plugins/completion_service.py:30)）
- 编辑器：
  - `{{` 触发补全，复用弹窗，选择后插入 `{{内容}}`（见 [ReactiveEditor._check_for_completion_trigger()](plugins/editable_editor/main.py:101)、[ReactiveEditor.insert_completion()](plugins/editable_editor/main.py:157)）
- 验收：
  - 五条标准均通过，报告见 [acceptance_report_v0.4.4.md](acceptance_report_v0.4.4.md)

### V0.4.3 (2025-10-02) - 命令面板 (Command Palette)
- 命令面板 UI、全局快捷键、命令服务与装饰器注册等（详见源码注释与历史 README）

…更早版本历史略。

## 计划路线图

- V0.4.5（拟）：内容块“同步修改”（变更传播/锚定对齐）、冲突与历史、批量操作接口

## 许可协议

MIT License
