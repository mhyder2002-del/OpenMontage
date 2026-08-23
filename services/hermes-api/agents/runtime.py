"""LM Studio / OpenAI-compatible probe + chat. Never hangs: labeled DRY-RUN."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE = "http://127.0.0.1:1234/v1"


def inference_base() -> str:
    return (
        os.environ.get("INFERENCE_BASE_URL")
        or os.environ.get("LM_STUDIO_BASE_URL")
        or DEFAULT_BASE
    ).rstrip("/")


def inference_key() -> str:
    return (
        os.environ.get("INFERENCE_API_KEY")
        or os.environ.get("LM_STUDIO_API_KEY")
        or "lm-studio"
    )


def infer_timeout() -> float:
    raw = os.environ.get("HERMES_AGENT_INFER_TIMEOUT") or "4"
    try:
        return max(0.2, float(raw))
    except ValueError:
        return 4.0


def _request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: float | None = None) -> tuple[int, Any]:
    url = f"{inference_base()}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {inference_key()}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urlopen(req, timeout=timeout or infer_timeout()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                body: Any = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {"raw": raw}
            return int(getattr(resp, "status", 200)), body
    except HTTPError as exc:
        return int(exc.code), {"error": exc.reason}
    except (URLError, TimeoutError, OSError) as exc:
        return 502, {"error": str(getattr(exc, "reason", exc))}


def probe_models() -> dict[str, Any]:
    code, body = _request("GET", "/models", timeout=min(2.0, infer_timeout()))
    models: list[str] = []
    if isinstance(body, dict):
        models = [
            item.get("id")
            for item in (body.get("data") or [])
            if isinstance(item, dict) and item.get("id")
        ]
    return {
        "reachable": code == 200,
        "status_code": code,
        "models": models,
        "base_url": inference_base(),
        "error": None if code == 200 else (body.get("error") if isinstance(body, dict) else str(body)),
    }


def chat_complete(system_prompt: str, user_prompt: str, model: str | None = None) -> dict[str, Any]:
    probe = probe_models()
    if not probe["reachable"]:
        return {
            "ok": False,
            "mode": "dry_run",
            "label": "DRY-RUN",
            "reason": "lm_studio_unreachable",
            "probe": probe,
            "content": None,
        }
    chosen = model or (probe["models"][0] if probe["models"] else os.environ.get("INFERENCE_MODEL") or "local-model")
    payload = {
        "model": chosen,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 220,
        "temperature": 0.3,
    }
    code, body = _request("POST", "/chat/completions", payload=payload)
    content = None
    if isinstance(body, dict):
        choices = body.get("choices") or []
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message") or {}
            content = msg.get("content")
    if code != 200 or not content:
        return {
            "ok": False,
            "mode": "dry_run",
            "label": "DRY-RUN",
            "reason": "chat_failed",
            "probe": probe,
            "model": chosen,
            "status_code": code,
            "content": None,
        }
    return {
        "ok": True,
        "mode": "lm_studio",
        "label": "LM-STUDIO",
        "reason": None,
        "probe": probe,
        "model": chosen,
        "status_code": code,
        "content": str(content).strip(),
    }
