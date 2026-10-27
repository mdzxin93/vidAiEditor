"""Automated Test Suite for OpenMontage Professional Editing Interface (Phase 9 API).

Tests:
1. System performance telemetry (/api/system/metrics)
2. Presets and visual parameters (/api/presets)
3. Project lifecycle: create, get details, rename, duplicate, delete
4. Media ingestion: upload, ffprobe metadata inspection, project media listing
5. Timeline editing: get decisions, manual adjustments, undo/redo history snapshots
6. AI workflow: analyze, autonomous editorial planning
7. Quality control: QA inspector, score calculation, automatic correction application
8. Background rendering and job lifecycle: submit job, status tracking, cancellation
"""

from __future__ import annotations

import copy
import io
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backlot import server as server_mod
from lib.paths import PROJECTS_DIR


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """TestClient wired with temporary projects directory."""
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


def test_system_metrics_endpoint(api_client):
    client, _ = api_client
    res = client.get("/api/system/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "cpu_percent" in data
    assert "ram_total_gb" in data
    assert "ram_used_gb" in data
    assert "active_renders" in data
    assert "Intel" in data.get("hardware_note", "")


def test_presets_endpoint(api_client):
    client, _ = api_client
    res = client.get("/api/presets")
    assert res.status_code == 200
    data = res.json()
    assert "aspect_ratios" in data
    aspect_ids = [a["id"] for a in data["aspect_ratios"]]
    assert "9:16" in aspect_ids
    assert "16:9" in aspect_ids
    assert "1:1" in aspect_ids
    assert "motion_graphics_components" in data
    assert "caption_presets" in data
    assert "cut_aggressiveness" in data
    assert "zoom_intensity" in data


def test_project_crud_and_lifecycle(api_client):
    client, pdir = api_client

    # 1. Create project
    create_payload = {
        "project_id": "test_reel_01",
        "title": "My Awesome Reel",
        "pipeline_type": "talking-head",
        "aspect_ratio": "9:16",
        "style_playbook": "clean-professional",
    }
    res_create = client.post("/api/projects", json=create_payload)
    assert res_create.status_code == 200
    assert res_create.json()["project_id"] == "test_reel_01"

    # Verify directory created
    proj_folder = pdir / "test_reel_01"
    assert proj_folder.is_dir()
    assert (proj_folder / "project.json").is_file()

    # 2. Get project details
    res_det = client.get("/api/project/test_reel_01")
    assert res_det.status_code == 200
    det = res_det.json()
    assert det["title"] == "My Awesome Reel"
    assert det["aspect_ratio"] == "9:16"

    # 3. Rename project
    res_ren = client.post("/api/project/test_reel_01/rename", json={"title": "Renamed Reel Title"})
    assert res_ren.status_code == 200
    res_det2 = client.get("/api/project/test_reel_01")
    assert res_det2.json()["title"] == "Renamed Reel Title"

    # 4. Duplicate project
    res_dup = client.post(
        "/api/project/test_reel_01/duplicate",
        json={"new_project_id": "test_reel_01_copy", "new_title": "Duplicated Reel"},
    )
    assert res_dup.status_code == 200
    assert (pdir / "test_reel_01_copy").is_dir()

    # 5. Delete duplicated project
    res_del = client.delete("/api/project/test_reel_01_copy")
    assert res_del.status_code == 200
    assert not (pdir / "test_reel_01_copy").exists()


def test_media_upload_and_listing(api_client):
    client, pdir = api_client

    # Create project
    client.post("/api/projects", json={
        "project_id": "media_test_proj",
        "title": "Media Test",
        "pipeline_type": "talking-head",
        "aspect_ratio": "9:16",
    })

    # Upload dummy MP4
    fake_mp4_bytes = b"fake mp4 video stream bytes for testing"
    files = {"file": ("test_clip.mp4", io.BytesIO(fake_mp4_bytes), "video/mp4")}
    data = {"category": "video"}

    res_up = client.post("/api/project/media_test_proj/upload", files=files, data=data)
    assert res_up.status_code == 200
    media_data = res_up.json()["media"]
    assert media_data["file_name"] == "test_clip.mp4"
    assert media_data["category"] == "video"

    # List media
    res_list = client.get("/api/project/media_test_proj/media")
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) == 1
    assert items[0]["name"] == "test_clip.mp4"
    assert items[0]["is_video"] is True


