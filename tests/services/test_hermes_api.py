"""Tests for the Hermes API FastAPI app."""

from __future__ import annotations

import importlib.util
import sys
import json
import time
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
    monkeypatch.setenv("HERMES_DB_PATH", str(tmp_path / "hermes.db"))
    monkeypatch.setenv("HERMES_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("HERMES_RESEARCH_TIMEOUT", "0.4")
    monkeypatch.setenv("HERMES_FLYWHEEL_STORE", str(tmp_path / "flywheel.json"))
    monkeypatch.setenv("HERMES_CAMPAIGN_RETRY_SECONDS", "0")
    monkeypatch.setenv("HERMES_CAMPAIGN_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("HERMES_FLYWHEEL_SLEEP_SECONDS", "0")
    monkeypatch.setenv("HERMES_AGENTS_STORE", str(tmp_path / "agents.json"))
    monkeypatch.setenv("HERMES_AGENT_INFER_TIMEOUT", "0.4")
    monkeypatch.setenv("HERMES_AGENT_CONCURRENCY", "3")
    monkeypatch.delenv("LM_STUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("HERMES_MAX_INFLIGHT", raising=False)
    import db as hermes_db

    hermes_db.reset_migrate_flag()
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
    assert body["research"] == "/api/agent/research"
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
    listed_body = http.get("/api/campaigns").json()
    assert listed_body["engine"]["pipeline"] == "hermes-flywheel"
    assert listed_body["engine"]["live_compose"] is False
    assert listed_body["engine"]["inference_down"] is True
    assert polled["label"] == "DRY-RUN"
    assert polled["pipeline"] == "hermes-flywheel"
    assert polled["live_compose"] is False
    assert polled["publish"]["label"] == "DRY-RUN"
    assert polled["publish"]["binary_upload"] is False


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
    assert polled["label"] == "live"
    assert polled["pipeline"] == "hermes-flywheel"
    assert polled["live_compose"] is False
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
    mpt = polled.get("moneyprinter") or {}
    assert mpt.get("label") == "DRY-RUN"
    assert mpt.get("video_paths")
    assert any(ev.get("type") == "moneyprinter_completed" or ev.get("stage") == "mpt" for ev in polled["events"])
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
    assert snap["inference_down"] is True
    assert snap["healed"] is True
    assert snap["label"] == "DRY-RUN"
    assert snap["pipeline"] == "hermes-flywheel"
    assert snap["live_compose"] is False
    assert snap["last_tick"]["label"] == "DRY-RUN"
    assert snap["last_tick"]["healed"] is True
    health = http.get("/health").json()
    assert health["flywheel"]["inference_down"] is True
    assert health["flywheel"]["label"] == "DRY-RUN"


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
    assert body["running"] is True
    assert body["operator"]["launch"] == "POST /api/campaigns"
    http.post("/api/flywheel/stop")


def test_campaign_launch_endpoint_auth_and_dry_run_labels(client):
    http, _ = client
    queued = http.post(
        "/api/campaigns",
        json={"niche": "Launch endpoint", "goal": "Grow", "launch": False},
    )
    assert queued.status_code == 200
    cid = queued.json()["id"]
    assert queued.json()["status"] == "queued"
    launched = http.post(f"/api/campaigns/{cid}/launch")
    assert launched.status_code == 200
    assert launched.json()["status"] in {"running", "completed_healed", "completed"}
    polled = None
    for _ in range(80):
        polled = http.get(f"/api/campaigns/{cid}").json()
        if polled["status"] in {"completed", "completed_healed", "failed"}:
            break
    assert polled["status"] == "completed_healed"
    assert polled["label"] == "DRY-RUN"
    assert polled["healed"] is True
    events = http.get(f"/api/campaigns/{cid}/events").json()
    assert events["label"] == "DRY-RUN"
    assert events["pipeline"] == "hermes-flywheel"
    assert events["publish"]["label"] == "DRY-RUN"


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
        if row["id"] == "publishing":
            assert "MoneyPrinter" in (row.get("moneyprinter") or row["summary"] or "")
        if row["id"] == "command":
            assert row.get("probes", {}).get("readyz") == "/readyz"
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
    assert "db.py" in dockerfile
    assert "research.py" in dockerfile
    assert "walking_skeleton.py" in dockerfile
    assert "product.py" in dockerfile
    assert "scrapers.py" in dockerfile
    assert "/api/orchestra/pipeline" in os_js
    assert "/api/orchestra/pipeline" in app_js
    assert "/api/jobs" in os_js
    assert "/api/jobs" in app_js
    assert "/api/memory" in os_js
    assert "/api/memory" in app_js
    assert "/api/evolution/variants/" in os_js
    assert "/api/evolution/variants/" in app_js
    assert "moneyprinter.py" in dockerfile
    assert "/readyz" in dockerfile
    assert "/api/knowledge/nodes" in os_js
    assert "/api/knowledge/nodes" in app_js
    for walking in ("/api/v1/scripts", "/api/v1/storyboards", "/api/v1/thumbnails", "/static/placeholders/walking-skeleton.svg"):
        assert walking in os_js
        assert walking in app_js
    assert 'Stripe <strong>live</strong>' in os_js
    assert 'Stripe <strong>live</strong>' in app_js
    compose = (APP_DIR / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${HERMES_HOST_PORT:-8091}:8080" in compose
    assert "HERMES_FLYWHEEL_AUTO" in compose
    assert "HERMES_AGENTS_STORE" in compose
    assert "DATABASE_URL" in compose
    assert "hermes_data:/app/data" in compose
    assert "/readyz" in compose
    hosted = (APP_DIR / "docker-compose.hosted.yml").read_text(encoding="utf-8")
    assert "HERMES_DB_PATH" in hosted
    assert "hermes_data:/app/data" in hosted
    assert "/readyz" in hosted


def test_research_endpoint_self_heals_and_upserts_node(client, tmp_path):
    http, _ = client
    started = time.monotonic()
    res = http.post("/api/agent/research", json={"topic": "AI"})
    elapsed = time.monotonic() - started
    assert res.status_code == 200
    body = res.json()
    assert body["topic"] == "AI"
    assert body["trend"]
    assert "[DRY-RUN]" in body["trend"]
    assert body["timestamp"]
    assert elapsed < 3
    nodes = http.get("/api/knowledge/nodes")
    assert nodes.status_code == 200
    topics = {n["topic"] for n in nodes.json()["nodes"]}
    assert "AI" in topics
    discovery = http.get("/api/discovery")
    assert discovery.status_code == 200
    assert any(t["name"] == "AI" for t in discovery.json()["topics"])
    db_file = tmp_path / "hermes.db"
    assert db_file.is_file()


def test_knowledge_db_migrates_json_campaigns(tmp_path, monkeypatch):
    import db as hermes_db

    store = tmp_path / "campaigns.json"
    store.write_text(
        json.dumps({"campaigns": {"c1": {"id": "c1", "niche": "AI", "updated_at": 1}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(store))
    monkeypatch.setenv("HERMES_DB_PATH", str(tmp_path / "migrate.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    hermes_db.reset_migrate_flag()
    path = hermes_db.ensure_db()
    assert Path(path).is_file()
    rows = hermes_db.list_campaign_rows()
    assert any(r.get("id") == "c1" for r in rows)


def test_campaigns_sqlite_round_trip(tmp_path, monkeypatch):
    import db as hermes_db
    import campaigns as camp

    monkeypatch.setenv("HERMES_DB_PATH", str(tmp_path / "sot.db"))
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(tmp_path / "legacy.json"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    hermes_db.reset_migrate_flag()
    created = camp.create_campaign({"niche": "SQLite niche", "goal": "round-trip"})
    cid = created["id"]
    loaded = camp.get_campaign(cid)
    assert loaded is not None
    assert loaded["niche"] == "SQLite niche"
    listed = camp.list_campaigns()
    assert listed[0]["id"] == cid
    rows = hermes_db.list_campaign_rows()
    assert any(r.get("id") == cid and r.get("niche") == "SQLite niche" for r in rows)
    loaded["status"] = "queued"
    camp.upsert_campaign(loaded)
    again = hermes_db.get_campaign_row(cid)
    assert again is not None
    assert again["status"] == "queued"
    assert not (tmp_path / "legacy.json").is_file()


def test_mutating_api_auth_503_vs_401(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import db as hermes_db

    monkeypatch.setenv("PUBLIC_DOMAIN", "hermestudios.com")
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("HERMES_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(tmp_path / "auth-campaigns.json"))
    monkeypatch.setenv("HERMES_FLYWHEEL_STORE", str(tmp_path / "fw.json"))
    monkeypatch.setenv("HERMES_AGENTS_STORE", str(tmp_path / "ag.json"))
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://127.0.0.1:9/v1")
    hermes_db.reset_migrate_flag()
    http = TestClient(_load_app().app)
    assert http.get("/livez").status_code == 200
    assert http.get("/health").status_code == 200
    assert http.get("/api/campaigns").status_code == 200
    assert http.post("/api/campaigns", json={"niche": "x", "launch": False}).status_code == 503
    assert http.post("/api/flywheel/start").status_code == 503
    assert http.post("/api/campaigns/x/launch").status_code == 503
    assert http.post("/api/agents/tick").status_code == 503
    assert http.post("/api/evolution/x/crown").status_code == 503
    assert http.post("/api/product/bootstrap").status_code == 503
    assert http.post("/api/v1/scripts", json={"topic": "AI", "audience": "devs"}).status_code == 503

    token = "unit-test-bearer"
    monkeypatch.setenv("HERMES_API_KEY", token)
    hermes_db.reset_migrate_flag()
    http = TestClient(_load_app().app)
    assert http.post("/api/campaigns", json={"niche": "x", "launch": False}).status_code == 401
    assert http.post("/api/flywheel/start").status_code == 401
    assert http.post("/api/agents/tick").status_code == 401
    assert http.post("/api/campaigns/missing/launch").status_code == 401
    assert http.post("/api/evolution/missing/crown").status_code == 401
    created = http.post(
        "/api/campaigns",
        json={"niche": "x", "launch": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 200
    assert created.json()["id"]
    launch = http.post(
        f"/api/campaigns/{created.json()['id']}/launch",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert launch.status_code == 200
    assert http.post("/api/v1/scripts", json={"topic": "AI", "audience": "devs"}).status_code == 401
    scripts = http.post(
        "/api/v1/scripts",
        json={"topic": "AI", "audience": "devs"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert scripts.status_code == 200


def test_walking_skeleton_round_trip_and_research_shape(client):
    http, _ = client
    missing = http.post("/api/v1/storyboards", json={"script_id": "does-not-exist"})
    assert missing.status_code == 404
    scripts = http.post("/api/v1/scripts", json={"topic": "AI", "audience": "founders"})
    assert scripts.status_code == 200
    script_body = scripts.json()
    assert script_body["script_id"]
    assert script_body["script"]
    assert script_body["timestamp"]
    assert "trend" not in script_body
    boards = http.post("/api/v1/storyboards", json={"script_id": script_body["script_id"]})
    assert boards.status_code == 200
    board_body = boards.json()
    assert board_body["storyboard_id"]
    assert len(board_body["scenes"]) == 3
    thumbs = http.post(
        "/api/v1/thumbnails",
        json={"script_id": script_body["script_id"], "storyboard_id": board_body["storyboard_id"]},
    )
    assert thumbs.status_code == 200
    thumb_body = thumbs.json()
    assert thumb_body["thumbnail_id"]
    assert thumb_body["thumbnail_url"] == "/static/placeholders/walking-skeleton.svg"
    assert "example.com" not in thumb_body["thumbnail_url"]
    mismatched = http.post(
        "/api/v1/thumbnails",
        json={"script_id": script_body["script_id"], "storyboard_id": "missing-board"},
    )
    assert mismatched.status_code == 404
    research = http.post("/api/agent/research", json={"topic": "AI"})
    assert research.status_code == 200
    research_body = research.json()
    assert research_body["topic"] == "AI"
    assert "trend" in research_body
    assert "node" in research_body
    assert "script_id" not in research_body
    placeholder = http.get("/static/placeholders/walking-skeleton.svg")
    assert placeholder.status_code == 200


def test_endpoints_json_unique_and_includes_walking_skeleton():
    catalog = json.loads((APP_DIR / "endpoints.json").read_text(encoding="utf-8"))
    keys = [(row["method"], row["path"]) for row in catalog]
    assert len(keys) == len(set(keys))
    assert ("POST", "/api/v1/scripts") in keys
    assert ("POST", "/api/v1/storyboards") in keys
    assert ("POST", "/api/v1/thumbnails") in keys
    assert ("POST", "/api/agent/research") in keys
    assert ("GET", "/health") in keys
    module = _load_app()
    live = {
        (method, route.path)
        for route in module.app.routes
        if hasattr(route, "methods") and hasattr(route, "path")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert set(keys) <= live


def test_flywheel_origin_from_public_domain(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import db as hermes_db

    monkeypatch.setenv("PUBLIC_DOMAIN", "hermestudios.com")
    monkeypatch.setenv("HERMES_API_KEY", "origin-test-key")
    monkeypatch.setenv("HERMES_DB_PATH", str(tmp_path / "origin.db"))
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(tmp_path / "origin-campaigns.json"))
    monkeypatch.setenv("HERMES_FLYWHEEL_STORE", str(tmp_path / "origin-fw.json"))
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://127.0.0.1:9/v1")
    hermes_db.reset_migrate_flag()
    http = TestClient(_load_app().app)
    health = http.get("/health")
    assert health.status_code == 200
    assert health.json()["flywheel"]["origin"] == "https://hermestudios.com"
    snap = http.get("/api/flywheel")
    assert snap.status_code == 200
    assert snap.json()["origin"] == "https://hermestudios.com"


def test_discovery_recency_and_knowledge_graph_links(client):
    http, _ = client
    first = http.post("/api/agent/research", json={"topic": "Claude"})
    second = http.post("/api/agent/research", json={"topic": "Shorts"})
    assert first.status_code == 200
    assert second.status_code == 200
    discovery = http.get("/api/discovery")
    assert discovery.status_code == 200
    body = discovery.json()
    names = {t["name"] for t in body["topics"]}
    assert "Claude" in names and "Shorts" in names
    for topic in body["topics"]:
        assert "recency_score" in topic
        assert 0 <= float(topic["recency_score"]) <= 1
        assert topic["mode"] in {"dry_run", "live", "pending"}
        assert topic["label"] in {"DRY-RUN", "live", "pending"}
        assert "wikipedia" not in topic
    graph = http.get("/api/knowledge/graph")
    assert graph.status_code == 200
    payload = graph.json()
    assert "nodes" in payload and "links" in payload
    assert payload["count"] >= 2
    assert any(
        {link["source"], link["target"]} == {"claude", "shorts"}
        or {link["source"], link["target"]} == {"Claude", "Shorts"}
        for link in payload["links"]
    )
    nodes = http.get("/api/knowledge/nodes")
    assert nodes.status_code == 200
    assert nodes.json()["count"] >= 2


def test_analytics_shape_and_evolution_crown(client):
    http, _ = client
    http.post("/api/agent/research", json={"topic": "Analytics"})
    created = http.post("/api/campaigns", json={"niche": "Analytics", "launch": False})
    assert created.status_code == 200
    cid = created.json()["id"]
    analytics = http.get("/api/analytics")
    assert analytics.status_code == 200
    snap = analytics.json()
    assert "tick_total" in snap
    assert "campaigns_by_label" in snap
    assert isinstance(snap["campaigns_by_label"], dict)
    assert snap["knowledge_count"] >= 1
    assert snap["campaign_count"] >= 1
    assert "research" in snap
    evo = http.get("/api/evolution")
    assert evo.status_code == 200
    assert any(row["id"] == cid for row in evo.json()["campaigns"])
    crowned = http.post(f"/api/evolution/{cid}/crown")
    assert crowned.status_code == 200
    assert crowned.json()["crowned"] is True
    listed = http.get("/api/evolution").json()
    assert any(row["id"] == cid and row["crowned"] for row in listed["crowned"])
    retired = http.post(f"/api/evolution/{cid}/retire")
    assert retired.status_code == 200
    assert retired.json()["crowned"] is False
    assert retired.json()["status"] == "retired"
    dbg = http.get("/api/debugger")
    assert dbg.status_code == 200
    assert isinstance(dbg.json()["events"], list)
    health = http.get("/health").json()
    assert health["lm_studio"]["status"] in {"up", "down"}
    assert "enabled" in health["moneyprinter"]
    status = http.get("/api/status").json()
    assert status["lm_studio"]["status"] in {"up", "down"}
    assert "moneyprinter" in status


def test_os_get_routes_stay_public_when_key_set(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import db as hermes_db

    monkeypatch.setenv("PUBLIC_DOMAIN", "hermestudios.com")
    monkeypatch.setenv("HERMES_API_KEY", "public-get-key")
    monkeypatch.setenv("HERMES_DB_PATH", str(tmp_path / "public.db"))
    monkeypatch.setenv("HERMES_BACKUP_DIR", str(tmp_path / "public-backups"))
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(tmp_path / "public-campaigns.json"))
    monkeypatch.setenv("HERMES_FLYWHEEL_STORE", str(tmp_path / "public-fw.json"))
    monkeypatch.setenv("HERMES_AGENTS_STORE", str(tmp_path / "public-ag.json"))
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://127.0.0.1:9/v1")
    hermes_db.reset_migrate_flag()
    http = TestClient(_load_app().app)
    for path in (
        "/api/discovery",
        "/api/knowledge/nodes",
        "/api/knowledge/graph",
        "/api/analytics",
        "/api/evolution",
        "/api/debugger",
        "/api/jobs",
        "/api/orchestra/pipeline",
        "/api/memory",
        "/api/ops/backup",
        "/terms",
        "/privacy",
        "/refunds",
        "/health",
        "/api/status",
    ):
        res = http.get(path)
        assert res.status_code == 200, path
    assert http.post("/api/evolution/missing/crown").status_code == 401
    assert http.post("/api/product/bootstrap").status_code == 401
    assert http.post("/api/discovery/scan").status_code == 401
    assert http.post("/api/ops/backup").status_code == 401


def test_product_surfaces_jobs_orchestra_evolution_memory(client):
    http, _ = client
    boot = http.post("/api/product/bootstrap")
    assert boot.status_code == 200
    body = boot.json()
    assert body["ok"] is True
    assert len(body["opportunities"]) == 3
    discovery = http.get("/api/discovery")
    assert discovery.status_code == 200
    disc = discovery.json()
    assert [s["name"] for s in disc["sources"]] == [
        "YouTube",
        "TikTok",
        "Reddit",
        "Trends",
        "X",
        "News",
        "Rivals",
    ]
    assert disc["opportunity_count"] >= 3
    assert disc["opportunities"][0]["score"] >= disc["opportunities"][-1]["score"]
    orch = http.get("/api/orchestra/pipeline")
    assert orch.status_code == 200
    keys = [a["key"] for a in orch.json()["agents"]]
    assert keys == [
        "research",
        "hook",
        "script",
        "storyboard",
        "narration",
        "video",
        "publishing",
        "analytics",
    ]
    analytics = http.get("/api/analytics").json()
    assert "compounding" in analytics
    assert len(analytics["compounding"]["cards"]) == 3
    evo = http.get("/api/evolution").json()
    assert evo["latest"]["number"] == 129
    assert evo["winners_promoted"] >= 1
    variant_id = evo["latest"]["variants"][0]["id"]
    promoted = http.post(f"/api/evolution/variants/{variant_id}/promote")
    assert promoted.status_code == 200
    assert promoted.json()["state"] == "promoted"
    mem = http.get("/api/memory").json()
    assert mem["count"] >= 2
    created = http.post(
        "/api/campaigns",
        json={
            "niche": "AI education",
            "goal": "Subscriber growth",
            "cadence": "3x daily",
            "launch": False,
        },
    )
    cid = created.json()["id"]
    assert created.json()["cadence"] == "3x daily"
    jobs = http.get(f"/api/jobs?campaign_id={cid}")
    assert jobs.status_code == 200
    missing = http.get("/api/jobs/does-not-exist")
    assert missing.status_code == 404
    assert http.post("/api/evolution/variants/missing/archive").status_code == 404
    status = http.get("/api/status").json()
    assert status["jobs"] == "/api/jobs"
    catalog = json.loads((APP_DIR / "endpoints.json").read_text(encoding="utf-8"))
    assert ("GET", "/api/jobs") in [(row["method"], row["path"]) for row in catalog]
    assert ("POST", "/api/discovery/scan") in [(row["method"], row["path"]) for row in catalog]


def test_discovery_scan_legal_and_sqlite_backup(client, monkeypatch):
    http, module = client
    landing = http.get("/")
    assert landing.status_code == 200
    assert b"/terms" in landing.content
    for path, needle in (("/terms", b"Terms"), ("/privacy", b"Privacy"), ("/refunds", b"Refunds")):
        page = http.get(path)
        assert page.status_code == 200, path
        assert needle in page.content
    atom = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Local LLMs on a Mac</title><link href="https://youtube.com/watch?v=x"/><published>2026-08-25T00:00:00Z</published></entry>
    </feed>"""
    rss = b"""<?xml version="1.0"?><rss><channel>
      <item><title>TikTok AI shorts exploding</title><link>https://news.example/t</link></item>
    </channel></rss>"""
    reddit = b"""{"data":{"children":[{"data":{"title":"Prompt engineering is dead","permalink":"/r/MachineLearning/1","ups":120}}]}}"""

    def fake_fetch(url: str, timeout: float) -> bytes:
        if "reddit.com" in url:
            return reddit
        if "news.google.com" in url:
            return rss
        return atom

    monkeypatch.setattr(module, "scan_public_feeds", lambda query=None: __import__("scrapers").scan_public_feeds(fetch=fake_fetch, query=query))
    scan = http.post("/api/discovery/scan", json={"query": "AI"})
    assert scan.status_code == 200
    body = scan.json()
    assert body["paid"] is False
    assert body["live_compose"] is False
    assert body["stored"] >= 1
    assert body["mode"] == "live"
    disc = http.get("/api/discovery").json()
    sources = {s["name"]: s["status"] for s in disc["sources"]}
    assert sources["YouTube"] == "live"
    assert sources["TikTok"] == "live"
    assert sources["Reddit"] == "live"
    titles = [o["title"] for o in disc["opportunities"]]
    assert any("Local LLMs" in t for t in titles)
    listed = http.get("/api/ops/backup")
    assert listed.status_code == 200
    created = http.post("/api/ops/backup")
    assert created.status_code == 200
    assert created.json()["ok"] is True
    assert created.json()["backend"] == "sqlite"
    assert created.json()["backups"]
    assert http.get("/api/status").json()["discovery_scan"] == "/api/discovery/scan"



