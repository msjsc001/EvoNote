use serde_json::Value;
use std::fs;

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

// BlockNote 编辑器内部默认属性黑名单，这些属性对用户无意义，不应污染 .md 文件
const BLOCKNOTE_INTERNAL_PROPS: &[&str] = &[
    "backgroundColor", "textColor", "textAlignment",
    "level",    // heading 级别已从 type 推断
    "checked",  // checkListItem 的勾选状态已内联处理
    "name",     // 文件/图片名由 url 推断
    "language", // codeBlock 的语言标记已内联处理
];

// 判断某个属性是否应被过滤
fn should_skip_prop(key: &str, value: &str) -> bool {
    if BLOCKNOTE_INTERNAL_PROPS.contains(&key) {
        return true;
    }
    if value.is_empty() || value == "default" || value == "left" {
        return true;
    }
    false
}

// 判断某个属性的值是否为布尔型/数值型默认值
fn should_skip_prop_value(key: &str, v: &Value) -> bool {
    if BLOCKNOTE_INTERNAL_PROPS.contains(&key) {
        return true;
    }
    // 布尔值 false 或数值 0 通常是默认值
    match v {
        Value::Bool(false) => return true,
        Value::String(s) => return should_skip_prop(key, s),
        _ => {}
    }
    false
}

// 从 inline content 数组中提取富文本（保留加粗/斜体/链接等 Markdown 标记）
fn extract_rich_text(content_arr: &Vec<Value>) -> String {
    let mut result = String::new();
    for item in content_arr {
        let item_type = item.get("type").and_then(|t| t.as_str()).unwrap_or("text");

        match item_type {
            "text" => {
                if let Some(text) = item.get("text").and_then(|t| t.as_str()) {
                    let mut formatted = text.to_string();
                    if let Some(styles) = item.get("styles").and_then(|s| s.as_object()) {
                        // 按 Markdown 嵌套优先级从内到外包裹
                        if styles.contains_key("code") {
                            formatted = format!("`{}`", formatted);
                        }
                        if styles.contains_key("bold") {
                            formatted = format!("**{}**", formatted);
                        }
                        if styles.contains_key("italic") {
                            formatted = format!("*{}*", formatted);
                        }
                        if styles.contains_key("strike") {
                            formatted = format!("~~{}~~", formatted);
                        }
                        if styles.contains_key("underline") {
                            formatted = format!("<u>{}</u>", formatted);
                        }
                    }
                    result.push_str(&formatted);
                }
            },
            "link" => {
                // BlockNote 链接结构: {type: "link", href: "...", content: [{type: "text", text: "..."}]}
                let href = item.get("href").and_then(|h| h.as_str()).unwrap_or("");
                let link_text = if let Some(content) = item.get("content").and_then(|c| c.as_array()) {
                    extract_rich_text(content)
                } else {
                    href.to_string()
                };
                result.push_str(&format!("[{}]({})", link_text, href));
            },
            "wikilink" => {
                if let Some(page) = item.get("props").and_then(|p| p.get("page")).and_then(|p| p.as_str()) {
                    result.push_str(&format!("[[{}]]", page));
                }
            },
            "tag" => {
                if let Some(tag) = item.get("props").and_then(|p| p.get("tag")).and_then(|p| p.as_str()) {
                    result.push_str(&format!("#{}", tag));
                }
            },
            "blockRef" => {
                if let Some(uuid) = item.get("props").and_then(|p| p.get("uuid")).and_then(|p| p.as_str()) {
                    result.push_str(&format!("(({}))", uuid));
                }
            },
            "blockEmbed" => {
                if let Some(uuid) = item.get("props").and_then(|p| p.get("uuid")).and_then(|p| p.as_str()) {
                    result.push_str(&format!("{{{{embed (({}))}}}}", uuid));
                }
            },
            _ => {
                // 其他未知类型保持原样
                if let Some(text) = item.get("text").and_then(|t| t.as_str()) {
                    result.push_str(text);
                }
            }
        }
    }
    result
}

