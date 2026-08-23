"""Hermes Studios public API — Hostinger-facing gateway to inference."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from billing import (
    apply_event,
    configured as stripe_configured,
    construct_event,
    create_checkout_session,
    entitlements as billing_entitlements,
    not_configured_payload,
    public_config as billing_public_config,
    record_usage,
)
from campaigns import (
    bind_infer_from_app,
    create_campaign,
    fail_campaign,
    get_campaign,
    list_campaigns,
    run_orchestra,
    upsert_campaign,
)
from flywheel import (
    CANONICAL_ORIGIN,
    SELF_CHECK_PATHS,
    request_start as flywheel_start,
    request_stop as flywheel_stop,
    run_loop as flywheel_run_loop,
    snapshot as flywheel_snapshot,
    summarize_probe,
)
from agents.orchestrator import snapshot as agents_snapshot
from agents.orchestrator import snapshot_category as agents_snapshot_category
from agents.orchestrator import tick_all as agents_tick_all

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_LM_STUDIO = "http://127.0.0.1:1234/v1"
START_MONOTONIC = time.monotonic()
_INFLIGHT: asyncio.Semaphore | None = None
_FLYWHEEL_TASK: asyncio.Task[None] | None = None


def _inference_base() -> str:
    return (
        os.environ.get("INFERENCE_BASE_URL")
        or os.environ.get("LM_STUDIO_BASE_URL")
        or DEFAULT_LM_STUDIO
    ).rstrip("/")


def _inference_key() -> str:
    return (
        os.environ.get("INFERENCE_API_KEY")
        or os.environ.get("LM_STUDIO_API_KEY")
        or "lm-studio"
    )


def _inference_backend() -> str:
    explicit = (os.environ.get("INFERENCE_BACKEND") or "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("INFERENCE_BASE_URL"):
        return "vllm"
    return "lm_studio"


def _lm_base() -> str:
    return _inference_base()


def _lm_key() -> str:
    return _inference_key()


def _public_domain() -> str:
    # Local uvicorn defaults to localhost so /v1 is usable without a production key.
    # Docker/VPS still set PUBLIC_DOMAIN=hermestudios.com in the image and compose.
    return os.environ.get("PUBLIC_DOMAIN") or "localhost"


def _api_key() -> str:
    return os.environ.get("HERMES_API_KEY") or ""


def _max_inflight() -> int:
    raw = os.environ.get("HERMES_MAX_INFLIGHT") or "32"
    try:
        return max(1, int(raw))
    except ValueError:
        return 32


def _inflight_wait_seconds() -> float:
    raw = os.environ.get("HERMES_INFLIGHT_WAIT_SECONDS") or "5"
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 5.0


def _production_locked() -> bool:
    if os.environ.get("HERMES_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}:
        return True
    domain = _public_domain().lower()
    return domain.endswith("hermestudios.com") or domain.endswith("hermestudios.online") or domain.endswith("hermestudios.org")


def _default_model() -> str:
    return (
        os.environ.get("INFERENCE_MODEL")
        or os.environ.get("LM_STUDIO_MODEL")
        or "local-model"
    )


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _INFLIGHT, _FLYWHEEL_TASK
    _INFLIGHT = asyncio.Semaphore(_max_inflight())
    auto = (os.environ.get("HERMES_FLYWHEEL_AUTO") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if auto:
        flywheel_start()
        _FLYWHEEL_TASK = asyncio.create_task(_flywheel_supervisor())
    yield
    if _FLYWHEEL_TASK is not None and not _FLYWHEEL_TASK.done():
        flywheel_stop()
        _FLYWHEEL_TASK.cancel()
        try:
            await _FLYWHEEL_TASK
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Hermes Studios", version="1.2.0", docs_url="/docs", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hermestudios.com",
        "https://www.hermestudios.com",
        "https://hermestudios.org",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://127.0.0.1:8091",
        "http://localhost:8091",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Stripe-Signature", "Idempotency-Key"],
)
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _require_auth(authorization: str | None) -> None:
    expected = _api_key()
    if not expected:
        if _production_locked():
            raise HTTPException(
                status_code=503,
                detail="HERMES_API_KEY is not configured; refusing public inference.",
            )
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def _get_inflight() -> asyncio.Semaphore:
    global _INFLIGHT
    if _INFLIGHT is None:
        _INFLIGHT = asyncio.Semaphore(_max_inflight())
    return _INFLIGHT


async def _acquire_inflight() -> asyncio.Semaphore:
    sem = _get_inflight()
    try:
        await asyncio.wait_for(sem.acquire(), timeout=_inflight_wait_seconds())
    except TimeoutError as exc:
        raise HTTPException(
            status_code=429,
            detail="Too many in-flight generations; retry shortly.",
        ) from exc
    return sem


@asynccontextmanager
async def _inflight_slot() -> AsyncIterator[None]:
    sem = await _acquire_inflight()
    try:
        yield
    finally:
        sem.release()


def _inference_unavailable(reason: object) -> dict[str, Any]:
    message = f"Inference unreachable at {_inference_base()}: {reason}"
    return {
        "error": {
            "message": message,
            "type": "inference_unavailable",
            "code": "inference_unreachable",
            "hint": (
                "Start LM Studio's local server (OpenAI-compatible) or set "
                "INFERENCE_BASE_URL, e.g. http://127.0.0.1:1234/v1"
            ),
        }
    }


def _upstream(method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 120) -> tuple[int, Any]:
    url = f"{_inference_base()}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = UrlRequest(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {_inference_key()}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            body: Any
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {"raw": raw}
            return int(getattr(resp, "status", 200)), body
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:2000]
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"error": raw}
        return int(exc.code), body
    except URLError as exc:
        return 502, _inference_unavailable(exc.reason)
    except TimeoutError as exc:
        return 504, _inference_unavailable(exc)
    except OSError as exc:
        return 502, _inference_unavailable(exc)


def _upstream_stream(path: str, payload: dict[str, Any], timeout: float = 180):
    url = f"{_inference_base()}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = UrlRequest(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {_inference_key()}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    resp = urlopen(req, timeout=timeout)

    def chunks():
        try:
            while True:
                chunk = resp.read(1024)
                if not chunk:
                    break
                yield chunk
        finally:
            resp.close()

    return chunks()


def _lm_health() -> dict[str, Any]:
    try:
        code, body = _upstream("GET", "/models", timeout=3)
    except Exception as exc:  # never fail /health
        return {
            "reachable": False,
            "status_code": 502,
            "models": [],
            "base_url_configured": _inference_base(),
            "backend": _inference_backend(),
            "error": str(exc),
        }
    models = []
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
        "base_url_configured": _inference_base(),
        "backend": _inference_backend(),
    }


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="Landing page missing")
    return FileResponse(index_path)


@app.get("/console")
def console() -> FileResponse:
    console_path = STATIC_DIR / "console.html"
    if not console_path.is_file():
        raise HTTPException(status_code=404, detail="Console missing")
    return FileResponse(console_path)


@app.get("/livez")
def livez() -> dict[str, Any]:
    """Process liveness — never probes upstream inference."""
    return {"ok": True, "service": "hermes-api"}


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    """Deploy readiness: production refuses to be ready without HERMES_API_KEY."""
    if _production_locked() and not _api_key():
        raise HTTPException(
            status_code=503,
            detail="HERMES_API_KEY is not configured; refusing public traffic.",
        )
    return {
        "ok": True,
        "service": "hermes-api",
        "domain": _public_domain(),
        "auth_configured": bool(_api_key()),
        "inference_backend": _inference_backend(),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    lm = _lm_health()
    fw = flywheel_snapshot()
    ag = agents_snapshot()
    return {
        "ok": True,
        "service": "hermes-api",
        "domain": _public_domain(),
        "uptime_seconds": round(time.monotonic() - START_MONOTONIC, 1),
        "auth_configured": bool(_api_key()),
        "origin": CANONICAL_ORIGIN,
        "inference": {
            "backend": lm["backend"],
            "reachable": lm["reachable"],
            "models": lm["models"],
            "max_inflight": _max_inflight(),
        },
        "lm_studio": {
            "reachable": lm["reachable"],
            "models": lm["models"],
        },
        "flywheel": {
            "running": fw.get("running"),
            "cycle_count": fw.get("cycle_count"),
            "origin": fw.get("origin"),
            "last_self_check": fw.get("last_self_check") or {},
        },
        "agents": {
            "count": ag.get("count"),
            "tick_count": ag.get("tick_count"),
            "concurrency": ag.get("concurrency"),
        },
    }


@app.get("/v1/models")
async def list_models(authorization: str | None = Header(default=None)) -> JSONResponse:
    _require_auth(authorization)
    async with _inflight_slot():
        code, body = await asyncio.to_thread(_upstream, "GET", "/models", None, 15)
    return JSONResponse(content=body, status_code=code)


async def _proxy_json(
    request: Request,
    authorization: str | None,
    upstream_path: str,
    *,
    stream: bool = False,
) -> JSONResponse | StreamingResponse:
    _require_auth(authorization)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    if not payload.get("model"):
        payload["model"] = _default_model()
    if stream or payload.get("stream"):
        sem = await _acquire_inflight()
        try:
            iterator = await asyncio.to_thread(_upstream_stream, upstream_path, payload, 180)
        except (URLError, TimeoutError, OSError) as exc:
            sem.release()
            reason = getattr(exc, "reason", exc)
            return JSONResponse(content=_inference_unavailable(reason), status_code=502)

        def stream_and_release():
            try:
                yield from iterator
            except (URLError, TimeoutError, OSError) as exc:
                reason = getattr(exc, "reason", exc)
                yield json.dumps(_inference_unavailable(reason)).encode()
            finally:
                sem.release()

        return StreamingResponse(stream_and_release(), media_type="text/event-stream")
    async with _inflight_slot():
        code, body = await asyncio.to_thread(_upstream, "POST", upstream_path, payload, 180)
    return JSONResponse(content=body, status_code=code)


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
):
    return await _proxy_json(request, authorization, "/chat/completions")


@app.post("/v1/completions")
async def completions(
    request: Request,
    authorization: str | None = Header(default=None),
):
    return await _proxy_json(request, authorization, "/completions")


@app.post("/v1/embeddings")
async def embeddings(
    request: Request,
    authorization: str | None = Header(default=None),
):
    return await _proxy_json(request, authorization, "/embeddings")


@app.post("/api/youtube/upload")
async def youtube_upload_stub(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Accept metadata only. Binary upload stays on the Mac CLI (renders are local)."""
    _require_auth(authorization)
    payload = await request.json()
    return {
        "ok": False,
        "error": "Use `python -m tools.publishers.youtube_upload` on the machine that holds the render.",
        "received": {
            "title": payload.get("title") if isinstance(payload, dict) else None,
        },
    }


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    return {
        "domain": _public_domain(),
        "health": "/health",
        "openai_base_url": f"https://{_public_domain()}/v1",
        "auth": "Bearer HERMES_API_KEY",
        "inference_backend": _inference_backend(),
        "campaigns": "/api/campaigns",
        "billing": "/api/billing/config",
        "flywheel": "/api/flywheel",
        "agents": "/api/agents",
        "stripe_configured": stripe_configured(),
        "origin": CANONICAL_ORIGIN,
    }


