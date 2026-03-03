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

function App() {
  const [db, setDb] = useState<Database | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [initialContent, setInitialContent] = useState<any | "loading">("loading");

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "synced">("idle");
  const isExternalUpdate = useRef(false);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 设置面板相关的状态
  const [showSettings, setShowSettings] = useState(false);
  const [vaultPath, setVaultPath] = useState<string>("");

  // WikiLink 自动补全状态
  const [wikiSuggest, setWikiSuggest] = useState<{ active: boolean, query: string, blockId: string | null }>({ active: false, query: "", blockId: null });
  // 过滤后的建议列表
  const suggestedFiles = files.filter(f => f.toLowerCase().includes(wikiSuggest.query.toLowerCase()));

  // 侧边栏文件分组
  const pagesFiles = files.filter(f => f.startsWith('pages/'));
  const journalsFiles = files.filter(f => f.startsWith('journals/'));
  const rootFiles = files.filter(f => !f.startsWith('pages/') && !f.startsWith('journals/'));

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
  const fetchFiles = async () => {
    try {
      const vPath = await invoke<string>("get_vault_path");
      setVaultPath(vPath);

      const fileList = await invoke<string[]>("get_files");
      setFiles(fileList);
      if (!currentFile) {
        if (fileList.length > 0) {
          setCurrentFile(fileList[0]);
        } else {
          setCurrentFile("pages/EvoNote_Welcome.md");
        }
      }
    } catch (e) {
      console.error("获取文件列表失败", e);
    }
  };

  // 新建笔记 (UI触发)
  const createNewNote = async (folder: string) => {
    const name = window.prompt(`请输入新 ${folder} 笔记名字:`);
    if (name) {
      const targetFileName = `${folder}/${name}.md`;
      try {
        await invoke("sync_to_markdown", { fileName: targetFileName, blocksJson: "[]" });
        setCurrentFile(targetFileName);
        fetchFiles();
      } catch (e) {
        console.error("创建新笔记失败", e);
        alert("创建失败: " + e);
      }
    }
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
          setCurrentFile(null); // 下次 fetchFiles 自动切回 Welcome
        }
        fetchFiles();
      } catch (err) {
        console.error("删除失败", err);
        alert("删除失败: " + err);
      }
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
          setInitialContent(JSON.parse(result[0].content));
        } else {
          try {
            const mdContent = await invoke<string>("load_file", { fileName: currentFile });
            const blocks = markdownToBlocks(mdContent);
            setInitialContent(blocks.length > 0 ? blocks : defaultBlocks);
          } catch (e) {
            console.log("新文件或读取物理文件失败，使用默认欢迎块", e);
            setInitialContent(defaultBlocks);
          }
        }
      } catch (e) {
        console.error("数据加载链异常:", e);
        setInitialContent(defaultBlocks);
      }
    }

    loadContent();
  }, [db, currentFile]);

  // key 用于在切换文件时强制重建编辑器实例
  const editor = useCreateBlockNote({
    initialContent: initialContent !== "loading" ? initialContent : undefined,
  }, [currentFile]);

  // 监听外部 .md 文件变更
  useEffect(() => {
    if (!editor || !currentFile) return;

    const unlisten = listen<{ file_name: string, content: string }>("md-file-changed", (event) => {
      // 检查变动的是否为当前激活文件
      if (event.payload.file_name === currentFile) {
        console.log(`[Frontend] External file change detected on ${currentFile}`);
        try {
          const newBlocks = markdownToBlocks(event.payload.content);
          if (newBlocks.length > 0) {
            isExternalUpdate.current = true;
            editor.replaceBlocks(editor.document, newBlocks as any);
            setSyncStatus("synced");
            setTimeout(() => { isExternalUpdate.current = false; }, 1000);
          }
        } catch (err) {
          console.error("[Frontend] Parse error:", err);
        }
      } else {
        // 其他文件变化刷新侧边栏
        fetchFiles();
      }
    });

    return () => { unlisten.then(fn => fn()); };
  }, [editor, currentFile]);

  const handleChange = () => {
    if (isExternalUpdate.current || !db || !currentFile) return;

    // --- WikiLink 触发逻辑 ---
    try {
      const cursorInfo = editor.getTextCursorPosition();
      if (cursorInfo && cursorInfo.block) {
        // 简单提取该块内的所有纯文本
        let fullText = "";
        for (const item of (cursorInfo.block.content as any[])) {
          if (item.type === "text") fullText += item.text;
        }

        // 匹配倒数第一个 [[ 及其后的文本
        const match = fullText.match(/\[\[([^\]]*)$/);
        if (match) {
          setWikiSuggest({ active: true, query: match[1], blockId: cursorInfo.block.id });
        } else {
          setWikiSuggest(prev => prev.active ? { active: false, query: "", blockId: null } : prev);
        }
      }
    } catch (e) {
      // 忽略 getTextCursorPosition 未就绪时的错误
    }

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    setSyncStatus("syncing");

    saveTimeoutRef.current = setTimeout(async () => {
      try {
        const blocks = editor.document;
        const blocksText = JSON.stringify(blocks);
        // SQLite 写入缓存 (区分路径)
        await db.execute(
          `INSERT INTO files_cache (file_path, content) VALUES ($1, $2) 
           ON CONFLICT(file_path) DO UPDATE SET content=excluded.content`,
          [currentFile, blocksText]
        );
        // Rust 反向编译写盘
        await invoke("sync_to_markdown", { fileName: currentFile, blocksJson: blocksText });
        setSyncStatus("synced");
      } catch (err) {
        console.error("持久化失败:", err);
        setSyncStatus("idle");
      }
    }, 500);
  };

  // 插入自动补全的内部函数
  const insertWikiLink = async (fileName: string) => {
    if (!wikiSuggest.blockId) return;

    // 当用户选择创建新笔记时，默认归类到 pages/ 目录
    let targetFileName = fileName.endsWith('.md') ? fileName : `${fileName}.md`;
    if (!targetFileName.includes('/')) {
      targetFileName = `pages/${targetFileName}`;
    }

    // 1. 获取当前块内容
    const block = await editor.getBlock(wikiSuggest.blockId);
    if (!block) return;

    // 2. 在纯文本里替换掉最后那个 `[[query` 为 `[[目标文件]] `
    const displayTitle = targetFileName.replace('.md', '').replace('pages/', '').replace('journals/', '');
    const newContent = (block.content as any[]).map(item => {
      if (item.type === "text") {
        return {
          ...item,
          text: item.text.replace(/\[\[([^\]]*)$/, `[[${displayTitle}]] `)
        };
      }
      return item;
    });

    // 3. 替换内容
    editor.updateBlock(block.id, { content: newContent });
    setWikiSuggest({ active: false, query: "", blockId: null });

    // 4. 如果是新文件，则通知后台创建一个空的
    if (!files.includes(targetFileName)) {
      try {
        await invoke("sync_to_markdown", { fileName: targetFileName, blocksJson: "[]" });
        fetchFiles();
      } catch (e) {
        console.error("自动创建新笔记失败", e);
      }
    }
  };

  if (initialContent === "loading" || editor === undefined) {
    return (
      <div className="app-layout" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>🚀 正在连接多文件工作区数据库...</div>
      </div>
    );
  }

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

            {/* Pages 分组 */}
            <div className="sidebar-section-title">Pages</div>
            {pagesFiles.map(file => (
              <div
                key={file}
                className={`file-item ${file === currentFile ? 'active' : ''}`}
                onClick={() => setCurrentFile(file)}
              >
                <span className="file-icon">📄</span>
                <span className="file-name">{file.replace('.md', '').replace('pages/', '')}</span>
                <button className="delete-btn" title="删除" onClick={(e) => deleteNote(file, e)}>✕</button>
              </div>
            ))}
            <button className="new-note-btn" onClick={() => createNewNote('pages')}>+ 新建 Page</button>

            {/* Journals 分组 */}
            <div className="sidebar-section-title" style={{ marginTop: 24 }}>Journals</div>
            {journalsFiles.map(file => (
              <div
                key={file}
                className={`file-item ${file === currentFile ? 'active' : ''}`}
                onClick={() => setCurrentFile(file)}
              >
                <span className="file-icon">📓</span>
                <span className="file-name">{file.replace('.md', '').replace('journals/', '')}</span>
                <button className="delete-btn" title="删除" onClick={(e) => deleteNote(file, e)}>✕</button>
              </div>
            ))}
            <button className="new-note-btn" onClick={() => createNewNote('journals')}>+ 新建 Journal</button>

            {/* Root 或其它层级 */}
            {rootFiles.length > 0 && (
              <>
                <div className="sidebar-section-title" style={{ marginTop: 24 }}>Root</div>
                {rootFiles.map(file => (
                  <div
                    key={file}
                    className={`file-item ${file === currentFile ? 'active' : ''}`}
                    onClick={() => setCurrentFile(file)}
                  >
                    <span className="file-icon">📝</span>
                    <span className="file-name">{file.replace('.md', '')}</span>
                    <button className="delete-btn" title="删除" onClick={(e) => deleteNote(file, e)}>✕</button>
                  </div>
                ))}
              </>
            )}

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
            <button className="topbar-btn" title="深色/浅色">🌙</button>
            <button className="topbar-btn" title="设置" onClick={() => setShowSettings(true)}>⚙</button>
          </div>
        </div>

        {/* 编辑器与浮动面板容器 */}
        <div className="editor-container" style={{ position: 'relative' }}>

          {wikiSuggest.active && (
            <div className="wiki-suggest-popover">
              <div className="suggest-title">链接到页面</div>
              {suggestedFiles.length > 0 ? (
                suggestedFiles.map(f => (
                  <div key={f} className="suggest-item" onClick={() => insertWikiLink(f)}>
                    📄 {f.replace('.md', '')}
                  </div>
                ))
              ) : (
                <div className="suggest-item create-new" onClick={() => insertWikiLink(wikiSuggest.query)}>
                  ✨ 创建新笔记: <strong>{wikiSuggest.query}</strong>
                </div>
              )}
            </div>
          )}

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
            <span style={{ marginLeft: 16 }}>
              {files.length} 篇笔记
            </span>
          </div>
          <div className="statusbar-right">
            <span>SQLite + Markdown 双写</span>
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

    </div>
  );
}

export default App;
