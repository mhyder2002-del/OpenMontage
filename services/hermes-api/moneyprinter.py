"""Hermes adapter for MoneyPrinterTurbo (HTTP or CLI). Never copies the MPT tree."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Canonical upstream: https://github.com/harry0703/MoneyPrinterTurbo (MIT).
CANONICAL_REPO = "https://github.com/harry0703/MoneyPrinterTurbo"
DEFAULT_BASE = "http://127.0.0.1:8088"
DEFAULT_CREATE_PATH = "/api/v1/videos"
DEFAULT_TASK_PATH = "/api/v1/tasks"


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def enabled() -> bool:
    """Opt-in live MPT. Unset → campaign records a labeled DRY-RUN for this stage only."""
    return _truthy("MONEYPRINTER_ENABLED")


def base_url() -> str:
    return (os.environ.get("MONEYPRINTER_BASE_URL") or DEFAULT_BASE).rstrip("/")


def api_key() -> str:
    return (os.environ.get("MONEYPRINTER_API_KEY") or "").strip()


def mode() -> str:
    raw = (os.environ.get("MONEYPRINTER_MODE") or "http").strip().lower()
    return raw if raw in {"http", "cli"} else "http"


def timeout_seconds() -> float:
    raw = os.environ.get("MONEYPRINTER_TIMEOUT_SECONDS") or "12"
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 12.0


def poll_seconds() -> float:
    raw = os.environ.get("MONEYPRINTER_POLL_SECONDS") or "0.5"
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.5


def poll_attempts() -> int:
    raw = os.environ.get("MONEYPRINTER_POLL_ATTEMPTS") or "4"
    try:
        return max(1, int(raw))
    except ValueError:
        return 4


def cli_path() -> Path | None:
    raw = (os.environ.get("MONEYPRINTER_CLI") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_file() else None


def workdir() -> Path | None:
    raw = (os.environ.get("MONEYPRINTER_WORKDIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    cli = cli_path()
    return cli.parent if cli else None


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = api_key()
    if key:
        headers["x-api-key"] = key
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _request(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
) -> tuple[int, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=_headers(), method=method)
    try:
        with urlopen(req, timeout=timeout or timeout_seconds()) as resp:
            raw = resp.read().decode("utf-8")
            body: Any = json.loads(raw) if raw else {}
            return int(resp.status), body
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {"error": str(exc)}
        except json.JSONDecodeError:
            body = {"error": raw or str(exc)}
        return int(exc.code), body
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(str(exc)) from exc


def probe_http() -> dict[str, Any]:
    url = f"{base_url()}{DEFAULT_TASK_PATH}?page=1&page_size=1"
    try:
        code, body = _request("GET", url)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)[:300], "url": url}
    ok = code == 200
    return {"ok": ok, "status": code, "url": url, "body": body if ok else body}


def probe_cli() -> dict[str, Any]:
    path = cli_path()
    if path is None:
        return {"ok": False, "error": "MONEYPRINTER_CLI is not a file"}
    python = shutil.which("python3") or shutil.which("python") or "python3"
    try:
        proc = subprocess.run(
            [python, str(path), "--help"],
            cwd=str(workdir() or path.parent),
            capture_output=True,
            text=True,
            timeout=timeout_seconds(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)[:300], "cli": str(path)}
    ok = proc.returncode == 0
    return {
        "ok": ok,
        "cli": str(path),
        "returncode": proc.returncode,
        "error": None if ok else (proc.stderr or proc.stdout or "cli --help failed")[:300],
    }


def available() -> dict[str, Any]:
    if mode() == "cli":
        return {**probe_cli(), "mode": "cli"}
    return {**probe_http(), "mode": "http"}


def _create_payload(topic: str, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "video_subject": topic,
        "video_aspect": "9:16",
        "video_language": (os.environ.get("MONEYPRINTER_LANGUAGE") or "en-US").strip(),
        "video_count": 1,
        "subtitle_enabled": True,
    }
    if extras:
        body.update(extras)
    return body


def create_http_task(topic: str, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{base_url()}{DEFAULT_CREATE_PATH}"
    code, body = _request("POST", url, _create_payload(topic, extras))
    if code != 200:
        raise RuntimeError(f"MPT HTTP {code}: {body}")
    data = body.get("data") if isinstance(body, dict) else None
    task_id = ""
    if isinstance(data, dict):
        task_id = str(data.get("task_id") or "")
    if not task_id:
        raise RuntimeError(f"MPT create missing task_id: {body}")
    return {"task_id": task_id, "raw": body}


def get_http_task(task_id: str) -> dict[str, Any]:
    url = f"{base_url()}{DEFAULT_TASK_PATH}/{task_id}"
    code, body = _request("GET", url)
    if code != 200:
        raise RuntimeError(f"MPT task HTTP {code}: {body}")
    data = body.get("data") if isinstance(body, dict) else body
    if not isinstance(data, dict):
        raise RuntimeError("MPT task body is not an object")
    return data


def _extract_paths(task: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("videos", "combined_videos"):
        items = task.get(key) or []
        if isinstance(items, list):
            paths.extend(str(item) for item in items if item)
    return paths


def poll_http_task(task_id: str) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(poll_attempts()):
        last = get_http_task(task_id)
        state = last.get("state")
        paths = _extract_paths(last)
        # Upstream: state 1 = success in TaskQueryResponse examples.
        if paths or state in {1, "1", "complete", "completed", "success"}:
            return last
        if state in {-1, "-1", "failed", "error"}:
            raise RuntimeError(str(last.get("error") or last.get("failed_stage") or last))
        time.sleep(poll_seconds())
    raise RuntimeError(f"MPT task {task_id} not ready after {poll_attempts()} polls")


def generate_http(topic: str, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    created = create_http_task(topic, extras)
    task = poll_http_task(created["task_id"])
    paths = _extract_paths(task)
    return {
        "ok": True,
        "mode": "live",
        "label": "live",
        "backend": "http",
        "task_id": created["task_id"],
        "video_paths": paths,
        "task": task,
        "canonical_repo": CANONICAL_REPO,
    }


def generate_cli(topic: str) -> dict[str, Any]:
    path = cli_path()
    if path is None:
        raise RuntimeError("MONEYPRINTER_CLI is not set to an existing file")
    python = shutil.which("python3") or shutil.which("python") or "python3"
    cmd = [python, str(path), "--video-subject", topic]
    proc = subprocess.run(
        cmd,
        cwd=str(workdir() or path.parent),
        capture_output=True,
        text=True,
        timeout=timeout_seconds(),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"exit {proc.returncode}")[:400])
    guessed: list[str] = []
    for ln in (proc.stdout or "").splitlines():
        for token in ln.replace(",", " ").split():
            if token.endswith(".mp4") or "/tasks/" in token:
                guessed.append(token)
    return {
        "ok": True,
        "mode": "live",
        "label": "live",
        "backend": "cli",
        "task_id": None,
        "video_paths": guessed,
        "stdout": (proc.stdout or "")[:800],
        "canonical_repo": CANONICAL_REPO,
    }


def dry_run_result(topic: str, reason: str) -> dict[str, Any]:
    slug = "".join(ch if ch.isalnum() else "_" for ch in topic.lower())[:24] or "topic"
    return {
        "ok": True,
        "mode": "dry_run",
        "label": "DRY-RUN",
        "backend": "none",
        "task_id": None,
        "video_paths": [f"[DRY-RUN] moneyprinter/{slug}/final-1.mp4"],
        "reason": reason[:400],
        "canonical_repo": CANONICAL_REPO,
        "install": (
            "Clone https://github.com/harry0703/MoneyPrinterTurbo or "
            "COMPOSE_PROFILES=moneyprinter docker compose up -d moneyprinter"
        ),
    }


def generate(topic: str, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    """Live MPT when enabled and reachable; otherwise labeled DRY-RUN (no raise)."""
    subject = (topic or "").strip() or "AI education short"
    if not enabled():
        return dry_run_result(subject, "MONEYPRINTER_ENABLED is off — optional MPT skipped.")
    try:
        probe = available()
        if not probe.get("ok"):
            return dry_run_result(subject, str(probe.get("error") or "MPT probe failed"))
        if mode() == "cli":
            return generate_cli(subject)
        return generate_http(subject, extras)
    except Exception as exc:  # self-heal — never hang the orchestra
        return dry_run_result(subject, str(exc))
