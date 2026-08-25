"""Hermes OS product surfaces from the reference console: discovery, orchestra, evolution, memory."""

from __future__ import annotations

import uuid
from typing import Any

from db import (
    append_debug_event,
    append_metric_point,
    get_experiment,
    list_experiments,
    list_jobs,
    list_learnings,
    list_metric_series,
    list_opportunities,
    list_pipeline_agents,
    set_variant_state,
    upsert_experiment,
    upsert_experiment_variant,
    upsert_job,
    upsert_learning,
    upsert_opportunity,
    upsert_pipeline_agent,
)

DISCOVERY_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "youtube", "name": "YouTube", "kind": "platform"},
    {"id": "tiktok", "name": "TikTok", "kind": "platform"},
    {"id": "reddit", "name": "Reddit", "kind": "platform"},
    {"id": "trends", "name": "Trends", "kind": "signal"},
    {"id": "x", "name": "X", "kind": "platform"},
    {"id": "news", "name": "News", "kind": "signal"},
    {"id": "rivals", "name": "Rivals", "kind": "competitive"},
)

WORKFORCE_AGENTS: tuple[dict[str, str], ...] = (
    {"key": "research", "title": "Research"},
    {"key": "hook", "title": "Hook"},
    {"key": "script", "title": "Script"},
    {"key": "storyboard", "title": "Storyboard"},
    {"key": "narration", "title": "Narration"},
    {"key": "video", "title": "Video"},
    {"key": "publishing", "title": "Publishing"},
    {"key": "analytics", "title": "Analytics"},
)

STAGE_TO_WORKFORCE: dict[str, str] = {
    "research": "research",
    "script": "script",
    "plan": "storyboard",
    "route": "video",
    "compose": "video",
    "mpt": "video",
    "score": "analytics",
    "breed": "analytics",
    "publish": "publishing",
}

DEFAULT_OPPORTUNITIES: tuple[dict[str, Any], ...] = (
    {"title": "AI agents explained", "score": 94, "source": "YouTube", "rank": 1},
    {"title": "Local LLMs in 2026", "score": 88, "source": "Trends", "rank": 2},
    {"title": "Prompt engineering is dead", "score": 81, "source": "Reddit", "rank": 3},
)

DEFAULT_LEARNINGS: tuple[dict[str, Any], ...] = (
    {"insight": "Hooks that mention money", "lift": 23.0, "category": "hook"},
    {"insight": "Fast zooms in first second", "lift": 18.0, "category": "motion"},
)

DEFAULT_VARIANTS: tuple[dict[str, Any], ...] = (
    {"label": "Thumbnail A", "category": "thumbnail", "score": 61, "state": "archived"},
    {"label": "Thumbnail B", "category": "thumbnail", "score": 94, "state": "promoted"},
    {"label": "Hook • curiosity", "category": "hook", "score": 88, "state": "promoted"},
    {"label": "Hook • challenge", "category": "hook", "score": 44, "state": "archived"},
    {"label": "Post 6PM", "category": "timing", "score": 40, "state": "testing"},
    {"label": "Post 9AM", "category": "timing", "score": 91, "state": "promoted"},
)


def _source_status(name: str, topics: list[dict[str, Any]]) -> str:
    blob = " ".join(str(t.get("source") or t.get("name") or "") for t in topics).lower()
    return "live" if name.lower() in blob else "idle"


def ingest_scanned_opportunities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stored = []
    for row in items:
        stored.append(upsert_opportunity(row))
    if stored:
        append_debug_event("discovery_scan", {"count": len(stored), "paid": False})
    return stored


def discovery_payload(topics: list[dict[str, Any]]) -> dict[str, Any]:
    stored = list_opportunities()
    opportunities = stored
    if not opportunities:
        opportunities = [
            {
                "id": f"topic-{i}",
                "title": str(node.get("name") or node.get("topic") or "topic"),
                "score": int(round(float(node.get("recency_score") or 0) * 100)) or 50,
                "source": str(node.get("source") or "research"),
                "rank": i + 1,
                "mode": node.get("mode"),
                "derived": True,
            }
            for i, node in enumerate(topics[:12])
        ]
    mix = list(topics) + list(opportunities)
    sources = [
        {**src, "status": _source_status(str(src["name"]), mix)}
        for src in DISCOVERY_SOURCES
    ]
    return {
        "sources": sources,
        "opportunities": opportunities,
        "count": len(topics),
        "opportunity_count": len(opportunities),
    }


def bootstrap_catalog(*, campaign_id: str | None = None) -> dict[str, Any]:
    opportunities = []
    for item in DEFAULT_OPPORTUNITIES:
        opportunities.append(upsert_opportunity(item))
    learnings = [upsert_learning(dict(item)) for item in DEFAULT_LEARNINGS]
    exp = upsert_experiment(
        {
            "id": "exp-129",
            "number": 129,
            "title": "Experiment #129",
            "campaign_id": campaign_id,
            "payload": {"lab": "evolution"},
        }
    )
    variants = []
    for item in DEFAULT_VARIANTS:
        variants.append(
            upsert_experiment_variant({**item, "experiment_id": exp["id"]})
        )
    series = []
    for metric, start, step in (
        ("retention", 10.0, 1.6),
        ("click_through", 6.0, 1.0),
        ("rpm", 2.0, 1.4),
    ):
        for run in range(1, 6):
            series.append(append_metric_point(metric, start + step * run, run_index=run))
    append_debug_event("product", {"action": "bootstrap", "opportunities": len(opportunities)})
    return {
        "ok": True,
        "opportunities": opportunities,
        "learnings": learnings,
        "experiment": {**exp, "variants": variants},
        "metrics_seeded": len(series),
    }


