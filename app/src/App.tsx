import { useState, useEffect, useRef } from "react";
import "@blocknote/core/fonts/inter.css";
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine";
import "@blocknote/mantine/style.css";
import Database from "@tauri-apps/plugin-sql";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
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

function App() {
  const [initialContent, setInitialContent] = useState<any | "loading">("loading");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "synced">("idle");
  const isExternalUpdate = useRef(false);

  useEffect(() => {
    async function initDB() {
      try {
        const db = await Database.load("sqlite:evonote.db");
        await db.execute(
          "CREATE TABLE IF NOT EXISTS document_blocks (id INTEGER PRIMARY KEY, content TEXT)"
        );
        const result = await db.select<Array<{ content: string }>>("SELECT content FROM document_blocks WHERE id = 1");
        if (result.length > 0) {
          setInitialContent(JSON.parse(result[0].content));
        } else {
          setInitialContent(defaultBlocks);
        }
      } catch (e) {
        console.error("加载失败", e);
        setInitialContent(defaultBlocks);
      }
    }
    initDB();
  }, []);

  const editor = useCreateBlockNote({
    initialContent: initialContent !== "loading" ? initialContent : undefined,
  });

  // 监听外部 .md 文件变更
  useEffect(() => {
    if (!editor) return;
    const unlisten = listen<string>("md-file-changed", (event) => {
      console.log("[Frontend] External file change detected");
      try {
        const newBlocks = markdownToBlocks(event.payload);
        if (newBlocks.length > 0) {
          isExternalUpdate.current = true;
          editor.replaceBlocks(editor.document, newBlocks as any);
          setSyncStatus("synced");
          setTimeout(() => { isExternalUpdate.current = false; }, 1000);
        }
      } catch (err) {
        console.error("[Frontend] Parse error:", err);
      }
    });
    return () => { unlisten.then(fn => fn()); };
  }, [editor]);

  if (initialContent === "loading" || editor === undefined) {
    return (
      <div className="app-layout" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>正在初始化 EvoNote 微内核...</div>
      </div>
    );
  }

  let saveTimeout: ReturnType<typeof setTimeout> | null = null;

  const handleChange = () => {
    if (isExternalUpdate.current) return;
    if (saveTimeout) clearTimeout(saveTimeout);
    setSyncStatus("syncing");

    saveTimeout = setTimeout(async () => {
      try {
        const blocks = editor.document;
        const db = await Database.load("sqlite:evonote.db");
        const blocksText = JSON.stringify(blocks);
        await db.execute(
          `INSERT INTO document_blocks (id, content) VALUES (1, $1) 
           ON CONFLICT(id) DO UPDATE SET content=excluded.content`,
          [blocksText]
        );
        await invoke("sync_to_markdown", { blocksJson: blocksText });
        setSyncStatus("synced");
      } catch (err) {
        console.error("持久化失败:", err);
        setSyncStatus("idle");
      }
    }, 500);
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
          <div className="sidebar-section">
            <div className="sidebar-section-title">文件</div>
            <div className="file-item active">
              <span className="file-icon">📄</span>
              evonote_sync.md
            </div>
            <div className="file-item">
              <span className="file-icon">📁</span>
              pages/
            </div>
            <div className="file-item">
              <span className="file-icon">📁</span>
              journals/
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
            evonote_sync.md
          </div>
          <div className="topbar-actions">
            <button className="topbar-btn" title="深色/浅色">🌙</button>
            <button className="topbar-btn" title="设置">⚙</button>
          </div>
        </div>

        {/* 编辑器 */}
        <div className="editor-container">
          <BlockNoteView
            editor={editor}
            theme="dark"
            onChange={handleChange}
          />
        </div>

        {/* 底部状态栏 */}
        <div className="statusbar">
          <div className="statusbar-left">
            <span>
              {syncStatus === "syncing" ? "⟳ 同步中..." :
                syncStatus === "synced" ? "✓ 已同步" : "● 就绪"}
            </span>
          </div>
          <div className="statusbar-right">
            <span>SQLite + Markdown 双写</span>
            <span>EvoNote v0.1.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
