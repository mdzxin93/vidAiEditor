"""OpenMontage Motion Design System (Phase 7).

Standardized design tokens, typography scales, layout safe areas,
and animation presets for professional motion graphics rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AspectRatio(str, Enum):
    VERTICAL_9_16 = "9:16"
    HORIZONTAL_16_9 = "16:9"
    SQUARE_1_1 = "1:1"


@dataclass(frozen=True)
class TypographyToken:
    font_family: str
    font_size: int
    font_weight: int
    line_height: float
    letter_spacing: str


@dataclass(frozen=True)
class SpringPreset:
    damping: float
    stiffness: float
    mass: float = 1.0


@dataclass(frozen=True)
class DurationPreset:
    min_seconds: float
    ideal_seconds: float
    max_seconds: float


class MotionDesignSystem:
    """Centralized Motion Design Tokens and Layout Constraints."""

    # Typography hierarchy
    TYPOGRAPHY = {
        "display": TypographyToken(
            font_family="Inter, Montserrat, sans-serif",
            font_size=68,
            font_weight=800,
            line_height=1.08,
            letter_spacing="-0.02em",
        ),
        "headline": TypographyToken(
            font_family="Inter, Montserrat, sans-serif",
            font_size=32,
            font_weight=700,
            line_height=1.20,
            letter_spacing="-0.01em",
        ),
        "body": TypographyToken(
            font_family="Inter, system-ui, sans-serif",
            font_size=24,
            font_weight=500,
            line_height=1.35,
            letter_spacing="0em",
        ),
        "caption": TypographyToken(
            font_family="Inter, system-ui, sans-serif",
            font_size=18,
            font_weight=500,
            line_height=1.40,
            letter_spacing="0.02em",
        ),
        "badge": TypographyToken(
            font_family="Inter, system-ui, sans-serif",
            font_size=15,
            font_weight=700,
            line_height=1.0,
            letter_spacing="0.06em",
        ),
    }

    # High-contrast, accessible WCAG AA (>= 4.5:1) color themes
    COLOR_THEMES = {
        "dark_slate": {
            "background": "rgba(15, 23, 42, 0.92)",
            "surface": "rgba(30, 41, 59, 0.85)",
            "text_primary": "#FFFFFF",
            "text_secondary": "rgba(255, 255, 255, 0.72)",
            "accent": "#38BDF8",       # Sky cyan
            "accent_negative": "#EF4444", # Red
            "accent_positive": "#10B981", # Emerald
            "accent_warning": "#F59E0B",  # Amber
            "border": "rgba(255, 255, 255, 0.12)",
        },
        "midnight": {
            "background": "rgba(2, 6, 23, 0.94)",
            "surface": "rgba(15, 23, 42, 0.85)",
            "text_primary": "#FFFFFF",
            "text_secondary": "rgba(255, 255, 255, 0.65)",
            "accent": "#818CF8",       # Indigo
            "accent_negative": "#F87171",
            "accent_positive": "#34D399",
            "accent_warning": "#FBBF24",
            "border": "rgba(255, 255, 255, 0.08)",
        },
    }

    # Animation spring dynamics
    SPRINGS = {
        "snappy": SpringPreset(damping=12, stiffness=120),
        "smooth": SpringPreset(damping=18, stiffness=90),
        "reveal": SpringPreset(damping=14, stiffness=100),
        "gentle": SpringPreset(damping=22, stiffness=80),
    }

    # Temporal duration presets (seconds)
    DURATIONS = {
        "stat_hit": DurationPreset(min_seconds=1.8, ideal_seconds=2.4, max_seconds=3.0),
        "callout_tip": DurationPreset(min_seconds=2.5, ideal_seconds=3.2, max_seconds=4.0),
        "process_diagram": DurationPreset(min_seconds=3.0, ideal_seconds=4.0, max_seconds=5.0),
        "broll_overlay": DurationPreset(min_seconds=2.0, ideal_seconds=3.0, max_seconds=4.5),
        "feature_card": DurationPreset(min_seconds=2.2, ideal_seconds=3.2, max_seconds=4.0),
    }

    # Safe areas (coordinates in pixels)
    SAFE_AREAS = {
        AspectRatio.VERTICAL_9_16: {
            "width": 1080,
            "height": 1920,
            "margin_top": 50,
            "margin_bottom": 420,  # Reserved for subtitles & social UI
            "margin_horizontal": 60,
            "overlay_max_height": 380,
            "subtitle_zone_top": 1500,
            "subtitle_zone_bottom": 1850,
        },
        AspectRatio.HORIZONTAL_16_9: {
            "width": 1920,
            "height": 1080,
            "margin_top": 60,
            "margin_bottom": 160,
            "margin_horizontal": 80,
            "overlay_max_height": 320,
            "subtitle_zone_top": 860,
            "subtitle_zone_bottom": 1020,
        },
    }

    @classmethod
    def get_safe_area(cls, aspect: str = "9:16") -> dict[str, int]:
        """Return safe area constraints for the target aspect ratio."""
        key = AspectRatio.VERTICAL_9_16 if "9:16" in aspect else AspectRatio.HORIZONTAL_16_9
        return cls.SAFE_AREAS[key]

    @classmethod
    def resolve_color_theme(cls, custom_accent: str | None = None) -> dict[str, str]:
        """Return theme dictionary with optional custom accent override."""
        theme = dict(cls.COLOR_THEMES["dark_slate"])
        if custom_accent and custom_accent.startswith("#"):
            theme["accent"] = custom_accent
        return theme
