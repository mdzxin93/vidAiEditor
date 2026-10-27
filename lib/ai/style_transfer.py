"""Intelligent Style Transfer & Conflict Resolution Matrix (Phase 6).

Implements the 4-tier decision priority hierarchy:
1. Explicit user editing instructions (Strict Highest Priority)
2. Source-video context, speech integrity & continuity
3. Reference editing-style preferences (from StyleProfile)
4. Default OpenMontage editorial presets

Translates a reference StyleProfile into concrete, content-aware editing parameters
for the AutonomousEditingPlanner, resolving conflicts and tracking complete provenance.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from lib.ai.style_analyzer import StyleProfile

logger = logging.getLogger(__name__)


@dataclass
class ConflictResolutionRecord:
    """Audit record for a resolved editorial preference conflict."""
    parameter: str
    chosen_value: Any
    reference_value: Any
    winning_tier: int  # 1: User Instruction, 2: Source Context, 3: Reference Style, 4: Default
    winning_tier_name: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TransferredStyleDirectives:
    """Concrete editorial rules synthesized from style transfer and conflict resolution."""
    # Pacing
    pacing_category: str = "moderate"
    min_pause_cut_duration: float = 0.8
    rest_interval_seconds: float = 2.5
    target_shot_duration: float = 3.5

    # Camera & Zoom
    zoom_frequency: str = "sparing"
    zoom_scale: float = 1.25
    max_zooms_allowed: int = 2

    # Captions
    words_per_page: int = 4
    caption_placement: str = "bottom-center"
    caption_font_preset: str = "modern_sans"
    caption_font_size: int = 52
    caption_font_family: str = "Inter, sans-serif"
    highlight_color: str = "#22D3EE"
    caption_color: str = "#FFFFFF"
    caption_background_color: str = "rgba(0, 0, 0, 0.65)"

    # Overlays & Graphics
    graphic_density: str = "medium"
    max_overlays_total: int = 2
    overlay_accent_color: str = "#22D3EE"
    overlay_background_color: str = "rgba(15, 23, 42, 0.92)"
    preferred_overlay_position: str = "upper_third"

    # Audio
    bgm_enabled: bool = True
    bgm_volume_target: float = 0.25

    # Conflict resolutions audit trail
    conflict_resolutions: list[ConflictResolutionRecord] = field(default_factory=list)


class StyleTransferEngine:
    """Applies reference style intelligence with strict 4-tier conflict resolution."""

    # Regex indicators for explicit user instructions overriding style
    FEW_ZOOM_PATTERNS = [
        re.compile(r"\b(?:no|few|little|rare|sparing|zero|minimal|don'?t|without)\s+zooms?\b", re.IGNORECASE),
        re.compile(r"\bzoom(?:s)?\s+(?:sparingly|rarely|minimally|very few)\b", re.IGNORECASE),
        re.compile(r"\bkeep\s+camera\s+(?:static|still|locked)\b", re.IGNORECASE),
    ]

    FREQUENT_ZOOM_PATTERNS = [
        re.compile(r"\b(?:frequent|many|lots of|more|heavy|dynamic|punch in)\s+zooms?\b", re.IGNORECASE),
        re.compile(r"\bzoom\s+(?:frequently|often|heavily)\b", re.IGNORECASE),
    ]

    FAST_PACING_PATTERNS = [
        re.compile(r"\b(?:fast|rapid|quick|high energy|snappy|punchy|jump cuts)\b", re.IGNORECASE),
        re.compile(r"\bcut\s+(?:every|all)\s+pause\b", re.IGNORECASE),
    ]

    SLOW_PACING_PATTERNS = [
        re.compile(r"\b(?:slow|deliberate|relaxed|calm|gentle|cinematic|unrushed)\b", re.IGNORECASE),
        re.compile(r"\bkeep\s+(?:all|natural)\s+pauses\b", re.IGNORECASE),
    ]

    NO_GRAPHICS_PATTERNS = [
        re.compile(r"\b(?:no|without|zero|remove|don'?t add)\s+(?:motion graphics|overlays|cards|graphics)\b", re.IGNORECASE),
        re.compile(r"\bclean\s+video\s+only\b", re.IGNORECASE),
    ]

    COLOR_OVERRIDE_PATTERNS = [
        (re.compile(r"\b(?:yellow|gold|amber)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#FACC15"),
        (re.compile(r"\b(?:green|emerald)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#10B981"),
        (re.compile(r"\b(?:cyan|blue|teal)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#22D3EE"),
        (re.compile(r"\b(?:red|crimson|coral)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#EF4444"),
        (re.compile(r"\b(?:purple|violet)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#A855F7"),
        (re.compile(r"\b(?:white)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#FFFFFF"),
    ]

    WORDS_PER_LINE_PATTERNS = [
        re.compile(r"\b(\d+)\s+words?\s+(?:per\s+(?:line|page|caption|group))\b", re.IGNORECASE),
    ]

    ZOOM_SCALE_PATTERNS = [
        re.compile(r"\b(1\.\d+)\s*x\s+zoom\b", re.IGNORECASE),
    ]

    def resolve_style_directives(
        self,
        user_instruction: str,
        style_profile: StyleProfile | None,
        source_metadata: dict[str, Any],
    ) -> TransferredStyleDirectives:
        """Apply 4-tier hierarchy to determine active editorial parameters."""
        directives = TransferredStyleDirectives()
        prompt_lower = user_instruction.lower()
        source_dur = source_metadata.get("duration", 20.0)

        # ---------------------------------------------------------------------
        # 1. RESOLVE CAMERA & ZOOM FREQUENCY
        # ---------------------------------------------------------------------
        ref_zoom_freq = style_profile.zoom_frequency if style_profile else "sparing"
        ref_zoom_scale = style_profile.zoom_scale if style_profile else 1.25

        # Check Tier 1 (Explicit User Instruction)
        user_wants_few_zooms = any(p.search(user_instruction) for p in self.FEW_ZOOM_PATTERNS)
        user_wants_frequent_zooms = any(p.search(user_instruction) for p in self.FREQUENT_ZOOM_PATTERNS)
        scale_match = self.ZOOM_SCALE_PATTERNS[0].search(user_instruction)

        if user_wants_few_zooms:
            directives.zoom_frequency = "sparing"
            directives.max_zooms_allowed = 1
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="zoom_frequency",
                    chosen_value="sparing (max 1 zoom)",
                    reference_value=ref_zoom_freq,
                    winning_tier=1,
                    winning_tier_name="user_instruction",
                    reason=f"Explicit user instruction prioritized over reference style '{ref_zoom_freq}' zoom preference",
                )
            )
        elif user_wants_frequent_zooms:
            directives.zoom_frequency = "frequent"
            directives.max_zooms_allowed = 4
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="zoom_frequency",
                    chosen_value="frequent (max 4 zooms)",
                    reference_value=ref_zoom_freq,
                    winning_tier=1,
                    winning_tier_name="user_instruction",
                    reason="Explicit user instruction requested frequent/dynamic punch-in zooms",
                )
            )
        elif source_dur < 10.0:
            # Tier 2: Source context limit for short video
            directives.zoom_frequency = "sparing"
            directives.max_zooms_allowed = 1
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="zoom_frequency",
                    chosen_value="sparing (max 1 zoom)",
                    reference_value=ref_zoom_freq,
                    winning_tier=2,
                    winning_tier_name="source_context",
                    reason=f"Short source duration ({round(source_dur, 1)}s) restricts zoom count to preserve viewer stability",
                )
            )
        elif style_profile is not None:
            # Tier 3: Reference Style Profile
            directives.zoom_frequency = ref_zoom_freq
            directives.max_zooms_allowed = 3 if ref_zoom_freq == "frequent" else 2 if ref_zoom_freq == "moderate" else 1
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="zoom_frequency",
                    chosen_value=ref_zoom_freq,
                    reference_value=ref_zoom_freq,
                    winning_tier=3,
                    winning_tier_name="reference_style",
                    reason=f"Adopted reference video camera zoom tendency '{ref_zoom_freq}' (no user conflict detected)",
                )
            )
        else:
            # Tier 4: Default
            directives.zoom_frequency = "sparing"
            directives.max_zooms_allowed = 2

        # Zoom Scale
        if scale_match:
            chosen_scale = float(scale_match.group(1))
            directives.zoom_scale = chosen_scale
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="zoom_scale",
                    chosen_value=chosen_scale,
                    reference_value=ref_zoom_scale,
                    winning_tier=1,
                    winning_tier_name="user_instruction",
                    reason=f"Explicit zoom scale '{chosen_scale}x' requested in user prompt",
                )
            )
        elif style_profile is not None:
            directives.zoom_scale = ref_zoom_scale

        # ---------------------------------------------------------------------
        # 2. RESOLVE PACING & PAUSE CUTTING
        # ---------------------------------------------------------------------
        ref_pacing = style_profile.pacing if style_profile else "moderate"
        ref_avg_shot = style_profile.average_shot_duration_sec if style_profile else 3.5

        user_wants_fast = any(p.search(user_instruction) for p in self.FAST_PACING_PATTERNS)
        user_wants_slow = any(p.search(user_instruction) for p in self.SLOW_PACING_PATTERNS)

        if user_wants_fast:
            directives.pacing_category = "fast"
            directives.min_pause_cut_duration = 0.55
            directives.rest_interval_seconds = 1.8
            directives.target_shot_duration = 2.2
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="pacing",
                    chosen_value="fast (0.55s cut threshold, 1.8s rest)",
                    reference_value=ref_pacing,
                    winning_tier=1,
                    winning_tier_name="user_instruction",
                    reason="Explicit user instruction for rapid/snappy pacing",
                )
            )
        elif user_wants_slow:
            directives.pacing_category = "deliberate"
            directives.min_pause_cut_duration = 1.10
            directives.rest_interval_seconds = 3.5
            directives.target_shot_duration = 6.0
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="pacing",
                    chosen_value="deliberate (1.1s cut threshold, 3.5s rest)",
                    reference_value=ref_pacing,
                    winning_tier=1,
                    winning_tier_name="user_instruction",
                    reason="Explicit user instruction for calm/unrushed pacing",
                )
            )
        elif style_profile is not None:
            directives.pacing_category = ref_pacing
            directives.target_shot_duration = ref_avg_shot
            if ref_pacing == "fast":
                directives.min_pause_cut_duration = 0.60
                directives.rest_interval_seconds = 2.0
            elif ref_pacing == "deliberate":
                directives.min_pause_cut_duration = 1.00
                directives.rest_interval_seconds = 3.2
            else:
                directives.min_pause_cut_duration = 0.80
                directives.rest_interval_seconds = 2.5
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="pacing",
                    chosen_value=f"{ref_pacing} ({directives.min_pause_cut_duration}s pause cut)",
                    reference_value=ref_pacing,
                    winning_tier=3,
                    winning_tier_name="reference_style",
                    reason=f"Transferring observable reference pacing rhythm ({ref_pacing}, avg shot {ref_avg_shot}s)",
                )
            )
        else:
            directives.pacing_category = "moderate"
            directives.min_pause_cut_duration = 0.80
            directives.rest_interval_seconds = 2.5
            directives.target_shot_duration = 3.5

        # ---------------------------------------------------------------------
        # 3. RESOLVE CAPTION TYPOGRAPHY & COLOR PALETTE
        # ---------------------------------------------------------------------
        ref_words_per_group = style_profile.words_per_line if style_profile else 4
        ref_accent = style_profile.accent_color if style_profile else "#22D3EE"
        ref_primary = style_profile.primary_color if style_profile else "#FFFFFF"
        ref_bg = style_profile.background_color if style_profile else "#0F172A"

        # Check explicit color override in prompt (Tier 1)
        explicit_color = None
        for pat, hex_col in self.COLOR_OVERRIDE_PATTERNS:
            if pat.search(user_instruction):
                explicit_color = hex_col
                break

        if explicit_color:
            directives.highlight_color = explicit_color
            directives.overlay_accent_color = explicit_color
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="highlight_color",
                    chosen_value=explicit_color,
                    reference_value=ref_accent,
                    winning_tier=1,
                    winning_tier_name="user_instruction",
                    reason=f"Explicit highlight color '{explicit_color}' requested by user",
                )
            )
        elif style_profile is not None:
            # Transfer reference accent
            directives.highlight_color = ref_accent
            directives.overlay_accent_color = ref_accent
            directives.caption_color = ref_primary
            directives.caption_background_color = "rgba(0, 0, 0, 0.65)" if ref_bg != "#FFFFFF" else "rgba(255, 255, 255, 0.85)"
            directives.caption_font_preset = getattr(style_profile, "captions_typography", {}).get("font_preset", "modern_sans")
            directives.caption_font_size = getattr(style_profile, "captions_typography", {}).get("font_size", 52)
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="highlight_color",
                    chosen_value=ref_accent,
                    reference_value=ref_accent,
                    winning_tier=3,
                    winning_tier_name="reference_style",
                    reason=f"Adopted reference video accent palette '{ref_accent}'",
                )
            )
        else:
            directives.highlight_color = "#22D3EE"
            directives.overlay_accent_color = "#22D3EE"

        # Words per line
        words_match = self.WORDS_PER_LINE_PATTERNS[0].search(user_instruction)
        if words_match:
            user_words = int(words_match.group(1))
            directives.words_per_page = max(1, min(10, user_words))
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="words_per_page",
                    chosen_value=directives.words_per_page,
                    reference_value=ref_words_per_group,
                    winning_tier=1,
                    winning_tier_name="user_instruction",
                    reason=f"Explicit word count per page ({user_words}) specified in prompt",
                )
            )
        elif style_profile is not None:
            directives.words_per_page = ref_words_per_group
        else:
            directives.words_per_page = 4

        # ---------------------------------------------------------------------
        # 4. RESOLVE MOTION GRAPHICS DENSITY
        # ---------------------------------------------------------------------
        ref_density = style_profile.graphic_density if style_profile else "medium"
        user_no_graphics = any(p.search(user_instruction) for p in self.NO_GRAPHICS_PATTERNS)

        if user_no_graphics:
            directives.graphic_density = "low"
            directives.max_overlays_total = 0
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="graphic_density",
                    chosen_value="disabled (0 overlays)",
                    reference_value=ref_density,
                    winning_tier=1,
                    winning_tier_name="user_instruction",
                    reason="Explicit user instruction suppressed motion graphics overlays",
                )
            )
        elif style_profile is not None:
            directives.graphic_density = ref_density
            directives.max_overlays_total = 3 if ref_density in ("high", "dense") else 1 if ref_density == "low" else 2
            directives.conflict_resolutions.append(
                ConflictResolutionRecord(
                    parameter="graphic_density",
                    chosen_value=f"{ref_density} (max {directives.max_overlays_total} overlays)",
                    reference_value=ref_density,
                    winning_tier=3,
                    winning_tier_name="reference_style",
                    reason=f"Adopted reference motion graphic density '{ref_density}'",
                )
            )
        else:
            directives.graphic_density = "medium"
            directives.max_overlays_total = 2

        return directives
