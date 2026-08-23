"""Uploads category agent."""

from .catalog import get_spec
from .runner import run_spec

SPEC = get_spec("uploads")


def run() -> dict:
    assert SPEC is not None
    return run_spec(SPEC)
