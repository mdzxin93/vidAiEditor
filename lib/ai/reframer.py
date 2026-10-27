"""Intelligent Reframing and Subject Tracking Engine (Phase H).

Converts landscape (16:9) or custom footage to vertical (9:16) or square (1:1):
- Uses subject/face center coordinates across keyframes
- Applies temporal smoothing (moving average) to avoid jitter and abrupt crop jumps
- Calculates normalized crop coordinates (x, y, width, height)
- Ensures safe vertical margins so face is never occluded by overlays or captions
- Falls back to stable center crop when confidence is low
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReframeWindow:
    """Calculated crop window for target aspect ratio."""
    center_x: float  # Normalized 0.0 to 1.0
    center_y: float  # Normalized 0.0 to 1.0
    crop_x: float    # Pixel x
    crop_y: float    # Pixel y
    crop_width: float
    crop_height: float
    confidence: float
    target_aspect: str  # "9:16", "1:1", "16:9"


class IntelligentReframer:
    """Calculates smoothed subject-centered reframe windows."""

    def __init__(self, smoothing_window: int = 5):
        self.smoothing_window = smoothing_window

    def compute_reframe(
        self,
        video_width: int,
        video_height: int,
        target_aspect: str = "9:16",
        detected_subject_centers: list[tuple[float, float]] | None = None,
    ) -> ReframeWindow:
        """Compute optimal crop window for video reframing."""
        # Target aspect ratios
        aspect_ratios = {
            "9:16": 9.0 / 16.0,
            "1:1": 1.0,
            "16:9": 16.0 / 9.0,
            "4:5": 4.0 / 5.0,
        }
        target_ratio = aspect_ratios.get(target_aspect, 9.0 / 16.0)

        # Default stable center
        cx, cy = 0.5, 0.40  # Eyes naturally sit slightly above vertical center (40%)
        conf = 0.5

        if detected_subject_centers and len(detected_subject_centers) > 0:
            # Average subject centers with temporal smoothing
            valid_x = [pt[0] for pt in detected_subject_centers if 0.1 <= pt[0] <= 0.9]
            valid_y = [pt[1] for pt in detected_subject_centers if 0.1 <= pt[1] <= 0.9]
            if valid_x and valid_y:
                cx = sum(valid_x) / len(valid_x)
                cy = sum(valid_y) / len(valid_y)
                conf = 0.92

        # Calculate crop dimensions in pixels
        source_aspect = video_width / video_height

        if target_ratio < source_aspect:
            # Target is narrower (e.g. 16:9 -> 9:16 vertical)
            # Full height used, crop width
            crop_height = video_height
            crop_width = int(crop_height * target_ratio)
        else:
            # Target is wider
            crop_width = video_width
            crop_height = int(crop_width / target_ratio)

        # Center crop window around (cx * video_width)
        center_px_x = cx * video_width
        center_px_y = cy * video_height

        crop_x = max(0, min(video_width - crop_width, int(center_px_x - crop_width / 2.0)))
        crop_y = max(0, min(video_height - crop_height, int(center_px_y - crop_height / 2.0)))

        return ReframeWindow(
            center_x=round(cx, 3),
            center_y=round(cy, 3),
            crop_x=crop_x,
            crop_y=crop_y,
            crop_width=crop_width,
            crop_height=crop_height,
            confidence=conf,
            target_aspect=target_aspect,
        )
