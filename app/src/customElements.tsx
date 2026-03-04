import { createReactInlineContentSpec, useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine";
import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";

declare global {
    interface Window {
        evoCustomSchema: any;
    }
}

// ==================== 通用样式常量 ====================
const COLORS = {
    accent: "var(--accent, #89b4fa)",
    accentDim: "var(--accent-dim, rgba(137,180,250,0.15))",
    text: "var(--text, #cdd6f4)",
    textMuted: "var(--text-muted, #6c7086)",
    surface: "var(--surface, rgba(49,50,68,0.5))",
    border: "var(--border, #45475a)",
    danger: "#f38ba8",
    dangerDim: "rgba(243,139,168,0.1)",
};

// ==================== 工具栏按钮渲染器 ====================
type ToolbarItem = { icon: string; title: string; onClick: () => void; danger?: boolean };
function TOOLBAR_ITEMS(items: ToolbarItem[]) {
    return items.map((item, i) => (
        <span key={i}
            onClick={(e) => { e.stopPropagation(); item.onClick(); }}
            style={{ cursor: "pointer", padding: "2px 6px", borderRadius: "4px", color: item.danger ? COLORS.danger : COLORS.text }}
            onMouseEnter={(e) => (e.currentTarget.style.background = item.danger ? COLORS.dangerDim : COLORS.accentDim)}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            title={item.title}
        >{item.icon}</span>
    ));
}

// ==================== 浮窗大纲编辑器内容 ====================
function ActualEditor({ initialBlocks, onSave, onCancel }: any) {
    const editor = useCreateBlockNote({
        initialContent: initialBlocks,
        schema: window.evoCustomSchema as any // 使用全局绑定的 schema，避免循环依赖
    });

    const handleSave = async () => {
        onSave(editor.document);
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <div style={{ flex: 1, minHeight: "150px", maxHeight: "60vh", overflowY: "auto", background: COLORS.surface, borderRadius: "8px", border: `1px solid ${COLORS.border}`, padding: "8px", color: COLORS.text }}>
                <BlockNoteView editor={editor} theme="dark" formattingToolbar={true} />
            </div>
            <div style={{ display: "flex", gap: "8px", marginTop: "12px", justifyContent: "flex-end" }}>
                <span onClick={onCancel} style={{
                    cursor: "pointer", padding: "6px 16px", borderRadius: "6px", fontSize: "13px",
                    color: COLORS.textMuted, border: `1px solid ${COLORS.border}`,
                }}>取消</span>
                <span onClick={handleSave} style={{
                    cursor: "pointer", padding: "6px 16px", borderRadius: "6px", fontSize: "13px",
                    background: COLORS.accent, color: "#1e1e2e", fontWeight: 500,
                }}>保存</span>
            </div>
        </div>
    );
}

// ==================== 浮窗编辑模态 (可拖拽) ====================
function EditModal({ title, subtitle, initialBlocks, onSave, onCancel }: {
    title: string; subtitle: string; initialBlocks: any[];
    onSave: (newBlocks: any[]) => void; onCancel: () => void;
}) {
    const [pos, setPos] = useState({ x: window.innerWidth / 2 - 250, y: window.innerHeight / 2 - 200 });
    const [isDragging, setIsDragging] = useState(false);
    const dragRef = useRef({ startX: 0, startY: 0, initialX: 0, initialY: 0 });

    const handlePointerDown = (e: React.PointerEvent) => {
        setIsDragging(true);
        dragRef.current = { startX: e.clientX, startY: e.clientY, initialX: pos.x, initialY: pos.y };
        e.currentTarget.setPointerCapture(e.pointerId);
    };
    const handlePointerMove = (e: React.PointerEvent) => {
        if (!isDragging) return;
        setPos({
            x: dragRef.current.initialX + (e.clientX - dragRef.current.startX),
            y: dragRef.current.initialY + (e.clientY - dragRef.current.startY)
        });
    };
    const handlePointerUp = (e: React.PointerEvent) => {
        setIsDragging(false);
        e.currentTarget.releasePointerCapture(e.pointerId);
    };

    return (
        <div style={{
            position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
            background: "transparent", backdropFilter: "blur(2px)", zIndex: 9999, pointerEvents: "auto",
        }} onClick={(e) => { e.stopPropagation(); onCancel(); }}>
            <div style={{
                position: "absolute", left: pos.x, top: pos.y,
                background: "var(--bg-main, #ffffff)", borderRadius: "8px",
                width: "min(600px, 90vw)", boxShadow: "0 12px 48px rgba(0,0,0,0.15)",
                border: `1px solid ${COLORS.border}`,
                display: "flex", flexDirection: "column",
            }} onClick={(e) => e.stopPropagation()}>
                {/* 拖拽头部 */}
                <div
                    onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerCancel={handlePointerUp}
                    style={{
                        padding: "12px 20px", cursor: isDragging ? "grabbing" : "grab",
                        borderBottom: `1px solid ${COLORS.border}`, background: "var(--bg-surface, #f8f9fa)",
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        borderTopLeftRadius: "8px", borderTopRightRadius: "8px",
                    }}
                >
                    <div>
                        <div style={{ fontSize: "14px", fontWeight: 600, color: COLORS.text }}>{title}</div>
                        <div style={{ fontSize: "11px", color: COLORS.textMuted }}>📄 {subtitle}</div>
                    </div>
                    <span onClick={onCancel} style={{ cursor: "pointer", color: COLORS.textMuted, fontSize: "16px", padding: "4px" }}>✕</span>
                </div>
                {/* 编辑区 */}
                <div style={{ padding: "20px" }}>
                    <ActualEditor initialBlocks={initialBlocks} onSave={onSave} onCancel={onCancel} />
                </div>
            </div>
        </div>
    );
}

// ==================== WikiLink [[页面名]] ====================
export const WikiLinkSpec = createReactInlineContentSpec(
    {
        type: "wikilink" as const,
        propSchema: { page: { default: "Untitled" } },
        content: "none" as const,
    },
    {
        render: (props: any) => {
            const page = props.inlineContent.props.page;
            return (
                <span className="evo-wikilink" style={{
                    color: COLORS.accent, cursor: "pointer", fontWeight: 500,
                    borderRadius: "3px", padding: "0 2px", transition: "background 150ms",
                }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = COLORS.accentDim)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    onClick={(e) => {
                        e.preventDefault(); e.stopPropagation();
                        window.dispatchEvent(new CustomEvent("evo-navigate", { detail: `pages/${page}.md` }));
                    }}
                    title={`点击跳转: ${page}`}
                >[[{page}]]</span>
            );
        },
    }
);

// ==================== Tag #标签 ====================
export const TagSpec = createReactInlineContentSpec(
    {
        type: "tag" as const,
        propSchema: { tag: { default: "Untitled" } },
        content: "none" as const,
    },
    {
        render: (props: any) => {
            const tag = props.inlineContent.props.tag;
            return (
                <span className="evo-tag" style={{
                    color: COLORS.accent, cursor: "pointer", fontWeight: 500,
                    padding: "0 2px", borderRadius: "3px", transition: "background 150ms",
                }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = COLORS.accentDim)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    onClick={(e) => {
                        e.preventDefault(); e.stopPropagation();
                        window.dispatchEvent(new CustomEvent("evo-navigate", { detail: `pages/${tag}.md` }));
                    }}
                    title={`点击跳转标签页: ${tag}`}
                >#{tag}</span>
            );
        },
    }
);

// ==================== BlockRef ((UUID)) ====================
function BlockRefRender(props: any) {
    const uuid = props.inlineContent.props.uuid;
    const [content, setContent] = useState<string | null>(null);
    const [filePath, setFilePath] = useState("");
    const [editing, setEditing] = useState(false);
    const [editBlocks, setEditBlocks] = useState<any[] | null>(null);
    const [showToolbar, setShowToolbar] = useState(false);
    const [error, setError] = useState(false);

    useEffect(() => {
        if (!uuid) return;
        invoke<{ content: string; file_path: string }>("resolve_block_ref", { uuid })
            .then((res) => { setContent(res.content); setFilePath(res.file_path); })
            .catch(() => setError(true));
    }, [uuid]);

    const handleEditStart = async () => {
        try {
            const { markdownToBlocks, findBlockInTree } = await import("./mdParser");
            const fileContent = await invoke<string>("load_file", { fileName: filePath });
            const ast = markdownToBlocks(fileContent);
            const subtree = findBlockInTree(ast, uuid);
            if (subtree) {
                setEditBlocks([subtree]);
                setEditing(true);
            }
        } catch (e) {
            console.error("加载引用源失败:", e);
        }
    };

    const handleSave = async (newBlocks: any[]) => {
        try {
            const { markdownToBlocks, replaceBlockInTree } = await import("./mdParser");
            const fileContent = await invoke<string>("load_file", { fileName: filePath });
            const ast = markdownToBlocks(fileContent);
            if (replaceBlockInTree(ast, uuid, newBlocks)) {
                await invoke("sync_to_markdown", { fileName: filePath, blocksJson: JSON.stringify(ast) });
            }
            invoke<{ content: string; file_path: string }>("resolve_block_ref", { uuid }).then(res => setContent(res.content));
            setEditing(false);
        } catch (e) { console.error("块内容更新失败:", e); }
    };

    const handleCopy = () => { navigator.clipboard.writeText(`((${uuid}))`); setShowToolbar(false); };
    const handleDelete = () => { try { props.updateInlineContent({ type: "text", text: "" } as any); } catch { } setShowToolbar(false); };
    const handleJumpSource = () => { window.dispatchEvent(new CustomEvent("evo-navigate", { detail: filePath + '#' + uuid })); setShowToolbar(false); };

    if (error) return <span style={{ color: COLORS.danger, fontSize: "0.85em" }}>⚠ 引用未找到</span>;
    if (content === null) return <span style={{ color: COLORS.textMuted, fontSize: "0.85em" }}>⏳</span>;

    return (
        <span style={{ position: "relative", display: "inline" }}
            onMouseEnter={() => setShowToolbar(true)} onMouseLeave={() => setShowToolbar(false)}
        >
            <span className="evo-block-ref" style={{
                color: COLORS.accent, cursor: "pointer",
                background: showToolbar ? COLORS.accentDim : "transparent",
                borderRadius: "3px", padding: "1px 3px", transition: "background 150ms",
                maxWidth: "400px", overflow: "hidden", textOverflow: "ellipsis",
                whiteSpace: "nowrap", display: "inline-block", verticalAlign: "bottom",
            }} onClick={(e) => { e.stopPropagation(); handleEditStart(); }} title={content}>
                {content}
            </span>
            {showToolbar && (
                <span style={{
                    position: "absolute", bottom: "calc(100% + 4px)", left: "0",
                    display: "flex", gap: "2px", padding: "2px 4px",
                    background: "#313244", borderRadius: "6px",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.3)", zIndex: 100, fontSize: "11px", whiteSpace: "nowrap",
                }}>
                    {TOOLBAR_ITEMS([
                        { icon: "✏️", title: "编辑", onClick: () => { handleEditStart(); setShowToolbar(false); } },
                        { icon: "📋", title: "复制引用", onClick: handleCopy },
                        { icon: "📄", title: "跳转到源", onClick: handleJumpSource },
                        { icon: "🗑", title: "删除引用", onClick: handleDelete, danger: true },
                    ])}
                </span>
            )}
            {editing && editBlocks && <EditModal title="编辑块引用" subtitle={filePath.split('/').pop()?.replace('.md', '') || ''}
                initialBlocks={editBlocks}
                onSave={handleSave} onCancel={() => setEditing(false)} />}
        </span>
    );
}

