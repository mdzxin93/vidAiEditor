"""OpenMontage AI Kinetic Caption & Subtitle Engine.

Production-grade, AI-powered kinetic typography, animated subtitle,
and intelligent caption generation system natively integrated into OpenMontage.

Capabilities:
1. Faster-Whisper ASR with word-level timestamps and intelligent caching.
2. Intelligent caption segmentation (1-4 words per cue, pause/clause-aware).
3. AI-powered emphasis detection (duration z-score, audio energy, lexical salience).
4. Editorial positioning & subject-aware placement (9:16 portrait, 16:9, 1:1).
5. Centralized style library (Cinematic Kinetic Podcast priority preset + 5 variants).
6. Remotion frame-deterministic rendering and FFmpeg ASS fallback.
7. Multi-format subtitle export (.srt, .vtt, .ass).
8. Editable timeline operations (split, merge, retime, override).
9. Style learning and reference training extraction.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

logger = logging.getLogger("openmontage.kinetic_caption_engine")

PRESETS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "caption_presets"
FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"


class KineticCaptionEngine(BaseTool):
    name = "kinetic_caption_engine"
    version = "2.0.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["binary:ffmpeg", "binary:ffprobe"]
    install_instructions = (
        "Install ffmpeg and faster-whisper:\n"
        "  pip install faster-whisper\n"
        "  Remotion: npm install in remotion-composer/"
    )
    agent_skills = ["remotion-best-practices", "ffmpeg"]

    capabilities = [
        "transcribe_and_segment",
        "detect_emphasis",
        "generate_kinetic_cues",
        "render_burned_captions",
        "export_subtitles",
        "apply_style_preset",
        "style_learning_extract",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_path"],
        "properties": {
            "video_path": {"type": "string", "description": "Path to input video file"},
            "output_path": {"type": "string", "description": "Optional output path for rendered MP4"},
            "preset_id": {
                "type": "string",
                "default": "kinetic_podcast_reference",
                "description": "Caption style preset ID (default: kinetic_podcast_reference)",
            },
            "model_size": {
                "type": "string",
                "default": "base",
                "enum": ["tiny", "base", "small", "medium", "large-v3"],
                "description": "Faster-Whisper model size",
            },
            "language": {"type": "string", "description": "Language code or auto-detect if null"},
            "words_per_cue": {"type": "integer", "default": 2, "description": "Target words per caption group"},
            "emphasis_frequency": {
                "type": "number",
                "default": 0.25,
                "description": "Ratio of emphasis opportunities to trigger (0.0 = none, 1.0 = max)",
            },
            "vertical_position": {
                "type": "number",
                "description": "Vertical position override (0.0 to 1.0)",
            },
            "export_formats": {
                "type": "array",
                "items": {"type": "string", "enum": ["mp4", "srt", "vtt", "ass"]},
                "default": ["mp4", "srt", "vtt", "ass"],
                "description": "Export deliverables to produce",
            },
            "corrections": {"type": "object", "description": "Optional dictionary of word corrections"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=500, network_required=False
    )
    idempotency_key_fields = ["video_path", "preset_id", "model_size"]
    side_effects = ["generates kinetic captions, exports subtitles, renders preview"]

    def __init__(self) -> None:
        super().__init__()
        self._preset_cache: dict[str, dict] = {}
        self._load_presets()

    def get_status(self) -> ToolStatus:
        if shutil.which("ffmpeg"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    # -----------------------------------------------------------------------
    # Preset Management (Phase 4 & Phase 11)
    # -----------------------------------------------------------------------

    def _load_presets(self) -> None:
        """Load built-in style presets from config directory."""
        if not PRESETS_DIR.exists():
            return
        for file in PRESETS_DIR.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                sid = data.get("style_id", file.stem)
                self._preset_cache[sid] = data
            except Exception as e:
                logger.warning(f"Failed to load preset {file}: {e}")

    def get_preset(self, preset_id: str) -> dict:
        """Retrieve a style preset by ID, defaulting to the reference style."""
        if not self._preset_cache:
            self._load_presets()
        return (
            self._preset_cache.get(preset_id)
            or self._preset_cache.get("kinetic_podcast_reference")
            or self._fallback_reference_preset()
        )

    load_preset = get_preset

    def list_presets(self) -> list[dict]:
        """List all available caption style presets."""
        if not self._preset_cache:
            self._load_presets()
        return [
            {
                "style_id": p.get("style_id", k),
                "name": p.get("name", k),
                "font_family": p.get("font_family", "Inter Display"),
                "font_weight": p.get("font_weight", 800),
                "font_color": p.get("font_color", "#FFFFFF"),
                "emphasis_enabled": p.get("emphasis_enabled", True),
                "emphasis_scale": p.get("emphasis_scale", 1.85),
            }
            for k, p in self._preset_cache.items()
        ]

    @staticmethod
    def _fallback_reference_preset() -> dict:
        return {
            "style_id": "kinetic_podcast_reference",
            "name": "Cinematic Kinetic Podcast",
            "font_family": "Inter Display",
            "font_weight": 800,
            "font_color": "#FFFFFF",
            "text_alignment": "center",
            "letter_spacing_em": -0.055,
            "background": "transparent",
            "outline_enabled": False,
            "shadow_enabled": True,
            "shadow_style": "0 2px 4px rgba(0,0,0,0.25)",
            "word_level_timing": True,
            "emphasis_enabled": True,
            "emphasis_scale": 1.85,
            "emphasis_font_weight": 900,
            "caption_grouping": {
                "minimum_words": 1,
                "maximum_words": 4,
                "target_words_per_cue": 2,
                "max_chars_per_line": 24,
                "pause_threshold_ms": 280,
            },
            "animation": {
                "type": "quick_scale_fade",
                "duration_ms": 140,
                "enter_frames": 3,
                "exit_frames": 2,
                "initial_scale": 0.94,
                "final_scale": 1.0,
                "fade_in": True,
                "fade_out": False,
                "easing": "easeOutCubic",
            },
            "layout": {
                "horizontal_alignment": "center",
                "vertical_position": 0.48,
                "top_emphasis_vertical_position": 0.22,
                "safe_margin_percent": 8,
                "max_width_percent": 92,
            },
            "rendering": {
                "resolution_adaptive": True,
                "anti_aliasing": True,
                "transparent_overlay": True,
                "normal_size_pct_of_width": 0.072,
                "emphasis_size_pct_of_width": 0.125,
                "support_size_pct_of_width": 0.055,
            },
        }

    # -----------------------------------------------------------------------
    # Transcription with Caching (Phase 5)
    # -----------------------------------------------------------------------

    def transcribe(
        self,
        video_path: Path,
        model_size: str = "base",
        language: Optional[str] = None,
        cache: bool = True,
        corrections: Optional[dict[str, str]] = None,
    ) -> list[dict]:
        """Transcribe video using Faster-Whisper with CPU-compatible int8 quantization and caching."""
        cache_dir = video_path.parent / ".transcript_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Compute cache key from file size + mtime + model
        st = video_path.stat()
        cache_key = hashlib.md5(f"{video_path.resolve()}:{st.st_size}:{st.st_mtime}:{model_size}:{language}".encode()).hexdigest()
        cache_file = cache_dir / f"transcript_{cache_key}.json"

        if cache and cache_file.exists():
            try:
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                logger.info(f"Loaded cached transcript from {cache_file}")
                words = cached_data.get("words", [])
                if words:
                    return self._apply_corrections_to_words(words, corrections)
            except Exception as e:
                logger.warning(f"Failed to read cache {cache_file}: {e}")

        # Execute transcription via tools.analysis.transcriber
        from tools.analysis.transcriber import Transcriber

        transcriber = Transcriber()
        res = transcriber.execute({
            "input_path": str(video_path),
            "model_size": model_size,
            "language": language,
            "output_dir": str(cache_dir),
        })

        if not res.success:
            raise RuntimeError(f"Transcription failed: {res.error}")

        raw_words = res.data.get("word_timestamps", [])
        # If word timestamps weren't extracted, fallback to segment decomposition
        if not raw_words and res.data.get("segments"):
            raw_words = []
            for seg in res.data["segments"]:
                seg_words = seg.get("words")
                if seg_words:
                    raw_words.extend(seg_words)
                else:
                    text_parts = seg.get("text", "").strip().split()
                    dur = seg["end"] - seg["start"]
                    step = dur / max(1, len(text_parts))
                    for i, tw in enumerate(text_parts):
                        raw_words.append({
                            "word": tw,
                            "start": round(seg["start"] + i * step, 3),
                            "end": round(seg["start"] + (i + 1) * step, 3),
                        })

        # Sanitize and deduplicate words
        cleaned_words = []
        for w in raw_words:
            text = str(w.get("word", "")).strip()
            if not text:
                continue
            cleaned_words.append({
                "word": text,
                "start": float(w["start"]),
                "end": max(float(w["end"]), float(w["start"]) + 0.05),
                "probability": float(w.get("probability", 1.0)),
            })

        # Save to cache
        if cache:
            try:
                cache_file.write_text(json.dumps({"words": cleaned_words}, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not write cache {cache_file}: {e}")

        return self._apply_corrections_to_words(cleaned_words, corrections)

    @staticmethod
    def _apply_corrections_to_words(
        words: list[dict], corrections: Optional[dict[str, str]]
    ) -> list[dict]:
        if not corrections:
            return words
        corr = {k.lower(): v for k, v in corrections.items()}
        result = []
        for w in words:
            item = dict(w)
            raw = item["word"].strip()
            stripped = raw.lower().rstrip(".,!?;:'\"")
            if stripped in corr:
                trailing = raw[len(stripped):]
                item["word"] = corr[stripped] + trailing
            result.append(item)
        return result

    # -----------------------------------------------------------------------
    # Intelligent Caption Segmentation (Phase 6)
    # -----------------------------------------------------------------------

    def segment_words_into_cues(
        self,
        words: list[dict],
        preset: dict,
        target_words_per_cue: Optional[int] = None,
        words_per_cue: Optional[int] = None,
    ) -> list[dict]:
        """Intelligently divides speech into short, readable 1-4 word caption groups.
        
        Evaluates:
        1. Breath / spoken pause boundaries (gap >= pause_threshold_ms).
        2. Clause and sentence punctuation (. , ! ? ; : —).
        3. Character length limits to prevent visual crowding.
        4. Natural rhythmic phrasing (1 to 4 words).
        """
        if not words:
            return []

        grouping = preset.get("caption_grouping", {})
        min_words = grouping.get("minimum_words", 1)
        max_words = grouping.get("maximum_words", 4)
        target_words = words_per_cue or target_words_per_cue or grouping.get("target_words_per_cue", 2)
        max_chars = grouping.get("max_chars_per_line", 24)
        pause_threshold_sec = grouping.get("pause_threshold_ms", 280) / 1000.0

        cues: list[dict] = []
        buffer: list[dict] = []

        for idx, w in enumerate(words):
            word_str = w["word"].strip()
            next_w = words[idx + 1] if idx + 1 < len(words) else None

            buffer.append(w)
            curr_text = " ".join(b["word"].strip() for b in buffer)

            # Check break conditions
            is_last = next_w is None
            pause_after = False
            if next_w:
                gap = next_w["start"] - w["end"]
                if gap >= pause_threshold_sec:
                    pause_after = True

            has_clause_punct = bool(re.search(r"[,!?;:—\.\"]$", word_str))
            hit_max_words = len(buffer) >= max_words
            hit_max_chars = len(curr_text) >= max_chars
            hit_target_words = len(buffer) >= target_words and (has_clause_punct or pause_after)

            should_flush = (
                is_last
                or hit_max_words
                or hit_max_chars
                or pause_after
                or (has_clause_punct and len(buffer) >= min_words)
                or hit_target_words
            )

            if should_flush and buffer:
                cue_start = buffer[0]["start"]
                cue_end = buffer[-1]["end"]

                # Ensure minimum visible hold duration (140ms)
                if cue_end - cue_start < 0.14:
                    cue_end = cue_start + 0.14

                cues.append({
                    "id": f"cue-{len(cues) + 1}",
                    "start": round(cue_start, 3),
                    "end": round(cue_end, 3),
                    "text": curr_text,
                    "mode": "normal",
                    "words": copy.deepcopy(buffer),
                })
                buffer = []

        # Flush any trailing words
        if buffer:
            cues.append({
                "id": f"cue-{len(cues) + 1}",
                "start": round(buffer[0]["start"], 3),
                "end": round(buffer[-1]["end"], 3),
                "text": " ".join(b["word"].strip() for b in buffer),
                "mode": "normal",
                "words": copy.deepcopy(buffer),
            })

        return cues

    # -----------------------------------------------------------------------
    # AI-Powered Emphasis Detection (Phase 7)
    # -----------------------------------------------------------------------

    def detect_and_apply_emphasis(
        self,
        cues: list[dict],
        audio_path_or_words: Any = None,
        preset: Optional[dict] = None,
        emphasis_frequency: float = 0.25,
        emphasis_scale: Optional[float] = None,
        **kwargs,
    ) -> list[dict]:
        """Identifies salient words to receive kinetic emphasis or two-tier stacked layout.
        
        Signals combined:
        1. Duration z-score: stressed words spoken significantly longer than avg.
        2. Lexical salience: high-information content nouns/verbs/numbers/caps.
        3. Audio energy spikes: loudness peaks via ebur128 analysis when audio available.
        """
        if not cues:
            return cues

        active_preset = preset or self._fallback_reference_preset()
        scale_val = emphasis_scale if emphasis_scale is not None else active_preset.get("emphasis_scale", 1.85)

        audio_path = None
        if isinstance(audio_path_or_words, (str, Path)):
            p = Path(audio_path_or_words)
            if p.exists():
                audio_path = p

        # Compute word duration statistics across all cues
        durations = []
        for cue in cues:
            for w in cue.get("words", []):
                dur = max(0.05, w["end"] - w["start"])
                # Normalize duration by character count
                char_dur = dur / max(1, len(w["word"].strip(".,!?;:\"'")))
                durations.append(char_dur)

        mean_dur = sum(durations) / max(1, len(durations)) if durations else 0.08
        variance = sum((d - mean_dur) ** 2 for d in durations) / max(1, len(durations))
        std_dur = math.sqrt(variance) if variance > 0 else 0.02

        # Optional audio energy profile
        energy_peaks: set[int] = set()
        if audio_path and audio_path.exists():
            try:
                from tools.analysis.audio_energy import AudioEnergy
                ae = AudioEnergy()
                ae_res = ae.execute({"input_path": str(audio_path)})
                if ae_res.success and ae_res.data:
                    for item in ae_res.data.get("energy_profile", []):
                        if item.get("loudness_lufs", -100) > -24:
                            energy_peaks.add(int(item.get("time_seconds", 0)))
            except Exception as e:
                logger.debug(f"Audio energy lookup skipped: {e}")

        # Stop words to penalize from emphasis
        FUNCTION_WORDS = {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
            "with", "by", "from", "of", "as", "is", "was", "are", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "i", "you",
            "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
            "my", "your", "our", "their", "his", "its", "just", "don't", "dont",
            "not", "can", "could", "will", "would", "shall", "should", "may", "might",
            "this", "that", "these", "those", "who", "which", "what", "so", "than",
        }

        enriched_cues = []
        last_emphasis_cue_idx = -999

        for cue_idx, cue in enumerate(cues):
            cue_copy = dict(cue)
            cue_words = cue_copy.get("words", [])

            # Check if cue is eligible for emphasis (respecting frequency spacing)
            is_spaced = (cue_idx - last_emphasis_cue_idx) >= int(1.0 / max(0.05, emphasis_frequency))

            # Evaluate each word's emphasis score
            scored_words = []
            for w in cue_words:
                raw_text = w["word"].strip(".,!?;:\"'")
                lower = raw_text.lower()
                dur = max(0.05, w["end"] - w["start"])
                char_dur = dur / max(1, len(raw_text))

                z_score = (char_dur - mean_dur) / max(0.001, std_dur)
                score = max(0.0, z_score * 1.5)

                # Lexical bonuses
                if lower not in FUNCTION_WORDS and len(raw_text) >= 4:
                    score += 1.8
                if raw_text.isupper() and len(raw_text) > 1:
                    score += 2.5
                if any(ch.isdigit() for ch in raw_text):
                    score += 2.0
                if int(w["start"]) in energy_peaks:
                    score += 1.5
                if lower in FUNCTION_WORDS:
                    score -= 4.0

                scored_words.append((score, w))

            # Sort candidate words
            scored_words.sort(key=lambda sw: sw[0], reverse=True)
            top_score, top_word = scored_words[0] if scored_words else (0.0, None)

            # Trigger emphasis only if word is non-function, score is strong, and spacing allows
            top_word_raw = top_word["word"].strip(".,!?;:\"'").lower() if top_word else ""
            if is_spaced and top_word and top_score >= 2.2 and top_word_raw not in FUNCTION_WORDS:
                last_emphasis_cue_idx = cue_idx
                main_word = top_word["word"].strip(".,!?;:\"'").upper()

                # Single word cue -> full emphasis headline
                if len(cue_words) == 1:
                    cue_copy["mode"] = "emphasis"
                    cue_copy["scale"] = scale_val
                    cue_copy["sizeScale"] = 1.0
                    cue_copy["font_weight"] = 900
                    cue_copy["emphasis_word"] = main_word
                    cue_copy["text"] = main_word
                # Multi-word cue with emphasis -> two-tier stack layout (like "on my" above "podcast")
                else:
                    cue_copy["mode"] = "stack"
                    cue_copy["scale"] = scale_val
                    cue_copy["sizeScale"] = 1.0
                    cue_copy["font_weight"] = 900
                    cue_copy["emphasis_word"] = main_word
                    cue_copy["text"] = main_word

                    # Remaining words become supporting phrase
                    support_words = [w["word"] for w in cue_words if w != top_word]
                    cue_copy["support_words"] = " ".join(support_words)
                    cue_copy["support"] = {
                        "text": " ".join(support_words),
                        "position": "top-center",
                        "scale": 0.48,
                    }

            enriched_cues.append(cue_copy)

        return enriched_cues

    # -----------------------------------------------------------------------
    # Editorial Positioning & Safe Margins (Phase 9)
    # -----------------------------------------------------------------------

    def apply_editorial_positioning(
        self,
        cues: list[dict],
        preset: dict,
        aspect_ratio: str = "9:16",
        vertical_position_override: Optional[float] = None,
        face_avoidance: bool = True,
        detected_face_y: Optional[float] = None,
    ) -> list[dict]:
        """Positions captions respecting safe margins, aspect ratio, and subject awareness."""
        layout = preset.get("layout", {})
        default_y = vertical_position_override or layout.get("vertical_position", 0.355)
        top_emphasis_y = layout.get("top_emphasis_vertical_position", 0.14)

        positioned = []
        for cue in cues:
            c = dict(cue)
            mode = c.get("mode", "normal")

            # Determine Y placement
            if mode in ("emphasis", "stack"):
                y = top_emphasis_y
            else:
                y = default_y

            # Adjust if detected face occupies this vertical band
            if face_avoidance and detected_face_y is not None:
                # If caption would collide within 15% of face center, push below or above
                if abs(y - detected_face_y) < 0.18:
                    y = min(0.82, detected_face_y + 0.22)

            c["x"] = c.get("x", 0.5)
            c["y"] = round(y, 3)
            c["position"] = {"x": c["x"], "y": c["y"]}
            positioned.append(c)

        return positioned

    # -----------------------------------------------------------------------
    # Subtitle Exports: SRT, VTT, ASS (Phase 13)
    # -----------------------------------------------------------------------

    def export_srt(self, cues: list[dict], output_path: Optional[Path] = None) -> str:
        """Export cues as SubRip (.srt) subtitle text."""
        content = self._generate_srt(cues)
        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return content

    def export_vtt(self, cues: list[dict], output_path: Optional[Path] = None) -> str:
        """Export cues as WebVTT (.vtt) subtitle text."""
        content = self._generate_vtt(cues)
        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return content

    def export_ass(
        self,
        cues: list[dict],
        output_path: Optional[Path] = None,
        preset: Optional[dict] = None,
        width: int = 1080,
        height: int = 1920,
    ) -> str:
        """Export cues as Advanced SubStation Alpha (.ass) with typography and coordinates."""
        active_preset = preset or self._fallback_reference_preset()
        content = self._generate_ass(cues, active_preset, width, height)
        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return content

    def export_subtitles(
        self,
        cues: list[dict],
        output_base_path: Path,
        formats: list[str] = ("srt", "vtt", "ass"),
        preset: Optional[dict] = None,
        width: int = 1080,
        height: int = 1920,
    ) -> dict[str, str]:
        """Exports professional .srt, .vtt, and advanced .ass subtitle files."""
        results: dict[str, str] = {}
        output_base_path = Path(output_base_path)
        output_base_path.parent.mkdir(parents=True, exist_ok=True)
        active_preset = preset or self._fallback_reference_preset()

        if "srt" in formats:
            srt_path = output_base_path.with_suffix(".srt")
            results["srt"] = str(srt_path)
            self.export_srt(cues, srt_path)

        if "vtt" in formats:
            vtt_path = output_base_path.with_suffix(".vtt")
            results["vtt"] = str(vtt_path)
            self.export_vtt(cues, vtt_path)

        if "ass" in formats:
            ass_path = output_base_path.with_suffix(".ass")
            results["ass"] = str(ass_path)
            self.export_ass(cues, ass_path, active_preset, width, height)

        return results


    @staticmethod
    def _sec_to_srt(s: float) -> str:
        ms = int(round(s * 1000))
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        sec, milli = divmod(rem, 1_000)
        return f"{h:02d}:{m:02d}:{sec:02d},{milli:03d}"

    @staticmethod
    def _sec_to_vtt(s: float) -> str:
        ms = int(round(s * 1000))
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        sec, milli = divmod(rem, 1_000)
        return f"{h:02d}:{m:02d}:{sec:02d}.{milli:03d}"

    @staticmethod
    def _sec_to_ass(s: float) -> str:
        cs = int(round(s * 100))  # centiseconds
        h, rem = divmod(cs, 360_000)
        m, rem = divmod(rem, 6_000)
        sec, centi = divmod(rem, 100)
        return f"{h}:{m:02d}:{sec:02d}.{centi:02d}"

    def _generate_srt(self, cues: list[dict]) -> str:
        lines = []
        for idx, cue in enumerate(cues, start=1):
            lines.append(str(idx))
            lines.append(f"{self._sec_to_srt(cue['start'])} --> {self._sec_to_srt(cue['end'])}")
            text = cue["text"]
            if cue.get("support"):
                text = f"{cue['support']['text']}\n{text}"
            lines.append(text)
            lines.append("")
        return "\n".join(lines)

    def _generate_vtt(self, cues: list[dict]) -> str:
        lines = ["WEBVTT", ""]
        for idx, cue in enumerate(cues, start=1):
            lines.append(str(idx))
            lines.append(f"{self._sec_to_vtt(cue['start'])} --> {self._sec_to_vtt(cue['end'])}")
            text = cue["text"]
            if cue.get("support"):
                text = f"{cue['support']['text']}\n{text}"
            lines.append(text)
            lines.append("")
        return "\n".join(lines)

    def _generate_ass(self, cues: list[dict], preset: dict, width: int, height: int) -> str:
        """Generates Advanced SubStation Alpha (.ass) with exact coordinates, fonts, and animation tags."""
        font_family = preset.get("font_family", "Inter Display")
        normal_font_size = int(width * preset.get("rendering", {}).get("normal_size_pct_of_width", 0.072))
        emphasis_font_size = int(width * preset.get("rendering", {}).get("emphasis_size_pct_of_width", 0.125))

        header = f"""[Script Info]
