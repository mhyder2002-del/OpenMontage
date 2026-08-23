"""moneyprinter_turbo tool — mocked adapter."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "hermes-api"))

from tools.video.moneyprinter_turbo import MoneyPrinterTurbo


def test_status_and_generate_dry(monkeypatch):
    monkeypatch.delenv("MONEYPRINTER_ENABLED", raising=False)
    tool = MoneyPrinterTurbo()
    status = tool.execute({"action": "status"})
    assert status.success
    assert status.data["canonical_repo"].endswith("MoneyPrinterTurbo")
    dry = tool.dry_run({"topic": "hooks"})
    assert dry["label"] == "DRY-RUN"
    live = tool.execute({"action": "generate", "topic": "hooks"})
    assert live.success
    assert live.data["label"] == "DRY-RUN"
    assert live.artifacts


def test_generate_live_http(monkeypatch):
    import moneyprinter as mpt

    monkeypatch.setenv("MONEYPRINTER_ENABLED", "true")
    monkeypatch.setattr(mpt, "available", lambda: {"ok": True})
    monkeypatch.setattr(
        mpt,
        "generate_http",
        lambda topic, extras=None: {
            "ok": True,
            "mode": "live",
            "label": "live",
            "backend": "http",
            "task_id": "z",
            "video_paths": ["/tasks/z/final-1.mp4"],
            "canonical_repo": mpt.CANONICAL_REPO,
        },
    )
    result = MoneyPrinterTurbo().execute({"topic": "space"})
    assert result.data["mode"] == "live"
    assert result.artifacts == ["/tasks/z/final-1.mp4"]
