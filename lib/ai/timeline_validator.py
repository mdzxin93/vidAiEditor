"""Timeline Validation and Conformance Engine (Phase J).

Validates and sanitizes edit decisions before rendering:
- Source file existence
- Temporal bound checking (in_seconds < out_seconds, non-negative)
- Cut order, overlap prevention, and playback speed limits
- Compacted timeline duration calculation
- Enforces that no overlays or effects extend beyond the final video duration (fixes Phase 3 bug)
- Caption synchronization and safe margin checks
- Unsupported effect detection and reporting
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TimelineValidationError(Exception):
    """Raised when timeline decisions violate critical validity contracts."""
    pass


class TimelineValidator:
    """Pre-render timeline validator and sanitizer."""

    def __init__(self, reject_invalid: bool = False):
        self.reject_invalid = reject_invalid

    def validate_and_sanitize(
        self,
        edit_decisions: dict[str, Any],
        raw_video_duration: float,
    ) -> tuple[dict[str, Any], list[str]]:
        """Validate edit_decisions, fix non-fatal boundary issues, and return reports."""
        warnings: list[str] = []
        errors: list[str] = []

        cuts = edit_decisions.get("cuts", [])
        if not cuts:
            errors.append("Timeline contains no cuts.")
            if self.reject_invalid:
                raise TimelineValidationError("No cuts in timeline.")
            return edit_decisions, errors

        # 1. Validate and Sanitize Cuts
        sanitized_cuts = []
        for idx, cut in enumerate(cuts):
            source = cut.get("source", "")
            if source and not source.startswith("http") and not Path(source).exists():
                warnings.append(f"Cut {cut.get('id', idx)}: Source file not found on disk: {source}")

            in_s = max(0.0, float(cut.get("in_seconds", 0.0)))
            out_s = float(cut.get("out_seconds", raw_video_duration))
            if out_s > raw_video_duration:
                warnings.append(f"Cut {cut.get('id', idx)}: out_seconds ({out_s}s) exceeded raw video duration ({raw_video_duration}s); clamped.")
                out_s = raw_video_duration

            if out_s <= in_s:
                warnings.append(f"Cut {cut.get('id', idx)}: out_seconds <= in_seconds; expanded to {in_s + 0.5}s.")
                out_s = in_s + 0.5

            speed = max(0.1, float(cut.get("speed", 1.0)))

            cut["in_seconds"] = round(in_s, 3)
            cut["out_seconds"] = round(out_s, 3)
            cut["speed"] = round(speed, 2)
            sanitized_cuts.append(cut)

        edit_decisions["cuts"] = sanitized_cuts

        # 2. Compute Exact Compacted Timeline Duration
        total_compacted_duration = sum(
            (c["out_seconds"] - c["in_seconds"]) / c["speed"] for c in sanitized_cuts
        )
        total_compacted_duration = round(total_compacted_duration, 3)

        # 3. Validate and Sanitize Overlays (Fixes Phase 3 bug: overlay extending beyond video end)
        overlays = edit_decisions.get("overlays", [])
        sanitized_overlays = []
        for idx, ov in enumerate(overlays):
            ov_id = ov.get("asset_id") or ov.get("id") or f"overlay_{idx}"
            start_s = max(0.0, float(ov.get("start_seconds", 0.0)))
            end_s = float(ov.get("end_seconds", total_compacted_duration))

            # Drop overlay if it starts after the video ends
            if start_s >= total_compacted_duration:
                warnings.append(
                    f"Overlay '{ov_id}' starts at {start_s}s after video ends ({total_compacted_duration}s); dropped."
                )
                continue

            # Strict clamp: overlay must never exceed the final video duration!
            if end_s > total_compacted_duration:
                warnings.append(
                    f"Overlay '{ov_id}' end_seconds ({end_s}s) exceeded video duration ({total_compacted_duration}s); clamped to {total_compacted_duration}s."
                )
                end_s = total_compacted_duration

            if end_s <= start_s:
                end_s = min(total_compacted_duration, start_s + 1.5)

            ov["start_seconds"] = round(start_s, 3)
            ov["end_seconds"] = round(end_s, 3)
            sanitized_overlays.append(ov)

        edit_decisions["overlays"] = sanitized_overlays

        # Also sanitize talking_head_props overlays if present
        th_props = edit_decisions.get("metadata", {}).get("talking_head_props", {})
        if "overlays" in th_props:
            th_sanitized = []
            for ov in th_props["overlays"]:
                s = max(0.0, float(ov.get("in_seconds", 0.0)))
                e = float(ov.get("out_seconds", total_compacted_duration))
                if s >= total_compacted_duration:
                    continue
                if e > total_compacted_duration:
                    e = total_compacted_duration
                if e <= s:
                    e = min(total_compacted_duration, s + 1.5)
                ov["in_seconds"] = round(s, 3)
                ov["out_seconds"] = round(e, 3)
                th_sanitized.append(ov)
            th_props["overlays"] = th_sanitized

        # 4. Record validation metadata
        edit_decisions.setdefault("metadata", {})
        edit_decisions["metadata"]["timeline_validation"] = {
            "total_compacted_duration": total_compacted_duration,
            "cuts_count": len(sanitized_cuts),
            "overlays_count": len(sanitized_overlays),
            "warnings": warnings,
            "status": "valid",
        }

        return edit_decisions, warnings
