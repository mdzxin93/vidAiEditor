"""Intelligent QA Fixer Engine (Phase 8 Safe Automatic Corrections).

Applies bounded, deterministic, and safe corrections to edit_decisions:
- Move overlays out of subtitle and face collision zones into certified safe regions
- Clamp out-of-bounds overlay display durations
- Correct invalid crop rectangles to stay strictly within source bounds
- Adjust caption density and safe margins
- Suppress simultaneous duplicate/colliding graphics
- Record immutable FixRecord audit trails for every modification
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from lib.ai.qa_models import (
    FixRecord,
    QAFixType,
    QAIssue,
    QASeverity,
)

logger = logging.getLogger(__name__)


class IntelligentQAFixer:
    """Applies safe, bounded corrections to edit_decisions based on detected QA issues."""

    def apply_fixes(
        self,
        edit_decisions: dict[str, Any],
        issues: list[QAIssue],
        video_duration: float,
    ) -> tuple[dict[str, Any], list[FixRecord]]:
        """Apply bounded automatic fixes to edit_decisions and return (updated_edits, fix_records)."""
        edits = copy.deepcopy(edit_decisions)
        fix_records: list[FixRecord] = []

        # Filter only auto-fixable issues
        fixable_issues = [i for i in issues if i.auto_fix_allowed and i.suggested_fix != QAFixType.NONE.value]

        for issue in fixable_issues:
            record = None

            if issue.suggested_fix == QAFixType.MOVE_OVERLAY.value:
                record = self._fix_move_overlay(edits, issue)

            elif issue.suggested_fix == QAFixType.SHORTEN_INTERVAL.value:
                record = self._fix_shorten_interval(edits, issue, video_duration)

            elif issue.suggested_fix == QAFixType.RETARGET_CROP.value:
                record = self._fix_retarget_crop(edits, issue)

            elif issue.suggested_fix == QAFixType.ADJUST_CAPTION_POSITION.value:
                record = self._fix_adjust_caption(edits, issue)

            elif issue.suggested_fix == QAFixType.SUPPRESS_REDUNDANT_GRAPHIC.value:
                record = self._fix_suppress_redundant(edits, issue)

            elif issue.suggested_fix == QAFixType.SCALE_OVERLAY.value:
                record = self._fix_scale_overlay(edits, issue)

            elif issue.suggested_fix == QAFixType.NORMALIZE_AUDIO.value:
                record = self._fix_normalize_audio(edits, issue)

            if record:
                fix_records.append(record)

        return edits, fix_records

    # ------------------------------------------------------------------------
    # Specific Safe Fix Implementations
    # ------------------------------------------------------------------------

    def _fix_move_overlay(
        self, edits: dict[str, Any], issue: QAIssue
    ) -> FixRecord | None:
        """Move an overlay out of the subtitle zone (>1500px) or face zone into upper_third/upper_window."""
        target_id = issue.evidence.get("overlay_id")
        th_props = edits.setdefault("metadata", {}).setdefault("talking_head_props", {})
        th_overlays = th_props.setdefault("overlays", [])
        top_overlays = edits.setdefault("overlays", [])

        moved = False
        original_val = "unknown"
        target_preset = "upper_third"

        # Check in talking_head_props
        for ov in th_overlays:
            curr_id = ov.get("id") or ov.get("asset_id")
            if curr_id == target_id or (target_id is None and issue.start_seconds <= ov.get("in_seconds", 0) <= issue.end_seconds):
                original_val = ov.get("position", "lower_third")
                # Large layouts (process_flow, broll) use upper_window
                target_preset = "upper_window" if ov.get("type") in ("process_flow", "broll") else "upper_third"
                ov["position"] = target_preset
                moved = True
                break

        # Check in top-level overlays
        for ov in top_overlays:
            curr_id = ov.get("asset_id") or ov.get("id")
            if curr_id == target_id or (target_id is None and issue.start_seconds <= ov.get("start_seconds", 0) <= issue.end_seconds):
                pos = ov.get("position")
                if isinstance(pos, dict):
                    original_val = f"y={pos.get('y')}"
                    pos["y"] = 50
                    pos["height"] = 380 if target_preset == "upper_window" else 210
                else:
                    original_val = str(pos)
                    ov["position"] = {
                        "x": 60,
                        "y": 50,
                        "width": 960,
                        "height": 380 if target_preset == "upper_window" else 210,
                    }
                moved = True
                break

        if moved:
            return FixRecord(
                fix_id=f"fix_move_{issue.issue_id}",
                issue_id=issue.issue_id,
                action="MOVE_OVERLAY",
                target_element=str(target_id or "overlay"),
                original_value=original_val,
                corrected_value=target_preset,
                rationale="Relocated overlay to upper safe region to prevent collision with subtitles/face.",
            )
        return None

    def _fix_shorten_interval(
        self, edits: dict[str, Any], issue: QAIssue, video_duration: float
    ) -> FixRecord | None:
        """Clamp overlay end time so it does not exceed video duration."""
        target_id = issue.evidence.get("overlay_id")
        th_props = edits.setdefault("metadata", {}).setdefault("talking_head_props", {})
        th_overlays = th_props.get("overlays", [])
        top_overlays = edits.get("overlays", [])

        clamped = False
        original_end = None
        new_end = round(max(0.5, video_duration - 0.2), 3)

        for ov in th_overlays:
            curr_id = ov.get("id") or ov.get("asset_id")
            if curr_id == target_id:
                original_end = ov.get("out_seconds")
                ov["out_seconds"] = new_end
                clamped = True
                break

        for ov in top_overlays:
            curr_id = ov.get("asset_id") or ov.get("id")
            if curr_id == target_id:
                original_end = ov.get("end_seconds")
                ov["end_seconds"] = new_end
                clamped = True
                break

        if clamped:
            return FixRecord(
                fix_id=f"fix_shorten_{issue.issue_id}",
                issue_id=issue.issue_id,
                action="SHORTEN_INTERVAL",
                target_element=str(target_id or "overlay"),
                original_value=f"{original_end}s",
                corrected_value=f"{new_end}s",
                rationale=f"Clamped overlay duration to stay within total video duration ({video_duration}s).",
            )
        return None

    def _fix_retarget_crop(
        self, edits: dict[str, Any], issue: QAIssue
    ) -> FixRecord | None:
        """Clamp invalid crop coordinates to valid source dimensions [1920x1080]."""
        cuts = edits.get("cuts", [])
        th_props = edits.setdefault("metadata", {}).setdefault("talking_head_props", {})
        th_cuts = th_props.get("cuts", [])
        all_cuts = cuts + th_cuts

        src_w = 1920.0
        src_h = 1080.0
        fixed = False
        orig_crop = None
        new_crop = None

        for c in all_cuts:
            trans = c.get("transform", {})
            crop = trans.get("crop")
            if crop and isinstance(crop, dict):
                cx = float(crop.get("x", 0.0))
                cy = float(crop.get("y", 0.0))
                cw = float(crop.get("width", src_w))
                ch = float(crop.get("height", src_h))

                if cx < 0 or cy < 0 or (cx + cw) > src_w or (cy + ch) > src_h:
                    orig_crop = copy.deepcopy(crop)
                    # Safe clamp
                    safe_w = min(cw, src_w)
                    safe_h = min(ch, src_h)
                    safe_x = max(0.0, min(cx, src_w - safe_w))
                    safe_y = max(0.0, min(cy, src_h - safe_h))

                    crop["x"] = round(safe_x, 1)
                    crop["y"] = round(safe_y, 1)
                    crop["width"] = round(safe_w, 1)
                    crop["height"] = round(safe_h, 1)
                    new_crop = crop
                    fixed = True

        if fixed:
            return FixRecord(
                fix_id=f"fix_crop_{issue.issue_id}",
                issue_id=issue.issue_id,
                action="RETARGET_CROP",
                target_element="cut_transform_crop",
                original_value=str(orig_crop),
                corrected_value=str(new_crop),
                rationale="Clamped out-of-bounds crop rectangle to fit within 1920x1080 frame boundary.",
            )
        return None

    def _fix_adjust_caption(
        self, edits: dict[str, Any], issue: QAIssue
    ) -> FixRecord | None:
        """Clamp caption words per page and font size to safe presets."""
        th_props = edits.setdefault("metadata", {}).setdefault("talking_head_props", {})
        orig_words = th_props.get("wordsPerPage", 3)

        th_props["wordsPerPage"] = 3
        th_props["fontSize"] = 52

        sub_block = edits.setdefault("subtitles", {})
        sub_block["max_words_per_line"] = 3

        return FixRecord(
            fix_id=f"fix_caption_{issue.issue_id}",
            issue_id=issue.issue_id,
            action="ADJUST_CAPTION_POSITION",
            target_element="captions_config",
            original_value=f"{orig_words} words/page",
            corrected_value="3 words/page",
            rationale="Restricted caption density to max 3 words/page to avoid line wrapping and overlap.",
        )

    def _fix_suppress_redundant(
        self, edits: dict[str, Any], issue: QAIssue
    ) -> FixRecord | None:
        """Suppress secondary overlay when two overlays simultaneously occupy the same screen space."""
        id2 = issue.evidence.get("overlay_2")
        th_props = edits.setdefault("metadata", {}).setdefault("talking_head_props", {})
        th_overlays = th_props.get("overlays", [])
        top_overlays = edits.get("overlays", [])

        # Remove id2 from overlays
        if id2:
            th_props["overlays"] = [o for o in th_overlays if (o.get("id") or o.get("asset_id")) != id2]
            edits["overlays"] = [o for o in top_overlays if (o.get("asset_id") or o.get("id")) != id2]
            return FixRecord(
                fix_id=f"fix_suppress_{issue.issue_id}",
                issue_id=issue.issue_id,
                action="SUPPRESS_REDUNDANT_GRAPHIC",
                target_element=str(id2),
                original_value="active_overlay",
                corrected_value="suppressed",
                rationale=f"Suppressed redundant overlay '{id2}' to eliminate simultaneous collision.",
            )
        return None

    def _fix_scale_overlay(
        self, edits: dict[str, Any], issue: QAIssue
    ) -> FixRecord | None:
        """Scale down oversized overlay bounding boxes."""
        target_id = issue.evidence.get("overlay_id")
        top_overlays = edits.get("overlays", [])

        for ov in top_overlays:
            if (ov.get("asset_id") or ov.get("id")) == target_id:
                pos = ov.get("position", {})
                if isinstance(pos, dict):
                    orig_h = pos.get("height", 450)
                    pos["height"] = 380
                    pos["width"] = min(960, pos.get("width", 960))
                    return FixRecord(
                        fix_id=f"fix_scale_{issue.issue_id}",
                        issue_id=issue.issue_id,
                        action="SCALE_OVERLAY",
                        target_element=str(target_id),
                        original_value=f"height={orig_h}px",
                        corrected_value="height=380px",
                        rationale="Scaled down overlay height to stay within upper safe window.",
                    )
        return None

    def _fix_normalize_audio(
        self, edits: dict[str, Any], issue: QAIssue
    ) -> FixRecord | None:
        """Set audio normalization metadata in edit_decisions to prevent clipping."""
        audio_block = edits.setdefault("audio", {})
        orig_vol = audio_block.get("normalize", False)
        audio_block["normalize"] = True
        audio_block["target_peak_db"] = -1.5

        return FixRecord(
            fix_id=f"fix_audio_{issue.issue_id}",
            issue_id=issue.issue_id,
            action="NORMALIZE_AUDIO",
            target_element="audio_pipeline",
            original_value=f"normalize={orig_vol}",
            corrected_value="normalize=True, target_peak=-1.5dB",
            rationale="Configured true peak normalization (-1.5 dB) to eliminate digital clipping.",
        )
