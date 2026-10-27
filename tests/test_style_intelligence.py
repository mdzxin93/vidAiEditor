"""Automated Test Suite for Phase 6: Reference Video Style Intelligence.

Tests:
1. ReferenceStyleAnalyzer feature extraction & schema compliance
2. Pacing shot duration distribution (min, max, mean, median, std_dev, iqr)
3. Color palette extraction via Pillow quantization
4. Audio feature extraction (volume, silence ratio, speech/music balance)
5. Accredited measurement sources and confidence scores
6. StyleTransferEngine 4-tier conflict resolution matrix (User > Source > Reference > Defaults)
7. StyleSimilarityEvaluator objective metric scoring & deviation reporting
8. Autonomous planner end-to-end integration with style transfer
"""

import json
from pathlib import Path
import jsonschema
import pytest

from lib.ai.autonomous_editor import AutonomousEditingPlanner
from lib.ai.config import AIEditorConfig
from lib.ai.providers.base import VideoUnderstandingResult
from lib.ai.style_analyzer import ReferenceStyleAnalyzer, StyleProfile
from lib.ai.style_evaluator import StyleSimilarityEvaluator
from lib.ai.style_transfer import StyleTransferEngine


@pytest.fixture
def sample_reference_path() -> Path:
    p = Path("assets/signal-from-tomorrow-demo.mp4")
    if not p.exists():
        p = Path("media/sample/sample_edited.mp4")
    return p


