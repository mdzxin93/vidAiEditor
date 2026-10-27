"""Unit & Integration Test Suite for OpenMontage Intelligent Editing Memory & Personalization (Phase 10).

Verifies all 12 Phase 10 requirements:
1. Saving an approved preference
2. Rejecting a temporary correction
3. Reusing a preference in a similar editing context
4. Avoiding preference application in unrelated contexts (aspect/genre divergence)
5. Explicit user instruction overriding memory (Tier 1 > Tier 3)
6. Preference disabling (toggle off)
7. Preference persistent deletion from disk
8. Undo and redo without accidental learning (UNDO_OP)
9. JSON import and export with strict path & code execution safety
10. Project reopening and persistence across store instances
11. Editing decisions recording correct provenance (learned_preference)
12. Fine-tuning training dataset exporter (opt-in)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backlot import server as server_mod
from lib.ai.memory.context_matcher import ContextMatcher
from lib.ai.memory.models import (
    ApprovalStatus,
    CorrectionRecord,
    EditingPreference,
    EditingPreferenceCategory,
    PreferenceTier,
    StylePreset,
)
from lib.ai.memory.preference_resolver import PreferenceResolver
from lib.ai.memory.preference_store import PreferenceStore


@pytest.fixture
def temp_pref_store(tmp_path):
    """Isolated PreferenceStore running in a temporary directory."""
    store_dir = tmp_path / "preferences"
    return PreferenceStore(storage_dir=store_dir)


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    """FastAPI TestClient with isolated preferences and projects."""
    pref_dir = tmp_path / "preferences"
    proj_dir = tmp_path / "projects"
    pref_dir.mkdir(parents=True, exist_ok=True)
    proj_dir.mkdir(parents=True, exist_ok=True)

    test_store = PreferenceStore(storage_dir=pref_dir)
    monkeypatch.setattr("lib.api.preferences_routes.store", test_store)
    monkeypatch.setattr("lib.ai.memory.preference_store.DEFAULT_PREFERENCES_DIR", pref_dir)
    monkeypatch.setattr(server_mod, "PROJECTS_DIR", proj_dir)

    async def no_watch():
        return None

    monkeypatch.setattr(server_mod, "_watch_projects", no_watch)

    app = server_mod.create_app()
    with TestClient(app) as client:
        yield client, test_store


# ---------------------------------------------------------------------------
# 1. Saving an Approved Preference & Persistence across Store Restarts
# ---------------------------------------------------------------------------

def test_saving_approved_preference(temp_pref_store):
    """Requirement 1 & 10: Approved corrections become versioned EditingPreferences that persist."""
    corr = CorrectionRecord(
        correction_id="corr_zoom_001",
        project_id="proj_alpha",
        category=EditingPreferenceCategory.ZOOM.value,
        parameter_key="zoom_scale",
        original_ai_value=1.25,
        user_corrected_value=1.10,
        editing_context={"aspect_ratio": "9:16", "category": "educational"},
        approval_status=ApprovalStatus.PENDING_REVIEW.value,
    )
    temp_pref_store.record_correction(corr)

    # Approve for future projects
    pref = temp_pref_store.approve_correction(
        correction_id="corr_zoom_001",
        apply_to_future=True,
    )
    assert pref is not None
    assert pref.parameter_key == "zoom_scale"
    assert pref.preferred_value == 1.10
    assert pref.category == "zoom"
    assert pref.enabled is True

    # Verify persistent reload from new store instance (application restart)
    reloaded_store = PreferenceStore(storage_dir=temp_pref_store.storage_dir)
    reloaded_prefs = reloaded_store.list_preferences()
    assert len(reloaded_prefs) == 1
    assert reloaded_prefs[0].preferred_value == 1.10
    assert reloaded_prefs[0].parameter_key == "zoom_scale"


# ---------------------------------------------------------------------------
# 2. Rejecting a Temporary Correction & One-Time Project Adjustments
# ---------------------------------------------------------------------------

def test_rejecting_temporary_correction(temp_pref_store):
    """Requirement 2: Rejecting or marking one-time does NOT create a learned preference."""
    # 1. Rejected correction
    corr_rejected = CorrectionRecord(
        correction_id="corr_temp_reject",
        project_id="proj_temp",
        category=EditingPreferenceCategory.PACING.value,
        parameter_key="min_pause_cut_duration",
        original_ai_value=0.8,
        user_corrected_value=0.4,
        approval_status=ApprovalStatus.PENDING_REVIEW.value,
    )
    temp_pref_store.record_correction(corr_rejected)

    # Reject
    corr_rejected.approval_status = ApprovalStatus.REJECTED.value
    temp_pref_store.record_correction(corr_rejected)

    # Verify no preference was generated
    assert len(temp_pref_store.list_preferences()) == 0

    # 2. One-time adjustment (apply_to_future=False)
    corr_onetime = CorrectionRecord(
        correction_id="corr_onetime_002",
        project_id="proj_temp",
        category=EditingPreferenceCategory.CAPTION.value,
        parameter_key="caption_highlight_color",
        original_ai_value="#22D3EE",
        user_corrected_value="#EF4444",
        approval_status=ApprovalStatus.PENDING_REVIEW.value,
    )
    temp_pref_store.record_correction(corr_onetime)

    result_pref = temp_pref_store.approve_correction(
        correction_id="corr_onetime_002",
        apply_to_future=False,
    )
    assert result_pref is None  # No future preference created
    assert len(temp_pref_store.list_preferences()) == 0

    # Correction status updated to ONE_TIME
    updated_corr = next(c for c in temp_pref_store.list_corrections() if c.correction_id == "corr_onetime_002")
    assert updated_corr.approval_status == ApprovalStatus.ONE_TIME.value


# ---------------------------------------------------------------------------
# 3 & 4. Context-Aware Preference Matching & Avoidance in Unrelated Contexts
# ---------------------------------------------------------------------------

def test_context_aware_matching_and_divergence(temp_pref_store):
    """Requirements 3 & 4: Matches compatible contexts; rejects mismatched aspect ratio or genre."""
    matcher = ContextMatcher()

    # Create a 9:16 high-energy viral preference
    pref_reels = EditingPreference(
        preference_id="pref_reels_zoom",
        category=EditingPreferenceCategory.ZOOM.value,
        parameter_key="zoom_scale",
        preferred_value=1.40,
        context_constraints={
            "target_aspect": "9:16",
            "video_category": "viral_short",
        },
    )

    # Target 1: Compatible Context (9:16 TikTok / Reels)
    context_compatible = {
        "target_aspect": "9:16",
        "video_category": "reels",
    }
    res_compatible = matcher.evaluate_match(pref_reels, context_compatible)
    assert res_compatible.is_compatible is True
    assert res_compatible.match_score >= 0.70

    # Target 2: Incompatible Context 1 (Aspect ratio mismatch: 16:9 YouTube landscape)
    context_landscape = {
        "target_aspect": "16:9",
        "video_category": "viral_short",
    }
    res_landscape = matcher.evaluate_match(pref_reels, context_landscape)
    assert res_landscape.is_compatible is False
    assert any("Aspect ratio mismatch" in r for r in res_landscape.incompatible_reasons)

    # Target 3: Incompatible Context 2 (Genre divergence: calm educational lecture)
    context_lecture = {
        "target_aspect": "9:16",
        "video_category": "educational",
    }
    res_lecture = matcher.evaluate_match(pref_reels, context_lecture)
    assert res_lecture.is_compatible is False
    assert any("Category divergence" in r for r in res_lecture.incompatible_reasons)


# ---------------------------------------------------------------------------
# 5. Explicit User Instruction Overriding Memory (Tier 1 > Tier 3)
# ---------------------------------------------------------------------------

def test_explicit_instruction_overrides_learned_memory(temp_pref_store):
    """Requirement 5: Strict 4-tier hierarchy guarantees explicit prompt overrides memory."""
    resolver = PreferenceResolver(store=temp_pref_store)

    # Save a learned preference for subtle 1.10x zoom
    pref = EditingPreference(
        preference_id="pref_zoom_subtle",
        category=EditingPreferenceCategory.ZOOM.value,
        parameter_key="zoom_scale",
        preferred_value=1.10,
        context_constraints={"target_aspect": "9:16"},
    )
    temp_pref_store.save_preference(pref)

    # Case A: User gives no zoom instruction -> Learned Preference applies (Tier 3)
    plan_normal = resolver.resolve_plan(
        user_prompt="Cut pauses and add motion graphics",
        video_metadata={"width": 1080, "height": 1920, "category": "educational"},
        enable_personalization=True,
    )
    assert plan_normal.zoom_scale == 1.10
    zoom_rec_a = next(r for r in plan_normal.applied_records if r.parameter_key == "zoom_scale")
    assert zoom_rec_a.winning_tier == PreferenceTier.TIER_3_USER_LEARNED.value
    assert zoom_rec_a.winning_tier_name == "learned_preference"

    # Case B: User explicitly requests "1.4x zoom" in prompt -> Explicit Prompt wins (Tier 1)
    plan_explicit = resolver.resolve_plan(
        user_prompt="Apply punchy 1.4x zoom on key metrics",
        video_metadata={"width": 1080, "height": 1920, "category": "educational"},
        enable_personalization=True,
    )
    assert plan_explicit.zoom_scale == 1.40
    zoom_rec_b = next(r for r in plan_explicit.applied_records if r.parameter_key == "zoom_scale")
    assert zoom_rec_b.winning_tier == PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value
    assert zoom_rec_b.winning_tier_name == "explicit_instruction"


# ---------------------------------------------------------------------------
# 6 & 7. Preference Disabling & Persistent Deletion
# ---------------------------------------------------------------------------

def test_preference_disabling_and_persistent_deletion(temp_pref_store):
    """Requirements 6 & 7: Disabling ignores preference; deletion removes file record permanently."""
    pref = EditingPreference(
        preference_id="pref_caption_color_test",
        category=EditingPreferenceCategory.CAPTION.value,
        parameter_key="highlight_color",
        preferred_value="#FACC15",
    )
    temp_pref_store.save_preference(pref)
    assert len(temp_pref_store.list_preferences()) == 1

    resolver = PreferenceResolver(store=temp_pref_store)

    # 1. Enabled test
    plan_enabled = resolver.resolve_plan(
        user_prompt="Standard edit",
        video_metadata={"duration": 15.0},
        enable_personalization=True,
    )
    assert plan_enabled.caption_highlight_color == "#FACC15"

    # 2. Disable preference
    pref.enabled = False
    temp_pref_store.save_preference(pref)

    plan_disabled = resolver.resolve_plan(
        user_prompt="Standard edit",
        video_metadata={"duration": 15.0},
        enable_personalization=True,
    )
    # Falls back to default preset/cyan
    assert plan_disabled.caption_highlight_color != "#FACC15"

    # 3. Persistent Deletion
    del_res = temp_pref_store.delete_preference("pref_caption_color_test")
    assert del_res is True
    assert len(temp_pref_store.list_preferences()) == 0

    # Verify physical file on disk contains 0 preferences
    with open(temp_pref_store.pref_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data.get("preferences", [])) == 0


# ---------------------------------------------------------------------------
# 8. Undo and Redo Without Accidental Learning
# ---------------------------------------------------------------------------

def test_undo_redo_does_not_trigger_accidental_learning():
    """Requirement 8: Timeline undo/redo actions are marked UNDO_OP and never promoted."""
    from lib.api.editor_routes import _detect_and_record_corrections

    prev_edits = {
        "cuts": [{"id": "cut_1", "transform": {"scale": 1.25}}],
        "metadata": {"target_aspect": "9:16"},
    }
    new_edits = {
        "cuts": [{"id": "cut_1", "transform": {"scale": 1.0}}],
        "metadata": {"target_aspect": "9:16"},
    }

    # When user clicks Undo (Ctrl+Z)
    records = _detect_and_record_corrections(
        project_id="proj_undo_test",
        prev_edits=prev_edits,
        new_edits=new_edits,
        commit_message="Undo previous trim operation",
    )
    assert len(records) == 1
    assert records[0].approval_status == ApprovalStatus.UNDO_OP.value


# ---------------------------------------------------------------------------
# 9. JSON Import & Export with Path Safety
# ---------------------------------------------------------------------------

def test_json_import_export_and_safety(temp_pref_store):
    """Requirement 9: Safe serialization, export, and rejection of path traversal."""
    # Add a custom preference and preset
    temp_pref_store.save_preference(
        EditingPreference(
            preference_id="pref_export_test",
            category="zoom",
            parameter_key="zoom_scale",
            preferred_value=1.12,
        )
    )
    temp_pref_store.save_preset(
        StylePreset(
            preset_id="custom-podcast",
            title="Custom Podcast",
            description="Talking head preset",
            is_builtin=False,
            zoom_scale=1.05,
        )
    )

    # 1. Export
    exported = temp_pref_store.export_data()
    assert exported["version"] == "1.0"
    assert len(exported["preferences"]) == 1
    assert any(p["preset_id"] == "custom-podcast" for p in exported["presets"])

    # 2. Import into a clean store
    clean_store_dir = temp_pref_store.storage_dir.parent / "clean_pref_store"
    clean_store = PreferenceStore(storage_dir=clean_store_dir)
    assert len(clean_store.list_preferences()) == 0

    report = clean_store.import_data(exported, overwrite=True)
    assert report["preferences_imported"] == 1
    assert report["presets_imported"] >= 1
    assert len(clean_store.list_preferences()) == 1
    assert clean_store.get_preference("pref_export_test").preferred_value == 1.12

    # 3. Path traversal attack rejection
    malicious_import = {
        "version": "1.0",
        "preferences": [
            {
                "preference_id": "../../etc/passwd",
                "category": "zoom",
                "parameter_key": "zoom_scale",
                "preferred_value": 1.5,
            }
        ]
    }
    with pytest.raises(ValueError, match="Invalid preference identifier"):
        clean_store.import_data(malicious_import)


# ---------------------------------------------------------------------------
# 11. Decision Provenance Recording in Planner
# ---------------------------------------------------------------------------

def test_autonomous_planner_records_preference_provenance(temp_pref_store):
    """Requirement 11: Edit decisions record decision_source='learned_preference' and preference_id."""
    from lib.ai.autonomous_editor import AutonomousEditingPlanner
    from lib.ai.providers.base import VideoUnderstandingResult

    # Set up approved zoom preference: 1.10x
    pref = EditingPreference(
        preference_id="pref_author_zoom",
        category=EditingPreferenceCategory.ZOOM.value,
        parameter_key="zoom_scale",
        preferred_value=1.10,
        context_constraints={"target_aspect": "9:16"},
    )
    temp_pref_store.save_preference(pref)

    planner = AutonomousEditingPlanner()
    planner.preference_store = temp_pref_store
    planner.preference_resolver = PreferenceResolver(store=temp_pref_store)

    from lib.ai.providers.base import ObservationItem

    understanding = VideoUnderstandingResult(
        observations=[
            ObservationItem(
                id="obs_1",
                category="topic",
                start_seconds=0.0,
                end_seconds=6.0,
                confidence=0.95,
                description="Talking head explaining productivity metrics",
            )
        ],
        speaker_position="center",
        framing="medium_close_up",
    )
    transcript = [
        {"word": "OpenMontage", "start": 0.0, "end": 1.2},
        {"word": "boosts", "start": 1.3, "end": 2.0},
        {"word": "productivity", "start": 2.1, "end": 3.0},
        {"word": "by", "start": 3.1, "end": 3.4},
        {"word": "84%", "start": 3.5, "end": 4.5},
        {"word": "in", "start": 4.6, "end": 5.0},
        {"word": "every", "start": 5.1, "end": 5.8},
        {"word": "video.", "start": 5.9, "end": 6.8},
    ]

    res = planner.plan(
        understanding=understanding,
        transcript=transcript,
        user_prompt="Make a clean edit",
        video_metadata={"duration": 7.0, "width": 1080, "height": 1920, "category": "educational"},
        enable_personalization=True,
    )

    edits = res.edit_decisions
    # Verify zoom cut adopted the learned 1.10x scale with provenance
    zoomed_cuts = [c for c in edits.get("cuts", []) if c.get("transform", {}).get("scale", 1.0) > 1.0]
    assert len(zoomed_cuts) > 0
    for zc in zoomed_cuts:
        assert zc["transform"]["scale"] == 1.10
        prov = zc["transform"]["zoom_provenance"]
        assert prov["decision_source"] == "learned_preference"
        assert prov["preference_id"] == "pref_author_zoom"

    # Verify metadata records personalization applied
    assert edits["metadata"]["personalization"]["enabled"] is True


# ---------------------------------------------------------------------------
# 12. Fine-Tuning Dataset Exporter (Phase 10 Section 11)
# ---------------------------------------------------------------------------

def test_future_model_training_dataset_exporter(test_client):
    """Requirement 12: Exports high-quality human corrections with original proposals and context."""
    client, store = test_client

    # Add an approved correction
    corr = CorrectionRecord(
        correction_id="corr_dataset_001",
        project_id="proj_private_123",
        category="zoom",
        parameter_key="zoom_scale",
        original_ai_value=1.25,
        user_corrected_value=1.10,
        editing_context={"aspect_ratio": "9:16", "video_category": "educational"},
        approval_status=ApprovalStatus.APPROVED.value,
        original_decision_provenance={"model_identifier": "metric_zoom_selector", "reason": "1.25x zoom"},
    )
    store.record_correction(corr)

    res = client.get("/api/preferences/dataset/export?anonymize=true")
    assert res.status_code == 200
    data = res.json()
    assert data["total_examples"] >= 1
    ex = data["examples"][0]
    assert ex["category"] == "zoom"
    assert ex["original_ai_proposal"] == 1.25
    assert ex["approved_human_decision"] == 1.10
    assert ex["editing_context"]["target_aspect"] == "9:16"
    # Project id stripped when anonymize=true
    assert "project_id" not in ex
