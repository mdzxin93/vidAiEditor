# OpenMontage v3 — Intelligent Editing Decision Planner

## Purpose
Rank assets using script meaning and your cinematic-explainer style guide. Builds an EDL that can be consumed by the existing rendering system. The packaged library remains self-contained, CPU compatible, and does not require an API key.

## Install
Unzip the library into `OpenMontage/assets/editing-stock/`. From that folder:

```bash
python scripts/test_v3.py
python scripts/semantic_edit_planner.py scripts/example_script.txt --output edit_plan_v3.json
python scripts/semantic_edit_planner.py scripts/example_transcript.json --output timed_plan.json
```

For optional stronger semantic retrieval install `sentence-transformers` in your environment, then append `--semantic`. This may download a model from Hugging Face on first use; standard offline BM25 mode never downloads anything.

## Faster-Whisper input
Export timestamped segments to a JSON file in the format of `scripts/example_transcript.json`. The planner understands seconds, not milliseconds. For reliable shot placement pass your real transcription timestamps. Plain-text timings are estimates and MUST be aligned before render.

## Renderer contract
EDL `events` are ordered, and use `a_roll` or `b_roll_overlay`. Each b-roll has a relative `asset_path`; concatenate with the library installation root. The renderer should honor `start_s` / `end_s` on the source timeline, keep original speech playing underneath, show illustrations over the original shot where appropriate, and apply its preset animation with `transition=hard_cut`. `sfx` values are suggestions only; don't add by default unless verified against the voice track. Do not stretch an entire source video to match a selected event.

## Guardrails
Assets are locally packaged and tagged original_in_package. Stock-provider URLs in the catalog do NOT represent downloaded or licensed assets. Review low-confidence choices. Repeated assets incur penalties and a cooldown. The planner is a ranker, not a fine-tuned model, and the machine-learning model on your own device is unchanged. To improve quality, curate script→approved-asset examples and introduce a learned reranker when you have sufficient data.
