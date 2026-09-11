from __future__ import annotations

import base64
import ctypes
import json
import os
import uuid
from ctypes import wintypes
from pathlib import Path


APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ACQuotaScreen"
CONFIG_PATH = APP_DIR / "config.json"
THEME_PATH = APP_DIR / "theme.css"
MEDIA_DIR = APP_DIR / "media"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buf = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def protect(value: str) -> str:
    raw, raw_buf = _blob(value.encode("utf-8"))
    out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(raw), "ACQuotaScreen", None, None, None, 0, ctypes.byref(out)
    ):
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(out.pbData, out.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)
        del raw_buf


def unprotect(value: str) -> str:
    raw, raw_buf = _blob(base64.b64decode(value))
    out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(raw), None, None, None, None, 0, ctypes.byref(out)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out.pbData, out.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)
        del raw_buf


def default_config() -> dict:
    return {
        "active_source": "relay",
        "active_profile_id": None,
        "profiles": [],
        "refresh_seconds": 30,
        "screen_refresh_seconds": 3,
        "port": 8765,
        "theme": "graphite",
        "screen_layout": "overview",
        "background_opacity": 16,
        "motion_enabled": True,
        "status_light_enabled": True,
        "screen_rotation": 270,
        "weather_city": "",
        "custom_text": "",
        "background_media": "",
        "background_effect": "none",
        "shortcuts": [],
    }


def load_config() -> dict:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        cfg = default_config()
        save_config(cfg)
        return cfg
    cfg = default_config()
    cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    cfg.setdefault("profiles", [])
    if cfg.get("active_source") not in ("relay", "official"):
        cfg["active_source"] = "relay"
    return cfg


def save_config(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)


def upsert_profile(cfg: dict, name: str, base_url: str, api_key: str, profile_id: str | None = None) -> str:
    profile_id = profile_id or uuid.uuid4().hex
    base_url = base_url.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("中转站地址必须以 http:// 或 https:// 开头")
    if '\r' in api_key or '\n' in api_key:
        raise ValueError('密钥不能包含换行符')
    existing = next((p for p in cfg["profiles"] if p["id"] == profile_id), None)
    encrypted = protect(api_key.strip()) if api_key.strip() else None
    if existing is None:
        if not encrypted:
            raise ValueError("新增中转站必须填写 API Key")
        existing = {"id": profile_id}
        cfg["profiles"].append(existing)
    existing["name"] = name.strip() or base_url
    existing["base_url"] = base_url
    if encrypted:
        existing["api_key_protected"] = encrypted
    if not cfg.get("active_profile_id"):
        cfg["active_profile_id"] = profile_id
    return profile_id


def active_profile(cfg: dict) -> dict | None:
    active_id = cfg.get("active_profile_id")
    return next((p for p in cfg.get("profiles", []) if p.get("id") == active_id), None)


def public_config(cfg: dict) -> dict:
    result = dict(cfg)
    result["profiles"] = [
        {
            "id": p["id"],
            "name": p.get("name", ""),
            "base_url": p.get("base_url", ""),
            "has_api_key": bool(p.get("api_key_protected")),
        }
        for p in cfg.get("profiles", [])
    ]
    return result
