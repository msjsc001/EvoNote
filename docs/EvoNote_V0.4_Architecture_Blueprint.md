# EvoNote V0.4 - 架构演进蓝图: 结构化文档编辑器

## 1. 核心问题

当前V0.3的“差分更新纯文本”架构虽然实现了基础编辑，但无法从根本上解决复杂的输入场景（如回车、列表缩进）和实现Markdown的所见即所得（WYSIWYG）编辑，因为其**纯文本数据模型无法表达丰富的结构和样式信息**。

## 2. 范式迁移：从“文本流”到“结构化文档”

V0.4的核心是一次架构范式迁移。我们将不再把文档看作一个巨大的字符串，而是将其视为一个由不同类型的**“块”（Block）**组成的有序列表。

- **ParagraphBlock**: 普通段落。
- **HeaderBlock**: 标题 (h1, h2等)。
- **CodeBlock**: 代码块。
- **ListBlock**: 列表项。

## 3. V0.4 架构三大支柱

### 3.1 支柱一：`Block` 化的数据模型 (Model)
- **`Document` 模型重构**: 内部数据结构从 `list[str]` 演变为 `self.blocks: list[Block]`。
- **`Block` 基类**: 定义所有块的通用接口。
- **Markdown 解析/序列化**: `parsing_service` 的职责演变为在 `Markdown文本` 和 `list[Block]` 之间进行双向转换。

### 3.2 支柱二：自定义文档布局与渲染 (View)
- **放弃 `QPlainTextEdit`**: 迁移到功能更强大的 `QTextEdit`，利用其底层的 `QTextDocument` 作为渲染画布。
- **渲染逻辑**: 渲染服务遍历 `self.blocks`，为每个 `Block` 在 `QTextDocument` 中创建对应的 `QTextBlock` 并应用相应的样式（`QTextFormat`）。

### 3.3 支柱三：面向结构的命令式编辑 (Controller)
- **上下文感知**: 编辑器逻辑始终知道光标当前所在的 `Block`。
- **命令模式 (Command Pattern)**: 用户操作被翻译成精确的命令对象。
  - `Enter` -> `SplitBlockCommand`
  - `Backspace` at start -> `MergeWithPreviousBlockCommand`
  - `# ` at start -> `ChangeBlockTypeCommand`
- **细粒度更新**: 命令直接修改 `self.blocks` 列表，并只触发**受影响块**的局部重新渲染，从根本上解决光标和输入问题。

## 4. 流程示例：将段落转为标题

```mermaid
graph TD
    subgraph 用户输入
        A[键盘事件: 输入'#'和空格]
    end

    subgraph Controller
        B{上下文判断: 当前在ParagraphBlock开头} --> C[创建 ChangeBlockTypeCommand(target_block, 'Header')];
        C --> D[执行命令];
    end

    subgraph Model
        D --> E[修改 Document.blocks: 将ParagraphBlock替换为HeaderBlock];
        E --> F[发出信号: block_changed(block_id, new_block)];
    end

    subgraph View
        F --> G{渲染服务响应信号};
        G --> H[在QTextDocument中找到对应的QTextBlock];
        H --> I[应用新的QTextFormat: 设置字号/粗体];
    end

    A --> B;
```

## 5. 建议的实施路线图 (Roadmap)

- **V0.4.1: 块数据模型与只读渲染**
  - 实现 `Block` 类体系。
  - 重构 `Document` 模型。
  - 实现 `Markdown -> list[Block]` 的解析。
  - 实现 `list[Block] -> QTextDocument` 的只读渲染。

- **V0.4.2: 实现第一个编辑命令**
  - 实现光标的块上下文感知。
  - 实现基础的段落内文本输入命令。

- **V0.4.3: 实现结构化编辑命令**
  - 实现块的分割 (`Enter`)、合并 (`Backspace`) 和类型转换 (`# `)。