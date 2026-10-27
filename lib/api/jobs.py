"""Background Job Runner, Lifecycle Management & System Monitor (Phase 11).

Provides:
- Persistent SQLite-backed task tracking that survives server crashes & restarts.
- Strict concurrency control (1 heavy render at a time for 16GB Intel CPU).
- Granular progress reporting with real measured progress updates.
- Complete process-tree cancellation via psutil.
- Safe crash recovery: detection of interrupted jobs and resumption from stage checkpoints.
- System telemetry: CPU %, RAM GB/%, active renders, available memory safety checks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import psutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from lib.api.job_store import DEFAULT_JOBS_DB_PATH, JobRecord, JobStatus, PersistentJobStore
from lib.paths import PROJECTS_DIR, REPO_ROOT

logger = logging.getLogger("openmontage.jobs")


class JobManager:
    """Singleton JobManager orchestrating video processing background tasks with SQLite persistence."""

    _instance: Optional[JobManager] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[Path | str] = None) -> JobManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager(db_path)
            return cls._instance

    def _init_manager(self, db_path: Optional[Path | str] = None) -> None:
        self.store = PersistentJobStore(db_path or DEFAULT_JOBS_DB_PATH)
        self.active_processes: dict[str, subprocess.Popen] = {}
        self.active_pids: dict[str, int] = {}
        self._live_records: dict[str, JobRecord] = {}
        self.render_semaphore = threading.Semaphore(1)  # Only 1 heavy render at once
        self._queue: list[tuple[JobRecord, Callable[[JobRecord, Callable[[float, str], None]], dict[str, Any]]]] = []
        self._queue_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._executor_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._executor_thread.start()

        self.analysis_cache_dir = REPO_ROOT / ".cache" / "analysis"
        self.analysis_cache_dir.mkdir(parents=True, exist_ok=True)

    def get_system_metrics(self) -> dict[str, Any]:
        """Collect current system performance telemetry."""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        all_jobs = self.store.list_jobs(limit=100)
        active_renders = sum(
            1 for j in all_jobs
            if j.status in (JobStatus.RENDERING.value, "running") and j.job_type.startswith("render_")
        )
        queued_count = sum(1 for j in all_jobs if j.status == JobStatus.QUEUED.value)
        interrupted_count = sum(1 for j in all_jobs if j.status == JobStatus.INTERRUPTED.value)

        return {
            "cpu_percent": cpu,
            "ram_total_gb": round(mem.total / (1024 ** 3), 1),
            "ram_used_gb": round(mem.used / (1024 ** 3), 1),
            "ram_available_gb": round(mem.available / (1024 ** 3), 1),
            "ram_percent": mem.percent,
            "active_renders": active_renders,
            "queued_jobs": queued_count,
            "interrupted_jobs": interrupted_count,
            "hardware_note": "Optimized for Intel Core i7-13620H (16 GB RAM)",
        }

    def compute_file_hash(self, path: Path) -> str:
        """Compute stable hash of file for deterministic caching."""
        stat = path.stat()
        hasher = hashlib.sha256()
        hasher.update(f"{stat.st_size}_{stat.st_mtime}_{path.name}".encode())
        return hasher.hexdigest()[:16]

    def get_cached_analysis(self, video_path: Path) -> Optional[dict[str, Any]]:
        """Retrieve cached analysis if source video content identity matches."""
        if not video_path.is_file():
            return None
        cache_key = self.compute_file_hash(video_path)
        cache_file = self.analysis_cache_dir / f"{cache_key}.json"
        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def store_cached_analysis(self, video_path: Path, data: dict[str, Any]) -> None:
        """Cache analysis result for source video."""
        if not video_path.is_file():
            return
        cache_key = self.compute_file_hash(video_path)
        cache_file = self.analysis_cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to store analysis cache: %s", e)

    def register_process(self, job_id: str, proc: subprocess.Popen) -> None:
        """Register active child subprocess for tree tracking and clean cancellation."""
        self.active_processes[job_id] = proc
        if proc.pid:
            self.active_pids[job_id] = proc.pid
            job = self.store.get_job(job_id)
            if job:
                job.pid = proc.pid
                self.store.save_job(job)

    def submit_job(
        self,
        project_id: str,
        job_type: str,
        target_fn: Callable[[JobRecord, Callable[[float, str], None]], dict[str, Any]],
        input_metadata: Optional[dict[str, Any]] = None,
        priority: int = 10,
    ) -> JobRecord:
        """Queue a new background task with persistence and priority ordering."""
        job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        record = JobRecord(
            job_id=job_id,
            project_id=project_id,
            job_type=job_type,
            status=JobStatus.QUEUED.value,
            stage="Waiting in queue",
            input_metadata=input_metadata or {},
        )
        self.store.save_job(record)
        self._live_records[job_id] = record

        with self._queue_lock:
            self._queue.append((priority, record, target_fn))
            self._queue.sort(key=lambda item: item[0])

        logger.info("Enqueued persistent job %s (%s, priority=%d) for project %s", job_id, job_type, priority, project_id)
        return record

    def get_queue_info(self, job_id: str) -> Optional[dict[str, Any]]:
        """Retrieve 1-based queue position and total queued count."""
        with self._queue_lock:
            for idx, item in enumerate(self._queue):
                if item[1].job_id == job_id:
                    return {
                        "queue_position": idx + 1,
                        "total_queued": len(self._queue),
                        "priority": item[0],
                    }
        return None

    def cancel_job(self, job_id: str) -> bool:
        """Request clean cancellation of an active or queued job, killing child processes."""
        job = self.store.get_job(job_id)
        live = self._live_records.get(job_id)
        if not job and not live:
            return False

        target = job or live
        target.cancel_requested = True
        target.logs.append(f"[{time.strftime('%X')}] Cancellation requested by user.")

        if live:
            live.cancel_requested = True
            live.status = JobStatus.CANCELLED.value
            live.stage = "Cancelled"
            live.completed_at = time.time()

        if target.status == JobStatus.QUEUED.value:
            target.status = JobStatus.CANCELLED.value
            target.stage = "Cancelled before execution"
            target.completed_at = time.time()
            self.store.save_job(target)
            return True

        # Kill registered process and all descendants
        pid = self.active_pids.get(job_id) or target.pid
        proc = self.active_processes.get(job_id)
        if pid:
            self._kill_process_tree(pid)
            target.logs.append(f"[{time.strftime('%X')}] Subprocess tree (PID {pid}) terminated.")

        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass

        target.status = JobStatus.CANCELLED.value
        target.stage = "Job cancelled safely"
        target.completed_at = time.time()
        self.store.save_job(target)
        return True

    def _kill_process_tree(self, pid: int) -> None:
        """Recursively kill a process and all its children on Windows."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            gone, alive = psutil.wait_procs(children, timeout=1.0)
            for child in alive:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.terminate()
            parent.wait(timeout=1.0)
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.warning("Error terminating process tree for PID %s: %s", pid, e)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._live_records.get(job_id) or self.store.get_job(job_id)

    def list_jobs(self, project_id: Optional[str] = None) -> list[JobRecord]:
        return self.store.list_jobs(project_id)

    def clear_completed_jobs(self, project_id: Optional[str] = None) -> int:
        return self.store.clear_completed_jobs(project_id)

    def recover_job(self, job_id: str) -> Optional[JobRecord]:
        """Mark an interrupted/failed job as recoverable/queued for resumption."""
        rec = self.get_job(job_id)
        if not rec:
            return None
        rec.status = JobStatus.QUEUED.value
        rec.stage = f"Recovered from checkpoint '{rec.last_checkpoint or 'initial'}'"
        rec.recoverable = True
        self.store.save_job(rec)
        self._live_records[job_id] = rec
        return rec

    def _worker_loop(self) -> None:
        while not self._shutdown_event.is_set():
            item = None
            with self._queue_lock:
                if self._queue:
                    item = self._queue.pop(0)

            if not item:
                time.sleep(0.2)
                continue

            if len(item) == 3:
                priority, record, target_fn = item
            else:
                record, target_fn = item

            # Check if cancelled before starting
            latest = self.store.get_job(record.job_id)
            if latest and latest.cancel_requested:
                latest.status = JobStatus.CANCELLED.value
                latest.completed_at = time.time()
                self.store.save_job(latest)
                continue

            is_heavy_render = record.job_type.startswith("render_")
            if is_heavy_render:
                self.render_semaphore.acquire()

            # Resource Guard: Wait if available RAM < 1.0 GB
            while psutil.virtual_memory().available < (1.0 * 1024 ** 3):
                logger.warning("Low memory guard active (< 1GB available). Pausing task %s...", record.job_id)
                time.sleep(1.0)
                if record.cancel_requested:
                    break

            try:
                # Map active status based on job type
                if record.job_type == "analyze":
                    record.status = JobStatus.ANALYZING.value
                elif record.job_type == "generate_edit":
                    record.status = JobStatus.PLANNING.value
                elif record.job_type.startswith("render_"):
                    record.status = JobStatus.RENDERING.value
                elif record.job_type == "qa_inspect":
                    record.status = JobStatus.QUALITY_CHECK.value
                else:
                    record.status = "running"

                record.started_at = time.time()
                record.progress = 5.0
                record.stage = "Starting execution..."
                record.logs.append(f"[{time.strftime('%X')}] Execution started.")
                self.store.save_job(record)

                def progress_cb(pct: float, stage_msg: str, checkpoint_stage: Optional[str] = None) -> None:
                    if record.cancel_requested:
                        raise InterruptedError("Job cancelled by user request")
                    record.progress = min(99.0, max(0.0, pct))
                    record.stage = stage_msg
                    if checkpoint_stage:
                        record.last_checkpoint = checkpoint_stage
                    record.logs.append(f"[{time.strftime('%X')}] [{record.progress:.0f}%] {stage_msg}")
                    self.store.save_job(record)

                result = target_fn(record, progress_cb)

                if record.cancel_requested:
                    record.status = JobStatus.CANCELLED.value
                    record.stage = "Cancelled"
                else:
                    record.status = JobStatus.COMPLETED.value
                    record.progress = 100.0
                    record.stage = "Finished successfully"
                    record.result = result
                    record.logs.append(f"[{time.strftime('%X')}] [100%] Completed successfully.")
            except InterruptedError:
                record.status = JobStatus.CANCELLED.value
                record.stage = "Cancelled by user"
                record.logs.append(f"[{time.strftime('%X')}] Process interrupted.")
            except Exception as e:
                logger.exception("Job %s failed: %s", record.job_id, e)
                record.status = JobStatus.FAILED.value
                record.error = str(e)
                record.stage = f"Failed: {str(e)[:100]}"
                record.logs.append(f"[{time.strftime('%X')}] Error: {str(e)}")
            finally:
                record.completed_at = time.time()
                self.active_processes.pop(record.job_id, None)
                self.active_pids.pop(record.job_id, None)
                self.store.save_job(record)
                if is_heavy_render:
                    self.render_semaphore.release()


job_manager = JobManager()
