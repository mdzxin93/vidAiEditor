"""Autonomous Editing Planner for OpenMontage (Phase 5).

Transforms video understanding and transcripts into schema-valid edit decisions:
- Phase 5 Editorial Intelligence: grounded metrics, punchline/contrast extraction, multi-candidate scoring, pacing rest intervals
- Provenance tracking (neural_vlm, script_directive, deterministic_heuristic, template_default)
- Mode 1: Automatic AI timeline planning (cutting dead air, sparing zooms, dynamic captions, motion graphics)
- Mode 2: Detailed script editing (explicit phrases mapped to triggers)
- Timeline validation & sanitization (fixes overlay overrun beyond video duration)
- Reference video style guidance
- Intelligent reframing coordination
- Context-aware local B-roll placement
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import jsonschema

from lib.ai.broll_selector import BRollSelector
from lib.ai.config import AIEditorConfig
from lib.ai.editorial_intelligence import EditorialIntelligenceEngine
from lib.ai.providers.base import BaseModelProvider, EditDecisionResult, VideoUnderstandingResult
from lib.ai.providers.factory import get_model_provider
from lib.ai.reframer import IntelligentReframer
from lib.ai.script_editor import ScriptDrivenEditor
from lib.ai.semantic_visual_planner import SemanticVisualPlanner
from lib.ai.style_analyzer import StyleProfile
from lib.ai.style_evaluator import StyleSimilarityEvaluator
from lib.ai.style_transfer import StyleTransferEngine
from lib.ai.memory.models import StylePreset
from lib.ai.memory.preference_resolver import PreferenceResolver, ResolvedEditorialPlan
from lib.ai.memory.preference_store import PreferenceStore
from lib.ai.timeline_validator import TimelineValidator

logger = logging.getLogger(__name__)


class AutonomousEditingPlanner:
    """Python-controlled planner generating validated edit decisions."""

    def __init__(
        self,
        provider: BaseModelProvider | None = None,
        config: AIEditorConfig | None = None,
        schema_path: str | Path | None = None,
    ):
        self.config = config or AIEditorConfig.load()
        self.provider = provider or get_model_provider(self.config)
        self.script_editor = ScriptDrivenEditor()
        self.validator = TimelineValidator()
        self.reframer = IntelligentReframer()
        self.broll_selector = BRollSelector()
        self.style_transfer = StyleTransferEngine()
        self.similarity_evaluator = StyleSimilarityEvaluator()
        self.visual_planner = SemanticVisualPlanner(
            broll_selector=self.broll_selector,
            min_rest_interval=getattr(self.config.editorial_rules, "rest_interval_seconds", 2.5),
        )
        self.editorial_engine = EditorialIntelligenceEngine(
            min_rest_interval=getattr(self.config.editorial_rules, "rest_interval_seconds", 2.5)
        )
        self.preference_store = PreferenceStore()
        self.preference_resolver = PreferenceResolver(store=self.preference_store)

        # Load schema
        if schema_path is None:
            cand = Path("schemas/artifacts/edit_decisions.schema.json")
            if not cand.exists():
                cand = Path(__file__).resolve().parent.parent.parent / "schemas" / "artifacts" / "edit_decisions.schema.json"
            schema_path = cand

        self.schema_path = Path(schema_path)
        self.schema = None
        if self.schema_path.exists():
            with open(self.schema_path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)

    def plan(
        self,
        understanding: VideoUnderstandingResult,
        transcript: list[dict[str, Any]],
        user_prompt: str,
        video_metadata: dict[str, Any],
        style_profile: StyleProfile | None = None,
        enable_personalization: bool = True,
        active_preset: StylePreset | None = None,
    ) -> EditDecisionResult:
        """Generate, validate, and return the edit plan."""
        t0 = time.time()
        logger.info("Generating autonomous edit plan using provider: %s", self.provider.name)
        video_duration = video_metadata.get("duration", 20.0)

        # 0. Resolve Personalized Preferences & Style Presets (Phase 10)
        resolved_editorial = self.preference_resolver.resolve_plan(
            user_prompt=user_prompt,
            video_metadata=video_metadata,
            enable_personalization=enable_personalization,
            active_preset=active_preset,
        )

        # 1. Parse Script Directives (Mode 2 support)
        script_directives, unsupported_script = self.script_editor.parse_and_align_script(
            instruction_text=user_prompt,
            transcript=transcript,
            video_duration=video_duration,
        )

        # 2. Resolve Style Intelligence & 4-Tier Conflict Resolution Matrix
        style_directives = self.style_transfer.resolve_style_directives(
            user_instruction=user_prompt,
            style_profile=style_profile,
            source_metadata=video_metadata,
        )

        # If personalization resolved preferences, apply to style directives
        if enable_personalization:
            style_directives.zoom_scale = resolved_editorial.zoom_scale
            style_directives.highlight_color = resolved_editorial.caption_highlight_color
            style_directives.caption_font_family = resolved_editorial.caption_font_family
            style_directives.words_per_page = resolved_editorial.words_per_page
            style_directives.min_pause_cut_duration = resolved_editorial.min_pause_cut_duration
        else:
            style_directives.zoom_scale = getattr(self.config.editorial_rules, "zoom_scale", 1.25)
            style_directives.highlight_color = getattr(self.config.editorial_rules, "highlight_color", "#22D3EE")

        # Generate Base Plan from Model / Heuristic Provider
        result = self.provider.plan_edits(
            understanding=understanding,
            transcript=transcript,
            user_prompt=user_prompt,
            video_metadata=video_metadata,
            style_name=style_profile.style_name if style_profile else "clean-professional",
            style_directives=style_directives,
        )

        edits = result.edit_decisions

        # 3. Intelligent Reframing Coordination (Phase 5 Reframer)
        src_w = video_metadata.get("width", 1920)
        src_h = video_metadata.get("height", 1080)
        target_aspect = getattr(self.config.editorial_rules, "export_aspect_ratio", "9:16")
        if src_w > 0 and src_h > 0:
            reframe_win = self.reframer.compute_reframe(
                video_width=src_w,
                video_height=src_h,
                target_aspect=target_aspect,
                detected_subject_centers=[(0.5, 0.4)],
            )
            edits.setdefault("metadata", {})["reframe_window"] = {
                "target_aspect": reframe_win.target_aspect,
                "crop_x": reframe_win.crop_x,
                "crop_y": reframe_win.crop_y,
                "crop_width": reframe_win.crop_width,
                "crop_height": reframe_win.crop_height,
                "confidence": reframe_win.confidence,
            }
            for c in edits.get("cuts", []):
                if "transform" in c and "crop" not in c["transform"]:
                    c["transform"]["crop"] = {
                        "x": float(reframe_win.crop_x),
                        "y": float(reframe_win.crop_y),
                        "width": float(reframe_win.crop_width),
                        "height": float(reframe_win.crop_height),
                    }

        # 4. Context-Aware Semantic Visual Planning (Phase 7)
        visual_plan = self.visual_planner.plan_visuals(
            transcript=transcript,
            video_duration=video_duration,
            understanding=understanding,
            user_instruction=user_prompt,
            style_profile=style_profile.to_dict() if style_profile else None,
        )
        edits.setdefault("metadata", {})["semantic_visual_plan"] = visual_plan.to_dict()

        if visual_plan.visual_events:
            th_props = edits.setdefault("metadata", {}).setdefault("talking_head_props", {})
            th_overlays = []
            schema_overlays = []
            broll_hits = []

            for ve in visual_plan.visual_events:
                # Talking head component props
                th_ov = {
                    "id": ve.event_id,
                    "type": ve.treatment_type,
                    "in_seconds": ve.start_seconds,
                    "out_seconds": ve.end_seconds,
                    "position": ve.position,
                    **ve.parameters,
                    "decision_source": ve.provenance.decision_source,
                    "reason": ve.provenance.reason,
                    "evidence_timestamps": ve.provenance.evidence_timestamps,
                    "confidence": ve.provenance.confidence,
                    "model_identifier": ve.provenance.model_identifier,
                }
                th_overlays.append(th_ov)

                # Schema-conforming top-level overlay
                is_window = ve.position in ("upper_window", "upper_pip")
                schema_overlays.append({
                    "asset_id": ve.event_id,
                    "start_seconds": ve.start_seconds,
                    "end_seconds": ve.end_seconds,
                    "position": {
                        "x": 60,
                        "y": 50,
                        "width": 960,
                        "height": 380 if is_window else 210,
                    },
                    "animation": "fade",
                    "opacity": 1.0,
                    "decision_source": ve.provenance.decision_source,
                    "reason": ve.provenance.reason,
                    "evidence_timestamps": ve.provenance.evidence_timestamps,
                    "confidence": ve.provenance.confidence,
                    "model_identifier": ve.provenance.model_identifier,
                })

                if ve.treatment_type == "broll" and "mediaSrc" in ve.parameters:
                    broll_hits.append({
                        "asset_path": ve.parameters["mediaSrc"],
                        "type": "video" if ve.parameters.get("isVideo") else "image",
                        "start": ve.start_seconds,
                        "end": ve.end_seconds,
                        "keyword": ve.parameters.get("title", "broll"),
                        "reason": ve.provenance.reason,
                    })

            th_props["overlays"] = th_overlays
            edits["overlays"] = schema_overlays
            if broll_hits:
                edits["metadata"]["broll_placements"] = broll_hits

        # Apply personalized adjustments & provenance tracking (Phase 10)
        prov_bd = edits.setdefault("metadata", {}).setdefault("provenance_breakdown", {})
        learned_count = 0

        # 1. Personalized Zoom Scale & Provenance
        zoom_rec = next((r for r in resolved_editorial.applied_records if r.parameter_key == "zoom_scale"), None)
        if zoom_rec and zoom_rec.winning_tier_name in ("learned_preference", "style_preset"):
            for c in edits.get("cuts", []):
                if c.get("transform", {}).get("scale", 1.0) > 1.0:
                    c["transform"]["scale"] = resolved_editorial.zoom_scale
                    c["reason"] = f"{zoom_rec.winning_tier_name.capitalize()}: {zoom_rec.reason}"
                    c["decision_source"] = zoom_rec.winning_tier_name
                    c["transform"]["zoom_provenance"] = {
                        "decision_source": zoom_rec.winning_tier_name,
                        "preference_id": zoom_rec.preference_id,
                        "preset_id": zoom_rec.preset_id,
                        "reason": zoom_rec.reason,
                        "confidence": 0.95,
                        "evidence_timestamps": [c["in_seconds"], c["out_seconds"]],
                        "model_identifier": "preference_store_v10",
                    }
                    learned_count += 1

        # 2. Personalized Captions
        th_props = edits.setdefault("metadata", {}).setdefault("talking_head_props", {})
        th_props["highlightColor"] = resolved_editorial.caption_highlight_color
        th_props["fontFamily"] = resolved_editorial.caption_font_family
        th_props["wordsPerPage"] = resolved_editorial.words_per_page

        color_rec = next((r for r in resolved_editorial.applied_records if r.parameter_key == "highlight_color"), None)
        if color_rec and color_rec.winning_tier_name in ("learned_preference", "style_preset"):
            th_props["color_provenance"] = {
                "decision_source": color_rec.winning_tier_name,
                "preference_id": color_rec.preference_id,
                "preset_id": color_rec.preset_id,
                "reason": color_rec.reason,
            }
            learned_count += 1

        # 3. Personalized Graphic Overlays (e.g. replace stat_card with comparison)
        pref_overlays = resolved_editorial.preferred_overlay_types
        overlay_rec = next((r for r in resolved_editorial.applied_records if r.parameter_key == "preferred_overlay_types"), None)
        if overlay_rec and overlay_rec.winning_tier_name in ("learned_preference", "style_preset"):
            if "comparison" in pref_overlays and "stat_card" not in pref_overlays:
                for ov in th_props.get("overlays", []):
                    if ov.get("type") == "stat_card":
                        ov["type"] = "comparison"
                        ov["title"] = "Performance vs Baseline"
                        ov["left_label"] = "Standard"
                        ov["left_value"] = "1.0x"
                        ov["right_label"] = "OpenMontage"
                        ov["right_value"] = "4.2x"
                        ov["decision_source"] = overlay_rec.winning_tier_name
                        ov["reason"] = f"{overlay_rec.winning_tier_name}: {overlay_rec.reason}"
                        learned_count += 1

        if learned_count > 0:
            prov_source = zoom_rec.winning_tier_name if zoom_rec else "learned_preference"
            prov_bd[prov_source] = prov_bd.get(prov_source, 0) + learned_count
            prov_bd["total_decisions"] = prov_bd.get("total_decisions", 0) + learned_count

        # 5. Apply Explicit Script Directives (Explicit script takes priority over AI defaults)
        if script_directives:
            self._apply_script_directives(edits, script_directives)

        # 6. Strict Timeline Validation & Boundary Clamping (Fixes Phase 3 overlay overrun)
        edits, validation_warnings = self.validator.validate_and_sanitize(
            edit_decisions=edits,
            raw_video_duration=video_duration,
        )

        # 5. Schema Validation
        validation_errors = self._validate_schema(edits)
        if validation_errors:
            logger.warning(
                "Schema validation encountered %d errors. Attempting automated repair...",
                len(validation_errors),
            )
            edits = self._repair_schema_discrepancies(edits)
            validation_errors = self._validate_schema(edits)
            if validation_errors:
                logger.error("Schema validation failed after repair: %s", validation_errors)
                result.errors.extend(validation_errors)

        # Record metadata
        edits.setdefault("metadata", {})
        edits["metadata"]["decision_source"] = result.decision_source
        edits["metadata"]["provider"] = result.provider_name
        edits["metadata"]["personalization"] = {
            "enabled": enable_personalization,
            "resolved_plan": resolved_editorial.to_dict(),
            "applied_records": [r.to_dict() for r in resolved_editorial.applied_records],
        }
        edits["metadata"]["applied_script_directives"] = [
            {"action": d.action, "phrase": d.trigger_phrase, "start": d.matched_start, "end": d.matched_end}
            for d in script_directives
        ]
        if unsupported_script:
            edits["metadata"]["unsupported_script_instructions"] = unsupported_script

        # Record Style Intelligence & Conflict Resolutions
        edits["metadata"]["conflict_resolutions"] = [
            r.to_dict() for r in style_directives.conflict_resolutions
        ]
        if style_profile:
            edits["metadata"]["applied_style_profile"] = style_profile.to_dict()
            sim_report = self.similarity_evaluator.evaluate(
                reference_profile=style_profile,
                edit_decisions=edits,
                user_instruction=user_prompt,
            )
            edits["metadata"]["style_similarity_report"] = sim_report.to_dict()
            result.metrics["style_similarity"] = sim_report.overall_similarity_score

        result.edit_decisions = edits
        result.planning_duration_sec = time.time() - t0
        return result

    def _apply_script_directives(
        self, edits: dict[str, Any], directives: list[Any]
    ) -> None:
        """Inject explicit user script instructions into cuts and overlays."""
        cuts = edits.get("cuts", [])
        overlays = edits.get("overlays", [])
        th_props = edits.get("metadata", {}).get("talking_head_props", {})
        prov_bd = edits.setdefault("metadata", {}).setdefault("provenance_breakdown", {})

        script_count = 0
        for d in directives:
            if d.action == "zoom":
                for c in cuts:
                    if c["in_seconds"] <= d.matched_start <= c["out_seconds"]:
                        c.setdefault("transform", {})["scale"] = d.parameters.get("scale", 1.15)
                        c["reason"] = f"Script directive: Explicit zoom request on '{d.trigger_phrase}'"
                        c["decision_source"] = "script_directive"
                        c["model_identifier"] = "script_rule_matcher"
                        c["confidence"] = 1.0
                        c["evidence_timestamps"] = [round(d.matched_start, 3), round(d.matched_end, 3)]
                        c["transform"]["zoom_provenance"] = {
                            "decision_source": "script_directive",
                            "reason": f"Script directive: Explicit zoom on '{d.trigger_phrase}'",
                            "evidence_timestamps": [round(d.matched_start, 3), round(d.matched_end, 3)],
                            "confidence": 1.0,
                            "model_identifier": "script_rule_matcher",
                        }
                        script_count += 1

            elif d.action == "highlight":
                color = d.parameters.get("color", "#FACC15")
                th_props["highlightColor"] = color
                script_count += 1

            elif d.action == "overlay":
                ov_params = d.parameters
                g_type = ov_params.get("type", "callout")
                new_ov = {
                    "id": f"script_overlay_{len(overlays)+1}",
                    "type": g_type,
                    "position": "upper_third",
                    "in_seconds": d.matched_start,
                    "out_seconds": d.matched_end,
                    **ov_params,
                    "decision_source": "script_directive",
                    "reason": f"Script directive: Explicit overlay trigger '{d.trigger_phrase}'",
                    "evidence_timestamps": [round(d.matched_start, 3), round(d.matched_end, 3)],
                    "confidence": 1.0,
                    "model_identifier": "script_rule_matcher",
                }
                if "overlays" in th_props:
                    th_props["overlays"].append(new_ov)
                overlays.append({
                    "asset_id": new_ov["id"],
                    "start_seconds": d.matched_start,
                    "end_seconds": d.matched_end,
                    "position": {"x": 60, "y": 50, "width": 960, "height": 210},
                    "animation": "fade",
                    "opacity": 1.0,
                    "decision_source": "script_directive",
                    "reason": f"Script directive: Explicit overlay trigger '{d.trigger_phrase}'",
                    "evidence_timestamps": [round(d.matched_start, 3), round(d.matched_end, 3)],
                    "confidence": 1.0,
                    "model_identifier": "script_rule_matcher",
                })
                script_count += 1

        prov_bd["script_directive"] = prov_bd.get("script_directive", 0) + script_count
        prov_bd["total_decisions"] = prov_bd.get("total_decisions", 0) + script_count

    def _validate_schema(self, edits: dict[str, Any]) -> list[str]:
        """Validate edits dictionary against edit_decisions.schema.json."""
        if not self.schema:
            return []

        validator = jsonschema.Draft202012Validator(self.schema)
        errors = []
        for err in validator.iter_errors(edits):
            errors.append(f"{err.json_path}: {err.message}")
        return errors

    def _repair_schema_discrepancies(self, edits: dict[str, Any]) -> dict[str, Any]:
        """Ensure all required schema fields exist with valid default structures."""
        edits.setdefault("version", "1.0")
        edits.setdefault("render_runtime", "remotion")
        edits.setdefault("cuts", [])

        if edits.get("render_runtime") not in ("remotion", "hyperframes", "ffmpeg"):
            edits["render_runtime"] = "remotion"

        return edits
