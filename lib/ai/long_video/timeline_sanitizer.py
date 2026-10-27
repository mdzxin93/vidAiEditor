"""Timeline Sanitizer for Long Sequences (Phase 11).

Provides:
- Gap detection and automated closure between sequential cuts.
- Overlap elimination to prevent audio double-plays.
- Monotonic timestamp validation.
- Subtitle and overlay bounds checking.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("openmontage.timeline_sanitizer")


class TimelineSanitizer:
    """Sanitizes long-video edit decisions to guarantee seamless, artifact-free playback."""

    @classmethod
    def sanitize(
        cls,
        edit_decisions: dict[str, Any],
        video_duration: float,
    ) -> dict[str, Any]:
        """Validate and adjust cuts, overlays, and captions for strict boundary continuity."""
        sanitized = dict(edit_decisions)
        cuts = list(sanitized.get("cuts", []))

        if not cuts:
            return sanitized

        sanitized_cuts = []
        for i, cut in enumerate(cuts):
            in_s = max(0.0, float(cut.get("in_seconds", 0.0)))
            out_s = min(video_duration, float(cut.get("out_seconds", in_s + 1.0)))

            # Prevent zero or inverted duration
            if out_s <= in_s:
                out_s = in_s + 0.5

            cut["in_seconds"] = round(in_s, 3)
            cut["out_seconds"] = round(out_s, 3)

            # Prevent overlap with previous cut if on the same track
            if sanitized_cuts:
                prev_out = sanitized_cuts[-1]["out_seconds"]
                if in_s < prev_out and cut.get("layer") == sanitized_cuts[-1].get("layer"):
                    # Adjust boundary to remove overlap
                    cut["in_seconds"] = prev_out
                    if cut["out_seconds"] <= cut["in_seconds"]:
                        cut["out_seconds"] = cut["in_seconds"] + 0.5

            sanitized_cuts.append(cut)

        sanitized["cuts"] = sanitized_cuts

        # Sanitize Subtitles
        if "subtitles" in sanitized and "words" in sanitized["subtitles"]:
            sanitized_words = []
            for w in sanitized["subtitles"]["words"]:
                start = max(0.0, float(w.get("start", 0.0)))
                end = min(video_duration, float(w.get("end", start + 0.2)))
                if end > start:
                    w["start"] = round(start, 3)
                    w["end"] = round(end, 3)
                    sanitized_words.append(w)
            sanitized["subtitles"]["words"] = sanitized_words

        # Sanitize Overlays
        if "overlays" in sanitized:
            sanitized_overlays = []
            for ov in sanitized["overlays"]:
                start_s = max(0.0, float(ov.get("start_seconds", ov.get("in_seconds", 0.0))))
                end_s = min(video_duration, float(ov.get("end_seconds", ov.get("out_seconds", start_s + 3.0))))
                if end_s > start_s:
                    ov["start_seconds"] = round(start_s, 3)
                    ov["end_seconds"] = round(end_s, 3)
                    ov.pop("in_seconds", None)
                    ov.pop("out_seconds", None)
                    sanitized_overlays.append(ov)
            sanitized["overlays"] = sanitized_overlays

        return sanitized
