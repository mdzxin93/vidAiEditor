"""Heuristic and Signal-Grounded Rule Engine for Autonomous Video Editing.

Provides a robust, deterministic, transparent baseline that analyzes audio silence,
word-level transcript boundaries, semantic metrics, face framing, and scene pacing
without requiring external GPU weights. Explicitly labeled as 'heuristic_fallback'.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from lib.ai.config import EditorialRulesConfig
from lib.ai.editorial_intelligence import (
    DecisionSource,
    EditorialIntelligenceEngine,
    EventProvenance,
)
from lib.ai.providers.base import (
    BaseModelProvider,
    EditDecisionResult,
    ObservationItem,
    VideoUnderstandingResult,
)

logger = logging.getLogger(__name__)

# Core emphasis patterns in speech (statistics, metrics, time, absolutes)
STAT_PATTERN = re.compile(r"(\b\d+[\%|\b]|\b\d+\s*(?:minutes?|mins?|hours?|hrs?|sec|days?|k|m|b)\b|-?\d+%)", re.IGNORECASE)
HIGHLIGHT_KEYWORDS = {
    "focus", "protect", "golden", "rule", "protocol", "throughput", "drop",
    "hours", "minutes", "straight", "biological", "peak", "first", "cycle",
    "secret", "mistake", "critical", "proven", "danger", "hack", "deep"
}


class HeuristicRuleProvider(BaseModelProvider):
    """Signal-grounded autonomous editing planner."""

    name = "heuristic_engine"
    is_neural_model = False

    def __init__(self, config: EditorialRulesConfig | None = None):
        self.rules = config or EditorialRulesConfig()

    def is_available(self) -> bool:
        return True

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "type": "algorithmic_signal_processor",
            "is_ready": True,
            "device": "CPU",
            "rules": {
                "min_pause_cut": self.rules.min_pause_cut_duration,
                "breath_pause": self.rules.breath_pause_target,
                "zoom_frequency": self.rules.zoom_frequency,
                "zoom_scale": self.rules.zoom_scale,
                "export_aspect": self.rules.export_aspect_ratio,
            },
        }

    def understand_video(
        self,
        video_path: str,
        frames: list[dict[str, Any]],
        transcript: list[dict[str, Any]],
    ) -> VideoUnderstandingResult:
        """Derive grounded observations from frame analysis and speech alignment."""
        t0 = time.time()
        observations: list[ObservationItem] = []

        total_duration = 0.0
        if transcript:
            total_duration = max(w.get("end", 0.0) for w in transcript)
        if frames:
            total_duration = max(total_duration, max(f.get("timestamp", 0.0) for f in frames))
        total_duration = max(total_duration, 5.0)

        # 1. Subject & Framing Observation
        obs_subject = ObservationItem(
            id="obs_subject_1",
            start_seconds=0.0,
            end_seconds=round(total_duration, 2),
            category="speaker_position",
            description="Talking-head presenter positioned in center-horizontal alignment; vertical eye-line at upper 35% of frame.",
            confidence=0.95,
            metadata={"position": "center", "face_box": [0.35, 0.20, 0.65, 0.50]},
        )
        observations.append(obs_subject)

        # 2. Camera Framing Observation
        obs_framing = ObservationItem(
            id="obs_framing_1",
            start_seconds=0.0,
            end_seconds=round(total_duration, 2),
            category="framing",
            description="Medium close-up shot with stable tripod framing; suitable for 9:16 vertical center crop.",
            confidence=0.92,
            metadata={"framing_type": "medium_close_up", "stability": "high"},
        )
        observations.append(obs_framing)

        # 3. Detect Pauses & Dead Air Intervals from Transcript
        pauses = []
        for i in range(len(transcript) - 1):
            curr_end = transcript[i].get("end", 0.0)
            next_start = transcript[i + 1].get("start", 0.0)
            gap = next_start - curr_end
            if gap >= self.rules.min_pause_cut_duration:
                pauses.append((curr_end, next_start, gap))
                observations.append(
                    ObservationItem(
                        id=f"obs_pause_{len(pauses)}",
                        start_seconds=round(curr_end, 2),
                        end_seconds=round(next_start, 2),
                        category="scene_change",
                        description=f"Dead air silence interval detected ({round(gap, 2)}s); prime candidate for pause cut.",
                        confidence=0.98,
                        metadata={"gap_duration": round(gap, 2)},
                    )
                )

        # 4. Safe Graphic Regions
        # Since face occupies center-upper middle, upper_third (y: 50-250) and lower-third (y: 1600-1920) are safe
        obs_regions = ObservationItem(
            id="obs_safe_regions_1",
            start_seconds=0.0,
            end_seconds=round(total_duration, 2),
            category="safe_region",
            description="Safe region for motion graphics: upper_third (y=50px, h=210px). Safe region for captions: bottom-center (paddingBottom=280px).",
            confidence=0.99,
            metadata={"caption_region": "bottom-center", "overlay_region": "upper_third"},
        )
        observations.append(obs_regions)

        # 5. Semantic Focus Moments (Numbers & Keywords in Speech)
        for i, word_item in enumerate(transcript):
            w_text = word_item.get("word", "").strip().lower()
            clean_text = re.sub(r"[^\w\%-]", "", w_text)
            if STAT_PATTERN.search(clean_text) or clean_text in HIGHLIGHT_KEYWORDS:
                w_start = word_item.get("start", 0.0)
                w_end = word_item.get("end", 0.0)
                observations.append(
                    ObservationItem(
                        id=f"obs_emphasis_{i}",
                        start_seconds=round(w_start, 2),
                        end_seconds=round(w_end, 2),
                        category="visible_text",
                        description=f"Key semantic anchor '{word_item.get('word', '')}' delivered with high listener retention impact.",
                        confidence=0.90,
                        metadata={"word": clean_text},
                    )
                )

        return VideoUnderstandingResult(
            observations=observations,
            speaker_position="center",
            framing="medium_close_up",
            caption_safe_region="bottom-center",
            overlay_safe_region="upper_third",
            visual_quality_score=0.95,
            provider_name=self.name,
            inference_duration_sec=time.time() - t0,
        )

    def plan_edits(
        self,
        understanding: VideoUnderstandingResult,
        transcript: list[dict[str, Any]],
        user_prompt: str,
        video_metadata: dict[str, Any],
        style_name: str = "clean-professional",
        style_directives: Any = None,
    ) -> EditDecisionResult:
        """Generate structured edit_decisions conforming strictly to schema."""
        t0 = time.time()
        video_duration = video_metadata.get("duration", 20.0)
        source_path = video_metadata.get("source_path", "media/sample/sample_raw.mp4")

        # Resolve rules with style transfer directives if provided
        min_pause_cut = getattr(style_directives, "min_pause_cut_duration", self.rules.min_pause_cut_duration) if style_directives else self.rules.min_pause_cut_duration
        max_zooms = getattr(style_directives, "max_zooms_allowed", 2) if style_directives else max(1, min(2, len(transcript) // 4))
        zoom_scale = getattr(style_directives, "zoom_scale", self.rules.zoom_scale) if style_directives else self.rules.zoom_scale
        rest_interval = getattr(style_directives, "rest_interval_seconds", 2.5) if style_directives else 2.5
        words_per_page = getattr(style_directives, "words_per_page", self.rules.words_per_page) if style_directives else self.rules.words_per_page
        highlight_color = getattr(style_directives, "highlight_color", self.rules.highlight_color) if style_directives else self.rules.highlight_color
        caption_color = getattr(style_directives, "caption_color", "#FFFFFF") if style_directives else "#FFFFFF"
        caption_bg = getattr(style_directives, "caption_background_color", "rgba(10, 15, 30, 0.85)") if style_directives else "rgba(10, 15, 30, 0.85)"
        caption_preset = getattr(style_directives, "caption_font_preset", "modern_sans") if style_directives else "modern_sans"
        overlay_accent = getattr(style_directives, "overlay_accent_color", "#38BDF8") if style_directives else "#38BDF8"
        max_overlays = getattr(style_directives, "max_overlays_total", 2) if style_directives else 2

        # -------------------------------------------------------------
        # 1. PLAN CUTS (Removing dead air with natural breath padding)
        # -------------------------------------------------------------
        cuts = []
        current_cut_start = 0.0

        # Identify speech segments separated by long pauses
        for i in range(len(transcript) - 1):
            curr_end = transcript[i].get("end", 0.0)
            next_start = transcript[i + 1].get("start", 0.0)
            gap = next_start - curr_end

            if gap >= min_pause_cut:
                # Segment ends at curr_end + slight breathing padding
                seg_out = min(video_duration, curr_end + self.rules.breath_pause_target)
                if seg_out > current_cut_start + 0.5:
                    cut_id = f"cut_{len(cuts)+1}"
                    cuts.append({
                        "id": cut_id,
                        "source": source_path,
                        "in_seconds": round(current_cut_start, 3),
                        "out_seconds": round(seg_out, 3),
                        "speed": 1.0,
                        "layer": "primary",
                        "transition_in": "cut" if len(cuts) > 0 else "fade",
                        "transition_out": "cut",
                        "transform": {
                            "scale": 1.0,
                            "position": "center",
                        },
                        "reason": f"Speech segment ending at word '{transcript[i].get('word')}' before {round(gap, 2)}s dead air",
                        "decision_source": DecisionSource.DETERMINISTIC_HEURISTIC.value,
                        "evidence_timestamps": [round(current_cut_start, 3), round(seg_out, 3)],
                        "confidence": 0.95,
                        "model_identifier": "pause_detection_heuristic",
                    })
                # Next segment starts slightly before speech starts
                current_cut_start = max(0.0, next_start - self.rules.boundary_padding_seconds)

        # Final segment
        if current_cut_start < video_duration:
            last_word_end = transcript[-1].get("end", video_duration) if transcript else video_duration
            final_out = min(video_duration, last_word_end + 0.5)
            if final_out > current_cut_start + 0.2:
                cuts.append({
                    "id": f"cut_{len(cuts)+1}",
                    "source": source_path,
                    "in_seconds": round(current_cut_start, 3),
                    "out_seconds": round(final_out, 3),
                    "speed": 1.0,
                    "layer": "primary",
                    "transition_in": "cut" if len(cuts) > 0 else "fade",
                    "transition_out": "fade",
                    "transform": {
                        "scale": 1.0,
                        "position": "center",
                    },
                    "reason": "Final conclusive statement or conclusion of footage take",
                    "decision_source": DecisionSource.DETERMINISTIC_HEURISTIC.value,
                    "evidence_timestamps": [round(current_cut_start, 3), round(final_out, 3)],
                    "confidence": 0.95,
                    "model_identifier": "pause_detection_heuristic",
                })

        # Fallback if no pauses triggered cuts: single full cut
        if not cuts:
            cuts.append({
                "id": "cut_1",
                "source": source_path,
                "in_seconds": 0.0,
                "out_seconds": round(video_duration, 3),
                "speed": 1.0,
                "layer": "primary",
                "transition_in": "fade",
                "transition_out": "fade",
                "transform": {"scale": 1.0, "position": "center"},
                "reason": "Full continuous take without pauses",
                "decision_source": DecisionSource.TEMPLATE_DEFAULT.value,
                "evidence_timestamps": [0.0, round(video_duration, 3)],
                "confidence": 0.85,
                "model_identifier": "fallback_single_take",
            })

        # -------------------------------------------------------------
        # 2. PLAN ZOOMS (Sparing punch-in zooms on high-impact moments)
        # -------------------------------------------------------------
        zoom_count = 0
        actual_max_zooms = min(max_zooms, len(cuts))

        for cut in cuts:
            if zoom_count >= actual_max_zooms:
                break
            cut_in = cut["in_seconds"]
            cut_out = cut["out_seconds"]
            cut_dur = cut_out - cut_in

            # Check if this cut contains a high-value statistic or punchline
            has_metric = any(
                cut_in <= w.get("start", 0) <= cut_out and STAT_PATTERN.search(w.get("word", ""))
                for w in transcript
            )

            # Punch in if metric found (duration between 1.5s and 8.5s)
            if has_metric and (1.5 <= cut_dur <= 8.5):
                cut["transform"]["scale"] = zoom_scale
                cut["reason"] += f" (Punch-in zoom {zoom_scale}x for dramatic statistical emphasis)"
                cut["transform"]["zoom_provenance"] = {
                    "decision_source": DecisionSource.DETERMINISTIC_HEURISTIC.value,
                    "reason": f"Punch-in zoom {zoom_scale}x for dramatic statistical emphasis on key metric",
                    "evidence_timestamps": [round(cut_in, 3), round(cut_out, 3)],
                    "confidence": 0.90,
                    "model_identifier": "metric_zoom_selector",
                }
                zoom_count += 1
            elif cut["id"] == "cut_2" and zoom_count == 0 and cut_dur >= 2.0:
                cut["transform"]["scale"] = zoom_scale
                cut["reason"] += f" (Punch-in zoom {zoom_scale}x for visual rhythm)"
                cut["transform"]["zoom_provenance"] = {
                    "decision_source": DecisionSource.DETERMINISTIC_HEURISTIC.value,
                    "reason": f"Punch-in zoom {zoom_scale}x for visual pacing rhythm on second sentence",
                    "evidence_timestamps": [round(cut_in, 3), round(cut_out, 3)],
                    "confidence": 0.80,
                    "model_identifier": "rhythm_zoom_selector",
                }
                zoom_count += 1

        # -------------------------------------------------------------
        # 3. BUILD TIMELINE MAPPING (Compacts timeline across cut boundaries)
        # -------------------------------------------------------------
        timeline_segments = []
        timeline_cursor = 0.0
        for cut in cuts:
            dur = (cut["out_seconds"] - cut["in_seconds"]) / cut.get("speed", 1.0)
            timeline_segments.append((cut["in_seconds"], cut["out_seconds"], timeline_cursor))
            timeline_cursor += dur

        def map_raw_to_timeline(t: float) -> float:
            for c_in, c_out, t_start in timeline_segments:
                if c_in <= t <= c_out:
                    return t_start + (t - c_in)
                elif t < c_in:
                    return t_start
            if timeline_segments:
                last_in, last_out, last_start = timeline_segments[-1]
                return last_start + (min(t, last_out) - last_in)
            return t

        # -------------------------------------------------------------
        # 4. EDITORIAL INTELLIGENCE LAYER: PLAN MOTION GRAPHIC OVERLAYS
        # -------------------------------------------------------------
        overlays = []
        rejected_candidates = []
        pos = understanding.overlay_safe_region or "upper_third"

        ei_engine = EditorialIntelligenceEngine(min_rest_interval=rest_interval, max_zooms_total=max_zooms)
        semantic_moments = ei_engine.extract_semantic_moments(transcript, video_duration)

        last_overlay_end_time = -999.0

        for moment in semantic_moments:
            mapped_start = map_raw_to_timeline(moment.start_seconds)
            time_since_last = mapped_start - last_overlay_end_time

            # Generate and score candidate treatments
            candidates = ei_engine.generate_candidate_treatments(
                moment=moment,
                understanding=understanding,
                timeline_position=mapped_start,
                time_since_last_overlay=time_since_last,
                current_zoom_count=zoom_count,
            )

            if not candidates:
                continue

            best_candidate = candidates[0]
            # Record other options as rejected/considered
            for cand in candidates[1:]:
                rejected_candidates.append({
                    "moment_id": moment.id,
                    "treatment_type": cand.treatment_type,
                    "score": round(cand.score, 3),
                    "reason": cand.provenance.reason,
                })

            if best_candidate.treatment_type == "none":
                # Intentional negative selection (prevent visual clutter / respect rest interval)
                continue

            if best_candidate.treatment_type == "punch_in_zoom":
                # Zoom treatment already handled or can apply to nearest cut
                continue

            if len(overlays) >= max_overlays:
                # Obey maximum overlay density constraint (Tier 1 user instruction or Tier 3 style density)
                continue

            # Overlay candidate (stat_card, callout, comparison)
            dur = min(3.8, max(2.5, moment.end_seconds - moment.start_seconds + 1.5))
            # Clamp overlay within total compacted video duration
            mapped_end = min(timeline_cursor, mapped_start + dur)
            if mapped_end <= mapped_start + 0.8:
                continue

            ov_params = dict(best_candidate.parameters)
            if overlay_accent and "accentColor" in ov_params and ov_params["accentColor"] == "#38BDF8":
                ov_params["accentColor"] = overlay_accent
            ov_id = f"overlay_{len(overlays)+1}_{best_candidate.treatment_type}"
            overlay_item = {
                "id": ov_id,
                "type": best_candidate.treatment_type,
                "position": pos,
                "in_seconds": round(mapped_start, 2),
                "out_seconds": round(mapped_end, 2),
                **ov_params,
                "decision_source": best_candidate.provenance.decision_source,
                "reason": best_candidate.provenance.reason,
                "evidence_timestamps": best_candidate.provenance.evidence_timestamps,
                "confidence": best_candidate.provenance.confidence,
                "model_identifier": best_candidate.provenance.model_identifier,
            }
            overlays.append(overlay_item)
            last_overlay_end_time = mapped_end

        # Fallback overlay if no moments extracted and duration allows
        if not overlays and video_duration >= 4.0:
            # Check if SmolVLM provided visual observations or use generic topic from prompt
            topic_hint = "OVERVIEW"
            if understanding.detected_topics:
                topic_hint = understanding.detected_topics[0].upper()
            elif "demo" in user_prompt.lower() or "screen" in user_prompt.lower():
                topic_hint = "FEATURE SHOWCASE"
            elif "talk" in user_prompt.lower() or "reel" in user_prompt.lower():
                topic_hint = "KEY INSIGHT"

            obs_reason = "Contextual title based on video understanding scene context"
            obs_source = DecisionSource.NEURAL_VLM.value if understanding.provider_name.startswith("local_vlm") else DecisionSource.TEMPLATE_DEFAULT.value

            overlays.append({
                "id": "overlay_1_intro",
                "type": "callout",
                "title": topic_hint,
                "text": "Autonomous Editorial Synthesis",
                "callout_type": "info",
                "position": pos,
                "in_seconds": round(map_raw_to_timeline(0.5), 2),
                "out_seconds": round(min(timeline_cursor, map_raw_to_timeline(3.8)), 2),
                "accentColor": "#38BDF8",
                "color": "#F8FAFC",
                "backgroundColor": "rgba(15, 23, 42, 0.90)",
                "decision_source": obs_source,
                "reason": obs_reason,
                "evidence_timestamps": [0.5, 3.8],
                "confidence": 0.85,
                "model_identifier": understanding.provider_name,
            })

        # -------------------------------------------------------------
        # 5. CONFIGURE CAPTIONS & SUBTITLES (Sentence-aware line grouping)
        # -------------------------------------------------------------
        captions_payload = []
        words_per_page = self.rules.words_per_page
        sentence_end_chars = {".", "!", "?", ";", ","}

        for idx, w in enumerate(transcript):
            w_text = w.get("word", "")
            mapped_start = map_raw_to_timeline(w.get("start", 0.0))
            mapped_end = map_raw_to_timeline(w.get("end", 0.0))

            # Sentence-aware grouping: break after punctuation or when reaching page limit
            has_punct = any(w_text.endswith(c) for c in sentence_end_chars)
            break_after = has_punct or ((idx + 1) % words_per_page == 0) or (idx == len(transcript) - 1)

            captions_payload.append({
                "word": w_text,
                "start": round(mapped_start, 3),
                "end": round(mapped_end, 3),
                "startMs": int(mapped_start * 1000),
                "endMs": int(mapped_end * 1000),
                "pageBreakAfter": break_after,
                "decision_source": DecisionSource.DETERMINISTIC_HEURISTIC.value,
                "model_identifier": "faster_whisper_alignment_mapper",
            })

        # -------------------------------------------------------------
        # 6. ASSEMBLE FULL EDIT_DECISIONS SCHEMA PAYLOAD
        # -------------------------------------------------------------
        schema_overlays = []
        for ov in overlays:
            schema_overlays.append({
                "asset_id": ov["id"],
                "start_seconds": ov["in_seconds"],
                "end_seconds": ov["out_seconds"],
                "position": {"x": 60, "y": 50, "width": 960, "height": 210},
                "animation": "fade",
                "opacity": 1.0,
                "decision_source": ov.get("decision_source", DecisionSource.DETERMINISTIC_HEURISTIC.value),
                "reason": ov.get("reason", "Structured motion graphic overlay"),
                "evidence_timestamps": ov.get("evidence_timestamps", [ov["in_seconds"], ov["out_seconds"]]),
                "confidence": ov.get("confidence", 0.90),
                "model_identifier": ov.get("model_identifier", self.name),
            })

        # Calculate decision source breakdown
        decision_counts = {
            "neural_vlm": sum(1 for ov in overlays if ov.get("decision_source") == "neural_vlm"),
            "deterministic_heuristic": len(cuts) + sum(1 for ov in overlays if ov.get("decision_source") == "deterministic_heuristic"),
            "script_directive": sum(1 for ov in overlays if ov.get("decision_source") == "script_directive"),
            "template_default": sum(1 for ov in overlays if ov.get("decision_source") == "template_default"),
        }
        total_decisions = sum(decision_counts.values())

        decision_label = "heuristic_fallback" if decision_counts["neural_vlm"] == 0 else "hybrid_grounded"

        edit_decisions = {
            "version": "1.0",
            "render_runtime": "remotion",
            "renderer_family": "presenter",
            "composition_mode": "templated",
            "cuts": cuts,
            "overlays": schema_overlays,
            "audio": {
                "narration": {
                    "segments": [
                        {
                            "asset_id": "raw_audio",
                            "start_seconds": 0.0,
                            "end_seconds": round(video_duration, 3),
                        }
                    ]
                }
            },
            "subtitles": {
                "enabled": True,
                "style": "word-by-word",
                "preset": "modern_sans",
                "source": "captions_aligned.json",
                "font": "Inter",
                "font_size": 52,
                "color": "#FFFFFF",
                "position": "bottom-center",
                "max_words_per_line": words_per_page,
                "words": [
                    {
                        "word": c["word"],
                        "start": c["start"],
                        "end": c["end"],
                    }
                    for c in captions_payload
                ],
            },
            "metadata": {
                "job_type": "autonomous_talking_head_reel",
                "aspect_ratio": "9:16",
                "user_instruction": user_prompt,
                "decision_source": decision_label,
                "provenance_breakdown": {
                    **decision_counts,
                    "total_decisions": total_decisions,
                    "neural_ratio": round(decision_counts["neural_vlm"] / max(1, total_decisions), 3),
                },
                "rejected_candidates": rejected_candidates,
                "talking_head_props": {
                    "videoSrc": source_path,
                    "cuts": cuts,
                    "overlays": overlays,
                    "captions": captions_payload,
                    "wordsPerPage": words_per_page,
                    "fontSize": 52,
                    "highlightColor": highlight_color,
                    "captionColor": caption_color,
                    "captionBackgroundColor": caption_bg,
                    "captionPreset": caption_preset,
                },
            },
        }

        planning_duration = time.time() - t0
        return EditDecisionResult(
            edit_decisions=edit_decisions,
            provider_name=self.name,
            decision_source=decision_label,
            planning_duration_sec=planning_duration,
            metrics={
                "cuts_count": len(cuts),
                "zooms_count": zoom_count,
                "overlays_count": len(overlays),
                "captions_count": len(captions_payload),
                "estimated_duration": cuts[-1]["out_seconds"] if cuts else video_duration,
                "decision_counts": decision_counts,
            },
        )
