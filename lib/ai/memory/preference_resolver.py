"""Intelligent Preference Resolver for OpenMontage (Phase 10).

Blends editorial decisions across the strict 4-tier decision priority hierarchy:
Tier 1: Explicit User Instruction in Prompt (Strict Highest Priority)
Tier 2: Source Video Constraints & Physical Boundaries
Tier 3: Approved Learned Preferences & Active Style Preset
Tier 4: System / Heuristic Defaults

Maintains decision provenance for every preference-influenced decision.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from lib.ai.memory.context_matcher import ContextMatcher
from lib.ai.memory.models import EditingPreference, PreferenceTier, StylePreset
from lib.ai.memory.preference_store import PreferenceStore

logger = logging.getLogger(__name__)


@dataclass
class AppliedPreferenceRecord:
    """Audit record indicating how a specific parameter was resolved."""

    parameter_key: str
    resolved_value: Any
    winning_tier: int  # 1 to 4
    winning_tier_name: str
    preference_id: Optional[str] = None
    preset_id: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolvedEditorialPlan:
    """Resolved editorial settings ready for consumption by AutonomousEditingPlanner."""

    # Zoom
    zoom_scale: float = 1.25
    zoom_intensity: str = "standard"  # subtle, standard, punchy, none
    zoom_frequency: str = "sparing"

    # Captions
    caption_font_family: str = "Inter, sans-serif"
    caption_font_size: int = 52
    caption_highlight_color: str = "#22D3EE"
    caption_background_color: str = "rgba(0, 0, 0, 0.65)"
    words_per_page: int = 4
    caption_preset: str = "word_highlight"

    # Pacing
    cut_aggressiveness: str = "balanced"
    min_pause_cut_duration: float = 0.8
    pacing_rest_interval: float = 2.5

    # Visual Overlays
    graphic_density: str = "medium"
    preferred_overlay_types: list[str] = field(default_factory=lambda: ["stat_card", "callout"])
    color_palette: dict[str, str] = field(
        default_factory=lambda: {
            "primary": "#2563EB",
            "accent": "#22D3EE",
            "background": "#FFFFFF",
        }
    )

    # Audio
    bgm_enabled: bool = True
    bgm_volume: float = 0.25

    # Audit Trail
    applied_records: list[AppliedPreferenceRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "zoom_scale": self.zoom_scale,
            "zoom_intensity": self.zoom_intensity,
            "zoom_frequency": self.zoom_frequency,
            "caption_font_family": self.caption_font_family,
            "caption_font_size": self.caption_font_size,
            "caption_highlight_color": self.caption_highlight_color,
            "caption_background_color": self.caption_background_color,
            "words_per_page": self.words_per_page,
            "caption_preset": self.caption_preset,
            "cut_aggressiveness": self.cut_aggressiveness,
            "min_pause_cut_duration": self.min_pause_cut_duration,
            "pacing_rest_interval": self.pacing_rest_interval,
            "graphic_density": self.graphic_density,
            "preferred_overlay_types": self.preferred_overlay_types,
            "color_palette": self.color_palette,
            "bgm_enabled": self.bgm_enabled,
            "bgm_volume": self.bgm_volume,
            "applied_records": [r.to_dict() for r in self.applied_records],
        }


class PreferenceResolver:
    """Resolves parameters by consulting user instructions, context matcher, and preference store."""

    ZOOM_SCALE_RE = re.compile(r"\b(1\.\d+)\s*x\s+zoom\b", re.IGNORECASE)
    NO_ZOOM_RE = re.compile(r"\b(?:no|zero|don'?t|without)\s+zooms?\b", re.IGNORECASE)
    SUBTLE_ZOOM_RE = re.compile(r"\b(?:subtle|gentle|slight)\s+zoom(?:s)?\b", re.IGNORECASE)
    PUNCHY_ZOOM_RE = re.compile(r"\b(?:punchy|aggressive|heavy|dramatic)\s+zoom(?:s)?\b", re.IGNORECASE)

    COLOR_RE_MAP = [
        (re.compile(r"\b(?:yellow|gold|amber)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#FACC15"),
        (re.compile(r"\b(?:green|emerald)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#10B981"),
        (re.compile(r"\b(?:cyan|blue|teal)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#22D3EE"),
        (re.compile(r"\b(?:red|crimson|coral)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#EF4444"),
        (re.compile(r"\b(?:purple|violet)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#A855F7"),
        (re.compile(r"\b(?:white)\s+(?:highlight|accent|captions?)\b", re.IGNORECASE), "#FFFFFF"),
    ]

    WORDS_PER_PAGE_RE = re.compile(r"\b(\d+)\s+words?\s+(?:per\s+(?:line|page|caption|group))\b", re.IGNORECASE)

    def __init__(
        self,
        store: Optional[PreferenceStore] = None,
        matcher: Optional[ContextMatcher] = None,
    ):
        self.store = store or PreferenceStore()
        self.matcher = matcher or ContextMatcher()

    def resolve_plan(
        self,
        user_prompt: str,
        video_metadata: dict[str, Any],
        enable_personalization: bool = True,
        active_preset: Optional[StylePreset] = None,
    ) -> ResolvedEditorialPlan:
        """Execute 4-tier resolution to construct an optimized editorial plan."""
        plan = ResolvedEditorialPlan()

        # Build normalized context dictionary
        width = video_metadata.get("width", 1920)
        height = video_metadata.get("height", 1080)
        target_aspect = "9:16" if height > width else "16:9"
        if "target_aspect" in video_metadata:
            target_aspect = video_metadata["target_aspect"]

        target_context = {
            "target_aspect": target_aspect,
            "video_category": video_metadata.get("category", "educational"),
            "speaking_pace": video_metadata.get("speaking_pace", "normal"),
            "graphic_purpose": video_metadata.get("graphic_purpose", "explain"),
        }

        # Check if personalization is globally enabled
        store_settings = self.store.get_settings()
        is_globally_enabled = store_settings.get("personalization_enabled", True)
        use_memory = enable_personalization and is_globally_enabled

        # Identify active preset if not explicitly passed
        if active_preset is None and use_memory:
            preset_id = store_settings.get("active_preset_id")
            if preset_id:
                active_preset = self.store.get_preset(preset_id)

        # --------------------------------------------------------------------
        # 1. RESOLVE ZOOM SCALE & INTENSITY
        # --------------------------------------------------------------------
        zoom_record = self._resolve_zoom(user_prompt, target_context, use_memory, active_preset)
        plan.zoom_scale = zoom_record.resolved_value
        if plan.zoom_scale <= 1.02:
            plan.zoom_intensity = "none"
        elif plan.zoom_scale <= 1.15:
            plan.zoom_intensity = "subtle"
        elif plan.zoom_scale >= 1.35:
            plan.zoom_intensity = "punchy"
        else:
            plan.zoom_intensity = "standard"
        plan.applied_records.append(zoom_record)

        # --------------------------------------------------------------------
        # 2. RESOLVE CAPTION HIGHLIGHT COLOR
        # --------------------------------------------------------------------
        color_record = self._resolve_caption_color(user_prompt, target_context, use_memory, active_preset)
        plan.caption_highlight_color = color_record.resolved_value
        plan.applied_records.append(color_record)

        # --------------------------------------------------------------------
        # 3. RESOLVE WORDS PER PAGE
        # --------------------------------------------------------------------
        wpp_record = self._resolve_words_per_page(user_prompt, target_context, use_memory, active_preset)
        plan.words_per_page = int(wpp_record.resolved_value)
        plan.applied_records.append(wpp_record)

        # --------------------------------------------------------------------
        # 4. RESOLVE CAPTION FONT & PRESET
        # --------------------------------------------------------------------
        font_record = self._resolve_caption_font(user_prompt, target_context, use_memory, active_preset)
        plan.caption_font_family = font_record.resolved_value
        plan.applied_records.append(font_record)

        # --------------------------------------------------------------------
        # 5. RESOLVE PACING / CUT AGGRESSIVENESS
        # --------------------------------------------------------------------
        pacing_record = self._resolve_pacing(user_prompt, target_context, use_memory, active_preset)
        plan.min_pause_cut_duration = float(pacing_record.resolved_value)
        plan.applied_records.append(pacing_record)

        # --------------------------------------------------------------------
        # 6. RESOLVE GRAPHIC DENSITY & OVERLAY TYPES
        # --------------------------------------------------------------------
        graphic_record = self._resolve_graphics(user_prompt, target_context, use_memory, active_preset)
        plan.preferred_overlay_types = graphic_record.resolved_value
        plan.applied_records.append(graphic_record)

        return plan

    def _resolve_zoom(
        self,
        user_prompt: str,
        target_context: dict[str, Any],
        use_memory: bool,
        active_preset: Optional[StylePreset],
    ) -> AppliedPreferenceRecord:
        # Tier 1: Explicit Instruction
        match = self.ZOOM_SCALE_RE.search(user_prompt)
        if match:
            val = float(match.group(1))
            return AppliedPreferenceRecord(
                parameter_key="zoom_scale",
                resolved_value=val,
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason=f"User prompt explicitly specified '{match.group(0)}'.",
            )
        if self.NO_ZOOM_RE.search(user_prompt):
            return AppliedPreferenceRecord(
                parameter_key="zoom_scale",
                resolved_value=1.00,
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason="User prompt requested no camera zooms.",
            )
        if self.SUBTLE_ZOOM_RE.search(user_prompt):
            return AppliedPreferenceRecord(
                parameter_key="zoom_scale",
                resolved_value=1.10,
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason="User prompt requested subtle zooms.",
            )
        if self.PUNCHY_ZOOM_RE.search(user_prompt):
            return AppliedPreferenceRecord(
                parameter_key="zoom_scale",
                resolved_value=1.40,
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason="User prompt requested punchy zooms.",
            )

        # Tier 3: User Learned Preference (if enabled)
        if use_memory:
            pref = self._find_compatible_preference("zoom_scale", target_context)
            if pref:
                return AppliedPreferenceRecord(
                    parameter_key="zoom_scale",
                    resolved_value=float(pref.preferred_value),
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="learned_preference",
                    preference_id=pref.preference_id,
                    reason=f"Applied approved editing preference '{pref.preference_id}' (value={pref.preferred_value}).",
                )
            if active_preset:
                return AppliedPreferenceRecord(
                    parameter_key="zoom_scale",
                    resolved_value=active_preset.zoom_scale,
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="style_preset",
                    preset_id=active_preset.preset_id,
                    reason=f"Applied active style preset '{active_preset.title}' (zoom_scale={active_preset.zoom_scale}).",
                )

        # Tier 4: System Default
        return AppliedPreferenceRecord(
            parameter_key="zoom_scale",
            resolved_value=1.25,
            winning_tier=PreferenceTier.TIER_4_SYSTEM_DEFAULT.value,
            winning_tier_name="system_default",
            reason="Standard OpenMontage baseline 1.25x zoom.",
        )

    def _resolve_caption_color(
        self,
        user_prompt: str,
        target_context: dict[str, Any],
        use_memory: bool,
        active_preset: Optional[StylePreset],
    ) -> AppliedPreferenceRecord:
        # Tier 1: Explicit Instruction
        for pattern, hex_code in self.COLOR_RE_MAP:
            if pattern.search(user_prompt):
                return AppliedPreferenceRecord(
                    parameter_key="highlight_color",
                    resolved_value=hex_code,
                    winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                    winning_tier_name="explicit_instruction",
                    reason=f"User prompt explicitly requested {hex_code} highlight color.",
                )

        # Tier 3: Learned Preference
        if use_memory:
            pref = self._find_compatible_preference("caption_highlight_color", target_context) or \
                   self._find_compatible_preference("highlight_color", target_context)
            if pref:
                return AppliedPreferenceRecord(
                    parameter_key="highlight_color",
                    resolved_value=str(pref.preferred_value),
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="learned_preference",
                    preference_id=pref.preference_id,
                    reason=f"Applied approved editing preference '{pref.preference_id}' (color={pref.preferred_value}).",
                )
            if active_preset and active_preset.caption_highlight_color:
                return AppliedPreferenceRecord(
                    parameter_key="highlight_color",
                    resolved_value=active_preset.caption_highlight_color,
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="style_preset",
                    preset_id=active_preset.preset_id,
                    reason=f"Applied active style preset '{active_preset.title}' highlight color.",
                )

        # Tier 4: System Default
        return AppliedPreferenceRecord(
            parameter_key="highlight_color",
            resolved_value="#22D3EE",
            winning_tier=PreferenceTier.TIER_4_SYSTEM_DEFAULT.value,
            winning_tier_name="system_default",
            reason="Default cyan highlight color (#22D3EE).",
        )

    def _resolve_words_per_page(
        self,
        user_prompt: str,
        target_context: dict[str, Any],
        use_memory: bool,
        active_preset: Optional[StylePreset],
    ) -> AppliedPreferenceRecord:
        # Tier 1: Explicit
        match = self.WORDS_PER_PAGE_RE.search(user_prompt)
        if match:
            return AppliedPreferenceRecord(
                parameter_key="words_per_page",
                resolved_value=int(match.group(1)),
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason=f"User prompt explicitly requested {match.group(1)} words per page.",
            )

        # Tier 3: Learned Preference
        if use_memory:
            pref = self._find_compatible_preference("words_per_page", target_context)
            if pref:
                return AppliedPreferenceRecord(
                    parameter_key="words_per_page",
                    resolved_value=int(pref.preferred_value),
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="learned_preference",
                    preference_id=pref.preference_id,
                    reason=f"Applied approved editing preference '{pref.preference_id}' ({pref.preferred_value} words).",
                )
            if active_preset:
                return AppliedPreferenceRecord(
                    parameter_key="words_per_page",
                    resolved_value=active_preset.words_per_page,
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="style_preset",
                    preset_id=active_preset.preset_id,
                    reason=f"Applied style preset '{active_preset.title}' words per page ({active_preset.words_per_page}).",
                )

        # Tier 4: System Default
        return AppliedPreferenceRecord(
            parameter_key="words_per_page",
            resolved_value=4,
            winning_tier=PreferenceTier.TIER_4_SYSTEM_DEFAULT.value,
            winning_tier_name="system_default",
            reason="Standard 4 words per page.",
        )

    def _resolve_caption_font(
        self,
        user_prompt: str,
        target_context: dict[str, Any],
        use_memory: bool,
        active_preset: Optional[StylePreset],
    ) -> AppliedPreferenceRecord:
        # Check prompt for specific fonts
        if "montserrat" in user_prompt.lower():
            return AppliedPreferenceRecord(
                parameter_key="caption_font_family",
                resolved_value="Montserrat, sans-serif",
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason="User requested Montserrat font.",
            )
        if "jetbrains" in user_prompt.lower() or "mono" in user_prompt.lower():
            return AppliedPreferenceRecord(
                parameter_key="caption_font_family",
                resolved_value="JetBrains Mono, monospace",
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason="User requested monospace font.",
            )

        if use_memory:
            pref = self._find_compatible_preference("caption_font_family", target_context)
            if pref:
                return AppliedPreferenceRecord(
                    parameter_key="caption_font_family",
                    resolved_value=str(pref.preferred_value),
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="learned_preference",
                    preference_id=pref.preference_id,
                    reason=f"Applied approved font preference '{pref.preferred_value}'.",
                )
            if active_preset and active_preset.caption_font_family:
                return AppliedPreferenceRecord(
                    parameter_key="caption_font_family",
                    resolved_value=active_preset.caption_font_family,
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="style_preset",
                    preset_id=active_preset.preset_id,
                    reason=f"Applied style preset font '{active_preset.caption_font_family}'.",
                )

        return AppliedPreferenceRecord(
            parameter_key="caption_font_family",
            resolved_value="Inter, sans-serif",
            winning_tier=PreferenceTier.TIER_4_SYSTEM_DEFAULT.value,
            winning_tier_name="system_default",
            reason="Standard Inter typography.",
        )

    def _resolve_pacing(
        self,
        user_prompt: str,
        target_context: dict[str, Any],
        use_memory: bool,
        active_preset: Optional[StylePreset],
    ) -> AppliedPreferenceRecord:
        prompt_lower = user_prompt.lower()
        if "fast" in prompt_lower or "aggressive" in prompt_lower or "jump cuts" in prompt_lower:
            return AppliedPreferenceRecord(
                parameter_key="min_pause_cut_duration",
                resolved_value=0.55,
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason="User requested fast-paced cutting.",
            )
        if "slow" in prompt_lower or "calm" in prompt_lower or "relaxed" in prompt_lower:
            return AppliedPreferenceRecord(
                parameter_key="min_pause_cut_duration",
                resolved_value=1.5,
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason="User requested relaxed pacing.",
            )

        if use_memory:
            pref = self._find_compatible_preference("min_pause_cut_duration", target_context)
            if pref:
                return AppliedPreferenceRecord(
                    parameter_key="min_pause_cut_duration",
                    resolved_value=float(pref.preferred_value),
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="learned_preference",
                    preference_id=pref.preference_id,
                    reason=f"Applied approved pacing preference ({pref.preferred_value}s pause threshold).",
                )
            if active_preset:
                return AppliedPreferenceRecord(
                    parameter_key="min_pause_cut_duration",
                    resolved_value=active_preset.min_pause_cut_duration,
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="style_preset",
                    preset_id=active_preset.preset_id,
                    reason=f"Applied preset '{active_preset.title}' pacing ({active_preset.min_pause_cut_duration}s).",
                )

        return AppliedPreferenceRecord(
            parameter_key="min_pause_cut_duration",
            resolved_value=0.8,
            winning_tier=PreferenceTier.TIER_4_SYSTEM_DEFAULT.value,
            winning_tier_name="system_default",
            reason="Balanced 0.8s pause cutting threshold.",
        )

    def _resolve_graphics(
        self,
        user_prompt: str,
        target_context: dict[str, Any],
        use_memory: bool,
        active_preset: Optional[StylePreset],
    ) -> AppliedPreferenceRecord:
        prompt_lower = user_prompt.lower()
        if "no graphics" in prompt_lower or "no overlays" in prompt_lower:
            return AppliedPreferenceRecord(
                parameter_key="preferred_overlay_types",
                resolved_value=[],
                winning_tier=PreferenceTier.TIER_1_EXPLICIT_INSTRUCTION.value,
                winning_tier_name="explicit_instruction",
                reason="User requested zero graphic overlays.",
            )

        if use_memory:
            pref = self._find_compatible_preference("preferred_overlay_types", target_context)
            if pref:
                val = pref.preferred_value if isinstance(pref.preferred_value, list) else [pref.preferred_value]
                return AppliedPreferenceRecord(
                    parameter_key="preferred_overlay_types",
                    resolved_value=val,
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="learned_preference",
                    preference_id=pref.preference_id,
                    reason=f"Applied approved overlay preference {val}.",
                )
            if active_preset:
                return AppliedPreferenceRecord(
                    parameter_key="preferred_overlay_types",
                    resolved_value=active_preset.preferred_overlay_types,
                    winning_tier=PreferenceTier.TIER_3_USER_LEARNED.value,
                    winning_tier_name="style_preset",
                    preset_id=active_preset.preset_id,
                    reason=f"Applied preset overlay types {active_preset.preferred_overlay_types}.",
                )

        return AppliedPreferenceRecord(
            parameter_key="preferred_overlay_types",
            resolved_value=["stat_card", "callout"],
            winning_tier=PreferenceTier.TIER_4_SYSTEM_DEFAULT.value,
            winning_tier_name="system_default",
            reason="Standard default overlay types (stat_card, callout).",
        )

    def _find_compatible_preference(
        self,
        parameter_key: str,
        target_context: dict[str, Any],
    ) -> Optional[EditingPreference]:
        """Query store for active preferences matching the parameter key and validate context compatibility."""
        candidates = [
            p for p in self.store.list_preferences(enabled_only=True)
            if p.parameter_key == parameter_key
        ]
        if not candidates:
            return None

        compatible: list[tuple[EditingPreference, float]] = []
        for cand in candidates:
            match_res = self.matcher.evaluate_match(cand, target_context)
            if match_res.is_compatible:
                compatible.append((cand, match_res.match_score))

        if not compatible:
            return None

        # Sort by match score and preference confidence/times_approved
        compatible.sort(key=lambda item: (item[1], item[0].confidence, item[0].times_approved), reverse=True)
        return compatible[0][0]
