"""End-to-End Validation Test Suite for Phase 10: Personalization & Editing Memory.

Executes the full two-project workflow specified in Phase 10 Section 14:
1. First Project (project_1_learning):
   - Ingests primary video (sample_raw.mp4)
   - Generates initial AI edit (baseline 1.25x zoom, #22D3EE highlight)
   - User modifies zoom preference (1.25x -> 1.10x)
   - User modifies caption highlight (#22D3EE -> #FACC15)
   - User explicitly approves both corrections for future projects
   - Confirms preferences are saved in local memory

2. Second Project (project_2_personalized):
   - Ingests second video (sample_edited.mp4)
   - Generates AI edit with enable_personalization=True
   - Verifies learned preferences influence decisions:
     * Zoom scale is 1.10x (provenance: learned_preference)
     * Caption highlight is #FACC15 (provenance: learned_preference)
   - Renders preview video via Remotion / FFmpeg
   - Runs automated QA inspection on rendered output

3. Comparison Project (project_2_baseline):
   - Generates plan for identical video with enable_personalization=False
   - Formulates explainable diff between personalized vs non-personalized plans
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backlot import server as server_mod
from lib.ai.memory.preference_store import PreferenceStore
from lib.api.jobs import job_manager
from lib.paths import PROJECTS_DIR, REPO_ROOT


@pytest.fixture
def e2e_env(tmp_path, monkeypatch):
    """Provides isolated projects and preferences environment."""
    temp_projects = tmp_path / "projects"
    temp_prefs = tmp_path / "preferences"
    temp_projects.mkdir(parents=True, exist_ok=True)
    temp_prefs.mkdir(parents=True, exist_ok=True)

    test_store = PreferenceStore(storage_dir=temp_prefs)
    monkeypatch.setattr("lib.api.preferences_routes.store", test_store)
    monkeypatch.setattr("lib.ai.memory.preference_store.DEFAULT_PREFERENCES_DIR", temp_prefs)

    monkeypatch.setattr(server_mod, "PROJECTS_DIR", temp_projects)
    monkeypatch.setattr("lib.checkpoint.PROJECTS_DIR", temp_projects)
    monkeypatch.setattr("lib.api.media_manager.PROJECTS_DIR", temp_projects)
    monkeypatch.setattr("lib.api.editor_routes.PROJECTS_DIR", temp_projects)
    monkeypatch.setattr(server_mod, "_summary_cache", {})

    async def no_watch():
        return None

    monkeypatch.setattr(server_mod, "_watch_projects", no_watch)

    app = server_mod.create_app()
    with TestClient(app) as client:
        yield client, temp_projects, temp_prefs, test_store


def test_e2e_personalization_two_project_workflow(e2e_env):
    """Full Phase 10 Section 14 End-to-End Validation."""
    client, temp_projects, temp_prefs, pref_store = e2e_env

    sample_raw = REPO_ROOT / "media" / "sample" / "sample_raw.mp4"
    sample_edited = REPO_ROOT / "media" / "sample" / "sample_edited.mp4"
    assert sample_raw.is_file(), f"Sample footage missing: {sample_raw}"
    assert sample_edited.is_file(), f"Second sample footage missing: {sample_edited}"

    # =========================================================================
    # PART 1: FIRST PROJECT — AI Edit, Manual Corrections & Explicit Approval
    # =========================================================================
    p1_id = "project_1_learning"
    res = client.post(
        "/api/projects",
        json={"project_id": p1_id, "title": "Project 1 - Learning", "aspect_ratio": "9:16"},
    )
    assert res.status_code == 200

    # Upload video 1
    with open(sample_raw, "rb") as f:
        res = client.post(
            f"/api/project/{p1_id}/upload",
            data={"category": "video"},
            files={"file": ("sample_raw.mp4", f, "video/mp4")},
        )
    assert res.status_code == 200
    p1_video_path = res.json()["media"]["relative_path"]

    # Generate initial AI plan
    res = client.post(
        f"/api/project/{p1_id}/generate-edit",
        json={
            "user_instruction": "High energy punchy edit. Fast jump cuts, punch in zooms on metrics, and dynamic captions.",
            "video_path": p1_video_path,
            "target_aspect": "9:16",
            "cut_aggressiveness": "aggressive",
            "zoom_intensity": "standard",
            "enable_personalization": False,
        },
    )
    assert res.status_code == 200
    job_id_1 = res.json()["job_id"]

    # Wait for plan generation
    for _ in range(60):
        time.sleep(0.5)
        job = job_manager.get_job(job_id_1)
        if job and job.status in ("completed", "failed"):
            break
    assert job and job.status == "completed", f"Plan 1 failed: {job.error if job else 'timeout'}"

    # Fetch initial decisions
    res = client.get(f"/api/project/{p1_id}/edit-decisions")
    assert res.status_code == 200
    edits_1 = res.json()["edit_decisions"]

    # Verify baseline AI decisions
    zoomed_cuts_1 = [c for c in edits_1.get("cuts", []) if c.get("transform", {}).get("scale", 1.0) > 1.0]
    assert len(zoomed_cuts_1) > 0
    assert zoomed_cuts_1[0]["transform"]["scale"] == 1.25  # Default baseline zoom

    # Modify zoom preference: reduce from 1.25x to 1.10x
    for c in edits_1["cuts"]:
        if c.get("transform", {}).get("scale", 1.0) > 1.0:
            c["transform"]["scale"] = 1.10

    # Modify caption highlight color: change from #22D3EE to #FACC15
    th_props = edits_1.setdefault("metadata", {}).setdefault("talking_head_props", {})
    th_props["highlightColor"] = "#FACC15"

    # Save user adjustments
    res = client.put(
        f"/api/project/{p1_id}/edit-decisions",
        json={
            "edit_decisions": edits_1,
            "commit_message": "User reduced zoom intensity to 1.10x and changed caption highlight to yellow",
        },
    )
    assert res.status_code == 200
    assert res.json()["recorded_corrections"] >= 1

    # Fetch recorded corrections
    res = client.get(f"/api/preferences/corrections/list?project_id={p1_id}")
    assert res.status_code == 200
    corrs = res.json()["corrections"]
    assert len(corrs) >= 1

    # Explicitly approve corrections for future projects
    for c in corrs:
        res = client.post(
            f"/api/preferences/corrections/{c['correction_id']}/approve",
            json={"apply_to_future": True, "context_constraints": {"target_aspect": "9:16"}},
        )
        assert res.status_code == 200

    # Confirm memory now contains approved preferences
    res = client.get("/api/preferences")
    assert res.status_code == 200
    learned_prefs = res.json()["preferences"]
    assert len(learned_prefs) >= 1
    zoom_pref = next((p for p in learned_prefs if p["parameter_key"] == "zoom_scale"), None)
    assert zoom_pref is not None
    assert zoom_pref["preferred_value"] == 1.10

    # =========================================================================
    # PART 2: SECOND PROJECT — Personalized AI Planning & Rendering
    # =========================================================================
    p2_id = "project_2_personalized"
    res = client.post(
        "/api/projects",
        json={"project_id": p2_id, "title": "Project 2 - Personalized", "aspect_ratio": "9:16"},
    )
    assert res.status_code == 200

    # Upload second video (sample_edited.mp4)
    with open(sample_edited, "rb") as f:
        res = client.post(
            f"/api/project/{p2_id}/upload",
            data={"category": "video"},
            files={"file": ("sample_edited.mp4", f, "video/mp4")},
        )
    assert res.status_code == 200
    p2_video_path = res.json()["media"]["relative_path"]

    # Generate AI plan WITH Personalization enabled
    res = client.post(
        f"/api/project/{p2_id}/generate-edit",
        json={
            "user_instruction": "High energy punchy edit. Fast jump cuts, punch in zooms on metrics, and dynamic captions.",
            "video_path": p2_video_path,
            "target_aspect": "9:16",
            "cut_aggressiveness": "aggressive",
            "zoom_intensity": "standard",
            "enable_personalization": True,
        },
    )
    assert res.status_code == 200
    job_id_2 = res.json()["job_id"]

    for _ in range(60):
        time.sleep(0.5)
        job = job_manager.get_job(job_id_2)
        if job and job.status in ("completed", "failed"):
            break
    assert job and job.status == "completed", f"Plan 2 failed: {job.error if job else 'timeout'}"

    # Verify Personalized Decisions & Provenance
    res = client.get(f"/api/project/{p2_id}/edit-decisions")
    assert res.status_code == 200
    edits_personalized = res.json()["edit_decisions"]

    # 1. Verify zoom cuts adopted learned 1.10x zoom
    p_zoomed_cuts = [c for c in edits_personalized.get("cuts", []) if c.get("transform", {}).get("scale", 1.0) > 1.0]
    assert len(p_zoomed_cuts) > 0
    for zc in p_zoomed_cuts:
        assert zc["transform"]["scale"] == 1.10
        prov = zc["transform"]["zoom_provenance"]
        assert prov["decision_source"] == "learned_preference"
        assert prov["preference_id"] == zoom_pref["preference_id"]

    # 2. Verify caption highlight adopted learned #FACC15
    p_th = edits_personalized.get("metadata", {}).get("talking_head_props", {})
    assert p_th.get("highlightColor") == "#FACC15"

    # 3. Verify metadata records active personalization
    assert edits_personalized["metadata"]["personalization"]["enabled"] is True

    # Render Preview
    res = client.post(
        f"/api/project/{p2_id}/render",
        json={"mode": "preview", "aspect_ratio": "9:16", "fps": 25},
    )
    assert res.status_code == 200
    render_job_id = res.json()["job_id"]

    for _ in range(120):
        time.sleep(1.0)
        r_job = job_manager.get_job(render_job_id)
        if r_job and r_job.status in ("completed", "failed"):
            break
    assert r_job and r_job.status == "completed", f"Render failed: {r_job.error if r_job else 'timeout'}"

    # Run Automatic QA Inspection
    res = client.post(f"/api/project/{p2_id}/qa-inspect", json={})
    assert res.status_code == 200
    qa_data = res.json()["qa_report"]
    assert "quality_score" in qa_data
    assert qa_data["quality_score"] >= 80.0

    # =========================================================================
    # PART 3: COMPARISON PLAN — Personalization Disabled Baseline
    # =========================================================================
    p3_id = "project_2_baseline_comparison"
    res = client.post(
        "/api/projects",
        json={"project_id": p3_id, "title": "Project 2 - Baseline Comparison", "aspect_ratio": "9:16"},
    )
    assert res.status_code == 200

    # Upload exact same video
    with open(sample_edited, "rb") as f:
        res = client.post(
            f"/api/project/{p3_id}/upload",
            data={"category": "video"},
            files={"file": ("sample_edited.mp4", f, "video/mp4")},
        )
    assert res.status_code == 200
    p3_video_path = res.json()["media"]["relative_path"]

    # Generate AI plan WITHOUT Personalization
    res = client.post(
        f"/api/project/{p3_id}/generate-edit",
        json={
            "user_instruction": "High energy punchy edit. Fast jump cuts, punch in zooms on metrics, and dynamic captions.",
            "video_path": p3_video_path,
            "target_aspect": "9:16",
            "cut_aggressiveness": "aggressive",
            "zoom_intensity": "standard",
            "enable_personalization": False,
        },
    )
    assert res.status_code == 200
    job_id_3 = res.json()["job_id"]

    for _ in range(60):
        time.sleep(0.5)
        job = job_manager.get_job(job_id_3)
        if job and job.status in ("completed", "failed"):
            break
    assert job and job.status == "completed"

    res = client.get(f"/api/project/{p3_id}/edit-decisions")
    assert res.status_code == 200
    edits_baseline = res.json()["edit_decisions"]

    # =========================================================================
    # COMPARISON & PROVENANCE AUDIT
    # =========================================================================
    base_zoomed = [c for c in edits_baseline.get("cuts", []) if c.get("transform", {}).get("scale", 1.0) > 1.0]
    assert len(base_zoomed) > 0
    # In baseline, zoom scale is the standard 1.25x
    assert base_zoomed[0]["transform"]["scale"] == 1.25
    assert base_zoomed[0]["transform"]["zoom_provenance"]["decision_source"] == "deterministic_heuristic"

    # In personalized, zoom scale was 1.10x with provenance learned_preference
    assert p_zoomed_cuts[0]["transform"]["scale"] == 1.10
    assert p_zoomed_cuts[0]["transform"]["zoom_provenance"]["decision_source"] == "learned_preference"

    # In baseline, caption color is standard #22D3EE cyan
    base_color = edits_baseline.get("metadata", {}).get("talking_head_props", {}).get("highlightColor")
    assert base_color != "#FACC15"  # Did not use user preference
    assert p_th.get("highlightColor") == "#FACC15"  # Successfully personalized

    print(
        f"\n[E2E Personalization Verified] "
        f"Baseline Zoom: {base_zoomed[0]['transform']['scale']}x vs "
        f"Personalized Zoom: {p_zoomed_cuts[0]['transform']['scale']}x. "
        f"Baseline Highlight: {base_color} vs "
        f"Personalized Highlight: {p_th.get('highlightColor')}."
    )
