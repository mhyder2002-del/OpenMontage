"""Hermes OS campaign store + autonomous video-campaign / orchestra runner."""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

# Research/script still lead so inference outages self-heal before tool stages.
ORCHESTRA_STAGES: tuple[tuple[str, str, str], ...] = (
    ("research", "Research Agent", "script"),
    ("script", "Writer Agent", "script"),
    ("plan", "Cut Planner", "idea"),
    ("route", "Video Selector", "preflight"),
    ("compose", "Composer Agent", "render"),
    ("mpt", "MoneyPrinter Agent", "render"),
    ("score", "Analyst Agent", "score"),
    ("breed", "Evolution Lab", "breed"),
    ("publish", "Publishing Agent", "publish"),
)

_HERE = Path(__file__).resolve().parent
_DEFAULT_STORE = _HERE / "data" / "campaigns.json"


def _repo_root() -> Path:
    """OpenMontage repo when present; /app in the Hostinger image."""
    for candidate in (_HERE, *_HERE.parents):
        if (candidate / "tools" / "video" / "video_selector.py").is_file():
            return candidate
        if candidate.parent == candidate:
            break
    try:
        return _HERE.parents[2]
    except IndexError:
        return _HERE


_REPO_ROOT = _repo_root()


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


def live_media_enabled() -> bool:
    return (os.environ.get("HERMES_CAMPAIGN_LIVE_MEDIA") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _now() -> float:
    return time.time()


def _empty_db() -> dict[str, Any]:
    return {"campaigns": {}}


def load_db() -> dict[str, Any]:
    """SQLite is source of truth; campaigns.json is migrated once via db.ensure_db."""
    from db import list_campaign_rows

    rows = list_campaign_rows()
    campaigns = {str(item["id"]): item for item in rows if isinstance(item, dict) and item.get("id")}
    return {"campaigns": campaigns}


def save_db(db: dict[str, Any]) -> None:
    from db import upsert_campaign_row

    campaigns = db.get("campaigns") if isinstance(db, dict) else None
    if not isinstance(campaigns, dict):
        return
    for item in campaigns.values():
        if isinstance(item, dict) and item.get("id"):
            upsert_campaign_row(item)


def campaign_label(campaign: dict[str, Any]) -> str:
    if bool(campaign.get("healed")) or campaign.get("mode") == "dry_run":
        return "DRY-RUN"
    if campaign.get("mode") == "live":
        return "live"
    return str(campaign.get("label") or "pending")


def publish_notes(campaign: dict[str, Any]) -> dict[str, Any]:
    mpt = campaign.get("moneyprinter") if isinstance(campaign.get("moneyprinter"), dict) else {}
    healed = bool(campaign.get("healed"))
    label = str(mpt.get("label") or campaign_label(campaign))
    paths = list(mpt.get("video_paths") or [])
    return {
        "label": label,
        "mode": mpt.get("mode") or ("dry_run" if healed else campaign.get("mode") or "queued"),
        "binary_upload": False,
        "mpt_paths": paths,
        "note": (
            f"MoneyPrinterTurbo {label}"
            + (f": {paths[:3]}" if paths else " (optional; :8088 DRY-RUN if down).")
            + " No binary upload from hermes-api."
        ),
    }


def decorate_campaign(campaign: dict[str, Any] | None) -> dict[str, Any] | None:
    """UI-bindable fields. Does not call video_compose.execute."""
    if not isinstance(campaign, dict):
        return campaign
    campaign["pipeline"] = campaign.get("pipeline") or "hermes-flywheel"
    campaign["pipeline_yaml"] = "pipeline_defs/hermes-flywheel.yaml"
    campaign["live_compose"] = False
    campaign["label"] = campaign_label(campaign)
    campaign["publish"] = publish_notes(campaign)
    return campaign


def list_campaigns() -> list[dict[str, Any]]:
    from db import list_campaign_rows

    items = list_campaign_rows()
    items.sort(key=lambda c: float(c.get("updated_at") or 0), reverse=True)
    return [decorate_campaign(item) or item for item in items]


def get_campaign(campaign_id: str) -> dict[str, Any] | None:
    from db import get_campaign_row

    item = get_campaign_row(campaign_id)
    return decorate_campaign(item) if isinstance(item, dict) else None


def upsert_campaign(campaign: dict[str, Any]) -> dict[str, Any]:
    from db import upsert_campaign_row

    campaign["updated_at"] = _now()
    upsert_campaign_row(campaign)
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
        "agent": "video-campaign",
        "niche": str(body.get("niche") or "AI education").strip() or "AI education",
        "goal": str(body.get("goal") or "Grow subscribers").strip() or "Grow subscribers",
        "brief": str(body.get("brief") or "").strip(),
        "platforms": str(body.get("platforms") or "YouTube Shorts, TikTok, Reels").strip(),
        "budget": str(body.get("budget") or "$2,000 / mo").strip(),
        "frequency": str(body.get("freq") or body.get("frequency") or "2 / day").strip(),
        "status": "queued",
        "mode": "pending",
        "stage": None,
        "healed": False,
        "label": "pending",
        "pipeline": "hermes-flywheel",
        "pipeline_yaml": "pipeline_defs/hermes-flywheel.yaml",
        "live_compose": False,
        "created_at": now,
        "updated_at": now,
        "events": [],
        "artifacts": {},
        "cuts": [],
        "routing": {},
        "compose": {},
        "moneyprinter": {},
        "publish": {},
    }
    return _upsert(campaign)


