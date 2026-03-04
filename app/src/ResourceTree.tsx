import React, { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { Tree, NodeRendererProps } from 'react-arborist';
import { VscChevronRight, VscChevronDown, VscFile, VscFolder, VscFolderOpened, VscNewFile, VscNewFolder, VscRegex } from 'react-icons/vsc';
import { Menu, Item, Separator, useContextMenu } from 'react-contexify';
import 'react-contexify/dist/ReactContexify.css';
import { invoke } from '@tauri-apps/api/core';

export type TreeNodeData = {
    id: string;
    name: string;
    isDir: boolean;
    children?: TreeNodeData[];
};

// Rust 返回的搜索结果结构
type SearchMatch = {
    file_path: string;
    line_num: number;
    line_text: string;
    match_type: 'filename' | 'content';
};

interface ResourceTreeProps {
    files: string[];
    currentFile: string | null;
    onSelectFile: (filePath: string) => void;
    onDeleteFile: (filePath: string, e: React.MouseEvent) => void;
    onCreateNote: (parentId: string, name: string) => void;
    onRenameNote: (oldPath: string, newPath: string) => void;
    onCreateFolder: (folderPath: string) => void;
}

type PendingAction =
    | { type: 'new_note'; parentId: string }
    | { type: 'new_folder'; parentId: string }
    | { type: 'rename'; nodeId: string; oldName: string };

export function ResourceTree({
    files, currentFile, onSelectFile, onDeleteFile,
    onCreateNote, onRenameNote, onCreateFolder
}: ResourceTreeProps) {
    const treeRef = useRef<any>(null);
    const [searchTerm, setSearchTerm] = useState("");
    const [isRegex, setIsRegex] = useState(false);
    const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
    const [searchResults, setSearchResults] = useState<SearchMatch[] | null>(null);
    const [isSearching, setIsSearching] = useState(false);

    const { show } = useContextMenu({ id: "resource-tree-menu" });
    const [contextMenuTarget, setContextMenuTarget] = useState<TreeNodeData | null>(null);

    // 防抖搜索：输入停顿 300ms 后触发 Rust 后端搜索
    useEffect(() => {
        if (!searchTerm.trim()) {
            setSearchResults(null);
            return;
        }
        setIsSearching(true);
        const timer = setTimeout(async () => {
            try {
                const results = await invoke<SearchMatch[]>('search_vault', {
                    query: searchTerm.trim(),
                    isRegex: isRegex,
                });
                setSearchResults(results);
            } catch (e: any) {
                console.error("搜索失败:", e);
                setSearchResults([]);
            } finally {
                setIsSearching(false);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [searchTerm, isRegex]);

    // 右键菜单
    const handleItemClick = useCallback(({ id: actionId, event }: { id: string; event: any }) => {
        if (!contextMenuTarget) return;
        const pid = contextMenuTarget.isDir
            ? contextMenuTarget.id
            : contextMenuTarget.id.split('/').slice(0, -1).join('/') + '/';
        switch (actionId) {
            case "new_note": setPendingAction({ type: 'new_note', parentId: pid }); break;
            case "new_folder": setPendingAction({ type: 'new_folder', parentId: pid }); break;
            case "rename":
                if (!contextMenuTarget.isDir) {
                    setPendingAction({ type: 'rename', nodeId: contextMenuTarget.id, oldName: contextMenuTarget.name });
                }
                break;
            case "delete":
                if (!contextMenuTarget.isDir) onDeleteFile(contextMenuTarget.id, event);
                break;
        }
    }, [contextMenuTarget, onDeleteFile]);

    // 内联提交
    const handleInlineSubmit = useCallback((value: string) => {
        if (!pendingAction) return;
        const trimmed = value.trim();
        const action = pendingAction;
        setPendingAction(null);
        if (!trimmed) return;
        if (action.type === 'new_note') {
            onCreateNote(action.parentId, trimmed);
        } else if (action.type === 'new_folder') {
            onCreateFolder(action.parentId + trimmed + '/');
        } else if (action.type === 'rename') {
            const oldParts = action.nodeId.split('/');
            oldParts.pop();
            const newName = trimmed.endsWith('.md') ? trimmed : trimmed + '.md';
            const newPath = oldParts.join('/') + '/' + newName;
            if (newPath !== action.nodeId) onRenameNote(action.nodeId, newPath);
        }
    }, [pendingAction, onCreateNote, onCreateFolder, onRenameNote]);

    // 构建树
    const treeData = useMemo(() => {
        const root: TreeNodeData[] = [];
        const dirMap = new Map<string, TreeNodeData>();
        const getOrCreateDir = (pathParts: string[]): TreeNodeData[] => {
            let currentLevel = root;
            let currentPath = "";
            for (let i = 0; i < pathParts.length - 1; i++) {
                const part = pathParts[i];
                currentPath = currentPath ? `${currentPath}/${part}` : part;
                let node = dirMap.get(currentPath);
                if (!node) {
                    node = { id: currentPath + '/', name: part, isDir: true, children: [] };
                    dirMap.set(currentPath, node);
                    currentLevel.push(node);
                }
                currentLevel = node.children!;
            }
            return currentLevel;
        };

        files.forEach(entry => {
            if (entry.endsWith('/')) {
                const parts = entry.replace(/\/$/, '').split('/');
                getOrCreateDir([...parts, 'dummy']);
            } else {
                const parts = entry.split('/');
                const fileName = parts[parts.length - 1];
                const targetLevel = getOrCreateDir(parts);
                const displayName = fileName.endsWith('.md') ? fileName.slice(0, -3) : fileName;
                targetLevel.push({ id: entry, name: displayName, isDir: false });
            }
        });

        if (pendingAction && (pendingAction.type === 'new_note' || pendingAction.type === 'new_folder')) {
            const pid = pendingAction.parentId;
            let targetLevel = root;
            if (pid) {
                const parts = pid.replace(/\/$/, '').split('/');
                targetLevel = getOrCreateDir([...parts, 'dummy']);
            }
            targetLevel.push({
                id: pendingAction.type === 'new_note' ? '__PENDING_NEW_NOTE__' : '__PENDING_NEW_FOLDER__',
                name: '', isDir: pendingAction.type === 'new_folder',
            });
        }
        return root;
    }, [files, pendingAction]);

    const handleTopNewNote = useCallback(() => {
        let pid = "";
        if (currentFile) { const p = currentFile.split('/'); p.pop(); pid = p.join('/') + '/'; }
        else if (treeData.length > 0 && treeData[0].isDir) pid = treeData[0].id;
        setPendingAction({ type: 'new_note', parentId: pid });
    }, [currentFile, treeData]);

    const handleTopNewFolder = useCallback(() => {
        let pid = "";
        if (currentFile) { const p = currentFile.split('/'); p.pop(); pid = p.join('/') + '/'; }
        else if (treeData.length > 0 && treeData[0].isDir) pid = treeData[0].id;
        setPendingAction({ type: 'new_folder', parentId: pid });
    }, [currentFile, treeData]);

    // 搜索结果按文件分组
    const groupedResults = useMemo(() => {
        if (!searchResults) return null;
        const groups = new Map<string, SearchMatch[]>();
        for (const r of searchResults) {
            const arr = groups.get(r.file_path) || [];
            arr.push(r);
            groups.set(r.file_path, arr);
        }
        return groups;
    }, [searchResults]);

    // 是否处于搜索模式
    const inSearchMode = searchTerm.trim().length > 0;

    return (
        <div className="resource-tree-container" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* 搜索栏 */}
            <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input
                    type="text"
                    placeholder="🔍 搜索文件名与内容..."
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                    className="tree-search-input"
                    style={{
                        flex: 1, padding: '5px 10px', borderRadius: '4px',
                        border: `1px solid ${isRegex ? 'var(--accent, #89b4fa)' : 'var(--border)'}`,
                        background: 'var(--surface)', color: 'var(--text-main)', fontSize: '13px',
                    }}
                />
                <VscRegex
                    onClick={() => setIsRegex(!isRegex)}
                    size={16}
                    style={{
                        cursor: 'pointer', flexShrink: 0,
                        color: isRegex ? 'var(--accent, #89b4fa)' : 'var(--text-muted, #6c7086)',
                        background: isRegex ? 'var(--primary-fade, rgba(137,180,250,0.15))' : 'transparent',
                        borderRadius: '3px', padding: '2px',
                    }}
                    title={isRegex ? "正则模式 (开)" : "正则模式 (关)"}
                />
                {!inSearchMode && (
                    <>
                        <VscNewFile onClick={handleTopNewNote} style={{ cursor: 'pointer', color: 'var(--text-main)', flexShrink: 0 }} title="新建笔记" size={16} />
                        <VscNewFolder onClick={handleTopNewFolder} style={{ cursor: 'pointer', color: 'var(--text-main)', flexShrink: 0 }} title="新建文件夹" size={16} />
                    </>
                )}
            </div>

            {/* 搜索模式：显示搜索结果列表 */}
            {inSearchMode ? (
                <div style={{ flex: 1, overflow: 'auto', padding: '6px 0' }}>
                    {isSearching && (
                        <div style={{ padding: '12px 14px', color: 'var(--text-muted, #6c7086)', fontSize: '12px' }}>搜索中...</div>
                    )}
                    {!isSearching && groupedResults && (
                        <>
                            <div style={{ padding: '4px 14px', fontSize: '11px', color: 'var(--text-muted, #6c7086)', borderBottom: '1px solid var(--border)' }}>
                                {searchResults!.length} 条匹配 · {groupedResults.size} 个文件
                            </div>
                            {Array.from(groupedResults.entries()).map(([filePath, matches]) => (
                                <div key={filePath} style={{ marginBottom: '2px' }}>
                                    {/* 文件标题 */}
                                    <div
                                        onClick={() => onSelectFile(filePath)}
                                        style={{
                                            padding: '5px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
                                            fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #cdd6f4)',
                                            background: currentFile === filePath ? 'var(--primary-fade, rgba(137,180,250,0.12))' : 'transparent',
                                        }}
                                    >
                                        <VscFile size={13} style={{ opacity: 0.7, flexShrink: 0 }} />
                                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {filePath.replace('.md', '').split('/').pop()}
                                        </span>
                                        <span style={{ fontSize: '10px', color: 'var(--text-muted, #6c7086)', marginLeft: 'auto', flexShrink: 0 }}>
                                            {matches.length}
                                        </span>
                                    </div>
                                    {/* 匹配行 */}
                                    {matches.map((m, idx) => (
                                        <div
                                            key={`${m.file_path}-${m.line_num}-${idx}`}
                                            onClick={() => onSelectFile(m.file_path)}
                                            style={{
                                                padding: '3px 14px 3px 34px', cursor: 'pointer', fontSize: '12px',
                                                color: m.match_type === 'filename' ? 'var(--accent, #89b4fa)' : 'var(--text-secondary, #a6adc8)',
                                                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                                            }}
                                            title={m.line_text}
                                        >
                                            {m.match_type === 'filename' ? (
                                                <span>📎 文件名匹配</span>
                                            ) : (
                                                <span>
                                                    <span style={{ color: 'var(--text-muted, #6c7086)', marginRight: 6, fontSize: '10px' }}>L{m.line_num}</span>
                                                    {m.line_text}
                                                </span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ))}
                            {searchResults!.length === 0 && (
                                <div style={{ padding: '20px 14px', textAlign: 'center', color: 'var(--text-muted, #6c7086)', fontSize: '13px' }}>
                                    没有找到匹配结果
                                </div>
                            )}
                        </>
                    )}
                </div>
            ) : (
                /* 正常模式：显示文件树 */
                <div style={{ flex: 1, overflow: 'hidden' }}>
                    <Tree ref={treeRef} data={treeData} width="100%" height={600} indent={18} rowHeight={30} paddingBottom={20} openByDefault={true}>
                        {(props) => <NodeRenderer {...props} />}
                    </Tree>
                </div>
            )}

            {/* 右键菜单 */}
            <Menu id="resource-tree-menu" theme="light">
                <Item id="new_note" onClick={handleItemClick as any}>📄 新建笔记</Item>
                <Item id="new_folder" onClick={handleItemClick as any}>📁 新建文件夹</Item>
                <Separator />
                <Item id="rename" onClick={handleItemClick as any} disabled={contextMenuTarget?.isDir}>✏️ 重命名</Item>
                <Item id="delete" onClick={handleItemClick as any} disabled={contextMenuTarget?.isDir}>🗑️ 删除</Item>
            </Menu>
        </div>
    );

    function NodeRenderer({ node, style }: NodeRendererProps<TreeNodeData>) {
        const isSelected = node.id === currentFile;
        const isPendingNote = node.id === '__PENDING_NEW_NOTE__';
        const isPendingFolder = node.id === '__PENDING_NEW_FOLDER__';
        const isRenaming = pendingAction?.type === 'rename' && (pendingAction as any).nodeId === node.id;
        const depth = node.level;

        if (isPendingNote || isPendingFolder || isRenaming) {
            const icon = isPendingFolder
                ? <VscFolder size={16} color="#e5c07b" style={{ marginRight: 6, flexShrink: 0 }} />
                : <VscFile size={14} style={{ marginRight: 6, opacity: 0.5, flexShrink: 0 }} />;
            const defaultVal = isRenaming ? (pendingAction as any).oldName : '';
            const placeholder = isPendingFolder ? '输入文件夹名...' : '输入笔记名...';
            return (
                <div style={{ ...style, display: 'flex', alignItems: 'center', paddingLeft: `${depth * 18 + 8}px` }}>
                    <span style={{ width: 16, flexShrink: 0 }} />
                    {icon}
                    <input
                        type="text" defaultValue={defaultVal} placeholder={placeholder} autoFocus
                        onBlur={e => handleInlineSubmit(e.currentTarget.value)}
                        onKeyDown={e => {
                            if (e.key === 'Enter') { e.preventDefault(); handleInlineSubmit(e.currentTarget.value); }
                            if (e.key === 'Escape') setPendingAction(null);
                        }}
                        onClick={e => e.stopPropagation()}
                        style={{
                            flex: 1, padding: '2px 6px', border: '1px solid var(--accent, #89b4fa)',
                            borderRadius: '3px', background: 'var(--bg-surface, #242438)',
                            color: 'var(--text-primary, #cdd6f4)', fontSize: '13px', outline: 'none',
                        }}
                    />
                </div>
            );
        }

        return (
            <div
                className={`tree-node ${isSelected ? 'selected' : ''} ${node.data.isDir ? 'tree-node-dir' : 'tree-node-file'}`}
                style={{
                    ...style, display: 'flex', alignItems: 'center',
                    paddingLeft: `${depth * 18 + 8}px`, paddingRight: '8px',
                    cursor: 'pointer',
                    background: isSelected ? 'var(--primary-fade, rgba(137,180,250,0.12))' : 'transparent',
                    color: isSelected ? 'var(--primary, #89b4fa)' : node.data.isDir ? 'var(--text-primary, #cdd6f4)' : 'var(--text-secondary, #a6adc8)',
                    fontWeight: node.data.isDir ? 600 : 400, fontSize: '13px',
                    userSelect: 'none', borderRadius: '4px', margin: '0 4px', transition: 'background 100ms ease',
                }}
                onClick={() => node.data.isDir ? node.toggle() : onSelectFile(node.data.id)}
                onContextMenu={e => { e.preventDefault(); setContextMenuTarget(node.data); show({ event: e }); }}
            >
                <span style={{ width: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, opacity: node.data.isDir ? 1 : 0 }}>
                    {node.data.isDir && (node.isOpen ? <VscChevronDown size={14} /> : <VscChevronRight size={14} />)}
                </span>
                <span style={{ marginRight: 6, display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                    {node.data.isDir
                        ? (node.isOpen ? <VscFolderOpened size={16} color="#e5c07b" /> : <VscFolder size={16} color="#e5c07b" />)
                        : <VscFile size={14} style={{ opacity: 0.7 }} />}
                </span>
                <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', letterSpacing: node.data.isDir ? '0.3px' : '0' }}>
                    {node.data.name}
                </span>
            </div>
        );
    }
}
