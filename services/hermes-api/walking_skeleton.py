"""Walking-skeleton creative routes: script → storyboard → thumbnail (SQLite + LM Studio)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

from db import (
    get_walking_script,
    get_walking_storyboard,
    upsert_walking_script,
    upsert_walking_storyboard,
    upsert_walking_thumbnail,
)

PLACEHOLDER_THUMBNAIL_URL = "/static/placeholders/walking-skeleton.svg"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class GenerateScriptRequest(BaseModel):
    topic: str = Field(default="AI", min_length=1)
    audience: str = ""


class GenerateScriptResponse(BaseModel):
    script_id: str
    script: str
    timestamp: str


class GenerateStoryboardRequest(BaseModel):
    script_id: str = Field(min_length=1)


class StoryboardScene(BaseModel):
    index: int
    title: str
    visual: str
    duration_s: float = 6.0


class GenerateStoryboardResponse(BaseModel):
    storyboard_id: str
    scenes: list[StoryboardScene]
    timestamp: str


class GenerateThumbnailRequest(BaseModel):
    script_id: str = Field(min_length=1)
    storyboard_id: str = Field(min_length=1)


class GenerateThumbnailResponse(BaseModel):
    thumbnail_id: str
    thumbnail_url: str
    timestamp: str


def dry_run_script(topic: str, audience: str) -> str:
    who = (audience or "general viewers").strip() or "general viewers"
    return (
        f"[DRY-RUN] 20s script on {topic} for {who}: hook → proof → CTA. "
        "Open with a concrete claim, show one example, end with a subscribe path."
    )


def dry_run_scenes(script: str) -> list[dict[str, Any]]:
    snippet = (script or "script").strip()[:80]
    return [
        {"index": 1, "title": "Hook", "visual": f"Cold open: {snippet}", "duration_s": 5.0},
        {"index": 2, "title": "Proof", "visual": "On-screen proof beat matching the script.", "duration_s": 8.0},
        {"index": 3, "title": "CTA", "visual": "End card with subscribe path.", "duration_s": 7.0},
    ]


def _infer_or_dry(prompt: str, infer: Callable[[str], str] | None, fallback: str) -> str:
    if infer is None:
        return fallback
    try:
        text = infer(prompt).strip()
        return text if text else fallback
    except Exception:
        return fallback


def create_script(
    topic: str,
    audience: str,
    *,
    infer: Callable[[str], str] | None = None,
) -> GenerateScriptResponse:
    cleaned_topic = (topic or "AI").strip() or "AI"
    cleaned_audience = (audience or "").strip()
    prompt = (
        f"Write a 20-second spoken script about {cleaned_topic!r} "
        f"for audience {cleaned_audience or 'general viewers'!r}. "
        "Three beats: hook, proof, CTA. No markdown."
    )
    script = _infer_or_dry(prompt, infer, dry_run_script(cleaned_topic, cleaned_audience))
    now = _now_iso()
    script_id = str(uuid.uuid4())
    upsert_walking_script(
        {
            "id": script_id,
            "topic": cleaned_topic,
            "audience": cleaned_audience,
            "script": script,
            "created_at": now,
        }
    )
    return GenerateScriptResponse(script_id=script_id, script=script, timestamp=now)


def create_storyboard(
    script_id: str,
    *,
    infer: Callable[[str], str] | None = None,
) -> GenerateStoryboardResponse | None:
    row = get_walking_script(script_id)
    if row is None:
        return None
    prompt = (
        "Turn this short into three storyboard scenes. Reply as three lines "
        "Title | visual description. No markdown.\n\n"
        f"{row.get('script') or ''}"
    )
    inferred = _infer_or_dry(prompt, infer, "")
    scenes = dry_run_scenes(str(row.get("script") or ""))
    if inferred and "|" in inferred:
        lines = [ln.strip() for ln in inferred.splitlines() if ln.strip()]
        parsed: list[dict[str, Any]] = []
        for i, line in enumerate(lines[:3], start=1):
            if "|" in line:
                title, visual = line.split("|", 1)
                parsed.append(
                    {
                        "index": i,
                        "title": title.strip()[:80] or f"Scene {i}",
                        "visual": visual.strip()[:240],
                        "duration_s": scenes[i - 1]["duration_s"] if i <= len(scenes) else 6.0,
                    }
                )
        if len(parsed) == 3:
            scenes = parsed
    now = _now_iso()
    storyboard_id = str(uuid.uuid4())
    upsert_walking_storyboard(
        {
            "id": storyboard_id,
            "script_id": str(row["id"]),
            "scenes": scenes,
            "created_at": now,
        }
    )
    return GenerateStoryboardResponse(
        storyboard_id=storyboard_id,
        scenes=[StoryboardScene.model_validate(s) for s in scenes],
        timestamp=now,
    )


def create_thumbnail(script_id: str, storyboard_id: str) -> GenerateThumbnailResponse | None:
    script = get_walking_script(script_id)
    board = get_walking_storyboard(storyboard_id)
    if script is None or board is None:
        return None
    if str(board.get("script_id")) != str(script.get("id")):
        return None
    now = _now_iso()
    thumbnail_id = str(uuid.uuid4())
    upsert_walking_thumbnail(
        {
            "id": thumbnail_id,
            "script_id": str(script["id"]),
            "storyboard_id": str(board["id"]),
            "thumbnail_url": PLACEHOLDER_THUMBNAIL_URL,
            "created_at": now,
        }
    )
    return GenerateThumbnailResponse(
        thumbnail_id=thumbnail_id,
        thumbnail_url=PLACEHOLDER_THUMBNAIL_URL,
        timestamp=now,
    )
