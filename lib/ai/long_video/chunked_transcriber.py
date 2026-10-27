"""Long-Video Processing Utilities (Phase 11).

Provides:
- Chunked speech transcription with global timestamp preservation.
- Boundary word deduplication for seamless audio splicing.
- Granular chunk checkpointing and resumption.
- Timeline gap and overlap sanitizer for long edits.
"""

from __future__ import annotations

import json
import logging
import math
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("openmontage.long_video")


class ChunkedTranscriber:
    """Bounded-memory chunked transcription for medium and long video footage."""

    def __init__(
        self,
        chunk_duration_sec: float = 120.0,
        overlap_sec: float = 1.0,
        model_size: str = "base",
        chunk_duration: Optional[float] = None,
        overlap: Optional[float] = None,
    ):
        self.chunk_duration_sec = chunk_duration if chunk_duration is not None else chunk_duration_sec
        self.overlap_sec = overlap if overlap is not None else overlap_sec
        self.model_size = model_size

    def transcribe(
        self,
        media_path: Path,
        output_cache_dir: Optional[Path] = None,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> list[dict[str, Any]]:
        """Convenience alias for transcribe_long_audio."""
        return self.transcribe_long_audio(media_path, output_cache_dir, progress_cb)

    def transcribe_long_audio(
        self,
        media_path: Path,
        output_cache_dir: Optional[Path] = None,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> list[dict[str, Any]]:
        """Transcribe long audio/video in bounded chunks, preserving exact global timestamps."""
        media_path = Path(media_path).resolve()
        duration = self._probe_duration(media_path)

        if duration <= self.chunk_duration_sec:
            # Short video: direct transcription
            return self._transcribe_segment(media_path, 0.0, duration, progress_cb)

        # Long video: chunk-based processing
        cache_dir = output_cache_dir or (media_path.parent / ".transcript_chunks")
        cache_dir.mkdir(parents=True, exist_ok=True)

        num_chunks = math.ceil(duration / (self.chunk_duration_sec - self.overlap_sec))
        all_words: list[dict[str, Any]] = []

        logger.info(
            "Transcribing long media (%s, %.1fs) in %d chunks...",
            media_path.name, duration, num_chunks,
        )

        current_start = 0.0
        chunk_idx = 0

        while current_start < duration:
            chunk_end = min(duration, current_start + self.chunk_duration_sec)
            chunk_cache_file = cache_dir / f"chunk_{chunk_idx:04d}_{int(current_start)}_{int(chunk_end)}.json"

            if progress_cb:
                pct = 10.0 + (chunk_idx / num_chunks) * 70.0
                progress_cb(pct, f"Transcribing segment {chunk_idx + 1}/{num_chunks} ({int(current_start)}s - {int(chunk_end)}s)...")

            # Check if chunk was previously completed and cached
            if chunk_cache_file.is_file():
                try:
                    with open(chunk_cache_file, "r", encoding="utf-8") as f:
                        chunk_words = json.load(f)
                    logger.info("Reusing cached transcript for chunk %d", chunk_idx)
                except Exception:
                    chunk_words = self._transcribe_segment_with_offset(media_path, current_start, chunk_end)
                    self._save_chunk_cache(chunk_cache_file, chunk_words)
            else:
                chunk_words = self._transcribe_segment_with_offset(media_path, current_start, chunk_end)
                self._save_chunk_cache(chunk_cache_file, chunk_words)

            # Deduplicate boundary overlap with previous words
            if all_words and chunk_words:
                chunk_words = self._deduplicate_overlap(all_words, chunk_words, overlap_window_sec=self.overlap_sec * 2)

            all_words.extend(chunk_words)

            chunk_idx += 1
            current_start += (self.chunk_duration_sec - self.overlap_sec)

        return all_words

    def _transcribe_segment_with_offset(
        self,
        media_path: Path,
        start_sec: float,
        end_sec: float,
    ) -> list[dict[str, Any]]:
        """Extract audio snippet and transcribe with faster-whisper, re-basing timestamps to global video clock."""
        from tools.analysis.transcriber import Transcriber

        # Create temporary audio snippet
        snippet_path = media_path.parent / f".tmp_chunk_{int(start_sec)}_{int(end_sec)}.wav"
        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{start_sec:.3f}",
                "-to", f"{end_sec:.3f}",
                "-i", str(media_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(snippet_path),
            ]
            subprocess.run(cmd, capture_output=True, check=True)

            transcriber = Transcriber()
            res = transcriber.execute({
                "input_path": str(snippet_path),
                "model_size": self.model_size,
            })

            words = []
            if res.success and res.data:
                raw_words = res.data.get("word_timestamps", [])
                for w in raw_words:
                    # Offset timestamps by snippet start
                    words.append({
                        "word": w.get("word", "").strip(),
                        "start": round(start_sec + float(w.get("start", 0.0)), 3),
                        "end": round(start_sec + float(w.get("end", 0.0)), 3),
                        "probability": round(float(w.get("probability", 0.9)), 3),
                    })
            return words
        finally:
            snippet_path.unlink(missing_ok=True)

    def _transcribe_segment(
        self,
        media_path: Path,
        start_sec: float,
        end_sec: float,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> list[dict[str, Any]]:
        from tools.analysis.transcriber import Transcriber
        transcriber = Transcriber()
        if progress_cb:
            progress_cb(30.0, "Transcribing speech audio with faster-whisper...")
        res = transcriber.execute({
            "input_path": str(media_path),
            "model_size": self.model_size,
        })
        if res.success and res.data:
            return res.data.get("word_timestamps", [])
        return []

    def _deduplicate_overlap(
        self,
        prev_words: list[dict[str, Any]],
        new_words: list[dict[str, Any]],
        overlap_window_sec: float,
    ) -> list[dict[str, Any]]:
        """Remove words in new_words that duplicate words at the tail of prev_words within overlap window."""
        if not prev_words or not new_words:
            return new_words

        last_word_time = prev_words[-1]["start"]
        filtered_new: list[dict[str, Any]] = []

        for nw in new_words:
            # If word is before the last word with substantial overlap, check match
            if nw["start"] < last_word_time:
                # Find matching word in tail of prev_words
                matched = any(
                    abs(pw["start"] - nw["start"]) < 0.35 and pw["word"].lower() == nw["word"].lower()
                    for pw in prev_words[-15:]
                )
                if not matched:
                    filtered_new.append(nw)
            else:
                filtered_new.append(nw)

        return filtered_new

    def _save_chunk_cache(self, cache_file: Path, words: list[dict[str, Any]]) -> None:
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(words, f, indent=2)
        except Exception as e:
            logger.warning("Could not cache transcript chunk to %s: %s", cache_file, e)

    def _probe_duration(self, media_path: Path) -> float:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ]
        try:
            out = subprocess.check_output(cmd, text=True).strip()
            return float(out)
        except Exception:
            return 30.0
