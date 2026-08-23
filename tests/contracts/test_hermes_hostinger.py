"""Contract tests for the Hermes Hostinger pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.pipeline_loader import get_stage_order, get_stage_skill, list_pipelines, load_pipeline
from schemas.artifacts import validate_artifact


def test_manifest_loads_and_is_listed():
    manifest = load_pipeline("hermes-hostinger")
    assert manifest["name"] == "hermes-hostinger"
    assert "hermes-hostinger" in list_pipelines()
    assert get_stage_order(manifest) == [
        "idea",
        "preflight",
        "tunnel",
        "backend",
        "dns",
        "publish",
        "verify",
    ]


def test_director_skills_exist():
    manifest = load_pipeline("hermes-hostinger")
    for stage in manifest["stages"]:
        skill = get_stage_skill(manifest, stage["name"])
        path = PROJECT_ROOT / "skills" / f"{skill}.md"
        assert path.is_file(), path
        body = path.read_text(encoding="utf-8")
        assert "## When to Use" in body
        assert "## Common Pitfalls" in body


def test_deploy_report_schema():
    validate_artifact(
        "deploy_report",
        {
            "version": "1.0",
            "target_domain": "hermestudios.com",
            "status": "planned",
            "lm_studio": {
                "base_url": "http://127.0.0.1:1234/v1",
                "reachable": False,
            },
            "inference": {
                "backend": "vllm",
                "base_url": "http://127.0.0.1:8000/v1",
                "reachable": False,
                "phase": "1",
            },
            "checks": [{"name": "lmstudio", "ok": False, "detail": "server stopped"}],
        },
    )


def test_scale_config_files_exist():
    root = PROJECT_ROOT / "infra" / "hermes-scale"
    assert (root / "README.md").is_file()
    assert (root / "env" / "gateway.env.example").is_file()
    assert (root / "env" / "inference-nvidia.env.example").is_file()
    assert (root / "env" / "inference-hosted.env.example").is_file()
    assert (root / "compose" / "docker-compose.vllm.yml").is_file()
    assert (PROJECT_ROOT / "services" / "hermes-api" / "Caddyfile").is_file()
    assert (PROJECT_ROOT / "services" / "hermes-api" / ".env.example").is_file()
    manifest = load_pipeline("hermes-hostinger")
    assert manifest["metadata"]["inference"]["planning_session"] == "cse_01PrUJjvaENr4zTMsM1UB4Bb"


def test_no_compose_stage():
    names = [s["name"] for s in load_pipeline("hermes-hostinger")["stages"]]
    assert "compose" not in names


def test_optional_moneyprinter_on_preflight_and_backend():
    manifest = load_pipeline("hermes-hostinger")
    pre = next(s for s in manifest["stages"] if s["name"] == "preflight")
    backend = next(s for s in manifest["stages"] if s["name"] == "backend")
    assert "moneyprinter_turbo" in pre["optional_tools"]
    assert "moneyprinter_turbo" in backend["optional_tools"]
    assert "moneyprinter_turbo" not in (backend.get("required_tools") or [])


def test_preflight_checkpoint_roundtrip(tmp_path):
    from lib.checkpoint import read_checkpoint, write_checkpoint

    report = {
        "version": "1.0",
        "target_domain": "hermestudios.com",
        "status": "degraded",
    }
    write_checkpoint(
        tmp_path,
        "hermes-api",
        "preflight",
        "awaiting_human",
        {"deploy_report": report},
        pipeline_type="hermes-hostinger",
        human_approval_required=True,
    )
    cp = read_checkpoint(tmp_path, "hermes-api", "preflight")
    assert cp["stage"] == "preflight"
    assert cp["artifacts"]["deploy_report"]["target_domain"] == "hermestudios.com"