// 判断当前块类型是否属于列表家族（列表项之间用单换行，段落之间用双换行）
fn is_list_type(t: &str) -> bool {
    matches!(t, "bulletListItem" | "numberedListItem" | "checkListItem")
}

// ===============================
// 核心胶水层：JSON 块树 -> 精准 Markdown 大纲文本
// 设计原则：
//  1. 段落(paragraph)之间用双换行(\n\n)分隔，保证 MD 渲染器不会把它们合并
//  2. 列表项之间用单换行(\n)，保持紧凑的列表格式
//  3. 标题(heading)前后各加空行，保证视觉层级清晰
//  4. 只输出有意义的自定义属性，过滤 BlockNote 内部默认值
// ===============================
fn blocks_to_markdown(blocks: &Vec<Value>, indent_level: usize) -> String {
    let mut md_text = String::new();
    let indent = "  ".repeat(indent_level);
    let mut list_counter: usize = 0;
    let block_count = blocks.len();

    for (i, block) in blocks.iter().enumerate() {
        if let Some(block_obj) = block.as_object() {
            let block_type = block_obj.get("type")
                .and_then(|t| t.as_str())
                .unwrap_or("paragraph");

            // 提取文字内容（带富文本格式还原）
            let text_content = if let Some(content_arr) = block_obj.get("content").and_then(|c| c.as_array()) {
                extract_rich_text(content_arr)
            } else {
                String::new()
            };

            // 获取 props 对象引用
            let props = block_obj.get("props").and_then(|p| p.as_object());

            // 根据 type 精准匹配前缀
            match block_type {
                "bulletListItem" => {
                    md_text.push_str(&format!("{}- {}\n", indent, text_content));
                    list_counter = 0;
                },
                "numberedListItem" => {
                    list_counter += 1;
                    md_text.push_str(&format!("{}{}. {}\n", indent, list_counter, text_content));
                },
                "heading" => {
                    let level = props
                        .and_then(|p| p.get("level"))
                        .and_then(|l| l.as_u64())
                        .unwrap_or(1) as usize;
                    let hashes = "#".repeat(level);
                    // 标题前后始终加空行以保证视觉层级
                    if !md_text.is_empty() && !md_text.ends_with("\n\n") {
                        md_text.push('\n');
                    }
                    md_text.push_str(&format!("{}{} {}\n\n", indent, hashes, text_content));
                    list_counter = 0;
                },
                "checkListItem" => {
                    let checked = props
                        .and_then(|p| p.get("checked"))
                        .and_then(|c| c.as_bool())
                        .unwrap_or(false);
                    let mark = if checked { "x" } else { " " };
                    md_text.push_str(&format!("{}- [{}] {}\n", indent, mark, text_content));
                    list_counter = 0;
                },
                "codeBlock" => {
                    let language = props
                        .and_then(|p| p.get("language"))
                        .and_then(|l| l.as_str())
                        .unwrap_or("");
                    md_text.push_str(&format!("{}```{}\n", indent, language));
                    md_text.push_str(&format!("{}{}\n", indent, text_content));
                    md_text.push_str(&format!("{}```\n\n", indent));
                    list_counter = 0;
                },
                "image" => {
                    let url = props
                        .and_then(|p| p.get("url"))
                        .and_then(|u| u.as_str())
                        .unwrap_or("");
                    let caption = props
                        .and_then(|p| p.get("caption"))
                        .and_then(|c| c.as_str())
                        .unwrap_or("image");
                    if !url.is_empty() {
                        md_text.push_str(&format!("{}![{}]({})\n\n", indent, caption, url));
                    }
                    list_counter = 0;
                },
                "video" | "audio" | "file" => {
                    let url = props
                        .and_then(|p| p.get("url"))
                        .and_then(|u| u.as_str())
                        .unwrap_or("");
                    let name = props
                        .and_then(|p| p.get("name"))
                        .and_then(|n| n.as_str())
                        .unwrap_or(block_type);
                    if !url.is_empty() {
                        md_text.push_str(&format!("{}[{}]({})\n\n", indent, name, url));
                    }
                    list_counter = 0;
                },
                "table" => {
                    // BlockNote 的 table 结构: content 是一个二维数组
                    // 简化处理：以 | cell | cell | 的 Markdown 表格格式输出
                    if let Some(table_content) = block_obj.get("content").and_then(|c| c.as_object()) {
                        if let Some(rows) = table_content.get("rows").and_then(|r| r.as_array()) {
                            for (row_idx, row) in rows.iter().enumerate() {
                                if let Some(cells) = row.get("cells").and_then(|c| c.as_array()) {
                                    let mut cell_texts: Vec<String> = Vec::new();
                                    for cell in cells {
                                        if let Some(cell_arr) = cell.as_array() {
                                            cell_texts.push(extract_rich_text(cell_arr));
                                        } else {
                                            cell_texts.push(String::new());
                                        }
                                    }
                                    md_text.push_str(&format!("{}| {} |\n", indent, cell_texts.join(" | ")));
                                    // 在第一行后插入表格分隔线
                                    if row_idx == 0 {
                                        let sep: Vec<String> = cell_texts.iter().map(|_| "---".to_string()).collect();
                                        md_text.push_str(&format!("{}| {} |\n", indent, sep.join(" | ")));
                                    }
                                }
                            }
                            md_text.push('\n');
                        }
                    }
                    list_counter = 0;
                },
                _ => {
                    // paragraph 及其他未知类型：纯文本输出
                    if text_content.is_empty() {
                        md_text.push('\n');
                    } else {
                        md_text.push_str(&format!("{}{}\n", indent, text_content));
                    }
                    list_counter = 0;
                }
            }

            // 提取有意义的自定义属性，过滤 BlockNote 内部默认属性
            if let Some(props_obj) = props {
                let prop_indent = "  ".repeat(indent_level + 1);
                for (k, v) in props_obj {
                    if !should_skip_prop_value(k, v) {
                        // 属性以独立缩进行呈现，保证视觉可读性
                        match v {
                            Value::String(s) => {
                                md_text.push_str(&format!("{}{}:: {}\n", prop_indent, k, s));
                            },
                            Value::Bool(b) => {
                                md_text.push_str(&format!("{}{}:: {}\n", prop_indent, k, b));
                            },
                            Value::Number(n) => {
                                md_text.push_str(&format!("{}{}:: {}\n", prop_indent, k, n));
                            },
                            _ => {}
                        }
                    }
                }
            }

            // 递归处理嵌套子块
            if let Some(children) = block_obj.get("children").and_then(|c| c.as_array()) {
                if !children.is_empty() {
                    md_text.push_str(&blocks_to_markdown(children, indent_level + 1));
                }
            }

            // 关键修复：段落之间插入空行，防止 Markdown 渲染器把连续行合并为同一段
            // 列表项之间不加空行以保持紧凑的列表视觉
            if i + 1 < block_count {
                let next_type = blocks[i + 1].as_object()
                    .and_then(|b| b.get("type"))
                    .and_then(|t| t.as_str())
                    .unwrap_or("paragraph");

                let current_is_list = is_list_type(block_type);
                let next_is_list = is_list_type(next_type);

                // 仅当"当前块不是列表"且"下个块也不是列表"时才加空行分隔
                // 这保证了：段落间有空行，列表间保持紧凑，段落到列表有过渡
                if !current_is_list || !next_is_list {
                    if !md_text.ends_with("\n\n") {
                        md_text.push('\n');
                    }
                }
            }
        }
    }
    md_text
}

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use std::path::Path;
use std::thread;
use notify::{Watcher, RecursiveMode, Config};
use tauri::Emitter;