async def _run_campaign_job(campaign_id: str) -> None:
    infer = bind_infer_from_app(_upstream)
    try:
        await run_orchestra(campaign_id, infer=infer)
    except Exception as exc:
        fail_campaign(campaign_id, f"Orchestra crashed after self-heal path: {exc}")


def _probe_call(path: str, fn: Any) -> dict[str, Any]:
    try:
        body = fn()
        if isinstance(body, JSONResponse):
            return summarize_probe(path, body.status_code, json.loads(body.body.decode()))
        return summarize_probe(path, 200, body)
    except HTTPException as exc:
        return summarize_probe(path, exc.status_code, {"detail": exc.detail})
    except Exception as exc:
        return summarize_probe(path, 500, {"error": str(exc)})


def _collect_flywheel_probes() -> list[dict[str, Any]]:
    probes = [
        _probe_call("/livez", livez),
        _probe_call("/readyz", readyz),
        _probe_call("/health", health),
        _probe_call("/api/status", api_status),
        _probe_call("/api/billing/config", api_billing_config),
        _probe_call("/api/campaigns", api_list_campaigns),
        _probe_call("/api/flywheel", api_flywheel),
        _probe_call("/api/agents", api_agents),
    ]
    assert [p["path"] for p in probes] == list(SELF_CHECK_PATHS)
    return probes


