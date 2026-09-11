"""Resolve Hermes inference backends: LM Studio → OpenAI-compatible → Ollama.

Presence-only health fields never include secret values. Short-TTL probe cache
avoids hammering upstreams on every /health call.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_LM_STUDIO = "http://127.0.0.1:1234/v1"
DEFAULT_OPENAI = "https://api.openai.com/v1"
DEFAULT_OLLAMA = "http://127.0.0.1:11434/v1"
_CACHE: dict[str, Any] = {"key": None, "at": 0.0, "value": None}
_CACHE_TTL_S = 20.0


def _strip(url: str | None) -> str:
    return (url or "").strip().rstrip("/")


def openai_configured() -> bool:
    return bool((os.environ.get("OPENAI_API_KEY") or "").strip())


def ollama_configured() -> bool:
    return bool(_strip(os.environ.get("OLLAMA_BASE_URL")))


def openai_base() -> str:
    return _strip(os.environ.get("OPENAI_BASE_URL")) or DEFAULT_OPENAI


def openai_model() -> str:
    return (os.environ.get("OPENAI_MODEL") or os.environ.get("INFERENCE_MODEL") or "gpt-4o-mini").strip()


def ollama_base() -> str:
    return _strip(os.environ.get("OLLAMA_BASE_URL")) or DEFAULT_OLLAMA


def primary_base() -> str:
    return (
        _strip(os.environ.get("INFERENCE_BASE_URL"))
        or _strip(os.environ.get("LM_STUDIO_BASE_URL"))
        or DEFAULT_LM_STUDIO
    )


def primary_key() -> str:
    return (
        (os.environ.get("INFERENCE_API_KEY") or "").strip()
        or (os.environ.get("LM_STUDIO_API_KEY") or "").strip()
        or "lm-studio"
    )


def primary_backend_name() -> str:
    explicit = (os.environ.get("INFERENCE_BACKEND") or "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("INFERENCE_BASE_URL"):
        return "vllm"
    return "lm_studio"


def primary_model() -> str:
    return (
        (os.environ.get("INFERENCE_MODEL") or "").strip()
        or (os.environ.get("LM_STUDIO_MODEL") or "").strip()
        or "local-model"
    )


def _env_fingerprint() -> str:
    keys = [
        "INFERENCE_BASE_URL",
        "INFERENCE_API_KEY",
        "INFERENCE_BACKEND",
        "INFERENCE_MODEL",
        "LM_STUDIO_BASE_URL",
        "LM_STUDIO_API_KEY",
        "LM_STUDIO_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "OLLAMA_BASE_URL",
    ]
    return "|".join(f"{k}={os.environ.get(k) or ''}" for k in keys)


def probe_models(base_url: str, api_key: str, *, timeout: float = 2.0) -> dict[str, Any]:
    base = _strip(base_url)
    url = f"{base}/models"
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = int(getattr(resp, "status", 200))
            try:
                body: Any = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {"raw": raw}
    except HTTPError as exc:
        code = int(exc.code)
        body = {"error": exc.reason}
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "reachable": False,
            "status_code": 502,
            "models": [],
            "base_url": base,
            "error": str(getattr(exc, "reason", exc)),
        }
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
        "base_url": base,
        "error": None if code == 200 else (body.get("error") if isinstance(body, dict) else str(body)),
    }


def _candidate(backend: str, base: str, key: str, model: str) -> dict[str, str]:
    return {"backend": backend, "base_url": _strip(base), "api_key": key, "model": model}


def _candidates() -> list[dict[str, str]]:
    explicit = (os.environ.get("INFERENCE_BACKEND") or "").strip().lower()
    ordered: list[dict[str, str]] = []

    # Explicit OpenAI-compatible preference goes first when a key exists.
    if explicit in {"openai", "openai_compatible", "openrouter"} and openai_configured():
        ordered.append(
            _candidate(
                "openai" if explicit == "openai_compatible" else explicit,
                openai_base(),
                (os.environ.get("OPENAI_API_KEY") or "").strip(),
                openai_model(),
            )
        )

    primary = _candidate(primary_backend_name(), primary_base(), primary_key(), primary_model())
    if not any(c["base_url"] == primary["base_url"] and c["backend"] == primary["backend"] for c in ordered):
        ordered.append(primary)

    if openai_configured():
        oa = _candidate(
            "openai",
            openai_base(),
            (os.environ.get("OPENAI_API_KEY") or "").strip(),
            openai_model(),
        )
        if not any(c["base_url"] == oa["base_url"] for c in ordered):
            ordered.append(oa)

    if ollama_configured():
        ol = _candidate(
            "ollama",
            ollama_base(),
            (os.environ.get("OLLAMA_API_KEY") or "ollama").strip() or "ollama",
            (os.environ.get("OLLAMA_MODEL") or os.environ.get("INFERENCE_MODEL") or "llama3.2").strip(),
        )
        if not any(c["base_url"] == ol["base_url"] for c in ordered):
            ordered.append(ol)

    return ordered


def resolve_inference(*, probe: bool = True, force: bool = False, timeout: float = 2.0) -> dict[str, Any]:
    """Pick the first reachable OpenAI-compatible backend; else report clear failure."""
    fp = _env_fingerprint()
    now = time.monotonic()
    if (
        not force
        and probe
        and _CACHE["key"] == fp
        and _CACHE["value"] is not None
        and (now - float(_CACHE["at"])) < _CACHE_TTL_S
    ):
        return dict(_CACHE["value"])

    configured = {
        "lm_studio": True,
        "openai": openai_configured(),
        "ollama": ollama_configured(),
        "inference_base_url": bool(_strip(os.environ.get("INFERENCE_BASE_URL"))),
    }
    candidates = _candidates()
    attempts: list[dict[str, Any]] = []
    chosen: dict[str, Any] | None = None

    for cand in candidates:
        if not probe:
            chosen = {
                **cand,
                "reachable": None,
                "status_code": None,
                "models": [],
                "error": None,
                "reason": None,
            }
            break
        result = probe_models(cand["base_url"], cand["api_key"], timeout=timeout)
        attempts.append(
            {
                "backend": cand["backend"],
                "base_url": cand["base_url"],
                "reachable": result["reachable"],
                "status_code": result["status_code"],
                "error": result.get("error"),
            }
        )
        if result["reachable"]:
            chosen = {
                **cand,
                "reachable": True,
                "status_code": result["status_code"],
                "models": result["models"],
                "error": None,
                "reason": None,
            }
            break

    if chosen is None:
        # Prefer reporting primary endpoint details when nothing answered.
        primary = candidates[0]
        last = attempts[-1] if attempts else {}
        if not configured["openai"] and not configured["ollama"] and not configured["inference_base_url"]:
            reason = "llm_not_configured"
        elif attempts and not any(a.get("reachable") for a in attempts):
            reason = "all_unreachable"
        else:
            reason = "inference_unreachable"
        chosen = {
            **primary,
            "reachable": False,
            "status_code": last.get("status_code") or 502,
            "models": [],
            "error": last.get("error") or reason,
            "reason": reason,
        }

    out = {
        "backend": chosen["backend"],
        "base_url": chosen["base_url"],
        "api_key": chosen["api_key"],
        "model": chosen["model"],
        "reachable": chosen.get("reachable"),
        "status_code": chosen.get("status_code"),
        "models": chosen.get("models") or [],
        "error": chosen.get("error"),
        "reason": chosen.get("reason"),
        "configured": configured,
        "attempts": attempts,
    }
    if probe:
        _CACHE["key"] = fp
        _CACHE["at"] = now
        # Cache without api_key duplication risk in shared refs — store copy sans mutating later.
        cached = dict(out)
        _CACHE["value"] = cached
    return out


def clear_cache() -> None:
    _CACHE["key"] = None
    _CACHE["at"] = 0.0
    _CACHE["value"] = None
