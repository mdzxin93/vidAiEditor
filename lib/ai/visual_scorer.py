"""Interpretable Visual Candidate Quality Scorer (Phase 7).

Evaluates and scores candidate visual treatments (stat cards, callouts, B-roll, diagrams, none)
across dimensional metrics: semantic relevance, timing suitability, aspect ratio,
subject obstruction safety, reference style compatibility, and novelty.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VisualScoreBreakdown:
    semantic_relevance: float         # 0.0 .. 1.0
    timing_suitability: float         # 0.0 .. 1.0
    aspect_ratio_compatibility: float # 0.0 .. 1.0
    visual_quality: float             # 0.0 .. 1.0
    subject_obstruction_safety: float # 0.0 .. 1.0
    style_compatibility: float        # 0.0 .. 1.0
    narrative_usefulness: float       # 0.0 .. 1.0
    novelty_penalty: float            # 0.0 .. 0.5 (deduction)
    final_score: float                # 0.0 .. 1.0

    def to_dict(self) -> dict[str, float]:
        return {
            "semantic_relevance": round(self.semantic_relevance, 3),
            "timing_suitability": round(self.timing_suitability, 3),
            "aspect_ratio_compatibility": round(self.aspect_ratio_compatibility, 3),
            "visual_quality": round(self.visual_quality, 3),
            "subject_obstruction_safety": round(self.subject_obstruction_safety, 3),
            "style_compatibility": round(self.style_compatibility, 3),
            "narrative_usefulness": round(self.narrative_usefulness, 3),
            "novelty_penalty": round(self.novelty_penalty, 3),
            "final_score": round(self.final_score, 3),
        }


@dataclass
class CandidateAuditRecord:
    candidate_id: str
    treatment_type: str
    selected: bool
    score_breakdown: VisualScoreBreakdown
    decision_reason: str
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "treatment_type": self.treatment_type,
            "selected": self.selected,
            "score": self.score_breakdown.to_dict(),
            "decision_reason": self.decision_reason,
            "rejection_reason": self.rejection_reason,
        }


class VisualCandidateScorer:
    """Calculates interpretable quality scores for motion graphics and B-roll candidates."""

    # Weights summing to 1.0
    WEIGHTS = {
        "semantic_relevance": 0.30,
        "narrative_usefulness": 0.20,
        "timing_suitability": 0.15,
        "subject_obstruction_safety": 0.15,
        "style_compatibility": 0.10,
        "aspect_ratio_compatibility": 0.05,
        "visual_quality": 0.05,
    }

    MIN_ACCEPTANCE_THRESHOLD = 0.58

    def __init__(self, min_rest_interval: float = 2.5):
        self.min_rest_interval = min_rest_interval

    def evaluate_candidate(
        self,
        treatment_type: str,
        moment_type: str,
        time_since_last_visual: float,
        speaker_framing: str,
        has_face_in_overlay_zone: bool,
        style_density: str = "balanced",
        target_aspect: str = "9:16",
        candidate_aspect: str = "9:16",
        is_duplicate: bool = False,
    ) -> VisualScoreBreakdown:
        """Evaluate a candidate treatment across mathematical dimensions."""
        # 1. Negative selection ('none') logic
        if treatment_type == "none":
            # If rest interval is violated, 'none' gets high score to preserve calm pacing
            timing = 0.95 if time_since_last_visual < self.min_rest_interval else 0.40
            return VisualScoreBreakdown(
                semantic_relevance=0.80,
                timing_suitability=timing,
                aspect_ratio_compatibility=1.0,
                visual_quality=1.0,
                subject_obstruction_safety=1.0,
                style_compatibility=0.85 if style_density == "low" else 0.60,
                narrative_usefulness=0.85 if time_since_last_visual < self.min_rest_interval else 0.40,
                novelty_penalty=0.0,
                final_score=0.90 if time_since_last_visual < self.min_rest_interval else 0.45,
            )

        # 2. Semantic relevance
        semantic = 0.50
        if treatment_type == "stat_card" and moment_type == "metric":
            semantic = 0.95
        elif treatment_type == "callout" and moment_type in ("punchline", "rule", "protocol"):
            semantic = 0.90
        elif treatment_type == "comparison" and moment_type == "contrast":
            semantic = 0.92
        elif treatment_type == "process_flow" and moment_type in ("process", "timeline", "protocol"):
            semantic = 0.92
        elif treatment_type == "feature_card" and moment_type in ("product", "feature", "tech"):
            semantic = 0.88
        elif treatment_type == "broll" and moment_type in ("tech", "broll_topic", "product"):
            semantic = 0.86

        # 3. Timing suitability (violating rest interval degrades score)
        if time_since_last_visual < self.min_rest_interval:
            timing = max(0.15, 0.40 * (time_since_last_visual / self.min_rest_interval))
        else:
            timing = 0.90

        # 4. Aspect ratio compatibility
        aspect = 1.0 if target_aspect == candidate_aspect else 0.85

        # 5. Visual quality
        quality = 0.90

        # 6. Subject obstruction safety
        obstruction = 0.95
        if has_face_in_overlay_zone or speaker_framing in ("close_up", "extreme_close_up"):
            obstruction = 0.65  # Penalize high visual clutter when face dominates

        # 7. Style compatibility
        style_comp = 0.85
        if style_density == "low" and treatment_type in ("broll", "process_flow"):
            style_comp = 0.60
        elif style_density == "high":
            style_comp = 0.95

        # 8. Narrative usefulness
        narrative = 0.85 if moment_type != "unclassified" else 0.40

        # 9. Novelty penalty
        novelty_penalty = 0.35 if is_duplicate else 0.0

        # Weighted calculation
        raw_score = (
            semantic * self.WEIGHTS["semantic_relevance"]
            + narrative * self.WEIGHTS["narrative_usefulness"]
            + timing * self.WEIGHTS["timing_suitability"]
            + obstruction * self.WEIGHTS["subject_obstruction_safety"]
            + style_comp * self.WEIGHTS["style_compatibility"]
            + aspect * self.WEIGHTS["aspect_ratio_compatibility"]
            + quality * self.WEIGHTS["visual_quality"]
        ) - novelty_penalty

        final_score = max(0.0, min(1.0, raw_score))

        return VisualScoreBreakdown(
            semantic_relevance=semantic,
            timing_suitability=timing,
            aspect_ratio_compatibility=aspect,
            visual_quality=quality,
            subject_obstruction_safety=obstruction,
            style_compatibility=style_comp,
            narrative_usefulness=narrative,
            novelty_penalty=novelty_penalty,
            final_score=final_score,
        )
