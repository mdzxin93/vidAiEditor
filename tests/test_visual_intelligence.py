"""Automated Test Suite for Phase 7: Context-Aware B-Roll & Visual Intelligence.

Verifies:
- Motion design system layout safe areas and typography tokens
- Intelligent B-roll library indexing, candidate scoring, and duplicate suppression
- Visual candidate quality scorer across mathematical dimensions
- Semantic visual planner grounded treatment selection (stats, process flows, feature cards, callouts, B-roll)
- Script-to-visual synchronization and temporal pacing rest enforcement
- Autonomous editor integration with schema validation
"""

from __future__ import annotations

import pytest
from pathlib import Path

from lib.ai.autonomous_editor import AutonomousEditingPlanner
from lib.ai.broll_selector import BRollSelector, IndexedMediaAsset
from lib.ai.motion_design_system import AspectRatio, MotionDesignSystem
from lib.ai.providers.base import VideoUnderstandingResult, ObservationItem
from lib.ai.semantic_visual_planner import SemanticVisualPlanner, VisualEvent, SemanticVisualPlan
from lib.ai.visual_scorer import VisualCandidateScorer, VisualScoreBreakdown


def test_motion_design_system_tokens_and_constraints():
    """Verify motion design system safe areas, typography tokens, and duration presets."""
    safe_916 = MotionDesignSystem.get_safe_area("9:16")
    assert safe_916["width"] == 1080
    assert safe_916["height"] == 1920
    assert safe_916["margin_top"] >= 50
    assert safe_916["margin_bottom"] >= 400  # Subtitle safe margin
    assert safe_916["overlay_max_height"] <= 400

    safe_169 = MotionDesignSystem.get_safe_area("16:9")
    assert safe_169["width"] == 1920
    assert safe_169["height"] == 1080

    theme = MotionDesignSystem.resolve_color_theme("#203A47")
    assert theme["accent"] == "#203A47"
    assert "background" in theme

    assert "display" in MotionDesignSystem.TYPOGRAPHY
    assert "stat_hit" in MotionDesignSystem.DURATIONS
    assert "snappy" in MotionDesignSystem.SPRINGS


def test_broll_selector_indexing_and_scoring():
    """Verify B-roll selector indexes local media, scores relevance, and handles duplicates."""
    selector = BRollSelector()
    indexed = selector.index_media_library()
    assert len(indexed) > 0, "B-roll selector should index available local assets"

    # Verify metadata fields
    first_asset = indexed[0]
    assert isinstance(first_asset, IndexedMediaAsset)
    assert first_asset.width > 0
    assert first_asset.height > 0
    assert len(first_asset.tags) > 0
    assert first_asset.license == "authorized_local_project_asset"

    # Test scoring with relevant keyword
    test_phrase = "Let's review the technical demo and software architecture"
    score = selector.compute_relevance_score(first_asset, test_phrase, target_aspect="9:16")
    assert 0.0 <= score <= 1.0

    # Test matching against transcript
    transcript = [
        {"word": "Let's", "start": 0.5, "end": 0.8},
        {"word": "focus", "start": 2.2, "end": 2.7},
        {"word": "on", "start": 2.7, "end": 2.9},
        {"word": "the", "start": 2.9, "end": 3.1},
        {"word": "preview", "start": 3.1, "end": 3.6},
        {"word": "demo.", "start": 3.6, "end": 4.1},
    ]
    placements = selector.match_broll_for_transcript(transcript, video_duration=10.0, target_max_placements=1)
    assert isinstance(placements, list)
    if placements:
        bp = placements[0]
        assert bp.start_seconds >= 2.0  # Protected intro
        assert bp.end_seconds > bp.start_seconds
        assert bp.relevance_score >= 0.60
        assert bp.license == "authorized_local_project_asset"


def test_visual_candidate_scorer_interpretability():
    """Verify VisualCandidateScorer produces interpretable breakdowns and enforces rest."""
    scorer = VisualCandidateScorer(min_rest_interval=2.5)

    # Rest interval satisfied: stat_card on metric should score high
    breakdown_good = scorer.evaluate_candidate(
        treatment_type="stat_card",
        moment_type="metric",
        time_since_last_visual=4.0,
        speaker_framing="medium_close_up",
        has_face_in_overlay_zone=False,
    )
    assert breakdown_good.final_score >= 0.75
    assert breakdown_good.semantic_relevance >= 0.90
    assert breakdown_good.timing_suitability >= 0.80

    # Rest interval violated (only 0.8s since last visual): stat_card score degrades
    breakdown_violated = scorer.evaluate_candidate(
        treatment_type="stat_card",
        moment_type="metric",
        time_since_last_visual=0.8,
        speaker_framing="medium_close_up",
        has_face_in_overlay_zone=False,
    )
    assert breakdown_violated.final_score < breakdown_good.final_score
    assert breakdown_violated.timing_suitability < 0.30

    # Negative selection ('none') should score high when rest interval is violated!
    breakdown_none = scorer.evaluate_candidate(
        treatment_type="none",
        moment_type="metric",
        time_since_last_visual=0.8,
        speaker_framing="medium_close_up",
        has_face_in_overlay_zone=False,
    )
    assert breakdown_none.final_score >= 0.85
    assert breakdown_none.timing_suitability >= 0.90


