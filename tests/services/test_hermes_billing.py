"""Stripe billing routes for Hermes OS (mocked SDK, test-mode catalog)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
APP_DIR = PROJECT_ROOT / "services" / "hermes-api"
sys.path.insert(0, str(APP_DIR))

APP_PATH = APP_DIR / "app.py"


def _load_app():
    spec = importlib.util.spec_from_file_location("hermes_api_billing_app", APP_PATH)
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
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("HERMES_BILLING_STORE", str(tmp_path / "billing.json"))
    monkeypatch.setenv("HERMES_CAMPAIGN_STORE", str(tmp_path / "campaigns.json"))
    module = _load_app()
    return TestClient(module.app), module


def test_publishable_config_and_checkout_unconfigured(client):
    http, _ = client
    cfg = http.get("/api/billing/config")
    assert cfg.status_code == 200
    body = cfg.json()
    assert body["configured"] is False
    skus = {p["sku"] for p in body["products"]}
    assert {"campaign_launch", "credit_pack", "autonomous_console", "inference_meter"} <= skus
    assert "connect" in body["skipped"]
    checkout = http.post("/api/billing/checkout", json={"sku": "campaign_launch"})
    assert checkout.status_code == 503
    err = checkout.json()
    assert err["error"] == "stripe_not_configured"
    assert "STRIPE_SECRET_KEY" in err["hint"]
    sub = http.post("/api/billing/subscribe", json={})
    assert sub.status_code == 503


def test_checkout_mocked_session_url(client, monkeypatch):
    http, module = client
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_mock_hermes")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_mock")

    class FakeSession:
        @staticmethod
        def create(**kwargs):
            assert kwargs["mode"] == "payment"
            assert kwargs.get("idempotency_key")
            return SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.com/c/pay/cs_test_1")

    fake = SimpleNamespace(
        api_key=None,
        checkout=SimpleNamespace(Session=FakeSession),
    )
    monkeypatch.setattr(module, "create_checkout_session", module.create_checkout_session)
    import billing as billing_mod

    monkeypatch.setattr(billing_mod, "_import_stripe", lambda: fake)
    monkeypatch.setattr(billing_mod, "configured", lambda: True)
    monkeypatch.setattr(billing_mod, "secret_key", lambda: "sk_test_mock_hermes")
    res = http.post("/api/billing/checkout", json={"sku": "campaign_launch"})
    assert res.status_code == 200
    assert res.json()["url"].startswith("https://checkout.stripe.com/")


def test_subscribe_mocked_subscription_mode(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PUBLIC_DOMAIN", "localhost")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_mock_hermes")
    monkeypatch.setenv("HERMES_BILLING_STORE", str(tmp_path / "b.json"))
    monkeypatch.delenv("HERMES_API_KEY", raising=False)

    class FakeSession:
        @staticmethod
        def create(**kwargs):
            assert kwargs["mode"] == "subscription"
            return {"id": "cs_sub", "url": "https://checkout.stripe.com/c/pay/cs_sub"}

    import billing as billing_mod

    monkeypatch.setattr(
        billing_mod,
        "_import_stripe",
        lambda: SimpleNamespace(checkout=SimpleNamespace(Session=FakeSession)),
    )
    monkeypatch.setattr(billing_mod, "configured", lambda: True)
    module = _load_app()
    http = TestClient(module.app)
    res = http.post("/api/billing/subscribe", json={})
    assert res.status_code == 200
    assert res.json()["mode"] == "subscription"


def test_webhook_unlocks_campaign_credits(client):
    http, _ = client
    event = {
        "id": "evt_test_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"sku": "campaign_launch", "campaign_id": "camp_1"},
            }
        },
    }
    first = http.post("/api/billing/webhook", content=json.dumps(event))
    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    second = http.post("/api/billing/webhook", content=json.dumps(event))
    assert second.json()["duplicate"] is True
    usage = http.post("/api/billing/usage", json={"quantity": 3})
    assert usage.status_code == 200
    assert usage.json()["usage"]["quantity"] == 3
    entitlements = http.get("/api/billing/entitlements")
    assert entitlements.status_code == 200
    ent = entitlements.json()["entitlements"]
    assert ent["campaign_credits"] >= 1


def test_status_exposes_billing(client):
    http, _ = client
    status = http.get("/api/status").json()
    assert status["billing"] == "/api/billing/config"
    assert status["stripe_configured"] is False
