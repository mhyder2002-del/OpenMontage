"""Run one category: LM Studio chat or labeled DRY-RUN."""

from __future__ import annotations

import time
from typing import Any

from .catalog import CategorySpec
from .runtime import chat_complete
from .store import record_result


def system_prompt(spec: CategorySpec) -> str:
    return (
        f"You are the Hermes OS {spec.title} agent. "
        f"Goal: {spec.goal} "
        "Reply in 1-4 short sentences. No paid APIs. No secrets."
    )


def run_spec(spec: CategorySpec) -> dict[str, Any]:
    started = time.time()
    chat = chat_complete(system_prompt(spec), spec.user_prompt)
    elapsed_ms = int((time.time() - started) * 1000)
    if chat.get("ok") and chat.get("content"):
        summary = chat["content"]
        mode = "lm_studio"
        label = "LM-STUDIO"
    else:
        summary = spec.dry_run_summary
        mode = "dry_run"
        label = "DRY-RUN"
    result = {
        "id": spec.id,
        "title": spec.title,
        "goal": spec.goal,
        "summary": summary,
        "mode": mode,
        "label": label,
        "reason": chat.get("reason"),
        "model": chat.get("model"),
        "probe": chat.get("probe"),
        "latency_ms": elapsed_ms,
        "ok": True,
    }
    record_result(spec.id, result)
    return result
