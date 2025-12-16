
# EvoNote 🌌

> **Evolve your thoughts. Own your data.**

EvoNote is a **local-first**, **bi-directional linking** note-taking application designed for speed, privacy, and extensibility. It combines the power of a digital garden with the comfort of a modern IDE, all while keeping your data in plain text Markdown.


![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Status](https://img.shields.io/badge/Status-V0.5.0%20(Beta)-orange)

> [!WARNING]
> **Under Development**: This project is currently in active development. Features and architecture are subject to change. It is **NOT** ready for production use or critical data storage.


---
<img alt="image" src="https://github.com/user-attachments/assets/5dadc359-c9d9-493e-89ae-44fe6f3870b4" />

## ✨ Why EvoNote?

### 🔐 100% Local & Private
Your thoughts belong to you. EvoNote stores everything as simple `.md` files on your hard drive. No cloud lock-in, no subscription fees, no data mining.

### 🧩 Microkernel Architecture
EvoNote is built different. The core is tiny; **everything** is a plugin.
- **File Browser?** It's a plugin.
- **Search?** It's a plugin.
- **Editor?** It's a plugin.
This ensures the app remains lightweight, modular, and infinitely hackable.
<img  alt="image" src="https://github.com/user-attachments/assets/812142b1-5e51-4e39-bb0d-f21362d8c484" />

### 🚀 "Click-to-Run" Simplicity
Forget complex Python environment setups. EvoNote's smart bootstrapper (`main.py`) automatically detects, installs, and manages its own dependencies. Just double-click and write.

---

## 🛠️ Key Features

- **Bi-Directional Linking**: Connect ideas with `[[WikiLinks]]`. Build your personal knowledge graph.
- **Global Search**: Instant full-text search powered by `Whoosh`, accessible via a dedicated Search Panel.
- **Rich Media**: Paste images directly from your clipboard (`Ctrl+V`). They are auto-saved and linked instantly.
- **Golden Layout**: A meticulously tuned interface featuring a File Tree (Left), Distraction-Free Editor (Center), and Backlinks/Outliner (Right).
- **🆕 Theme Toggle**: Light/Dark mode switch with one click. Preferences are saved automatically.
- **Navigation Panel**: A floatable, dockable, tab-able navigation bar for organic layout management.

---

## 📖 Usage Guide

EvoNote is designed around the philosophy: **"WYSIWYG for writing, Bi-directional for thinking."** Here is your core workflow:

### 1. 📝 Creating & Writing
- **New Note**: Click the `+` button above the File Tree.
- **Markdown**: Use standard Markdown syntax.
    - **Headers**: `# H1`, `## H2`...
    - **Bold/Italic**: `**Bold**`, `*Italic*`
    - **Lists**: `- Item`, `1. Item`
    - **Quotes**: `> Blockquote`
    - **Code**: \`\`\`python ... \`\`\`
- **WYSIWYG**: Markdown syntax (like `**`) is hidden by default and reveals itself only when your cursor hovers over it, keeping your interface clean.

### 2. 🔗 Bi-Directional Linking
The soul of EvoNote.
- **Link**: Type `[[`, and a completion popup will appear. Select a note to link it.
- **Create on the Fly**: Type `[[A New Concept]]`. If the note doesn't exist, clicking the link will create it for you instantly.
- **Backlinks**: Open the Right Panel to see **what links to the current note**. This helps you rediscover forgotten connections.

### 3. 🧩 Content Blocks (Sync Magic)
A unique superpower of EvoNote.
- **What is a Block?**: Any text wrapped in `{{...}}`.
- **Sync**:
    - You write `{{Standard Footer}}` in Note A.
    - You write `{{Standard Footer}}` in Note B.
    - They are now **the same block**.
- **Global Update**:
    - Edit one instance (e.g., change to `{{New Standard Footer}}`).
    - EvoNote asks if you want to **Global Update**.
    - Say "Yes", and EVERY instance in your vault updates instantly.
    - Perfect for footers, disclaimers, math formulas, or code snippets.

### 4. 🔍 Global Search
- Click **Search** in the Navigation Panel.
- Enter keywords (fuzzy match supported).
- Click results to jump to the exact location with **highlighted keywords**.

### 5. 🧩 Plugins
- Click the `🧩 Plugins` icon in the status bar to open the Plugin Manager.
- View loaded plugins. Thanks to the microkernel architecture, almost everything (including the editor) is a plugin.

### 6. 🎨 Customization
- **Theme**: Click `☀️/🌙` in the status bar to toggle Light/Dark mode.
- **Layout**:
    - **Drag**: All panels (File Tree, Outline, Search) are draggable.
    - **Dock**: Pin them Left, Right, Bottom, or float them as separate windows.
    - **Persist**: Your layout preference is saved automatically.

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

### V0.5.0 - The "Experience Evolution" Update (2025-12-16)
*Focus: Improving user experience, enhancing editor intelligence, and refining the theme system.*

-   **🎨 Theme Toggle**:
    -   New status bar button for one-click Light/Dark mode switching.
    -   Fixed button text visibility issues in dark mode.
    -   Theme preference is saved and restored on next launch.
-   **📂 Session Restore**:
    -   Shift+Click opened note windows now remember their docked positions.
    -   All open note windows are saved on exit and restored on next launch.
-   **🔄 Global Update Auto-Refresh**:
    -   After modifying content blocks and clicking "Global Update", open editors refresh automatically.
-   **✨ Granular Syntax Highlighting**:
    -   Markdown syntax is only revealed when cursor is directly on the element.
-   **🌐 Plugin Manager i18n**:
    -   Plugin list now shows bilingual (Chinese/English) names and descriptions.
-   **🐛 Stability Fixes**:
    -   Fixed Safe Mode infinite loop causing black screen.
    -   Fixed crash when re-docking floating windows.

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
