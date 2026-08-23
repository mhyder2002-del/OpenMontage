"""MoneyPrinterTurbo Hermes adapter — mocked HTTP/CLI, no live MPT."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "services" / "hermes-api"
sys.path.insert(0, str(APP_DIR))

import moneyprinter as mpt  # noqa: E402


def test_dry_run_when_disabled(monkeypatch):
    monkeypatch.delenv("MONEYPRINTER_ENABLED", raising=False)
    result = mpt.generate("Everyday Carry")
    assert result["label"] == "DRY-RUN"
    assert result["mode"] == "dry_run"
    assert result["ok"] is True
    assert result["video_paths"]
    assert "harry0703/MoneyPrinterTurbo" in result["canonical_repo"]


def test_http_create_and_poll(monkeypatch):
    monkeypatch.setenv("MONEYPRINTER_ENABLED", "true")
    monkeypatch.setenv("MONEYPRINTER_BASE_URL", "http://mpt.test")
    monkeypatch.setenv("MONEYPRINTER_POLL_ATTEMPTS", "2")
    monkeypatch.setenv("MONEYPRINTER_POLL_SECONDS", "0")

    calls: list[tuple[str, str]] = []

    def fake_request(method, url, payload=None, timeout=None):
        calls.append((method, url))
        if method == "GET" and "/api/v1/tasks?" in url:
            return 200, {"data": {"tasks": [], "total": 0}}
        if method == "POST" and url.endswith("/api/v1/videos"):
            assert payload["video_subject"] == "Claude"
            return 200, {"data": {"task_id": "task-abc"}}
        if method == "GET" and url.endswith("/api/v1/tasks/task-abc"):
            return 200, {
                "data": {
                    "task_id": "task-abc",
                    "state": 1,
                    "videos": ["/tasks/task-abc/final-1.mp4"],
                }
            }
        raise AssertionError((method, url))

    monkeypatch.setattr(mpt, "_request", fake_request)
    result = mpt.generate("Claude")
    assert result["mode"] == "live"
    assert result["task_id"] == "task-abc"
    assert result["video_paths"] == ["/tasks/task-abc/final-1.mp4"]
    assert any(c[0] == "POST" for c in calls)


def test_http_failure_self_heals(monkeypatch):
    monkeypatch.setenv("MONEYPRINTER_ENABLED", "true")
    monkeypatch.setenv("MONEYPRINTER_BASE_URL", "http://mpt.test")

    def boom(*_a, **_k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(mpt, "available", lambda: {"ok": True})
    monkeypatch.setattr(mpt, "generate_http", boom)
    result = mpt.generate("AI education")
    assert result["label"] == "DRY-RUN"
    assert "connection refused" in result["reason"]


def test_cli_generate(monkeypatch, tmp_path):
    script = tmp_path / "cli.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setenv("MONEYPRINTER_ENABLED", "true")
    monkeypatch.setenv("MONEYPRINTER_MODE", "cli")
    monkeypatch.setenv("MONEYPRINTER_CLI", str(script))
    monkeypatch.setenv("MONEYPRINTER_WORKDIR", str(tmp_path))

    class Proc:
        returncode = 0
        stdout = "wrote /tmp/out/final-1.mp4\n"
        stderr = ""

    monkeypatch.setattr(mpt, "available", lambda: {"ok": True})
    monkeypatch.setattr(mpt.subprocess, "run", lambda *a, **k: Proc())
    result = mpt.generate_cli("topic")
    assert result["backend"] == "cli"
    assert result["video_paths"] == ["/tmp/out/final-1.mp4"]


def test_probe_http_uses_tasks(monkeypatch):
    monkeypatch.setenv("MONEYPRINTER_BASE_URL", "http://mpt.test")

    def fake_request(method, url, payload=None, timeout=None):
        assert method == "GET"
        assert "/api/v1/tasks" in url
        return 200, {"data": {"tasks": [], "total": 0}}

    monkeypatch.setattr(mpt, "_request", fake_request)
    assert mpt.probe_http()["ok"] is True


def test_apply_moneyprinter_records_cut_paths(monkeypatch, tmp_path):
    import campaigns as camp

    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(tmp_path / "c.json"))
    campaign = {
        "id": "c1",
        "niche": "EDC",
        "cuts": [{"id": "edc_1", "status": "planned"}],
    }

    def fake_generate(topic):
        return {
            "ok": True,
            "mode": "live",
            "label": "live",
            "task_id": "t1",
            "video_paths": ["/tasks/t1/final-1.mp4"],
        }

    monkeypatch.setattr("moneyprinter.generate", fake_generate)
    text = camp.apply_moneyprinter(campaign, force_dry=False)
    assert "t1" in text
    assert campaign["cuts"][0]["mpt_paths"] == ["/tasks/t1/final-1.mp4"]
    assert campaign["moneyprinter"]["task_id"] == "t1"


def test_request_json_roundtrip(monkeypatch):
    captured = {}

    class FakeResp:
        status = 200

        def read(self):
            return json.dumps({"ok": True}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["method"] = req.get_method()
        captured["data"] = req.data
        return FakeResp()

    monkeypatch.setattr(mpt, "urlopen", fake_urlopen)
    code, body = mpt._request("POST", "http://mpt.test/api/v1/videos", {"video_subject": "x"})
    assert code == 200
    assert body == {"ok": True}
    assert json.loads(captured["data"])["video_subject"] == "x"
