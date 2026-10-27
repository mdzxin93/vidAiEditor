"""Audio Waveform Peaks Extractor (Phase 12).

Extracts normalized peak amplitudes from video or audio files using FFmpeg.
Produces lightweight JSON (<10 KB) for high-performance frontend timeline rendering
without decoding raw audio in the browser.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import struct
import subprocess
from pathlib import Path
from typing import Optional

from lib.storage_paths import get_storage

logger = logging.getLogger("openmontage.waveform")


class WaveformExtractor:
    """Extracts lightweight normalized waveform peak arrays for timeline display."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        storage = get_storage()
        self.cache_dir = (cache_dir or storage.cache_dir) / "waveforms"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def extract_peaks(
        self,
        media_path: Path | str,
        target_points: int = 800,
    ) -> dict[str, Any]:
        """Extract or retrieve cached waveform amplitude peaks."""
        media_path = Path(media_path).resolve()
        if not media_path.is_file():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        stat = media_path.stat()
        cache_key = hashlib.sha256(
            f"{media_path}|{stat.st_size}|{stat.st_mtime_ns}|{target_points}".encode()
        ).hexdigest()
        cache_file = self.cache_dir / f"wf_{cache_key}.json"

        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Extract 8kHz 16-bit signed PCM mono audio stream via FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", str(media_path),
            "-vn",
            "-ac", "1",
            "-ar", "8000",
            "-f", "s16le",
            "-",
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
            if res.returncode != 0 or not res.stdout:
                logger.warning("FFmpeg audio extraction failed: %s", res.stderr.decode("utf-8", "ignore")[:300])
                # Generate fallback silence points
                return {
                    "duration": 10.0,
                    "points_count": target_points,
                    "peaks": [0.05] * target_points,
                }

            pcm_data = res.stdout
            total_samples = len(pcm_data) // 2
            duration = total_samples / 8000.0

            if total_samples == 0:
                return {"duration": 0.0, "points_count": target_points, "peaks": []}

            # Unpack samples and downsample to target_points
            samples_per_point = max(1, total_samples // target_points)
            peaks = []

            for i in range(target_points):
                start_sample = i * samples_per_point
                end_sample = min(total_samples, start_sample + samples_per_point)
                
                if start_sample >= total_samples:
                    peaks.append(0.0)
                    continue

                chunk_bytes = pcm_data[start_sample * 2 : end_sample * 2]
                sample_count = len(chunk_bytes) // 2
                if sample_count == 0:
                    peaks.append(0.0)
                    continue

                # Format 'h' is 16-bit signed integer (-32768 to 32767)
                unpacked = struct.unpack(f"<{sample_count}h", chunk_bytes)
                max_val = max(abs(s) for s in unpacked)
                # Normalize to 0.0 - 1.0 with subtle non-linear boost for speech clarity
                norm = min(1.0, max_val / 32768.0)
                boosted = math.sqrt(norm)  # perceptual square-root compression
                peaks.append(round(boosted, 3))

            result = {
                "duration": round(duration, 3),
                "points_count": len(peaks),
                "peaks": peaks,
            }

            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(result, f)
            except Exception:
                pass

            return result

        except Exception as e:
            logger.error("Failed to extract waveform: %s", e)
            return {
                "duration": 10.0,
                "points_count": target_points,
                "peaks": [0.1] * target_points,
            }