// ===============================
// 多文件系统与文件监听驱动程序
// ===============================

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Default)]
struct AppConfig {
    vault_path: Option<String>,
}

fn get_config_path() -> std::path::PathBuf {
    if let Ok(appdata) = std::env::var("APPDATA") {
        Path::new(&appdata).join("EvoNote").join("config.json")
    } else {
        Path::new(".").join(".EvoNote").join("config.json")
    }
}

fn get_vault_dir() -> std::path::PathBuf {
    let config_path = get_config_path();
    if config_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&config_path) {
            if let Ok(config) = serde_json::from_str::<AppConfig>(&content) {
                if let Some(path) = config.vault_path {
                    let p = Path::new(&path);
                    return p.to_path_buf();
                }
            }
        }
    }
    
    if let Ok(appdata) = std::env::var("APPDATA") {
        Path::new(&appdata).join("EvoNote").join("Vault")
    } else {
        Path::new(".").join(".EvoNote").join("Vault")
    }
}

fn scan_vault_tree(dir: &std::path::Path, vault_name: &str, prefix: &str, entries: &mut Vec<String>) {
    if let Ok(dir_entries) = std::fs::read_dir(dir) {
        for entry in dir_entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    if !name.starts_with('.') {
                        let dir_relative = format!("{}{}/", prefix, name);
                        // 发射目录节点自身（保证空目录也能被前端感知）
                        entries.push(format!("{}/{}", vault_name, dir_relative));
                        // 继续递归
                        scan_vault_tree(&path, vault_name, &dir_relative, entries);
                    }
                }
            } else if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("md") {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    entries.push(format!("{}/{}{}", vault_name, prefix, name));
                }
            }
        }
    }
}

