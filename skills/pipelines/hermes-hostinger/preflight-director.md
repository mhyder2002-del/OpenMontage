# Preflight Director — Hermes Hostinger

## When to Use
Probe LM Studio, Hostinger deploy credentials, and YouTube OAuth **before**
opening a tunnel or pushing Docker.

## Prerequisites
| Layer | Resource |
|-------|----------|
| Tools | `lmstudio` (required), `hostinger_deploy`, `youtube_upload` |
| Prior | `brief` |
| Schema | `schemas/artifacts/deploy_report.schema.json` |

## Process

### Step 1: LM Studio
```
lmstudio.execute({"action": "health"})
lmstudio.execute({"action": "models"})
```
Record `base_url`, `reachable`, and loaded model ids. Unreachable is
**degraded**, not a crash — the Mac server may be stopped. Tell the user
to start LM Studio's local server on port 1234.

### Step 2: Hostinger
```
hostinger_deploy.execute({"action": "status"})
```
Missing `HOSTINGER_API_KEY` / `HOSTINGER_VM_ID` is expected on a fresh
machine. The backend can still run locally via Docker. Do not purchase a
VPS.

### Step 3: YouTube
If the brief includes upload, run `youtube_upload` with `action: "status"`.
Missing client secrets → degraded with install notes from the tool.

### Step 3b: Optional MoneyPrinterTurbo
If the brief includes campaign shorts, probe `moneyprinter_turbo` with
`action: "status"`. Unset `MONEYPRINTER_ENABLED` or unreachable `:8088` is
**degraded**, not blocked — record it on `deploy_report.checks`. Do not make
MPT a required tool.

### Step 4: Write deploy_report
`status`: `healthy` if LM Studio reachable; `degraded` if not; `blocked`
only if the brief required a public deploy and Docker is unavailable.

### Step 5: Self-evaluate
| Criterion | Question |
|-----------|----------|
| Honesty | Are unavailable tools reported as such? |
| No spend | Did we avoid paid fallbacks? |

### Step 6: Submit
Checkpoint `preflight` `awaiting_human`. **END YOUR TURN**.

## Common Pitfalls
- Claiming the cloud agent can hit `127.0.0.1:1234` (it cannot).
- Treating missing Hostinger keys as a hard stop for local `serve`.
