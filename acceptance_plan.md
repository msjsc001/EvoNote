# EvoNote V0.4.1 验收计划

## 任务一：准备验收环境与数据

**目标：** 创建一个干净、可预测的测试环境，用于后续的功能验收。

**步骤：**

1.  **清理旧数据：**
    *   删除项目根目录下的 `index.db` 文件，以确保索引是全新生成的。

2.  **创建测试笔记文件：**
    *   在项目根目录下创建以下三个 Markdown 文件，用于测试链接补全功能。

    *   **`Note A.md`**:
        ```markdown
        # Note A
        This is the first test note.
        ```

    *   **`Note B.md`**:
        ```markdown
        # Note B
        This is the second test note.
        ```

    *   **`Another Note C.md`**:
        ```markdown
        # Another Note C
        This note has a multi-word title.
        ```

---
*（后续测试任务将在此文件后追加...）*

## 任务二：FR-1 & FR-2 - 信号总线与后台服务功能验收

**目标：** 独立验证后台补全服务的功能是否正确，以及是否与UI层完全解耦。

**方法：** 我们将编写一个临时的Python脚本 `_temp_test_completion.py`，它将模拟UI插件的行为：发射 `completion_requested` 信号，并监听 `completion_results_ready` 信号，然后打印结果。这可以在不运行完整UI的情况下，精确测试后台服务。

**步骤：**

1.  **创建测试脚本 `_temp_test_completion.py`：**
    *   此脚本需要初始化 `QApplication`。
    *   手动加载 `CompletionServicePlugin`。
    *   定义一个槽函数，用于接收 `completion_results_ready` 信号并打印结果。
    *   连接该槽函数到全局信号总线。
    *   发射 `completion_requested` 信号，使用不同的查询文本（例如 `'Note'` 和 `'Another'`)。
    *   启动事件循环，并在接收到结果后退出。

2.  **执行测试脚本：**
    *   在 `code` 模式下运行 `python _temp_test_completion.py`。

3.  **验证结果：**
    *   当查询为 `'Note'` 时，预期输出应包含 `Note A.md` 和 `Note B.md`。
    *   当查询为 `'Another'` 时，预期输出应包含 `Another Note C.md`。

## 任务三：FR-3 & NFR - 编辑器补全功能与交互验收

**目标：** 全面测试面向用户的补全功能，包括UI交互、响应速度和准确性。

**方法：** 运行完整的 EvoNote 应用程序，并模拟用户在编辑器中的输入行为。

**步骤：**

1.  **启动应用程序：**
    *   在 `code` 模式下运行 `python main.py`。

2.  **验证补全触发与显示：**
    *   在编辑器中输入 `[[`，预期会立即出现一个空的或包含所有笔记的补全弹窗。
    *   继续输入 `Note`，形成 `[[Note`。预期弹窗内容会异步刷新，最终显示 `Note A.md` 和 `Note B.md`。
    *   在输入过程中，编辑器不得出现任何可感知的卡顿 (NFR-1)。

3.  **验证键盘交互：**
    *   **向下键 (Down Arrow):** 按下方向键，高亮会移动到下一个选项。
    *   **向上键 (Up Arrow):** 按下方向键，高亮会移动到上一个选项。
    *   **回车/Tab键 (Enter/Tab):** 在高亮 `Note B.md` 时按下回车，编辑器中的文本应变为 `[[Note B.md]]`，并且弹窗关闭。
    *   **Escape键 (Esc):** 在任何时候按下 Esc，弹窗应立即关闭。

4.  **验证边界情况：**
    *   删除文本，当 `[[` 模式不再匹配时（例如删除了一个 `[`），弹窗应自动隐藏。

## 任务四：代码与架构符合性审查

**目标：** 再次确认最终代码完全符合 SRS 中定义的所有架构原则。

**步骤：**

1.  **代码审查：**
    *   检查 `plugins/completion_service.py` 和 `plugins/editable_editor/main.py`，确认它们之间没有 `import` 或直接方法调用。
    *   确认所有通信均通过 `core/signals.py` 中的 `GlobalSignalBus` 完成。
    *   确认 `CompletionServicePlugin` 没有创建任何 UI 组件（例如 `QDockWidget`）。
    *   确认 `CompletionWorker` 中的数据库查询是在一个单独的 `QThread` 中执行的。