Title: OpenMontage Kinetic Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KineticNormal,{font_family},{normal_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,-1,0,1,0,1,5,40,40,40,1
Style: KineticEmphasis,{font_family},{emphasis_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,-2,0,1,0,2,5,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        dialogue_lines = []
        for cue in cues:
            start_str = self._sec_to_ass(cue["start"])
            end_str = self._sec_to_ass(cue["end"])
            mode = cue.get("mode", "normal")
            style_name = "KineticEmphasis" if mode == "emphasis" else "KineticNormal"

            px = int(cue.get("x", 0.5) * width)
            py = int(cue.get("y", 0.355) * height)

            # ASS fade: \fad(100, 50) = 100ms fade-in, 50ms fade-out
            tags = f"{{\\an5\\pos({px},{py})\\fad(90,40)}}"

            text = cue["text"]
            if cue.get("support"):
                text = f"{cue['support']['text']}\\N{text}"

            dialogue_lines.append(f"Dialogue: 0,{start_str},{end_str},{style_name},,0,0,0,,{tags}{text}")

        return header + "\n".join(dialogue_lines) + "\n"

    # -----------------------------------------------------------------------
    # Timeline Editing Operations (Phase 10)
    # -----------------------------------------------------------------------

    @staticmethod
    def edit_split_cue(cues: list[dict], cue_id: str, split_word_index: int) -> list[dict]:
        """Split a caption cue into two independent cues at the specified word index."""
        result = []
        for c in cues:
            if c.get("id") == cue_id and c.get("words") and 0 < split_word_index < len(c["words"]):
                w1 = c["words"][:split_word_index]
                w2 = c["words"][split_word_index:]

                cue1 = dict(c)
                cue1["id"] = f"{cue_id}-a"
                cue1["end"] = w1[-1]["end"]
                cue1["text"] = " ".join(x["word"].strip() for x in w1)
                cue1["words"] = w1

                cue2 = dict(c)
                cue2["id"] = f"{cue_id}-b"
                cue2["start"] = w2[0]["start"]
                cue2["text"] = " ".join(x["word"].strip() for x in w2)
                cue2["words"] = w2

                result.extend([cue1, cue2])
            else:
                result.append(dict(c))
        return result

    @staticmethod
    def edit_merge_cues(cues: list[dict], cue_id_1: str, cue_id_2: str) -> list[dict]:
        """Merge two adjacent caption cues into a single cue."""
        c1, c2 = None, None
        idx1, idx2 = -1, -1
        for idx, c in enumerate(cues):
            if c.get("id") == cue_id_1:
                c1, idx1 = c, idx
            elif c.get("id") == cue_id_2:
                c2, idx2 = c, idx

        if c1 and c2 and abs(idx1 - idx2) == 1:
            first = c1 if idx1 < idx2 else c2
            second = c2 if idx1 < idx2 else c1
            merged = {
                "id": first.get("id", "merged"),
                "start": first["start"],
                "end": second["end"],
                "text": f"{first['text']} {second['text']}",
                "mode": first.get("mode", "normal"),
                "words": first.get("words", []) + second.get("words", []),
                "x": first.get("x", 0.5),
                "y": first.get("y", 0.355),
            }
            new_cues = []
            for idx, c in enumerate(cues):
                if idx == min(idx1, idx2):
                    new_cues.append(merged)
                elif idx != max(idx1, idx2):
                    new_cues.append(dict(c))
            return new_cues
        return cues

    @staticmethod
    def edit_retime_cue(cues: list[dict], cue_id: str, new_start: float, new_end: float) -> list[dict]:
        """Adjust start and end timing for a specific cue."""
        result = []
        for c in cues:
            item = dict(c)
            if item.get("id") == cue_id:
                item["start"] = round(new_start, 3)
                item["end"] = round(new_end, 3)
            result.append(item)
        return result

    @staticmethod
    def edit_update_cue(cues: list[dict], cue_id: str, updates: dict[str, Any]) -> list[dict]:
        """Update any properties of an existing cue (text, position, mode, color, scale)."""
        result = []
        for c in cues:
            item = dict(c)
            if item.get("id") == cue_id:
                item.update(updates)
            result.append(item)
        return result

    # -----------------------------------------------------------------------
    # Dynamic Punch-in Zoom Cuts Generation
    # -----------------------------------------------------------------------

    def generate_punch_zoom_cuts(
        self,
        cues: list[dict],
        total_duration: float,
        source_name: Optional[str] = None,
        zoom_intensity: str = "standard",
    ) -> list[dict]:
        """Generates dynamic punch-in zoom jump cuts synchronized to narrative speech clauses.

        Alternates between establishing 1.0x framing, punch-in 1.15x zooms, and peak 1.25x closeups
        around major emphasis cues and sentence pauses, preserving face and eye centering.
        """
        if not cues or total_duration <= 0:
            return [{
                "id": "cut-01",
                "in_seconds": 0.0,
                "out_seconds": round(max(1.0, total_duration), 2),
                "speed": 1.0,
                "transform": {"scale": 1.0, "position": "center"},
                "reason": "Establishing framing",
            }]

        scales_map = {
            "subtle": [1.0, 1.08, 1.15, 1.0, 1.08],
            "standard": [1.0, 1.15, 1.25, 1.0, 1.15],
            "punchy": [1.0, 1.20, 1.35, 1.0, 1.20],
        }
        scale_sequence = scales_map.get(zoom_intensity, scales_map["standard"])

        cut_points = [0.0]
        for idx, cue in enumerate(cues[:-1]):
            next_cue = cues[idx + 1]
            pause = next_cue["start"] - cue["end"]
            is_emphasis = cue.get("mode") in ("emphasis", "stack")
            time_since_last_cut = cue["end"] - cut_points[-1]

            # Cut when significant pause occurs or emphasis cue ends, maintaining minimum 1.2s cut duration
            if (pause >= 0.22 or is_emphasis) and time_since_last_cut >= 1.2:
                cut_points.append(round(cue["end"], 2))

        # Ensure final boundary
        if total_duration - cut_points[-1] > 0.5:
            cut_points.append(round(total_duration, 2))
        else:
            cut_points[-1] = round(total_duration, 2)

        cuts = []
        for i in range(len(cut_points) - 1):
            in_s = cut_points[i]
            out_s = cut_points[i + 1]
            if out_s <= in_s:
                continue
            scale = scale_sequence[i % len(scale_sequence)]
            cut_obj = {
                "id": f"cut-{i + 1:02d}",
                "in_seconds": in_s,
                "out_seconds": out_s,
                "speed": 1.0,
                "transform": {
                    "scale": scale,
                    "position": "center"
                },
                "reason": f"{'Wide establishing' if scale == 1.0 else 'Punch-in zoom ' + str(scale) + 'x'}",
            }
            if source_name:
                cut_obj["source"] = source_name
            cuts.append(cut_obj)

        return cuts

    # -----------------------------------------------------------------------
    # Remotion Rendering & Video Composition (Phases 8, 12, 14)
    # -----------------------------------------------------------------------

    def render_video(
        self,
        video_path: Path,
        cues: list[dict],
        output_path: Path,
        preset: dict,
        cuts: Optional[list[dict]] = None,
        overlays: Optional[list[dict]] = None,
        width: int = 1080,
        height: int = 1920,
    ) -> ToolResult:
        """Renders kinetic captions directly onto the video using Remotion, or FFmpeg ASS fallback."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        remotion_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
        has_remotion = (
            shutil.which("npx") is not None
            and remotion_dir.is_dir()
            and (remotion_dir / "node_modules").is_dir()
        )

        if has_remotion:
            return self._render_via_remotion(
                video_path, cues, output_path, preset, remotion_dir, width, height, cuts=cuts, overlays=overlays
            )
        else:
            return self._render_via_ffmpeg_ass(video_path, cues, output_path, preset, width, height)

    def _render_via_remotion(
        self,
        video_path: Path,
        cues: list[dict],
        output_path: Path,
        preset: dict,
        remotion_dir: Path,
        width: int,
        height: int,
        cuts: Optional[list[dict]] = None,
        overlays: Optional[list[dict]] = None,
    ) -> ToolResult:
        """Render using Remotion KineticCaptionsVideo composition."""
        # Probe source duration
        dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video_path)]
        dur_proc = subprocess.run(dur_cmd, capture_output=True, text=True)
        try:
            dur_sec = float(dur_proc.stdout.strip())
        except ValueError:
            dur_sec = max([c["end"] for c in cues] + [10.0])

        total_frames = max(30, math.ceil(dur_sec * 30))

        # Copy video to remotion public folder
        public_dir = remotion_dir / "public" / "talking-head"
        public_dir.mkdir(parents=True, exist_ok=True)
        dest_video = public_dir / video_path.name
        try:
            shutil.copy2(video_path, dest_video)
        except Exception:
            pass

        # Write props JSON with cuts, cues, and B-roll overlays
        props = {
            "videoSrc": f"public/talking-head/{video_path.name}",
            "cuts": cuts or [],
            "cues": cues,
            "overlays": overlays or [],
            "preset": preset,
        }
        props_dir = remotion_dir / "public" / "demo-props"
        props_dir.mkdir(parents=True, exist_ok=True)
        props_file = props_dir / f"kinetic-{video_path.stem}.json"
        props_file.write_text(json.dumps(props, indent=2), encoding="utf-8")

        # Execute Remotion render
        import sys
        npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
        cmd = [
            npx_cmd, "remotion", "render",
            "src/index.tsx",
            "KineticCaptionsVideo",
            str(output_path.resolve()),
            f"--props={props_file.relative_to(remotion_dir)}",
            f"--width={width}",
            f"--height={height}",
            "--fps=30",
            f"--frames=0-{total_frames - 1}",
            "--codec=h264",
            "--crf=18",
        ]

        logger.info(f"Executing Remotion render: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=str(remotion_dir), capture_output=True, text=True)

        if not output_path.exists():
            logger.warning(f"Remotion render failed ({proc.stderr}). Falling back to FFmpeg ASS...")
            return self._render_via_ffmpeg_ass(video_path, cues, output_path, preset, width, height)

        return ToolResult(
            success=True,
            data={
                "method": "remotion",
                "output_path": str(output_path),
                "duration_seconds": dur_sec,
                "total_frames": total_frames,
                "cue_count": len(cues),
                "cut_count": len(cuts or []),
                "resolution": f"{width}x{height}",
            },
            artifacts=[str(output_path)],
        )

    def _render_via_ffmpeg_ass(
        self,
        video_path: Path,
        cues: list[dict],
        output_path: Path,
        preset: dict,
        width: int,
        height: int,
    ) -> ToolResult:
        """Render using FFmpeg ASS subtitle burning filter."""
        ass_path = output_path.parent / f"_temp_{int(time.time())}.ass"
        ass_content = self._generate_ass(cues, preset, width, height)
        ass_path.write_text(ass_content, encoding="utf-8")

        escaped_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")
        fonts_dir_escaped = str(FONTS_DIR).replace("\\", "/").replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"ass='{escaped_ass}':fontsdir='{fonts_dir_escaped}'",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-c:a", "copy",
            str(output_path),
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            ass_path.unlink()
        except OSError:
            pass

        if not output_path.exists():
            return ToolResult(success=False, error=f"FFmpeg ASS burn failed: {proc.stderr}")

        return ToolResult(
            success=True,
            data={
                "method": "ffmpeg_ass",
                "output_path": str(output_path),
                "cue_count": len(cues),
            },
            artifacts=[str(output_path)],
        )

    # -----------------------------------------------------------------------
    # Style Learning and Reference Dataset (Phase 15)
    # -----------------------------------------------------------------------

    def extract_style_training_record(
        self,
        source_video: str,
        cues: list[dict],
        style_id: str,
        output_dataset_path: Optional[Path] = None,
    ) -> dict:
        """Extracts labeled examples of caption layouts and animations into a structured dataset."""
        records = []
        for cue in cues:
            records.append({
                "source_video": str(source_video),
                "style_id": style_id,
                "caption": cue.get("text", ""),
                "start_ms": int(cue.get("start", 0) * 1000),
                "end_ms": int(cue.get("end", 0) * 1000),
                "font_family": cue.get("font_family") or cue.get("fontFamily") or "Inter Display",
                "font_weight": cue.get("font_weight") or cue.get("fontWeight") or 800,
                "emphasis": cue.get("mode") in ("emphasis", "stack"),
                "scale": cue.get("scale") or cue.get("sizeScale", 1.0),
                "position": cue.get("position") or {"x": cue.get("x", 0.5), "y": cue.get("y", 0.355)},
                "animation": "quick_scale_fade",
            })

        if output_dataset_path:
            output_dataset_path = Path(output_dataset_path)
            output_dataset_path.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if output_dataset_path.exists():
                try:
                    existing = json.loads(output_dataset_path.read_text(encoding="utf-8"))
                except Exception:
                    existing = []
            existing.extend(records)
            output_dataset_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        return {"record_count": len(records), "records": records}

    def extract_style_learning_records(
        self,
        source_video: str,
        cues: list[dict],
        preset: Optional[dict] = None,
        output_dataset_path: Optional[Path] = None,
    ) -> list[dict]:
        style_id = preset.get("style_id", "kinetic_podcast_reference") if preset else "kinetic_podcast_reference"
        res = self.extract_style_training_record(source_video, cues, style_id, output_dataset_path)
        return res.get("records", [])

    def generate_remotion_props(
        self,
        video_src: str,
        cues: list[dict],
        preset: dict,
        aspect_ratio: str = "9:16",
        width: int = 1080,
        height: int = 1920,
    ) -> dict:
        return {
            "videoSrc": video_src,
            "cues": cues,
            "preset": preset,
            "aspectRatio": aspect_ratio,
            "width": width,
            "height": height,
        }


    # -----------------------------------------------------------------------
    # Main BaseTool Execution Entrypoint
    # -----------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        video_path = Path(inputs["video_path"])
        if not video_path.exists():
            return ToolResult(success=False, error=f"Video file not found: {video_path}")

        preset_id = inputs.get("preset_id", "kinetic_podcast_reference")
        preset = self.get_preset(preset_id)

        model_size = inputs.get("model_size", "base")
        language = inputs.get("language")
        words_per_cue = inputs.get("words_per_cue", 2)
        emphasis_freq = inputs.get("emphasis_frequency", 0.25)
        vertical_pos = inputs.get("vertical_position")
        video_style = inputs.get("video_style", "dynamic_zoom")
        zoom_intensity = inputs.get("zoom_intensity", "standard")
        custom_cuts = inputs.get("cuts")
        export_formats = inputs.get("export_formats", ["mp4", "srt", "vtt", "ass"])
        corrections = inputs.get("corrections")
        output_path = inputs.get("output_path")

        # Step 1: Transcribe
        try:
            words = self.transcribe(
                video_path,
                model_size=model_size,
                language=language,
                corrections=corrections,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Transcription error: {e}")

        # Step 2: Segment into cues
        cues = self.segment_words_into_cues(words, preset, target_words_per_cue=words_per_cue)

        # Step 3: Detect and apply emphasis
        cues = self.detect_and_apply_emphasis(
            cues,
            audio_path=video_path,
            emphasis_frequency=emphasis_freq,
            emphasis_scale=preset.get("emphasis_scale", 1.85),
        )

        # Step 4: Apply editorial positioning
        cues = self.apply_editorial_positioning(
            cues,
            preset=preset,
            aspect_ratio="9:16",
            vertical_position_override=vertical_pos,
        )

        # Step 5: Generate dynamic punch-in zoom cuts or static framing based on video_style
        dur_sec = max([c["end"] for c in cues] + [10.0])
        if video_style in ("dynamic_zoom", "punch_zoom"):
            if custom_cuts:
                cuts = custom_cuts
            else:
                cuts = self.generate_punch_zoom_cuts(
                    cues,
                    dur_sec,
                    source_name=f"public/talking-head/{video_path.name}",
                    zoom_intensity=zoom_intensity,
                )
        else:
            cuts = []

        # Step 5.5: Semantic B-Roll & Visual Decisions (OpenMontage v3)
        enable_broll = inputs.get("enable_broll", True)
        custom_overlays = inputs.get("overlays")
        overlays = []
        edl_v3 = None

        if custom_overlays is not None:
            overlays = custom_overlays
        elif enable_broll:
            try:
                from tools.editorial.semantic_broll_planner import SemanticBRollPlanner
                broll_planner = SemanticBRollPlanner()
                transcript_input = words if words else cues
                tcand = video_path.parent / f"{video_path.stem}_transcript.json"
                if tcand.exists():
                    try:
                        with open(tcand, "r", encoding="utf-8") as f:
                            transcript_input = json.load(f)
                    except Exception:
                        pass
                broll_res = broll_planner.execute({
                    "transcript": transcript_input,
                    "video_path": str(video_path),
                })
                if broll_res.success:
                    overlays = broll_res.data.get("overlays", [])
                    edl_v3 = broll_res.data.get("edl")
            except Exception as e:
                logger.warning(f"Semantic B-roll planning error: {e}")

        # Step 6: Export subtitles (SRT, VTT, ASS)
        base_out = (Path(output_path).with_suffix("") if output_path else video_path.parent / f"{video_path.stem}_kinetic")
        sub_exports = self.export_subtitles(
            cues,
            output_base_path=base_out,
            formats=[f for f in export_formats if f in ("srt", "vtt", "ass")],
            preset=preset,
        )

        # Step 7: Render burned-in video if requested
        render_result = None
        if "mp4" in export_formats:
            final_mp4 = Path(output_path) if output_path else video_path.parent / f"{video_path.stem}_captioned.mp4"
            render_res = self.render_video(video_path, cues, final_mp4, preset, cuts=cuts, overlays=overlays)
            if render_res.success:
                sub_exports["mp4"] = str(final_mp4)
                render_result = render_res.data

        elapsed = round(time.time() - start_time, 2)
        return ToolResult(
            success=True,
            data={
                "video_path": str(video_path),
                "preset_id": preset_id,
                "preset_name": preset.get("name"),
                "video_style": video_style,
                "cuts": cuts,
                "overlays": overlays,
                "edl": edl_v3,
                "total_words": len(words),
                "total_cues": len(cues),
                "exports": sub_exports,
                "cues": cues,
                "render_details": render_result,
            },
            artifacts=list(sub_exports.values()),
            duration_seconds=elapsed,
        )
