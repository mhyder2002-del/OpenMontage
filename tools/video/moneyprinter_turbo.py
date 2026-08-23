"""OpenMontage tool: POST a topic to MoneyPrinterTurbo (or labeled DRY-RUN)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

_HERMES = Path(__file__).resolve().parents[2] / "services" / "hermes-api"
if str(_HERMES) not in sys.path:
    sys.path.insert(0, str(_HERMES))


def _adapter():
    import moneyprinter as mpt

    return mpt


class MoneyPrinterTurbo(BaseTool):
    name = "moneyprinter_turbo"
    version = "1.0.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "moneyprinterturbo"
    # Topic→short orchestra (script+TTS+stock+captions). Not a clip T2V provider.
    selector_routable = False
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies: list[str] = []
    install_instructions = (
        "Optional local short-form generator (MIT, harry0703/MoneyPrinterTurbo).\n"
        "COMPOSE_PROFILES=moneyprinter docker compose -f services/hermes-api/docker-compose.yml "
        "up -d moneyprinter\n"
        "Or clone https://github.com/harry0703/MoneyPrinterTurbo and set "
        "MONEYPRINTER_BASE_URL + MONEYPRINTER_ENABLED=true.\n"
        "See third_party/MoneyPrinterTurbo/README.md. No paid APIs required for Edge TTS."
    )
    agent_skills = ["create-video"]

    capabilities = ["topic_to_short", "status"]
    supports = {"http": True, "cli": True, "dry_run": True, "free": True}
    best_for = ["topic → script + TTS + stock B-roll + captions short"]
    not_good_for = ["atelier / pipeline-gated OpenMontage compose"]

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, network_required=True)

    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "generate"]},
            "topic": {"type": "string"},
            "niche": {"type": "string"},
        },
    }

    def get_status(self) -> ToolStatus:
        mpt = _adapter()
        if not mpt.enabled():
            return ToolStatus.DEGRADED
        probe = mpt.available()
        return ToolStatus.AVAILABLE if probe.get("ok") else ToolStatus.UNAVAILABLE

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        mpt = _adapter()
        topic = str(inputs.get("topic") or inputs.get("niche") or "demo")
        return mpt.dry_run_result(topic, "tool dry_run — no HTTP/CLI call")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        mpt = _adapter()
        action = str(inputs.get("action") or "generate")
        if action == "status":
            probe = mpt.available()
            return ToolResult(
                success=True,
                data={
                    "enabled": mpt.enabled(),
                    "mode": mpt.mode(),
                    "base_url": mpt.base_url(),
                    "probe": probe,
                    "canonical_repo": mpt.CANONICAL_REPO,
                },
            )
        topic = str(inputs.get("topic") or inputs.get("niche") or "").strip()
        data = mpt.generate(topic)
        paths = list(data.get("video_paths") or [])
        return ToolResult(
            success=bool(data.get("ok")),
            data=data,
            artifacts=paths,
        )
