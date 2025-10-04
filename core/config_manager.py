import json
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List

VERSION_STR = "0.4.5a"

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": VERSION_STR,
    "vaults": [],
    "current_vault": None,
    "flags": {"cleaned_program_dir_v0_4_5a": False},
}

WHITELIST_MD = {
    "Note A.md",
    "Note B.md",
    "Another Note C.md",
    "source.md",
    "renamed_target.md",
}


def get_config_dir() -> Path:
    """
    Return platform-specific EvoNote config directory:
      - Windows: %APPDATA%/EvoNote
      - macOS: ~/Library/Application Support/EvoNote
      - Linux: ~/.config/EvoNote (or $XDG_CONFIG_HOME/EvoNote)
    """
    sys_name = platform.system()
    if sys_name == "Windows":
        appdata = os.getenv("APPDATA")
        if not appdata:
            appdata = str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "EvoNote"
    elif sys_name == "Darwin":
        return Path.home() / "Library" / "Application Support" / "EvoNote"
    else:
        xdg = os.getenv("XDG_CONFIG_HOME")
        if not xdg:
            xdg = str(Path.home() / ".config")
        return Path(xdg) / "EvoNote"


def get_config_path() -> Path:
    """Return full path of config.json under the config dir."""
    return get_config_dir() / "config.json"


def _canonicalize_path(p: Any) -> str:
    """Normalize a path to a POSIX-style absolute string without requiring existence."""
    try:
        path = Path(str(p)).expanduser()
    except Exception:
        path = Path(str(p))
    try:
        resolved = path.resolve(strict=False)
    except Exception:
        resolved = path.absolute()
    return resolved.as_posix()


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for it in items:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out


def _normalize_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure required keys/types exist; coerce values and de-duplicate vaults."""
    out: Dict[str, Any] = {}
    out["version"] = str(cfg.get("version") or VERSION_STR)
    # vaults
    vlist = cfg.get("vaults")
    if not isinstance(vlist, list):
        vlist = []
    norm_vaults: List[str] = []
    for v in vlist:
        if isinstance(v, (str, Path)):
            norm_vaults.append(_canonicalize_path(v))
    out["vaults"] = _dedupe_keep_order(norm_vaults)
    # current_vault
    cur = cfg.get("current_vault")
    if isinstance(cur, (str, Path)) and str(cur).strip():
        out["current_vault"] = _canonicalize_path(cur)
    else:
        out["current_vault"] = None
    # flags
    flags = cfg.get("flags") if isinstance(cfg.get("flags"), dict) else {}
    cleaned = bool(flags.get("cleaned_program_dir_v0_4_5a", False))
    out["flags"] = {"cleaned_program_dir_v0_4_5a": cleaned}
    return out


def load_config() -> Dict[str, Any]:
    """
    Load config from disk. If missing, create directory and default config.json.
    On any read/parse error, log and return an in-memory default config.
    """
    cfg_dir = get_config_dir()
    cfg_path = get_config_path()
    try:
        cfg_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.warning(f"Failed to ensure config dir {cfg_dir}: {e}")
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            norm = _normalize_config(raw)
            # If normalization changed content, save back.
            try:
                if raw != norm:
                    save_config(norm)
            except Exception as e:
                logging.warning(f"Failed to persist normalized config: {e}")
            return norm
        except Exception as e:
            logging.error(f"Failed to load config; using defaults. Error: {e}")
            return _normalize_config(DEFAULT_CONFIG.copy())
    else:
        # Create default config file
        try:
            default_cfg = _normalize_config(DEFAULT_CONFIG.copy())
            save_config(default_cfg)
            return default_cfg
        except Exception as e:
            logging.error(f"Failed to create default config; using in-memory default: {e}")
            return _normalize_config(DEFAULT_CONFIG.copy())


def save_config(cfg: Dict[str, Any]) -> None:
    """Save config dict to config.json (pretty-printed UTF-8)."""
    cfg_dir = get_config_dir()
    cfg_path = get_config_path()
    try:
        cfg_dir.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(_normalize_config(cfg), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to save config to {cfg_path}: {e}")


def add_vault(cfg: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Add a vault path (normalized) to config.vaults if absent."""
    if not isinstance(cfg, dict):
        cfg = _normalize_config(DEFAULT_CONFIG.copy())
    norm = _normalize_config(cfg)
    if path is None:
        return norm
    p = _canonicalize_path(path)
    vaults = norm.get("vaults", [])
    if p not in vaults:
        vaults.append(p)
    norm["vaults"] = _dedupe_keep_order(vaults)
    return norm


