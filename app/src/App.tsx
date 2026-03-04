import { useState, useEffect, useRef, useCallback } from "react";
import "@blocknote/core/fonts/inter.css";
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine";
import "@blocknote/mantine/style.css";
import { BlockNoteSchema, defaultBlockSpecs, defaultInlineContentSpecs } from "@blocknote/core";
import { WikiLinkSpec, TagSpec, BlockRefSpec, BlockEmbedSpec } from "./customElements";
import Database from "@tauri-apps/plugin-sql";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import { markdownToBlocks } from "./mdParser";
import { ResourceTree } from "./ResourceTree";
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

// ========== BlockNote 自定义 Schema 保护区 ==========
// 这里的关键作用是：告诉 BlockNote 引擎接受我们从 mdParser 解析出的特殊 Logseq 属性 (id, collapsed等)
// 避免刚加载进引擎这些未知属性就被底层白名单过滤系统给抛弃了 (保护“样本笔记”的元数据不丢失)。
const customSchema = BlockNoteSchema.create({
  blockSpecs: {
    ...defaultBlockSpecs,
  },
  inlineContentSpecs: {
    ...defaultInlineContentSpecs,
    wikilink: WikiLinkSpec,
    tag: TagSpec,
    blockRef: BlockRefSpec,
    blockEmbed: BlockEmbedSpec,
  }
});
// 暴露给 customElements.tsx 的 EditModal 使用，避免循环依赖
(window as any).evoCustomSchema = customSchema;
// 实际上为了保护通用 Markdown 里的 key:: value，我们需要在底层反向编译器拦截。
// 但因为 BlockNote 自身的架构限制，最彻底的"原样保存"做法是拦截底层 update。
// 由于 BlockNote Schema 开发极其复杂，我们在这里改为在 `useCreateBlockNote` 层做初始化的预保存。

