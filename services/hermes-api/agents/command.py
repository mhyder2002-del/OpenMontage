"""Command Center category agent — report /livez and /readyz."""

from .catalog import get_spec
from .runner import run_spec

SPEC = get_spec("command")


def run() -> dict:
    assert SPEC is not None
    result = run_spec(SPEC)
    extra = " Gateway probes: GET /livez (process) and GET /readyz (deploy auth)."
    result["summary"] = f"{result.get('summary') or ''}{extra}".strip()
    result["probes"] = {"livez": "/livez", "readyz": "/readyz"}
    return result
