"""Console nav categories as independent agent variables."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategorySpec:
    id: str
    title: str
    goal: str
    user_prompt: str
    dry_run_summary: str


CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec(
        "overview",
        "Overview",
        "Summarize Research → Create → Optimize → Scale loop health and next action.",
        "Produce a 4-bullet operating snapshot: loop stage, flywheel health, top risk, next action.",
        "Overview DRY-RUN: loop on Improve; flywheel self-check continues; next action is a labeled campaign tick.",
    ),
    CategorySpec(
        "discovery",
        "Discovery",
        "Scan cross-platform opportunity signals and rank whitespace topics.",
        "Rank 3 high-velocity topics for AI education shorts with competition/velocity notes.",
        "Discovery DRY-RUN: Automation, Claude, Everyday Carry remain high-velocity whitespace.",
    ),
    CategorySpec(
        "knowledge",
        "Knowledge Graph",
        "Propose causal edges from topic → hook → publish → analytics.",
        "Name 3 causal edges Hermes should store after the last publish.",
        "Knowledge DRY-RUN: money-hooks → CTR; first-frame motion → retention; EDC niche → Shorts+TikTok compound.",
    ),
    CategorySpec(
        "campaigns",
        "Campaigns",
        "Draft the next video-campaign brief without launching paid APIs.",
        "Write a one-line niche, goal, and 20s vertical brief for the next autonomous campaign.",
        "Campaigns DRY-RUN: niche AI education · grow subscribers · one workflow per 20s cut.",
    ),
    CategorySpec(
        "orchestra",
        "Agent Orchestra",
        "Record organization events so Orchestra shows every category tick.",
        "Emit a one-line orchestra event describing this cycle's agent set.",
        "Orchestra DRY-RUN: 14 category agents ticked with max concurrency 3.",
    ),
    CategorySpec(
        "debugger",
        "AI Debugger",
        "Replay last inference mode, latency class, and fallback (LM Studio vs dry-run).",
        "State inference mode, whether /v1/models was reachable, and fallback label.",
        "Debugger DRY-RUN: inference unreachable at 127.0.0.1:1234 — labeled DRY-RUN, no hang.",
    ),
    CategorySpec(
        "studio",
        "Studio",
        "Compose the next scene stack (hook → proof → payoff) for an active cut.",
        "List a 5-beat scene stack with durations totaling ~20s.",
        "Studio DRY-RUN: Hook 3s → Problem 4s → Demo 6s → Proof 4s → CTA 3s.",
    ),
    CategorySpec(
        "evolution",
        "Evolution Lab",
        "Crown a winner and retire a loser from recent variants.",
        "Name one variant to crown and one intro to retire, with a one-line reason.",
        "Evolution DRY-RUN: crown thumbnail B; retire still first-frames.",
    ),
    CategorySpec(
        "analytics",
        "Analytics",
        "Forecast retention/RPM movement from the last loop step.",
        "Give a 30-day forecast sentence assuming the Improve loop stays on.",
        "Analytics DRY-RUN: channel Strong; CTR 6.8% and retention 54% if Improve holds.",
    ),
    CategorySpec(
        "memory",
        "Memory",
        "Write one causal lesson from the last publish into living memory.",
        "State one learned rule Hermes should reuse on the next campaign.",
        "Memory DRY-RUN: money hooks +23% CTR — reuse on first frame.",
    ),
    CategorySpec(
        "command",
        "Command Center",
        "Report gateway health: livez, readyz, inference backend, origin 8091.",
        "One line: origin, inference backend, and whether the process is live.",
        "Command DRY-RUN: origin http://127.0.0.1:8091 · lm_studio · livez ok.",
    ),
    CategorySpec(
        "publishing",
        "Publishing",
        "Queue the next Shorts/TikTok/Reels slot without uploading binaries.",
        "Name three queued titles and platforms for the next cycle.",
        "Publishing DRY-RUN: YouTube Short + TikTok + Reels queued (metadata only).",
    ),
    CategorySpec(
        "uploads",
        "Uploads",
        "Classify inbound brand kits/stills as graph nodes, not dead files.",
        "Describe how the next upload becomes a knowledge-graph node.",
        "Uploads DRY-RUN: drop zone maps stills → graph nodes before Studio.",
    ),
    CategorySpec(
        "settings",
        "Settings",
        "Confirm studio identity and OpenAI-compatible /v1 local defaults.",
        "State INFERENCE_BASE_URL default and that no paid APIs are required.",
        "Settings DRY-RUN: INFERENCE_BASE_URL=http://127.0.0.1:1234/v1 · local only.",
    ),
)


def category_ids() -> list[str]:
    return [c.id for c in CATEGORIES]


def get_spec(category: str) -> CategorySpec | None:
    key = (category or "").strip().lower()
    for spec in CATEGORIES:
        if spec.id == key:
            return spec
    return None