InferenceFn = Callable[[str, dict[str, Any]], str]


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:32] or "cut"


def plan_cuts(campaign: dict[str, Any], *, dry: bool) -> list[dict[str, Any]]:
    """Deterministic cut slate from niche/goal/brief — not a paid generation call."""
    niche = str(campaign.get("niche") or "campaign")
    goal = str(campaign.get("goal") or "grow")
    brief = str(campaign.get("brief") or "").strip()
    platforms = str(campaign.get("platforms") or "Shorts")
    base = _slug(niche)
    hooks = [
        f"Hook: {niche} in 3 seconds — {goal}",
        f"Proof cut: what actually works for {niche}",
        f"CTA cut: subscribe path for {platforms.split(',')[0].strip()}",
    ]
    if brief:
        hooks[0] = f"Hook from brief: {brief[:80]}"
    label = "DRY-RUN" if dry else "planned"
    mode = "dry_run" if dry else "live"
    cuts: list[dict[str, Any]] = []
    templates = (
        (7, 20.0),
        (7, 19.94),
        (4, 12.6),
    )
    for i, ((scenes, duration), hook) in enumerate(zip(templates, hooks), start=1):
        cuts.append(
            {
                "id": f"{base}_{i}",
                "slug": f"{base}_{i}",
                "title": niche,
                "hook": hook,
                "scenes": scenes,
                "duration_s": duration,
                "status": "dry_run_complete" if dry else "planned",
                "mode": mode,
                "label": label,
                "asset": None,
            }
        )
    return cuts


def _simulated_artifact(stage: str, campaign: dict[str, Any]) -> str:
    niche = campaign.get("niche") or "the niche"
    if stage == "research":
        return f"[DRY-RUN] Opportunity scan for {niche}: 3 high-velocity hooks."
    if stage == "script":
        return f"[DRY-RUN] 20s script for {niche}: hook → proof → CTA."
    if stage == "plan":
        return f"[DRY-RUN] Planned {len(campaign.get('cuts') or []) or 3} vertical cuts for {niche}."
    if stage == "route":
        return "[DRY-RUN] video_selector rank skipped (self-heal). No provider generate."
    if stage == "compose":
        return "[DRY-RUN] Composition plan queued — live render requires OpenMontage pipeline."
    if stage == "mpt":
        return (
            "[DRY-RUN] MoneyPrinterTurbo skipped (not enabled or unreachable). "
            "Set MONEYPRINTER_ENABLED=true and run the moneyprinter compose profile."
        )
    if stage == "score":
        return "[DRY-RUN] Fitness 0.71 (simulated; inference unavailable)."
    if stage == "breed":
        return "[DRY-RUN] Next-gen seeds: hook mutation + CTA variant."
    return f"[DRY-RUN] Publish queued for {campaign.get('platforms')} (no live upload)."