#[tauri::command]
fn get_files() -> Result<Vec<String>, String> {
    let vault_path = get_vault_dir();
    let vault_name = vault_path.file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("Vault");
    
    // 初始化常规子目录（必须在扫描前创建，否则新库连空文件夹都看不到）
    let _ = fs::create_dir_all(vault_path.join("pages"));
    let _ = fs::create_dir_all(vault_path.join("journals"));
    
    let mut entries = Vec::new();
    // 递归全量深度扫描：返回所有 md 文件 + 所有目录节点
    scan_vault_tree(&vault_path, vault_name, "", &mut entries);
    
    entries.sort();
    Ok(entries)
}

#[tauri::command]
fn load_file(file_name: &str) -> Result<String, String> {
    // file_name 格式可能包含 "VaultName/..."，需要剥离第一层
    let parts: Vec<&str> = file_name.splitn(2, '/').collect();
    let relative_path = if parts.len() == 2 { parts[1] } else { file_name };
    
    let file_path = get_vault_dir().join(relative_path);
    if file_path.exists() {
        fs::read_to_string(file_path).map_err(|e| format!("读取失败: {}", e))
    } else {
        Err("文件不存在".into())
    }
}

/// 属性合并器：将原文件中的属性行（key:: value）恢复到新生成的 Markdown 中
/// 策略：提取原文件中每个内容行及其紧随的属性行，在新输出中按内容文本匹配后注入
fn merge_properties(original: &str, new_output: &str) -> String {
    let prop_pattern = regex::Regex::new(r"^\s*\S+::\s").unwrap();
    let orig_lines: Vec<&str> = original.lines().collect();
    let new_lines: Vec<&str> = new_output.lines().collect();

    // 从原文件提取 "内容行 -> 属性行列表" 的映射
    // key = 内容文本(trimmed, 去掉列表前缀)
    let mut prop_map: std::collections::HashMap<String, Vec<String>> = std::collections::HashMap::new();
    // 页面级属性（文件头部连续的属性行，不属于任何内容行）
    let mut page_props: Vec<String> = Vec::new();
    let mut in_page_header = true;

    let mut i = 0;
    while i < orig_lines.len() {
        let line = orig_lines[i];

        // 文件头部的连续属性行 = 页面级属性
        if in_page_header && prop_pattern.is_match(line) {
            page_props.push(line.to_string());
            i += 1;
            continue;
        }
        in_page_header = false;

        if line.trim().is_empty() || prop_pattern.is_match(line) {
            i += 1;
            continue;
        }

        // 当前是内容行，收集紧随的属性行
        let content_key = line.trim().trim_start_matches("- ").trim_start_matches("* ").to_string();
        let mut props: Vec<String> = Vec::new();
        let mut j = i + 1;
        while j < orig_lines.len() && prop_pattern.is_match(orig_lines[j]) {
            props.push(orig_lines[j].to_string());
            j += 1;
        }
        if !props.is_empty() {
            prop_map.insert(content_key, props);
        }
        i = j;
    }

    // 用属性集合标记已使用，避免重复注入
    let mut used_keys: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut result = String::new();

    // 先注入页面级属性
    for p in &page_props {
        result.push_str(p);
        result.push('\n');
    }

    for line in &new_lines {
        result.push_str(line);
        result.push('\n');

        if line.trim().is_empty() {
            continue;
        }

        let content_key = line.trim().trim_start_matches("- ").trim_start_matches("* ").to_string();
        if !used_keys.contains(&content_key) {
            if let Some(props) = prop_map.get(&content_key) {
                for prop_line in props {
                    result.push_str(prop_line);
                    result.push('\n');
                }
                used_keys.insert(content_key);
            }
        }
    }

    result
}

