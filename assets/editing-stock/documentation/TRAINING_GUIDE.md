# Training and evaluation roadmap

**Stage 1: No weight training** — Use deterministic caption and visual preset plus script-to-EDL candidate generation.
**Stage 2: Supervised examples** — For each edited video capture source transcript, aligned words, edit cuts, reason tags, candidates, selected assets, effect parameters, rejected suggestions, and human review. Store license pointers; do not rehost external stock.
**Stage 3: Candidate ranker** — Train retrieval/ranking on (script span, available candidates, user-chosen asset) pairs; split evaluation by VIDEO to avoid data leakage.
**Stage 4: Edit policy** — Learn probability of graphic insert, A-roll return, hard cut, zoom, and overlay; keep duration and face-safe constraints deterministic.
**Stage 5: Evaluate** — Human approval, semantic relevance, timing tolerance, dialogue continuity, render failures, CPU render time, aesthetic consistency, licensing audit.

Required production interface: `make_edit_plan(raw_video, optional_script, asset_index, style_preset) -> validated_edit_decision_list`. Do not generate stock from unlicensed reference frames or assume the reference contains reusable third-party clip rights.