async def _flywheel_supervisor() -> None:
    infer = bind_infer_from_app(_upstream)
    await flywheel_run_loop(
        infer=infer,
        run_orchestra=run_orchestra,
        collect_probes=_collect_flywheel_probes,
        sleep=asyncio.sleep,
    )


def _ensure_flywheel_task() -> None:
    global _FLYWHEEL_TASK
    if _FLYWHEEL_TASK is None or _FLYWHEEL_TASK.done():
        _FLYWHEEL_TASK = asyncio.create_task(_flywheel_supervisor())


def _campaign_or_404(campaign_id: str) -> dict[str, Any]:
    campaign = get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@app.get("/api/campaigns")
def api_list_campaigns() -> dict[str, Any]:
    return {"campaigns": list_campaigns()}


@app.post("/api/campaigns")
async def api_create_campaign(
    request: Request,
    background: BackgroundTasks,
) -> dict[str, Any]:
    try:
        raw = await request.json()
    except Exception:
        raw = {}
    payload = raw if isinstance(raw, dict) else {}
    campaign = create_campaign(payload)
    if payload.get("launch") is not False:
        campaign["status"] = "running"
        upsert_campaign(campaign)
        background.add_task(_run_campaign_job, campaign["id"])
    return campaign


@app.post("/api/campaigns/{campaign_id}/launch")
def api_launch_campaign(campaign_id: str, background: BackgroundTasks) -> dict[str, Any]:
    campaign = _campaign_or_404(campaign_id)
    if campaign.get("status") in {"running"}:
        return campaign
    campaign["status"] = "running"
    upsert_campaign(campaign)
    background.add_task(_run_campaign_job, campaign_id)
    return get_campaign(campaign_id) or campaign


