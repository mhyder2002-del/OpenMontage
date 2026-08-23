"""Thin research agent: LM Studio via existing inference proxy, else labeled dry-run."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable

from db import upsert_knowledge_node


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dry_run_trend(topic: str) -> str:
    return f"[DRY-RUN] Opportunity scan for {topic}: high-velocity hooks on Shorts + Reddit."


def infer_trend(topic: str, infer: Callable[[str], str]) -> str:
    prompt = (
        f"Name one current content trend for the topic {topic!r} in one short sentence. "
        "No markdown."
    )
    text = infer(prompt).strip()
    if not text:
        raise RuntimeError("empty research completion")
    return text[:400]


def run_research(
    topic: str,
    *,
    infer: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    cleaned = (topic or "AI").strip() or "AI"
    timeout_raw = os.environ.get("HERMES_RESEARCH_TIMEOUT") or "4"
    try:
        timeout = max(0.2, float(timeout_raw))
    except ValueError:
        timeout = 4.0
    trend = ""
    mode = "dry_run"
    if infer is not None:
        try:
            # Bound by caller timeout on _upstream; never hang the console.
            _ = timeout
            trend = infer_trend(cleaned, infer)
            mode = "live"
        except Exception:
            trend = dry_run_trend(cleaned)
            mode = "dry_run"
    if not trend:
        trend = dry_run_trend(cleaned)
    node = upsert_knowledge_node(cleaned, trend, source="research")
    return {
        "topic": cleaned,
        "trend": trend,
        "timestamp": _now_iso(),
        "mode": mode,
        "label": "DRY-RUN" if mode == "dry_run" else "live",
        "node": node,
    }
