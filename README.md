# ◈ EvoNote 

> **让思想自由生长。你的数据，你做主。**

EvoNote 是一款**本地优先 (Local-First)**、**追求丝滑性能的 Markdown 块粒度级大纲双链笔记**桌面应用。基于 Tauri + React + SQLite 的现代混合架构，它将类 Notion 的丝滑编辑体验与纯净的 Markdown 文件存储完美融合——你的数据永远是硬盘上可读的纯文本。
<img alt="image" src="https://github.com/user-attachments/assets/1fd1587a-c49d-422d-88b6-59868cc10840" />


> [!WARNING]
> - 用爱发电缘故之前 Python + Markdown 的方式，工程量过于庞大不太现实已经放弃，现采用成熟宽松协议的开源项目和胶水代码为主进行开发，力求用极少的开发时间完成高可用性的使用。

> [!CAUTION]
> **⚠️ 开发测试阶段 (Pre-Alpha)**
>
> 本项目目前仍处于**活跃的早期开发阶段**，核心架构与功能正在快速迭代中。
> - **请勿**将其用于管理重要或不可替代的数据。
> - 数据格式、API 和配置可能在未来版本中**发生不兼容变更**。
> - 当前版本仅供技术预览与测试反馈。
> - 请在使用前自行备份您的数据。

---

## ✨ 核心亮点

### ⚡ 物理级性能！
底层采用 **Rust + SQLite** 作为热缓存引擎。前端不直接处理海量文本——编辑器仅渲染视口内的 DOM 节点，**百万字百万块级别的单笔记页面依然丝滑流畅！！**

### 🔐 绝对的数据主权！
所有内容以标准 `.md` 纯文本文件存储在本地硬盘。没有云端锁定，没有私有数据库格式。卸载 EvoNote 后，你的笔记文件夹可以被任何文本编辑器直接打开。

### 🔄 双向无感同步！
**正向**：编辑器修改 → 防抖写入 SQLite → Rust 反向编译器自动生成标准 Markdown 文件。
**反向**：外部程序（如 VSCode）修改 `.md` 文件 → Rust 文件监听器侦测 → 自动解析并推送至编辑器实时更新。

### 🧱 高度解耦的缝合架构！
界面（React）、数据（SQLite）、文件（.md）三层完全解耦。未来可独立替换任意模块，或通过外部脚本（如 Python）直接读写 SQLite 数据库实现无头工作流 (Headless Workflow)。

---

## 🛠️ 技术栈

