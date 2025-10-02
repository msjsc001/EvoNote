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