def _ensure_repo_on_path() -> None:
    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def rank_video_tools(prompt: str) -> dict[str, Any]:
    """Registry rank only — never text_to_video generation from this agent."""
    _ensure_repo_on_path()
    try:
        from tools.video.video_selector import VideoSelector
    except ImportError:
        return {
            "top_tool": "none",
            "top_status": "unavailable",
            "ranked": 0,
            "explanation": "OpenMontage tools/ not present in this image; rank skipped.",
            "live_generate": False,
            "skipped": True,
        }

    result = VideoSelector().execute(
        {
            "prompt": prompt,
            "operation": "rank",
            "target_operation": "text_to_video",
            "aspect_ratio": "9:16",
            "duration": "8",
        }
    )
    if not result.success:
        raise RuntimeError(result.error or "video_selector rank failed")
    data = result.data if isinstance(result.data, dict) else {}
    rankings = data.get("rankings") or []
    top = rankings[0] if rankings and isinstance(rankings[0], dict) else {}
    return {
        "top_tool": top.get("tool_name") or top.get("name") or "none",
        "top_status": top.get("status"),
        "ranked": len(rankings),
        "explanation": str(data.get("explanation") or "")[:600],
        "live_generate": False,
    }


def apply_moneyprinter(campaign: dict[str, Any], *, force_dry: bool) -> str:
    """Optional MPT topic→short. Unreachable/disabled → labeled DRY-RUN without failing the run."""
    from moneyprinter import dry_run_result, generate

    topic = str(campaign.get("niche") or campaign.get("brief") or "campaign short")
    if force_dry:
        result = dry_run_result(topic, "campaign already in labeled dry-run")
    else:
        result = generate(topic)
    campaign["moneyprinter"] = result
    paths = list(result.get("video_paths") or [])
    extra = {
        "mpt_label": result.get("label"),
        "mpt_mode": result.get("mode"),
        "mpt_paths": paths,
    }
    _set_cuts_status(
        campaign,
        "mpt_dry" if result.get("mode") == "dry_run" else "mpt_ready",
        extra=extra,
    )
    if result.get("mode") == "dry_run":
        return (
            f"MoneyPrinterTurbo DRY-RUN ({result.get('reason') or 'optional'}). "
            f"paths={paths}"
        )
    return f"MoneyPrinterTurbo live task={result.get('task_id')} paths={paths}"


def compose_runtime_plan() -> dict[str, Any]:
    _ensure_repo_on_path()
    try:
        from tools.video.video_compose import VideoCompose
    except ImportError:
        return {
            "render_engines": {},
            "runtime_governance": None,
            "live_render": False,
            "skipped": True,
            "note": "OpenMontage tools/ not present in this image; compose plan skipped.",
        }

    info = VideoCompose().get_info()
    engines = info.get("render_engines") or {}
    return {
        "render_engines": engines,
        "runtime_governance": info.get("runtime_governance"),
        "live_render": False,
        "note": (
            "Campaign agent does not call video_compose.execute. "
            "Live media must go through an OpenMontage pipeline with stage directors."
        ),
    }


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
        f"You are the Hermes video-campaign {stage} agent. "
        f"Niche: {campaign.get('niche')}. Goal: {campaign.get('goal')}. "
        f"Brief: {campaign.get('brief') or '(none)'}. "
        f"Platforms: {campaign.get('platforms')}. "
        "Reply in 2 short sentences with a concrete next action. No markdown."
    )


def _set_cuts_status(campaign: dict[str, Any], status: str, *, extra: dict[str, Any] | None = None) -> None:
    cuts = campaign.get("cuts")
    if not isinstance(cuts, list):
        return
    for cut in cuts:
        if not isinstance(cut, dict):
            continue
        cut["status"] = status
        if extra:
            cut.update(extra)


def _run_tool_stage(stage: str, campaign: dict[str, Any], used_dry: bool) -> str:
    dry = used_dry or campaign.get("mode") == "dry_run"
    if stage == "plan":
        cuts = plan_cuts(campaign, dry=dry)
        campaign["cuts"] = cuts
        return f"Planned {len(cuts)} cuts ({'DRY-RUN' if dry else 'live-plan'})."
    if stage == "route":
        if dry:
            _set_cuts_status(campaign, "routed_dry", extra={"label": "DRY-RUN"})
            campaign["routing"] = {"live_generate": False, "healed": True}
            return _simulated_artifact("route", campaign)
        ranking = rank_video_tools(
            f"{campaign.get('niche')} {campaign.get('goal')} {campaign.get('brief') or ''} vertical short"
        )
        if live_media_enabled():
            ranking["pipeline_gate"] = (
                "HERMES_CAMPAIGN_LIVE_MEDIA is on, but this agent will not call "
                "video_selector generate. Use an OpenMontage pipeline for media."
            )
        campaign["routing"] = ranking
        _set_cuts_status(
            campaign,
            "routed",
            extra={"tool": ranking.get("top_tool"), "label": "rank-only"},
        )
        return (
            f"video_selector rank: top={ranking.get('top_tool')} "
            f"({ranking.get('ranked')} tools). No generate."
        )
    if stage == "compose":
        if dry:
            _set_cuts_status(campaign, "dry_run_complete", extra={"label": "DRY-RUN"})
            campaign["compose"] = {"live_render": False, "healed": True}
            return _simulated_artifact("compose", campaign)
        plan = compose_runtime_plan()
        campaign["compose"] = plan
        _set_cuts_status(
            campaign,
            "compose_planned",
            extra={"label": "pipeline-gated"},
        )
        engines = plan.get("render_engines") or {}
        return f"video_compose get_info engines={engines}. No execute/render."
    if stage == "mpt":
        return apply_moneyprinter(campaign, force_dry=dry)
    raise RuntimeError(f"not a tool stage: {stage}")


