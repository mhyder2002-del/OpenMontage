"""Persist per-category agent results and a shared event stream."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

_DEFAULT_STORE = Path(__file__).resolve().parent.parent / "data" / "agents.json"


def store_path() -> Path:
    raw = (os.environ.get("HERMES_AGENTS_STORE") or "").strip()
    return Path(raw) if raw else _DEFAULT_STORE


def _empty() -> dict[str, Any]:
    return {"categories": {}, "events": [], "last_tick": None, "tick_count": 0}


def load() -> dict[str, Any]:
    path = store_path()
    if not path.is_file():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    base = _empty()
    base.update(data)
    if not isinstance(base.get("categories"), dict):
        base["categories"] = {}
    if not isinstance(base.get("events"), list):
        base["events"] = []
    return base


def save(state: dict[str, Any]) -> dict[str, Any]:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)
    return state


def record_result(category: str, result: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        state = load()
        cats = dict(state.get("categories") or {})
        event = {
            "ts": time.time(),
            "category": category,
            "type": "category_tick",
            "agent": result.get("title") or category,
            "stage": category,
            "message": result.get("summary") or "",
            "label": result.get("label") or "DRY-RUN",
            "mode": result.get("mode"),
        }
        events = list(state.get("events") or [])
        events.append(event)
        cats[category] = {**result, "updated_at": time.time()}
        state["categories"] = cats
        state["events"] = events[-400:]
        return save(state)


def record_tick_meta(payload: dict[str, Any]) -> None:
    with _LOCK:
        state = load()
        state["last_tick"] = payload
        state["tick_count"] = int(state.get("tick_count") or 0) + 1
        save(state)
