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