---
name: hermes-grok-health-loop
description: >-
  Recurring Grok operator loop for hermestudios.com health, flywheel origin,
  unpaid self-heal, skill/MCP/subagent tightening. Use on AGENT_LOOP_TICK_grok_site_health.
---

# Hermes Grok health loop

You are the Grok-backed background operator. A one-shot curl is not the job.
Each wake must probe, decide, log, optionally patch unpaid-path issues, then
leave the loop armed.

## Interval

Default **10 minutes** (`sleep 600`). Tighten only for local-only probes.

Sentinel: `AGENT_LOOP_TICK_grok_site_health`

See ticks: `services/hermes-api/data/grok-health-loop.jsonl`

## Each tick (short probes)

1. `python3 services/hermes-api/scripts/grok_health_tick.py` (HTTP codes only).
2. Origins: `https://hermestudios.com` (canonical), `www`, local `http://127.0.0.1:8091`.
3. Paths: `/livez` `/readyz` `/health` `/console` `/api/flywheel`.
4. Record flywheel `origin`. Production must advertise `https://hermestudios.com`.
5. Never print `HERMES_API_KEY`, `.env`, tokens, or Authorization headers.

## Fail / fix (unpaid only)

| Signal | Action |
|--------|--------|
| livez not 200 | Process down. Restart **local** uvicorn only if **this** agent started it. Do not clobber VPS tarball/PR deploy. |
| readyz 503 + `auth_configured: false` | Production refuses traffic without key. Observe deploy agent; do not buy Postgres/ngrok/Stripe. Log and wait. |
| health 200 but origin is `:8091` on public host | Origin bug — coordinate, do not fight mid-deploy. |
| flywheel `running: false` on prod | Expected unless auto-start. Do not POST start on production without auth. |
| LM Studio `:1234` down | Agents stay DRY-RUN. Do not call paid APIs. |
| MPT `:8088` down | Stay DRY-RUN. Never `video_compose.execute` from hermes-api (Rule Zero). |

Do **not** force-push, edit `hermes_scaffolding_next_8f72ea48.plan.md`, or interrupt another agent's cherry-pick/VPS deploy.

## Productization (small diffs)

Console UX, health ladder, Discovery/KG, Command Center. No Next.js rewrite.

Tighten Command Center prompts: origin + livez/readyz meaning in one line.

## MCP / toolkits (conceptual)

Do not purchase paid MCP. Prefer free/local:

- `cursor-ide-browser` — verify console UX after UI changes.
- `cursor-app-control` — do not rename chats unless asked.
- Cloudflare/Stripe/Linear/Figma/Notion/Datadog — skip unless authenticated **and** unpaid.
- Native `cursor` `GenerateImage` — only if user asked for an image.

Discover tools with `GetDynamicTools`; never log MCP tokens.

## Subagent quality

Shorter health probes, HTTP codes only, explicit wait-vs-heal. Re-arm the loop every tick.