@app.get("/api/campaigns/{campaign_id}")
def api_get_campaign(campaign_id: str) -> dict[str, Any]:
    return _campaign_or_404(campaign_id)


@app.get("/api/flywheel")
def api_flywheel() -> dict[str, Any]:
    return flywheel_snapshot()


@app.post("/api/flywheel/start")
async def api_flywheel_start() -> dict[str, Any]:
    snap = flywheel_start()
    _ensure_flywheel_task()
    return snap


@app.get("/api/flywheel/stop")
@app.post("/api/flywheel/stop")
def api_flywheel_stop() -> dict[str, Any]:
    return flywheel_stop()


@app.get("/api/agents")
def api_agents() -> dict[str, Any]:
    return agents_snapshot()


@app.get("/api/agents/{category}")
def api_agent_category(category: str) -> dict[str, Any]:
    row = agents_snapshot_category(category)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown category")
    return row


@app.post("/api/agents/tick")
async def api_agents_tick() -> dict[str, Any]:
    return await agents_tick_all()


@app.get("/api/billing/config")
def api_billing_config() -> dict[str, Any]:
    return billing_public_config()


@app.get("/api/billing/entitlements")
def api_billing_entitlements(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_auth(authorization)
    return {"ok": True, "entitlements": billing_entitlements()}


@app.post("/api/billing/checkout")
async def api_billing_checkout(request: Request) -> JSONResponse:
    try:
        raw = await request.json()
    except Exception:
        raw = {}
    payload = raw if isinstance(raw, dict) else {}
    sku = str(payload.get("sku") or "campaign_launch")
    result = create_checkout_session(
        sku,
        campaign_id=str(payload["campaign_id"]) if payload.get("campaign_id") else None,
        customer_email=str(payload["email"]) if payload.get("email") else None,
        idempotency_key=(request.headers.get("idempotency-key") or None),
    )
    status = int(result.pop("status", 200 if result.get("ok") else 503))
    if not result.get("ok") and status == 503:
        body = not_configured_payload()
        body.update(result)
        return JSONResponse(content=body, status_code=503)
    return JSONResponse(content=result, status_code=status)


@app.post("/api/billing/subscribe")
async def api_billing_subscribe(request: Request) -> JSONResponse:
    try:
        raw = await request.json()
    except Exception:
        raw = {}
    payload = raw if isinstance(raw, dict) else {}
    result = create_checkout_session(
        "autonomous_console",
        customer_email=str(payload["email"]) if payload.get("email") else None,
        idempotency_key=(request.headers.get("idempotency-key") or None),
    )
    status = int(result.pop("status", 200 if result.get("ok") else 503))
    if not result.get("ok") and status == 503:
        body = not_configured_payload()
        body.update(result)
        return JSONResponse(content=body, status_code=503)
    return JSONResponse(content=result, status_code=status)


@app.post("/api/billing/usage")
async def api_billing_usage(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(authorization)
    try:
        raw = await request.json()
    except Exception:
        raw = {}
    payload = raw if isinstance(raw, dict) else {}
    return record_usage(
        int(payload.get("quantity") or 1),
        customer=str(payload["customer"]) if payload.get("customer") else None,
        campaign_id=str(payload["campaign_id"]) if payload.get("campaign_id") else None,
    )


@app.post("/api/billing/webhook")
async def api_billing_webhook(request: Request) -> JSONResponse:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = construct_event(payload, signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook signature or body invalid: {exc}") from exc
    if not isinstance(event, dict):
        event = dict(event)
    result = apply_event(event)
    return JSONResponse(content=result)


@app.get("/api/campaigns/{campaign_id}/events")
def api_campaign_events(campaign_id: str) -> dict[str, Any]:
    campaign = _campaign_or_404(campaign_id)
    return {
        "id": campaign["id"],
        "status": campaign.get("status"),
        "mode": campaign.get("mode"),
        "healed": campaign.get("healed"),
        "agent": campaign.get("agent") or "video-campaign",
        "cuts": campaign.get("cuts") or [],
        "events": campaign.get("events") or [],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=int(os.environ.get("HERMES_HOST_PORT") or "8080"))
