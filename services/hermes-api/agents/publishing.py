"""Publishing category agent — queue metadata; attach optional MoneyPrinterTurbo paths."""

from __future__ import annotations

from .catalog import get_spec
from .runner import run_spec

SPEC = get_spec("publishing")


def _mpt_note() -> str:
    try:
        from campaigns import list_campaigns
        from moneyprinter import enabled
    except Exception:
        return ""
    campaigns = list_campaigns()
    latest = campaigns[0] if campaigns else None
    if not isinstance(latest, dict):
        if enabled():
            return " MoneyPrinterTurbo is enabled; no campaign outputs yet."
        return " MoneyPrinterTurbo optional (DRY-RUN until MONEYPRINTER_ENABLED + API)."
    mpt = latest.get("moneyprinter") if isinstance(latest.get("moneyprinter"), dict) else {}
    paths = mpt.get("video_paths") or []
    label = mpt.get("label") or "unset"
    return f" Last campaign MPT {label}: {paths[:3]}"


def run() -> dict:
    assert SPEC is not None
    result = run_spec(SPEC)
    note = _mpt_note()
    if note:
        result["summary"] = f"{result.get('summary') or ''}{note}".strip()
        result["moneyprinter"] = note.strip()
    return result
