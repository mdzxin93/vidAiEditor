"""Context-Aware Preference Matcher for OpenMontage (Phase 10).

Provides explainable, lightweight context similarity evaluation to prevent
preferences from one genre (e.g. 9:16 high-energy viral reel) from inappropriately
bleeding into an unrelated context (e.g. 16:9 calm educational lecture).

Zero heavy neural embedding models — 100% local, explainable, and fast.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from lib.ai.memory.models import EditingPreference

logger = logging.getLogger(__name__)


@dataclass
class ContextMatchResult:
    """Detailed explainable result of matching a preference against a target video context."""

    preference_id: str
    is_compatible: bool
    match_score: float  # 0.0 to 1.0
    matched_reasons: list[str] = field(default_factory=list)
    incompatible_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preference_id": self.preference_id,
            "is_compatible": self.is_compatible,
            "match_score": round(self.match_score, 3),
            "matched_reasons": self.matched_reasons,
            "incompatible_reasons": self.incompatible_reasons,
        }


class ContextMatcher:
    """Evaluates whether an editing preference is appropriate for a target video context."""

    def __init__(self, compatibility_threshold: float = 0.50):
        self.compatibility_threshold = compatibility_threshold

    def evaluate_match(
        self,
        preference: EditingPreference,
        target_context: dict[str, Any],
    ) -> ContextMatchResult:
        """Evaluate if preference constraints match target video context."""
        constraints = preference.context_constraints or {}
        
        # If the preference has no specific constraints, it is globally applicable
        if not constraints:
            return ContextMatchResult(
                preference_id=preference.preference_id,
                is_compatible=True,
                match_score=0.85,
                matched_reasons=["Global preference without narrow constraints."],
            )

        score_components: list[float] = []
        matched_reasons: list[str] = []
        incompatible_reasons: list[str] = []

        # 1. Target Aspect Ratio (Hard Constraint for aspect-dependent settings)
        pref_aspect = constraints.get("target_aspect") or constraints.get("aspect_ratio")
        target_aspect = target_context.get("target_aspect") or target_context.get("aspect_ratio")
        if pref_aspect and target_aspect:
            def _norm_aspect(val: Any) -> str:
                s = str(val).strip()
                if s.startswith("9:") or s.startswith("9/"):
                    return "9:16"
                if s.startswith("16:") or s.startswith("16/"):
                    return "16:9"
                if "9" in s and s.find("9") < s.find("16"):
                    return "9:16"
                return "16:9"

            norm_pref_aspect = _norm_aspect(pref_aspect)
            norm_tgt_aspect = _norm_aspect(target_aspect)
            if norm_pref_aspect == norm_tgt_aspect:
                score_components.append(1.0)
                matched_reasons.append(f"Matching aspect ratio ({norm_tgt_aspect}).")
            else:
                score_components.append(0.0)
                incompatible_reasons.append(
                    f"Aspect ratio mismatch: preference requires {norm_pref_aspect}, target is {norm_tgt_aspect}."
                )

        # 2. Video Category / Genre
        pref_cat = constraints.get("video_category") or constraints.get("category")
        target_cat = target_context.get("video_category") or target_context.get("category")
        if pref_cat and target_cat:
            pref_cat_str = str(pref_cat).lower().strip()
            target_cat_str = str(target_cat).lower().strip()
            if pref_cat_str == target_cat_str:
                score_components.append(1.0)
                matched_reasons.append(f"Identical video category: '{target_cat_str}'.")
            elif self._are_categories_compatible(pref_cat_str, target_cat_str):
                score_components.append(0.7)
                matched_reasons.append(f"Compatible video category: '{pref_cat_str}' ~ '{target_cat_str}'.")
            else:
                score_components.append(0.1)
                incompatible_reasons.append(
                    f"Category divergence: preference for '{pref_cat_str}' vs target '{target_cat_str}'."
                )

        # 3. Speaking Style / Pace (Words Per Minute)
        pref_pace = constraints.get("speaking_pace") or constraints.get("pace")
        target_pace = target_context.get("speaking_pace") or target_context.get("pace")
        if pref_pace and target_pace:
            if str(pref_pace).lower() == str(target_pace).lower():
                score_components.append(1.0)
                matched_reasons.append(f"Matching speaking pace: '{target_pace}'.")
            else:
                score_components.append(0.2)
                incompatible_reasons.append(
                    f"Speaking pace difference: preference expects '{pref_pace}', target is '{target_pace}'."
                )

        # 4. Target Graphic Purpose / Intent
        pref_intent = constraints.get("graphic_purpose") or constraints.get("intent")
        target_intent = target_context.get("graphic_purpose") or target_context.get("intent")
        if pref_intent and target_intent:
            if str(pref_intent).lower() == str(target_intent).lower():
                score_components.append(1.0)
                matched_reasons.append(f"Matching graphic intent: '{target_intent}'.")
            else:
                score_components.append(0.3)
                incompatible_reasons.append(
                    f"Graphic intent divergence: '{pref_intent}' vs '{target_intent}'."
                )

        # Compute composite score
        if not score_components:
            # Constraints existed in dictionary but were not recognized or target_context lacked them
            final_score = 0.70
            matched_reasons.append("Partial context match (constraints did not explicitly conflict).")
        else:
            final_score = sum(score_components) / len(score_components)

        is_compatible = final_score >= self.compatibility_threshold and len(incompatible_reasons) == 0

        return ContextMatchResult(
            preference_id=preference.preference_id,
            is_compatible=is_compatible,
            match_score=final_score,
            matched_reasons=matched_reasons,
            incompatible_reasons=incompatible_reasons,
        )

    def _are_categories_compatible(self, cat1: str, cat2: str) -> bool:
        """Heuristic compatibility between editorial categories."""
        group_educational = {"educational", "tutorial", "explainer", "tech_demo", "lecture"}
        group_social_short = {"viral_short", "reels", "tiktok", "high_energy", "shorts"}
        group_corporate = {"corporate", "product_launch", "interview", "minimal_professional"}

        for group in (group_educational, group_social_short, group_corporate):
            if cat1 in group and cat2 in group:
                return True
        return False
