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

// 被监听的目标文件路径（由于测试阶段均在 app/src-tauri 启动，所以指定到项目根目录）
const WATCH_FILE_PATH: &str = "../../evonote_sync.md";

#[tauri::command]
fn sync_to_markdown(blocks_json: &str, last_write: tauri::State<'_, LastWriteTime>) -> Result<String, String> {
    println!("[Rust Backend] Received IPC sync_to_markdown with {} chars", blocks_json.len());

    let blocks: Vec<Value> = serde_json::from_str(blocks_json)
        .map_err(|e| {
            println!("[Rust Backend] JSON Parse Error: {}", e);
            format!("JSON 解析失败: {}", e)
        })?;
        
    let markdown_output = blocks_to_markdown(&blocks, 0);
    
    println!("[Rust Backend] Writing to path: {}", WATCH_FILE_PATH);

    // 记录写入时间戳，防止文件监听器把我们自己的写入当成"外部修改"
    {
        let mut ts = last_write.0.lock().unwrap();
        *ts = Instant::now();
    }

    fs::write(WATCH_FILE_PATH, &markdown_output)
        .map_err(|e| {
            println!("[Rust Backend] FS Write Error: {}", e);
            format!("文件写入失败: {}", e)
        })?;
        
    println!("[Rust Backend] Successfully wrote {} bytes", markdown_output.len());
    Ok(format!("Successfully synced {} bytes", markdown_output.len()))
}

// 共享的"最后一次我们自己写入的时间"，用于防止监听器的自触发循环
struct LastWriteTime(Arc<Mutex<Instant>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let last_write = Arc::new(Mutex::new(Instant::now() - Duration::from_secs(10)));

    tauri::Builder::default()
        .manage(LastWriteTime(last_write.clone()))
        .plugin(tauri_plugin_sql::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet, sync_to_markdown])
        .setup(move |app| {
            let handle = app.handle().clone();
            let last_write_clone = last_write.clone();

            // 启动后台文件监听器线程
            thread::spawn(move || {
                println!("[Rust Watcher] Starting file watcher on: {}", WATCH_FILE_PATH);

                // 确保被监听的文件存在
                let watch_path = Path::new(WATCH_FILE_PATH);
                if !watch_path.exists() {
                    let _ = fs::write(watch_path, "");
                }

                let (tx, rx) = std::sync::mpsc::channel();

                let mut watcher = notify::RecommendedWatcher::new(tx, Config::default())
                    .expect("[Rust Watcher] Failed to create watcher");

                watcher.watch(watch_path, RecursiveMode::NonRecursive)
                    .expect("[Rust Watcher] Failed to watch file");

                println!("[Rust Watcher] File watcher active and listening...");

                // 防抖：忽略 2 秒内"我们自己触发的写入"
                for res in rx {
                    match res {
                        Ok(event) => {
                            // 只关注"修改"类型的事件
                            if event.kind.is_modify() {
                                let elapsed = {
                                    let ts = last_write_clone.lock().unwrap();
                                    ts.elapsed()
                                };

                                // 如果距离我们自己最后一次写入不到 2 秒，
                                // 说明这次变更是我们自己触发的，跳过
                                if elapsed < Duration::from_secs(2) {
                                    continue;
                                }

                                println!("[Rust Watcher] External modification detected!");

                                // 读取文件最新内容并推送至前端
                                match fs::read_to_string(WATCH_FILE_PATH) {
                                    Ok(content) => {
                                        println!("[Rust Watcher] Emitting md-file-changed event ({} bytes)", content.len());
                                        let _ = handle.emit("md-file-changed", content);
                                    },
                                    Err(e) => {
                                        println!("[Rust Watcher] Failed to read file: {}", e);
                                    }
                                }
                            }
                        },
                        Err(e) => {
                            println!("[Rust Watcher] Watch error: {:?}", e);
                        }
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
