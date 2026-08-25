"""Thin research agent: LM Studio via existing inference proxy, else labeled dry-run."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable

from db import append_debug_event, link_research_session, upsert_knowledge_node


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def recency_score(updated_at: str | None) -> float:
    raw = str(updated_at or "").strip()
    if not raw:
        return 0.0
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.0
    hours = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0)
    return round(1.0 / (1.0 + hours / 24.0), 4)


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
    label = "DRY-RUN" if mode == "dry_run" else "live"
    node = upsert_knowledge_node(cleaned, trend, source="research", mode=mode, label=label)
    try:
        from product import upsert_opportunity as store_opportunity

        score = 90 if mode == "live" else 72
        store_opportunity(
            {
                "id": f"opp-{(node.get('id') or cleaned).lower()[:48]}",
                "title": cleaned,
                "score": score,
                "source": "research",
                "rank": 1,
                "payload": {"mode": mode, "trend": trend},
            }
        )
    except Exception:
        pass
    try:
        link_research_session(str(node.get("id") or ""))
    except Exception as exc:
        try:
            append_debug_event("research_link_error", {"topic": cleaned, "error": type(exc).__name__})
        except Exception:
            pass
    try:
        append_debug_event("research", {"topic": cleaned, "mode": mode, "label": label})
    except Exception:
        pass
    return {
        "topic": cleaned,
        "trend": trend,
        "timestamp": _now_iso(),
        "mode": mode,
        "label": label,
        "node": node,
    }


def wikipedia_summary(topic: str, *, timeout: float = 0.8) -> str | None:
    """Optional unpaid Wikipedia REST extract. Skip on any failure."""
    import json
    from urllib.error import HTTPError, URLError
    from urllib.parse import quote
    from urllib.request import Request, urlopen

    slug = quote((topic or "").strip().replace(" ", "_"))
    if not slug:
        return None
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    req = Request(url, headers={"User-Agent": "HermesDiscovery/1.0 (OpenMontage; unpaid)"})
    try:
        with urlopen(req, timeout=max(0.2, float(timeout))) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw else {}
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None
    extract = data.get("extract") if isinstance(data, dict) else None
    if isinstance(extract, str) and extract.strip():
        return extract.strip()[:400]
    return None
