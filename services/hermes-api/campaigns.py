"""Hermes OS campaign store + autonomous flywheel/orchestra runner."""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable

ORCHESTRA_STAGES: tuple[tuple[str, str, str], ...] = (
    ("research", "Research Agent", "script"),
    ("script", "Writer Agent", "script"),
    ("render", "Editor Agent", "render"),
    ("score", "Analyst Agent", "score"),
    ("breed", "Evolution Lab", "breed"),
    ("publish", "Publishing Agent", "publish"),
)

_DEFAULT_STORE = Path(__file__).resolve().parent / "data" / "campaigns.json"


def store_path() -> Path:
    raw = (os.environ.get("HERMES_CAMPAIGN_STORE") or "").strip()
    return Path(raw) if raw else _DEFAULT_STORE


def retry_backoff_seconds() -> float:
    raw = os.environ.get("HERMES_CAMPAIGN_RETRY_SECONDS") or "0.05"
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.05


def max_stage_attempts() -> int:
    raw = os.environ.get("HERMES_CAMPAIGN_MAX_ATTEMPTS") or "3"
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def _now() -> float:
    return time.time()


def _empty_db() -> dict[str, Any]:
    return {"campaigns": {}}


def load_db() -> dict[str, Any]:
    path = store_path()
    if not path.is_file():
        return _empty_db()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_db()
    if not isinstance(data, dict) or not isinstance(data.get("campaigns"), dict):
        return _empty_db()
    return data


def save_db(db: dict[str, Any]) -> None:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(db, indent=2), encoding="utf-8")
    tmp.replace(path)


def list_campaigns() -> list[dict[str, Any]]:
    db = load_db()
    items = list(db["campaigns"].values())
    items.sort(key=lambda c: float(c.get("updated_at") or 0), reverse=True)
    return items


def get_campaign(campaign_id: str) -> dict[str, Any] | None:
    db = load_db()
    item = db["campaigns"].get(campaign_id)
    return item if isinstance(item, dict) else None


def upsert_campaign(campaign: dict[str, Any]) -> dict[str, Any]:
    db = load_db()
    campaign["updated_at"] = _now()
    db["campaigns"][campaign["id"]] = campaign
    save_db(db)
    return campaign


def _upsert(campaign: dict[str, Any]) -> dict[str, Any]:
    return upsert_campaign(campaign)


