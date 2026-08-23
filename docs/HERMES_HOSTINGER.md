# Hermes Hostinger — local LM Studio + public API + YouTube

Wire a **free local** LM Studio server to a **public Hostinger domain**
(`hermestudios.com`) and optionally upload OpenMontage renders to YouTube.

This is not a video compose pipeline. Renders still come from `hermes-flywheel`
or a base OpenMontage pipeline.

```
Mac LM Studio  :1234/v1          (studio / fallback only)
      │
      │  optional Cloudflare Tunnel
      ▼
Hostinger VPS  services/hermes-api
      https://hermestudios.com
      │
      ▼
NVIDIA vLLM or hosted /v1        (infra/hermes-scale)
```

Scale templates (do not purchase from the agent): `infra/hermes-scale/`
Planning session: `cse_01PrUJjvaENr4zTMsM1UB4Bb`.

## Files
| Path | Role |
|------|------|
| `pipeline_defs/hermes-hostinger.yaml` | Manifest |
| `skills/pipelines/hermes-hostinger/` | Stage directors |
| `skills/creative/hermes-hostinger.md` | Driver skill |
| `.cursor/skills/hermes-hostinger-pipeline/` | Cursor skill |
| `tools/llm/lmstudio.py` | Local OpenAI-compatible client |
| `tools/publishers/youtube_upload.py` | YouTube CLI / tool |
| `tools/publishers/hostinger_deploy.py` | Scaffold + VPS gate |
| `services/hermes-api/` | FastAPI backend + landing page + Caddy TLS profile |
| `infra/hermes-scale/` | NVIDIA/AMD/hosted/Mac env + vLLM compose |
| `.github/workflows/deploy-hostinger.yml` | Hostinger VPS deploy |

## Run locally
```bash
python scripts/hermes_hostinger.py preflight
python scripts/hermes_hostinger.py serve
# http://127.0.0.1:8080/health
```

Start LM Studio's local server on port 1234 first if you want `/v1` to proxy.

Gateway liveness is `GET /livez` (no upstream ping). `GET /health` still
reports inference reachability. Production TLS:

```bash
COMPOSE_PROFILES=tls docker compose -f services/hermes-api/docker-compose.yml up -d
```

## Deploy to Hostinger
1. Canonical host is `hermestudios.com` (map `hermestudio.com`; do not buy it).
2. Point DNS A/@ and A/www at the VPS: `python scripts/hermes_hostinger.py dns --apply --ipv4 <VPS_IPV4>`.
3. Add GitHub secrets `HOSTINGER_API_KEY`, `HERMES_API_KEY`, `LM_STUDIO_BASE_URL`
   and variable `HOSTINGER_VM_ID`.
4. Run the **Deploy Hermes API to Hostinger** workflow.

Do not buy a VPS or plan from the agent. Local `serve` is enough to verify.

## YouTube
```bash
python -m tools.publishers.youtube_upload --status
python -m tools.publishers.youtube_upload --file renders/final.mp4 --title "..." --dry-run
```
Default privacy is **unlisted**. Needs `YOUTUBE_CLIENT_SECRETS_FILE`.

## MoneyPrinterTurbo (optional)

Canonical repo: [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) (MIT).
Hermes does **not** vendor the full tree. See `third_party/MoneyPrinterTurbo/README.md`.

```bash
# local API on :8088 — profile keeps default VPS compose unchanged
cd services/hermes-api
COMPOSE_PROFILES=moneyprinter docker compose up -d moneyprinter
export MONEYPRINTER_ENABLED=true
export MONEYPRINTER_BASE_URL=http://127.0.0.1:8088
```

Campaign stage `mpt` POSTs `{video_subject}` to `/api/v1/videos`, polls `/api/v1/tasks/{id}`,
and writes `video_paths` onto campaign cuts. If MPT is off or down, that stage is labeled
**DRY-RUN** and the rest of the orchestra still completes. Publishing agent appends those paths.