def compounding_analytics() -> dict[str, Any]:
    by_metric: dict[str, list[float]] = {}
    for point in list_metric_series():
        by_metric.setdefault(str(point["metric"]), []).append(float(point["value"]))
    cards = []
    for key, label in (
        ("retention", "RETENTION"),
        ("click_through", "CLICK-THROUGH"),
        ("rpm", "REVENUE / MILLE"),
    ):
        series = by_metric.get(key) or []
        latest = series[-1] if series else 0.0
        previous = series[-2] if len(series) > 1 else latest
        delta = latest - previous
        cards.append(
            {
                "metric": key,
                "label": label,
                "value": round(latest, 1),
                "delta": round(delta, 1),
                "trend": "up" if delta >= 0 else "down",
                "series": [round(v, 2) for v in series],
            }
        )
    return {"cards": cards, "headline": "COMPOUNDING, EVERY RUN"}


def memory_payload() -> dict[str, Any]:
    items = list_learnings()
    return {"title": "Things Hermes learned", "items": items, "count": len(items)}


def workforce_snapshot(campaign_id: str | None = None) -> dict[str, Any]:
    rows = list_pipeline_agents(campaign_id)
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("agent_key") or "")
        if key and key not in latest:
            latest[key] = row
    agents = []
    live = 0
    for spec in WORKFORCE_AGENTS:
        row = latest.get(spec["key"])
        status = str(row.get("status") if row else "idle")
        if status not in {"idle", "queued", "complete"}:
            live += 1
        if status == "complete":
            live += 1
        agents.append(
            {
                "key": spec["key"],
                "title": spec["title"],
                "status": status,
                "message": (row or {}).get("message") or "idle",
                "progress": float((row or {}).get("progress") or 0),
            }
        )
    return {
        "title": "AGENT ORCHESTRA",
        "live_count": min(8, max(live, sum(1 for a in agents if a["status"] != "idle"))),
        "agents": agents,
        "workforce": True,
        "pipeline": "hermes-flywheel",
        "live_compose": False,
    }


def sync_workforce_stage(campaign_id: str, stage: str, *, status: str, message: str, progress: float) -> None:
    key = STAGE_TO_WORKFORCE.get(stage, stage)
    if key == "script":
        upsert_pipeline_agent(
            {
                "campaign_id": campaign_id,
                "agent_key": "hook",
                "status": "complete" if status == "complete" else status,
                "message": "complete" if status == "complete" else "Scoring hooks",
                "progress": 1.0 if status == "complete" else min(progress, 0.9),
            }
        )
        upsert_pipeline_agent(
            {
                "campaign_id": campaign_id,
                "agent_key": "narration",
                "status": status,
                "message": "Synthesizing voice" if status == "running" else message,
                "progress": progress * 0.6,
            }
        )
    upsert_pipeline_agent(
        {
            "campaign_id": campaign_id,
            "agent_key": key if key in {s["key"] for s in WORKFORCE_AGENTS} else "video",
            "status": status,
            "message": message,
            "progress": progress,
        }
    )


def enqueue_job(
    *,
    kind: str,
    campaign_id: str | None,
    stage: str | None,
    status: str,
    progress: float,
    detail: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    return upsert_job(
        {
            "id": job_id or str(uuid.uuid4()),
            "kind": kind,
            "campaign_id": campaign_id,
            "stage": stage,
            "status": status,
            "progress": progress,
            "detail": detail or {},
        }
    )


def jobs_payload(campaign_id: str | None = None) -> dict[str, Any]:
    items = list_jobs(campaign_id=campaign_id)
    return {"jobs": items, "count": len(items)}


def evolution_lab() -> dict[str, Any]:
    experiments = list_experiments()
    latest = experiments[0] if experiments else None
    variants = list((latest or {}).get("variants") or [])
    promoted = [v for v in variants if v.get("state") == "promoted"]
    archived = [v for v in variants if v.get("state") == "archived"]
    return {
        "experiments": experiments,
        "latest": latest,
        "promoted": promoted,
        "archived": archived,
        "winners_promoted": len(promoted),
        "archived_count": len(archived),
    }


def promote_variant(variant_id: str) -> dict[str, Any] | None:
    row = set_variant_state(variant_id, "promoted")
    if row:
        append_debug_event("evolution_promote", row)
    return row


def archive_variant(variant_id: str) -> dict[str, Any] | None:
    row = set_variant_state(variant_id, "archived")
    if row:
        append_debug_event("evolution_archive", row)
    return row


def record_run_metrics(*, retention: float | None = None, ctr: float | None = None, rpm: float | None = None) -> None:
    if retention is not None:
        append_metric_point("retention", retention)
    if ctr is not None:
        append_metric_point("click_through", ctr)
    if rpm is not None:
        append_metric_point("rpm", rpm)
