"""FastAPI Routes for Intelligent Editing Memory & Personalization (Phase 10).

Provides REST APIs for:
1. Learned Editing Preferences (CRUD, toggle, persistent deletion, reset)
2. Approval-Based Corrections Lifecycle (Audit log, approve for future, keep one-time, reject)
3. Reusable Style Presets (Educational Explainer, High-Energy Short, Minimal, Custom)
4. Safe JSON Export & Import (strictly validated, no code execution, path-safe)
5. Structured Opt-in Training Dataset Exporter (Phase 10 Section 11)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lib.ai.memory.models import (
    ApprovalStatus,
    CorrectionRecord,
    EditingPreference,
    EditingPreferenceCategory,
    StylePreset,
)
from lib.ai.memory.preference_store import PreferenceStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preferences", tags=["Editing Memory & Personalization"])
store = PreferenceStore()


# ---------------------------------------------------------------------------
# Request & Response Models
# ---------------------------------------------------------------------------

class UpdatePreferenceRequest(BaseModel):
    preferred_value: Optional[Any] = None
    enabled: Optional[bool] = None
    confidence: Optional[float] = None
    context_constraints: Optional[dict[str, Any]] = None
    description: Optional[str] = None


class ApproveCorrectionRequest(BaseModel):
    apply_to_future: bool = Field(True, description="True: save to memory for future projects; False: one-time project only")
    context_constraints: Optional[dict[str, Any]] = Field(None, description="Optional constraints e.g. {'target_aspect': '9:16'}")
    preferred_value_override: Optional[Any] = Field(None, description="Optional override of corrected value")


class RecordCorrectionRequest(BaseModel):
    project_id: str
    category: str
    parameter_key: str
    original_ai_value: Any
    user_corrected_value: Any
    editing_context: dict[str, Any] = Field(default_factory=dict)
    approval_status: str = Field(ApprovalStatus.PENDING_REVIEW.value)
    original_decision_provenance: dict[str, Any] = Field(default_factory=dict)
    user_note: Optional[str] = None


class UpdateSettingsRequest(BaseModel):
    personalization_enabled: Optional[bool] = None
    active_preset_id: Optional[str] = None
    preference_influence_weight: Optional[float] = None
    auto_learn_from_approved_only: Optional[bool] = None


class StylePresetCreateRequest(BaseModel):
    preset_id: str
    title: str
    description: str = ""
    target_aspect: str = "9:16"
    caption_preset: str = "word_highlight"
    caption_font_family: str = "Inter, sans-serif"
    caption_font_size: int = 52
    caption_highlight_color: str = "#22D3EE"
    caption_background_color: str = "rgba(0, 0, 0, 0.65)"
    words_per_page: int = 4
    zoom_intensity: str = "standard"
    zoom_scale: float = 1.25
    cut_aggressiveness: str = "balanced"
    min_pause_cut_duration: float = 1.0
    pacing_rest_interval: float = 2.5
    graphic_density: str = "medium"
    preferred_overlay_types: list[str] = Field(default_factory=lambda: ["stat_card", "callout"])
    color_palette: dict[str, str] = Field(default_factory=lambda: {"primary": "#2563EB", "accent": "#22D3EE", "background": "#FFFFFF"})
    audio_settings: dict[str, Any] = Field(default_factory=lambda: {"bgm_enabled": True, "bgm_volume": 0.25})


class ImportPreferencesRequest(BaseModel):
    import_data: dict[str, Any]
    overwrite_existing: bool = False


# ---------------------------------------------------------------------------
# 1. Global Settings
# ---------------------------------------------------------------------------

@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    """Retrieve global personalization settings and active preset."""
    return store.get_settings()


@router.put("/settings")
async def update_settings(req: UpdateSettingsRequest) -> dict[str, Any]:
    """Update global personalization settings (e.g. on/off toggle, active preset)."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    return store.update_settings(updates)


# ---------------------------------------------------------------------------
# 2. Preferences Management (CRUD, Persistent Deletion, Reset)
# ---------------------------------------------------------------------------

@router.get("")
async def list_preferences(
    category: Optional[str] = Query(None, description="Filter by category (zoom, caption, pacing, etc.)"),
    enabled_only: bool = Query(False, description="Filter only enabled preferences"),
) -> dict[str, Any]:
    """List all stored editing preferences."""
    prefs = store.list_preferences(category=category, enabled_only=enabled_only)
    return {
        "ok": True,
        "count": len(prefs),
        "preferences": [p.to_dict() for p in prefs],
    }


