"""Automated tests for OpenMontage Phase 3 Autonomous AI Editing Engine."""

import json
from pathlib import Path
import pytest

from lib.ai.config import AIEditorConfig
from lib.ai.providers.base import ObservationItem, VideoUnderstandingResult
from lib.ai.providers.factory import get_model_provider
from lib.ai.providers.local_vlm import LocalVLMProvider
from lib.ai.providers.rule_engine import HeuristicRuleProvider
from lib.ai.video_understanding import VideoUnderstandingEngine
from lib.ai.autonomous_editor import AutonomousEditingPlanner
from lib.ai.observability import ObservabilityTracker


def test_ai_editor_config_load():
    """Verify that AIEditorConfig loads default and YAML configuration."""
    cfg = AIEditorConfig.load()
    assert cfg is not None
    assert cfg.provider in ("heuristic_engine", "local_vlm", "local_llm", "remote_api")
    assert cfg.editorial_rules.min_pause_cut_duration > 0
    assert cfg.editorial_rules.zoom_scale > 1.0


def test_provider_factory():
    """Verify provider factory returns appropriate provider."""
    cfg = AIEditorConfig(provider="heuristic_engine")
    prov = get_model_provider(cfg)
    assert isinstance(prov, HeuristicRuleProvider)
    assert prov.is_available()

    status = prov.get_status()
    assert status["is_ready"] is True
    assert status["provider"] == "heuristic_engine"


def test_local_vlm_status_audit():
    """Verify LocalVLMProvider safely reports hardware and VRAM without crashing."""
    vlm = LocalVLMProvider()
    status = vlm.get_status()
    assert "cuda_available" in status
    assert "vram_total_gb" in status
    assert "device" in status


def test_video_understanding_observations():
    """Verify video understanding produces grounded observations conforming to schema."""
    sample_transcript = [
        {"word": "Hello", "start": 0.5, "end": 0.9},
        {"word": "world", "start": 0.9, "end": 1.2},
        {"word": "now", "start": 3.0, "end": 3.4},  # 1.8s dead air pause
        {"word": "we", "start": 3.4, "end": 3.6},
        {"word": "have", "start": 3.6, "end": 3.8},
        {"word": "90", "start": 3.8, "end": 4.1},   # key metric
        {"word": "minutes", "start": 4.1, "end": 4.4},
    ]

    prov = HeuristicRuleProvider()
    vu_engine = VideoUnderstandingEngine(prov)
    
    # Run analysis with mock or sample video
    result = prov.understand_video(
        video_path="media/sample/sample_raw.mp4",
        frames=[{"timestamp": 0.0, "path": "f1.jpg"}],
        transcript=sample_transcript,
    )

    assert isinstance(result, VideoUnderstandingResult)
    assert len(result.observations) >= 3

    # Check required fields on each observation
    categories = set()
    for obs in result.observations:
        assert obs.id
        assert obs.start_seconds >= 0
        assert obs.end_seconds >= obs.start_seconds
        assert obs.description
        assert 0.0 <= obs.confidence <= 1.0
        categories.add(obs.category)

    # Must contain speaker framing, safe regions, and pause detection
    assert "speaker_position" in categories
    assert "safe_region" in categories
    assert "scene_change" in categories or "visible_text" in categories


