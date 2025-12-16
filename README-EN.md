
# EvoNote 🌌

> **Evolve your thoughts. Own your data.**

EvoNote is a **local-first**, **bi-directional linking** note-taking application designed for speed, privacy, and extensibility. It combines the power of a digital garden with the comfort of a modern IDE, all while keeping your data in plain text Markdown.


![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Status](https://img.shields.io/badge/Status-V0.4.8%20(Beta)-orange)

> [!WARNING]
> **Under Development**: This project is currently in active development. Features and architecture are subject to change. It is **NOT** ready for production use or critical data storage.


---

## ✨ Why EvoNote?

### 🔐 100% Local & Private
Your thoughts belong to you. EvoNote stores everything as simple `.md` files on your hard drive. No cloud lock-in, no subscription fees, no data mining.

### 🧩 Microkernel Architecture
EvoNote is built different. The core is tiny; **everything** is a plugin.
- **File Browser?** It's a plugin.
- **Search?** It's a plugin.
- **Editor?** It's a plugin.
This ensures the app remains lightweight, modular, and infinitely hackable.

### 🚀 "Click-to-Run" Simplicity
Forget complex Python environment setups. EvoNote's smart bootstrapper (`main.py`) automatically detects, installs, and manages its own dependencies. Just double-click and write.

---

## 🛠️ Key Features

- **Bi-Directional Linking**: Connect ideas with `[[WikiLinks]]`. Build your personal knowledge graph.
- **Global Search**: Instant full-text search powered by `Whoosh`, accessible via a dedicated Search Panel.
- **Rich Media**: Paste images directly from your clipboard (`Ctrl+V`). They are auto-saved and linked instantly.
- **Golden Layout**: A meticulously tuned interface featuring a File Tree (Left), Distraction-Free Editor (Center), and Backlinks/Outliner (Right).
- **Dark Mode**: A professional, eye-strain-free dark theme with native system fonts.
- **Navigation Panel**: A floatable, dockable, tab-able navigation bar for organic layout management.

---

## 📥 Getting Started

### Prerequisites
- Windows 10/11
- Python 3.10+ installed

### Installation
1.  **Clone the repo** (or download usage):
    ```bash
    git clone https://github.com/your-repo/EvoNote.git
    cd EvoNote
    ```
2.  **Run it**:
    ```bash
    python main.py
    ```
    *On the first run, EvoNote will automatically set up its virtual environment and install components (`PySide6`, `markdown-it-py`, `watchdog`, etc.). This may take a minute.*

---

## 📅 Changelog

### V0.4.8 - The "Interaction & Polish" Update (2025-12-16)
*Focus: Fixing UI roughness and establishing a professional baseline.*

-   **🆕 Navigation Panel**: The top toolbar is now a fully dockable **Panel**. Drag it, float it, or tab it with other windows. No more rigid bars.
-   **✨ Visuals**: Replaced text buttons with sleek **Icons** (⬅️ ➡️) for a cleaner look.
-   **🚑 Layout Rescue**:
    -   **File Browser Fixed**: Restored the missing file tree functionality.
    -   **Plugin Manager Tamed**: Moved the "God View" plugin manager to a background dialog (accessible via Status Bar 🧩), decluttering the main UI.
    -   **Golden Layout Enforced**: App launches with a balanced Left-Center-Right layout by default.
-   **🐛 Stability**:
    -   **Safe Mode**: Automatically detects crash loops and launches in Safe Mode to let you disable bad plugins.
    -   **Error Isolation**: Plugin errors are caught and shown in the Status Bar (Red Alert) instead of crashing the app.

### V0.4.7 - The "Foundation" Update
-   **Bootstrapper**: New `main.py` for auto-dependency management.
-   **Image Paste**: Seamless generic image pasting support.
-   **Dark Theme**: Modern QSS-based dark theme.

---

## 🔮 Roadmap

-   [ ] **Live Preview**: Render Markdown syntax (like `**bold**`, `[[links]]`) instantly (WYSIWYG feel).
-   [ ] **Graph View**: Visualizing your note connections.
-   [ ] **Command Palette**: A Sublime/VSCode style `Ctrl+P` commander.

---

**Happy Writing!** 🖊️
