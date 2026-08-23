"""Discovery category agent."""

from .catalog import get_spec
from .runner import run_spec

SPEC = get_spec("discovery")


def run() -> dict:
    assert SPEC is not None
    return run_spec(SPEC)
