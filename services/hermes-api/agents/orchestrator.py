"""Tick all console category agents with bounded concurrency."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from .catalog import CATEGORIES, get_spec
from .runner import run_spec
from .store import load, record_tick_meta


def max_concurrency() -> int:
    raw = os.environ.get("HERMES_AGENT_CONCURRENCY") or "3"
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return 3


def snapshot() -> dict[str, Any]:
    state = load()
    categories = []
    for spec in CATEGORIES:
        row = (state.get("categories") or {}).get(spec.id) or {
            "id": spec.id,
            "title": spec.title,
            "goal": spec.goal,
            "summary": None,
            "mode": "idle",
            "label": None,
            "ok": False,
        }
        categories.append(row)
    return {
        "count": len(CATEGORIES),
        "concurrency": max_concurrency(),
        "tick_count": int(state.get("tick_count") or 0),
        "last_tick": state.get("last_tick"),
        "categories": categories,
        "events": (state.get("events") or [])[-80:],
    }


def snapshot_category(category: str) -> dict[str, Any] | None:
    spec = get_spec(category)
    if spec is None:
        return None
    state = load()
    row = (state.get("categories") or {}).get(spec.id)
    events = [e for e in (state.get("events") or []) if e.get("category") == spec.id]
    return {
        "id": spec.id,
        "title": spec.title,
        "goal": spec.goal,
        "result": row,
        "events": events[-40:],
    }


def tick_one(category: str) -> dict[str, Any]:
    spec = get_spec(category)
    if spec is None:
        return {"ok": False, "error": "unknown_category", "id": category}
    return run_spec(spec)


async def tick_all() -> dict[str, Any]:
    started = time.time()
    sem = asyncio.Semaphore(max_concurrency())
    results: list[dict[str, Any]] = []

    async def one(spec):
        async with sem:
            return await asyncio.to_thread(run_spec, spec)

    gathered = await asyncio.gather(*(one(spec) for spec in CATEGORIES), return_exceptions=True)
    for spec, item in zip(CATEGORIES, gathered):
        if isinstance(item, Exception):
            results.append(
                {
                    "id": spec.id,
                    "title": spec.title,
                    "goal": spec.goal,
                    "summary": spec.dry_run_summary,
                    "mode": "dry_run",
                    "label": "DRY-RUN",
                    "reason": str(item),
                    "ok": True,
                }
            )
        else:
            results.append(item)
    meta = {
        "ts": time.time(),
        "elapsed_ms": int((time.time() - started) * 1000),
        "concurrency": max_concurrency(),
        "count": len(results),
        "modes": {r["id"]: r.get("mode") for r in results},
        "lm_studio_used": any(r.get("mode") == "lm_studio" for r in results),
    }
    record_tick_meta(meta)
    return {"ok": True, "tick": meta, "results": results, **snapshot()}
