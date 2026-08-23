"""Perpetual Hermes campaign flywheel: self-check, self-heal, enqueue next cycle."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from campaigns import create_campaign, list_campaigns

_DEFAULT_STORE = Path(__file__).resolve().parent / "data" / "flywheel.json"
CANONICAL_ORIGIN = "http://127.0.0.1:8091"
SELF_CHECK_PATHS = (
    "/livez",
    "/readyz",
    "/health",
    "/api/status",
    "/api/billing/config",
    "/api/campaigns",
)


def store_path() -> Path:
    raw = (os.environ.get("HERMES_FLYWHEEL_STORE") or "").strip()
    return Path(raw) if raw else _DEFAULT_STORE


def sleep_seconds() -> float:
    raw = os.environ.get("HERMES_FLYWHEEL_SLEEP_SECONDS") or "0.25"
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.25


def _empty() -> dict[str, Any]:
    return {
        "running": False,
        "stop_requested": False,
        "cycle_count": 0,
        "max_concurrent": 1,
        "origin": CANONICAL_ORIGIN,
        "origin_note": (
            "Single console origin is http://127.0.0.1:8091. "
            "If the port is stale, restart one uvicorn there — do not bind a second origin."
        ),
        "last_self_check": {},
        "last_campaign_id": None,
        "active_campaign_id": None,
        "ticks": [],
        "updated_at": time.time(),
    }


def load_state() -> dict[str, Any]:
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
    if not isinstance(base.get("ticks"), list):
        base["ticks"] = []
    return base


def save_state(state: dict[str, Any]) -> dict[str, Any]:
    state["updated_at"] = time.time()
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)
    return state


def snapshot() -> dict[str, Any]:
    state = load_state()
    ticks = state.get("ticks") or []
    return {
        "running": bool(state.get("running")) and not bool(state.get("stop_requested")),
        "stop_requested": bool(state.get("stop_requested")),
        "cycle_count": int(state.get("cycle_count") or 0),
        "max_concurrent": 1,
        "origin": CANONICAL_ORIGIN,
        "origin_note": state.get("origin_note"),
        "last_self_check": state.get("last_self_check") or {},
        "last_campaign_id": state.get("last_campaign_id"),
        "active_campaign_id": state.get("active_campaign_id"),
        "ticks": ticks[-20:],
        "tick_total": len(ticks),
    }


def request_stop() -> dict[str, Any]:
    state = load_state()
    state["stop_requested"] = True
    state["running"] = False
    save_state(state)
    return snapshot()


def request_start() -> dict[str, Any]:
    state = load_state()
    state["stop_requested"] = False
    state["running"] = True
    save_state(state)
    return snapshot()


def should_continue() -> bool:
    state = load_state()
    return bool(state.get("running")) and not bool(state.get("stop_requested"))


def summarize_probe(path: str, status_code: int, body: Any) -> dict[str, Any]:
    ok = 200 <= int(status_code) < 300
    inference_down = False
    if path == "/health" and isinstance(body, dict):
        inf = body.get("inference") if isinstance(body.get("inference"), dict) else {}
        inference_down = inf.get("reachable") is False
    return {
        "path": path,
        "ok": ok,
        "status_code": status_code,
        "inference_down": inference_down,
    }


def record_self_check(probes: list[dict[str, Any]]) -> dict[str, Any]:
    inference_down = any(p.get("inference_down") for p in probes)
    failing = [p["path"] for p in probes if not p.get("ok")]
    payload = {
        "ts": time.time(),
        "ok": not failing,
        "inference_down": inference_down,
        "failing": failing,
        "probes": probes,
        "mode": "dry_run" if inference_down or failing else "live",
        "note": (
            "Inference down — flywheel still ticks as labeled dry-run."
            if inference_down
            else "Self-check passed."
        ),
    }
    state = load_state()
    state["last_self_check"] = payload
    save_state(state)
    return payload


def _running_campaigns() -> int:
    return sum(1 for c in list_campaigns() if c.get("status") == "running")


async def run_one_tick(
    *,
    infer: Callable[[str], str] | None,
    run_orchestra: Callable[..., Awaitable[dict[str, Any]]],
    probes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Self-check, then run exactly one campaign (max concurrent 1), persist the tick."""
    check = record_self_check(probes)
    state = load_state()
    if not should_continue():
        return {"skipped": True, "reason": "stop_requested", **snapshot()}

    agent_tick: dict[str, Any] | None = None
    try:
        from agents.orchestrator import tick_all as _tick_category_agents

        agent_tick = await _tick_category_agents()
    except Exception as exc:
        agent_tick = {"ok": False, "error": str(exc), "mode": "dry_run"}

    if _running_campaigns() >= 1 or state.get("active_campaign_id"):
        return {
            "skipped": True,
            "reason": "max_concurrent",
            "agents": agent_tick,
            **snapshot(),
        }

    campaign = create_campaign(
        {
            "niche": "AI education",
            "goal": "Grow subscribers",
            "brief": "Flywheel tick — self-check then breed/publish, then enqueue next.",
            "agent": "video-campaign",
        }
    )
    state = load_state()
    state["active_campaign_id"] = campaign["id"]
    save_state(state)

    try:
        result = await run_orchestra(campaign["id"], infer=infer)
    except Exception:
        state = load_state()
        state["active_campaign_id"] = None
        save_state(state)
        raise
    status = str(result.get("status") or "")
    healed = bool(result.get("healed"))
    tick = {
        "ts": time.time(),
        "cycle": int(load_state().get("cycle_count") or 0) + 1,
        "campaign_id": campaign["id"],
        "status": status,
        "healed": healed,
        "self_check_ok": check.get("ok"),
        "inference_down": check.get("inference_down"),
        "mode": result.get("mode") or check.get("mode"),
        "agents": {
            "ok": bool((agent_tick or {}).get("ok")),
            "count": len((agent_tick or {}).get("results") or []),
            "lm_studio_used": bool(((agent_tick or {}).get("tick") or {}).get("lm_studio_used")),
        },
    }
    state = load_state()
    state["cycle_count"] = int(state.get("cycle_count") or 0) + 1
    state["last_campaign_id"] = campaign["id"]
    state["active_campaign_id"] = None
    ticks = list(state.get("ticks") or [])
    ticks.append(tick)
    state["ticks"] = ticks[-200:]
    save_state(state)
    return {"skipped": False, "tick": tick, "agents": agent_tick, **snapshot()}


async def run_loop(
    *,
    infer: Callable[[str], str] | None,
    run_orchestra: Callable[..., Awaitable[dict[str, Any]]],
    collect_probes: Callable[[], list[dict[str, Any]]],
    sleep: Callable[[float], Awaitable[Any]],
) -> None:
    while should_continue():
        await run_one_tick(
            infer=infer,
            run_orchestra=run_orchestra,
            probes=collect_probes(),
        )
        if not should_continue():
            break
        await sleep(sleep_seconds())
    state = load_state()
    state["running"] = False
    save_state(state)