## 任务五：生成最终验收报告

**目标：** 汇总所有测试结果，形成正式的 V0.4.1 验收报告。

**步骤：**

1.  **撰写报告：**
    *   创建一个 `V0.4.1_Acceptance_Report.md` 文件。
    *   在报告中，针对每一个验收项（FR-1, FR-2, FR-3, NFR-1, NFR-2）及其子项，记录测试结果（通过/失败）。
    *   对发现的任何问题进行描述。
    *   给出最终的验收结论：**通过** 或 **需要修复**。
## 任务六：V0.4.3 命令面板（Command Palette）验收计划

目标
- 验证命令架构（装饰器注册、全局可发现、可扩展）与命令面板 UI 的功能与响应性。
- 验证“工具启动器”Dock 的可移动、可隐藏、右键开关、以及通过命令路径打开命令面板。

范围与实现基线
- 命令契约与基础类：[core/command.py](core/command.py)
- 命令注册服务（装饰器）：[plugins/command_service.py](plugins/command_service.py)
- 命令面板 UI（分组、过滤、执行）：[core/command_palette.py](core/command_palette.py)
- 全局快捷键与打开逻辑：Ctrl+P/Cmd+P、事件过滤兜底：[core/app.py](core/app.py)
- 工具启动器 Dock（按钮入口与右键菜单开关）：[plugins/tool_launcher.py](plugins/tool_launcher.py)
- 内置命令：
  - 应用：命令面板 [plugins/command_palette_command.py](plugins/command_palette_command.py)
  - 文件：新建笔记 [plugins/new_note_command.py](plugins/new_note_command.py)
  - 关于：EvoNote [plugins/about_command.py](plugins/about_command.py)

前置条件
- 正常安装运行依赖（见 README）。
- 运行命令：python main.py
- 如需临时显示顶部“工具”菜单，设置环境变量（默认隐藏）：
  - Windows CMD: set EVONOTE_TOOLS_MENU=1 &amp;&amp; python main.py
  - PowerShell: $env:EVONOTE_TOOLS_MENU=1; python main.py

验收步骤与预期

1) 服务与命令注册日志
- 启动后在终端应看到：
  - 成功加载插件：'command_service.py'
  - INFO: Command registered: app.command_palette -&gt; 应用：命令面板
  - INFO: Command registered: file.new_note -&gt; 文件：新建笔记
  - INFO: Command registered: app.about -&gt; 关于：EvoNote
- 若未出现，检查 [plugins/command_service.py](plugins/command_service.py) 与各命令插件的 create_plugin 装饰器注册。

2) 命令面板打开方式
- 快捷键（推荐）：在主窗口聚焦时按 Ctrl+P（或 Cmd+P、Ctrl+Shift+P）；终端出现：
  - INFO: Shortcut triggered: Command Palette
  - INFO: Opening Command Palette...
- Dock 按钮：点击“工具启动器”中的“命令面板…”，终端出现其路径日志：
  - INFO: ToolLauncher: executing command 'app.command_palette'
  - INFO: Opening Command Palette...
- 打开逻辑基线：[core/app.py](core/app.py) 与 [plugins/tool_launcher.py](plugins/tool_launcher.py)

3) 列表分组与实时过滤
- 面板初始应显示分组标题（粗体且不可选）：[app]、[file]（可能还有 [misc]）。
- 在搜索框输入“笔记”，仅剩 [file] 组，且只包含“文件：新建笔记”。
- 组头为非可选项，↑/↓ 导航会自动跳过组头并选中真实命令。
- 实现基线：[core/command_palette.py](core/command_palette.py)

4) 命令执行与关闭
- 选择“关于：EvoNote”并回车或双击：
  - 面板关闭
  - 终端打印：INFO: Executing command: About EvoNote
- 基线实现：[plugins/about_command.py](plugins/about_command.py)

