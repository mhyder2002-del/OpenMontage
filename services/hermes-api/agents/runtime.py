"""LM Studio / OpenAI-compatible probe + chat. Never hangs: labeled DRY-RUN."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from inference_resolve import resolve_inference

DEFAULT_BASE = "http://127.0.0.1:1234/v1"


def inference_base() -> str:
    return str(resolve_inference(probe=True)["base_url"]).rstrip("/")


def inference_key() -> str:
    return str(resolve_inference(probe=True)["api_key"])


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
    active = resolve_inference(probe=True, timeout=min(2.0, infer_timeout()))
    return {
        "reachable": bool(active.get("reachable")),
        "status_code": active.get("status_code") or 502,
        "models": list(active.get("models") or []),
        "base_url": active.get("base_url"),
        "backend": active.get("backend"),
        "reason": active.get("reason"),
        "configured": active.get("configured") or {},
        "error": None if active.get("reachable") else (active.get("error") or active.get("reason")),
    }


def chat_complete(system_prompt: str, user_prompt: str, model: str | None = None) -> dict[str, Any]:
    probe = probe_models()
    if not probe["reachable"]:
        reason = probe.get("reason") or "lm_studio_unreachable"
        return {
            "ok": False,
            "mode": "dry_run",
            "label": "DRY-RUN",
            "reason": reason,
            "probe": probe,
            "content": None,
        }
    backend = str(probe.get("backend") or "lm_studio")
    chosen = model or (
        probe["models"][0]
        if probe["models"]
        else resolve_inference(probe=False).get("model")
        or "local-model"
    )
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
    mode = backend if backend in {"lm_studio", "vllm", "openai", "ollama", "openrouter"} else "lm_studio"
    label = {
        "lm_studio": "LM-STUDIO",
        "vllm": "VLLM",
        "openai": "OPENAI",
        "ollama": "OLLAMA",
        "openrouter": "OPENROUTER",
    }.get(mode, mode.upper())
    return {
        "ok": True,
        "mode": mode,
        "label": label,
        "reason": None,
        "probe": probe,
        "model": chosen,
        "status_code": code,
        "content": str(content).strip(),
    }
