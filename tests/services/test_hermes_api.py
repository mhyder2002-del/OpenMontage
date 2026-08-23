"""Tests for the Hermes API FastAPI app."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
APP_DIR = PROJECT_ROOT / "services" / "hermes-api"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(APP_DIR))

APP_PATH = APP_DIR / "app.py"


def _load_app():
    spec = importlib.util.spec_from_file_location("hermes_api_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def client(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PUBLIC_DOMAIN", "localhost")
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("INFERENCE_BACKEND", "lm_studio")
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(tmp_path / "campaigns.json"))
    monkeypatch.setenv("HERMES_FLYWHEEL_STORE", str(tmp_path / "flywheel.json"))
    monkeypatch.setenv("HERMES_CAMPAIGN_RETRY_SECONDS", "0")
    monkeypatch.setenv("HERMES_CAMPAIGN_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("HERMES_FLYWHEEL_SLEEP_SECONDS", "0")
    monkeypatch.setenv("HERMES_AGENTS_STORE", str(tmp_path / "agents.json"))
    monkeypatch.setenv("HERMES_AGENT_INFER_TIMEOUT", "0.4")
    monkeypatch.setenv("HERMES_AGENT_CONCURRENCY", "3")
    monkeypatch.delenv("LM_STUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("HERMES_MAX_INFLIGHT", raising=False)
    module = _load_app()
    return TestClient(module.app), module


def test_health_and_landing(client):
    http, _ = client
    livez = http.get("/livez")
    assert livez.status_code == 200
    assert livez.json()["ok"] is True
    readyz = http.get("/readyz")
    assert readyz.status_code == 200
    health = http.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["service"] == "hermes-api"
    landing = http.get("/")
    assert landing.status_code == 200
    assert b"Hermes" in landing.content
    assert b"html" in landing.content.lower()
    assert "inference" in body
    assert body["inference"]["backend"] == "lm_studio"
    assert body["inference"]["max_inflight"] == 32
    assert body["flywheel"]["origin"] == "http://127.0.0.1:8091"
    assert body["agents"]["count"] == 14


def test_unauthenticated_chat_rejected_when_key_set(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PUBLIC_DOMAIN", "hermestudios.com")
    monkeypatch.setenv("HERMES_API_KEY", "secret-test-key")
    module = _load_app()
    http = TestClient(module.app)
    res = http.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert res.status_code == 401


def test_missing_production_key_refuses_inference(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PUBLIC_DOMAIN", "hermestudios.com")
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    module = _load_app()
    http = TestClient(module.app)
    res = http.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert res.status_code == 503
    livez = http.get("/livez")
    assert livez.status_code == 200
    readyz = http.get("/readyz")
    assert readyz.status_code == 503


def test_inference_base_url_preferred(monkeypatch):
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://vllm.internal:8000/v1")
    monkeypatch.setenv("INFERENCE_BACKEND", "vllm")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    module = _load_app()
    assert module._inference_base() == "http://vllm.internal:8000/v1"
    assert module._inference_backend() == "vllm"
    assert module._lm_base() == "http://vllm.internal:8000/v1"


def test_console_and_status(client):
    http, module = client
    console = http.get("/console")
    assert console.status_code == 200
    assert b"html" in console.content.lower()
    status = http.get("/api/status")
    assert status.status_code == 200
    body = status.json()
    assert body["health"] == "/health"
    assert body["agents"] == "/api/agents"
    assert "v1" in body["openai_base_url"]
    assert module._public_domain() == "localhost"


def test_v1_degraded_when_inference_down(client):
    http, _ = client
    chat = http.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert chat.status_code == 502
    err = chat.json()["error"]
    assert err["type"] == "inference_unavailable"
    assert "1234" in err["hint"] or "INFERENCE_BASE_URL" in err["hint"]
    embeds = http.post("/v1/embeddings", json={"input": "hello"})
    assert embeds.status_code == 502
    models = http.get("/v1/models")
    assert models.status_code == 502
    health = http.get("/health")
    assert health.status_code == 200
    assert health.json()["inference"]["reachable"] is False


def test_stream_degraded_when_inference_down(client):
    http, _ = client
    res = http.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert res.status_code == 502
    assert res.json()["error"]["type"] == "inference_unavailable"


def test_campaign_create_launch_self_heals_when_inference_down(client, tmp_path, monkeypatch):
    http, module = client
    store = tmp_path / "campaigns.json"
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(store))
    monkeypatch.setenv("HERMES_CAMPAIGN_RETRY_SECONDS", "0")
    monkeypatch.setenv("HERMES_CAMPAIGN_MAX_ATTEMPTS", "2")
    created = http.post(
        "/api/campaigns",
        json={"niche": "AI education", "goal": "Grow subscribers", "launch": True},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["id"]
    assert body["status"] in {"running", "completed_healed", "completed"}
    campaign_id = body["id"]
    polled = None
    for _ in range(80):
        polled = http.get(f"/api/campaigns/{campaign_id}").json()
        if polled["status"] in {"completed", "completed_healed", "failed"}:
            break
    assert polled is not None
    assert polled["status"] == "completed_healed"
    assert polled["healed"] is True
    assert polled["mode"] == "dry_run"
    types = [ev.get("type") for ev in polled["events"]]
    assert "orchestra_started" in types
    assert "self_heal" in types
    assert "orchestra_completed" in types
    assert any(ev.get("label") == "DRY-RUN" for ev in polled["events"])
    events = http.get(f"/api/campaigns/{campaign_id}/events")
    assert events.status_code == 200
    assert len(events.json()["events"]) >= 6
    listed = http.get("/api/campaigns").json()["campaigns"]
    assert any(item["id"] == campaign_id for item in listed)


def test_campaign_live_inference_completes_without_heal(client, tmp_path, monkeypatch):
    http, module = client
    store = tmp_path / "live.json"
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(store))

    def fake_upstream(method, path, payload=None, timeout=12):
        return 200, {"choices": [{"message": {"content": "Live hook for the niche."}}]}

    monkeypatch.setattr(module, "_upstream", fake_upstream)
    import campaigns as camp

    monkeypatch.setattr(
        camp,
        "rank_video_tools",
        lambda prompt: {"top_tool": "video_selector", "ranked": 2, "live_generate": False},
    )
    monkeypatch.setattr(
        camp,
        "compose_runtime_plan",
        lambda: {"render_engines": {"ffmpeg": True}, "live_render": False},
    )
    created = http.post("/api/campaigns", json={"niche": "Claude", "launch": True})
    campaign_id = created.json()["id"]
    polled = None
    for _ in range(40):
        polled = http.get(f"/api/campaigns/{campaign_id}").json()
        if polled["status"] in {"completed", "completed_healed", "failed"}:
            break
    assert polled["status"] == "completed"
    assert polled["healed"] is False
    assert any(ev.get("type") == "stage_inferred" for ev in polled["events"])
    assert polled.get("agent") == "video-campaign"
    assert len(polled.get("cuts") or []) == 3
    types = [ev.get("type") for ev in polled["events"]]
    assert "cuts_planned" in types
    assert "video_ranked" in types or "stage_simulated" in types
    assert "compose_planned" in types or "self_heal" in types
    routing = polled.get("routing") or {}
    assert routing.get("live_generate") is False


def test_video_campaign_dry_run_cuts_after_heal(client):
    http, _ = client
    created = http.post(
        "/api/campaigns",
        json={
            "niche": "Everyday Carry",
            "goal": "Grow subscribers",
            "brief": "7-scene EDC short",
            "launch": True,
        },
    )
    campaign_id = created.json()["id"]
    polled = None
    for _ in range(50):
        polled = http.get(f"/api/campaigns/{campaign_id}").json()
        if polled["status"] in {"completed", "completed_healed", "failed"}:
            break
    assert polled["status"] == "completed_healed"
    cuts = polled["cuts"]
    assert len(cuts) == 3
    assert all(cut.get("label") == "DRY-RUN" for cut in cuts)
    assert any("edc" in cut["slug"] or "everyday" in cut["slug"] for cut in cuts)
    events = http.get(f"/api/campaigns/{campaign_id}/events").json()
    assert events["agent"] == "video-campaign"
    assert len(events["cuts"]) == 3


def test_cors_allows_localhost_console(client):
    http, _ = client
    res = http.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code in {200, 204}
    assert res.headers.get("access-control-allow-origin")


def test_flywheel_tick_continues_after_healed_campaign(client):
    http, module = client
    import asyncio
    import flywheel as fw

    probes = module._collect_flywheel_probes()
    assert [p["path"] for p in probes] == list(fw.SELF_CHECK_PATHS)
    assert any(p["path"] == "/health" and p.get("inference_down") for p in probes)

    fw.request_start()

    async def two_ticks():
        first = await fw.run_one_tick(
            infer=module.bind_infer_from_app(module._upstream),
            run_orchestra=module.run_orchestra,
            probes=module._collect_flywheel_probes(),
        )
        second = await fw.run_one_tick(
            infer=module.bind_infer_from_app(module._upstream),
            run_orchestra=module.run_orchestra,
            probes=module._collect_flywheel_probes(),
        )
        return first, second

    first, second = asyncio.run(two_ticks())
    assert first["skipped"] is False
    assert second["skipped"] is False
    assert first["tick"]["status"] == "completed_healed"
    assert second["tick"]["status"] == "completed_healed"
    assert second["cycle_count"] >= 2
    listed = http.get("/api/campaigns").json()["campaigns"]
    healed = [c for c in listed if c["status"] == "completed_healed"]
    assert len(healed) >= 2
    snap = http.get("/api/flywheel").json()
    assert snap["cycle_count"] >= 2
    assert snap["origin"] == "http://127.0.0.1:8091"


def test_flywheel_stop_flag(client):
    http, module = client
    import asyncio
    import flywheel as fw

    fw.request_start()
    asyncio.run(
        fw.run_one_tick(
            infer=module.bind_infer_from_app(module._upstream),
            run_orchestra=module.run_orchestra,
            probes=module._collect_flywheel_probes(),
        )
    )
    stopped = http.post("/api/flywheel/stop").json()
    assert stopped["stop_requested"] is True
    assert stopped["running"] is False
    via_get = http.get("/api/flywheel/stop").json()
    assert via_get["stop_requested"] is True
    skipped = asyncio.run(
        fw.run_one_tick(
            infer=module.bind_infer_from_app(module._upstream),
            run_orchestra=module.run_orchestra,
            probes=module._collect_flywheel_probes(),
        )
    )
    assert skipped["skipped"] is True
    assert skipped["reason"] == "stop_requested"


def test_flywheel_http_start_returns_ok(client):
    http, _ = client
    started = http.post("/api/flywheel/start")
    assert started.status_code == 200
    body = started.json()
    assert body["origin"] == "http://127.0.0.1:8091"
    http.post("/api/flywheel/stop")


def test_category_agents_tick_dry_run_when_lm_studio_down(client):
    http, _ = client
    listed = http.get("/api/agents")
    assert listed.status_code == 200
    assert listed.json()["count"] == 14
    ticked = http.post("/api/agents/tick")
    assert ticked.status_code == 200
    body = ticked.json()
    assert body["ok"] is True
    assert len(body["results"]) == 14
    assert body["tick"]["lm_studio_used"] is False
    ids = {row["id"] for row in body["results"]}
    assert ids == {
        "overview",
        "discovery",
        "knowledge",
        "campaigns",
        "orchestra",
        "debugger",
        "studio",
        "evolution",
        "analytics",
        "memory",
        "command",
        "publishing",
        "uploads",
        "settings",
    }
    for row in body["results"]:
        assert row["label"] == "DRY-RUN"
        assert row["mode"] == "dry_run"
        assert row["summary"]
    snap = http.get("/api/agents").json()
    assert len(snap["categories"]) == 14
    assert all(c.get("label") == "DRY-RUN" for c in snap["categories"])
    studio = http.get("/api/agents/studio")
    assert studio.status_code == 200
    assert studio.json()["result"] is not None
    assert studio.json()["result"]["label"] == "DRY-RUN"
    assert studio.json()["events"]
    missing = http.get("/api/agents/not-a-nav")
    assert missing.status_code == 404


def test_flywheel_tick_records_category_agents(client):
    http, module = client
    import asyncio
    import flywheel as fw

    fw.request_start()

    async def once():
        return await fw.run_one_tick(
            infer=module.bind_infer_from_app(module._upstream),
            run_orchestra=module.run_orchestra,
            probes=module._collect_flywheel_probes(),
        )

    result = asyncio.run(once())
    assert result["skipped"] is False
    agents = result.get("agents") or {}
    assert agents.get("ok") is True
    assert len(agents.get("results") or []) == 14
    snap = http.get("/api/agents").json()
    assert snap["tick_count"] >= 1
    assert all((c.get("label") or c.get("mode")) for c in snap["categories"])


def test_console_pages_bind_every_category_agent():
    os_js = (APP_DIR / "static" / "os.js").read_text(encoding="utf-8")
    app_js = (APP_DIR / "static" / "app.js").read_text(encoding="utf-8")
    ids = [
        "overview",
        "discovery",
        "knowledge",
        "campaigns",
        "orchestra",
        "debugger",
        "studio",
        "evolution",
        "analytics",
        "memory",
        "command",
        "publishing",
        "uploads",
        "settings",
    ]
    for category in ids:
        assert f"/api/agents/{category}" in os_js
        assert f"/api/agents/{category}" in app_js
    dockerfile = (APP_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "flywheel.py" in dockerfile
    assert "COPY agents ./agents" in dockerfile
    compose = (APP_DIR / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${HERMES_HOST_PORT:-8091}:8080" in compose
    assert "HERMES_FLYWHEEL_AUTO" in compose
    assert "HERMES_AGENTS_STORE" in compose