#[tauri::command]
fn sync_to_markdown(file_name: &str, blocks_json: &str, last_write: tauri::State<'_, LastWriteTime>) -> Result<String, String> {
    println!("[Rust Backend] Syncing to {}", file_name);

    let parts: Vec<&str> = file_name.splitn(2, '/').collect();
    let relative_path = if parts.len() == 2 { parts[1] } else { file_name };

    let blocks: Vec<Value> = serde_json::from_str(blocks_json)
        .map_err(|e| format!("JSON 解析失败: {}", e))?;
        
    let markdown_output = blocks_to_markdown(&blocks, 0);
    let file_path = get_vault_dir().join(relative_path);

    // 属性保护机制：读取原文件的属性行，保存时合并回去
    // BlockNote 会丢弃未注册的 props（如 id::, collapsed::），这里从原文件恢复
    let final_output = if file_path.exists() {
        if let Ok(original) = fs::read_to_string(&file_path) {
            merge_properties(&original, &markdown_output)
        } else {
            markdown_output.clone()
        }
    } else {
        markdown_output.clone()
    };

    // 记录写入时间戳，防止文件监听器触发自循环
    {
        let mut ts = last_write.0.lock().unwrap();
        *ts = Instant::now();
    }

    fs::write(file_path, &final_output)
        .map_err(|e| format!("文件写入失败: {}", e))?;
        
    Ok(format!("Successfully synced {} bytes", final_output.len()))
}

#[tauri::command]
fn get_vault_path() -> String {
    get_vault_dir().to_string_lossy().to_string()
}

#[tauri::command]
fn set_vault_path(new_path: String) -> Result<(), String> {
    let config_path = get_config_path();
    if let Some(parent) = config_path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    
    let config = AppConfig {
        vault_path: Some(new_path.clone()),
    };
    
    let content = serde_json::to_string_pretty(&config)
        .map_err(|e| format!("序列化失败: {}", e))?;
        
    fs::write(&config_path, content)
        .map_err(|e| format!("配置保存失败: {}", e))?;
    
    // 初始化子目录
    let _ = fs::create_dir_all(Path::new(&new_path).join("pages"));
    let _ = fs::create_dir_all(Path::new(&new_path).join("journals"));
        
    Ok(())
}

use tauri_plugin_opener::OpenerExt;

