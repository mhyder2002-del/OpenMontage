# Backend Director — Hermes Hostinger

## When to Use
Build and deploy the Hermes API (`services/hermes-api`) to the Hostinger
domain, or run it locally when VPS credentials are missing.

## Prerequisites
| Layer | Resource |
|-------|----------|
| Tool | `hostinger_deploy` |
| Code | `services/hermes-api/` |
| Workflow | `.github/workflows/deploy-hostinger.yml` |
| Prior | `deploy_report` with tunnel decision |

## Process

### Step 1: Scaffold
```
hostinger_deploy.execute({
  "action": "scaffold",
  "domain": "<brief domain>"
})
```
This writes any missing gateway files under `services/hermes-api/`
(Dockerfile, compose, Caddyfile, `.env.example`) and runs
`docker compose config`. Confirm `compose_valid` is true (or docker is
absent, in which case files still exist). Docker HEALTHCHECK hits
`/livez` so a down GPU does not mark the container unhealthy. Production
TLS is the `tls` compose profile (`COMPOSE_PROFILES=tls` → Caddy 80/443).

Optional **MoneyPrinterTurbo** is a second compose profile — never required for
the API. Probe with `moneyprinter_turbo.execute({"action": "status"})`. If the
user wants campaign `mpt` live, they must set `MONEYPRINTER_ENABLED=true` and:

```
COMPOSE_PROFILES=moneyprinter docker compose -f services/hermes-api/docker-compose.yml up -d moneyprinter
```

Do not add `moneyprinter` to the default VPS `tls` profile. If MPT is down or
disabled, campaigns still complete: the `mpt` stage is labeled DRY-RUN. That is
the same contract as the OpenMontage `moneyprinter_turbo` tool.

### Step 2: Production env
Required on the VPS:
- `HERMES_API_KEY` (non-empty)
- `INFERENCE_BASE_URL` (NVIDIA vLLM or hosted API) **or** `LM_STUDIO_BASE_URL` (tunnel/studio fallback)
- `PUBLIC_DOMAIN` (e.g. `hermestudios.com`)
- Scale templates: `infra/hermes-scale/` (NVIDIA default; do not buy GPUs from the agent)

Refuse to mark `deployed: true` if the production key is empty.

### Step 3: Deploy
If `HOSTINGER_API_KEY` and `HOSTINGER_VM_ID` are set:
```
hostinger_deploy.execute({"action": "deploy", "domain": "..."})
```
Else run locally:
```
hostinger_deploy.execute({"action": "serve_local"})
```
and tell the user the GitHub Action path
(`.github/workflows/deploy-hostinger.yml` + hPanel API key + VM id).
Do not subscribe to a new VPS.

### Step 4: DNS
Do not set records here. The next stage is `dns` (`dns-director.md`).
Record the intended public URL on `deploy_report.backend.url`
(`https://hermestudios.com`). Map any `hermestudio.com` shorthand to that
canonical host.

### Step 5: Self-evaluate
| Criterion | Question |
|-----------|----------|
| Auth | Is HERMES_API_KEY required in production? |
| Compose | Does `docker compose config` succeed? |

### Step 6: Submit
Checkpoint `backend` `awaiting_human`. **END YOUR TURN**.

## Common Pitfalls
- Pushing an image that still proxies with auth disabled.
- Deploying the whole OpenMontage GPU stack to a tiny VPS (API-only).