5) 工具启动器 Dock 行为
- 默认位于底部，可拖动到任意边或浮动，可关闭/隐藏。
- 在主窗口空白处右键，弹出面板名单菜单（包含“工具启动器”“Reactive Editor”“反向链接”等），可勾选显示/隐藏。
- 基线实现：[plugins/tool_launcher.py](plugins/tool_launcher.py)

6) 第三方扩展性（装饰器注册）
- 在 plugins 目录新增一个命令插件文件（例如 plugins/hello_command.py），在 create_plugin(app) 内部通过 app.app_context.commands.register 装饰器注册 BaseCommand 子类（无须改内核）。
- 重启应用后，命令自动出现在命令面板（分组依据 id 前缀）。
- 关键约束：
  - BaseCommand.id/ BaseCommand.title 必须为非空字符串
  - 命令 id 全局唯一，否则注册会抛出错误（去重保护在 [plugins/command_service.py](plugins/command_service.py)）

通过标准（全部满足为通过）
- Ctrl+P / Cmd+P 可打开命令面板，或通过“工具启动器→命令面板…”打开，终端日志与 UI 行为一致。
- 初始列表包含“文件：新建笔记”“关于：EvoNote”等注册命令，且按分组显示。
- 输入“笔记”，列表仅剩“文件：新建笔记”。
- 选中“关于：EvoNote”并回车，打印 INFO: Executing command: About EvoNote，且面板关闭。
- 新增任意命令插件文件并注册后，重启应用即可在命令面板看到该命令。

备注
- 若发现快捷键与某些输入法/系统存在冲突，已在 [core/app.py](core/app.py) 实施全局事件过滤兜底（QEvent.ShortcutOverride/KeyPress），并保留 Ctrl+Shift+P 作为回退组合键。
- 顶部“工具”菜单默认隐藏，仅在 EVONOTE_TOOLS_MENU=1 时启用；不影响 Dock 自由布局与右键开关体验。

---

## 任务七：V0.4.5 内容块同步引擎（完整版）验收计划

### 前置准备

1. 删除 `.enotes/index.db`，确保索引库为全新版本（包含 `block_instances`）。
2. 将 `Note A.md`、`Note B.md`、`Another Note C.md` 中预置以下示例块，方便复测：
   - `Note A.md`、`Note B.md` 均包含 `{{Shared Block}}`
   - `Another Note C.md` 保留其它内容，便于观察无关文件不被误改。
3. 启动应用：`python main.py`；等待初次索引完成（观察终端日志 `Task queue is empty. Indexer is idle.`）。

### 验收标准与测试流程

1. **实例追踪**
   - 操作：在三份笔记中分别插入 `{{Shared Block}}` 后保存。
   - 验证：使用 SQLite CLI 查询 `.enotes/index.db`：
     ```sql
     SELECT block_hash, file_path FROM block_instances WHERE block_hash = (
       SELECT hash FROM blocks WHERE content = 'Shared Block'
     );
     ```
     预期返回两行，分别指向 `Note A.md`、`Note B.md`。
2. **UI 与安全默认**
   - 操作：在 `Note A.md` 中将 `{{Shared Block}}` 修改为 `{{Shared Block Updated}}`，停止输入后等待 600ms。
   - 预期：块下方浮现半透明选项栏；无任何操作直接点击编辑器其它位置。
   - 验证：仅当前文件的块内容变成 `{{Shared Block Updated}}`，`Note B.md` 仍为原内容；数据库中出现新哈希且 block_instances 记录只更新当前文件。
3. **取消功能**
   - 操作：重复修改 `{{Shared Block}}`，当选项栏出现时点击 `[取消]`。
   - 验证：当前块内容恢复为修改前文本；浮动栏隐藏；数据库无新记录。
4. **全局更新功能**
   - 操作：再次修改 `Note A.md` 的块为 `{{Shared Block Global}}`，点击 `[全局更新]`。
   - 验证：
     - UI 层：选项栏立即隐藏，可继续编辑其它文本。
     - 后台：稍后（异步）`Note B.md` 以及所有引用文件自动更新为 `{{Shared Block Global}}`。
     - 数据：`blocks` 表新增/复用相应内容；`block_instances` 所有相关记录更新为新哈希。
