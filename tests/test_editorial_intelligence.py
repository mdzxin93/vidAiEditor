"""Automated tests for OpenMontage Phase 5 Editorial Intelligence Layer."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from lib.ai.config import AIEditorConfig
from lib.ai.editorial_intelligence import (
    CandidateTreatment,
    DecisionSource,
    EditorialIntelligenceEngine,
    EventProvenance,
    SemanticMoment,
)
from lib.ai.providers.base import ObservationItem, VideoUnderstandingResult
from lib.ai.providers.rule_engine import HeuristicRuleProvider
from lib.ai.autonomous_editor import AutonomousEditingPlanner
from lib.ai.reframer import IntelligentReframer


def test_event_provenance_serialization():
    """Verify EventProvenance serializes with rounded precision and valid fields."""
    prov = EventProvenance(
        decision_source=DecisionSource.NEURAL_VLM.value,
        reason="Detected speaker face in center anchor",
        evidence_timestamps=[1.23456, 4.56789],
        confidence=0.95432,
        model_identifier="smolvlm_local",
    )
    d = prov.to_dict()
    assert d["decision_source"] == "neural_vlm"
    assert d["reason"] == "Detected speaker face in center anchor"
    assert d["evidence_timestamps"] == [1.235, 4.568]
    assert d["confidence"] == 0.954
    assert d["model_identifier"] == "smolvlm_local"


def test_semantic_moment_metric_extraction():
    """Verify EditorialIntelligenceEngine extracts genuine metrics with word timestamps."""
    sample_transcript = [
        {"word": "Most", "start": 0.5, "end": 0.8},
        {"word": "people", "start": 0.8, "end": 1.1},
        {"word": "experience", "start": 1.1, "end": 1.4},
        {"word": "a", "start": 1.4, "end": 1.5},
        {"word": "-40%", "start": 1.5, "end": 1.9},
        {"word": "drop", "start": 1.9, "end": 2.2},
        {"word": "in", "start": 2.2, "end": 2.4},
        {"word": "throughput", "start": 2.4, "end": 2.8},
        {"word": "after", "start": 2.8, "end": 3.0},
        {"word": "90", "start": 3.0, "end": 3.3},
        {"word": "minutes.", "start": 3.3, "end": 3.7},
    ]

    engine = EditorialIntelligenceEngine(min_rest_interval=2.5)
    moments = engine.extract_semantic_moments(sample_transcript, video_duration=5.0)

    assert len(moments) >= 2
    metric_values = {m.value for m in moments if m.moment_type == "metric"}
    assert "-40%" in metric_values
    assert any("90" in v for v in metric_values)

    # Check timestamps and provenance on first metric
    m_drop = next(m for m in moments if "-40%" in m.value)
    assert m_drop.start_seconds >= 1.4
    assert m_drop.end_seconds >= 1.8
    assert m_drop.provenance.decision_source == DecisionSource.DETERMINISTIC_HEURISTIC.value
    assert m_drop.provenance.confidence >= 0.90


def test_semantic_moment_punchline_and_contrast_extraction():
    """Verify extraction of punchlines, golden rules, and contrast structures."""
    transcript = [
        {"word": "Remember,", "start": 0.5, "end": 0.9},
        {"word": "the", "start": 0.9, "end": 1.0},
        {"word": "golden", "start": 1.0, "end": 1.3},
        {"word": "rule", "start": 1.3, "end": 1.6},
        {"word": "is", "start": 1.6, "end": 1.8},
        {"word": "to", "start": 1.8, "end": 1.9},
        {"word": "protect", "start": 1.9, "end": 2.3},
        {"word": "your", "start": 2.3, "end": 2.5},
        {"word": "morning.", "start": 2.5, "end": 3.0},
        {"word": "Do", "start": 4.0, "end": 4.2},
        {"word": "deep", "start": 4.2, "end": 4.5},
        {"word": "work", "start": 4.5, "end": 4.8},
        {"word": "instead", "start": 4.8, "end": 5.1},
        {"word": "of", "start": 5.1, "end": 5.3},
        {"word": "shallow", "start": 5.3, "end": 5.7},
        {"word": "meetings.", "start": 5.7, "end": 6.2},
    ]

    engine = EditorialIntelligenceEngine(min_rest_interval=2.0)
    moments = engine.extract_semantic_moments(transcript, video_duration=10.0)

    assert len(moments) >= 2
    types = {m.moment_type for m in moments}
    assert "punchline" in types
    assert "contrast" in types

    punch = next(m for m in moments if m.moment_type == "punchline")
    assert "GOLDEN" in punch.value

    contrast = next(m for m in moments if m.moment_type == "contrast")
    assert "instead of" in contrast.text.lower() or "deep work" in contrast.text.lower()


def test_candidate_treatments_and_negative_selection():
    """Verify multi-candidate generation and negative selection ('none') on rest violation."""
    engine = EditorialIntelligenceEngine(min_rest_interval=2.5, max_zooms_total=2)

    prov = EventProvenance(
        decision_source=DecisionSource.DETERMINISTIC_HEURISTIC.value,
        reason="Test metric moment",
        evidence_timestamps=[2.0, 3.5],
        confidence=0.90,
        model_identifier="test",
    )
    moment = SemanticMoment(
        id="moment_test_1",
        moment_type="metric",
        text="throughput dropped by -40%",
        value="-40% DROP",
        subtitle="Throughput Drop",
        start_seconds=2.0,
        end_seconds=3.5,
        confidence=0.90,
        provenance=prov,
    )

    vu_normal = VideoUnderstandingResult(
        observations=[],
        speaker_position="center",
        framing="medium_close_up",
        overlay_safe_region="upper_third",
    )

    # Case A: Rest interval satisfied (e.g. 4.0s elapsed since last overlay)
    candidates_rest_ok = engine.generate_candidate_treatments(
        moment=moment,
        understanding=vu_normal,
        timeline_position=5.0,
        time_since_last_overlay=4.0,
        current_zoom_count=0,
    )
    assert len(candidates_rest_ok) >= 3
    best_candidate_ok = candidates_rest_ok[0]
    assert best_candidate_ok.treatment_type == "stat_card"
    assert best_candidate_ok.score >= 0.85
    assert best_candidate_ok.parameters["accentColor"] == "#EF4444"  # Red for drop

    # Case B: Rest interval violated (only 1.0s elapsed since last overlay)
    candidates_rest_violated = engine.generate_candidate_treatments(
        moment=moment,
        understanding=vu_normal,
        timeline_position=5.0,
        time_since_last_overlay=1.0,
        current_zoom_count=0,
    )
    best_candidate_violated = candidates_rest_violated[0]
    # Pacing governor enforces negative selection to prevent visual clutter
    assert best_candidate_violated.treatment_type == "none"
    assert best_candidate_violated.score >= 0.90


def test_collision_avoidance_scoring_adjustment():
    """Verify collision risk raises and scores lower when speaker framing is extreme close-up."""
    engine = EditorialIntelligenceEngine(min_rest_interval=2.5)
    prov = EventProvenance(
        decision_source=DecisionSource.DETERMINISTIC_HEURISTIC.value,
        reason="Test metric moment",
        evidence_timestamps=[1.0, 2.5],
        confidence=0.90,
        model_identifier="test",
    )
    moment = SemanticMoment(
        id="moment_1",
        moment_type="metric",
        text="90 minutes",
        value="90 MIN",
        subtitle="Focus Cycle",
        start_seconds=1.0,
        end_seconds=2.5,
        confidence=0.90,
        provenance=prov,
    )

    vu_closeup = VideoUnderstandingResult(
        observations=[],
        speaker_position="center",
        framing="close_up",  # High risk of occluding speaker head
        overlay_safe_region="upper_third",
    )

    candidates = engine.generate_candidate_treatments(
        moment=moment,
        understanding=vu_closeup,
        timeline_position=3.0,
        time_since_last_overlay=3.0,
        current_zoom_count=0,
    )

    stat_card_cand = next(c for c in candidates if c.treatment_type == "stat_card")
    assert stat_card_cand.collision_risk > 0.15
    # Score is penalized due to face occlusion risk
    assert stat_card_cand.score < 0.80


def test_rule_engine_phase5_provenance_breakdown():
    """Verify HeuristicRuleProvider integrates Phase 5 Editorial Intelligence."""
    transcript = [
        {"word": "Protect", "start": 0.5, "end": 0.9},
        {"word": "your", "start": 0.9, "end": 1.1},
        {"word": "first", "start": 1.1, "end": 1.4},
        {"word": "90", "start": 1.4, "end": 1.8},
        {"word": "minutes", "start": 1.8, "end": 2.2},
        {"word": "for", "start": 2.2, "end": 2.4},
        {"word": "deep", "start": 2.4, "end": 2.7},
        {"word": "work.", "start": 2.7, "end": 3.2},
        # Dead air pause from 3.2 to 4.5 (1.3s)
        {"word": "Otherwise", "start": 4.5, "end": 5.0},
        {"word": "you", "start": 5.0, "end": 5.2},
        {"word": "lose", "start": 5.2, "end": 5.5},
        {"word": "-40%", "start": 5.5, "end": 6.0},
        {"word": "capacity.", "start": 6.0, "end": 6.5},
    ]

    prov = HeuristicRuleProvider()
    vu = VideoUnderstandingResult(
        observations=[
            ObservationItem(
                id="obs_1",
                start_seconds=0.0,
                end_seconds=7.0,
                category="speaker_position",
                description="Speaker centered in medium close-up",
                confidence=0.95,
            )
        ],
        speaker_position="center",
        framing="medium_close_up",
        overlay_safe_region="upper_third",
    )

    plan_res = prov.plan_edits(
        understanding=vu,
        transcript=transcript,
        user_prompt="Make a 9:16 vertical reel.",
        video_metadata={"duration": 7.0, "source_path": "media/sample/sample_raw.mp4"},
    )

    edits = plan_res.edit_decisions
    assert "cuts" in edits
    assert "overlays" in edits
    assert len(edits["overlays"]) >= 1

    # Check that overlays have Phase 5 provenance fields
    for ov in edits["overlays"]:
        assert ov["decision_source"] in (
            DecisionSource.NEURAL_VLM.value,
            DecisionSource.DETERMINISTIC_HEURISTIC.value,
            DecisionSource.TEMPLATE_DEFAULT.value,
        )
        assert ov["reason"]
        assert len(ov["evidence_timestamps"]) == 2
        assert 0.0 <= ov["confidence"] <= 1.0
        assert ov["model_identifier"]

    # Check zoom provenance on cut transform
    cuts_with_zoom = [c for c in edits["cuts"] if c.get("transform", {}).get("scale", 1.0) > 1.0]
    for c in cuts_with_zoom:
        assert "zoom_provenance" in c["transform"]
        zp = c["transform"]["zoom_provenance"]
        assert zp["decision_source"]
        assert zp["reason"]

    # Check metadata provenance breakdown
    meta = edits["metadata"]
    assert "provenance_breakdown" in meta
    bd = meta["provenance_breakdown"]
    assert "deterministic_heuristic" in bd
    assert "total_decisions" in bd
    assert bd["total_decisions"] >= len(edits["cuts"]) + len(edits["overlays"])
    assert "rejected_candidates" in meta


def test_script_directive_phase5_provenance_integration():
    """Verify Mode 2 script directives override with decision_source=script_directive."""
    transcript = [
        {"word": "Revenue", "start": 1.0, "end": 1.5},
        {"word": "surpassed", "start": 1.5, "end": 2.0},
        {"word": "$50k", "start": 2.0, "end": 2.5},
        {"word": "last", "start": 2.5, "end": 2.8},
        {"word": "month.", "start": 2.8, "end": 3.3},
    ]

    planner = AutonomousEditingPlanner()
    vu = VideoUnderstandingResult(
        observations=[],
        speaker_position="center",
        framing="medium_close_up",
        overlay_safe_region="upper_third",
    )

    prompt = "Zoom in when I mention '$50k'. Highlight '$50k' in yellow."
    plan_res = planner.plan(
        understanding=vu,
        transcript=transcript,
        user_prompt=prompt,
        video_metadata={"duration": 4.0, "source_path": "media/sample/sample_raw.mp4"},
    )

    edits = plan_res.edit_decisions
    # Check that zoom was attributed to script_directive
    zoom_cuts = [c for c in edits["cuts"] if c.get("transform", {}).get("scale", 1.0) > 1.0]
    assert len(zoom_cuts) >= 1
    zc = zoom_cuts[0]
    assert zc["decision_source"] == "script_directive"
    assert zc["transform"]["zoom_provenance"]["decision_source"] == "script_directive"
    assert "$50k" in zc["reason"]

    # Check breakdown reflects script directive count
    bd = edits["metadata"]["provenance_breakdown"]
    assert bd["script_directive"] >= 2  # zoom + highlight
