---
name: mcp-toolkit-routing
description: >-
  How Hermes/OpenMontage subagents should pick Cursor MCP namespaces without
  buying paid MCP or logging tokens. Use before CallDynamicTool.
---

# MCP toolkit routing (unpaid)

Inspect schemas with `GetDynamicTools` first. Never paste tokens into logs or chat.

## Prefer (no purchase)

| Namespace | When |
|-----------|------|
| `cursor-ide-browser` | Console UX / hermestudios.com visual verify |
| `cursor-app-control` | Workspace root, open resource — not chat rename unless asked |
| `cursor` `GenerateImage` | Only if the user asked for an image |
| `plugin-cloudflare-cloudflare-docs` | Docs search only (no paid Cloudflare plan) |

## Skip unless already authenticated and needed

`plugin-stripe-stripe`, `plugin-linear-linear`, `plugin-figma-figma`,
`plugin-notion-workspace-notion`, `plugin-datadog-datadog`,
Cloudflare bindings/builds/observability.

If `namespaceStatus` is `needsAuth` or `error`, do not call `mcp_auth` to
unlock a **paid** product. Document the gap; continue with curl + repo tools.

## Hermes Rule Zero

Never call `video_compose.execute` from `services/hermes-api`. Production
video goes through OpenMontage pipelines.