// 核心编辑器组件：通过 React Key 强制挂载/卸载以解决 React Hook 生命周期竞态（窜稿 Bug）
function EditorArea({
  file,
  initialContent,
  onSaveRequest,
  allFiles,
  refreshSidebar,
  theme,
  onCreateLinkedNote,
  onNavigate,
  targetBlockId
}: {
  file: string,
  initialContent: any,
  onSaveRequest: (blocksText: string) => void,
  allFiles: string[],
  refreshSidebar: () => void,
  theme: "dark" | "light",
  onCreateLinkedNote: (targetName: string) => Promise<string>,
  onNavigate: (filePath: string) => void,
  targetBlockId: string | null
}) {
  const isExternalUpdate = useRef(false);

  // 这里的 initialContent 里包含了我们在 mdParser 塞进去的含有 Logseq 属性的 raw blocks。
  const editor = useCreateBlockNote({
    initialContent: initialContent as any,
    schema: customSchema as any
  });

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

    const onEvoNavigate = (e: any) => {
      onNavigate(e.detail);
    };
    window.addEventListener('evo-navigate', onEvoNavigate);

    return () => {
      unlisten.then(fn => fn());
      window.removeEventListener('evo-navigate', onEvoNavigate);
    };
  }, [file]);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (targetBlockId) {
      setTimeout(() => {
        const el = document.querySelector(`[data-id="${targetBlockId}"]`);
        if (el && scrollRef.current) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add('highlight-flash');
          setTimeout(() => el.classList.remove('highlight-flash'), 2000);
        }
      }, 150);
    } else if (file && scrollRef.current) {
      // Restore scroll position if it exists
      const savedScroll = (window as any).scrollCache?.[file];
      if (savedScroll) {
        setTimeout(() => {
          if (scrollRef.current) scrollRef.current.scrollTop = savedScroll;
        }, 50);
      }
    }
  }, [file, targetBlockId, editor]);

  const handleScroll = () => {
    if (scrollRef.current && file) {
      if (!(window as any).scrollCache) (window as any).scrollCache = {};
      (window as any).scrollCache[file] = scrollRef.current.scrollTop;
    }
  };

  const insertWikiLink = async (targetPath: string, isNew: boolean = false) => {
    if (!wikiSuggest.blockId) return;

    let finalLink = targetPath;
    if (isNew) {
      finalLink = await onCreateLinkedNote(targetPath);
    }

    const block = editor.document.find((b: any) => b.id === wikiSuggest.blockId);
    if (block && Array.isArray(block.content)) {
      // 遍历 content，找到最后一个文本节点并执行替换
      const newContent = [...(block.content as any[])];
      for (let i = newContent.length - 1; i >= 0; i--) {
        const item = newContent[i];
        if (item.type === "text") {
          const matchIndex = item.text.lastIndexOf('[[');
          if (matchIndex !== -1) {
            const beforeText = item.text.substring(0, matchIndex);
            // 构造新的内联内容序列
            const replacements: any[] = [];
            if (beforeText) replacements.push({ type: "text", text: beforeText, styles: item.styles });

            const displayTitle = finalLink.replace('.md', '').split('/').pop() || finalLink;
            replacements.push({
              type: "wikilink",
              props: { page: displayTitle }
            });
            // 补充一个空格方便继续输入
            replacements.push({ type: "text", text: " ", styles: {} });

            newContent.splice(i, 1, ...replacements);
            break;
          }
        }
      }
      editor.updateBlock(block, { content: newContent } as any);
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

        // 检测 [[xxx]] 完整闭合 -> 自动转换为 wikilink 节点
        const closedMatch = fullText.match(/\[\[([^\]]+)\]\]/);
        if (closedMatch) {
          const pageName = closedMatch[1];
          const blockContent = [...(cursorInfo.block.content as any[])];
          for (let idx = blockContent.length - 1; idx >= 0; idx--) {
            const item = blockContent[idx];
            if (item.type === "text" && item.text.includes(`[[${pageName}]]`)) {
              const parts = item.text.split(`[[${pageName}]]`);
              const replacements: any[] = [];
              if (parts[0]) replacements.push({ type: "text", text: parts[0], styles: item.styles });
              replacements.push({ type: "wikilink", props: { page: pageName } });
              if (parts[1]) replacements.push({ type: "text", text: parts[1], styles: item.styles });
              else replacements.push({ type: "text", text: " ", styles: {} });
              blockContent.splice(idx, 1, ...replacements);
              editor.updateBlock(cursorInfo.block, { content: blockContent } as any);
              setWikiSuggest(p => p.active ? { active: false, query: "", blockId: null } : p);
              return;
            }
          }
        }

        // 检测未闭合 [[ -> 弹出建议
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

  // WikiLink (evo:// 协议) 点击拦截：阻止默认跳转，调用 navigateTo
  const handleEditorClick = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    const anchor = target.closest('a');
    if (anchor) {
      const href = anchor.getAttribute('href') || '';
      if (href.startsWith('evo://')) {
        e.preventDefault();
        e.stopPropagation();
        const filePath = href.replace('evo://', '');
        onNavigate(filePath);
      }
    }
  }, [onNavigate]);

  // 反向引用：搜索所有引用了当前页面的文件
  const [backlinks, setBacklinks] = useState<{ file_path: string; line_text: string }[]>([]);
  const [showBacklinks, setShowBacklinks] = useState(false);
  useEffect(() => {
    const pageName = file.replace('.md', '').split('/').pop() || '';
    if (!pageName) return;
    (async () => {
      try {
        const results = await invoke<any[]>('search_vault', {
          query: `[[${pageName}]]`,
          isRegex: false,
        });
        // 也搜索 #tag 形式
        const tagResults = await invoke<any[]>('search_vault', {
          query: `#${pageName}`,
          isRegex: false,
        });
        const allRefs = [...results, ...tagResults]
          .filter(r => r.file_path !== file) // 排除自身
          .filter((r, i, arr) => arr.findIndex(x => x.file_path === r.file_path && x.line_num === r.line_num) === i);
        setBacklinks(allRefs);
      } catch { setBacklinks([]); }
    })();
  }, [file]);

  return (
    <div className="editor-container" style={{ position: 'relative', height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 反向引用面板 */}
      {backlinks.length > 0 && (
        <div style={{
          borderBottom: '1px solid var(--border)', fontSize: '12px',
          background: 'var(--bg-surface, rgba(30,30,46,0.5))',
        }}>
          <div
            onClick={() => setShowBacklinks(!showBacklinks)}
            style={{
              padding: '6px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
              color: 'var(--text-muted, #6c7086)', fontWeight: 500,
            }}
          >
            <span style={{ transform: showBacklinks ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 150ms', display: 'inline-block' }}>▸</span>
            🔗 {backlinks.length} 个页面包含了此页
          </div>
          {showBacklinks && (
            <div style={{ padding: '0 14px 8px 28px' }}>
              {backlinks.map((bl, i) => (
                <div
                  key={`${bl.file_path}-${i}`}
                  onClick={() => onNavigate(bl.file_path)}
                  style={{
                    padding: '3px 0', cursor: 'pointer',
                    color: 'var(--accent, #89b4fa)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}
                  title={bl.line_text}
                >
                  📄 {bl.file_path.replace('.md', '').split('/').pop()}
                  <span style={{ color: 'var(--text-muted, #6c7086)', marginLeft: 8, fontSize: '11px' }}>
                    {bl.line_text.substring(0, 80)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

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
      <div style={{ flex: 1, overflowY: 'auto' }} onClick={handleEditorClick} ref={scrollRef} onScroll={handleScroll}>
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
  const [pageMenuOpen, setPageMenuOpen] = useState(false);

  // 前进/后退导航栈
  const [navHistory, setNavHistory] = useState<string[]>([]);
  const [navIndex, setNavIndex] = useState(-1);
  const [targetBlockId, setTargetBlockId] = useState<string | null>(null);
  const [fileRevision, setFileRevision] = useState(0); // 用于强制 EditorArea 重新挂载

  const navigateTo = useCallback((filePath: string) => {
    let resolvedPath = filePath;
    let hash: string | null = null;
    if (filePath.includes("#")) {
      [resolvedPath, hash] = filePath.split("#");
    }

    if (!files.includes(filePath)) {
      // 尝试在文件列表中模糊匹配
      const match = files.find(f => f.endsWith('/' + filePath) || f.endsWith('/' + filePath.replace(/^pages\//, '')));
      if (match) {
        resolvedPath = match;
      } else {
        // 尝试用当前文件的 Vault 前缀拼接
        const currentVault = currentFile?.split('/')[0] || '';
        const prefixed = currentVault ? `${currentVault}/${filePath}` : filePath;
        if (files.includes(prefixed)) {
          resolvedPath = prefixed;
        } else {
          // 页面不存在，自动创建
          resolvedPath = prefixed;
          invoke("sync_to_markdown", { fileName: resolvedPath, blocksJson: JSON.stringify([{ type: "paragraph", content: [] }]) })
            .then(() => fetchFiles())
            .catch(console.error);
        }
      }
    }

    const finalNavPath = hash ? `${resolvedPath}#${hash}` : resolvedPath;
    setNavHistory(prev => {
      const newHistory = prev.slice(0, navIndex + 1);
      newHistory.push(finalNavPath);
      return newHistory;
    });
    setNavIndex(prev => prev + 1);
    setCurrentFile(resolvedPath);
    setTargetBlockId(hash);
  }, [navIndex, files, currentFile]);

  const applyNavHistory = (index: number, history: string[]) => {
    const pathWithHash = history[index];
    let resolvedPath = pathWithHash;
    let hash = null;
    if (pathWithHash.includes("#")) {
      [resolvedPath, hash] = pathWithHash.split("#");
    }
    setCurrentFile(resolvedPath);
    setTargetBlockId(hash);
  };

  const goBack = useCallback(() => {
    if (navIndex > 0) {
      setNavIndex(navIndex - 1);
      applyNavHistory(navIndex - 1, navHistory);
    }
  }, [navIndex, navHistory]);

  const goForward = useCallback(() => {
    if (navIndex < navHistory.length - 1) {
      setNavIndex(navIndex + 1);
      applyNavHistory(navIndex + 1, navHistory);
    }
  }, [navIndex, navHistory]);

  const canGoBack = navIndex > 0;
  const canGoForward = navIndex < navHistory.length - 1;

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "synced">("idle");
  const [theme, setTheme] = useState<"dark" | "light">("light");

  const [showSettings, setShowSettings] = useState(false);
  const [vaultPath, setVaultPath] = useState<string>("");

  // 监听主题切换，更新全局 DOM
  useEffect(() => {
    if (theme === "light") {
      document.body.classList.add("light-theme");
    } else {
      document.body.classList.remove("light-theme");
    }
  }, [theme]);

  // 初始化数据库并建表
  useEffect(() => {
    async function initDB() {
      try {
        const database = await Database.load("sqlite:evonote.db");
        await database.execute(
          "CREATE TABLE IF NOT EXISTS files_cache (file_path TEXT PRIMARY KEY, content TEXT)"
        );
        // 建表后，为了强制应用新的 mdParser Schema 解析，清空现有的所有毒缓存
        await database.execute("DELETE FROM files_cache");
        console.log("已清表，强制应用最新自定义 Schema 解析");

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

  // 监听 Rust 后端 vault 结构变化（文件/文件夹新增、删除、重命名）→ 自动刷新文件树
  useEffect(() => {
    let debounceTimer: ReturnType<typeof setTimeout> | null = null;
    const unlisten = listen('vault-changed', () => {
      // 500ms 防抖：外部批量操作（如复制文件夹）不会疯狂刷新
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        fetchFiles();
      }, 500);
    });
    return () => {
      unlisten.then(fn => fn());
      if (debounceTimer) clearTimeout(debounceTimer);
    };
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
  }, [db, currentFile, fileRevision]); // Add fileRevision to trigger reload

  // 提供给子树的原生创建接口 (Inline Creation 回调)
  const createNoteFromTree = async (parentId: string, name: string) => {
    if (!name.trim()) return;
    const cleanName = name.trim();
    // targetFileName 将由父级目录(例如 VaultName/pages/) + 用户所输入文件名拼接
    const targetFileName = parentId + (cleanName.endsWith('.md') ? cleanName : `${cleanName}.md`);
    const defaultInitBlock = '[{"type":"paragraph","content":[]}]';
    try {
      await invoke("sync_to_markdown", { fileName: targetFileName, blocksJson: defaultInitBlock });
      if (db) {
        await db.execute("INSERT OR REPLACE INTO files_cache (file_path, content) VALUES ($1, $2)", [targetFileName, defaultInitBlock]);
      }
      await fetchFiles(targetFileName);
    } catch (e) {
      console.error("创建新笔记失败", e);
      alert("创建失败: " + e);
    }
  };

  // 供编辑器拦截 WikiLink 并创建的子级下发函数
  const createLinkedNote = async (baseName: string) => {
    let prefix = "";
    if (currentFile) {
      const parts = currentFile.split('/');
      parts.pop();
      if (parts.length > 0) {
        prefix = parts.join('/') + '/';
      }
    }
    const fn = prefix + `${baseName}.md`;
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
          setInitialContent([{ type: "paragraph", content: [] }]);
          setCurrentFile(null);
        }
        fetchFiles();
      } catch (err) {
        console.error("删除失败", err);
        alert("删除失败: " + err);
      }
    }
  };

  // 重命名笔记
  const renameNote = async (oldPath: string, newPath: string) => {
    try {
      await invoke("rename_file", { oldName: oldPath, newName: newPath });
      if (db) {
        // 迁移缓存记录
        await db.execute("UPDATE files_cache SET file_path = $1 WHERE file_path = $2", [newPath, oldPath]);
      }
      if (currentFile === oldPath) {
        setCurrentFile(newPath);
      }
      fetchFiles();
    } catch (err) {
      console.error("重命名失败", err);
      alert("重命名失败: " + err);
    }
  };

  // 新建文件夹
  const createFolderFromTree = async (folderPath: string) => {
    try {
      await invoke("create_folder", { folderPath });
      fetchFiles();
    } catch (err) {
      console.error("新建文件夹失败", err);
      alert("新建文件夹失败: " + err);
    }
  };

  // SQLite 与 Rust 的双写收口函数
  const handleContentChanged = async (blocksText: string) => {
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
            <div className="logo" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', paddingRight: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <span className="logo-icon">◈</span>
                <span>EvoNote</span>
              </div>
              <button className="topbar-btn" title="设置" onClick={() => setShowSettings(true)} style={{ padding: '4px', fontSize: '14px' }}>⚙</button>
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
            <ResourceTree
              files={files}
              currentFile={currentFile}
              onSelectFile={navigateTo}
              onDeleteFile={deleteNote}
              onCreateNote={createNoteFromTree}
              onRenameNote={renameNote}
              onCreateFolder={createFolderFromTree}
            />
          </div>
        )}
      </aside>

      {/* ===== 主内容区 ===== */}
      <div className="main-content">
        {/* 顶部栏 */}
        <div className="topbar">
          <div className="topbar-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              className="topbar-btn nav-btn"
              onClick={goBack}
              disabled={!canGoBack}
              title="后退"
              style={{ opacity: canGoBack ? 1 : 0.3, fontSize: '14px', padding: '2px 6px' }}
            >◀</button>
            <button
              className="topbar-btn nav-btn"
              onClick={goForward}
              disabled={!canGoForward}
              title="前进"
              style={{ opacity: canGoForward ? 1 : 0.3, fontSize: '14px', padding: '2px 6px' }}
            >▶</button>
            <span className="dot"></span>
            {currentFile ? currentFile.replace('.md', '').split('/').pop() : "未选择文件"}
          </div>
          <div className="topbar-actions" style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <button className="topbar-btn" title="深色/浅色切换" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} style={{ marginRight: '4px' }}>
              {theme === 'dark' ? '🌙' : '☀️'}
            </button>
            {currentFile && (
              <button className="topbar-btn" title="页面菜单" onClick={() => setPageMenuOpen(v => !v)}>⋯</button>
            )}
            {pageMenuOpen && currentFile && (
              <div
                className="page-menu-dropdown"
                style={{
                  position: 'absolute', top: '100%', right: 0, zIndex: 200,
                  background: '#313244', borderRadius: '8px',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
                  padding: '4px', minWidth: '200px', fontSize: '13px',
                }}
              >
                <div className="page-menu-item" style={{ padding: '6px 12px', cursor: 'pointer', borderRadius: '6px', color: '#cdd6f4' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(137,180,250,0.15)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  onClick={async () => {
                    try {
                      const vaultPath = await invoke<string>('get_vault_path');
                      const parts = currentFile!.split('/');
                      parts.shift();
                      const filePath = vaultPath + '\\' + parts.join('\\');
                      const { openPath } = await import('@tauri-apps/plugin-opener');
                      await openPath(filePath);
                    } catch (e) { console.error(e); }
                    setPageMenuOpen(false);
                  }}
                >📝 用默认程序打开</div>
                <div className="page-menu-item" style={{ padding: '6px 12px', cursor: 'pointer', borderRadius: '6px', color: '#cdd6f4' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(137,180,250,0.15)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  onClick={async () => {
                    try {
                      const vaultPath = await invoke<string>('get_vault_path');
                      const parts = currentFile!.split('/');
                      parts.shift();
                      const filePath = vaultPath + '\\' + parts.join('\\');
                      const { revealItemInDir } = await import('@tauri-apps/plugin-opener');
                      await revealItemInDir(filePath);
                    } catch (e) { console.error(e); }
                    setPageMenuOpen(false);
                  }}
                >📂 打开文件所在目录</div>
                <div className="page-menu-item" style={{ padding: '6px 12px', cursor: 'pointer', borderRadius: '6px', color: '#cdd6f4' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(137,180,250,0.15)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  onClick={async () => {
                    try {
                      const vaultPath = await invoke<string>('get_vault_path');
                      const parts = currentFile!.split('/');
                      parts.shift();
                      const filePath = vaultPath + '\\' + parts.join('\\');
                      await navigator.clipboard.writeText(filePath);
                    } catch (e) { console.error(e); }
                    setPageMenuOpen(false);
                  }}
                >📋 复制文件路径</div>
              </div>
            )}
          </div>
        </div>


        {/* 编辑器区域 */}
        {initialContent === "loading" ? (
          <div className="editor-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>🚀 正在唤醒数据库与文件...</div>
          </div>
        ) : (
          <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
            {currentFile && initialContent !== "loading" ? (
              <EditorArea
                key={`${currentFile}-${fileRevision}`} // Ensure fresh unmount on revision change
                file={currentFile}
                initialContent={initialContent}
                targetBlockId={targetBlockId}
                allFiles={files}
                refreshSidebar={fetchFiles}
                onSaveRequest={handleContentChanged}
                theme={theme}
                onCreateLinkedNote={createLinkedNote}
                onNavigate={(p) => navigateTo(p)}
              />
            ) : currentFile ? (
              <div className="editor-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>文件内容为空或加载失败。</div>
              </div>
            ) : (
              <div className="editor-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>请从左侧选择一个文件，或创建一个新文件。</div>
              </div>
            )}
          </div>
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
      {
        showSettings && (
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
        )
      }
    </div >
  );
}

export default App;