@router.get("/{preference_id}")
async def get_preference(preference_id: str) -> dict[str, Any]:
    """Get a specific editing preference by ID."""
    pref = store.get_preference(preference_id)
    if not pref:
        raise HTTPException(status_code=404, detail=f"Preference '{preference_id}' not found.")
    return {"ok": True, "preference": pref.to_dict()}


@router.put("/{preference_id}")
async def update_preference(preference_id: str, req: UpdatePreferenceRequest) -> dict[str, Any]:
    """Update an existing preference's values, enabled state, or context constraints."""
    pref = store.get_preference(preference_id)
    if not pref:
        raise HTTPException(status_code=404, detail=f"Preference '{preference_id}' not found.")

    if req.preferred_value is not None:
        pref.preferred_value = req.preferred_value
    if req.enabled is not None:
        pref.enabled = req.enabled
    if req.confidence is not None:
        pref.confidence = max(0.0, min(1.0, req.confidence))
    if req.context_constraints is not None:
        pref.context_constraints = req.context_constraints
    if req.description is not None:
        pref.description = req.description

    pref.updated_at = time.time()
    store.save_preference(pref)
    return {"ok": True, "preference": pref.to_dict()}


@router.delete("/{preference_id}")
async def delete_preference(preference_id: str) -> dict[str, Any]:
    """Persistently delete an approved preference from local disk."""
    success = store.delete_preference(preference_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Preference '{preference_id}' not found.")
    return {"ok": True, "deleted_preference_id": preference_id}


@router.delete("")
async def reset_preferences() -> dict[str, Any]:
    """Factory reset: purge all learned preferences and restore default presets."""
    store.reset_all_preferences()
    return {"ok": True, "message": "All preferences purged and reset to system factory defaults."}


# ---------------------------------------------------------------------------
# 3. Corrections & Approval-Based Learning Lifecycle
# ---------------------------------------------------------------------------

@router.get("/corrections/list")
async def list_corrections(
    project_id: Optional[str] = Query(None, description="Optional project filter"),
) -> dict[str, Any]:
    """List recorded user corrections and their approval statuses."""
    corrs = store.list_corrections(project_id=project_id)
    return {
        "ok": True,
        "count": len(corrs),
        "corrections": [c.to_dict() for c in corrs],
    }


@router.post("/corrections/record")
async def record_correction(req: RecordCorrectionRequest) -> dict[str, Any]:
    """Record an edit decision modification for audit and potential approval."""
    cid = f"corr_{int(time.time() * 1000)}_{req.category}"
    rec = CorrectionRecord(
        correction_id=cid,
        project_id=req.project_id,
        category=req.category,
        parameter_key=req.parameter_key,
        original_ai_value=req.original_ai_value,
        user_corrected_value=req.user_corrected_value,
        editing_context=req.editing_context,
        approval_status=req.approval_status,
        original_decision_provenance=req.original_decision_provenance,
        user_note=req.user_note,
        timestamp=time.time(),
    )
    store.record_correction(rec)
    return {"ok": True, "correction": rec.to_dict()}


@router.post("/corrections/{correction_id}/approve")
async def approve_correction(correction_id: str, req: ApproveCorrectionRequest) -> dict[str, Any]:
    """Explicitly approve a user correction.
    
    If apply_to_future is True, promotes the correction into a learned EditingPreference.
    If apply_to_future is False, marks it as ONE_TIME for this project only.
    """
    pref = store.approve_correction(
        correction_id=correction_id,
        apply_to_future=req.apply_to_future,
        context_constraints=req.context_constraints,
    )
    return {
        "ok": True,
        "correction_id": correction_id,
        "applied_to_future": req.apply_to_future,
        "learned_preference": pref.to_dict() if pref else None,
    }


@router.post("/corrections/{correction_id}/reject")
async def reject_correction(correction_id: str) -> dict[str, Any]:
    """Explicitly reject / ignore a correction so it is never learned."""
    corrs = store.list_corrections()
    target = next((c for c in corrs if c.correction_id == correction_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Correction '{correction_id}' not found.")

    target.approval_status = ApprovalStatus.REJECTED.value
    store.record_correction(target)
    return {"ok": True, "correction_id": correction_id, "approval_status": "rejected"}


# ---------------------------------------------------------------------------
# 4. Style Preset Management
# ---------------------------------------------------------------------------

@router.get("/presets/list")
async def list_presets() -> dict[str, Any]:
    """List all available style presets (built-in and custom)."""
    presets = store.list_presets()
    return {
        "ok": True,
        "count": len(presets),
        "presets": [p.to_dict() for p in presets],
    }


@router.get("/presets/{preset_id}")
async def get_preset(preset_id: str) -> dict[str, Any]:
    """Retrieve details for a specific style preset."""
    preset = store.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")
    return {"ok": True, "preset": preset.to_dict()}


@router.post("/presets")
async def create_or_update_preset(req: StylePresetCreateRequest) -> dict[str, Any]:
    """Create a new custom style preset or update an existing user preset."""
    existing = store.get_preset(req.preset_id)
    if existing and existing.is_builtin:
        raise HTTPException(status_code=400, detail="Cannot overwrite system built-in presets. Please duplicate with a unique ID.")

    preset = StylePreset(
        preset_id=req.preset_id,
        title=req.title,
        description=req.description,
        is_builtin=False,
        target_aspect=req.target_aspect,
        caption_preset=req.caption_preset,
        caption_font_family=req.caption_font_family,
        caption_font_size=req.caption_font_size,
        caption_highlight_color=req.caption_highlight_color,
        caption_background_color=req.caption_background_color,
        words_per_page=req.words_per_page,
        zoom_intensity=req.zoom_intensity,
        zoom_scale=req.zoom_scale,
        cut_aggressiveness=req.cut_aggressiveness,
        min_pause_cut_duration=req.min_pause_cut_duration,
        pacing_rest_interval=req.pacing_rest_interval,
        graphic_density=req.graphic_density,
        preferred_overlay_types=req.preferred_overlay_types,
        color_palette=req.color_palette,
        audio_settings=req.audio_settings,
    )
    store.save_preset(preset)
    return {"ok": True, "preset": preset.to_dict()}


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str) -> dict[str, Any]:
    """Delete a custom style preset (built-ins cannot be deleted)."""
    success = store.delete_preset(preset_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Preset '{preset_id}' could not be deleted (not found or is a built-in).")
    return {"ok": True, "deleted_preset_id": preset_id}


@router.post("/presets/{preset_id}/activate")
async def activate_preset(preset_id: str) -> dict[str, Any]:
    """Set the active style preset for future autonomous editing jobs."""
    preset = store.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")
    store.update_settings({"active_preset_id": preset_id})
    return {"ok": True, "active_preset_id": preset_id, "title": preset.title}


# ---------------------------------------------------------------------------
# 5. Safe JSON Export & Import
# ---------------------------------------------------------------------------

@router.get("/export/download")
async def export_preferences() -> dict[str, Any]:
    """Export all learned preferences, presets, and global settings to JSON."""
    return store.export_data()


@router.post("/import/upload")
async def import_preferences(req: ImportPreferencesRequest) -> dict[str, Any]:
    """Validate and import preferences JSON. Strictly path-safe, zero code execution."""
    try:
        report = store.import_data(req.import_data, overwrite=req.overwrite_existing)
        return {"ok": True, "report": report}
    except Exception as e:
        logger.error("Failed to import preferences: %s", e)
        raise HTTPException(status_code=400, detail=f"Preference import failed: {e}")


# ---------------------------------------------------------------------------
# 6. Future Model Training Dataset Exporter (Phase 10 Section 11)
# ---------------------------------------------------------------------------

@router.get("/dataset/export")
async def export_training_dataset(
    anonymize: bool = Query(True, description="Strip sensitive file paths and project identifiers"),
) -> dict[str, Any]:
    """Export high-quality human corrections as a structured dataset for future lightweight model fine-tuning."""
    corrs = store.list_corrections()
    approved = [c for c in corrs if c.approval_status == ApprovalStatus.APPROVED.value]

    examples: list[dict[str, Any]] = []
    for c in approved:
        example = {
            "example_id": c.correction_id,
            "category": c.category,
            "parameter_key": c.parameter_key,
            "original_ai_proposal": c.original_ai_value,
            "approved_human_decision": c.user_corrected_value,
            "editing_context": {
                "target_aspect": c.editing_context.get("aspect_ratio", "9:16"),
                "video_category": c.editing_context.get("video_category", "general"),
                "speaking_pace": c.editing_context.get("speaking_pace", "normal"),
            },
            "provenance": {
                "model_identifier": c.original_decision_provenance.get("model_identifier", "rule_engine"),
                "original_reason": c.original_decision_provenance.get("reason", ""),
            },
            "timestamp": c.timestamp,
        }
        if not anonymize:
            example["project_id"] = c.project_id
            example["user_note"] = c.user_note
        examples.append(example)

    return {
        "version": "1.0",
        "description": "OpenMontage Phase 10 Editorial Preference Fine-Tuning Dataset",
        "total_examples": len(examples),
        "exported_at": time.time(),
        "examples": examples,
    }
