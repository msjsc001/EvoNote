import { useState, useEffect, useRef } from "react";
import "@blocknote/core/fonts/inter.css";
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine";
import "@blocknote/mantine/style.css";
import Database from "@tauri-apps/plugin-sql";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import { markdownToBlocks } from "./mdParser";
import "./App.css";

const defaultBlocks = [
  {
    "id": "welcome-block",
    "type": "heading",
    "props": { "level": 2 },
    "content": [{ "type": "text", "text": "欢迎来到 EvoNote", "styles": {} }],
    "children": []
  },
  {
    "id": "intro-block",
    "type": "paragraph",
    "props": {},
    "content": [{ "type": "text", "text": "在这里随意书写，所有内容将自动同步至本地 Markdown 文件。", "styles": {} }],
    "children": []
  }
];

// 核心编辑器组件：通过 React Key 强制挂载/卸载以解决 React Hook 生命周期竞态（窜稿 Bug）
function EditorArea({
  file,
  initialContent,
  onSaveRequest,
  allFiles,
  refreshSidebar,
  theme,
  onCreateLinkedNote
}: {
  file: string,
  initialContent: any,
  onSaveRequest: (blocksText: string) => void,
  allFiles: string[],
  refreshSidebar: () => void,
  theme: "dark" | "light",
  onCreateLinkedNote: (targetName: string) => Promise<string>
}) {
  const isExternalUpdate = useRef(false);
  const editor = useCreateBlockNote({ initialContent });
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [wikiSuggest, setWikiSuggest] = useState<{ active: boolean, query: string, blockId: string | null }>({ active: false, query: "", blockId: null });
  const suggestedFiles = allFiles.filter(f => f.toLowerCase().includes(wikiSuggest.query.toLowerCase()));

  useEffect(() => {
    const unlisten = listen<{ file_name: string, content: string }>("md-file-changed", (event) => {
      if (event.payload.file_name === file) {
        try {
          const newBlocks = markdownToBlocks(event.payload.content);
          if (newBlocks.length > 0) {
            isExternalUpdate.current = true;
            editor.replaceBlocks(editor.document, newBlocks as any);
            setTimeout(() => { isExternalUpdate.current = false; }, 1000);
          }
        } catch (err) { }
      } else {
        refreshSidebar();
      }
    });
    return () => { unlisten.then(fn => fn()); };
  }, [editor, file, refreshSidebar]);

  const insertWikiLink = async (targetPath: string, isNew: boolean = false) => {
    if (!wikiSuggest.blockId) return;

    let finalLink = targetPath;
    if (isNew) {
      finalLink = await onCreateLinkedNote(targetPath);
    }

    const block = editor.document.find((b: any) => b.id === wikiSuggest.blockId);
    if (block) {
      let fullText = "";
      for (const item of (block.content as any[])) {
        if (item.type === "text") fullText += item.text;
      }
      const matchText = fullText.match(/\[\[([^\]]*)$/);
      if (matchText) {
        const displayTitle = finalLink.replace('.md', '').split('/').pop();
        const newText = fullText.substring(0, fullText.length - matchText[0].length) + `[${displayTitle}](evo://${finalLink}) `;
        editor.updateBlock(block, { content: newText } as any);
      }
    }
    setWikiSuggest({ active: false, query: "", blockId: null });
  };

  const handleChange = () => {
    if (isExternalUpdate.current) return;

    try {
      const cursorInfo = editor.getTextCursorPosition();
      if (cursorInfo && cursorInfo.block) {
        let fullText = "";
        for (const item of (cursorInfo.block.content as any[])) {
          if (item.type === "text") fullText += item.text;
        }
        const match = fullText.match(/\[\[([^\]]*)$/);
        if (match) {
          setWikiSuggest({ active: true, query: match[1], blockId: cursorInfo.block.id });
        } else {
          setWikiSuggest(p => p.active ? { active: false, query: "", blockId: null } : p);
        }
      }
    } catch (e) { }

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(() => {
      onSaveRequest(JSON.stringify(editor.document));
    }, 500);
  };

  return (
    <div className="editor-container" style={{ position: 'relative', height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
      {wikiSuggest.active && (
        <div className="wiki-suggest-popover">
          <div className="suggest-title">链接到页面</div>
          {suggestedFiles.length > 0 ? (
            suggestedFiles.map(f => (
              <div key={f} className="suggest-item" onClick={() => insertWikiLink(f)}>
                📄 {f.replace('.md', '').split('/').pop()}
              </div>
            ))
          ) : (
            <div className="suggest-item create-new" onClick={() => insertWikiLink(wikiSuggest.query, true)}>
              + 创建并链接到 "{wikiSuggest.query}"
            </div>
          )}
        </div>
      )}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <BlockNoteView editor={editor} onChange={handleChange} theme={theme} formattingToolbar={true} />
      </div>
    </div>
  );
}

function App() {
  const [db, setDb] = useState<Database | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [initialContent, setInitialContent] = useState<any | "loading">("loading");

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "synced">("idle");
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const [showSettings, setShowSettings] = useState(false);
  const [vaultPath, setVaultPath] = useState<string>("");

  // 新建笔记相关的状态
  const [showNewNote, setShowNewNote] = useState(false);
  const [newNoteName, setNewNoteName] = useState("");

  // 监听主题切换，更新全局 DOM
  useEffect(() => {
    if (theme === "light") {
      document.body.classList.add("light-theme");
    } else {
      document.body.classList.remove("light-theme");
    }
  }, [theme]);

  // 侧边栏文件动态分组
  const folderGroups: Record<string, string[]> = { "Root": [] };
  files.forEach(f => {
    const parts = f.split('/');
    if (parts.length > 1) {
      const folder = parts[0];
      if (!folderGroups[folder]) folderGroups[folder] = [];
      folderGroups[folder].push(f);
    } else {
      folderGroups["Root"].push(f);
    }
  });

  // 初始化数据库并建表
  useEffect(() => {
    async function initDB() {
      try {
        const database = await Database.load("sqlite:evonote.db");
        await database.execute(
          "CREATE TABLE IF NOT EXISTS files_cache (file_path TEXT PRIMARY KEY, content TEXT)"
        );
        setDb(database);
      } catch (e) {
        console.error("初始化数据库失败", e);
      }
    }
    initDB();
  }, []);

  // 获取文件列表及配置
  const fetchFiles = async (forceSelect?: string) => {
    try {
      const vPath = await invoke<string>("get_vault_path");
      setVaultPath(vPath);

      const fileList = await invoke<string[]>("get_files");
      setFiles(fileList);

      if (forceSelect) {
        setCurrentFile(forceSelect);
      } else if (!currentFile && fileList.length > 0) {
        setCurrentFile(fileList[0]);
      } else if (!currentFile && fileList.length === 0) {
        // Auto-create a welcome note if vault is 100% empty
        setCurrentFile("EvoNote_Welcome.md");
      }
    } catch (e) {
      console.error("获取文件列表失败", e);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  // 加载当前文件内容
  useEffect(() => {
    if (!db || !currentFile) return;

    async function loadContent() {
      setInitialContent("loading");
      try {
        const result = await db!.select<Array<{ content: string }>>(
          "SELECT content FROM files_cache WHERE file_path = $1",
          [currentFile]
        );

        if (result.length > 0) {
          const parsed = JSON.parse(result[0].content);
          // 防御性校验：BlockNote 引擎无法渲染空数组 [] ，否则整个 React 树会崩溃黑屏
          if (Array.isArray(parsed) && parsed.length > 0) {
            setInitialContent(parsed);
          } else {
            // 毒缓存自动修复
            const safeFallback = [{ type: "paragraph", content: [] }];
            if (db) {
              await db.execute("UPDATE files_cache SET content = $1 WHERE file_path = $2", [JSON.stringify(safeFallback), currentFile]);
            }
            setInitialContent(safeFallback);
          }
        } else {
          try {
            const mdContent = await invoke<string>("load_file", { fileName: currentFile });
            const blocks = markdownToBlocks(mdContent);
            // 这里修复了 Bug 2: 只有 Welcome.md 且为空时才下发 defaultBlocks，其他新建文件为彻底的空白块
            if (blocks.length > 0) {
              setInitialContent(blocks);
            } else if (currentFile?.includes("Welcome")) {
              setInitialContent(defaultBlocks);
            } else {
              setInitialContent([{ type: "paragraph", content: [] }]);
            }
          } catch (e) {
            console.log("新文件，使用空块", e);
            setInitialContent(currentFile?.includes("Welcome") ? defaultBlocks : [{ type: "paragraph", content: [] }]);
          }
        }
      } catch (e) {
        console.error("数据加载链异常:", e);
        setInitialContent([{ type: "paragraph", content: [] }]);
      }
    }

    loadContent();
  }, [db, currentFile]);

  // 新建笔记 (提交模态框)
  const submitNewNote = async () => {
    if (!newNoteName.trim()) return;
    const cleanName = newNoteName.trim();
    const targetFileName = cleanName.endsWith('.md') ? cleanName : `${cleanName}.md`;
    const defaultInitBlock = '[{"type":"paragraph","content":[]}]';
    try {
      await invoke("sync_to_markdown", { fileName: targetFileName, blocksJson: defaultInitBlock });
      if (db) {
        await db.execute("INSERT OR REPLACE INTO files_cache (file_path, content) VALUES ($1, $2)", [targetFileName, defaultInitBlock]);
      }
      setShowNewNote(false);
      setNewNoteName("");
      await fetchFiles(targetFileName);
    } catch (e) {
      console.error("创建新笔记失败", e);
      alert("创建失败: " + e);
    }
  };

  // 供编辑器拦截 WikiLink 并创建的子级下发函数
  const createLinkedNote = async (baseName: string) => {
    const fn = `${baseName}.md`;
    const defaultInitBlock = '[{"type":"paragraph","content":[]}]';
    await invoke("sync_to_markdown", { fileName: fn, blocksJson: defaultInitBlock });
    if (db) {
      await db.execute("INSERT OR REPLACE INTO files_cache (file_path, content) VALUES ($1, $2)", [fn, defaultInitBlock]);
    }
    fetchFiles();
    return fn;
  };

  // 删除笔记
  const deleteNote = async (file: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const shortName = file.replace('.md', '').split('/').pop();
    if (window.confirm(`确定要永久删除笔记 "${shortName}" 吗？此操作不可逆！`)) {
      try {
        await invoke("delete_file", { fileName: file });
        if (db) {
          await db.execute("DELETE FROM files_cache WHERE file_path = $1", [file]);
        }
        if (currentFile === file) {
          setCurrentFile(null); // 下次 fetchFiles 自动切回其他文件或Welcome
        }
        fetchFiles();
      } catch (err) {
        console.error("删除失败", err);
        alert("删除失败: " + err);
      }
    }
  };

  // SQLite 与 Rust 的双写收口函数
  const handleSaveRequest = async (blocksText: string) => {
    if (!db || !currentFile) return;
    setSyncStatus("syncing");
    try {
      await db.execute(
        `INSERT INTO files_cache (file_path, content) VALUES ($1, $2) 
         ON CONFLICT(file_path) DO UPDATE SET content=excluded.content`,
        [currentFile, blocksText]
      );
      await invoke("sync_to_markdown", { fileName: currentFile, blocksJson: blocksText });
      setSyncStatus("synced");
    } catch (err) {
      console.error("持久化失败:", err);
      setSyncStatus("idle");
    }
  };

  return (
    <div className="app-layout">
      {/* ===== 左侧边栏 ===== */}
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          {!sidebarCollapsed && (
            <div className="logo">
              <span className="logo-icon">◈</span>
              <span>EvoNote</span>
            </div>
          )}
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? "展开侧边栏" : "折叠侧边栏"}
          >
            {sidebarCollapsed ? "▸" : "◂"}
          </button>
        </div>

        {!sidebarCollapsed && (
          <div className="sidebar-section" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100% - 60px)', padding: 0 }}>

            <button className="new-note-btn-global" onClick={() => setShowNewNote(true)}>
              <span style={{ fontSize: 18, lineHeight: 1 }}>+</span> 新建笔记
            </button>

            <div className="sidebar-scroll-area">
              {Object.entries(folderGroups)
                .sort(([a], [b]) => {
                  if (a === "Root") return -1;
                  if (b === "Root") return 1;
                  return a.localeCompare(b);
                })
                .map(([folderName, filesInFolder]) => (
                  filesInFolder.length > 0 ? (
                    <div key={folderName} style={{ marginBottom: 12 }}>
                      {folderName !== "Root" && <div className="sidebar-folder-title">📁 {folderName}</div>}

                      {filesInFolder.map(file => (
                        <div
                          key={file}
                          className={`file-item ${file === currentFile ? 'active' : ''}`}
                          onClick={() => setCurrentFile(file)}
                          style={{ margin: '0 8px' }}
                        >
                          <span className="file-icon">📄</span>
                          <span className="file-name">{file.replace('.md', '').split('/').pop()}</span>
                          <button className="delete-btn" title="删除" onClick={(e) => deleteNote(file, e)}>✕</button>
                        </div>
                      ))}
                    </div>
                  ) : null
                ))}

              {files.length === 0 && (
                <div style={{ padding: '0 16px', fontSize: 12, color: 'var(--text-muted)' }}>
                  空仓库
                </div>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* ===== 主内容区 ===== */}
      <div className="main-content">
        {/* 顶部栏 */}
        <div className="topbar">
          <div className="topbar-title">
            <span className="dot"></span>
            {currentFile ? currentFile.replace('.md', '').split('/').pop() : "未选择文件"}
          </div>
          <div className="topbar-actions">
            <button className="topbar-btn" title="深色/浅色切换" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? '🌙' : '☀️'}
            </button>
            <button className="topbar-btn" title="设置" onClick={() => setShowSettings(true)}>⚙</button>
          </div>
        </div>

        {/* 编辑器区域 */}
        {initialContent === "loading" ? (
          <div className="editor-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>🚀 正在唤醒数据库与文件...</div>
          </div>
        ) : (
          <EditorArea
            key={currentFile || "empty"} // 极其关键！强制卸载并重置状态，杜绝窜文 bug！
            file={currentFile!}
            initialContent={initialContent}
            onSaveRequest={handleSaveRequest}
            allFiles={files}
            refreshSidebar={() => fetchFiles()}
            theme={theme}
            onCreateLinkedNote={createLinkedNote}
          />
        )}

        {/* 状态栏 */}
        <div className="statusbar">
          <div className="statusbar-left">
            <span>{files.length} 个笔记</span>
            <span className="separator">|</span>
            <span style={{ color: "var(--text-muted)" }}>{currentFile || "..."}</span>
          </div>
          <div className="statusbar-right">
            <span>状态: {syncStatus === 'syncing' ? '同步中...' : syncStatus === 'synced' ? '已持久化' : '空闲'}</span>
            <span className="separator">|</span>
            <span>EvoNote v0.2.0</span>
          </div>
        </div>
      </div>

      {/* ===== 核心配置面板 ===== */}
      {showSettings && (
        <div className="settings-overlay" onClick={() => setShowSettings(false)}>
          <div className="settings-modal" onClick={e => e.stopPropagation()}>
            <div className="settings-header">
              <h2>⚙️ 核心与存储设置</h2>
              <button className="settings-close" onClick={() => setShowSettings(false)}>✕</button>
            </div>

            <div className="settings-content">
              <div className="settings-group">
                <label>数据核心库位置 (The Vault)</label>
                <div className="settings-desc">EvoNote 以本地 Markdown 文件夹作为唯一的真相来源。你随时可以带着这些文本离开。</div>
                <div className="settings-path-display">
                  <div className="path-text" title={vaultPath}>{vaultPath}</div>
                  <button className="btn-primary" onClick={async () => {
                    await invoke("open_vault_dir");
                    setShowSettings(false);
                  }}>📂 系统一键打开</button>
                </div>
                <button className="settings-action-btn" onClick={async () => {
                  const selectedPath = await open({
                    directory: true,
                    multiple: false,
                    defaultPath: vaultPath,
                    title: "选择新的 EvoNote 核心库位置"
                  });
                  if (typeof selectedPath === 'string') {
                    try {
                      await invoke("set_vault_path", { newPath: selectedPath });
                      alert("✅ 核心库位置已更新！\n\n数据视窗已热重载。为了让后台的物理文件双向监听器挂载到新目录，建议在稍后完全重启 EvoNote。");
                      setCurrentFile(null); // Force reload
                      fetchFiles();
                      setShowSettings(false);
                    } catch (e) {
                      console.error("切换库失败", e);
                    }
                  }
                }}>🔄 迁移 / 更改位置</button>
              </div>

              <div className="settings-group">
                <label>高级实验性功能</label>
                <div className="settings-desc">正在等待下发 AI 并发处理指令。</div>
                <button className="settings-action-btn disabled">🤖 接入 Headless 处理引擎 (规划中)</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===== 新建笔记面板 ===== */}
      {showNewNote && (
        <div className="settings-overlay" onClick={() => setShowNewNote(false)}>
          <div className="settings-modal" onClick={e => e.stopPropagation()} style={{ width: 400 }}>
            <div className="settings-header">
              <h2>📝 创建新笔记</h2>
              <button className="settings-close" onClick={() => setShowNewNote(false)}>✕</button>
            </div>

            <div className="settings-content">
              <div className="settings-group">
                <label>笔记名称与路径</label>
                <div className="settings-desc">支持使用斜杠创建目录，例如: `工作/会议记录` 或 `我的想法`</div>
                <input
                  type="text"
                  autoFocus
                  className="settings-input"
                  placeholder="请输入笔记名称..."
                  value={newNoteName}
                  onChange={(e) => setNewNoteName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') submitNewNote();
                    if (e.key === 'Escape') setShowNewNote(false);
                  }}
                  style={{
                    padding: '10px 12px',
                    background: 'var(--bg-app)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-primary)',
                    fontSize: '14px',
                    outline: 'none',
                    marginTop: '8px',
                    width: '100%'
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
                <button className="settings-action-btn" onClick={() => setShowNewNote(false)}>取消</button>
                <button className="btn-primary" style={{ padding: '8px 16px', fontSize: '14px' }} onClick={submitNewNote}>
                  🚀 创建并落盘
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default App;
