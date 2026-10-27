"""End-to-End User Workflow Test for OpenMontage Phase 9.

Tests the full 14-step user workflow:
1. Create a new project in the UI/API.
2. Import footage (sample_raw.mp4).
3. Enter editing instructions.
4. Run AI analysis.
5. Generate editing decisions.
6. Display timeline events.
7. Modify at least one caption.
8. Modify one motion graphic.
9. Preview the changes.
10. Export an MP4.
11. Run automatic QA.
12. Inspect final output.
13. Reopen the saved project.
14. Confirm edits persist.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backlot import server as server_mod
from lib.paths import REPO_ROOT, PROJECTS_DIR
from lib.api.jobs import job_manager


@pytest.fixture
def e2e_client(tmp_path, monkeypatch):
    temp_projects = tmp_path / "projects"
    temp_projects.mkdir(parents=True, exist_ok=True)
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
        yield client, temp_projects


def test_complete_14_step_e2e_workflow(e2e_client):
    client, temp_projects = e2e_client
    project_id = "e2e_showcase_proj"
    sample_mp4 = REPO_ROOT / "media" / "sample" / "sample_raw.mp4"
    assert sample_mp4.is_file(), f"Sample footage missing: {sample_mp4}"

    # -------------------------------------------------------------
    # Step 1: Create a new project in the UI
    # -------------------------------------------------------------
    create_payload = {
        "project_id": project_id,
        "title": "E2E Showcase Reel",
        "pipeline_type": "talking-head",
        "aspect_ratio": "9:16",
    }
    res_create = client.post("/api/projects", json=create_payload)
    assert res_create.status_code == 200, res_create.text
    create_data = res_create.json()
    assert create_data["project_id"] == project_id
    assert (temp_projects / project_id / "project.json").is_file()

    # -------------------------------------------------------------
    # Step 2: Import footage (sample_raw.mp4)
    # -------------------------------------------------------------
    with open(sample_mp4, "rb") as f:
        res_upload = client.post(
            f"/api/project/{project_id}/upload",
            data={"category": "video"},
            files={"file": ("sample_raw.mp4", f, "video/mp4")},
        )
    assert res_upload.status_code == 200, res_upload.text
    upload_res = res_upload.json()
    assert upload_res["media"]["name"] == "sample_raw.mp4"
    assert upload_res["media"]["is_primary"] is True

    # Check project media listing
    res_media = client.get(f"/api/project/{project_id}/media")
    assert res_media.status_code == 200
    media_items = res_media.json()
    assert len(media_items) >= 1
    assert any(m["name"] == "sample_raw.mp4" for m in media_items)

    # -------------------------------------------------------------
    # Step 3: Enter editing instructions
    # -------------------------------------------------------------
    user_prompt = (
        "Create a viral 9:16 vertical short. Cut dead air, add punchy stat cards, "
        "highlight key value metrics, and dynamic Hormozi captions."
    )

    # -------------------------------------------------------------
    # Step 4: Run AI analysis
    # -------------------------------------------------------------
    res_analyze = client.post(
        f"/api/project/{project_id}/analyze",
        json={"video_path": "assets/video/sample_raw.mp4", "quality_preset": "fast"},
    )
    assert res_analyze.status_code == 200, res_analyze.text
    analyze_job_id = res_analyze.json()["job_id"]

    # Wait for analysis job completion (up to 60s)
    for _ in range(120):
        status_res = client.get(f"/api/jobs/{analyze_job_id}").json()
        if status_res["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    assert status_res["status"] == "completed"

    # -------------------------------------------------------------
    # Step 5: Generate editing decisions
    # -------------------------------------------------------------
    res_gen = client.post(
        f"/api/project/{project_id}/generate-edit",
        json={
            "user_instruction": user_prompt,
            "video_path": "assets/video/sample_raw.mp4",
            "mode": "autonomous",
            "target_aspect": "9:16",
            "cut_aggressiveness": "balanced",
            "zoom_intensity": "dynamic",
            "caption_preset": "viral_dynamic",
        },
    )
    assert res_gen.status_code == 200, res_gen.text
    gen_job_id = res_gen.json()["job_id"]

    for _ in range(120):
        status_res = client.get(f"/api/jobs/{gen_job_id}").json()
        if status_res["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    assert status_res["status"] == "completed"

    # -------------------------------------------------------------
    # Step 6: Display timeline events
    # -------------------------------------------------------------
    res_edits = client.get(f"/api/project/{project_id}/edit-decisions")
    assert res_edits.status_code == 200
    edits = res_edits.json()["edit_decisions"]
    assert len(edits["cuts"]) >= 1
    assert len(edits["overlays"]) >= 1
    assert edits["subtitles"]["enabled"] is True
    assert len(edits["subtitles"]["words"]) >= 5

    initial_first_word = edits["subtitles"]["words"][0]["word"]
    initial_overlay_count = len(edits["overlays"])

    # -------------------------------------------------------------
    # Step 7: Modify at least one caption
    # -------------------------------------------------------------
    modified_edits = dict(edits)
    # Modify the first word token to an uppercase emphatic variant
    modified_edits["subtitles"]["words"][0]["word"] = "ATTENTION:"
    modified_edits["subtitles"]["words"][0]["start"] = 0.2

    # -------------------------------------------------------------
    # Step 8: Modify one motion graphic
    # -------------------------------------------------------------
    # Modify the first overlay to be a high-impact Stat Card
    modified_edits["overlays"][0]["type"] = "stat_card"
    modified_edits["overlays"][0]["content"] = {
        "value": "+94.2%",
        "label": "Viewer Retention Rate",
        "trend": "positive",
    }
    modified_edits["overlays"][0]["accentColor"] = "#f59e0b"
    modified_edits["overlays"][0]["animation"] = "spring"
    modified_edits["overlays"][0]["in_seconds"] = 1.0
    modified_edits["overlays"][0]["out_seconds"] = 4.5

    # Also add a second overlay
    new_overlay = {
        "id": "overlay_callout_manual",
        "type": "callout",
        "in_seconds": 5.0,
        "out_seconds": 8.0,
        "position": "lower_third",
        "accentColor": "#06b6d4",
        "animation": "slide",
        "content": {
            "title": "Pro Tip",
            "subtitle": "Always hook viewers in first 3 seconds",
            "callout_type": "tip",
        },
    }
    modified_edits["overlays"].append(new_overlay)

    # Save modified decisions
    res_save = client.put(
        f"/api/project/{project_id}/edit-decisions",
        json={"edit_decisions": modified_edits, "commit_message": "Manual caption & motion graphic adjustment"},
    )
    assert res_save.status_code == 200

    # -------------------------------------------------------------
    # Step 9: Preview the changes
    # -------------------------------------------------------------
    res_recheck = client.get(f"/api/project/{project_id}/edit-decisions")
    assert res_recheck.status_code == 200
    saved_edits = res_recheck.json()["edit_decisions"]
    # Check that caption was updated
    assert saved_edits["subtitles"]["words"][0]["word"] == "ATTENTION:"
    # Check that motion graphic was updated
    assert saved_edits["overlays"][0]["content"]["value"] == "+94.2%"
    assert len(saved_edits["overlays"]) == initial_overlay_count + 1

    # -------------------------------------------------------------
    # Step 10: Export an MP4
    # -------------------------------------------------------------
    res_render = client.post(
        f"/api/project/{project_id}/render",
        json={
            "mode": "preview",
            "resolution": "720x1280",
            "fps": 30,
            "output_filename": "preview_e2e_export.mp4",
        },
    )
    assert res_render.status_code == 200, res_render.text
    render_job_id = res_render.json()["job_id"]

    for _ in range(1200):
        render_status = client.get(f"/api/jobs/{render_job_id}").json()
        if render_status["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    assert render_status["status"] == "completed", f"Render failed: {render_status.get('error')}"

    # Verify exported file exists
    export_file = temp_projects / project_id / "renders" / "preview_e2e_export.mp4"
    assert export_file.is_file(), "Exported MP4 file does not exist on disk"
    assert export_file.stat().st_size > 1000, "Exported MP4 file is empty"

    # -------------------------------------------------------------
    # Step 11: Run automatic QA
    # -------------------------------------------------------------
    res_qa = client.post(
        f"/api/project/{project_id}/qa-inspect",
        json={"video_path": "renders/preview_e2e_export.mp4"},
    )
    assert res_qa.status_code == 200, res_qa.text
    qa_report = res_qa.json()["qa_report"]

    # -------------------------------------------------------------
    # Step 12: Inspect final output
    # -------------------------------------------------------------
    assert "quality_score" in qa_report
    assert "passed" in qa_report
    assert "severity_counts" in qa_report
    assert qa_report["duration_seconds"] > 0
    assert qa_report["quality_score"] >= 70.0
    assert "passing_threshold" in qa_report

    # -------------------------------------------------------------
    # Step 13: Reopen the saved project
    # -------------------------------------------------------------
    res_details = client.get(f"/api/project/{project_id}")
    assert res_details.status_code == 200
    details = res_details.json()
    assert details["project_id"] == project_id
    assert details["title"] == "E2E Showcase Reel"
    assert details["has_edits"] is True

    # -------------------------------------------------------------
    # Step 14: Confirm edits persist
    # -------------------------------------------------------------
    persisted_edits = details["edit_decisions"]
    assert persisted_edits is not None
    assert persisted_edits["subtitles"]["words"][0]["word"] == "ATTENTION:"
    assert persisted_edits["overlays"][0]["content"]["value"] == "+94.2%"
    assert any(o.get("id") == "overlay_callout_manual" for o in persisted_edits["overlays"])

    # Confirm history snapshots recorded
    res_hist = client.get(f"/api/project/{project_id}/history")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 2
    assert any("Manual caption" in h.get("commit_message", "") for h in history)
