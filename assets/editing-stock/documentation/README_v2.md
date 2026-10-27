# OpenMontage Editing Stock Library v2

This is an additive package compatible with the v1 directory. It contains **original generated assets**, not licensed third-party stock footage. The MP4 loops are simple 360x640 placeholder/background motion graphics, **not cinematic camera footage**. Use them as explainer transitions and motion design accents.

## Installation
1. Extract this ZIP into your OpenMontage project, e.g. `assets/editing-stock/`.
2. Run `python assets/editing-stock/scripts/validate_v2.py`.
3. Index `catalog/assets.json` by id, tags and script_signals.
4. Load `presets/editing_decision_rules_v2.json` into your existing edit planner, but review actual timing against transcribed speech.
5. Generate edit decision lists, resolve relative file paths under the asset root, build compositions in Remotion, mix sounds through FFmpeg, then export.

## Script workflow
Transcribe -> sentence / word alignment -> identify narrative beats -> retrieve candidate assets -> enforce cooldown / license / avoidance rules -> human review -> render -> automated QA.

## What this package cannot do
It does not fine-tune model weights, automatically integrate with an unknown source code repository, or include downloadable third-party B-roll. It does not prove visual equivalence with the original reference. All cuts require real script timings.

## Audio note
Sound effects are short synthesized cues. Normalize audio and keep them below narration loudness.
