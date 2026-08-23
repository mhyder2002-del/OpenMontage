"""moneyprinter_turbo tool — mocked adapter."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "hermes-api"))

from tools.video.moneyprinter_turbo import MoneyPrinterTurbo
from tools.tool_registry import ToolRegistry
from lib.pipeline_loader import load_pipeline


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


def test_capability_and_not_selector_routable():
    tool = MoneyPrinterTurbo()
    assert tool.capability == "video_generation"
    assert tool.selector_routable is False
    assert tool.name == "moneyprinter_turbo"


def test_registry_discovers_moneyprinter_turbo():
    from tools.video import moneyprinter_turbo as mod

    reg = ToolRegistry()
    names = reg.register_module(mod)
    assert "moneyprinter_turbo" in names
    found = reg.get("moneyprinter_turbo")
    assert found is not None
    assert found.capability == "video_generation"
    assert found.selector_routable is False


def test_selector_excludes_moneyprinter():
    from tools.video.video_selector import VideoSelector

    class _ClipProvider:
        name = "stub_t2v"
        capability = "video_generation"
        selector_routable = True

    sel = VideoSelector()
    candidates = [MoneyPrinterTurbo(), _ClipProvider()]
    routed = [
        t
        for t in candidates
        if t.name != sel.name and getattr(t, "selector_routable", True)
    ]
    assert [t.name for t in routed] == ["stub_t2v"]


def test_pipeline_manifests_list_optional_mpt():
    fly = load_pipeline("hermes-flywheel")
    render = next(s for s in fly["stages"] if s["name"] == "render")
    assert "moneyprinter_turbo" in render["optional_tools"]
    full = next(ss for ss in render["sub_stages"] if ss["name"] == "full-render")
    assert "moneyprinter_turbo" in full["tools_available"]
    assert "video_selector" in full["tools_available"]

    host = load_pipeline("hermes-hostinger")
    pre = next(s for s in host["stages"] if s["name"] == "preflight")
    backend = next(s for s in host["stages"] if s["name"] == "backend")
    assert "moneyprinter_turbo" in pre["optional_tools"]
    assert "moneyprinter_turbo" in backend["optional_tools"]

    clips = load_pipeline("clip-factory")
    compose = next(s for s in clips["stages"] if s["name"] == "compose")
    assert "moneyprinter_turbo" in compose["optional_tools"]
    expl = load_pipeline("animated-explainer")
    assets = next(s for s in expl["stages"] if s["name"] == "assets")
    assert "moneyprinter_turbo" in assets["optional_tools"]
    assert "moneyprinter_turbo" not in (assets.get("required_tools") or [])