def test_semantic_visual_planner_treatment_selection():
    """Verify SemanticVisualPlanner extracts metrics, punchlines, and processes correctly."""
    planner = SemanticVisualPlanner(min_rest_interval=2.0)

    transcript = [
        {"word": "Most", "start": 0.5, "end": 0.8},
        {"word": "people", "start": 0.8, "end": 1.1},
        {"word": "lose", "start": 1.1, "end": 1.4},
        {"word": "40%", "start": 1.4, "end": 1.8},
        {"word": "of", "start": 1.8, "end": 2.0},
        {"word": "their", "start": 2.0, "end": 2.2},
        {"word": "focus.", "start": 2.2, "end": 2.6},
        {"word": "The", "start": 5.0, "end": 5.2},
        {"word": "golden", "start": 5.2, "end": 5.6},
        {"word": "protocol", "start": 5.6, "end": 6.1},
        {"word": "is", "start": 6.1, "end": 6.3},
        {"word": "deep", "start": 6.3, "end": 6.6},
        {"word": "work", "start": 6.6, "end": 7.0},
        {"word": "blocks.", "start": 7.0, "end": 7.4},
    ]

    plan = planner.plan_visuals(
        transcript=transcript,
        video_duration=12.0,
        user_instruction="Use clean visuals and transfer deliberate pacing",
    )

    assert isinstance(plan, SemanticVisualPlan)
    assert plan.total_visuals_placed >= 1
    assert len(plan.audit_records) > 0

    treatments = [v.treatment_type for v in plan.visual_events]
    # Should include stat_card (for 40%) or callout (for golden protocol)
    assert any(t in treatments for t in ("stat_card", "callout", "process_flow"))

    # Verify stat_card includes trend indicators if present
    for ve in plan.visual_events:
        assert ve.start_seconds >= 0.5
        assert ve.end_seconds <= 12.0
        assert ve.relevance_score >= 0.58
        if ve.treatment_type == "stat_card":
            assert "stat" in ve.parameters


def test_visual_planner_instruction_priority_override():
    """Verify Tier 1 user instruction to suppress graphics limits visual events."""
    planner = SemanticVisualPlanner(min_rest_interval=2.5)

    transcript = [
        {"word": "We", "start": 0.5, "end": 0.8},
        {"word": "saw", "start": 0.8, "end": 1.0},
        {"word": "-40%", "start": 1.0, "end": 1.5},
        {"word": "and", "start": 4.0, "end": 4.2},
        {"word": "90", "start": 4.2, "end": 4.5},
        {"word": "minutes", "start": 4.5, "end": 5.0},
    ]

    # User explicitly instructs minimal graphics
    plan_minimal = planner.plan_visuals(
        transcript=transcript,
        video_duration=10.0,
        user_instruction="Use very few graphics and keep it completely uncluttered",
    )

    assert plan_minimal.total_visuals_placed <= 1


def test_autonomous_editor_end_to_end_phase7_integration():
    """Verify AutonomousEditingPlanner produces valid semantic_visual_plan and schema-compliant edit decisions."""
    planner = AutonomousEditingPlanner()

    understanding = VideoUnderstandingResult(
        observations=[
            ObservationItem(
                id="obs_1",
                start_seconds=0.0,
                end_seconds=15.0,
                category="subject",
                description="Speaker in center",
                confidence=0.95,
            )
        ],
        framing="medium_close_up",
        overlay_safe_region="upper_third",
        provider_name="heuristic_engine",
    )

    transcript = [
        {"word": "Our", "start": 0.5, "end": 0.8},
        {"word": "revenue", "start": 0.8, "end": 1.2},
        {"word": "grew", "start": 1.2, "end": 1.5},
        {"word": "+120%", "start": 1.5, "end": 2.0},
        {"word": "under", "start": 2.0, "end": 2.3},
        {"word": "the", "start": 2.3, "end": 2.5},
        {"word": "new", "start": 2.5, "end": 2.8},
        {"word": "protocol.", "start": 2.8, "end": 3.2},
    ]

    result = planner.plan(
        understanding=understanding,
        transcript=transcript,
        user_prompt="Produce an autonomous edit emphasizing key growth numbers",
        video_metadata={"width": 1920, "height": 1080, "duration": 10.0},
    )

    assert result.edit_decisions is not None
    edits = result.edit_decisions
    assert "cuts" in edits
    assert "overlays" in edits
    assert "metadata" in edits

    meta = edits["metadata"]
    assert "semantic_visual_plan" in meta
    svp = meta["semantic_visual_plan"]
    assert svp["total_visuals_placed"] >= 1

    # Verify talking_head_props overlays match semantic visual events
    th_props = meta.get("talking_head_props", {})
    assert "overlays" in th_props
    assert len(th_props["overlays"]) == len(edits["overlays"])
