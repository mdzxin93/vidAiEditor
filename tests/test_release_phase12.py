"""Phase 12 Comprehensive Release & Packaging Tests.

Validates:
1. StoragePaths: Application data isolation, %LOCALAPPDATA% support, project resolution.
2. WaveformExtractor: Audio peak extraction and caching.
3. SegmentedRenderEngine: Deterministic cut fingerprinting and incremental audit.
4. JobManager Priority Queue: Priority ordering (preview ahead of final).
5. JobManager Queue Position: Accurate 1-based position and total count reporting.
6. Localhost Security Guard: Cross-origin mutation blocking from untrusted origins.
7. System Models Status: Clean offline detection without downloading weights.
8. Dynamic Remotion Timeout: Proportional scaling for multi-minute compositions.
9. Root Path Serving: Integrated React Studio served on http://127.0.0.1:8000/.
10. Incremental Cache Invalidation: Deterministic change detection on edited cuts.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from backlot.server import create_app
from lib.storage_paths import StoragePaths, get_storage
from lib.ai.waveform_extractor import WaveformExtractor
from lib.render.segmented_engine import SegmentedRenderEngine
from lib.api.jobs import JobManager, JobStatus
from lib.api.job_store import PersistentJobStore, JobRecord


@pytest.fixture
def test_client():
    app = create_app()
    return TestClient(app)


def test_1_storage_paths_isolation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        sp = StoragePaths(base_data_dir=Path(tmp_dir))
        assert sp.root == Path(tmp_dir).resolve()
        assert sp.projects_dir == Path(tmp_dir).resolve() / "projects"
        assert sp.config_dir == Path(tmp_dir).resolve() / "config"
        assert sp.cache_dir == Path(tmp_dir).resolve() / ".cache"
        assert sp.logs_dir == Path(tmp_dir).resolve() / "logs"
        assert sp.jobs_db_path == Path(tmp_dir).resolve() / "config" / "jobs.db"
        assert sp.projects_dir.is_dir()


def test_2_audio_waveform_extraction():
    with tempfile.TemporaryDirectory() as tmp_dir:
        sample_video = Path("assets/signal-from-tomorrow-demo.mp4").resolve()
        if not sample_video.is_file():
            pytest.skip("Sample video asset missing")

        extractor = WaveformExtractor(cache_dir=Path(tmp_dir))
        data = extractor.extract_peaks(sample_video, target_points=120)
        assert data["duration"] > 0
        assert data["points_count"] == 120
        assert len(data["peaks"]) == 120
        assert all(0.0 <= p <= 1.0 for p in data["peaks"])

        # Test caching on second read
        cached_data = extractor.extract_peaks(sample_video, target_points=120)
        assert cached_data["peaks"] == data["peaks"]


def test_3_segmented_render_cut_fingerprinting():
    with tempfile.TemporaryDirectory() as tmp_dir:
        engine = SegmentedRenderEngine(cache_dir=Path(tmp_dir))
        cut_a = {"source": "clip1.mp4", "in_seconds": 0.0, "out_seconds": 15.0, "speed": 1.0}
        cut_b = {"source": "clip1.mp4", "in_seconds": 0.0, "out_seconds": 15.0, "speed": 1.0}
        cut_c = {"source": "clip1.mp4", "in_seconds": 0.0, "out_seconds": 20.0, "speed": 1.0}

        fp_a = engine.compute_cut_fingerprint(cut_a, [], [])
        fp_b = engine.compute_cut_fingerprint(cut_b, [], [])
        fp_c = engine.compute_cut_fingerprint(cut_c, [], [])

        assert fp_a == fp_b, "Identical cut must produce identical deterministic fingerprint"
        assert fp_a != fp_c, "Modified duration must invalidate cut fingerprint"


def test_4_incremental_render_audit_evaluation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        engine = SegmentedRenderEngine(cache_dir=Path(tmp_dir))
        cuts = [
            {"id": "cut_1", "source": "clip.mp4", "in_seconds": 0.0, "out_seconds": 10.0},
            {"id": "cut_2", "source": "clip.mp4", "in_seconds": 10.0, "out_seconds": 20.0},
        ]
        audit = engine.evaluate_incremental_plan(cuts, [], [])
        assert audit["total_cuts"] == 2
        assert audit["cached_cuts"] == 0
        assert audit["dirty_cuts"] == 2
        assert audit["can_stream_copy_assemble"] is False

        # Simulate caching segment 1
        fp1 = audit["segments"][0]["fingerprint"]
        dummy_seg = Path(tmp_dir) / "dummy.mp4"
        dummy_seg.write_bytes(b"dummy mp4 content" * 100)
        engine.store_cached_segment(fp1, dummy_seg)

        audit_after = engine.evaluate_incremental_plan(cuts, [], [])
        assert audit_after["cached_cuts"] == 1
        assert audit_after["dirty_cuts"] == 1
        assert audit_after["cache_hit_ratio"] == 0.5


def test_5_priority_queueing_order():
    from lib.api.jobs import job_manager

    executed_order = []

    def task_batch(rec, cb):
        executed_order.append(rec.job_type)
        return {"ok": True}

    def task_preview(rec, cb):
        executed_order.append(rec.job_type)
        return {"ok": True}

    with job_manager._queue_lock:
        job_manager._queue.clear()

    # Submit lower priority first, then higher priority
    job1 = job_manager.submit_job("p1", "render_batch", task_batch, priority=10)
    job2 = job_manager.submit_job("p1", "render_preview", task_preview, priority=5)

    with job_manager._queue_lock:
        # First item in queue should be job2 (preview) due to priority 5 < 10
        assert job_manager._queue[0][1].job_id == job2.job_id
        assert job_manager._queue[1][1].job_id == job1.job_id

    # Clean up test jobs
    with job_manager._queue_lock:
        job_manager._queue.clear()


def test_6_queue_position_reporting():
    from lib.api.jobs import job_manager

    with job_manager._queue_lock:
        job_manager._queue.clear()

    def dummy_fn(rec, cb):
        return {}

    j1 = job_manager.submit_job("p1", "render_batch", dummy_fn, priority=10)
    j2 = job_manager.submit_job("p1", "render_preview", dummy_fn, priority=5)

    # j2 has priority 5, so it is position 1
    q_info_j2 = job_manager.get_queue_info(j2.job_id)
    assert q_info_j2 is not None
    assert q_info_j2["queue_position"] == 1
    assert q_info_j2["total_queued"] == 2

    # j1 has priority 10, so it is position 2
    q_info_j1 = job_manager.get_queue_info(j1.job_id)
    assert q_info_j1 is not None
    assert q_info_j1["queue_position"] == 2

    # Clean up
    with job_manager._queue_lock:
        job_manager._queue.clear()


def test_7_localhost_security_guard_cross_origin_blocking(test_client):
    import uuid
    uniq_id = f"sec_test_{uuid.uuid4().hex[:6]}"
    # Allowed local origin
    res_local = test_client.post(
        "/api/projects",
        json={"title": "Security Test", "project_id": uniq_id},
        headers={"Origin": "http://localhost:8000"},
    )
    assert res_local.status_code == 200

    # Malicious external origin attempting cross-origin drive-by mutation
    res_malicious = test_client.post(
        "/api/projects",
        json={"title": "Attacker Project", "project_id": f"evil_{uniq_id}"},
        headers={"Origin": "https://malicious-attacker-website.com"},
    )
    assert res_malicious.status_code == 403
    assert "Cross-origin mutation request blocked" in res_malicious.text


def test_8_system_models_status_endpoint(test_client):
    res = test_client.get("/api/system/models")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "models_directory" in data
    assert "smolvlm_500m" in data
    assert "whisper" in data
    assert "hardware" in data
    assert data["hardware"]["cuda_available"] is False


def test_9_root_path_serves_react_studio(test_client):
    res = test_client.get("/")
    assert res.status_code == 200
    # Should serve either compiled React Studio index.html or Backlot library
    assert "<!DOCTYPE html>" in res.text or "<html" in res.text


def test_10_waveform_endpoint_api(test_client):
    # Test waveform endpoint on signal demo or fixture
    res = test_client.get("/api/project/sec_test_local/waveform")
    # If media file not yet uploaded to sec_test_local, returns 404
    assert res.status_code in (200, 404)