#[tauri::command]
fn open_vault_dir(app_handle: tauri::AppHandle) -> Result<(), String> {
    let path = get_vault_dir();
    if !path.exists() {
        let _ = fs::create_dir_all(&path);
    }
    app_handle.opener().open_path(path.to_string_lossy().to_string(), None::<&str>)
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn delete_file(file_name: &str) -> Result<(), String> {
    let parts: Vec<&str> = file_name.splitn(2, '/').collect();
    let relative_path = if parts.len() == 2 { parts[1] } else { file_name };
    
    let file_path = get_vault_dir().join(relative_path);
    if file_path.exists() {
        fs::remove_file(file_path).map_err(|e| format!("文件删除失败: {}", e))
    } else {
        Err("文件不存在".into())
    }
}

#[tauri::command]
fn rename_file(old_name: &str, new_name: &str) -> Result<String, String> {
    let old_parts: Vec<&str> = old_name.splitn(2, '/').collect();
    let old_relative = if old_parts.len() == 2 { old_parts[1] } else { old_name };

    let new_parts: Vec<&str> = new_name.splitn(2, '/').collect();
    let new_relative = if new_parts.len() == 2 { new_parts[1] } else { new_name };

    let vault = get_vault_dir();
    let old_path = vault.join(old_relative);
    let new_path = vault.join(new_relative);

    if !old_path.exists() {
        return Err("源文件不存在".into());
    }
    if new_path.exists() {
        return Err("目标文件已存在".into());
    }
    // 确保目标目录存在
    if let Some(parent) = new_path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    fs::rename(&old_path, &new_path)
        .map_err(|e| format!("重命名失败: {}", e))?;
    Ok(new_name.to_string())
}

#[tauri::command]
fn create_folder(folder_path: &str) -> Result<(), String> {
    let parts: Vec<&str> = folder_path.splitn(2, '/').collect();
    let relative_path = if parts.len() == 2 { parts[1] } else { folder_path };
    // 去掉尾部 /
    let clean = relative_path.trim_end_matches('/');
    let full_path = get_vault_dir().join(clean);
    fs::create_dir_all(&full_path)
        .map_err(|e| format!("创建文件夹失败: {}", e))
}
#[derive(serde::Serialize, Clone)]
struct SearchMatch {
    file_path: String,   // "Vault/pages/note.md" 格式
    line_num: usize,     // 0 = 文件名匹配, >0 = 内容匹配行号
    line_text: String,   // 匹配行内容预览
    match_type: String,  // "filename" | "content"
}

fn collect_md_files(dir: &std::path::Path, vault_name: &str, prefix: &str, out: &mut Vec<(String, std::path::PathBuf)>) {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    if !name.starts_with('.') {
                        let sub = format!("{}{}/", prefix, name);
                        collect_md_files(&path, vault_name, &sub, out);
                    }
                }
            } else if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("md") {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    let id = format!("{}/{}{}", vault_name, prefix, name);
                    out.push((id, path.clone()));
                }
            }
        }
    }
}

#[tauri::command]
fn search_vault(query: &str, is_regex: bool) -> Result<Vec<SearchMatch>, String> {
    if query.is_empty() {
        return Ok(vec![]);
    }

    let vault_path = get_vault_dir();
    let vault_name = vault_path.file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("Vault");

    let mut all_files: Vec<(String, std::path::PathBuf)> = Vec::new();
    collect_md_files(&vault_path, vault_name, "", &mut all_files);

    let mut results: Vec<SearchMatch> = Vec::new();
    let max_results = 200; // 防止内存爆炸

    if is_regex {
        let re = regex::Regex::new(query)
            .map_err(|e| format!("正则表达式语法错误: {}", e))?;

        for (file_id, file_path) in &all_files {
            if results.len() >= max_results { break; }

            // 文件名匹配
            let fname = file_path.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if re.is_match(fname) {
                results.push(SearchMatch {
                    file_path: file_id.clone(),
                    line_num: 0,
                    line_text: fname.to_string(),
                    match_type: "filename".into(),
                });
            }

            // 内容逐行匹配
            if let Ok(content) = fs::read_to_string(file_path) {
                for (idx, line) in content.lines().enumerate() {
                    if results.len() >= max_results { break; }
                    if re.is_match(line) {
                        results.push(SearchMatch {
                            file_path: file_id.clone(),
                            line_num: idx + 1,
                            line_text: line.chars().take(200).collect(),
                            match_type: "content".into(),
                        });
                    }
                }
            }
        }
    } else {
        let query_lower = query.to_lowercase();

        for (file_id, file_path) in &all_files {
            if results.len() >= max_results { break; }

            let fname = file_path.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if fname.to_lowercase().contains(&query_lower) {
                results.push(SearchMatch {
                    file_path: file_id.clone(),
                    line_num: 0,
                    line_text: fname.to_string(),
                    match_type: "filename".into(),
                });
            }

            if let Ok(content) = fs::read_to_string(file_path) {
                for (idx, line) in content.lines().enumerate() {
                    if results.len() >= max_results { break; }
                    if line.to_lowercase().contains(&query_lower) {
                        results.push(SearchMatch {
                            file_path: file_id.clone(),
                            line_num: idx + 1,
                            line_text: line.chars().take(200).collect(),
                            match_type: "content".into(),
                        });
                    }
                }
            }
        }
    }

    Ok(results)
}