5. **智能合并功能**
   - 准备：在 `Note A.md` 中另建 `{{Existing Target}}`，触发索引。
   - 操作：将原共享块修改为 `{{Existing Target}}` 并点击 `[全局更新]`。
   - 验证：数据库未插入重复内容，所有引用直接改指向 `{{Existing Target}}` 的既有哈希。
6. **垃圾回收功能**
   - 操作：在所有笔记中删除或替换掉 `{{Some Temp Block}}`，确保其不再被引用。
   - 验证：等待 5 分钟或重启应用，观察日志中 `GC: deleting … orphan blocks`；在数据库中确认该块的哈希从 `blocks`/`blocks_fts` 中移除。
7. **性能**
   - 准备：利用脚本或手动在 10+ 个 Markdown 文件内写入同一内容块。
   - 操作：对其中一处执行 `[全局更新]`。
   - 验证：主界面在批量替换期间保持可交互（无冻结），后台日志记录每个文件的原子写入。

### 附加回归

- 验证全局更新后再次在任一文件中编辑该块，引用计数仍正确显示浮动栏。
- 检查 `.enotes/index.db` 中的索引：`block_instances` 的 UNIQUE 约束保证无重复 `(block_hash, file_path)`。
- 若执行过程中出现崩溃或异常，记录日志与数据状态，重新初始化数据库后复测。

通过上述 7 条验收标准与性能回归全部通过即可宣布 V0.4.5 功能合格。
---

# V0.4.5a 验收计划

适用版本：V0.4.5a（窗口标题与关于信息应显示 V0.4.5a；参见 [core/app.py](core/app.py)）

## 一、范围与能力边界

- 链接跳转与隐藏 .md（含 `[[笔记名]]`、`[[子目录/笔记名]]`）
- Shift+点击，在新编辑窗口中打开（仅编辑器窗口）
- 从链接创建新笔记（缺失则默认生成于 [pages/](pages/) 下，文件名为“笔记名.md”）
- 内容块（`{{...}}`）：
  - IME 输入结束约 250ms 稳定触发浮窗
  - 支持“全局更新”与“取消恢复”
- 库管理：
  - 添加 / 切换 / 移除库
  - 清空并重建 [.EvoNotDB](.EvoNotDB)（包含 whoosh_index 与 index.db）
  - 禁止将程序目录设为库
  - 无库态显示欢迎语并禁用编辑
- 回归清单：
  - 反向链接面板：列表项不显示 .md 后缀
  - 补全基于 SQLite 的 files.stem 前缀匹配（候选不含 .md）

参考实现与位置：
- 应用与全局信号： [core/app.py](core/app.py)、[core/signals.py](core/signals.py)
- 配置与库结构： [core/config_manager.py](core/config_manager.py)
- 索引与内容块： [services/file_indexer_service.py](services/file_indexer_service.py)
- 编辑器/链接解析与新窗： [plugins/editable_editor/main.py](plugins/editable_editor/main.py)
- 补全服务： [plugins/completion_service.py](plugins/completion_service.py)
- 反向链接： [plugins/backlink_service.py](plugins/backlink_service.py)、[plugins/backlink_panel.py](plugins/backlink_panel.py)

---

## 二、开发者验收（Dev）

1) 全局信号触发与接收路径验证（导航/打开/活动页/库状态）
- 目标：验证以下信号在典型操作中被正确发射与接收（记录终端日志或断点）：
  - page_navigation_requested
  - page_open_requested
  - active_page_changed
  - vault_state_changed
- 步骤：
  - 启动应用：`python main.py`
  - 在编辑器内点击 `[[Note B]]` 链接，观察触发导航链路直至 active_page_changed
  - 按住 Shift 点击 `[[Note B]]`，观察触发新窗链路（open 请求）且活动页变更不影响主窗
  - 切换库与清空库，观察 vault_state_changed 的布尔状态与路径字符串
- 预期：
  - 日志/断点可见上述信号按序触发，异常时记录错误信息位置（见 [core/app.py](core/app.py)）

