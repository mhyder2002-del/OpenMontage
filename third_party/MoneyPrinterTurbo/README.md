# MoneyPrinterTurbo (Hermes integration)

Canonical upstream: **[harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)** (MIT).

This directory is an **attribution + install stub**, not a vendored copy of the
full upstream tree (keeps OpenMontage deploys small). License text is in
[`LICENSE`](LICENSE).

Harry0703/MoneyPrinterTurbo turns a **topic** into a short video (script, TTS,
stock/B-roll, captions). Hermes calls it over HTTP (`POST /api/v1/videos`) or
optionally via `cli.py`. If MPT is not running, Hermes self-heals to a labeled
**DRY-RUN** and still finishes the campaign.

## Install / run locally

**Option A — official Docker image (preferred)**

From `services/hermes-api` (does **not** start on default VPS compose):

```bash
# first time: copy upstream config if you clone the repo
COMPOSE_PROFILES=moneyprinter docker compose up -d moneyprinter
```

- API / docs: `http://127.0.0.1:8088/docs` (host port `MONEYPRINTER_HOST_PORT`)
- WebUI: `http://127.0.0.1:8501`

Or follow upstream:

```bash
git clone https://github.com/harry0703/MoneyPrinterTurbo.git
cd MoneyPrinterTurbo
cp config.example.toml config.toml   # optional; configure in WebUI
docker compose -f docker-compose.release.yml up
```

**Option B — clone here and run CLI / API**

```bash
git clone https://github.com/harry0703/MoneyPrinterTurbo.git third_party/MoneyPrinterTurbo/src
cd third_party/MoneyPrinterTurbo/src
# Python 3.11+: uv sync --frozen   or  python -m venv .venv && pip install -r requirements.txt
uv run python main.py                # API on :8080
# or: uv run python cli.py --video-subject "How AI is changing everyday life"
```

Point Hermes at it:

```bash
export MONEYPRINTER_ENABLED=true
export MONEYPRINTER_BASE_URL=http://127.0.0.1:8088
# optional CLI:
# export MONEYPRINTER_MODE=cli
# export MONEYPRINTER_CLI=third_party/MoneyPrinterTurbo/src/cli.py
# export MONEYPRINTER_WORKDIR=third_party/MoneyPrinterTurbo/src
```

No paid APIs are required for Edge TTS. Stock footage keys (Pexels, etc.) are
configured **inside MPT**, not committed from OpenMontage.

## License note

MPT itself is MIT (Copyright 2024 Harry). Stock clips, music, and generated
scripts remain subject to **their** licenses — review before commercial publish.