/// 块引用解析：扫描 Vault 中所有 .md 文件，找到包含 `id:: <uuid>` 的块，返回该块的文本内容
#[tauri::command]
fn resolve_block_ref(uuid: &str) -> Result<serde_json::Value, String> {
    let vault = get_vault_dir();
    let vault_name = vault.file_name().and_then(|n| n.to_str()).unwrap_or("Vault");
    let mut all_files: Vec<(String, std::path::PathBuf)> = Vec::new();
    collect_md_files(&vault, vault_name, "", &mut all_files);

    let id_pattern = format!("id:: {}", uuid);

    for (file_id, file_path) in &all_files {
        if let Ok(content) = fs::read_to_string(file_path) {
            let lines: Vec<&str> = content.lines().collect();
            for (idx, line) in lines.iter().enumerate() {
                if line.trim() == id_pattern || line.trim().starts_with(&id_pattern) {
                    // 找到 id:: 行，往上找到对应的内容行
                    // 内容行是 id:: 行的前一行（同缩进层级的非属性行）
                    let mut content_line = String::new();
                    if idx > 0 {
                        // 向上搜索最近的非属性行
                        let mut k = idx as i64 - 1;
                        while k >= 0 {
                            let prev = lines[k as usize].trim();
                            // 跳过其他属性行
                            if prev.contains(":: ") && !prev.starts_with("- ") && !prev.starts_with("# ") {
                                k -= 1;
                                continue;
                            }
                            // 去掉列表前缀
                            content_line = if prev.starts_with("- ") {
                                prev[2..].to_string()
                            } else {
                                prev.to_string()
                            };
                            break;
                        }
                    }
                    return Ok(serde_json::json!({
                        "content": content_line,
                        "file_path": file_id,
                        "line_num": idx + 1
                    }));
                }
            }
        }
    }

    Err(format!("未找到 UUID: {}", uuid))
}

/// 块内容更新：定位源文件中 UUID 对应的块，替换其文本内容
#[tauri::command]
fn update_block_content(uuid: &str, new_content: &str) -> Result<(), String> {
    let vault = get_vault_dir();
    let vault_name = vault.file_name().and_then(|n| n.to_str()).unwrap_or("Vault");
    let mut all_files: Vec<(String, std::path::PathBuf)> = Vec::new();
    collect_md_files(&vault, vault_name, "", &mut all_files);

    let id_pattern = format!("id:: {}", uuid);

    for (_file_id, file_path) in &all_files {
        if let Ok(content) = fs::read_to_string(file_path) {
            let lines: Vec<&str> = content.lines().collect();
            for (idx, line) in lines.iter().enumerate() {
                if line.trim() == id_pattern || line.trim().starts_with(&id_pattern) {
                    if idx > 0 {
                        // 向上找到内容行
                        let mut k = idx as i64 - 1;
                        while k >= 0 {
                            let prev = lines[k as usize].trim();
                            if prev.contains(":: ") && !prev.starts_with("- ") && !prev.starts_with("# ") {
                                k -= 1;
                                continue;
                            }
                            break;
                        }
                        if k >= 0 {
                            let target_idx = k as usize;
                            let old_line = lines[target_idx];
                            // 保留原始缩进和列表前缀
                            let indent_match: String = old_line.chars().take_while(|c| c.is_whitespace()).collect();
                            let has_bullet = old_line.trim_start().starts_with("- ");
                            let new_line = if has_bullet {
                                format!("{}- {}", indent_match, new_content)
                            } else {
                                format!("{}{}", indent_match, new_content)
                            };

                            let mut new_lines: Vec<String> = lines.iter().map(|l| l.to_string()).collect();
                            new_lines[target_idx] = new_line;
                            let new_file_content = new_lines.join("\n");
                            fs::write(file_path, new_file_content)
                                .map_err(|e| format!("写入失败: {}", e))?;
                            return Ok(());
                        }
                    }
                }
            }
        }
    }

    Err(format!("未找到 UUID: {}", uuid))
}

