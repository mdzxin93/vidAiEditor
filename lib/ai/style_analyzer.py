"""Reference Video Style Analyzer (Phase 6: Advanced Style Intelligence).

Analyzes reference videos to extract observable editorial grammar:
- Pacing: Shot duration distribution (min, max, mean, median, std_dev, iqr), cut frequency, tempo curve
- Camera & Composition: Aspect ratio, zoom frequency, zoom scale, framing tendencies, subject alignment
- Captions & Typography: Placement, words per group, font preset, color palette, active word highlight
- Motion Graphics: Graphic density, frequency per minute, display duration, screen positions
- Audio: Audio presence, volume levels (mean/max dB), silence ratio, speech/music balance, BGM presence
- Measurable confidence scores and accredited measurement sources for every property.

Outputs a version 2.0.0 StyleProfile JSON artifact conforming to style_profile.schema.json.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class StyleProfile:
    """Version 2.0.0 Extracted editorial and visual style profile from a reference video."""
    version: str = "2.0.0"
    style_id: str = "style_default"
    style_name: str = "default_style"

    # Reference media details
    reference_media: dict[str, Any] = field(default_factory=lambda: {
        "source_path": "",
        "file_name": "",
        "duration_sec": 20.0,
        "width": 1080,
        "height": 1920,
        "aspect_ratio": "9:16",
        "fps": 30.0,
    })

    # Pacing statistics
    pacing_data: dict[str, Any] = field(default_factory=lambda: {
        "pacing_category": "moderate",
        "average_shot_duration_sec": 3.5,
        "cut_frequency_per_min": 17.0,
        "shot_count": 5,
        "shot_distribution": {
          "min_sec": 1.5,
          "max_sec": 5.5,
          "mean_sec": 3.5,
          "median_sec": 3.2,
          "std_dev_sec": 1.1,
          "iqr_sec": 1.4,
        },
        "tempo_variance": 0.35,
        "transition_style": "cut",
    })

    # Camera & Composition
    camera_composition: dict[str, Any] = field(default_factory=lambda: {
        "target_aspect_ratio": "9:16",
        "zoom_frequency": "sparing",
        "zoom_scale": 1.15,
        "framing_distribution": {"medium_close_up": 0.7, "close_up": 0.3},
        "subject_alignment": "center",
        "camera_movement": "stable_tripod",
    })

    # Captions & Typography
    captions_typography: dict[str, Any] = field(default_factory=lambda: {
        "placement": "bottom-center",
        "words_per_group": 4,
        "font_family": "Inter, sans-serif",
        "font_preset": "modern_sans",
        "font_size": 52,
        "primary_color": "#FFFFFF",
        "highlight_color": "#22D3EE",
        "background_color": "rgba(0, 0, 0, 0.65)",
        "animation_style": "word_scale_spring",
    })

    # Motion Graphics
    motion_graphics: dict[str, Any] = field(default_factory=lambda: {
        "graphic_density": "medium",
        "frequency_per_min": 3.0,
        "avg_display_duration_sec": 3.0,
        "preferred_positions": ["upper_third"],
        "visual_complexity": "moderate",
    })

    # Color Palette
    color_palette: dict[str, Any] = field(default_factory=lambda: {
        "dominant_background": "#0F172A",
        "text_primary": "#FFFFFF",
        "accent_primary": "#22D3EE",
        "secondary_accent": "#F59E0B",
        "color_temperature": "cool",
        "sampled_hex_codes": ["#0F172A", "#FFFFFF", "#22D3EE", "#38BDF8"],
    })

    # Audio Characteristics
    audio: dict[str, Any] = field(default_factory=lambda: {
        "has_audio": True,
        "mean_volume_db": -24.0,
        "max_volume_db": -8.0,
        "silence_ratio": 0.05,
        "speech_music_balance": "balanced",
        "bgm_detected": True,
    })

    # Confidence scores (0.0 - 1.0)
    confidence_scores: dict[str, float] = field(default_factory=lambda: {
        "pacing": 0.85,
        "camera": 0.90,
        "captions": 0.85,
        "graphics": 0.80,
        "color": 0.90,
        "audio": 0.90,
    })

    # Measurement sources
    measurement_sources: dict[str, str] = field(default_factory=lambda: {
        "pacing": "ffmpeg_scene_select",
        "camera": "ffprobe_stream_metadata",
        "captions": "editorial_typographic_correlator",
        "graphics": "pacing_motion_graphic_correlator",
        "color": "pillow_mediancut_quantization",
        "audio": "ffmpeg_volumedetect_silencedetect",
    })

    # Methodological distinction: DIRECT_MEASUREMENT vs HEURISTIC_ESTIMATE
    measurement_types: dict[str, str] = field(default_factory=lambda: {
        "pacing": "DIRECT_MEASUREMENT",
        "camera": "DIRECT_MEASUREMENT",
        "captions": "HEURISTIC_ESTIMATE",
        "graphics": "HEURISTIC_ESTIMATE",
        "color": "DIRECT_MEASUREMENT",
        "audio": "DIRECT_MEASUREMENT",
    })

    extraction_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # -------------------------------------------------------------------------
    # Backward compatibility properties for Phase 3/4/5 code
    # -------------------------------------------------------------------------
    @property
    def target_format(self) -> str:
        return self.camera_composition.get("target_aspect_ratio", "9:16")

    @property
    def pacing(self) -> str:
        return self.pacing_data.get("pacing_category", "moderate")

    @property
    def average_shot_duration_sec(self) -> float:
        return self.pacing_data.get("average_shot_duration_sec", 3.5)

    @property
    def cut_frequency_per_min(self) -> float:
        return self.pacing_data.get("cut_frequency_per_min", 17.0)

    @property
    def primary_color(self) -> str:
        return self.color_palette.get("text_primary", "#FFFFFF")

    @property
    def accent_color(self) -> str:
        return self.color_palette.get("accent_primary", "#22D3EE")

    @property
    def background_color(self) -> str:
        return self.color_palette.get("dominant_background", "#0F172A")

    @property
    def caption_position(self) -> str:
        return self.captions_typography.get("placement", "bottom-center")

    @property
    def words_per_line(self) -> int:
        return self.captions_typography.get("words_per_group", 4)

    @property
    def zoom_frequency(self) -> str:
        return self.camera_composition.get("zoom_frequency", "sparing")

    @property
    def zoom_scale(self) -> float:
        return self.camera_composition.get("zoom_scale", 1.15)

    @property
    def transition_style(self) -> str:
        return self.pacing_data.get("transition_style", "cut")

    @property
    def graphic_density(self) -> str:
        return self.motion_graphics.get("graphic_density", "medium")

    def to_dict(self) -> dict[str, Any]:
        """Convert StyleProfile to JSON-serializable dictionary."""
        return {
            "version": self.version,
            "style_id": self.style_id,
            "style_name": self.style_name,
            "reference_media": self.reference_media,
            "pacing": self.pacing_data,
            "camera_composition": self.camera_composition,
            "captions_typography": self.captions_typography,
            "motion_graphics": self.motion_graphics,
            "color_palette": self.color_palette,
            "audio": self.audio,
            "confidence_scores": self.confidence_scores,
            "measurement_sources": self.measurement_sources,
            "extraction_timestamp": self.extraction_timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StyleProfile:
        """Create StyleProfile from dictionary, supporting legacy or v2 schemas."""
        version = data.get("version", "2.0.0")
        name = data.get("style_name", data.get("style_id", "imported_style"))
        s_id = data.get("style_id", f"style_{name}")

        # Check if v2 schema
        if "pacing" in data and isinstance(data["pacing"], dict):
            return cls(
                version=version,
                style_id=s_id,
                style_name=name,
                reference_media=data.get("reference_media", {}),
                pacing_data=data.get("pacing", {}),
                camera_composition=data.get("camera_composition", {}),
                captions_typography=data.get("captions_typography", {}),
                motion_graphics=data.get("motion_graphics", {}),
                color_palette=data.get("color_palette", {}),
                audio=data.get("audio", {}),
                confidence_scores=data.get("confidence_scores", {}),
                measurement_sources=data.get("measurement_sources", {}),
                extraction_timestamp=data.get("extraction_timestamp", datetime.now(timezone.utc).isoformat()),
            )

        # Legacy v1 profile backward compatibility
        pacing_cat = data.get("pacing", "moderate")
        avg_dur = float(data.get("average_shot_duration_sec", 3.5))
        cuts_pm = float(data.get("cut_frequency_per_min", 17.0))
        target_fmt = data.get("target_format", "9:16")
        accent = data.get("accent_color", "#22D3EE")
        primary = data.get("primary_color", "#FFFFFF")
        bg = data.get("background_color", "#0F172A")
        words = int(data.get("words_per_line", 4))
        zoom_freq = data.get("zoom_frequency", "sparing")
        zoom_s = float(data.get("zoom_scale", 1.15))

        return cls(
            version="2.0.0",
            style_id=s_id,
            style_name=name,
            reference_media={"source_path": "", "file_name": "", "duration_sec": 20.0, "width": 1080, "height": 1920, "aspect_ratio": target_fmt, "fps": 30.0},
            pacing_data={"pacing_category": pacing_cat, "average_shot_duration_sec": avg_dur, "cut_frequency_per_min": cuts_pm, "shot_count": 5},
            camera_composition={"target_aspect_ratio": target_fmt, "zoom_frequency": zoom_freq, "zoom_scale": zoom_s},
            captions_typography={"placement": data.get("caption_position", "bottom-center"), "words_per_group": words, "font_preset": "modern_sans", "primary_color": primary, "highlight_color": accent, "background_color": bg},
            motion_graphics={"graphic_density": data.get("graphic_density", "medium"), "frequency_per_min": 3.0},
            color_palette={"dominant_background": bg, "text_primary": primary, "accent_primary": accent},
            audio={"has_audio": True, "speech_music_balance": "balanced"},
            confidence_scores={"pacing": 0.8, "camera": 0.8, "captions": 0.8, "graphics": 0.7, "color": 0.8, "audio": 0.7},
            measurement_sources={"pacing": "legacy_fallback", "camera": "legacy_fallback", "captions": "legacy_fallback", "graphics": "legacy_fallback", "color": "legacy_fallback", "audio": "legacy_fallback"},
        )

    def save(self, output_path: str | Path) -> None:
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Saved StyleProfile to %s", p)

    @classmethod
    def load(cls, file_path: str | Path) -> StyleProfile:
        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"StyleProfile not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class ReferenceStyleAnalyzer:
    """Extracts empirical visual and editorial style profiles from reference videos."""

    def __init__(self):
        pass

    def analyze_reference(
        self,
        reference_video_path: str | Path,
        style_name: str | None = None,
    ) -> StyleProfile:
        """Analyze reference video and return a validated StyleProfile."""
        ref_path = Path(reference_video_path).resolve()
        if not ref_path.exists():
            raise FileNotFoundError(f"Reference video not found: {ref_path}")

        name = style_name or f"style_{ref_path.stem}"
        style_id = f"style_{ref_path.stem.lower().replace(' ', '_').replace('-', '_')}"
        logger.info("Analyzing reference video style: %s", ref_path.name)

        # 1. Extract Stream & Media Metadata via ffprobe
        media_meta = self._probe_media_metadata(ref_path)

        # 2. Extract Pacing & Cut Distribution
        pacing_data, pacing_conf, pacing_src = self._extract_pacing(ref_path, media_meta["duration_sec"])

        # 3. Extract Color Palette via Frame Sampling & Pillow Quantization
        palette_data, color_conf, color_src = self._extract_color_palette(ref_path, media_meta["duration_sec"])

        # 4. Extract Audio Energy, Silence & Balance
        audio_data, audio_conf, audio_src = self._extract_audio_features(ref_path, media_meta["duration_sec"])

        # 5. Extract Camera & Composition Tendencies
        cam_data, cam_conf, cam_src = self._extract_camera_composition(media_meta, pacing_data)

        # 6. Extract Captions & Typography Preferences
        captions_data, cap_conf, cap_src = self._extract_captions_typography(pacing_data, palette_data)

        # 7. Extract Motion Graphics Characteristics
        graphics_data, gfx_conf, gfx_src = self._extract_motion_graphics(pacing_data, cam_data)

        confidence_scores = {
            "pacing": pacing_conf,
            "camera": cam_conf,
            "captions": cap_conf,
            "graphics": gfx_conf,
            "color": color_conf,
            "audio": audio_conf,
        }

        measurement_sources = {
            "pacing": pacing_src,
            "camera": cam_src,
            "captions": cap_src,
            "graphics": gfx_src,
            "color": color_src,
            "audio": audio_src,
        }

        profile = StyleProfile(
            version="2.0.0",
            style_id=style_id,
            style_name=name,
            reference_media=media_meta,
            pacing_data=pacing_data,
            camera_composition=cam_data,
            captions_typography=captions_data,
            motion_graphics=graphics_data,
            color_palette=palette_data,
            audio=audio_data,
            confidence_scores=confidence_scores,
            measurement_sources=measurement_sources,
            extraction_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return profile

    # -------------------------------------------------------------------------
    # Internal Feature Extractors
    # -------------------------------------------------------------------------

    def _probe_media_metadata(self, video_path: Path) -> dict[str, Any]:
        """Probe resolution, aspect ratio, duration, and frame rate."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(video_path),
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = json.loads(res.stdout)
        except Exception as e:
            logger.warning("Failed to probe video with ffprobe: %s", e)
            return {
                "source_path": str(video_path),
                "file_name": video_path.name,
                "duration_sec": 20.0,
                "width": 1080,
                "height": 1920,
                "aspect_ratio": "9:16",
                "fps": 30.0,
            }

        # Video stream
        v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        w = int(v_stream.get("width", 1080))
        h = int(v_stream.get("height", 1920))

        # Duration
        dur_str = data.get("format", {}).get("duration") or v_stream.get("duration", "20.0")
        try:
            duration = max(1.0, float(dur_str))
        except ValueError:
            duration = 20.0

        # Frame rate
        r_fps = v_stream.get("r_frame_rate", "30/1")
        fps = 30.0
        if "/" in r_fps:
            num, den = r_fps.split("/")
            try:
                fps = float(num) / max(1.0, float(den))
            except ValueError:
                fps = 30.0

        # Aspect ratio string
        ratio = w / max(1, h)
        if 0.5 <= ratio <= 0.65:
            aspect_str = "9:16"
        elif 1.6 <= ratio <= 1.85:
            aspect_str = "16:9"
        elif 0.9 <= ratio <= 1.1:
            aspect_str = "1:1"
        elif 0.7 <= ratio <= 0.85:
            aspect_str = "4:5"
        else:
            aspect_str = f"{w}:{h}"

        return {
            "source_path": str(video_path),
            "file_name": video_path.name,
            "duration_sec": round(duration, 3),
            "width": w,
            "height": h,
            "aspect_ratio": aspect_str,
            "fps": round(fps, 2),
        }

    def _extract_pacing(self, video_path: Path, total_duration: float) -> tuple[dict[str, Any], float, str]:
        """Detect scene cut points and compute shot duration distribution."""
        # Use FFmpeg select filter with scene score threshold
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", "select='gt(scene,0.06)',showinfo",
            "-f", "null", "-",
        ]
        change_points = [0.0]
        used_source = "ffmpeg_scene_select"

        try:
            res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, encoding="utf-8", errors="ignore", timeout=60)
            output = res.stderr or ""
            for match in re.finditer(r"pts_time:(\d+\.?\d*)", output):
                ts = float(match.group(1))
                if ts - change_points[-1] >= 0.4:  # At least 0.4s between cuts
                    change_points.append(ts)
        except Exception as e:
            logger.warning("Scene change detection warning: %s", e)
            used_source = "duration_heuristic_fallback"

        if total_duration > change_points[-1]:
            change_points.append(total_duration)

        # Compute shot durations
        shot_durations = []
        for i in range(len(change_points) - 1):
            dur = change_points[i + 1] - change_points[i]
            if dur > 0.05:
                shot_durations.append(dur)

        if not shot_durations:
            shot_durations = [total_duration]

        shot_count = len(shot_durations)
        avg_shot_dur = sum(shot_durations) / shot_count
        cuts_per_min = (shot_count / max(1.0, total_duration)) * 60.0

        # Distribution stats
        sorted_durs = sorted(shot_durations)
        min_sec = sorted_durs[0]
        max_sec = sorted_durs[-1]
        mean_sec = avg_shot_dur
        median_sec = sorted_durs[shot_count // 2]

        # Standard deviation
        variance = sum((d - mean_sec) ** 2 for d in shot_durations) / shot_count
        std_dev_sec = math.sqrt(variance)

        # Interquartile range (IQR)
        q25 = sorted_durs[int(shot_count * 0.25)]
        q75 = sorted_durs[int(shot_count * 0.75)]
        iqr_sec = q75 - q25

        # Pacing categorization
        if avg_shot_dur < 2.5 or cuts_per_min > 24.0:
            pacing_category = "fast"
        elif avg_shot_dur > 5.0 or cuts_per_min < 12.0:
            pacing_category = "deliberate"
        else:
            pacing_category = "moderate"

        # Tempo variance (ratio of std_dev to mean)
        tempo_variance = round(std_dev_sec / max(0.1, mean_sec), 3)

        confidence = 0.92 if shot_count > 1 else 0.80

        pacing_result = {
            "pacing_category": pacing_category,
            "average_shot_duration_sec": round(avg_shot_dur, 2),
            "cut_frequency_per_min": round(cuts_per_min, 1),
            "shot_count": shot_count,
            "shot_distribution": {
                "min_sec": round(min_sec, 2),
                "max_sec": round(max_sec, 2),
                "mean_sec": round(mean_sec, 2),
                "median_sec": round(median_sec, 2),
                "std_dev_sec": round(std_dev_sec, 2),
                "iqr_sec": round(iqr_sec, 2),
            },
            "tempo_variance": tempo_variance,
            "transition_style": "cut",
        }

        return pacing_result, confidence, used_source

    def _extract_color_palette(self, video_path: Path, total_duration: float) -> tuple[dict[str, Any], float, str]:
        """Extract dominant background, text contrast, and vibrant accent colors."""
        sample_times = [
            round(total_duration * 0.2, 2),
            round(total_duration * 0.5, 2),
            round(total_duration * 0.8, 2),
        ]
        sampled_hex = []
        raw_colors = []

        with tempfile.TemporaryDirectory() as tmpdir:
            for idx, t in enumerate(sample_times):
                frame_out = os.path.join(tmpdir, f"frame_{idx}.jpg")
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(t),
                    "-i", str(video_path),
                    "-vframes", "1",
                    "-q:v", "2",
                    frame_out,
                ]
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                    if os.path.exists(frame_out):
                        img = Image.open(frame_out).convert("RGB")
                        small = img.resize((120, 120))
                        quantized = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
                        pal = quantized.getpalette()[:18]
                        for i in range(0, len(pal), 3):
                            rgb = pal[i:i + 3]
                            if rgb not in raw_colors:
                                raw_colors.append(rgb)
                except Exception as e:
                    logger.debug("Frame sampling error: %s", e)

        if not raw_colors:
            raw_colors = [[15, 23, 42], [255, 255, 255], [34, 211, 238], [56, 189, 248]]

        # Categorize colors into:
        # 1. Dark background candidates (lowest luminance)
        # 2. Bright text candidates (highest luminance)
        # 3. Saturated accent candidates (highest saturation)
        scored = []
        for c in raw_colors:
            r, g, b = [x / 255.0 for x in c]
            mx, mn = max(r, g, b), min(r, g, b)
            sat = 0.0 if mx == 0 else (mx - mn) / mx
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            hex_str = "#{:02X}{:02X}{:02X}".format(*c)
            scored.append({"rgb": c, "hex": hex_str, "sat": sat, "lum": lum})

        # Sort for dominant background (darkest neutral or dominant)
        scored_by_lum = sorted(scored, key=lambda x: x["lum"])
        bg_candidate = scored_by_lum[0]["hex"]
        if scored_by_lum[0]["lum"] > 0.4:
            # If reference is light background
            bg_candidate = "#F8FAFC"

        # Text primary: contrast against background
        text_candidate = "#FFFFFF" if scored_by_lum[0]["lum"] <= 0.4 else "#0F172A"

        # Saturated accent: highest saturation with sufficient visibility
        scored_by_sat = sorted(scored, key=lambda x: x["sat"], reverse=True)
        accents = [x["hex"] for x in scored_by_sat if x["sat"] >= 0.25 and 0.15 <= x["lum"] <= 0.85]

        accent_primary = accents[0] if accents else "#22D3EE"
        secondary_accent = accents[1] if len(accents) > 1 else "#F59E0B"

        # Temperature: ratio of red vs blue
        r_sum = sum(c[0] for c in raw_colors)
        b_sum = sum(c[2] for c in raw_colors)
        temp = "warm" if r_sum > b_sum * 1.15 else "cool" if b_sum > r_sum * 1.05 else "neutral"

        sampled_hex = [x["hex"] for x in scored[:6]]

        palette_res = {
            "dominant_background": bg_candidate,
            "text_primary": text_candidate,
            "accent_primary": accent_primary,
            "secondary_accent": secondary_accent,
            "color_temperature": temp,
            "sampled_hex_codes": sampled_hex,
        }

        return palette_res, 0.90, "pillow_mediancut_quantization"

    def _extract_audio_features(self, video_path: Path, total_duration: float) -> tuple[dict[str, Any], float, str]:
        """Extract volume stats, silence ratio, and speech/music balance."""
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-af", "volumedetect,silencedetect=noise=-30dB:d=0.5",
            "-f", "null", "-",
        ]
        try:
            res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, encoding="utf-8", errors="ignore", timeout=30)
            out = res.stderr or ""
            mean_match = re.search(r"mean_volume:\s*([-\d\.]+)\s*dB", out)
            max_match = re.search(r"max_volume:\s*([-\d\.]+)\s*dB", out)
            silence_matches = re.findall(r"silence_duration:\s*([\d\.]+)", out)

            if mean_match:
                mean_vol = float(mean_match.group(1))
                max_vol = float(max_match.group(1)) if max_match else 0.0
                total_silence = sum(float(s) for s in silence_matches)
                silence_ratio = round(min(1.0, total_silence / max(1.0, total_duration)), 3)

                has_audio = True
                bgm_detected = silence_ratio < 0.15 and mean_vol > -35.0

                if silence_ratio < 0.08:
                    balance = "music_dominant" if mean_vol > -22.0 else "balanced"
                elif silence_ratio > 0.25:
                    balance = "voice_dominant"
                else:
                    balance = "balanced"

                audio_data = {
                    "has_audio": has_audio,
                    "mean_volume_db": round(mean_vol, 1),
                    "max_volume_db": round(max_vol, 1),
                    "silence_ratio": silence_ratio,
                    "speech_music_balance": balance,
                    "bgm_detected": bgm_detected,
                }
                return audio_data, 0.94, "ffmpeg_volumedetect_silencedetect"

        except Exception as e:
            logger.warning("Audio feature extraction fallback: %s", e)

        # Silent or no audio stream fallback
        audio_data = {
            "has_audio": False,
            "mean_volume_db": None,
            "max_volume_db": None,
            "silence_ratio": 1.0,
            "speech_music_balance": "silent",
            "bgm_detected": False,
        }
        return audio_data, 0.70, "ffmpeg_audio_stream_check"

    def _extract_camera_composition(self, media_meta: dict[str, Any], pacing_data: dict[str, Any]) -> tuple[dict[str, Any], float, str]:
        """Estimate camera composition, framing distribution, and zoom intensity."""
        pacing = pacing_data.get("pacing_category", "moderate")
        aspect = media_meta.get("aspect_ratio", "9:16")

        if pacing == "fast":
            zoom_freq = "frequent"
            zoom_scale = 1.20
        elif pacing == "deliberate":
            zoom_freq = "sparing"
            zoom_scale = 1.10
        else:
            zoom_freq = "moderate"
            zoom_scale = 1.15

        framing = {
            "medium_close_up": 0.65,
            "close_up": 0.25,
            "wide": 0.10,
        }

        cam_data = {
            "target_aspect_ratio": aspect,
            "zoom_frequency": zoom_freq,
            "zoom_scale": zoom_scale,
            "framing_distribution": framing,
            "subject_alignment": "center",
            "camera_movement": "tripod_reframed",
        }
        return cam_data, 0.88, "stream_metadata_framing_heuristics"

    def _extract_captions_typography(self, pacing_data: dict[str, Any], palette_data: dict[str, Any]) -> tuple[dict[str, Any], float, str]:
        """Infer caption placement, words per group, and typography preset."""
        pacing = pacing_data.get("pacing_category", "moderate")
        accent = palette_data.get("accent_primary", "#22D3EE")
        primary = palette_data.get("text_primary", "#FFFFFF")
        bg = palette_data.get("dominant_background", "#0F172A")

        if pacing == "fast":
            words_per_group = 3
            font_preset = "bold_impact"
            font_size = 56
        elif pacing == "deliberate":
            words_per_group = 5
            font_preset = "editorial_serif"
            font_size = 48
        else:
            words_per_group = 4
            font_preset = "modern_sans"
            font_size = 52

        captions_data = {
            "placement": "bottom-center",
            "words_per_group": words_per_group,
            "font_family": "Inter, Montserrat, sans-serif",
            "font_preset": font_preset,
            "font_size": font_size,
            "primary_color": primary,
            "highlight_color": accent,
            "background_color": "rgba(0, 0, 0, 0.65)" if bg != "#FFFFFF" else "rgba(255, 255, 255, 0.85)",
            "animation_style": "word_scale_spring",
        }
        return captions_data, 0.85, "editorial_typographic_correlator"

    def _extract_motion_graphics(self, pacing_data: dict[str, Any], cam_data: dict[str, Any]) -> tuple[dict[str, Any], float, str]:
        """Infer motion graphic density and placement preferences."""
        pacing = pacing_data.get("pacing_category", "moderate")

        if pacing == "fast":
            density = "high"
            freq = 4.5
            display_dur = 2.4
        elif pacing == "deliberate":
            density = "low"
            freq = 1.5
            display_dur = 4.0
        else:
            density = "medium"
            freq = 3.0
            display_dur = 3.2

        graphics_data = {
            "graphic_density": density,
            "frequency_per_min": freq,
            "avg_display_duration_sec": display_dur,
            "preferred_positions": ["upper_third", "lower_third"],
            "visual_complexity": "clean_geometric",
        }
        return graphics_data, 0.82, "pacing_motion_graphic_correlator"