def test_autonomous_editing_planner_schema_validation(tmp_path):
    """Verify planner generates schema-valid edit_decisions without agent coding."""
    sample_transcript = [
        {"word": "Most", "start": 0.5, "end": 0.8},
        {"word": "people", "start": 0.8, "end": 1.1},
        {"word": "try", "start": 1.1, "end": 1.34},
        {"word": "to", "start": 1.34, "end": 1.44},
        {"word": "focus", "start": 1.44, "end": 1.74},
        {"word": "for", "start": 1.74, "end": 2.04},
        {"word": "8", "start": 2.04, "end": 2.34},
        {"word": "hours", "start": 2.34, "end": 2.6},
        {"word": "straight,", "start": 2.6, "end": 2.94},
        # Dead air pause from 2.94 to 4.2 (1.26s)
        {"word": "protect", "start": 4.2, "end": 4.5},
        {"word": "the", "start": 4.5, "end": 4.7},
        {"word": "first", "start": 4.7, "end": 4.9},
        {"word": "90", "start": 4.9, "end": 5.4},
        {"word": "minutes.", "start": 5.4, "end": 5.8},
    ]

    prov = HeuristicRuleProvider()
    vu = prov.understand_video("media/sample/sample_raw.mp4", [], sample_transcript)

    planner = AutonomousEditingPlanner(provider=prov)
    plan_res = planner.plan(
        understanding=vu,
        transcript=sample_transcript,
        user_prompt="Edit this talking-head into an engaging 9:16 Instagram Reel. Remove long pauses, highlight important words, use zooms sparingly, add relevant motion graphics.",
        video_metadata={"duration": 6.5, "source_path": "media/sample/sample_raw.mp4"},
    )

    assert plan_res.decision_source == "heuristic_fallback"
    edits = plan_res.edit_decisions

    # Verify root fields
    assert edits["version"] == "1.0"
    assert edits["render_runtime"] == "remotion"
    assert edits["renderer_family"] == "presenter"
    assert "cuts" in edits and len(edits["cuts"]) >= 2  # Pause cut should split into >= 2 cuts
    assert "overlays" in edits and len(edits["overlays"]) >= 1
    assert "subtitles" in edits
    assert "metadata" in edits

    # Check bounds on cuts
    for cut in edits["cuts"]:
        assert cut["in_seconds"] >= 0
        assert cut["out_seconds"] > cut["in_seconds"]
        assert cut["speed"] >= 0.1
        assert "transform" in cut

    # Verify zero schema validation errors
    val_errors = planner._validate_schema(edits)
    assert len(val_errors) == 0, f"Schema validation errors: {val_errors}"


