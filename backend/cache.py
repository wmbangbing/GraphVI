"""Simple local file-based cache, persists across restarts."""

import os
import json
import time

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "_cache")
os.makedirs(_CACHE_DIR, exist_ok=True)


def _safe_path(key: str) -> str:
    """Convert cache key to a safe filename."""
    safe = ""
    for c in key:
        if c.isalnum() or c in "._-":
            safe += c
        else:
            safe += "_"
    return safe[:200] + ".json"


def get(key: str):
    """Get cached value. Returns None if missing or expired."""
    path = os.path.join(_CACHE_DIR, _safe_path(key))
    try:
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        if time.time() < entry["expire"]:
            return entry["value"]
        os.remove(path)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def set(key: str, value, ttl: int):
    """Store value with TTL in seconds."""
    path = os.path.join(_CACHE_DIR, _safe_path(key))
    entry = {"expire": time.time() + ttl, "value": value}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)


def clear():
    """Clear all cached entries."""
    for fname in os.listdir(_CACHE_DIR):
        if fname.endswith(".json"):
            try:
                os.remove(os.path.join(_CACHE_DIR, fname))
            except OSError:
                pass