async def run_orchestra(
    campaign_id: str,
    *,
    infer: Callable[[str], str] | None = None,
    sleep: Callable[[float], Any] | None = None,
) -> dict[str, Any]:
    """Run video-campaign stages with retries. Failures self-heal to labeled dry-run."""
    waiter = sleep or asyncio.sleep
    campaign = get_campaign(campaign_id)
    if campaign is None:
        raise KeyError(campaign_id)
    campaign["status"] = "running"
    campaign["mode"] = "live"
    campaign["agent"] = "video-campaign"
    campaign["pipeline"] = "hermes-flywheel"
    campaign["pipeline_yaml"] = "pipeline_defs/hermes-flywheel.yaml"
    campaign["live_compose"] = False
    campaign["label"] = "live"
    campaign = _append_event(
        campaign,
        {
            "type": "orchestra_started",
            "message": (
                "Launching video-campaign agent "
                "(plan cuts → video_selector rank → compose plan → optional MoneyPrinterTurbo)."
            ),
            "label": "live",
            "agent": "video-campaign",
        },
    )

    tool_stages = {"plan", "route", "compose", "mpt"}

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
                if stage == "plan":
                    campaign["cuts"] = plan_cuts(campaign, dry=True)
                elif stage in {"route", "compose", "mpt"}:
                    result_text = _run_tool_stage(stage, campaign, True)
                else:
                    result_text = _simulated_artifact(stage, campaign)
                if stage == "plan":
                    result_text = _simulated_artifact("plan", campaign)
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
                if stage in tool_stages:
                    result_text = await asyncio.to_thread(_run_tool_stage, stage, campaign, False)
                    event_type = {
                        "plan": "cuts_planned",
                        "route": "video_ranked",
                        "compose": "compose_planned",
                        "mpt": "moneyprinter_completed",
                    }[stage]
                    campaign = _append_event(
                        campaign,
                        {
                            "type": event_type,
                            "stage": stage,
                            "agent": agent,
                            "attempt": attempt,
                            "label": "live",
                            "message": result_text,
                        },
                    )
                    break
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
                campaign["label"] = "DRY-RUN"
                if stage == "plan":
                    campaign["cuts"] = plan_cuts(campaign, dry=True)
                    result_text = _simulated_artifact("plan", campaign)
                elif stage in tool_stages:
                    result_text = _run_tool_stage(stage, campaign, True)
                else:
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
                            "Stage unavailable after retries. "
                            "Self-healed to labeled dry-run video campaign; cycle will complete."
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
    if campaign.get("cuts"):
        _set_cuts_status(
            campaign,
            "dry_run_complete" if healed else "ready",
            extra={"label": "DRY-RUN" if healed else "queued"},
        )
    campaign["status"] = "completed_healed" if healed else "completed"
    campaign["stage"] = "done"
    campaign["label"] = "DRY-RUN" if healed else "live"
    campaign["live_compose"] = False
    campaign["publish"] = publish_notes(campaign)
    campaign = _append_event(
        campaign,
        {
            "type": "orchestra_completed",
            "label": "DRY-RUN" if healed else "live",
            "healed": healed,
            "agent": "video-campaign",
            "cuts": len(campaign.get("cuts") or []),
            "message": (
                "Video campaign complete (self-healed dry-run cuts)."
                if healed
                else "Video campaign complete: cuts planned, tools ranked, compose gated."
            ),
        },
    )
    return campaign


def bind_infer_from_app(upstream: Callable[..., tuple[int, Any]]) -> Callable[[str], str]:
    def _infer(prompt: str) -> str:
        return default_inference(prompt, upstream)

    return _infer