2) 线程正确性
- 目标：索引/补全/反链服务在独立线程运行，启停/rebuild 无资源泄漏
- 步骤：
  - 启动服务后打开/切换库，确认旧的 FileIndexerService.stop() 被调用，新服务 start()
  - 执行 rebuild_index（清空 .EvoNotDB 后重建），观察任务队列空闲后进入 idle
  - 观察补全与反链查询在工作线程执行（避免 UI 阻塞）
- 预期：
  - 线程创建/退出成对，任务入队后执行完成；UI 无明显卡顿（见 [services/file_indexer_service.py](services/file_indexer_service.py)、[plugins/completion_service.py](plugins/completion_service.py)）

3) 数据一致性（内容块）
- 目标：块写入原子，任务入队可追踪，blocks/blocks_fts 与 block_instances 映射一致
- 步骤：
  - 在 Note A.md 编辑 `{{Shared Block}}` 停止输入约 250ms，浮窗出现时点击“全局更新”
  - 使用 SQLite 查看 [.EvoNotDB/index.db](.EvoNotDB/index.db)：
    - blocks/blocks_fts 新内容存在
    - block_instances 中相关文件的实例 hash 一致更新
- 预期：
  - 未出现半写入状态；任何失败有日志与回滚；孤儿块后续由 GC 任务清理

4) 配置系统
- 目标：config.json 位置与内容正确；切换库后 app_context.current_vault_path 更新生效
- 步骤：
  - 切换库 A→B，检查配置持久化（参考 [core/config_manager.py](core/config_manager.py)）
  - 重启应用后应恢复到库 B；编辑器与服务均使用库 B 的路径
- 预期：
  - current_vault 与 vaults 列表更新，app_context.current_vault_path 与服务 db 路径一致

5) 无库态安全兜底
- 目标：在“无库态”时拦截导航/新窗请求，避免越界访问
- 步骤：
  - 从库管理移除当前库或启动时不选择库
  - 在编辑器尝试点击链接或 Shift+点击
- 预期：
  - 终端出现“no active vault, ignore ...”日志（参考 [core/app.py](core/app.py)），无崩溃，无文件创建

---

## 三、用户手动验收（UAT）

A. 链接与新窗
- 在 Note A.md 中点击 `[[Note B]]`，应跳转到 Note B
- 按住 Shift 点击 `[[Note B]]`，在“新窗口”打开，窗口标题为“Note B”
- 输入并选择 `[[New Note]]`，应创建 [pages/New Note.md](pages/New Note.md) 并跳转/新窗打开（取决于是否按住 Shift）
- 输入 `[[子目录/Note X]]` 并回车，若不存在应创建 [pages/子目录/Note X.md](pages/子目录/Note X.md)
- 补全下拉仅显示“笔记名”（stem），不包含 `.md`

B. 内容块（{{...}}）
- IME 结束约 250ms 后出现浮窗；UI 可交互，无卡顿
- 点击“全局更新”：其它文件中的该块同步更新
- 点击“取消”：当前块恢复为修改前文本

C. 库管理（工具栏）
- 打开“工具栏 → 库管理”：
  - 添加两个不同目录为库，成功后可在库列表看到
  - 切换库：编辑器与侧边栏联动更新；默认确保 [pages/](pages/) 与 [assets/](assets/) 自动创建
  - 移除库：可移除非当前库
  - 清空并重建索引：删除 [.EvoNotDB](.EvoNotDB) 后自动重建（出现 whoosh_index 与 index.db）
  - 尝试将程序目录作为库，应被拒绝并给出提示
- 无库态：
  - 显示欢迎语并禁用编辑、拦截跳转/新窗

D. 反链面板
- 列表项不显示 `.md` 后缀
- 点击列表项可正常跳转到对应笔记

---

## 四、回归清单

- 反向链接面板隐藏 `.md` 后缀（见 [plugins/backlink_panel.py](plugins/backlink_panel.py)）
- 补全基于 SQLite files.stem 的前缀匹配（见 [plugins/completion_service.py](plugins/completion_service.py)）
- 链接点击行为与新窗行为在多窗口下互不干扰（主窗与子窗）
- 重命名/创建后索引与补全结果一致

