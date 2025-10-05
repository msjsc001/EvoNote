# EvoNote V0.4.6 验收报告

概述
- 目标：修复两个问题，并优化多窗口与面板的交互直觉。
  1) 在 A 窗 Shift+左键 [[B笔记]] 新窗后，所有窗口都变为 B。
  2) 关闭第 3 个笔记浮动窗后，在底层主窗右键菜单仍残留未勾选的窗口条目。
- 本版将版本号从 V0.4.5b 升级为 V0.4.6。

根因摘要
- 问题1：所有编辑器都订阅了全局激活页信号，且编辑器获得焦点时会广播激活页，导致多窗互相“拉扯”。
- 问题2：浮动 QDockWidget 默认 close() 仅隐藏未销毁，主窗的“窗口列表”仍保留其项。

交互准则（V0.4.6）
- 面板（如反链）：跟随当前获得焦点的编辑器窗口。
- 编辑器内容：互不干扰。主编辑器与浮动编辑器各自独立。
- 历史导航：仅主编辑器产生的导航进入全局历史；浮动窗普通点击在本窗内部切换，不污染全局历史。

实现变更（文件级）
- 新增面板上下文总线信号：[core/signals.py](core/signals.py)
  - panel_context_changed(str)：编辑器获得焦点或在本窗内导航时广播当前页，供面板更新。
- 反链面板订阅“面板上下文”并去重：[plugins/backlink_panel.py](plugins/backlink_panel.py)
  - 保留对 active_page_changed 的订阅以兼容旧行为，但不再依赖。
- 编辑器作用域与本地导航：[plugins/editable_editor/main.py](plugins/editable_editor/main.py)
  - 新增实例标志：_follow_global_active_page（默认 True）、_handle_navigation_locally（默认 False）。
  - 提取 _load_page_for_self(page) 用于“仅加载本编辑器”。
  - on_active_page_changed 加守卫：当 follow_global=False 时忽略全局切换。
  - focusInEvent 改为广播 panel_context_changed，而非 active_page_changed。
  - 新增 _resolve_and_ensure_page_local 与 _navigate_locally_to，用于浮动窗在本窗内解析/创建并加载目标页，同时入队索引 upsert，广播 panel_context_changed。
- 新窗创建与销毁：[core/app.py](core/app.py)
  - 新建浮动 QDockWidget 后设置 WA_DeleteOnClose=True，确保 close() 即销毁，不在底层右键菜单残留。
  - 对新窗编辑器设置：_follow_global_active_page=False、_handle_navigation_locally=True，并调用 _load_page_for_self(rel)。
  - 打开新窗与主编辑器导航时，补发 panel_context_changed 以驱动面板立即更新。
- 版本号更新为 0.4.6：[core/app.py](core/app.py)

关键行为验证
- Shift+左键 [[B笔记]]：
  - 新浮动窗加载 B；主编辑器保持原内容不变。
  - 焦点在新窗时，面板显示 B 的反链。
- 关闭浮动窗：
  - 主窗右键“窗口列表”不再显示已关闭的条目（销毁而非仅隐藏）。
- 主编辑器普通点击 [[C笔记]]：
  - 主编辑器切到 C；浮动窗不受影响。面板随当前焦点更新。
- 浮动窗内普通点击 [[D笔记]]：
  - 仅该浮动窗切到 D；不影响主编辑器与全局历史。
- 导航工具栏的后退/前进：
  - 仅作用于主编辑器维护的导航历史。

回归与兼容
- 面板仍保留 active_page_changed 订阅以兼容；但焦点切换与本地导航主要通过 panel_context_changed 驱动。
- 未改动现有命令、索引服务与其他插件接口。
- 编辑器内部自动保存、补全、内容块联动等逻辑不受影响。

变更清单（主要代码位置）
- [core/signals.py](core/signals.py)：新增 panel_context_changed 信号与注释。
- [plugins/backlink_panel.py](plugins/backlink_panel.py)：新增对 panel_context_changed 的订阅与去重。
- [plugins/editable_editor/main.py](plugins/editable_editor/main.py)：
  - 新增作用域标志、_load_page_for_self、_resolve_and_ensure_page_local、_navigate_locally_to；
  - 修改 focusInEvent 与 on_active_page_changed；
  - 修正本地路径解析细节。
- [core/app.py](core/app.py)：
  - _open_note_window 设置 WA_DeleteOnClose=true；
  - 新窗隔离全局激活，启用本地导航；
  - 在导航/开窗/启动/切库时补发 panel_context_changed；
  - VERSION 升级为 0.4.6。

手工验收步骤
1) 启动应用，确保标题显示 “EvoNote V0.4.6”。
2) 在主编辑器输入 [[B笔记]]，Shift+左键：应弹出新窗显示 B，主编辑器保持当前内容。
3) 将焦点切至新窗：反链面板显示 B 的反链。
4) 关闭新窗：主窗右键“窗口列表”中不应再出现该窗口条目。
5) 在主编辑器普通左键 [[C笔记]]：主编辑器切到 C，浮动窗（若存在）不变；工具栏后退按钮可用。
6) 在某个浮动窗普通左键 [[D笔记]]：仅该浮动窗切到 D；工具栏后退/前进不受其影响。

风险与缓解
- 面板重复刷新：通过简单去重减少重复查询；即使重复，也仅是轻量数据库读取。
- 未来若需要“浮动窗也维护独立历史”，可在本地导航中追加自有历史栈，不影响当前实现。

版本与文件
- 版本：V0.4.6
- 主要改动文件：
  - [core/signals.py](core/signals.py)
  - [core/app.py](core/app.py)
  - [plugins/editable_editor/main.py](plugins/editable_editor/main.py)
  - [plugins/backlink_panel.py](plugins/backlink_panel.py)

结论
- 已修复“新窗导致所有窗口变同一笔记”与“关闭后右键菜单残留”两项问题，并引入面板上下文机制，使面板随当前焦点窗口更新，符合直觉且最小侵入。