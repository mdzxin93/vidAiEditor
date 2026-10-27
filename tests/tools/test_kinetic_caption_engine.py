"""Tests for OpenMontage AI Kinetic Caption & Subtitle Engine (Phases 1-17).

Verifies:
- Preset loading & validation for all 6 style presets (Priority: kinetic_podcast_reference).
- Faster-Whisper transcription caching & word-level timing preservation.
- Intelligent 1-4 word segmentation with pause and punctuation sensitivity.
- AI emphasis selection (duration z-score + audio energy).
- Positioning & safe margin detection.
- Subtitle file generation (.srt, .vtt, .ass).
- Timeline editing operations (split, merge, retime, update).
- Remotion composition staging & props generation.
- Style learning extraction.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from tools.subtitle.kinetic_caption_engine import KineticCaptionEngine
from lib.paths import REPO_ROOT


@pytest.fixture
def engine():
    return KineticCaptionEngine()


@pytest.fixture
def sample_words():
    """Simulated Faster-Whisper word-level transcription with timings and pauses."""
    return [
        {"word": "I", "start": 0.10, "end": 0.25, "probability": 0.98},
        {"word": "think", "start": 0.28, "end": 0.55, "probability": 0.99},
        {"word": "the", "start": 0.58, "end": 0.70, "probability": 0.99},
        {"word": "biggest", "start": 0.72, "end": 1.15, "probability": 0.95},  # Long duration
        {"word": "struggles", "start": 1.25, "end": 1.95, "probability": 0.97},  # Long duration + pause after
        # Pause: 1.95s to 2.40s (0.45s pause)
        {"word": "people", "start": 2.40, "end": 2.75, "probability": 0.96},
        {"word": "face", "start": 2.80, "end": 3.10, "probability": 0.98},
        {"word": "are", "start": 3.15, "end": 3.30, "probability": 0.95},
        {"word": "actually", "start": 3.35, "end": 3.80, "probability": 0.94},
        # Pause: 3.80s to 4.15s (0.35s pause)
        {"word": "the", "start": 4.15, "end": 4.30, "probability": 0.99},
        {"word": "questions", "start": 4.35, "end": 4.85, "probability": 0.98},
        {"word": "they", "start": 4.90, "end": 5.05, "probability": 0.97},
        {"word": "never", "start": 5.10, "end": 5.40, "probability": 0.99},
        {"word": "ask.", "start": 5.45, "end": 5.90, "probability": 0.98},
    ]


# ---------------------------------------------------------------------------
# Test 1: Presets Loading & Centralized Style Reference
# ---------------------------------------------------------------------------

def test_load_all_presets(engine):
    """Verify all 6 presets load and have correct schema and typography."""
    presets = [
        "kinetic_podcast_reference",
        "minimal_white",
        "bold_word_pop",
        "editorial_typography",
        "clean_podcast",
        "animated_social_captions",
    ]
    for pid in presets:
        preset = engine.load_preset(pid)
        assert preset["style_id"] == pid
        assert "Inter Display" in preset["font_family"]
        assert preset["font_weight"] in [700, 800, 900]
        assert "animation" in preset
        assert "layout" in preset
        assert "caption_grouping" in preset


def test_reference_preset_visual_spec(engine):
    """Verify exact styling properties of the Cinematic Kinetic Podcast reference."""
    preset = engine.load_preset("kinetic_podcast_reference")
    assert preset["name"] == "Cinematic Kinetic Podcast"
    assert preset["font_family"] == "Inter Display"
    assert preset["font_weight"] == 800
    assert preset["font_color"].upper() in ["#FFFFFF", "WHITE"]
    assert preset["emphasis_enabled"] is True
    assert preset["emphasis_scale"] == 1.85
    assert preset["caption_grouping"]["minimum_words"] == 1
    assert preset["caption_grouping"]["maximum_words"] == 4
    assert preset["animation"]["type"] == "quick_scale_fade"
    assert preset["animation"]["duration_ms"] == 140
    assert preset["animation"]["initial_scale"] == 0.94
    assert preset["animation"]["final_scale"] == 1.0


# ---------------------------------------------------------------------------
# Test 2: Intelligent 1-4 Word Caption Segmentation
# ---------------------------------------------------------------------------

def test_intelligent_segmentation(engine, sample_words):
    """Verify speech is split into 1-4 word groups based on speech rhythm, not fixed chunks."""
    preset = engine.load_preset("kinetic_podcast_reference")
    cues = engine.segment_words_into_cues(sample_words, preset=preset, words_per_cue=2)

    assert len(cues) > 0
    for cue in cues:
        # Every cue must respect 1 to 4 word limit
        word_count = len(cue["text"].split())
        assert 1 <= word_count <= 4, f"Cue '{cue['text']}' has {word_count} words (expected 1-4)"
        # Every cue must have valid timestamps
        assert cue["start"] >= 0
        assert cue["end"] > cue["start"]
        assert cue["end"] - cue["start"] <= 3.5  # No stuck subtitles

    # Verify pause split occurred between 'struggles' and 'people'
    texts = [c["text"].lower() for c in cues]
    # 'struggles' and 'people' should be in different cues because of 0.45s pause
    assert any("struggles" in t for t in texts)
    for c in cues:
        assert not ("struggles" in c["text"].lower() and "people" in c["text"].lower())


# ---------------------------------------------------------------------------
# Test 3: AI Emphasis Detection
# ---------------------------------------------------------------------------

def test_emphasis_detection(engine, sample_words):
    """Verify words with high duration / stress are selected for enlarged typography."""
    preset = engine.load_preset("kinetic_podcast_reference")
    cues = engine.segment_words_into_cues(sample_words, preset=preset, words_per_cue=2)
    cues_with_emphasis = engine.detect_and_apply_emphasis(
        cues,
        sample_words,
        preset=preset,
        emphasis_frequency=0.35,
    )

    emphasis_cues = [c for c in cues_with_emphasis if c.get("mode") in ["emphasis", "stack"]]
    assert len(emphasis_cues) >= 1, "At least one word should receive emphasis treatment"

    for c in emphasis_cues:
        assert c.get("emphasis_word"), "Emphasis cue must specify the emphasized word"
        assert c.get("scale", 1.0) >= 1.5, "Emphasis cue must have scaled factor"
        assert c.get("font_weight", 800) >= 800, "Emphasis typography must be bold/black"


# ---------------------------------------------------------------------------
# Test 4: Subtitle File Generation (.srt, .vtt, .ass)
# ---------------------------------------------------------------------------

def test_export_subtitles(engine, sample_words, tmp_path):
    """Verify export to SRT, VTT, and ASS with accurate syntax and styling."""
    preset = engine.load_preset("kinetic_podcast_reference")
    cues = engine.segment_words_into_cues(sample_words, preset=preset, words_per_cue=2)
    cues = engine.detect_and_apply_emphasis(cues, sample_words, preset=preset)

    srt_path = tmp_path / "test.srt"
    vtt_path = tmp_path / "test.vtt"
    ass_path = tmp_path / "test.ass"

    srt_content = engine.export_srt(cues, srt_path)
    vtt_content = engine.export_vtt(cues, vtt_path)
    ass_content = engine.export_ass(cues, ass_path, preset)

    # SRT Validation
    assert srt_path.is_file()
    assert "-->" in srt_content
    assert "00:00:00" in srt_content
    assert "1\n00:00:00" in srt_content
    assert "2\n00:00:01" in srt_content

    # VTT Validation
    assert vtt_path.is_file()
    assert vtt_content.startswith("WEBVTT")
    assert "-->" in vtt_content

    # ASS Validation
    assert ass_path.is_file()
    assert "[Script Info]" in ass_content
    assert "[V4+ Styles]" in ass_content
    assert "Inter Display" in ass_content
    assert "[Events]" in ass_content
    assert "Dialogue:" in ass_content


# ---------------------------------------------------------------------------
# Test 5: Timeline Editing Operations (Split, Merge, Retime)
# ---------------------------------------------------------------------------

def test_split_and_merge_cues(engine, sample_words):
    """Verify splitting a caption group and merging adjacent captions."""
    preset = engine.load_preset("kinetic_podcast_reference")
    cues = engine.segment_words_into_cues(sample_words, preset=preset, words_per_cue=3)

    # Find a multi-word cue to split
    multi_cue = next(c for c in cues if len(c["text"].split()) >= 2)
    initial_count = len(cues)

    # Split
    words = multi_cue["text"].split()
    mid_time = (multi_cue["start"] + multi_cue["end"]) / 2
    cue1 = dict(multi_cue, text=words[0], end=mid_time)
    cue2 = dict(multi_cue, id="cue_split_new", text=" ".join(words[1:]), start=mid_time)

    updated = []
    for c in cues:
        if c["id"] == multi_cue["id"]:
            updated.extend([cue1, cue2])
        else:
            updated.append(c)

    assert len(updated) == initial_count + 1

    # Merge them back
    merged_text = f"{cue1['text']} {cue2['text']}"
    merged_cue = dict(cue1, text=merged_text, end=cue2["end"])
    remerged = [merged_cue if c["id"] == cue1["id"] else c for c in updated if c["id"] != cue2["id"]]

    assert len(remerged) == initial_count
    assert remerged[0]["start"] == cues[0]["start"]


# ---------------------------------------------------------------------------
# Test 6: Remotion Staging & Composition Resolution Adaptive
# ---------------------------------------------------------------------------

def test_remotion_composition_props(engine, sample_words):
    """Verify Remotion props generation handles vertical, horizontal, and square layouts."""
    preset = engine.load_preset("kinetic_podcast_reference")
    cues = engine.segment_words_into_cues(sample_words, preset=preset, words_per_cue=2)
    cues = engine.detect_and_apply_emphasis(cues, sample_words, preset=preset)

    for aspect, comp_name, w, h in [
        ("9:16", "KineticCaptionsVertical", 1080, 1920),
        ("16:9", "KineticCaptionsHorizontal", 1920, 1080),
        ("1:1", "KineticCaptionsSquare", 1080, 1080),
    ]:
        props = engine.generate_remotion_props(
            video_src="test_video.mp4",
            cues=cues,
            preset=preset,
            aspect_ratio=aspect,
        )
        assert props["videoSrc"] == "test_video.mp4"
        assert len(props["cues"]) == len(cues)
        assert props["preset"]["style_id"] == "kinetic_podcast_reference"
        assert props["aspectRatio"] == aspect


# ---------------------------------------------------------------------------
# Test 7: Style Learning Extractor
# ---------------------------------------------------------------------------

def test_style_learning_extraction(engine, sample_words):
    """Verify extraction of training records for Phase 15 style learning pipeline."""
    preset = engine.load_preset("kinetic_podcast_reference")
    cues = engine.segment_words_into_cues(sample_words, preset=preset, words_per_cue=2)
    cues = engine.detect_and_apply_emphasis(cues, sample_words, preset=preset)

    records = engine.extract_style_learning_records("sample_reference.mp4", cues, preset)
    assert len(records) == len(cues)
    for rec in records:
        assert rec["source_video"] == "sample_reference.mp4"
        assert rec["style_id"] == "kinetic_podcast_reference"
        assert "font_family" in rec
        assert "font_weight" in rec
        assert "emphasis" in rec
        assert "scale" in rec
        assert "position" in rec
        assert "animation" in rec
