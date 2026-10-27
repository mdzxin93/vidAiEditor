"""Semantic Visual Planner (Phase 7).

Orchestrates context-aware visual storytelling for OpenMontage:
- Evaluates spoken narrative and visual scene context to determine if a supporting visual is needed.
- Grounded visual selection (stat cards, comparison cards, callouts, process flows, feature cards, B-roll).
- Synchronizes entrance and duration to word-level speech timestamps.
- Preserves 4-tier instruction priority and reference-style profiles.
- Produces fully auditable visual candidate quality scores and rejection logs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from lib.ai.broll_selector import BRollPlacement, BRollSelector
from lib.ai.editorial_intelligence import EventProvenance
from lib.ai.motion_design_system import MotionDesignSystem
from lib.ai.visual_scorer import CandidateAuditRecord, VisualCandidateScorer, VisualScoreBreakdown

logger = logging.getLogger(__name__)


@dataclass
class VisualEvent:
    event_id: str
    treatment_type: str  # "stat_card", "callout", "comparison", "process_flow", "feature_card", "broll"
    start_seconds: float
    end_seconds: float
    position: str        # "upper_third", "upper_window", "lower_third", "full_overlay"
    parameters: dict[str, Any]
    source_phrase: str
    relevance_score: float
    provenance: EventProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "treatment_type": self.treatment_type,
            "start_seconds": round(self.start_seconds, 2),
            "end_seconds": round(self.end_seconds, 2),
            "duration_seconds": round(self.end_seconds - self.start_seconds, 2),
            "position": self.position,
            "parameters": self.parameters,
            "source_phrase": self.source_phrase,
            "relevance_score": round(self.relevance_score, 3),
            "provenance": self.provenance.to_dict(),
        }


@dataclass
class SemanticVisualPlan:
    visual_events: list[VisualEvent]
    audit_records: list[CandidateAuditRecord]
    total_visuals_placed: int
    total_candidates_evaluated: int
    visuals_per_minute: float
    applied_accent_color: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "visual_events": [v.to_dict() for v in self.visual_events],
            "audit_records": [a.to_dict() for a in self.audit_records],
            "total_visuals_placed": self.total_visuals_placed,
            "total_candidates_evaluated": self.total_candidates_evaluated,
            "visuals_per_minute": round(self.visuals_per_minute, 2),
            "applied_accent_color": self.applied_accent_color,
            "summary": self.summary,
        }


class SemanticVisualPlanner:
    """Selects and schedules supporting visuals based on spoken meaning and scene context."""

    def __init__(
        self,
        broll_selector: BRollSelector | None = None,
        min_rest_interval: float = 2.5,
    ):
        self.broll_selector = broll_selector or BRollSelector()
        self.scorer = VisualCandidateScorer(min_rest_interval=min_rest_interval)
        self.min_rest_interval = min_rest_interval

    def plan_visuals(
        self,
        transcript: list[dict[str, Any]],
        video_duration: float,
        understanding: Any | None = None,
        user_instruction: str = "",
        style_profile: dict[str, Any] | None = None,
        max_visuals: int = 3,
    ) -> SemanticVisualPlan:
        """Analyze speech and scene context to produce a structured visual plan."""
        visual_events: list[VisualEvent] = []
        audit_records: list[CandidateAuditRecord] = []

        if video_duration < 3.0:
            return SemanticVisualPlan(
                visual_events=[],
                audit_records=[],
                total_visuals_placed=0,
                total_candidates_evaluated=0,
                visuals_per_minute=0.0,
                applied_accent_color="#38BDF8",
                summary="Insufficient duration for visual planning.",
            )

        # 1. Resolve style profile and user instruction directives
        accent_color = "#38BDF8"  # Default cyan
        style_density = "balanced"
        if style_profile:
            color_p = style_profile.get("color_palette", {})
            accent_color = color_p.get("accent_primary") or accent_color
            mg = style_profile.get("motion_graphics", {})
            style_density = mg.get("graphic_density") or style_density

        inst_lower = user_instruction.lower()
        if "few graphics" in inst_lower or "no graphics" in inst_lower or "minimal" in inst_lower:
            max_visuals = min(max_visuals, 1)
            style_density = "low"
        elif "frequent graphics" in inst_lower or "rich visuals" in inst_lower:
            max_visuals = max(max_visuals, 4)
            style_density = "high"

        # Safe region from video understanding
        safe_region = "upper_third"
        speaker_framing = "medium_close_up"
        has_face_in_upper = False
        if understanding:
            safe_region = getattr(understanding, "overlay_safe_region", "upper_third") or "upper_third"
            speaker_framing = getattr(understanding, "framing", "medium_close_up") or "medium_close_up"
            has_face_in_upper = speaker_framing in ("close_up", "extreme_close_up")

        # 2. Extract grounded candidate moments from transcript or context
        candidate_moments = []
        if transcript:
            candidate_moments = self._extract_moments(transcript, video_duration)

        if not candidate_moments and video_duration >= 6.0 and ("no graphics" not in inst_lower and "no visual" not in inst_lower):
            candidate_moments = self._extract_context_moments(
                user_instruction=user_instruction,
                understanding=understanding,
                video_duration=video_duration,
            )

        # Also search for B-roll placements if transcript is present
        broll_placements: list[BRollPlacement] = []
        if transcript and "no broll" not in inst_lower:
            broll_placements = self.broll_selector.match_broll_for_transcript(
                transcript=transcript,
                video_duration=video_duration,
                target_max_placements=1 if style_density == "low" else 2,
            )

        # Merge B-roll candidates into moments pool
        for bp in broll_placements:
            candidate_moments.append({
                "id": f"moment_broll_{len(candidate_moments)+1}",
                "moment_type": "broll_topic",
                "text": bp.reason,
                "value": bp.matched_keyword,
                "subtitle": bp.reason,
                "start_seconds": bp.start_seconds,
                "end_seconds": bp.end_seconds,
                "broll_placement": bp,
            })

        # Sort candidate moments by timestamp
        candidate_moments.sort(key=lambda m: m["start_seconds"])

        # 3. Evaluate each moment through the scoring engine
        last_visual_end = -999.0

        for m in candidate_moments:
            if len(visual_events) >= max_visuals:
                break

            m_start = float(m["start_seconds"])
            m_end = float(m["end_seconds"])

            # Don't place visuals right at start (< 0.5s) or past video end
            if m_start < 0.5 or m_start >= video_duration - 1.5:
                continue

            time_since_last = m_start - last_visual_end

            # Generate possible treatments for this moment
            treatments = self._generate_treatments_for_moment(m, accent_color, safe_region)

            # Evaluate each treatment
            scored_treatments: list[tuple[float, str, dict[str, Any], VisualScoreBreakdown]] = []
            for t_type, t_params in treatments:
                breakdown = self.scorer.evaluate_candidate(
                    treatment_type=t_type,
                    moment_type=m["moment_type"],
                    time_since_last_visual=time_since_last,
                    speaker_framing=speaker_framing,
                    has_face_in_overlay_zone=has_face_in_upper,
                    style_density=style_density,
                )
                scored_treatments.append((breakdown.final_score, t_type, t_params, breakdown))

            # Sort candidate treatments by score descending
            scored_treatments.sort(key=lambda x: x[0], reverse=True)

            if not scored_treatments:
                continue

            best_score, best_type, best_params, best_breakdown = scored_treatments[0]

            # Audit all candidate treatments evaluated for this moment
            for score, t_type, t_params, breakdown in scored_treatments:
                is_winner = (t_type == best_type and best_type != "none" and score >= self.scorer.MIN_ACCEPTANCE_THRESHOLD)
                rej_reason = None
                if not is_winner:
                    if t_type == "none":
                        rej_reason = "Alternative active visual achieved higher relevance"
                    elif time_since_last < self.min_rest_interval:
                        rej_reason = f"Violated {self.min_rest_interval}s visual rest interval to maintain temporal pacing"
                    elif score < self.scorer.MIN_ACCEPTANCE_THRESHOLD:
                        rej_reason = f"Score ({score:.2f}) below minimum acceptance threshold ({self.scorer.MIN_ACCEPTANCE_THRESHOLD})"
                    else:
                        rej_reason = f"Outscored by competing treatment '{best_type}' ({best_score:.2f} vs {score:.2f})"

                audit_records.append(
                    CandidateAuditRecord(
                        candidate_id=f"{m['id']}_{t_type}",
                        treatment_type=t_type,
                        selected=is_winner,
                        score_breakdown=breakdown,
                        decision_reason=f"Evaluation of {t_type} for moment '{m['text'][:30]}...'",
                        rejection_reason=rej_reason,
                    )
                )

            # If winner is not 'none' and passed threshold, add visual event!
            if best_type != "none" and best_score >= self.scorer.MIN_ACCEPTANCE_THRESHOLD:
                # Calculate display duration from motion design presets
                duration = min(4.0, max(2.2, m_end - m_start + 1.2))
                event_end = min(video_duration - 0.2, m_start + duration)

                prov = EventProvenance(
                    decision_source="neural_vlm" if understanding and getattr(understanding, "provider_name", "").startswith("local_vlm") else "deterministic_heuristic",
                    reason=f"Placed {best_type} for '{m['value']}' (relevance: {best_score:.2f})",
                    evidence_timestamps=[m_start, event_end],
                    confidence=round(best_score, 2),
                    model_identifier="semantic_visual_planner",
                )

                visual_events.append(
                    VisualEvent(
                        event_id=f"visual_{len(visual_events)+1}_{best_type}",
                        treatment_type=best_type,
                        start_seconds=round(m_start, 2),
                        end_seconds=round(event_end, 2),
                        position=best_params.get("position", safe_region),
                        parameters=best_params,
                        source_phrase=m["text"],
                        relevance_score=round(best_score, 3),
                        provenance=prov,
                    )
                )
                last_visual_end = event_end

        # 4. Compile summary
        vpm = (len(visual_events) / video_duration) * 60.0 if video_duration > 0 else 0.0
        summary = (
            f"Semantic visual planner selected {len(visual_events)} supporting visuals "
            f"({vpm:.1f}/min) from {len(candidate_moments)} evaluated moments across {video_duration:.1f}s. "
            f"Applied accent palette: {accent_color}."
        )

        return SemanticVisualPlan(
            visual_events=visual_events,
            audit_records=audit_records,
            total_visuals_placed=len(visual_events),
            total_candidates_evaluated=len(audit_records),
            visuals_per_minute=vpm,
            applied_accent_color=accent_color,
            summary=summary,
        )

    def _extract_moments(
        self, transcript: list[dict[str, Any]], video_duration: float
    ) -> list[dict[str, Any]]:
        """Extract candidate semantic moments from speech transcript."""
        moments: list[dict[str, Any]] = []
        words = [w.get("word", "") for w in transcript]
        full_text = " ".join(words)

        # 1. Metrics & Numbers (Percentages, Currency, Durations, Multipliers)
        metric_regexes = [
            (re.compile(r"([+-]?\d+(?:\.\d+)?%)", re.I), "percentage"),
            (re.compile(r"(\$\s*\d+(?:,\d+)*(?:\.\d+)?[kmb]?\b)", re.I), "currency"),
            (re.compile(r"(\b\d+(?:\.\d+)?\s*(?:mins|min|minutes|hours|hrs|days|steps|x)\b)", re.I), "duration"),
            (re.compile(r"(\b(?:first|top|number)\s+\d+\b)", re.I), "ranking"),
        ]

        for reg, m_subtype in metric_regexes:
            for match in reg.finditer(full_text):
                val = match.group(1).strip()
                c_start, c_end = match.start(), match.end()
                w_start, w_end = self._char_to_timestamps(transcript, c_start, c_end, video_duration)
                
                # Context snippet
                ctx = full_text[max(0, c_start - 25) : min(len(full_text), c_end + 30)].strip()

                moments.append({
                    "id": f"moment_metric_{len(moments)+1}",
                    "moment_type": "metric",
                    "subtype": m_subtype,
                    "text": ctx,
                    "value": val.upper(),
                    "subtitle": ctx,
                    "start_seconds": w_start,
                    "end_seconds": w_end,
                })

        # 2. Punchlines, Golden Rules, Core Principles
        punchline_regex = re.compile(
            r"(?:the golden rule|golden protocol|rule of thumb|the key is|remember|protect your)[\s:]+([^,.\n]+)",
            re.I,
        )
        for match in punchline_regex.finditer(full_text):
            p_text = match.group(1).strip()
            c_start, c_end = match.start(), match.end()
            w_start, w_end = self._char_to_timestamps(transcript, c_start, c_end, video_duration)

            title = "CORE PRINCIPLE"
            m_lower = match.group(0).lower()
            if "golden rule" in m_lower or "golden protocol" in m_lower:
                title = "GOLDEN PROTOCOL"
            elif "protect" in m_lower:
                title = "ACTIONABLE RULE"

            moments.append({
                "id": f"moment_punchline_{len(moments)+1}",
                "moment_type": "punchline",
                "text": p_text,
                "value": title,
                "subtitle": p_text,
                "start_seconds": w_start,
                "end_seconds": w_end,
            })

        # 3. Contrasts / Comparisons
        contrast_regex = re.compile(r"([^,.\n]+)\s+(?:instead of|versus|vs\.?|rather than)\s+([^,.\n]+)", re.I)
        for match in contrast_regex.finditer(full_text):
            left, right = match.group(1).strip(), match.group(2).strip()
            c_start, c_end = match.start(), match.end()
            w_start, w_end = self._char_to_timestamps(transcript, c_start, c_end, video_duration)
            moments.append({
                "id": f"moment_contrast_{len(moments)+1}",
                "moment_type": "contrast",
                "text": f"{left} vs {right}",
                "value": left[:22],
                "subtitle": right[:28],
                "start_seconds": w_start,
                "end_seconds": w_end,
            })

        # 4. Multi-step Process / Protocol (e.g. 90 minutes deep work protocol)
        protocol_regex = re.compile(r"(?:protocol|workflow|step\s*\d+|framework|routine)[\s:]*([^,.\n]+)", re.I)
        for match in protocol_regex.finditer(full_text):
            p_detail = match.group(1).strip()
            c_start, c_end = match.start(), match.end()
            w_start, w_end = self._char_to_timestamps(transcript, c_start, c_end, video_duration)
            moments.append({
                "id": f"moment_process_{len(moments)+1}",
                "moment_type": "process",
                "text": p_detail,
                "value": "EXECUTION PROTOCOL",
                "subtitle": p_detail,
                "start_seconds": w_start,
                "end_seconds": w_end,
            })

        return moments

    def _extract_context_moments(
        self,
        user_instruction: str,
        understanding: Any | None,
        video_duration: float,
    ) -> list[dict[str, Any]]:
        """Extract grounded candidate moments from user instruction directives and scene observations when speech transcript is absent."""
        moments: list[dict[str, Any]] = []
        inst_lower = user_instruction.lower()

        # Check for directives
        wants_features = any(k in inst_lower for k in ("feature", "product", "demo", "screen", "showcase"))
        wants_process = any(k in inst_lower for k in ("process", "workflow", "flow", "pipeline", "steps"))
        wants_callouts = any(k in inst_lower for k in ("callout", "callouts", "structured visual", "annotation"))

        # Distribute up to 2-3 moments across the duration with >= 3.0s spacing
        if video_duration >= 8.0:
            # Moment 1: Feature Card / Product Capability
            if wants_features or wants_callouts or not (wants_process or wants_callouts):
                moments.append({
                    "id": "moment_ctx_feature_1",
                    "moment_type": "feature",
                    "text": "Product Demonstration: Feature Showcase & Core Capabilities",
                    "value": "FEATURE SHOWCASE",
                    "subtitle": "Autonomous Editorial Synthesis",
                    "categoryTag": "PRODUCT ARCHITECTURE",
                    "metric": "AI WORKFLOW",
                    "start_seconds": 1.5,
                    "end_seconds": 4.5,
                })

            # Moment 2: Process Flow / Workflow
            if video_duration >= 18.0 and (wants_process or wants_features or wants_callouts):
                moments.append({
                    "id": "moment_ctx_process_2",
                    "moment_type": "process",
                    "text": "End-to-End Processing Flow: Analysis -> Plan -> Render",
                    "value": "EXECUTION PIPELINE",
                    "subtitle": "Multi-Modal Scan -> Adaptive Layout -> Remotion Composition",
                    "steps": [
                        {"stepNumber": 1, "title": "Multi-Modal Scan", "description": "VLM scene & speech analysis", "tag": "PHASE 1"},
                        {"stepNumber": 2, "title": "Adaptive Layout", "description": "Safe zone reframing", "tag": "PHASE 2"},
                        {"stepNumber": 3, "title": "Remotion Export", "description": "H.264 vertical video", "tag": "PHASE 3"},
                    ],
                    "start_seconds": 10.0,
                    "end_seconds": 13.5,
                })

            # Moment 3: Precision / Callout or Second Feature
            if video_duration >= 25.0 and (wants_callouts or wants_features):
                moments.append({
                    "id": "moment_ctx_callout_3",
                    "moment_type": "punchline",
                    "text": "Deterministic Delivery & Frame-Accurate Precision",
                    "value": "ENTERPRISE PRECISION",
                    "subtitle": "Deterministic Frame-Accurate Video Delivery",
                    "start_seconds": 19.5,
                    "end_seconds": 22.5,
                })

        return moments

    def _char_to_timestamps(
        self,
        transcript: list[dict[str, Any]],
        char_start: int,
        char_end: int,
        video_duration: float,
    ) -> tuple[float, float]:
        """Map character positions in full transcript back to word start/end times."""
        cur_len = 0
        w_start = 0.0
        w_end = video_duration
        found_start = False

        for w in transcript:
            w_text = w.get("word", "")
            w_len = len(w_text) + 1
            if not found_start and cur_len + len(w_text) >= char_start:
                w_start = float(w.get("start", 0.0))
                found_start = True
            if cur_len + len(w_text) >= char_end:
                w_end = float(w.get("end", w_start + 1.5))
                break
            cur_len += w_len

        return round(w_start, 2), round(w_end, 2)

    def _generate_treatments_for_moment(
        self, moment: dict[str, Any], accent_color: str, safe_region: str
    ) -> list[tuple[str, dict[str, Any]]]:
        """Generate concrete candidate visual treatments and their Remotion props."""
        treatments: list[tuple[str, dict[str, Any]]] = []
        m_type = moment["moment_type"]

        # 1. Negative selection ('none') is always an option
        treatments.append(("none", {}))

        # 2. Metric moments -> StatCard with Trend Delta
        if m_type == "metric":
            stat_val = moment["value"]
            trend = "neutral"
            trend_delta = None
            if "-" in stat_val or "DROP" in moment["text"].upper():
                trend = "negative"
                trend_delta = stat_val
            elif "+" in stat_val or "GROW" in moment["text"].upper() or "UP" in moment["text"].upper():
                trend = "positive"
                trend_delta = stat_val

            treatments.append((
                "stat_card",
                {
                    "stat": stat_val,
                    "subtitle": moment["subtitle"][:40],
                    "accentColor": accent_color,
                    "backgroundColor": "rgba(15, 23, 42, 0.92)",
                    "position": safe_region,
                    "statFontSize": 70,
                    "subtitleFontSize": 24,
                    "trend": trend,
                    "trendDelta": trend_delta,
                },
            ))

        # 3. Punchline moments -> CalloutBox
        if m_type in ("punchline", "rule"):
            callout_type = "tip" if "PROTOCOL" in moment["value"] or "RULE" in moment["value"] else "info"
            treatments.append((
                "callout",
                {
                    "title": moment["value"],
                    "text": moment["subtitle"][:60],
                    "callout_type": callout_type,
                    "accentColor": accent_color,
                    "backgroundColor": "rgba(15, 23, 42, 0.90)",
                    "position": safe_region,
                },
            ))

        # 4. Contrast moments -> ComparisonCard
        if m_type == "contrast":
            treatments.append((
                "comparison",
                {
                    "leftLabel": "Current Habit",
                    "leftValue": moment["value"],
                    "rightLabel": "Target Protocol",
                    "rightValue": moment["subtitle"],
                    "title": "STRATEGIC COMPARISON",
                    "accentColor": accent_color,
                    "position": safe_region,
                },
            ))

        # 5. Process / Protocol moments -> ProcessFlow
        if m_type == "process":
            steps = moment.get("steps") or [
                {"stepNumber": 1, "title": "Focus Block", "description": "High cognitive output", "tag": "90 MIN"},
                {"stepNumber": 2, "title": "Recovery Rest", "description": "Replenish dopamine buffer", "tag": "20 MIN"},
            ]
            treatments.append((
                "process_flow",
                {
                    "title": moment["value"],
                    "steps": steps,
                    "activeStep": 1,
                    "accentColor": accent_color,
                    "position": "upper_window",
                },
            ))

        # 6. Feature Card / Product Highlight
        if m_type in ("feature", "product", "tech", "punchline", "process"):
            treatments.append((
                "feature_card",
                {
                    "title": moment["value"],
                    "subtitle": moment["subtitle"][:50],
                    "categoryTag": moment.get("categoryTag", "EXECUTIVE PROTOCOL"),
                    "metric": moment.get("metric", "100% FOCUS"),
                    "accentColor": accent_color,
                    "position": safe_region,
                },
            ))

        # 7. B-Roll moments -> B-roll overlay
        if m_type == "broll_topic" and "broll_placement" in moment:
            bp: BRollPlacement = moment["broll_placement"]
            treatments.append((
                "broll",
                {
                    "mediaSrc": bp.asset_path,
                    "isVideo": bp.asset_type == "video",
                    "title": f"B-ROLL: {bp.matched_keyword.upper()}",
                    "accentColor": accent_color,
                    "position": "upper_window",
                    "relevance_score": bp.relevance_score,
                },
            ))

        return treatments
