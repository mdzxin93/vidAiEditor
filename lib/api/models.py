"""Data models for OpenMontage Professional Editing Interface (Phase 9).

Type-safe request and response payloads for projects, media assets,
AI editorial planning, timeline state synchronization, background rendering, and QA.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    project_id: str = Field(..., description="Unique alphanumeric kebab-case project identifier")
    title: str = Field(..., description="Human readable project title")
    pipeline_type: str = Field("talking-head", description="Pipeline type (talking-head, screen-demo, animated-explainer, etc.)")
    aspect_ratio: str = Field("9:16", description="Target aspect ratio: 9:16, 16:9, or 1:1")
    style_playbook: Optional[str] = Field("clean-professional", description="Style playbook name")


class ProjectRenameRequest(BaseModel):
    title: str = Field(..., description="Updated project title")


class ProjectDuplicateRequest(BaseModel):
    new_project_id: str = Field(..., description="New unique project ID")
    new_title: str = Field(..., description="New project title")


class AiAnalyzeRequest(BaseModel):
    video_path: Optional[str] = Field(None, description="Project-relative video path to analyze")
    quality_preset: str = Field("balanced", description="fast, balanced, or quality")


class AiGenerateEditRequest(BaseModel):
    user_instruction: str = Field(..., description="Natural language direction or script prompt")
    video_path: Optional[str] = Field(None, description="Relative path to primary video in project")
    reference_video_path: Optional[str] = Field(None, description="Relative path to reference video")
    mode: str = Field("auto", description="'auto' for autonomous planning or 'script' for directive script matching")
    target_aspect: str = Field("9:16", description="Target aspect ratio: 9:16, 16:9, or 1:1")
    cut_aggressiveness: str = Field("balanced", description="conservative, balanced, or aggressive")
    zoom_intensity: str = Field("standard", description="none, subtle (1.1x), standard (1.25x), or punchy (1.4x)")
    caption_preset: str = Field("word_highlight", description="word_highlight, clean_lower_third, bold_box, minimal")
    motion_graphics_style: str = Field("stats_and_callouts", description="stats_and_callouts, minimal, data_heavy, or all")
    quality_preset: str = Field("balanced", description="fast, balanced, or quality")
    enable_personalization: Optional[bool] = Field(True, description="Whether to apply learned editing preferences")
    preset_id: Optional[str] = Field(None, description="Active style preset ID to apply")


class EditDecisionsUpdateRequest(BaseModel):
    edit_decisions: dict[str, Any] = Field(..., description="Full updated edit_decisions artifact")
    commit_message: Optional[str] = Field("Manual timeline adjustment", description="Description for undo/history log")


class RenderJobRequest(BaseModel):
    mode: str = Field("final", description="'preview' for fast draft render or 'final' for high-quality export")
    composition_id: str = Field("TalkingHead", description="Remotion composition ID (TalkingHead, Explainer, etc.)")
    aspect_ratio: Optional[str] = Field(None, description="Override aspect ratio: 9:16, 16:9, 1:1")
    resolution: Optional[str] = Field(None, description="Resolution string e.g. 1080x1920")
    fps: Optional[int] = Field(30, description="Target frame rate")
    quality: Optional[str] = Field("balanced", description="fast, balanced, high")
    render_preset: Optional[str] = Field("balanced", description="fast_preview, balanced, final_quality")
    output_filename: Optional[str] = Field(None, description="Custom export filename (defaults to final.mp4 or preview.mp4)")


class QaInspectRequest(BaseModel):
    video_path: Optional[str] = Field(None, description="Relative path to rendered video to inspect")


class QaApplyFixesRequest(BaseModel):
    issue_ids: Optional[list[str]] = Field(None, description="Specific issue IDs to fix (None = all auto-fixable)")


class KineticCaptionGenerateRequest(BaseModel):
    video_path: Optional[str] = Field(None, description="Project-relative video path to process")
    preset_id: str = Field("kinetic_podcast_reference", description="Caption preset ID")
    video_style: str = Field("dynamic_zoom", description="Video editing style: 'dynamic_zoom' (punch zoom jump cuts) or 'static' (continuous framing)")
    zoom_intensity: str = Field("standard", description="Punch zoom intensity: subtle, standard, or punchy")
    model_size: str = Field("base", description="Faster-Whisper model size (tiny, base, small, medium, large-v3)")
    language: Optional[str] = Field(None, description="Spoken language code or auto-detect")
    words_per_cue: int = Field(2, description="Target words per caption group (1-4)")
    emphasis_frequency: float = Field(0.25, description="Emphasis frequency (0.0 to 1.0)")
    vertical_position: Optional[float] = Field(None, description="Normalized Y position (0.0 to 1.0)")
    render_video: bool = Field(False, description="Whether to immediately render burned captions to MP4")


class KineticCaptionExportRequest(BaseModel):
    format: str = Field("srt", description="Export format: srt, vtt, or ass")
    cues: Optional[list[dict[str, Any]]] = Field(None, description="Optional custom/edited cues to export")
    preset_id: Optional[str] = Field("kinetic_podcast_reference", description="Preset ID for styling")

