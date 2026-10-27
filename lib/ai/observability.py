"""Observability and structured logging for autonomous editing jobs."""

from __future__ import annotations

import json
import logging
import platform
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class JobObservabilityMetrics:
    job_id: str
    user_instruction: str
    source_video: str
    selected_provider: str
    decision_source: str  # "model_generated" | "heuristic_fallback"
    device: str
    cpu_architecture: str = "Intel Core i7-13620H (10 Cores: 6P+4E, 16 Threads)"
    ram_total_gb: float = 16.0
    ram_free_gb: float = 3.0
    vram_total_gb: float = 0.0
    vram_free_gb: float = 0.0
    video_analysis_duration_sec: float = 0.0
    planning_duration_sec: float = 0.0
    render_duration_sec: float = 0.0
    total_pipeline_duration_sec: float = 0.0
    json_validation_failures: int = 0
    inference_errors: list[str] = field(default_factory=list)
    cuts_count: int = 0
    cut_frequency_per_min: float = 0.0
    shot_frequency_per_min: float = 0.0
    zooms_count: int = 0
    overlays_count: int = 0
    output_mp4_path: str = ""
    status: str = "pending"  # "pending", "in_progress", "rendered", "failed"
    timestamp: float = field(default_factory=time.time)


class ObservabilityTracker:
    """Tracks and persists structured telemetry per editing job."""

    def __init__(self, job_id: str, log_dir: str | Path | None = None):
        self.job_id = job_id
        if log_dir is None:
            log_dir = Path("projects") / job_id / "logs"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "autonomous_edit_telemetry.json"
        
        # System memory telemetry
        ram_total, ram_free = self._get_ram_stats()
        vram_total, vram_free, device = self._get_vram_stats()

        self.metrics = JobObservabilityMetrics(
            job_id=job_id,
            user_instruction="",
            source_video="",
            selected_provider="unknown",
            decision_source="heuristic_fallback",
            device=device,
            ram_total_gb=round(ram_total, 2),
            ram_free_gb=round(ram_free, 2),
            vram_total_gb=round(vram_total, 2),
            vram_free_gb=round(vram_free, 2),
        )

    def _get_ram_stats(self) -> tuple[float, float]:
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys / (1024**3), stat.ullAvailPhys / (1024**3)
        except Exception:
            return 16.0, 3.0

    def _get_vram_stats(self) -> tuple[float, float, str]:
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                tot = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                free = (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)) / (1024**3)
                return tot, free, name
        except Exception:
            pass
        return 0.0, 0.0, "Intel(R) UHD Graphics (DirectX/CPU)"

    def record_analysis_complete(self, duration: float) -> None:
        self.metrics.video_analysis_duration_sec = round(duration, 3)

    def record_planning_complete(self, duration: float, cuts: int, zooms: int, overlays: int, val_failures: int = 0) -> None:
        self.metrics.planning_duration_sec = round(duration, 3)
        self.metrics.cuts_count = cuts
        self.metrics.zooms_count = zooms
        self.metrics.overlays_count = overlays
        self.metrics.json_validation_failures = val_failures

    def record_render_complete(self, duration: float, output_path: str) -> None:
        self.metrics.render_duration_sec = round(duration, 3)
        self.metrics.output_mp4_path = output_path
        self.metrics.status = "rendered"
        self.metrics.total_pipeline_duration_sec = round(
            self.metrics.video_analysis_duration_sec + self.metrics.planning_duration_sec + duration, 3
        )
        self.save()

    def record_error(self, err_msg: str) -> None:
        self.metrics.inference_errors.append(err_msg)
        self.metrics.status = "failed"
        self.save()

    def save(self) -> None:
        data = asdict(self.metrics)
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved telemetry to %s", self.log_file)
