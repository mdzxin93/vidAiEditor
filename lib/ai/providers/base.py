"""Base classes and data models for AI model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ObservationItem:
    """A grounded structured visual or auditory observation."""
    id: str
    start_seconds: float
    end_seconds: float
    category: str  # "person_object", "framing", "scene_change", "speaker_position", "screen_demo", "visible_text", "safe_region"
    description: str
    confidence: float  # 0.0 to 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
            "category": self.category,
            "description": self.description,
            "confidence": round(self.confidence, 3),
            "metadata": self.metadata,
        }


@dataclass
class VideoUnderstandingResult:
    """Structured output of the video understanding phase."""
    observations: list[ObservationItem]
    speaker_position: str = "center"  # "center", "left", "right"
    framing: str = "medium_close_up"  # "close_up", "medium", "wide"
    caption_safe_region: str = "bottom-center"
    overlay_safe_region: str = "upper_third"
    detected_topics: list[str] = field(default_factory=list)
    visual_quality_score: float = 0.9
    provider_name: str = "heuristic_engine"
    inference_duration_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "observations": [o.to_dict() for o in self.observations],
            "speaker_position": self.speaker_position,
            "framing": self.framing,
            "caption_safe_region": self.caption_safe_region,
            "overlay_safe_region": self.overlay_safe_region,
            "detected_topics": self.detected_topics,
            "visual_quality_score": round(self.visual_quality_score, 3),
            "provider_name": self.provider_name,
            "inference_duration_sec": round(self.inference_duration_sec, 3),
        }


@dataclass
class EditDecisionResult:
    """Structured output of the autonomous editing planner."""
    edit_decisions: dict[str, Any]
    provider_name: str
    decision_source: str  # "model_generated" | "heuristic_fallback"
    planning_duration_sec: float
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class BaseModelProvider(ABC):
    """Abstract interface for autonomous video editing model providers."""

    name: str = "base"
    is_neural_model: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if weights/endpoints and dependencies are ready."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Return provider status, hardware info, and model metadata."""
        pass

    @abstractmethod
    def understand_video(
        self,
        video_path: str,
        frames: list[dict[str, Any]],
        transcript: list[dict[str, Any]],
    ) -> VideoUnderstandingResult:
        """Extract structured visual/auditory observations from video frames & transcript."""
        pass

    @abstractmethod
    def plan_edits(
        self,
        understanding: VideoUnderstandingResult,
        transcript: list[dict[str, Any]],
        user_prompt: str,
        video_metadata: dict[str, Any],
        style_name: str = "clean-professional",
        style_directives: Any = None,
    ) -> EditDecisionResult:
        """Generate structured edit_decisions conforming to schema."""
        pass