@pytest.fixture
def sample_transcript() -> list[dict]:
    with open("media/sample/captions_aligned.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_style_analyzer_feature_extraction_and_schema_validation(sample_reference_path):
    """Verify that ReferenceStyleAnalyzer extracts all required dimensions conforming to schema."""
    analyzer = ReferenceStyleAnalyzer()
    profile = analyzer.analyze_reference(sample_reference_path)

    assert isinstance(profile, StyleProfile)
    data = profile.to_dict()

    # Validate against JSON schema
    schema_path = Path("schemas/artifacts/style_profile.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    jsonschema.validate(instance=data, schema=schema)

    # Check media metadata
    assert data["reference_media"]["duration_sec"] > 0
    assert data["reference_media"]["width"] > 0
    assert data["reference_media"]["height"] > 0
    assert data["reference_media"]["aspect_ratio"] in ("9:16", "16:9", "1:1", "4:5")

    # Check pacing distribution
    pacing = data["pacing"]
    assert pacing["pacing_category"] in ("fast", "moderate", "deliberate")
    assert pacing["average_shot_duration_sec"] > 0
    assert pacing["cut_frequency_per_min"] >= 0
    dist = pacing["shot_distribution"]
    assert dist["min_sec"] <= dist["mean_sec"] <= dist["max_sec"]
    assert dist["median_sec"] > 0
    assert dist["std_dev_sec"] >= 0
    assert dist["iqr_sec"] >= 0

    # Check color palette
    palette = data["color_palette"]
    assert palette["dominant_background"].startswith("#")
    assert palette["text_primary"].startswith("#")
    assert palette["accent_primary"].startswith("#")
    assert palette["color_temperature"] in ("warm", "cool", "neutral")

    # Check audio features
    audio = data["audio"]
    assert isinstance(audio["has_audio"], bool)
    assert 0.0 <= audio["silence_ratio"] <= 1.0
    assert audio["speech_music_balance"] in ("voice_dominant", "music_dominant", "balanced", "silent", "ambient")

    # Check confidence and sources
    assert all(0.0 <= score <= 1.0 for score in data["confidence_scores"].values())
    assert all(len(src) > 0 for src in data["measurement_sources"].values())


def test_conflict_resolution_user_priority_over_reference_zooms():
    """Verify Tier 1 user instruction takes strict priority over reference frequent zooms."""
    engine = StyleTransferEngine()

    # Mock reference with frequent zooms
    ref_profile = StyleProfile(
        style_name="energetic_reel",
        camera_composition={"target_aspect_ratio": "9:16", "zoom_frequency": "frequent", "zoom_scale": 1.25},
    )

    # User says: "Use very few zooms"
    user_prompt = "Edit this raw footage into a clean video. Use very few zooms and maintain stability."
    directives = engine.resolve_style_directives(
        user_instruction=user_prompt,
        style_profile=ref_profile,
        source_metadata={"duration": 20.0},
    )

    assert directives.zoom_frequency == "sparing"
    assert directives.max_zooms_allowed == 1

    # Verify conflict resolution record exists
    zoom_conflicts = [c for c in directives.conflict_resolutions if c.parameter == "zoom_frequency"]
    assert len(zoom_conflicts) == 1
    rec = zoom_conflicts[0]
    assert rec.winning_tier == 1
    assert rec.winning_tier_name == "user_instruction"
    assert "Explicit user instruction prioritized" in rec.reason


def test_conflict_resolution_user_priority_over_reference_colors():
    """Verify Tier 1 user instruction takes strict priority over reference color palette."""
    engine = StyleTransferEngine()

    ref_profile = StyleProfile(
        style_name="cyan_corporate",
        color_palette={"dominant_background": "#0F172A", "text_primary": "#FFFFFF", "accent_primary": "#22D3EE"},
    )

    # User explicitly requests yellow captions
    user_prompt = "Highlight the important numbers with a bright yellow highlight."
    directives = engine.resolve_style_directives(
        user_instruction=user_prompt,
        style_profile=ref_profile,
        source_metadata={"duration": 20.0},
    )

    assert directives.highlight_color == "#FACC15"

    color_conflicts = [c for c in directives.conflict_resolutions if c.parameter == "highlight_color"]
    assert len(color_conflicts) == 1
    assert color_conflicts[0].winning_tier == 1
    assert color_conflicts[0].winning_tier_name == "user_instruction"


def test_reference_style_transfer_when_no_user_conflict():
    """Verify reference style characteristics are transferred cleanly when user prompt doesn't conflict."""
    engine = StyleTransferEngine()

    ref_profile = StyleProfile(
        style_name="editorial_style",
        pacing_data={"pacing_category": "fast", "average_shot_duration_sec": 2.1, "cut_frequency_per_min": 28.0},
        captions_typography={"placement": "bottom-center", "words_per_group": 3, "font_preset": "bold_impact"},
        color_palette={"dominant_background": "#000000", "text_primary": "#FFFFFF", "accent_primary": "#EF4444"},
    )

    user_prompt = "Create an engaging video for social media."
    directives = engine.resolve_style_directives(
        user_instruction=user_prompt,
        style_profile=ref_profile,
        source_metadata={"duration": 20.0},
    )

    assert directives.pacing_category == "fast"
    assert directives.highlight_color == "#EF4444"
    assert directives.words_per_page == 3

    # Check Tier 3 accreditation
    winning_tiers = [c.winning_tier for c in directives.conflict_resolutions]
    assert 3 in winning_tiers


def test_style_similarity_evaluator_metrics():
    """Verify that StyleSimilarityEvaluator outputs objective similarity metrics and reports."""
    evaluator = StyleSimilarityEvaluator()

    ref_profile = StyleProfile(
        style_name="demo_ref",
        pacing_data={"pacing_category": "moderate", "average_shot_duration_sec": 3.5, "cut_frequency_per_min": 17.0},
        camera_composition={"target_aspect_ratio": "9:16", "zoom_frequency": "sparing", "zoom_scale": 1.15},
        color_palette={"dominant_background": "#0F172A", "text_primary": "#FFFFFF", "accent_primary": "#22D3EE"},
        captions_typography={"placement": "bottom-center", "words_per_group": 4},
    )

    mock_edits = {
        "cuts": [
            {"id": "c1", "in_seconds": 0.0, "out_seconds": 3.5, "transform": {"scale": 1.0}},
            {"id": "c2", "in_seconds": 3.5, "out_seconds": 7.0, "transform": {"scale": 1.15}},
            {"id": "c3", "in_seconds": 7.0, "out_seconds": 10.5, "transform": {"scale": 1.0}},
        ],
        "overlays": [{"id": "ov1"}],
        "metadata": {
            "talking_head_props": {
                "wordsPerPage": 4,
                "highlightColor": "#22D3EE",
            }
        },
    }

    report = evaluator.evaluate(ref_profile, mock_edits)

    assert 0.0 <= report.overall_similarity_score <= 1.0
    assert report.overall_similarity_score > 0.70  # Closely aligned mock edit
    assert len(report.shared_style_traits) > 0
    assert "metrics" in report.to_dict()
    assert report.metrics["color"]["color_similarity"] == 1.0  # Exact hex match


def test_autonomous_editor_style_guided_plan_integration(sample_reference_path, sample_transcript):
    """Verify autonomous editor integrates style profile and outputs schema-valid decisions with provenance."""
    config = AIEditorConfig()
    config.provider = "heuristic_engine"
    planner = AutonomousEditingPlanner(config=config)

    analyzer = ReferenceStyleAnalyzer()
    ref_profile = analyzer.analyze_reference(sample_reference_path)

    vu = VideoUnderstandingResult(
        observations=[],
        provider_name="test_fixture",
        framing="medium_close_up",
        overlay_safe_region="upper_third",
        detected_topics=["deep work", "focus"],
    )

    video_meta = {"source_path": "media/sample/sample_raw.mp4", "duration": 20.6, "width": 3840, "height": 2160, "fps": 25.0}

    # Run style-guided plan with explicit instruction
    prompt = "Edit this video using the reference style. Use very few zooms."
    res = planner.plan(
        understanding=vu,
        transcript=sample_transcript,
        user_prompt=prompt,
        video_metadata=video_meta,
        style_profile=ref_profile,
    )

    edits = res.edit_decisions
    meta = edits.get("metadata", {})

    # Check presence of Phase 6 style intelligence artifacts
    assert "applied_style_profile" in meta
    assert "conflict_resolutions" in meta
    assert "style_similarity_report" in meta
    assert "style_similarity" in res.metrics

    # Check that user instruction took priority: zoom count <= 1
    zooms = [c for c in edits["cuts"] if c.get("transform", {}).get("scale", 1.0) > 1.05]
    assert len(zooms) <= 1

    # Check conflict resolution logged for zoom frequency
    conflicts = meta["conflict_resolutions"]
    zoom_rec = next((c for c in conflicts if c["parameter"] == "zoom_frequency"), None)
    assert zoom_rec is not None
    assert zoom_rec["winning_tier"] == 1
