"""Campaigns category agent (not campaigns.py store)."""

from .catalog import get_spec
from .runner import run_spec

SPEC = get_spec("campaigns")


def run() -> dict:
    assert SPEC is not None
    return run_spec(SPEC)