---

## 五、通过标准

- 运行 `python main.py`，主窗口标题显示 `V0.4.5a`
- README 的“快速上手”命令可直接执行（`pip install -r requirements.txt`、`python main.py`）
- README 与实际行为一致（.EvoNotDB / 库管理 / 无库态等描述）
- 本章节 Dev/UAT 所有步骤均按预期结果通过

---

## 六、回滚策略

- 版本号可随时回退（[core/app.py](core/app.py)）
- 文档变更仅涉及 README 与 Mermaid/验收文本，回滚对应文件不影响执行
# V0.4.5b 验收计划

适用版本：V0.4.5b（窗口标题应显示 V0.4.5b；参见 [core/app.py](core/app.py) 的 VERSION，待D5更新）

一、范围与能力边界
- 导航与常用按键
  - 新增“导航”QToolBar（后退/前进），按钮可拖拽自排序并持久化顺序配置
  - 导航历史服务：记录成功页面跳转历史，前进/后退联动按钮使能
- 窗口与编辑器
  - Shift+点击 [[笔记名]] 在主界面内弹出浮动 QDockWidget，可拖回任意停靠区
  - 编辑器 Dock 标题随当前笔记名自动更新
  - Dock 标题栏支持双击重命名，入队 rename_file 任务，全库同步更新 [[引用]]
- 索引与重命名
  - rename_file：磁盘重命名 + SQLite/Whoosh 更新 + 全库 [[旧名]] → [[新名]] 同步 + upsert