def test_observability_tracker(tmp_path):
    """Verify structured telemetry is saved properly."""
    tracker = ObservabilityTracker(job_id="test_job", log_dir=tmp_path)
    tracker.record_analysis_complete(1.25)
    tracker.record_planning_complete(0.45, cuts=3, zooms=1, overlays=2)
    tracker.record_render_complete(4.8, str(tmp_path / "out.mp4"))

    assert tracker.log_file.exists()
    with open(tracker.log_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["job_id"] == "test_job"
    assert data["status"] == "rendered"
    assert data["cuts_count"] == 3
    assert data["zooms_count"] == 1
    assert data["total_pipeline_duration_sec"] > 0


def test_timeline_validator_overlay_bounds():
    """Verify TimelineValidator strictly clamps overlays to total compacted video duration."""
    from lib.ai.timeline_validator import TimelineValidator

    validator = TimelineValidator()
    # Edits where cuts total 10.0s, but overlay erroneously ends at 15.0s
    edits = {
        "cuts": [
            {"id": "c1", "in_seconds": 0.0, "out_seconds": 6.0, "speed": 1.0},
            {"id": "c2", "in_seconds": 7.0, "out_seconds": 11.0, "speed": 1.0},
        ],
        "overlays": [
            {"asset_id": "ov1", "start_seconds": 2.0, "end_seconds": 15.0},  # Exceeds 10s!
            {"asset_id": "ov2", "start_seconds": 12.0, "end_seconds": 14.0}, # Starts after video ends!
        ],
    }

    sanitized, warnings = validator.validate_and_sanitize(edits, raw_video_duration=20.0)
    assert len(sanitized["cuts"]) == 2
    # ov2 must be dropped because it starts after the 10.0s mark
    assert len(sanitized["overlays"]) == 1
    # ov1 must be clamped to exactly 10.0s
    assert sanitized["overlays"][0]["end_seconds"] == 10.0
    assert any("exceeded video duration" in w for w in warnings)


def test_script_driven_editor_mode_2():
    """Verify Mode 2 detailed script editing locates phrases and creates directives."""
    from lib.ai.script_editor import ScriptDrivenEditor

    editor = ScriptDrivenEditor()
    transcript = [
        {"word": "Let's", "start": 0.5, "end": 0.8},
        {"word": "look", "start": 0.8, "end": 1.0},
        {"word": "at", "start": 1.0, "end": 1.2},
        {"word": "our", "start": 1.2, "end": 1.4},
        {"word": "conversion", "start": 1.4, "end": 1.9},
        {"word": "rate.", "start": 1.9, "end": 2.4},
        {"word": "Zoom", "start": 2.6, "end": 2.8},
        {"word": "in", "start": 2.8, "end": 3.0},
        {"word": "when", "start": 3.0, "end": 3.2},
        {"word": "revenue", "start": 3.2, "end": 3.6},
        {"word": "grows.", "start": 3.6, "end": 4.0},
    ]

    prompt = "Highlight the phrase 'conversion rate' in yellow. Zoom in when I mention 'revenue'."
    directives, unsupported = editor.parse_and_align_script(prompt, transcript, video_duration=5.0)

    assert len(directives) >= 2
    actions = {d.action for d in directives}
    assert "highlight" in actions
    assert "zoom" in actions

    hl = next(d for d in directives if d.action == "highlight")
    assert hl.matched is True
    assert hl.matched_start == 1.4

    zm = next(d for d in directives if d.action == "zoom")
    assert zm.matched is True
    assert zm.matched_start == 3.2


def test_intelligent_reframer():
    """Verify IntelligentReframer computes centered crop window for 9:16 target."""
    from lib.ai.reframer import IntelligentReframer

    reframer = IntelligentReframer()
    # 4K landscape: 3840x2160 -> 9:16 vertical
    reframe = reframer.compute_reframe(
        video_width=3840,
        video_height=2160,
        target_aspect="9:16",
        detected_subject_centers=[(0.55, 0.40), (0.53, 0.42)],
    )

    assert reframe.target_aspect == "9:16"
    assert reframe.crop_height == 2160
    assert reframe.crop_width == int(2160 * 9 / 16)  # 1215px
    assert 0 <= reframe.crop_x <= 3840 - reframe.crop_width
    assert reframe.confidence > 0.8


def test_broll_selector():
    """Verify BRollSelector can index candidate media and match concepts."""
    from lib.ai.broll_selector import BRollSelector

    selector = BRollSelector()
    candidates = selector.find_candidates()
    assert len(candidates) > 0  # Should find sample files

    transcript = [
        {"word": "Let's", "start": 1.0, "end": 1.3},
        {"word": "focus", "start": 2.5, "end": 3.0},
        {"word": "on", "start": 3.0, "end": 3.2},
        {"word": "deep", "start": 3.2, "end": 3.5},
        {"word": "work.", "start": 3.5, "end": 4.0},
    ]
    matches = selector.match_broll_for_transcript(transcript, video_duration=10.0)
    # May or may not find asset depending on naming, but should not crash
    assert isinstance(matches, list)


def test_neural_smolvlm_local_inference():
    """Verify LocalVLMProvider runs genuine neural inference and marks model_generated."""
    vlm = LocalVLMProvider()
    assert vlm.is_available() is True

    status = vlm.get_status()
    assert status["is_ready"] is True
    assert "Intel" in status["device"] or "CPU" in status["device"]

    sample_transcript = [
        {"word": "Protect", "start": 0.5, "end": 0.9},
        {"word": "your", "start": 0.9, "end": 1.1},
        {"word": "first", "start": 1.1, "end": 1.4},
        {"word": "90", "start": 1.4, "end": 1.8},
        {"word": "minutes.", "start": 1.8, "end": 2.2},
    ]

    # Run neural video understanding on sample frame
    result = vlm.understand_video(
        video_path="media/sample/sample_raw.mp4",
        frames=[{"timestamp": 0.0, "path": "media/sample/preview_90min_stat.jpg"}],
        transcript=sample_transcript,
    )

    assert result.provider_name.startswith("local_vlm:")
    assert len(result.observations) >= 3
    # Check that at least one observation was produced
    assert any(obs.id.startswith("obs_neural_") for obs in result.observations)

    # Check neural editing decision planning
    plan_res = vlm.plan_edits(
        understanding=result,
        transcript=sample_transcript,
        user_prompt="Edit this talking-head into a 9:16 vertical reel.",
        video_metadata={"duration": 5.0, "source_path": "media/sample/sample_raw.mp4"},
    )

    assert plan_res.decision_source in ("model_generated", "hybrid_neural_heuristic")
    assert "cuts" in plan_res.edit_decisions


