"""Data Models for OpenMontage Intelligent Editing Memory & Personalization (Phase 10).

Defines:
- EditingPreferenceCategory: Semantic domain of an editing preference
- ApprovalStatus: Explicit user decision on whether a correction becomes a permanent preference
- PreferenceTier: Hierarchy level (Explicit Instruction > Project Override > User Learned > Reference Style > System Default)
- EditingPreference: Persisted user preference with context constraints, confidence, and audit trail
- CorrectionRecord: Immutable record of a user modification to an AI proposal
- StylePreset: Reusable multi-parameter editing profile (e.g. Educational Explainer, High-Energy Short)
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class EditingPreferenceCategory(str, Enum):
    CAPTION = "caption"
    ZOOM = "zoom"
    PACING = "pacing"
    MOTION_GRAPHIC = "motion_graphic"
    AUDIO = "audio"
    ASPECT_RATIO = "aspect_ratio"
    TRANSITION = "transition"
    BROLL = "broll"


class ApprovalStatus(str, Enum):
    APPROVED = "approved"            # User explicitly approved learning this correction as a future preference
    ONE_TIME = "one_time"            # Kept for this project only, not learned for future
    PENDING_REVIEW = "pending_review"# Recorded modification awaiting user decision
    REJECTED = "rejected"            # User explicitly rejected learning this correction
    UNDO_OP = "undo_op"              # Discarded as an undo/redo/transient edit (never learned)


class PreferenceTier(int, Enum):
    TIER_1_EXPLICIT_INSTRUCTION = 1  # Natural language instruction in prompt (Strict Highest)
    TIER_2_PROJECT_OVERRIDE = 2      # Project-specific metadata/aspect overrides
    TIER_3_USER_LEARNED = 3          # Approved user editing memory & style reference
    TIER_4_SYSTEM_DEFAULT = 4        # OpenMontage baseline heuristics


@dataclass
class EditingPreference:
    """A learned, versioned editorial preference that can influence future AI planning."""

    preference_id: str
    category: str                   # From EditingPreferenceCategory
    parameter_key: str              # e.g. "zoom_scale", "highlight_color", "font_family", "words_per_page"
    preferred_value: Any            # e.g. 1.10, "#38BDF8", "Inter, sans-serif", 3
    confidence: float = 0.90        # 0.0 to 1.0 confidence weight
    times_approved: int = 1         # Reinforcement count
    context_constraints: dict[str, Any] = field(default_factory=dict) # e.g. {"target_aspect": "9:16"}
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_correction_id: Optional[str] = None
    description: str = ""

    def matches_context(self, target_context: dict[str, Any]) -> bool:
        """Check if target video context satisfies the preference's constraints."""
        if not self.context_constraints:
            return True
        for key, expected_val in self.context_constraints.items():
            if key in target_context and target_context[key] != expected_val:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EditingPreference:
        return cls(
            preference_id=data["preference_id"],
            category=data["category"],
            parameter_key=data["parameter_key"],
            preferred_value=data["preferred_value"],
            confidence=float(data.get("confidence", 0.9)),
            times_approved=int(data.get("times_approved", 1)),
            context_constraints=dict(data.get("context_constraints", {})),
            enabled=bool(data.get("enabled", True)),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            source_correction_id=data.get("source_correction_id"),
            description=data.get("description", ""),
        )


@dataclass
class CorrectionRecord:
    """Immutable audit trail of a user modification to an AI-generated editing decision."""

    correction_id: str
    project_id: str
    category: str                   # From EditingPreferenceCategory
    parameter_key: str              # e.g. "zoom_scale", "stat_card.content", "caption.highlight"
    original_ai_value: Any
    user_corrected_value: Any
    editing_context: dict[str, Any] = field(default_factory=dict)
    approval_status: str = ApprovalStatus.PENDING_REVIEW.value
    original_decision_provenance: dict[str, Any] = field(default_factory=dict)
    user_note: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorrectionRecord:
        return cls(
            correction_id=data["correction_id"],
            project_id=data["project_id"],
            category=data["category"],
            parameter_key=data["parameter_key"],
            original_ai_value=data["original_ai_value"],
            user_corrected_value=data["user_corrected_value"],
            editing_context=dict(data.get("editing_context", {})),
            approval_status=data.get("approval_status", ApprovalStatus.PENDING_REVIEW.value),
            original_decision_provenance=dict(data.get("original_decision_provenance", {})),
            user_note=data.get("user_note"),
            timestamp=float(data.get("timestamp", time.time())),
        )


@dataclass
class StylePreset:
    """Pre-configured or user-created editing style bundle."""

    preset_id: str
    title: str
    description: str
    is_builtin: bool = False
    target_aspect: str = "9:16"
    caption_preset: str = "word_highlight"
    caption_font_family: str = "Inter, sans-serif"
    caption_font_size: int = 52
    caption_highlight_color: str = "#22D3EE"
    caption_background_color: str = "rgba(0, 0, 0, 0.65)"
    words_per_page: int = 4
    zoom_intensity: str = "standard"  # none, subtle, standard, punchy
    zoom_scale: float = 1.25
    cut_aggressiveness: str = "balanced"  # conservative, balanced, aggressive
    min_pause_cut_duration: float = 1.0
    pacing_rest_interval: float = 2.5
    graphic_density: str = "medium"  # minimal, medium, data_heavy
    preferred_overlay_types: list[str] = field(default_factory=lambda: ["stat_card", "callout"])
    color_palette: dict[str, str] = field(
        default_factory=lambda: {
            "primary": "#2563EB",
            "accent": "#22D3EE",
            "background": "#FFFFFF",
        }
    )
    audio_settings: dict[str, Any] = field(
        default_factory=lambda: {"bgm_enabled": True, "bgm_volume": 0.25}
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StylePreset:
        return cls(
            preset_id=data["preset_id"],
            title=data["title"],
            description=data.get("description", ""),
            is_builtin=bool(data.get("is_builtin", False)),
            target_aspect=data.get("target_aspect", "9:16"),
            caption_preset=data.get("caption_preset", "word_highlight"),
            caption_font_family=data.get("caption_font_family", "Inter, sans-serif"),
            caption_font_size=int(data.get("caption_font_size", 52)),
            caption_highlight_color=data.get("caption_highlight_color", "#22D3EE"),
            caption_background_color=data.get("caption_background_color", "rgba(0, 0, 0, 0.65)"),
            words_per_page=int(data.get("words_per_page", 4)),
            zoom_intensity=data.get("zoom_intensity", "standard"),
            zoom_scale=float(data.get("zoom_scale", 1.25)),
            cut_aggressiveness=data.get("cut_aggressiveness", "balanced"),
            min_pause_cut_duration=float(data.get("min_pause_cut_duration", 1.0)),
            pacing_rest_interval=float(data.get("pacing_rest_interval", 2.5)),
            graphic_density=data.get("graphic_density", "medium"),
            preferred_overlay_types=list(data.get("preferred_overlay_types", ["stat_card", "callout"])),
            color_palette=dict(data.get("color_palette", {"primary": "#2563EB", "accent": "#22D3EE", "background": "#FFFFFF"})),
            audio_settings=dict(data.get("audio_settings", {"bgm_enabled": True, "bgm_volume": 0.25})),
        )