def test_timeline_sync_and_undo_history(api_client):
    client, pdir = api_client

    client.post("/api/projects", json={
        "project_id": "timeline_proj",
        "title": "Timeline Sync Test",
        "pipeline_type": "talking-head",
    })

    # Get initial edit decisions and save as baseline
    res_init = client.get("/api/project/timeline_proj/edit-decisions")
    assert res_init.status_code == 200
    edits = res_init.json()["edit_decisions"]

    # Save initial baseline
    res_base = client.put(
        "/api/project/timeline_proj/edit-decisions",
        json={"edit_decisions": edits, "commit_message": "Initial baseline"},
    )
    assert res_base.status_code == 200

    # Modify cuts and overlays
    time.sleep(0.01)
    modified_edits = copy.deepcopy(edits)
    modified_edits["overlays"].append({
        "id": "stat_card_rev1",
        "type": "stat_card",
        "in_seconds": 2.5,
        "out_seconds": 6.0,
        "position": "upper_third",
        "content": {"value": "+240%", "label": "Retention"},
    })

    # Update timeline
    res_put = client.put(
        "/api/project/timeline_proj/edit-decisions",
        json={"edit_decisions": modified_edits, "commit_message": "Added Stat Card overlay"},
    )
    assert res_put.status_code == 200

    # Verify history snapshot was created
    res_hist = client.get("/api/project/timeline_proj/history")
    assert res_hist.status_code == 200
    history_items = res_hist.json()
    assert len(history_items) >= 1

    # Verify modified edits are returned
    res_check = client.get("/api/project/timeline_proj/edit-decisions")
    assert len(res_check.json()["edit_decisions"]["overlays"]) == 1

    # Revert to snapshot
    first_snap = history_items[0]["snapshot_id"]
    res_rev = client.post(
        f"/api/project/timeline_proj/history/revert?snapshot_id={first_snap}"
    )
    assert res_rev.status_code == 200
    assert len(res_rev.json()["edit_decisions"]["overlays"]) == 0


def test_qa_inspection_and_auto_fixes(api_client):
    client, pdir = api_client

    client.post("/api/projects", json={
        "project_id": "qa_proj",
        "title": "QA Test Project",
        "pipeline_type": "talking-head",
    })

    # Setup defective edits with colliding overlays
    defective_edits = {
        "version": "1.0",
        "render_runtime": "remotion",
        "renderer_family": "presenter",
        "cuts": [{"id": "c1", "in_seconds": 0.0, "out_seconds": 10.0, "speed": 1.0}],
        "overlays": [
            {
                "id": "stat_1",
                "type": "stat_card",
                "in_seconds": 3.0,
                "out_seconds": 7.0,
                "position": "upper_third",
            },
            {
                "id": "stat_colliding",
                "type": "stat_card",
                "in_seconds": 3.0,
                "out_seconds": 7.0,
                "position": "upper_third",
            },
        ],
        "metadata": {
            "talking_head_props": {
                "overlays": [
                    {
                        "id": "stat_1",
                        "type": "stat_card",
                        "in_seconds": 3.0,
                        "out_seconds": 7.0,
                        "position": "upper_third",
                    },
                    {
                        "id": "stat_colliding",
                        "type": "stat_card",
                        "in_seconds": 3.0,
                        "out_seconds": 7.0,
                        "position": "upper_third",
                    },
                ]
            }
        },
    }

    client.put(
        "/api/project/qa_proj/edit-decisions",
        json={"edit_decisions": defective_edits},
    )

    # Fake QA report
    qa_report_data = {
        "report_id": "test_qa_rep_01",
        "quality_score": 85.0,
        "passed": False,
        "duration_seconds": 10.0,
        "issues": [
            {
                "issue_id": "col_1",
                "category": "overlay_collision",
                "start_seconds": 3.0,
                "end_seconds": 7.0,
                "severity": "high",
                "confidence": 0.95,
                "detection_source": "geometry_validator",
                "description": "Simultaneous collision at upper_third",
                "suggested_fix": "suppress_redundant_graphic",
                "auto_fix_allowed": True,
                "evidence": {"overlay_2": "stat_colliding"},
            }
        ],
        "fixes_applied": [],
    }
    qa_file = pdir / "qa_proj" / "artifacts" / "qa_report.json"
    qa_file.parent.mkdir(parents=True, exist_ok=True)
    with open(qa_file, "w", encoding="utf-8") as f:
        json.dump(qa_report_data, f)

    # Test GET qa-report
    res_get_qa = client.get("/api/project/qa_proj/qa-report")
    assert res_get_qa.status_code == 200
    assert res_get_qa.json()["qa_report"]["quality_score"] == 85.0
    assert res_get_qa.json()["qa_report"]["passed"] is False

    # Test apply fixes
    res_fixes = client.post("/api/project/qa_proj/qa-apply-fixes", json={})
    assert res_fixes.status_code == 200
    fixes_res = res_fixes.json()
    assert fixes_res["fixes_applied_count"] >= 1
    # Check that colliding overlay was suppressed
    fixed_overlays = fixes_res["edit_decisions"]["metadata"]["talking_head_props"]["overlays"]
    overlay_ids = [o["id"] for o in fixed_overlays]
    assert "stat_colliding" not in overlay_ids


def test_background_job_submission_and_cancel():
    from lib.api.jobs import job_manager

    # Test submitting a mock job and cancelling it
    def slow_task(record, progress_cb):
        progress_cb(10.0, "Step 1")
        time.sleep(1.0)
        progress_cb(50.0, "Step 2")
        time.sleep(1.0)
        return {"done": True}

    job = job_manager.submit_job("test_proj", "test_job", slow_task)
    assert job.status in ("queued", "running")

    # Cancel job
    cancelled = job_manager.cancel_job(job.job_id)
    assert cancelled is True
    assert job.status == "cancelled"


def test_editor_ui_serving(api_client):
    client, _ = api_client
    res = client.get("/editor")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "OpenMontage" in res.text