def remove_vault(cfg: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Remove a vault path from config; if it was current_vault, clear it."""
    if not isinstance(cfg, dict):
        cfg = _normalize_config(DEFAULT_CONFIG.copy())
    norm = _normalize_config(cfg)
    p = _canonicalize_path(path)
    norm["vaults"] = [v for v in norm.get("vaults", []) if v != p]
    if norm.get("current_vault") == p:
        norm["current_vault"] = None
    return norm


def set_current_vault(cfg: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Set current_vault; ensure it exists in vaults list."""
    if not isinstance(cfg, dict):
        cfg = _normalize_config(DEFAULT_CONFIG.copy())
    norm = _normalize_config(cfg)
    p = _canonicalize_path(path)
    norm["current_vault"] = p
    if p not in norm.get("vaults", []):
        norm["vaults"] = _dedupe_keep_order(norm.get("vaults", []) + [p])
    return norm


def _is_subpath(child: Path, base: Path) -> bool:
    try:
        child_res = child.resolve(strict=False)
        base_res = base.resolve(strict=False)
        child_res.relative_to(base_res)
        return True
    except Exception:
        return False


def validate_vault_path(path: str, app_dir: Path) -> Tuple[bool, str]:
    """
    Validate that the selected vault path is NOT the program directory
    and not a subdirectory of it. Other validations can be added later.
    """
    if not path or not str(path).strip():
        return False, "库路径不能为空。"
    try:
        p = Path(path).expanduser().resolve(strict=False)
    except Exception:
        p = Path(str(path))
    app_dir = app_dir.resolve(strict=False)
    if p == app_dir or _is_subpath(p, app_dir):
        return False, "库路径不能位于程序目录或其子目录。请选择程序目录之外的文件夹。"
    return True, "OK"


def ensure_vault_structure(path: Path) -> None:
    """
    Ensure that the vault root exists and contains 'pages/' and 'assets/' directories.
    This function is idempotent.
    """
    root = Path(path).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    (root / "pages").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(parents=True, exist_ok=True)


def perform_one_time_cleanup_if_needed(cfg: Dict[str, Any], app_dir: Path) -> Dict[str, Any]:
    """
    One-time cleanup in the program directory:
      - Delete .enotes/ and .EvoNotDB/ directories
      - Delete ONLY whitelisted sample .md files
    After successful attempt, set flags.cleaned_program_dir_v0_4_5a = True to avoid re-executing.
    """
    if not isinstance(cfg, dict):
        cfg = _normalize_config(DEFAULT_CONFIG.copy())
    norm = _normalize_config(cfg)
    flags = norm.get("flags", {})
    if bool(flags.get("cleaned_program_dir_v0_4_5a", False)):
        return norm
    # Attempt cleanup
    try:
        for d in (".enotes", ".EvoNotDB"):
            target = app_dir / d
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
        # Remove only whitelisted markdown files under program dir
        for name in WHITELIST_MD:
            fp = app_dir / name
            try:
                if fp.exists() and fp.is_file():
                    fp.unlink()
            except Exception as e:
                logging.warning(f"Failed to remove whitelist file {fp}: {e}")
    except Exception as e:
        logging.warning(f"Cleanup encountered issues: {e}")
    # Set flag to prevent re-execution even if partial
    norm["flags"]["cleaned_program_dir_v0_4_5a"] = True
    return norm