| 层级           | 技术                                                                                             | 职责                               |
| -------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------- |
| **桌面宿主**   | [Tauri V2](https://tauri.app/) (Rust)                                                            | 原生窗口、系统 API、文件 I/O       |
| **前端渲染**   | [React 18](https://react.dev/) + TypeScript + Vite                                               | UI 组件与状态管理                  |
| **块级编辑器** | [BlockNote](https://www.blocknotejs.org/)                                                        | 类 Notion 的丝滑块级编辑体验       |
| **热缓存引擎** | SQLite ([tauri-plugin-sql](https://github.com/tauri-apps/plugins-workspace/tree/v2/plugins/sql)) | 毫秒级数据持久化                   |
| **文件系统**   | Open / Dialog ([tauri-plugin-opener](https://v2.tauri.app/plugins/opener/) 等)                   | 与原生操作系统的资源管理器协同调用 |
| **文件监听**   | [notify](https://docs.rs/notify/) (Rust)                                                         | 实时侦测 `.md` 文件外部变更        |
| **数据序列化** | [serde_json](https://docs.rs/serde_json/) (Rust)                                                 | JSON ↔ Markdown 双向转换           |

---

## 📥 快速开始

### 环境要求

- **操作系统**：Windows 10/11
- **Node.js**：18.0+
- **Rust**：1.70+（通过 [rustup](https://rustup.rs/) 安装）

### 安装与运行

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/EvoNote.git
cd EvoNote

# 2. 安装前端依赖
cd app
npm install

# 3. 启动开发服务器（首次启动需编译 Rust 后端，约需数分钟）
npm run tauri dev
```

首次运行时，Cargo 将自动下载并编译约 300+ 个 Rust 依赖包。请耐心等待编译完成（后续启动将在数秒内完成）。

---

## 📁 项目结构

```text
EvoNote/
├── app/                        # Tauri + React 前端应用
│   ├── src/
│   │   ├── App.tsx             # 主界面组件（三栏布局 + 双向同步逻辑）
│   │   ├── App.css             # 全局设计系统（Catppuccin 深色主题）
│   │   ├── mdParser.ts         # Markdown → BlockNote JSON 正向解析器
│   │   └── main.tsx            # React 入口
│   ├── src-tauri/
│   │   ├── src/lib.rs          # Rust 核心（反向编译器 + 文件监听器 + IPC）
│   │   ├── capabilities/       # Tauri 安全权限配置
│   │   └── Cargo.toml          # Rust 依赖管理
│   └── package.json            # 前端依赖管理
├── parser_poc/                 # 阶段 1 原型验证（Markdown AST 解析 PoC）
├── old/                        # 旧版 Python/PySide6 代码归档（仅供参考）
├── evonote_sync.md             # 实时同步的 Markdown 输出文件
└── README.md                   # 本文件
```

---

## 🔮 演进路线图 (Roadmap)

- [x] **多文件管理**：侧边栏支持分组渲染、展示纯净文件名并直接新建或销毁笔记。
- [x] **数据源解耦**：用户可一键自定 Vault 存储系统路径，并可热转移和系统一键开箱。
- [x] **大纲双链雏形**：编辑器中输入 `[[` 自动捕获关联文件并提供下拉筛选器。
- [x] **反向链接面板**：页面**顶部栏**目展示当前笔记被引用的位置，直观的显示包含该页面的笔记页面。
- [x] **块引与块嵌入深度编辑**：不仅实现了源头块的双向同步，且提供**悬浮的完整子树渲染编辑模式**。
- [x] **跨页精确定位与滚动记忆**：在跳转到目标源位置时带有平滑定位闪烁特效；不同页面的滚动点状态将完全缓存记忆，永不丢失阅读进度。
- [x] **全文搜索**：基于 Rust `regex` 结合 Fuse.js 的秒级全文、文件名混合检索。
- [ ] **知识图谱**：可视化展示笔记间的双链关系网络
- [ ] **AI 无头工作流**：外部 Python 脚本直接读写 SQLite，实现自动化知识注入
- [ ] **主题切换**：亮色/暗色主题一键切换
- [ ] **导出与发布**：一键导出为 PDF / HTML

---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！在贡献之前，请注意：

1. 本项目目前处于早期开发阶段，架构可能随时调整
2. 请确保你的代码通过 `npm run build` 和 `cargo build` 的编译检查
3. 提交前请简要描述你的修改动机

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

## ⚖️ 免责声明

### 使用风险

本软件 **"按原样 (AS IS)"** 提供，不附带任何形式的明示或暗示保证，包括但不限于对适销性、特定用途适用性和不侵权性的保证。

**在任何情况下**，本项目的作者和贡献者均不对因使用或无法使用本软件而产生的任何直接、间接、附带、特殊、惩罚性或后果性损害（包括但不限于数据丢失、业务中断、计算机故障或其他商业损害）承担任何责任，即使已被告知此类损害的可能性。

### 数据安全

- 本软件目前处于 **Pre-Alpha 测试阶段**，可能存在未发现的 Bug 导致数据损坏或丢失。
- 用户有责任自行对重要数据进行备份。开发者不对任何数据丢失承担责任。
- 本软件的数据格式在正式版发布前可能发生不兼容变更。

### 第三方核心组件生态

EvoNote 秉持**“不重复造轮子，专注于架构总成”**的理念，站在开源巨人的肩膀上构建。本项目严格挑选基于宽松协议（MIT / Apache 2.0 / 类似）的顶级开源基建：

- **宿主与底座**：[Tauri V2](https://tauri.app/) (MIT / Apache-2.0)
- **前端与状态**：[React 18](https://react.dev/) (MIT) + [Zustand](https://github.com/pmndrs/zustand) (MIT)
- **高性能富文本**：[BlockNote](https://www.blocknotejs.org/) (MIT)
- **本地存储矩阵**：[SQLite](https://sqlite.org/) (Public Domain) + native Rust crates
- **资源管理器**：[react-arborist](https://github.com/brimdata/react-arborist) (MIT) —— 企业级可折叠树状结构组件
- **上下文菜单**：[react-contexify](https://github.com/fkhadra/react-contexify) (MIT) —— 节点右键操作菜单
- **图标库**：[react-icons](https://react-icons.github.io/react-icons/) (MIT) —— VSCode 风格图标集
- **全文搜索引擎**：Rust 原生实现 + [regex](https://docs.rs/regex) (MIT / Apache-2.0) —— 支持文件名、文件内容逐行搜索与正则表达式匹配

### 合规性与知识产权

1. **合规的框架构建**：本项目完全基于公开的技术文档与上述主流开源生态进行构建，不涉及对任何闭源商业软件的代码逆向。
2. **安全缝合协议指南（白名单与黑名单）**：未来的 EvoNote 官方扩展，以及各位开发者的二次开发（商用或开源），请务必遵循以下“安全缝合”的依赖引入原则，以确保您拥有绝对的代码主权与免责安全：
   - ✅ **放心使用的白名单协议**：`MIT License`、`Apache License 2.0`、`BSD License (2-Clause / 3-Clause)`、`Public Domain / WTFPL`。引入含有这些协议的代码或库，您享有极高自由度，支持闭源及商业售卖（通常仅需在项目中保留原始版权声明文本）。
   - ❌ **绝对禁止的黑名单协议（强传染性）**：`AGPL (Affero General Public License)`、`GPL (General Public License v2/v3)`。如果您将含有此类协议的代码直接编译或“缝合”进本软件，**您的整个软件及未来修改的代码将被强制要求开源**。请在选型时严格避开。
3. **隔离级调用策略**：如果某些极品功能模块（如本地 AI 底座）必须使用 GPL/AGPL 协议，安全的做法是**进程物理隔离**。即：让被调用程序作为独立的进程运行于后台，EvoNote 仅通过本地网络 API 或命令行与之通信（IPC），绝不将代码混合编译。
4. **知识产权与避风港声明**：本项目为基于无尘室设计（Clean Room）原则独立构建的开源软件。除文档中已声明引用的第三方宽松协议开源基建外，EvoNote 的核心业务逻辑、前端交互与底层通信代码均为开发者逐行独立编写，绝不涉及对任何闭源商业软件的代码逆向工程或源码窃取。本项目尊重并致力于保护知识产权，所有功能实现均依托合规的开源生态与行业通用设计规范。如果您认为本项目的任何部分无意间侵犯了您的合法权益，请通过项目主页联系开发者，我们将在核实后第一时间采取包括移除争议内容在内的配合措施。

---

## 🙏 致谢 (Acknowledgements)

任何伟大的产品都无法脱离开源社区的繁荣。EvoNote 能够保持极简、极速与极高的架构自由度，得益于以下卓越开源项目（均基于宽松许可证）：

- 致敬 **[Tauri](https://tauri.app/)** 团队提供的轻量化 Rust 桌面基座与系统原生能力；
- 致敬 **[BlockNote](https://www.blocknotejs.org/)** 与 ProseMirror 带来的工业级富文本编辑体验；
- 致敬 **[React](https://react.dev/)** 生态系统提供的高效前端状态驱动；
- 致敬 **[SQLite](https://sqlite.org/)** 提供的坚如磐石的单文件关系型数据库支撑；
- 致敬 **[react-arborist](https://github.com/brimdata/react-arborist)** 提供的顶级树组件，为侧边栏赋予了 VSCode 级体验；
- 致敬 **[react-contexify](https://github.com/fkhadra/react-contexify)** 提供的优雅右键上下文菜单。

是开源技术的无私共享，使得像 EvoNote 这样聚合型的架构成为可能。 

---

**使用本软件即表示您已阅读、理解并同意以上免责声明的全部内容。**

---

<p align="center">
  <strong>EvoNote</strong> — 让思想自由生长 🌱
</p>