- 稳定性
  - {{ 输入时的触发加固：任意输入（含 {{12）不应清空文档
  - 自动保存：编辑停止约 800ms 后原子写入并 upsert（主/浮动编辑器统一）
- 库管理防御
  - UI 禁用当前库的移除
  - 配置层防御：拒绝移除 current_vault

实现基线（主要参考文件）
- 导航工具栏：[plugins/navigation_toolbar.py](plugins/navigation_toolbar.py)
- 导航历史服务：[services/navigation_history_service.py](services/navigation_history_service.py)
- 信号总线（新增 back/forward/state）：[core/signals.py](core/signals.py)
- 应用接线（历史、前进/后退、Shift+新窗）：[core/app.py](core/app.py)
- 编辑器（Dock标题、重命名UI、自动保存、{{加固}）：[plugins/editable_editor/main.py](plugins/editable_editor/main.py)
- 索引服务（rename_file + 全库同步 + 原子写）：[services/file_indexer_service.py](services/file_indexer_service.py)
- 配置层（UI设置、remove_vault 防御）：[core/config_manager.py](core/config_manager.py)

二、开发者验收（Dev）
1) 导航历史与工具栏联动
- 步骤：
  - 启动应用并加载库，依次导航到 Note A、Note B、Another Note C（点击或 [[链接]]）
  - 观察“导航”工具栏按钮使能状态随历史变化（后退可用/不可用）
- 预期：
  - 历史入栈仅发生在正常导航成功后（启动默认广播或 Shift+新窗不入栈）
  - 按钮状态与历史边界一致
- 参考实现：[core/app.py](core/app.py)，[services/navigation_history_service.py](services/navigation_history_service.py)，[plugins/navigation_toolbar.py](plugins/navigation_toolbar.py)

2) Shift+点击浮动Dock
- 步骤：
  - 在主编辑器 Shift+点击 [[Note B]]，应出现一个浮动 Dock（标题为“Note B”）
  - 将浮动 Dock 拖入主界面右侧停靠区，再拖出为浮动
- 预期：
  - 新窗为 QDockWidget，非独立 QMainWindow
  - 编辑、导航、补全在该窗保持正常
- 参考实现：[core/app.py](core/app.py)（Shift+新窗处理路径）

3) Dock 标题与重命名（UI→任务入队）
- 步骤：
  - 点击 [[Note A]] 后，Dock 标题为“Note A”
  - 双击标题进入编辑，改为“Note A Renamed”并回车
- 预期：
  - 标题立即更新；后台任务队列入队 {"type":"rename_file", "src_path", "dest_path"}
- 参考实现：[plugins/editable_editor/main.py](plugins/editable_editor/main.py)

4) rename_file 全库同步
- 步骤：
  - 等待后台任务完成（观察日志），检查磁盘与索引变化
  - 搜索全库所有 [[Note A]]、[[pages/Note A]] 等引用
- 预期：
  - 磁盘文件已重命名，Whoosh/SQLite 均更新
  - 所有 [[旧名]]、[[旧名#anchor]]、[[旧名|别名]]、[[pages/旧名…]] 均替换为 [[新名…]]，尾部锚点/别名保留
  - 所有变更文件已 upsert
- 参考实现：[services/file_indexer_service.py](services/file_indexer_service.py)

5) {{ 输入稳健性与自动保存
- 步骤：
  - 在空白笔记多次快速输入 {{、{{1、{{12、{{\n 等
  - 停止输入约 800ms，验证自动保存（文件时间戳变化与 upsert 日志）
- 预期：
  - 文档绝不会被清空；补全/弹窗失效仅隐藏，不影响文档
  - 自动保存仅在内容变化时写入，采用原子写；随后入队 upsert
- 参考实现与测试：[plugins/editable_editor/main.py](plugins/editable_editor/main.py)，[tests/test_content_block_input.py](tests/test_content_block_input.py)

6) 配置层防御：当前库不可移除
- 步骤：
  - 打开“库管理”，选择当前库，移除按钮应为禁用状态
  - 若通过其他路径调用 remove_vault(current_vault)，应被拒绝并日志警告
- 预期：
  - UI 与配置层双重防御生效
- 参考实现：[plugins/tool_launcher.py](plugins/tool_launcher.py)，[core/config_manager.py](core/config_manager.py)

三、用户手动验收（UAT）
1) 导航栏与历史
- 打开 Note A → Note B → Another Note C
- 连续点击“后退”：回到 Note B → 回到 Note A（按钮灰掉）
- 点击“前进”：回到 Note B
- 期望：按钮使能随历史边界自动变化

2) Shift+点击浮动窗口
- 在 Note A 中 Shift+点击 [[Note B]]，弹出浮动“Note B”
- 将其拖入右侧停靠，再拖出为浮动
- 在浮动窗口中输入文本，停顿 0.8s 后保存；切到主窗口再切回，内容仍在

3) 标题与重命名
- 点击 [[Note A]] 跳转；Dock 标题显示“Note A”
- 双击标题改名为“Note A Renamed”，回车
- 稍候在任意笔记内搜索 [[Note A]]，应自动变为 [[Note A Renamed]]（含锚点/别名尾部保持）

4) {{ 稳定性与输入
- 在空白或现有笔记快速输入 {{12、{{ 等
- 文档任何情况下不被清空，补全/弹窗仅按需显示/隐藏

5) 库管理
- 添加、切换库；尝试移除当前库 → 应提示或禁用
- 重建索引可用；切换库后默认 pages/ 与 assets/ 自动创建

6) 工具栏排序与持久化
- 拖动“后退/前进”按钮交换顺序
- 重启应用后顺序保持
- 修改 nav_history_maxlen 于配置并重启，历史长度按新值生效

四、前置条件
- 已选择有效库，存在 Note A.md、Note B.md、Another Note C.md
- 建议先执行一次索引初扫，等待“Indexer is idle”日志（或短暂延迟）

五、通过标准
- 本章节 Dev/UAT 全部步骤按预期通过
- 无库态安全：拦截导航/新窗并显示欢迎语
- 稳定性：无崩溃；编辑器在自动保存/补全/浮动窗期间保持可交互

六、回归与回滚
- 若 rename_file 异常：确认 rename 失败时配置与索引一致性（必要时重建索引）
- 若出现异常字符/路径冲突：应记录日志并拒绝提交；文档不损坏
- 文档变更与版本号回滚：调整 [core/app.py](core/app.py) 的 VERSION 与本文档对应条目