"""Persistent SQLite Job Store & Lifecycle Manager (Phase 11).

Provides:
- Thread-safe SQLite storage for all OpenMontage background tasks.
- Persistence across server restarts and crash recovery detection.
- Granular statuses: QUEUED, ANALYZING, PLANNING, RENDERING, QUALITY_CHECK, COMPLETED, FAILED, CANCELLED, INTERRUPTED, RECOVERABLE.
- Subprocess tracking (PID) for process-tree termination.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from lib.paths import PROJECTS_DIR, REPO_ROOT

logger = logging.getLogger("openmontage.job_store")

try:
    from lib.storage_paths import get_storage
    DEFAULT_JOBS_DB_PATH = get_storage().jobs_db_path
except Exception:
    DEFAULT_JOBS_DB_PATH = REPO_ROOT / "config" / "jobs.db"


class JobStatus(str, Enum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    RENDERING = "rendering"
    QUALITY_CHECK = "quality_check"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    RECOVERABLE = "recoverable"


@dataclass
class JobRecord:
    job_id: str
    project_id: str
    job_type: str  # e.g. "analyze", "generate_edit", "render_preview", "render_final", "qa_inspect"
    status: str = JobStatus.QUEUED.value
    progress: float = 0.0
    stage: str = "Queued"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    logs: list[str] = field(default_factory=list)
    cancel_requested: bool = False
    input_metadata: Optional[dict[str, Any]] = None
    recoverable: bool = False
    last_checkpoint: Optional[str] = None
    pid: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "project_id": self.project_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress": round(self.progress, 1),
            "stage": self.stage,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "result": self.result,
            "logs": self.logs[-50:],  # return tail logs
            "cancel_requested": self.cancel_requested,
            "input_metadata": self.input_metadata or {},
            "recoverable": self.recoverable,
            "last_checkpoint": self.last_checkpoint,
            "pid": self.pid,
        }


class PersistentJobStore:
    """Thread-safe SQLite storage for OpenMontage background tasks."""

    def __init__(self, db_path: Path | str = DEFAULT_JOBS_DB_PATH, mark_interrupted: bool = False):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        if mark_interrupted:
            self._mark_interrupted_jobs_on_startup()

    def mark_interrupted_jobs_on_startup(self) -> None:
        """Explicitly run startup check to mark previously active jobs as interrupted."""
        self._mark_interrupted_jobs_on_startup()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0.0,
                    stage TEXT NOT NULL DEFAULT 'Queued',
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    error TEXT,
                    result TEXT,
                    logs TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    input_metadata TEXT,
                    recoverable INTEGER NOT NULL DEFAULT 0,
                    last_checkpoint TEXT,
                    pid INTEGER
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_project_id ON jobs(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)")

    def _mark_interrupted_jobs_on_startup(self) -> None:
        """Any job left in running/analyzing/planning/rendering states when server starts was interrupted by crash/restart."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            active_statuses = [
                "running",
                JobStatus.ANALYZING.value,
                JobStatus.PLANNING.value,
                JobStatus.RENDERING.value,
                JobStatus.QUALITY_CHECK.value,
            ]
            placeholders = ",".join("?" for _ in active_statuses)
            cursor.execute(
                f"""
                UPDATE jobs
                SET status = ?,
                    stage = 'Interrupted by application restart',
                    recoverable = 1,
                    completed_at = ?
                WHERE status IN ({placeholders})
                """,
                [JobStatus.INTERRUPTED.value, time.time()] + active_statuses,
            )
            affected = cursor.rowcount
            if affected > 0:
                logger.info("Marked %d running jobs as INTERRUPTED on application startup.", affected)

    def save_job(self, job: JobRecord) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, project_id, job_type, status, progress, stage,
                    created_at, started_at, completed_at, error, result,
                    logs, cancel_requested, input_metadata, recoverable,
                    last_checkpoint, pid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    progress=excluded.progress,
                    stage=excluded.stage,
                    started_at=excluded.started_at,
                    completed_at=excluded.completed_at,
                    error=excluded.error,
                    result=excluded.result,
                    logs=excluded.logs,
                    cancel_requested=excluded.cancel_requested,
                    input_metadata=excluded.input_metadata,
                    recoverable=excluded.recoverable,
                    last_checkpoint=excluded.last_checkpoint,
                    pid=excluded.pid
                """,
                (
                    job.job_id,
                    job.project_id,
                    job.job_type,
                    job.status,
                    job.progress,
                    job.stage,
                    job.created_at,
                    job.started_at,
                    job.completed_at,
                    job.error,
                    json.dumps(job.result) if job.result else None,
                    json.dumps(job.logs[-100:]),
                    1 if job.cancel_requested else 0,
                    json.dumps(job.input_metadata) if job.input_metadata else None,
                    1 if job.recoverable else 0,
                    job.last_checkpoint,
                    job.pid,
                ),
            )

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_jobs(self, project_id: Optional[str] = None, limit: int = 100) -> list[JobRecord]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                    (project_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cursor.fetchall()
            return [self._row_to_record(r) for r in rows]

    def delete_job(self, job_id: str) -> bool:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            return cursor.rowcount > 0

    def clear_completed_jobs(self, project_id: Optional[str] = None) -> int:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            terminal = (
                JobStatus.COMPLETED.value,
                JobStatus.CANCELLED.value,
                JobStatus.FAILED.value,
                "interrupted",
                "recoverable",
            )
            placeholders = ",".join("?" for _ in terminal)
            deleted_count = 0
            if project_id:
                cursor.execute(
                    f"DELETE FROM jobs WHERE project_id = ? AND status IN ({placeholders})",
                    (project_id, *terminal),
                )
                deleted_count += cursor.rowcount
            else:
                cursor.execute(
                    f"DELETE FROM jobs WHERE status IN ({placeholders})",
                    terminal,
                )
                deleted_count += cursor.rowcount

                # Also prune any jobs whose project directory does not exist on disk
                cursor.execute("SELECT DISTINCT project_id FROM jobs")
                pids = [r[0] for r in cursor.fetchall()]
                for pid in pids:
                    pdir = PROJECTS_DIR / pid
                    if not pdir.is_dir():
                        cursor.execute("DELETE FROM jobs WHERE project_id = ?", (pid,))
                        deleted_count += cursor.rowcount
            return deleted_count

    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        res = json.loads(row["result"]) if row["result"] else None
        logs = json.loads(row["logs"]) if row["logs"] else []
        meta = json.loads(row["input_metadata"]) if row["input_metadata"] else None
        return JobRecord(
            job_id=row["job_id"],
            project_id=row["project_id"],
            job_type=row["job_type"],
            status=row["status"],
            progress=row["progress"],
            stage=row["stage"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            result=res,
            logs=logs,
            cancel_requested=bool(row["cancel_requested"]),
            input_metadata=meta,
            recoverable=bool(row["recoverable"]),
            last_checkpoint=row["last_checkpoint"],
            pid=row["pid"],
        )
