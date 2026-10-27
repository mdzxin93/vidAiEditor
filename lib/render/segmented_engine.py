"""OpenMontage Segmented Rendering & Incremental Cache Engine (Phases 11-12).

Provides:
- Independent segment rendering for long timelines.
- Per-cut / per-interval content-addressed caching (SHA-256 fingerprint).
- Instant reuse of unmodified segments when tweaking timeline events.
- Stream-copy concatenation via FFmpeg (`-c copy`) for compatible segments.
- Automatic fallback to full composition rendering if stitching or codecs mismatch.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from lib.storage_paths import get_storage
from lib.api.media_manager import probe_media_file

logger = logging.getLogger("openmontage.segmented_engine")


class SegmentedRenderEngine:
    """Renders timelines in independent segments with incremental caching."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        storage = get_storage()
        self.segments_cache_dir = (cache_dir or storage.cache_dir) / "segments"
        self.segments_cache_dir.mkdir(parents=True, exist_ok=True)

    def compute_cut_fingerprint(
        self,
        cut: dict[str, Any],
        overlays: list[dict[str, Any]],
        captions: list[dict[str, Any]],
        render_preset: str = "fast_preview",
        target_resolution: str = "540x960",
    ) -> str:
        """Calculate deterministic SHA-256 hash for a specific cut and its timed assets."""
        c_in = float(cut.get("in_seconds") or 0.0)
        c_out = float(cut.get("out_seconds") or 0.0)

        # Overlays active during this cut's window
        active_overlays = []
        for ov in overlays:
            ov_in = float(ov.get("start_seconds") if ov.get("start_seconds") is not None else ov.get("in_seconds", 0.0))
            ov_out = float(ov.get("end_seconds") if ov.get("end_seconds") is not None else ov.get("out_seconds", ov_in + 3.0))
            if ov_in < c_out and ov_out > c_in:
                active_overlays.append(ov)

        # Captions active during this cut's window
        active_captions = []
        for cap in captions:
            cap_in = float(cap.get("start", 0.0))
            cap_out = float(cap.get("end", cap_in + 0.3))
            if cap_in < c_out and cap_out > c_in:
                active_captions.append(cap)

        payload = {
            "source": str(cut.get("source", "")),
            "in_seconds": round(c_in, 3),
            "out_seconds": round(c_out, 3),
            "speed": float(cut.get("speed", 1.0)),
            "transform": cut.get("transform", {}),
            "overlays": active_overlays,
            "captions": active_captions,
            "render_preset": render_preset,
            "target_resolution": target_resolution,
        }
        raw_json = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    def get_cached_segment(self, fingerprint: str) -> Optional[Path]:
        """Retrieve existing valid pre-rendered segment."""
        candidate = self.segments_cache_dir / f"seg_{fingerprint}.mp4"
        if candidate.is_file() and candidate.stat().st_size > 1024:
            return candidate
        return None

    def store_cached_segment(self, fingerprint: str, source_segment: Path) -> Path:
        """Store rendered segment in content-addressed cache."""
        target = self.segments_cache_dir / f"seg_{fingerprint}.mp4"
        import shutil
        shutil.copy2(source_segment, target)
        return target

    def concatenate_segments_stream_copy(
        self,
        segment_paths: list[Path],
        output_path: Path,
    ) -> bool:
        """Losslessly stitch pre-rendered MP4 segments using FFmpeg concat protocol."""
        if not segment_paths:
            return False

        if len(segment_paths) == 1:
            import shutil
            shutil.copy2(segment_paths[0], output_path)
            return True

        output_path.parent.mkdir(parents=True, exist_ok=True)
        concat_list_file = output_path.parent / f"concat_{os.getpid()}_{output_path.stem}.txt"
        
        try:
            # Write FFmpeg concat manifest
            with open(concat_list_file, "w", encoding="utf-8") as f:
                for seg in segment_paths:
                    # Escape single quotes for ffmpeg concat demuxer
                    escaped_path = str(seg.resolve()).replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_file),
                "-c", "copy",
                "-movflags", "+faststart",
                str(output_path),
            ]

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode != 0:
                logger.warning("Stream copy concatenation failed: %s", res.stderr)
                return False

            probe = probe_media_file(output_path)
            if probe.get("duration", 0) <= 0:
                logger.warning("Concatenated output is empty or zero duration")
                return False

            return True
        except Exception as e:
            logger.warning("Segment concatenation encountered error: %s", e)
            return False
        finally:
            if concat_list_file.is_file():
                try:
                    concat_list_file.unlink()
                except Exception:
                    pass

    def evaluate_incremental_plan(
        self,
        cuts: list[dict[str, Any]],
        overlays: list[dict[str, Any]],
        captions: list[dict[str, Any]],
        render_preset: str = "fast_preview",
        target_resolution: str = "540x960",
    ) -> dict[str, Any]:
        """Audit timeline cuts to determine cached vs dirty segments."""
        cached_count = 0
        dirty_count = 0
        segments_info = []

        for idx, cut in enumerate(cuts):
            fp = self.compute_cut_fingerprint(
                cut=cut,
                overlays=overlays,
                captions=captions,
                render_preset=render_preset,
                target_resolution=target_resolution,
            )
            cached_path = self.get_cached_segment(fp)
            is_cached = cached_path is not None
            if is_cached:
                cached_count += 1
            else:
                dirty_count += 1

            segments_info.append({
                "cut_index": idx,
                "cut_id": cut.get("id", f"cut_{idx}"),
                "fingerprint": fp,
                "is_cached": is_cached,
                "cached_path": str(cached_path) if cached_path else None,
                "duration": float(cut.get("out_seconds", 0.0)) - float(cut.get("in_seconds", 0.0)),
            })

        can_stream_copy = dirty_count == 0
        return {
            "total_cuts": len(cuts),
            "cached_cuts": cached_count,
            "dirty_cuts": dirty_count,
            "cache_hit_ratio": round(cached_count / max(1, len(cuts)), 2),
            "can_stream_copy_assemble": can_stream_copy,
            "segments": segments_info,
        }
