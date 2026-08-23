"""Stripe billing for Hermes OS (test-mode Checkout + subscriptions).

Payment types (from product copy — campaigns + /v1 usage):
  implemented
    one_time   campaign_launch, credit_pack  → Checkout Session (mode=payment)
    recurring  autonomous_console (v0.4.0)   → Checkout Session (mode=subscription)
    usage      inference_meter               → local ledger; Stripe MeterEvent if env set
    tax        automatic_tax flag            → off unless STRIPE_AUTOMATIC_TAX=true
    webhooks   checkout/invoice/payment_intent → unlock credits / plan
  skipped
    connect    Hermes is not a creator marketplace (no connected accounts)
    tax registration / live products — operator must approve paid Catalog items
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

# Catalog amounts are USD test prices only. Do not treat as live SKUs until
# the operator creates matching Dashboard products and confirms paid go-live.
CATALOG: dict[str, dict[str, Any]] = {
    "campaign_launch": {
        "sku": "campaign_launch",
        "kind": "one_time",
        "name": "Campaign launch pack",
        "description": "Unlock one autonomous media campaign launch on Hermes OS.",
        "amount_cents": 2900,
        "currency": "usd",
        "credits": 1,
        "unlock": "campaign_credits",
        "price_env": "STRIPE_PRICE_CAMPAIGN_LAUNCH",
    },
    "credit_pack": {
        "sku": "credit_pack",
        "kind": "one_time",
        "name": "Inference credit pack",
        "description": "Prepaid tokens for OpenAI-compatible /v1 on hermestudios.com.",
        "amount_cents": 1900,
        "currency": "usd",
        "credits": 100,
        "unlock": "inference_credits",
        "price_env": "STRIPE_PRICE_CREDIT_PACK",
    },
    "autonomous_console": {
        "sku": "autonomous_console",
        "kind": "recurring",
        "name": "Hermes OS Autonomous v0.4.0",
        "description": "Monthly console subscription for the autonomous campaign flywheel.",
        "amount_cents": 4900,
        "currency": "usd",
        "interval": "month",
        "unlock": "plan",
        "plan": "autonomous",
        "price_env": "STRIPE_PRICE_AUTONOMOUS",
    },
    "inference_meter": {
        "sku": "inference_meter",
        "kind": "usage",
        "name": "Metered /v1 inference",
        "description": "Usage records for chat/completions; Stripe Billing Meter when configured.",
        "currency": "usd",
        "unlock": "usage",
        "price_env": "STRIPE_PRICE_INFERENCE_METER",
        "meter_env": "STRIPE_METER_EVENT_NAME",
    },
}

SKIPPED: dict[str, str] = {
    "connect": "Skipped: Hermes OS is a studio console, not a creator marketplace.",
    "tax_registration": "Skipped: do not register Stripe Tax without operator approval.",
}

_DEFAULT_STORE = Path(__file__).resolve().parent / "data" / "billing.json"


def store_path() -> Path:
    raw = (os.environ.get("HERMES_BILLING_STORE") or "").strip()
    return Path(raw) if raw else _DEFAULT_STORE


def secret_key() -> str:
    return (os.environ.get("STRIPE_SECRET_KEY") or "").strip()


def publishable_key() -> str:
    return (os.environ.get("STRIPE_PUBLISHABLE_KEY") or "").strip()


def webhook_secret() -> str:
    return (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()


def configured() -> bool:
    key = secret_key()
    return key.startswith(("sk_", "rk_"))


def test_mode() -> bool:
    return secret_key().startswith("sk_test_") or not configured()


def automatic_tax() -> bool:
    return (os.environ.get("STRIPE_AUTOMATIC_TAX") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def public_origin() -> str:
    domain = (os.environ.get("PUBLIC_DOMAIN") or "localhost").strip() or "localhost"
    if domain in {"localhost", "127.0.0.1"}:
        port = os.environ.get("HERMES_HOST_PORT") or "8091"
        return f"http://127.0.0.1:{port}"
    return f"https://{domain}"


def _empty_db() -> dict[str, Any]:
    return {
        "entitlements": {
            "plan": "free",
            "campaign_credits": 0,
            "inference_credits": 0,
            "campaigns_unlocked": [],
        },
        "events": {},
        "usage": [],
    }


def load_db() -> dict[str, Any]:
    path = store_path()
    if not path.is_file():
        return _empty_db()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_db()
    if not isinstance(data, dict):
        return _empty_db()
    base = _empty_db()
    base.update(data)
    if not isinstance(base.get("entitlements"), dict):
        base["entitlements"] = _empty_db()["entitlements"]
    if not isinstance(base.get("events"), dict):
        base["events"] = {}
    if not isinstance(base.get("usage"), list):
        base["usage"] = []
    return base


def save_db(db: dict[str, Any]) -> None:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(db, indent=2), encoding="utf-8")
    tmp.replace(path)


def entitlements() -> dict[str, Any]:
    return dict(load_db()["entitlements"])


def not_configured_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "error": "stripe_not_configured",
        "hint": (
            "Set STRIPE_SECRET_KEY=sk_test_... (test mode only) and optional "
            "STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET. Copy services/hermes-api/.env.example. "
            "Do not use sk_live keys without operator approval."
        ),
        "docs": "https://docs.stripe.com/checkout/quickstart",
    }


def public_config() -> dict[str, Any]:
    products = []
    for sku, item in CATALOG.items():
        products.append(
            {
                "sku": sku,
                "kind": item["kind"],
                "name": item["name"],
                "description": item["description"],
                "amount_cents": item.get("amount_cents"),
                "currency": item.get("currency", "usd"),
                "interval": item.get("interval"),
                "configured_price_id": bool((os.environ.get(item.get("price_env") or "") or "").strip()),
            }
        )
    meter_name = (os.environ.get("STRIPE_METER_EVENT_NAME") or "").strip()
    return {
        "ok": True,
        "configured": configured(),
        "test_mode": test_mode(),
        "publishable_key": publishable_key() or None,
        "automatic_tax": automatic_tax(),
        "products": products,
        "usage_meter": {
            "implemented": True,
            "stripe_meter_configured": bool(meter_name),
            "event_name": meter_name or None,
            "note": (
                "Local usage ledger always records. Stripe MeterEvent.create "
                "runs only when STRIPE_METER_EVENT_NAME is set."
            ),
        },
        "skipped": SKIPPED,
        "success_path": "/console#/settings?billing=success",
        "cancel_path": "/console#/settings?billing=cancel",
    }


def _import_stripe():
    try:
        import stripe  # type: ignore
    except ImportError as exc:
        raise RuntimeError("stripe package missing; pip install -r requirements.billing.txt") from exc
    return stripe


def _create_checkout(params: dict[str, Any], idempotency_key: str):
    stripe = _import_stripe()
    client_cls = getattr(stripe, "StripeClient", None)
    if client_cls is not None:
        client = client_cls(secret_key())
        sessions = getattr(getattr(client, "checkout", None), "sessions", None)
        create = getattr(sessions, "create", None)
        if callable(create):
            try:
                return create(params, idempotency_key=idempotency_key)
            except TypeError:
                return create(**params, idempotency_key=idempotency_key)
    stripe.api_key = secret_key()
    return stripe.checkout.Session.create(**params, idempotency_key=idempotency_key)


def _line_item(product: dict[str, Any]) -> dict[str, Any]:
    price_id = (os.environ.get(product.get("price_env") or "") or "").strip()
    if price_id:
        return {"price": price_id, "quantity": 1}
    price_data: dict[str, Any] = {
        "currency": product.get("currency") or "usd",
        "product_data": {
            "name": product["name"],
            "description": product["description"][:500],
        },
        "unit_amount": int(product["amount_cents"]),
    }
    if product["kind"] == "recurring":
        price_data["recurring"] = {"interval": product.get("interval") or "month"}
    return {"price_data": price_data, "quantity": 1}


def _idempotency_key(sku: str, extra: str = "") -> str:
    raw = f"{sku}:{extra}:{int(time.time() // 30)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def create_checkout_session(
    sku: str,
    *,
    campaign_id: str | None = None,
    customer_email: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if not configured():
        payload = not_configured_payload()
        payload["status"] = 503
        return payload
    product = CATALOG.get(sku)
    if product is None:
        return {"ok": False, "error": "unknown_sku", "status": 400, "skus": list(CATALOG)}
    if product["kind"] == "usage":
        return {
            "ok": False,
            "error": "usage_sku_not_checkout",
            "status": 400,
            "hint": "POST /api/billing/usage for metered inference; Checkout is for one_time and recurring SKUs.",
        }
    mode = "subscription" if product["kind"] == "recurring" else "payment"
    origin = public_origin()
    metadata = {"sku": sku, "hermes": "os"}
    if campaign_id:
        metadata["campaign_id"] = campaign_id
    params: dict[str, Any] = {
        "mode": mode,
        "line_items": [_line_item(product)],
        "success_url": f"{origin}/console#/settings?billing=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{origin}/console#/settings?billing=cancel",
        "metadata": metadata,
        "client_reference_id": campaign_id or sku,
    }
    if customer_email:
        params["customer_email"] = customer_email
    if automatic_tax():
        params["automatic_tax"] = {"enabled": True}
    try:
        key = idempotency_key or _idempotency_key(sku, f"{campaign_id or ''}:{customer_email or ''}")
        session = _create_checkout(params, key)
    except Exception as exc:
        return {
            "ok": False,
            "status": 503,
            "error": "stripe_checkout_failed",
            "hint": str(exc),
        }
    url = getattr(session, "url", None) or (session.get("url") if isinstance(session, dict) else None)
    sid = getattr(session, "id", None) or (session.get("id") if isinstance(session, dict) else None)
    return {
        "ok": True,
        "id": sid,
        "url": url,
        "mode": mode,
        "sku": sku,
        "test_mode": test_mode(),
        "idempotency_key": key,
    }


def record_usage(
    quantity: int,
    *,
    customer: str | None = None,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    qty = max(1, int(quantity))
    row = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "quantity": qty,
        "customer": customer,
        "campaign_id": campaign_id,
        "stripe_sent": False,
    }
    meter = (os.environ.get("STRIPE_METER_EVENT_NAME") or "").strip()
    if configured() and meter:
        stripe = _import_stripe()
        payload = {
            "event_name": meter,
            "payload": {"value": str(qty), "stripe_customer_id": customer or "anonymous"},
        }
        stripe.billing.MeterEvent.create(**payload)
        row["stripe_sent"] = True
    db = load_db()
    db["usage"].append(row)
    save_db(db)
    return {"ok": True, "usage": row, "stripe_meter": bool(meter and configured())}


def _apply_sku(db: dict[str, Any], sku: str, campaign_id: str | None) -> None:
    product = CATALOG.get(sku) or {}
    ent = db["entitlements"]
    unlock = product.get("unlock")
    if unlock == "campaign_credits":
        ent["campaign_credits"] = int(ent.get("campaign_credits") or 0) + int(product.get("credits") or 1)
    elif unlock == "inference_credits":
        ent["inference_credits"] = int(ent.get("inference_credits") or 0) + int(product.get("credits") or 0)
    elif unlock == "plan":
        ent["plan"] = product.get("plan") or "autonomous"
    if campaign_id:
        unlocked = list(ent.get("campaigns_unlocked") or [])
        if campaign_id not in unlocked:
            unlocked.append(campaign_id)
        ent["campaigns_unlocked"] = unlocked
        try:
            from campaigns import get_campaign, upsert_campaign

            campaign = get_campaign(campaign_id)
            if campaign:
                campaign["paid"] = True
                campaign["paid_sku"] = sku
                upsert_campaign(campaign)
        except Exception:
            pass


def apply_event(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event.get("id") or "")
    etype = str(event.get("type") or "")
    db = load_db()
    if event_id and event_id in db["events"]:
        return {"ok": True, "duplicate": True, "id": event_id}
    data = event.get("data") or {}
    obj = data.get("object") if isinstance(data, dict) else {}
    if not isinstance(obj, dict):
        obj = {}
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    sku = str(metadata.get("sku") or obj.get("client_reference_id") or "")
    if sku not in CATALOG:
        sku = "campaign_launch" if "checkout" in etype or "payment_intent" in etype else sku
    campaign_id = metadata.get("campaign_id")
    if etype in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "invoice.paid",
        "invoice.payment_succeeded",
        "payment_intent.succeeded",
        "customer.subscription.updated",
        "customer.subscription.created",
    }:
        if sku in CATALOG:
            _apply_sku(db, sku, campaign_id if isinstance(campaign_id, str) else None)
        if etype.startswith("customer.subscription") or etype.startswith("invoice."):
            db["entitlements"]["plan"] = CATALOG["autonomous_console"].get("plan") or "autonomous"
    db["events"][event_id or str(uuid.uuid4())] = {
        "type": etype,
        "sku": sku,
        "ts": time.time(),
    }
    save_db(db)
    return {"ok": True, "duplicate": False, "id": event_id, "type": etype, "sku": sku}


def construct_event(payload: bytes, signature: str | None) -> dict[str, Any]:
    secret = webhook_secret()
    if not secret:
        try:
            body = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid json and no STRIPE_WEBHOOK_SECRET") from exc
        if not isinstance(body, dict):
            raise ValueError("webhook body must be an object")
        return body
    stripe = _import_stripe()
    return stripe.Webhook.construct_event(payload, signature or "", secret)