export const BlockRefSpec = createReactInlineContentSpec(
    {
        type: "blockRef" as const,
        propSchema: { uuid: { default: "" } },
        content: "none" as const,
    },
    { render: BlockRefRender }
);

// ==================== BlockEmbed {{embed ((UUID))}} ====================
function BlockEmbedRender(props: any) {
    const uuid = props.inlineContent.props.uuid;
    const [content, setContent] = useState<string | null>(null);
    const [childrenContent, setChildrenContent] = useState<string[]>([]);
    const [filePath, setFilePath] = useState("");
    const [editing, setEditing] = useState(false);
    const [editBlocks, setEditBlocks] = useState<any[] | null>(null);
    const [showToolbar, setShowToolbar] = useState(false);
    const [error, setError] = useState(false);

    const loadEmbedContent = async () => {
        try {
            const res = await invoke<{ content: string; file_path: string }>("resolve_block_ref", { uuid });
            setContent(res.content);
            setFilePath(res.file_path);
            const fileContent = await invoke<string>("load_file", { fileName: res.file_path });
            const { markdownToBlocks, findBlockInTree } = await import("./mdParser");
            const ast = markdownToBlocks(fileContent);
            const node = findBlockInTree(ast, uuid);
            if (node && node.children) {
                // 递归提取所有的文本内容展示，遇到 uuid 时只取内容
                const extractText = (blocks: any[], depth: number): string[] => {
                    let textLines: string[] = [];
                    for (const b of blocks) {
                        const prefix = "  ".repeat(depth) + "- ";
                        let text = "";
                        if (b.content && Array.isArray(b.content)) {
                            text = b.content.map((c: any) => c.text || (c.type === "blockRef" ? `(引用: ${c.props.uuid.substring(0, 6)})` : "")).join("");
                        }
                        textLines.push(prefix + text);
                        if (b.children) {
                            textLines.push(...extractText(b.children, depth + 1));
                        }
                    }
                    return textLines;
                };
                setChildrenContent(extractText(node.children, 0));
            } else {
                setChildrenContent([]);
            }
        } catch (e) {
            setError(true);
        }
    };

    useEffect(() => {
        if (!uuid) return;
        loadEmbedContent();
    }, [uuid]);

    const handleEditStart = async () => {
        try {
            const { markdownToBlocks, findBlockInTree } = await import("./mdParser");
            const fileContent = await invoke<string>("load_file", { fileName: filePath });
            const ast = markdownToBlocks(fileContent);
            const subtree = findBlockInTree(ast, uuid);
            if (subtree) {
                setEditBlocks([subtree]);
                setEditing(true);
            }
        } catch (e) {
            console.error("加载引用源失败:", e);
        }
    };

    const handleSave = async (newBlocks: any[]) => {
        try {
            const { markdownToBlocks, replaceBlockInTree } = await import("./mdParser");
            const fileContent = await invoke<string>("load_file", { fileName: filePath });
            const ast = markdownToBlocks(fileContent);
            if (replaceBlockInTree(ast, uuid, newBlocks)) {
                await invoke("sync_to_markdown", { fileName: filePath, blocksJson: JSON.stringify(ast) });
            }
            loadEmbedContent(); // 重新加载整树预览
            setEditing(false);
        } catch (e) { console.error("嵌入块更新失败:", e); }
    };

    const handleCopy = () => { navigator.clipboard.writeText(`{{embed ((${uuid}))}}`); setShowToolbar(false); };
    const handleDelete = () => { try { props.updateInlineContent({ type: "text", text: "" } as any); } catch { } };
    const handleJumpSource = () => { window.dispatchEvent(new CustomEvent("evo-navigate", { detail: filePath + '#' + uuid })); setShowToolbar(false); };

    if (error) {
        return (
            <span style={{
                display: "block", padding: "8px 14px", margin: "4px 0",
                background: COLORS.dangerDim, borderLeft: `3px solid ${COLORS.danger}`,
                borderRadius: "6px", color: COLORS.danger, fontSize: "0.85em",
            }}>
                ⚠ 嵌入块未找到 ({uuid.substring(0, 8)}...)
            </span>
        );
    }

    if (content === null) {
        return (
            <span style={{
                display: "block", padding: "10px 14px", margin: "4px 0",
                background: COLORS.surface, borderLeft: `3px solid ${COLORS.border}`,
                borderRadius: "6px", color: COLORS.textMuted,
            }}>
                ⏳ 加载嵌入内容...
            </span>
        );
    }

    return (
        <span className="evo-block-embed" style={{
            display: "block", padding: "6px 14px", margin: "4px 0",
            background: "transparent",
            border: `1px solid ${COLORS.border}`,
            borderRadius: "4px", position: "relative",
            transition: "box-shadow 150ms",
            boxShadow: showToolbar ? `0 0 0 1px ${COLORS.accent}40` : "none",
        }} onMouseEnter={() => setShowToolbar(true)} onMouseLeave={() => setShowToolbar(false)}>
            {/* 浮出工具栏 */}
            {showToolbar && (
                <span style={{
                    position: "absolute", top: "-10px", right: "10px",
                    display: "flex", gap: "2px", padding: "2px 4px",
                    background: "#313244", borderRadius: "6px",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.3)", zIndex: 100, fontSize: "11px",
                }}>
                    {TOOLBAR_ITEMS([
                        { icon: "✏️", title: "编辑块嵌入", onClick: () => { handleEditStart(); setShowToolbar(false); } },
                        { icon: "📄", title: "跳转到源页面", onClick: handleJumpSource },
                        { icon: "📋", title: "复制嵌入指令", onClick: handleCopy },
                        { icon: "🗑", title: "移除嵌入", onClick: handleDelete, danger: true },
                    ])}
                </span>
            )}

            {/* 内容预览 */}
            <div style={{ color: "inherited", cursor: "text" }} onDoubleClick={handleEditStart} title="双击编辑">
                {content}
            </div>
            {childrenContent.length > 0 && (
                <div style={{
                    marginTop: "8px", paddingTop: "8px",
                    borderTop: `1px dashed ${COLORS.border}`, fontSize: "0.9em", color: COLORS.textMuted
                }}>
                    {childrenContent.map((child, i) => (
                        <div key={i} style={{ marginBottom: "2px", whiteSpace: "pre-wrap" }}>{child}</div>
                    ))}
                </div>
            )}
            <div style={{
                marginTop: "4px", fontSize: "10px", color: COLORS.textMuted,
                opacity: showToolbar ? 1 : 0.5, transition: "opacity 150ms", textAlign: "right",
            }}>
                📄 {filePath.split("/").pop()?.replace(".md", "")}
            </div>
            {/* 编辑模态 */}
            {editing && editBlocks && (
                <EditModal title="编辑嵌入块" subtitle={filePath.split('/').pop()?.replace('.md', '') || ''}
                    initialBlocks={editBlocks}
                    onSave={handleSave} onCancel={() => setEditing(false)} />
            )}
        </span>
    );
}

export const BlockEmbedSpec = createReactInlineContentSpec(
    {
        type: "blockEmbed" as const,
        propSchema: { uuid: { default: "" } },
        content: "none" as const,
    },
    { render: BlockEmbedRender }
);