// 共享的"最后一次写入的时间"状态
struct LastWriteTime(Arc<Mutex<Instant>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let last_write = Arc::new(Mutex::new(Instant::now() - Duration::from_secs(10)));

    tauri::Builder::default()
        .manage(LastWriteTime(last_write.clone()))
        .plugin(tauri_plugin_sql::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![greet, sync_to_markdown, get_files, load_file, get_vault_path, set_vault_path, open_vault_dir, delete_file, rename_file, create_folder, search_vault, resolve_block_ref, update_block_content])
        .setup(move |app| {
            let handle = app.handle().clone();
            let last_write_clone = last_write.clone();

            // 启动后台全目录文件监听器线程
            thread::spawn(move || {
                let watch_dir = get_vault_dir();
                if !watch_dir.exists() {
                    let _ = fs::create_dir_all(&watch_dir);
                }
                println!("[Rust Watcher] Starting directory watcher on: {:?}", watch_dir);

                let (tx, rx) = std::sync::mpsc::channel();

                let mut watcher = notify::RecommendedWatcher::new(tx, Config::default())
                    .expect("[Rust Watcher] Failed to create watcher");

                watcher.watch(&watch_dir, RecursiveMode::Recursive)
                    .expect("[Rust Watcher] Failed to watch directory");

                println!("[Rust Watcher] Directory watcher active...");

                for res in rx {
                    match res {
                        Ok(event) => {
                            let elapsed = {
                                let ts = last_write_clone.lock().unwrap();
                                ts.elapsed()
                            };
                            // 防抖：忽略自身写入后 2 秒内的事件
                            if elapsed < Duration::from_secs(2) {
                                continue;
                            }

                            let is_structure_change = event.kind.is_create()
                                || event.kind.is_remove()
                                || matches!(event.kind, notify::EventKind::Modify(notify::event::ModifyKind::Name(_)));

                            // 结构变化（新增/删除/重命名）→ 通知前端刷新文件树
                            if is_structure_change {
                                println!("[Rust Watcher] Structure change: {:?}", event.kind);
                                let _ = handle.emit("vault-changed", ());
                            }

                            // 内容变化 → 通知前端热更新文件内容
                            if event.kind.is_modify() {
                                if let Some(path) = event.paths.first() {
                                    if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("md") {
                                        if let Ok(rel_path) = path.strip_prefix(&watch_dir) {
                                            let rel_path_str = rel_path.to_string_lossy().replace("\\", "/");
                                            println!("[Rust Watcher] Content change: {}", rel_path_str);
                                            match fs::read_to_string(path) {
                                                Ok(content) => {
                                                    #[derive(serde::Serialize, Clone)]
                                                    struct FileChangePayload {
                                                        file_name: String,
                                                        content: String,
                                                    }
                                                    let payload = FileChangePayload {
                                                        file_name: rel_path_str,
                                                        content,
                                                    };
                                                    let _ = handle.emit("md-file-changed", payload);
                                                },
                                                Err(e) => println!("[Rust Watcher] Read error: {}", e),
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        Err(e) => println!("[Rust Watcher] Watch error: {:?}", e),
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
