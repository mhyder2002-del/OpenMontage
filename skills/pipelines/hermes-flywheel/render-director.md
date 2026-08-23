# Render Director — Hermes Flywheel

## When to Use
You are the **Render** stage. You take a `script` + `scene_plan` from the Script
stage and execute one underlying OpenMontage pipeline to produce a rendered
individual. You do NOT invent a new renderer — you drive an existing pipeline
the normal, sanctioned way (read its manifest + director skills, use its tools,
self-review, checkpoint).

## Pipeline selection
Read `compatible_pipelines` from the `hermes-flywheel` manifest. Pick the base
pipeline by topic:
- conceptual / educational explainer → `animated-explainer`
- cinematic trailer → `cinematic`
- repurposed short-form → `clip-factory`
- presenter-led → `talking-head`

For the chosen base, follow its director skills for `assets → edit → compose`.
Reuse the SAME tools the base pipeline uses (no ad-hoc scripts). Record the
render in the project so Backlot shows it.

### Optional MoneyPrinterTurbo vs `video_selector`

`moneyprinter_turbo` is **optional**. Never fail the render because MPT is off.

| Path | When | How |
|------|------|-----|
| `video_selector` | Per-scene **T2V / I2V / stock** clips that will be edited into an OpenMontage compose (Remotion/HyperFrames/ffmpeg) | `video_selector.execute({prompt, operation})` — ranks real clip providers. MPT is **not** selector-routable. |
| `moneyprinter_turbo` | A **whole topic→short** (script + Edge TTS + stock B-roll + captions) as a flywheel individual or campaign companion | `moneyprinter_turbo.execute({"action": "status"})` then `{"action": "generate", "topic": "<niche>"}` |

Same env as the Hermes campaign `mpt` stage: `MONEYPRINTER_ENABLED`, `MONEYPRINTER_BASE_URL` (default `http://127.0.0.1:8088`), `MONEYPRINTER_MODE` (`http`/`cli`). Enable locally with `COMPOSE_PROFILES=moneyprinter docker compose -f services/hermes-api/docker-compose.yml up -d moneyprinter`.

**Self-heal:** If `get_status()` is not AVAILABLE, or generate returns `mode: dry_run` / `label: DRY-RUN`, log that on the artifact (`mpt_mode`, `mpt_reason`) and continue the base pipeline. Do not retry paid T2V as a silent substitute without a new `decision_log` entry.

### Skill-selection discipline (read first)
Before committing to a base pipeline, consult the **`video-media-skill-selector`**
skill (`skills/creative/video-media-skill-selector.md`). It encodes the catalog
discipline for choosing a Video & Media skill:
- Select around **source media + final platform** (planning / editing /
  transcription / audio / delivery).
- **Preflight a short representative clip** to test timing, codec, caption, and
  rights constraints before a full render.
- Confirm support for the required containers, codecs, resolutions, frame
  rates, channel layouts, caption formats; verify edits stay editable and
  traceable to source timestamps; check upload limits, processing location,
  retention, consent, and music/footage rights before sending source media.

## Process
### Step 1: Preflight
- `composition_validator` (required tool) on the composition before the expensive render. Fix any asset/duration mismatches.
- Check budget via `tools/cost_tracker.py`; reserve before paid calls.

### Step 2: Produce the artifact
Run assets → edit → compose. The output is a **rendered individual**: a video
file (if a runtime is available) AND a portable `artifact` payload the Score
stage scores. The artifact payload must include measurable fields:
```json
{
  "topic": "...", "pipeline": "animated-explainer",
  "duration_seconds": 60.0, "target_duration_seconds": 60.0,
  "word_count": 140, "target_word_count": 140,
  "cost_usd": 1.33, "budget_usd": 5.0,
  "sections": [{"label": "...", "enhancement_cues": [...], "text": "..."}],
  "retention_anchors": 3, "novelty_flag": false,
  "render_path": "projects/<name>/renders/gen1/v0.mp4",
  "notes": "..."
}
```

### Step 3: Validate
- `composition_validator` passes.
- `artifact.duration_seconds` within ~5% of target.
- Render file exists (or, if no runtime available, mark `render_path` as `dry_run` and note it — the loop still scores the artifact).

### Step 4: Submit
Persist `render_report` + `artifact`, then END YOUR TURN at the checkpoint
(autonomous mode proceeds to Score).

## Common Pitfalls
- Skipping `composition_validator` then producing a broken/truncated render.
- Skipping the skill-selection preflight: running a full render before verifying
  codec/caption/rights on a short clip (per `video-media-skill-selector`).
- Over-spending: a generation has `budget_usd` (manifest `budget_default_usd` / `population_size`). Reserve first.
- Emitting an artifact without the measurable fields — `breed_scorer` can't score what it can't measure.
- Treating this as a new pipeline. It is a base pipeline's render, parameterized by the flywheel.

## Gate Reminder
Autonomous (`human_approval_default: false`). Checkpoint `status="auto"`, END TURN.
