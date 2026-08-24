#!/usr/bin/env python3
"""HTTP-code health tick for the Grok site-health loop. Never logs secrets."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "grok-health-loop.jsonl"
PATHS = ("/livez", "/readyz", "/health", "/console", "/api/flywheel")
BASES = (
    "https://hermestudios.com",
    "https://www.hermestudios.com",
    "http://127.0.0.1:8091",
)
SECRET_SUBSTR = ("key", "token", "secret", "authorization", "password")


def _safe_json(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    for k in list(data):
        if any(s in str(k).lower() for s in SECRET_SUBSTR):
            data[k] = "<redacted>"
    return data


def probe(base: str, path: str) -> dict:
    url = base + path
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(8192)
            parsed = _safe_json(body)
            return {
                "code": int(resp.status),
                "origin": parsed.get("origin"),
                "ok": parsed.get("ok"),
                "running": parsed.get("running"),
            }
    except urllib.error.HTTPError as exc:
        return {"code": int(exc.code)}
    except Exception as exc:
        return {"code": 0, "error": type(exc).__name__}


def main() -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": "grok-site-health",
        "results": {base: {p: probe(base, p) for p in PATHS} for base in BASES},
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    slim = {
        base: {p: v.get("code") for p, v in paths.items()}
        for base, paths in row["results"].items()
    }
    origins = {
        base: (paths.get("/api/flywheel") or {}).get("origin")
        or (paths.get("/health") or {}).get("origin")
        for base, paths in row["results"].items()
    }
    print(json.dumps({"codes": slim, "origins": origins}, indent=2))


if __name__ == "__main__":
    main()
