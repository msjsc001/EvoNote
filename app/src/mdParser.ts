// 核心胶水层（正向）：Markdown 纯文本 → BlockNote JSON 块树
// 移植自阶段 1 的 parse.js PoC，适配 TypeScript 与前端运行时环境
// 支持：段落、无序/有序列表、标题、代码块、待办项、属性注入(id:: / collapsed::)

import { v4 as uuidv4 } from "uuid";

// Logseq 属性正则：匹配 `key:: value` 格式
const PROP_REGEX = /^([a-zA-Z0-9_-]+)::\s*(.+)$/;

interface BlockNoteBlock {
    id: string;
    type: string;
    props: Record<string, any>;
    content: any[];
    children: BlockNoteBlock[];
}

/**
 * 从文本行中提取 Logseq 属性键值对
 */
function extractProperties(lines: string[]): {
    contentLines: string[];
    properties: Record<string, string>;
} {
    const properties: Record<string, string> = {};
    const contentLines: string[] = [];

    for (const line of lines) {
        const match = line.match(PROP_REGEX);
        if (match) {
            properties[match[1]] = match[2].trim();
        } else {
            contentLines.push(line);
        }
    }

    return { contentLines, properties };
}

/**
 * 解析 Markdown 内联格式为 BlockNote content 数组
 * 支持：**bold**, *italic*, ~~strike~~, `code`, [link](url)
 */
function parseInlineContent(
    text: string
): Array<{ type: string; text?: string; styles?: Record<string, any>; href?: string; content?: any[] }> {
    if (!text) return [{ type: "text", text: "", styles: {} }];

    const result: any[] = [];
    // 使用正则逐步拆分格式标记
    const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|~~(.+?)~~|`(.+?)`|\[([^\]]+)\]\(([^)]+)\))/g;

    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
        // 匹配前的纯文本
        if (match.index > lastIndex) {
            result.push({
                type: "text",
                text: text.slice(lastIndex, match.index),
                styles: {},
            });
        }

        if (match[2]) {
            // **bold**
            result.push({ type: "text", text: match[2], styles: { bold: true } });
        } else if (match[3]) {
            // *italic*
            result.push({ type: "text", text: match[3], styles: { italic: true } });
        } else if (match[4]) {
            // ~~strike~~
            result.push({ type: "text", text: match[4], styles: { strike: true } });
        } else if (match[5]) {
            // `code`
            result.push({ type: "text", text: match[5], styles: { code: true } });
        } else if (match[6] && match[7]) {
            // [text](url)
            result.push({
                type: "link",
                href: match[7],
                content: [{ type: "text", text: match[6], styles: {} }],
            });
        }

        lastIndex = match.index + match[0].length;
    }

    // 末尾纯文本
    if (lastIndex < text.length) {
        result.push({ type: "text", text: text.slice(lastIndex), styles: {} });
    }

    return result.length > 0 ? result : [{ type: "text", text, styles: {} }];
}

/**
 * 主入口：将完整的 Markdown 文本解析为 BlockNote JSON 块树
 */
export function markdownToBlocks(markdown: string): BlockNoteBlock[] {
    const lines = markdown.split(/\r?\n/);
    const blocks: BlockNoteBlock[] = [];

    // 解析状态栈：追踪缩进层级以构建父子关系
    // stack[i] = { indent: number, blocks: BlockNoteBlock[] }
    const stack: Array<{ indent: number; blocks: BlockNoteBlock[] }> = [
        { indent: -1, blocks },
    ];

    let i = 0;
    while (i < lines.length) {
        const line = lines[i];

        // 跳过纯空行
        if (line.trim() === "") {
            i++;
            continue;
        }

        // 计算当前行的缩进（空格数）
        const indentMatch = line.match(/^(\s*)/);
        const indent = indentMatch ? indentMatch[1].length : 0;
        const trimmed = line.trimStart();

        // 收集紧随当前行的属性行（下一行如果是 `key:: value` 形式）
        const propLines: string[] = [];
        let j = i + 1;
        while (j < lines.length) {
            const nextTrimmed = lines[j].trim();
            if (PROP_REGEX.test(nextTrimmed)) {
                propLines.push(nextTrimmed);
                j++;
            } else {
                break;
            }
        }
        const { properties } = extractProperties(propLines);

        // 解析块类型
        let block: BlockNoteBlock;

        if (trimmed.startsWith("- [x] ") || trimmed.startsWith("- [ ] ")) {
            // 待办项: - [x] text 或 - [ ] text
            const checked = trimmed.startsWith("- [x] ");
            const text = trimmed.slice(6);
            block = {
                id: properties.id || uuidv4(),
                type: "checkListItem",
                props: { ...properties, checked },
                content: parseInlineContent(text),
                children: [],
            };
        } else if (trimmed.startsWith("- ")) {
            // 无序列表项: - text
            const text = trimmed.slice(2);
            block = {
                id: properties.id || uuidv4(),
                type: "bulletListItem",
                props: { ...properties },
                content: parseInlineContent(text),
                children: [],
            };
        } else if (/^\d+\.\s/.test(trimmed)) {
            // 有序列表项: 1. text
            const text = trimmed.replace(/^\d+\.\s/, "");
            block = {
                id: properties.id || uuidv4(),
                type: "numberedListItem",
                props: { ...properties },
                content: parseInlineContent(text),
                children: [],
            };
        } else if (trimmed.startsWith("#")) {
            // 标题: # / ## / ###
            const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
            if (headingMatch) {
                block = {
                    id: properties.id || uuidv4(),
                    type: "heading",
                    props: { ...properties, level: headingMatch[1].length },
                    content: parseInlineContent(headingMatch[2]),
                    children: [],
                };
            } else {
                block = {
                    id: uuidv4(),
                    type: "paragraph",
                    props: {},
                    content: parseInlineContent(trimmed),
                    children: [],
                };
            }
        } else if (trimmed.startsWith("```")) {
            // 代码块: ```lang ... ```
            const language = trimmed.slice(3).trim();
            const codeLines: string[] = [];
            let k = i + 1;
            while (k < lines.length && !lines[k].trim().startsWith("```")) {
                codeLines.push(lines[k]);
                k++;
            }
            block = {
                id: uuidv4(),
                type: "codeBlock",
                props: { language },
                content: [{ type: "text", text: codeLines.join("\n"), styles: {} }],
                children: [],
            };
            // 跳过代码块的结束标记
            i = k + 1;
            // 找到合适的父级并插入
            while (stack.length > 1 && stack[stack.length - 1].indent >= indent) {
                stack.pop();
            }
            stack[stack.length - 1].blocks.push(block);
            continue;
        } else {
            // 普通段落
            block = {
                id: properties.id || uuidv4(),
                type: "paragraph",
                props: { ...properties },
                content: parseInlineContent(trimmed),
                children: [],
            };
        }

        // 根据缩进层级确定父子关系
        while (stack.length > 1 && stack[stack.length - 1].indent >= indent) {
            stack.pop();
        }

        // 将当前块插入到正确的父级
        stack[stack.length - 1].blocks.push(block);

        // 将当前块压入栈（作为潜在的父级）
        stack.push({ indent, blocks: block.children });

        // 跳过已处理的属性行
        i = j;
    }

    return blocks;
}