def _append_event(campaign: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    events = campaign.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        campaign["events"] = events
    payload = {"ts": _now(), **event}
    events.append(payload)
    return _upsert(campaign)


def fail_campaign(campaign_id: str, message: str) -> dict[str, Any] | None:
    campaign = get_campaign(campaign_id)
    if campaign is None:
        return None
    campaign["status"] = "failed"
    return _append_event(
        campaign,
        {"type": "orchestra_failed", "message": message},
    )


def create_campaign(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    campaign_id = str(uuid.uuid4())
    now = _now()
    campaign = {
        "id": campaign_id,
        "niche": str(body.get("niche") or "AI education").strip() or "AI education",
        "goal": str(body.get("goal") or "Grow subscribers").strip() or "Grow subscribers",
        "platforms": str(body.get("platforms") or "YouTube Shorts, TikTok, Reels").strip(),
        "budget": str(body.get("budget") or "$2,000 / mo").strip(),
        "frequency": str(body.get("freq") or body.get("frequency") or "2 / day").strip(),
        "status": "queued",
        "mode": "pending",
        "stage": None,
        "healed": False,
        "pipeline": "hermes-flywheel",
        "created_at": now,
        "updated_at": now,
        "events": [],
        "artifacts": {},
    }
    return _upsert(campaign)


InferenceFn = Callable[[str, dict[str, Any]], str]


def _simulated_artifact(stage: str, campaign: dict[str, Any]) -> str:
    niche = campaign.get("niche") or "the niche"
    if stage == "research":
        return f"[DRY-RUN] Opportunity scan for {niche}: 3 high-velocity hooks."
    if stage == "script":
        return f"[DRY-RUN] 20s script for {niche}: hook → proof → CTA."
    if stage == "render":
        return f"[DRY-RUN] Composition plan queued ({campaign.get('platforms')})."
    if stage == "score":
        return "[DRY-RUN] Fitness 0.71 (simulated; inference unavailable)."
    if stage == "breed":
        return "[DRY-RUN] Next-gen seeds: hook mutation + CTA variant."
    return f"[DRY-RUN] Publish queued for {campaign.get('platforms')} (no live upload)."


def _extract_completion(body: Any) -> str:
    if not isinstance(body, dict):
        raise RuntimeError("inference returned a non-object body")
    if body.get("error"):
        err = body["error"]
        if isinstance(err, dict):
            raise RuntimeError(str(err.get("message") or err.get("type") or err))
        raise RuntimeError(str(err))
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("inference returned no choices")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content") or first.get("text") or ""
    text = str(content).strip()
    if not text:
        raise RuntimeError("inference returned empty content")
    return text[:1200]


def default_inference(prompt: str, upstream: Callable[..., tuple[int, Any]]) -> str:
    code, body = upstream(
        "POST",
        "/chat/completions",
        {
            "model": os.environ.get("INFERENCE_MODEL")
            or os.environ.get("LM_STUDIO_MODEL")
            or "local-model",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 120,
            "temperature": 0.4,
        },
        12,
    )
    if code != 200:
        raise RuntimeError(f"inference HTTP {code}: {body}")
    return _extract_completion(body)


def _stage_prompt(stage: str, campaign: dict[str, Any]) -> str:
    return (
        f"You are the Hermes {stage} agent on the hermes-flywheel orchestra. "
        f"Niche: {campaign.get('niche')}. Goal: {campaign.get('goal')}. "
        f"Platforms: {campaign.get('platforms')}. "
        "Reply in 2 short sentences with a concrete next action. No markdown."
    )


async def run_orchestra(
    campaign_id: str,
    *,
    infer: Callable[[str], str] | None = None,
    sleep: Callable[[float], Any] | None = None,
) -> dict[str, Any]:
    """Run flywheel stages with retries. Inference failure self-heals to dry-run."""
    waiter = sleep or asyncio.sleep
    campaign = get_campaign(campaign_id)
    if campaign is None:
        raise KeyError(campaign_id)
    campaign["status"] = "running"
    campaign["mode"] = "live"
    campaign = _append_event(
        campaign,
        {
            "type": "orchestra_started",
            "message": "Launching agent orchestra (hermes-flywheel).",
            "label": "live",
        },
    )

    for stage, agent, flywheel_stage in ORCHESTRA_STAGES:
        campaign = get_campaign(campaign_id) or campaign
        campaign["stage"] = stage
        campaign = _append_event(
            campaign,
            {
                "type": "stage_started",
                "stage": stage,
                "flywheel_stage": flywheel_stage,
                "agent": agent,
                "message": f"{agent} started {stage}.",
            },
        )

        attempts = max_stage_attempts()
        last_error = ""
        used_dry = campaign.get("mode") == "dry_run"
        result_text = ""

        for attempt in range(1, attempts + 1):
            if used_dry:
                result_text = _simulated_artifact(stage, campaign)
                campaign = _append_event(
                    campaign,
                    {
                        "type": "stage_simulated",
                        "stage": stage,
                        "agent": agent,
                        "attempt": attempt,
                        "label": "DRY-RUN",
                        "message": f"{agent} completed {stage} in labeled dry-run (self-heal).",
                    },
                )
                break
            try:
                if infer is None:
                    raise RuntimeError("no inference function bound")
                result_text = await asyncio.to_thread(infer, _stage_prompt(stage, campaign))
                campaign = _append_event(
                    campaign,
                    {
                        "type": "stage_inferred",
                        "stage": stage,
                        "agent": agent,
                        "attempt": attempt,
                        "label": "live",
                        "message": f"{agent} used inference for {stage}.",
                    },
                )
                break
            except Exception as exc:  # retry then heal — never hang the console
                last_error = str(exc)
                campaign = _append_event(
                    campaign,
                    {
                        "type": "stage_retry",
                        "stage": stage,
                        "agent": agent,
                        "attempt": attempt,
                        "error": last_error[:400],
                        "message": f"{agent} failed {stage} (attempt {attempt}/{attempts}); backing off.",
                    },
                )
                if attempt < attempts:
                    await waiter(retry_backoff_seconds() * (2 ** (attempt - 1)))
                    continue
                used_dry = True
                campaign["mode"] = "dry_run"
                campaign["healed"] = True
                result_text = _simulated_artifact(stage, campaign)
                campaign = _append_event(
                    campaign,
                    {
                        "type": "self_heal",
                        "stage": stage,
                        "agent": agent,
                        "label": "DRY-RUN",
                        "error": last_error[:400],
                        "message": (
                            "Inference unavailable after retries. "
                            "Self-healed to labeled dry-run orchestra; cycle will complete."
                        ),
                    },
                )

        artifacts = campaign.setdefault("artifacts", {})
        if not isinstance(artifacts, dict):
            artifacts = {}
            campaign["artifacts"] = artifacts
        artifacts[stage] = result_text
        campaign = _append_event(
            campaign,
            {
                "type": "stage_completed",
                "stage": stage,
                "agent": agent,
                "mode": campaign.get("mode"),
                "message": f"{agent} finished {stage}.",
            },
        )

    campaign = get_campaign(campaign_id) or campaign
    healed = bool(campaign.get("healed"))
    campaign["status"] = "completed_healed" if healed else "completed"
    campaign["stage"] = "done"
    campaign = _append_event(
        campaign,
        {
            "type": "orchestra_completed",
            "label": "DRY-RUN" if healed else "live",
            "healed": healed,
            "message": (
                "Campaign cycle complete (self-healed dry-run)."
                if healed
                else "Campaign cycle complete with live inference."
            ),
        },
    )
    return campaign


def bind_infer_from_app(upstream: Callable[..., tuple[int, Any]]) -> Callable[[str], str]:
    def _infer(prompt: str) -> str:
        return default_inference(prompt, upstream)

    return _infer
