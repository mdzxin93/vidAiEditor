"""FastAPI API Router for OpenMontage Professional Editing Interface (Phase 9).

Endpoints:
- /api/system/metrics (CPU %, RAM, active render queues)
- /api/projects (CRUD, duplicate, rename, history)
- /api/project/{id}/media (upload, list, ffprobe inspect)
- /api/project/{id}/analyze (Whisper transcription & multimodal understanding)
- /api/project/{id}/generate-edit (Autonomous editorial planning)
- /api/project/{id}/edit-decisions (GET/PUT timeline sync with undo/history snapshots)
- /api/project/{id}/render (Preview draft render & final export via Remotion)
- /api/jobs/{id} (Job status, progress %, cancel)
- /api/project/{id}/qa-inspect & qa-apply-fixes (QA reports and automatic revisions)
- /api/presets (Aspect ratios, motion graphics templates, caption styles)
"""

from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from lib.api.jobs import job_manager
from lib.api.media_manager import (
    get_safe_project_dir,
    list_project_media,
    probe_media_file,
    save_uploaded_media,
)
from lib.api.persistence import (
    compute_checksum,
    read_json_with_recovery,
    resolve_safe_path,
    write_json_atomic,
)
from lib.api.cache_manager import cache_manager
from lib.ai.long_video import ChunkedTranscriber, TimelineSanitizer
from lib.ai.video_understanding import compute_adaptive_frame_count
from lib.api.models import (
    AiAnalyzeRequest,
    AiGenerateEditRequest,
    EditDecisionsUpdateRequest,
    ProjectCreateRequest,
    ProjectDuplicateRequest,
    ProjectRenameRequest,
    QaApplyFixesRequest,
    QaInspectRequest,
    RenderJobRequest,
    KineticCaptionGenerateRequest,
    KineticCaptionExportRequest,
)
from lib.checkpoint import (
    PROJECT_MARKER_FILENAME,
    PROJECTS_DIR,
    init_project,
    read_checkpoint,
    write_checkpoint,
)
from lib.paths import REPO_ROOT
from backlot.state import list_projects, summarize_project

logger = logging.getLogger("openmontage.editor_routes")

router = APIRouter(prefix="/api", tags=["editor"])


# ---------------------------------------------------------------------------
# 1. System Telemetry & Presets
# ---------------------------------------------------------------------------

@router.get("/system/metrics")
async def get_system_metrics() -> dict[str, Any]:
    """Return real-time hardware status and active processing queues."""
    return job_manager.get_system_metrics()


@router.get("/presets")
async def get_presets() -> dict[str, Any]:
    """Return supported aspect ratios, style playbooks, and component types."""
    return {
        "aspect_ratios": [
            {"id": "9:16", "label": "Vertical Reel / TikTok (9:16)", "width": 1080, "height": 1920},
            {"id": "16:9", "label": "Horizontal / YouTube (16:9)", "width": 1920, "height": 1080},
            {"id": "1:1", "label": "Square / Feed (1:1)", "width": 1080, "height": 1080},
        ],
        "caption_presets": [
            {
                "id": "kinetic_podcast_reference",
                "label": "Cinematic Kinetic Podcast (Reference)",
                "desc": "Inter Display Bold, rapid 3-frame scale/fade, 1.85x emphasis, two-tier stacked typography",
                "is_default": True,
                "priority": 1,
            },
            {
                "id": "minimal_white",
                "label": "Minimal White",
                "desc": "Crisp white Inter Display with clean subtle drop shadow",
                "priority": 2,
            },
            {
                "id": "bold_word_pop",
                "label": "Bold Word Pop",
                "desc": "High-contrast Black weight (900) with punchy active word pop",
                "priority": 3,
            },
            {
                "id": "editorial_typography",
                "label": "Editorial Typography",
                "desc": "Stacked two-tier editorial hierarchy with small support above giant hero word",
                "priority": 4,
            },
            {
                "id": "clean_podcast",
                "label": "Clean Podcast",
                "desc": "Balanced 2-3 word lower-middle rhythm with soft entrance",
                "priority": 5,
            },
            {
                "id": "animated_social_captions",
                "label": "Animated Social Captions",
                "desc": "Dynamic scaling and high-energy social video cadence",
                "priority": 6,
            },
            {
                "id": "word_highlight",
                "label": "Karaoke Pop (Legacy Word Highlight)",
                "desc": "Active word highlights with spring pop",
            },
        ],
        "motion_graphics_components": [
            {
                "type": "stat_card",
                "label": "Metric Stat Card",
                "default_content": {"value": "+185%", "label": "Growth Rate", "trend": "positive"},
                "positions": ["upper_third", "lower_third", "left_panel", "right_panel"],
            },
            {
                "type": "text_card",
                "label": "Text Headline Card",
                "default_content": {"title": "Key Takeaway", "subtitle": "Core strategic focus"},
                "positions": ["upper_third", "lower_third", "left_panel", "right_panel"],
            },
            {
                "type": "callout",
                "label": "Callout Tip Box",
                "default_content": {"title": "Pro Tip", "text": "Execute in 90-minute blocks", "callout_type": "tip"},
                "positions": ["upper_third", "lower_third", "right_panel"],
            },
            {
                "type": "comparison",
                "label": "Comparison Split Card",
                "default_content": {"leftLabel": "Standard", "leftValue": "45%", "rightLabel": "OpenMontage", "rightValue": "95%"},
                "positions": ["upper_third", "lower_third", "full_overlay"],
            },
            {
                "type": "bar_chart",
                "label": "Animated Bar Chart",
                "default_content": {"title": "Q3 Performance", "chartData": [{"label": "A", "value": 30}, {"label": "B", "value": 85}]},
                "positions": ["upper_third", "lower_third"],
            },
        ],
        "quality_presets": [
            {"id": "fast", "label": "Fast Draft", "desc": "Quick preview render, fast analysis"},
            {"id": "balanced", "label": "Balanced (Recommended)", "desc": "Balanced speed and fidelity"},
            {"id": "quality", "label": "Production Quality", "desc": "Highest precision and sampling"},
        ],
        "cut_aggressiveness": [
            {"id": "conservative", "label": "Conservative", "desc": "Cuts dead pauses > 1.5s"},
            {"id": "balanced", "label": "Balanced", "desc": "Cuts dead pauses > 1.0s"},
            {"id": "aggressive", "label": "Aggressive / Fast", "desc": "Cuts dead pauses > 0.6s"},
        ],
        "zoom_intensity": [
            {"id": "none", "label": "None (Static 1.0x)", "scale": 1.0},
            {"id": "subtle", "label": "Subtle (1.1x)", "scale": 1.1},
            {"id": "standard", "label": "Standard (1.25x)", "scale": 1.25},
            {"id": "punchy", "label": "Punchy (1.4x)", "scale": 1.4},
        ],
    }


# ---------------------------------------------------------------------------
# 2. Project Management
# ---------------------------------------------------------------------------

@router.get("/editor/projects")
@router.get("/projects/all")
async def get_projects() -> list[dict[str, Any]]:
    """Enumerate all existing projects with status, posters, and last activity."""
    if not PROJECTS_DIR.is_dir():
        return []
    summaries = []
    for entry in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not entry.is_dir() or entry.name.startswith(("_", ".")):
            continue
        try:
            sm = summarize_project(entry)
            # Enrich with editor-specific indicators
            ed_path = entry / "artifacts" / "edit_decisions.json"
            sm["has_edit_decisions"] = ed_path.is_file()
            qa_path = entry / "artifacts" / "qa_report.json"
            if qa_path.is_file():
                try:
                    with open(qa_path, "r", encoding="utf-8") as f:
                        qa_data = json.load(f)
                    sm["qa_score"] = qa_data.get("quality_score")
                    sm["qa_passed"] = qa_data.get("passed")
                except Exception:
                    pass
            summaries.append(sm)
        except Exception as e:
            logger.warning("Error summarizing project %s: %s", entry.name, e)
    return summaries


@router.post("/projects")
async def create_new_project(req: ProjectCreateRequest) -> dict[str, Any]:
    """Initialize a brand-new project with canonical workspace structure."""
    if any(c in req.project_id for c in "/\\: ") or not req.project_id.isalnum() and "-" not in req.project_id and "_" not in req.project_id:
        raise HTTPException(status_code=400, detail="Project ID must only contain letters, numbers, hyphens, and underscores.")
    pdir = PROJECTS_DIR / req.project_id
    if pdir.exists():
        raise HTTPException(status_code=409, detail=f"Project '{req.project_id}' already exists.")

    init_project(
        req.project_id,
        title=req.title,
        pipeline_type=req.pipeline_type,
        style_playbook=req.style_playbook,
    )

    # Write initial project metadata with target aspect ratio
    marker_path = pdir / PROJECT_MARKER_FILENAME
    marker = read_json_with_recovery(marker_path, default={})
    marker["aspect_ratio"] = req.aspect_ratio
    write_json_atomic(marker_path, marker)

    return {"ok": True, "project_id": req.project_id, "title": req.title, "path": str(pdir)}


@router.get("/project/{project_id}")
async def get_project_details(project_id: str) -> dict[str, Any]:
    """Retrieve full project overview, media assets, checkpoints, and current decisions."""
    pdir = get_safe_project_dir(project_id)
    marker_path = pdir / PROJECT_MARKER_FILENAME
    marker = read_json_with_recovery(marker_path, default={})

    media_items = list_project_media(project_id)

    # Check for primary video
    video_items = [m for m in media_items if m["category"] in ("video", "render")]
    primary_video = video_items[0] if video_items else None

    # Load edit decisions if generated
    ed_path = pdir / "artifacts" / "edit_decisions.json"
    edits = None
    if ed_path.is_file():
        edits = read_json_with_recovery(ed_path, default=None)

    # Load QA report if available
    qa_path = pdir / "artifacts" / "qa_report.json"
    qa_report = None
    if qa_path.is_file():
        qa_report = read_json_with_recovery(qa_path, default=None)

    return {
        "project_id": project_id,
        "title": marker.get("title", project_id),
        "pipeline_type": marker.get("pipeline_type", "talking-head"),
        "aspect_ratio": marker.get("aspect_ratio", "9:16"),
        "created_at": marker.get("created_at"),
        "media_count": len(media_items),
        "primary_video": primary_video,
        "has_edits": edits is not None,
        "edit_decisions": edits,
        "qa_report": qa_report,
    }


@router.post("/project/{project_id}/rename")
async def rename_project(project_id: str, req: ProjectRenameRequest) -> dict[str, Any]:
    """Rename project title in project.json."""
    pdir = get_safe_project_dir(project_id)
    marker_path = pdir / PROJECT_MARKER_FILENAME
    marker = read_json_with_recovery(marker_path, default={})
    marker["title"] = req.title
    write_json_atomic(marker_path, marker)
    return {"ok": True, "project_id": project_id, "title": req.title}


@router.post("/project/{project_id}/duplicate")
async def duplicate_project(project_id: str, req: ProjectDuplicateRequest) -> dict[str, Any]:
    """Safely duplicate a project to a new directory."""
    src_dir = get_safe_project_dir(project_id)
    dest_dir = PROJECTS_DIR / req.new_project_id
    if dest_dir.exists():
        raise HTTPException(status_code=409, detail=f"Destination project '{req.new_project_id}' already exists.")

    shutil.copytree(src_dir, dest_dir, ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"))

    marker_path = dest_dir / PROJECT_MARKER_FILENAME
    if marker_path.exists():
        marker = read_json_with_recovery(marker_path, default={})
        marker["project_id"] = req.new_project_id
        marker["title"] = req.new_title
        marker["created_at"] = datetime.now(timezone.utc).isoformat()
        write_json_atomic(marker_path, marker)

    return {"ok": True, "new_project_id": req.new_project_id, "new_title": req.new_title}


@router.delete("/project/{project_id}")
async def delete_project(project_id: str) -> dict[str, Any]:
    """Delete a project directory with safety verification."""
    pdir = get_safe_project_dir(project_id)
    trash_dir = PROJECTS_DIR / ".trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    target_trash = trash_dir / f"{project_id}_{int(time.time())}"
    try:
        shutil.move(str(pdir), str(target_trash))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {e}")
    return {"ok": True, "deleted_project_id": project_id}


# ---------------------------------------------------------------------------
# 3. Media Ingestion & Inspection
# ---------------------------------------------------------------------------

@router.get("/project/{project_id}/media")
async def get_project_media(project_id: str) -> list[dict[str, Any]]:
    """List all assets in the project media bins."""
    return list_project_media(project_id)


@router.post("/project/{project_id}/upload")
async def upload_media(
    project_id: str,
    file: UploadFile = File(...),
    category: str = Form("video"),
    overwrite: bool = Form(False),
) -> dict[str, Any]:
    """Upload footage, b-roll, audio, or reference video."""
    content = await file.read()
    try:
        res = save_uploaded_media(
            project_id=project_id,
            filename=file.filename or "media_upload.mp4",
            content=content,
            category=category,
            overwrite=overwrite,
        )
        return {"ok": True, "media": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Upload failed for %s: %s", project_id, e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.get("/project/{project_id}/media-probe")
async def probe_media(project_id: str, path: str) -> dict[str, Any]:
    """Probe media properties using FFprobe."""
    pdir = get_safe_project_dir(project_id)
    target = (pdir / path).resolve()
    try:
        target.relative_to(pdir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path escapes project")
    return probe_media_file(target)


# ---------------------------------------------------------------------------
# 4. AI Analysis & Autonomous Editorial Planning
# ---------------------------------------------------------------------------

@router.post("/project/{project_id}/analyze")
async def analyze_footage(project_id: str, req: AiAnalyzeRequest) -> dict[str, Any]:
    """Run multimodal video understanding and transcription in background."""
    pdir = get_safe_project_dir(project_id)

    # Locate video file
    if req.video_path:
        target_video = (pdir / req.video_path).resolve()
    else:
        # Auto-detect first video
        media_items = list_project_media(project_id)
        vids = [m for m in media_items if m["is_video"] and m["category"] != "render"]
        if not vids:
            # Check renders or assets/video
            vids = [m for m in media_items if m["is_video"]]
        if not vids:
            raise HTTPException(status_code=400, detail="No video footage found in project. Please upload footage first.")
        target_video = (pdir / vids[0]["relative_path"]).resolve()

    if not target_video.is_file():
        raise HTTPException(status_code=404, detail=f"Video file not found: {target_video}")

    # Check cache
    cached = job_manager.get_cached_analysis(target_video)
    if cached:
        logger.info("Found cached analysis for %s", target_video.name)
        artifacts_dir = pdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(artifacts_dir / "video_analysis.json", cached)
        return {"ok": True, "cached": True, "analysis": cached}

    def run_analysis_task(record, progress_cb):
        from lib.ai.pipeline import AutonomousEditingEngine

        progress_cb(10.0, "Probing video stream properties...")
        engine = AutonomousEditingEngine()
        probe = engine._probe_video(target_video)
        duration = float(probe.get("duration", 20.0))

        # Check transcript cache
        cached_transcript = cache_manager.get_cached_transcript(target_video)
        if cached_transcript:
            progress_cb(35.0, "Reusing cached speech transcript...")
            transcript = cached_transcript
        else:
            progress_cb(25.0, "Transcribing speech audio with Whisper...")
            sample_captions = REPO_ROOT / "media" / "sample" / "captions_aligned.json"
            captions_file = None
            if (target_video.parent / "captions_aligned.json").is_file():
                captions_file = target_video.parent / "captions_aligned.json"
            elif target_video.with_suffix(".json").is_file():
                captions_file = target_video.with_suffix(".json")
            elif sample_captions.is_file() and "sample_raw" in target_video.name:
                captions_file = sample_captions

            if captions_file and captions_file.is_file():
                transcript = engine._load_or_extract_transcript(target_video, captions_file)
            elif duration > 120.0:
                progress_cb(28.0, f"Using chunked transcriber for long video ({duration:.1f}s)...")
                chunker = ChunkedTranscriber(chunk_duration=60.0, overlap=3.0)
                transcript = chunker.transcribe(
                    target_video,
                    progress_cb=lambda pct, msg: progress_cb(25.0 + (pct * 0.2), msg),
                )
            else:
                transcript = engine._load_or_extract_transcript(target_video, None)

            cache_manager.store_cached_transcript(target_video, transcript)

        progress_cb(50.0, "Running multimodal scene understanding...")
        sample_frames = compute_adaptive_frame_count(duration)
        if req.quality_preset == "fast":
            sample_frames = min(5, sample_frames)

        cached_obs = cache_manager.get_cached_observations(target_video, "smolvlm", sample_frames)
        if cached_obs:
            progress_cb(75.0, "Reusing cached visual scene observations...")
            obs_list = cached_obs.get("observations", [])
        else:
            vu = engine.understanding_engine.analyze(
                video_path=target_video,
                transcript=transcript,
                sample_frame_count=sample_frames,
            )
            obs_list = [
                {
                    "id": o.id,
                    "category": o.category,
                    "start": o.start_seconds,
                    "end": o.end_seconds,
                    "confidence": o.confidence,
                    "description": o.description,
                }
                for o in vu.observations
            ]
            cache_manager.store_cached_observations(
                target_video,
                "smolvlm",
                sample_frames,
                {"observations": obs_list},
            )

        progress_cb(85.0, "Compiling visual observations and speech beats...")
        result = {
            "source_video": str(target_video.name),
            "duration": duration,
            "observations_count": len(obs_list),
            "observations": obs_list,
            "transcript_words_count": len(transcript),
            "transcript_sample": transcript[:30],
        }

        # Cache result in job_manager
        job_manager.store_cached_analysis(target_video, result)

        artifacts_dir = pdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(artifacts_dir / "video_analysis.json", result)

        return result

    job = job_manager.submit_job(
        project_id,
        "analyze",
        run_analysis_task,
        input_metadata={"video_path": req.video_path, "quality_preset": req.quality_preset},
    )
    return {"ok": True, "job_id": job.job_id, "status": job.status}


@router.post("/project/{project_id}/generate-edit")
async def generate_editorial_plan(project_id: str, req: AiGenerateEditRequest) -> dict[str, Any]:
    """Execute AI autonomous editing planner and write edit_decisions.json."""
    pdir = get_safe_project_dir(project_id)

    # Locate source video
    if req.video_path:
        target_video = (pdir / req.video_path).resolve()
    else:
        media_items = list_project_media(project_id)
        vids = [m for m in media_items if m["is_video"] and m["category"] != "render"]
        if not vids:
            vids = [m for m in media_items if m["is_video"]]
        if not vids:
            raise HTTPException(status_code=400, detail="No video footage found in project. Please upload footage first.")
        target_video = (pdir / vids[0]["relative_path"]).resolve()

    def run_plan_task(record, progress_cb):
        from lib.ai.pipeline import AutonomousEditingEngine
        from lib.ai.config import AIEditorConfig
        from lib.ai.reframer import IntelligentReframer

        progress_cb(15.0, "Loading video and transcript...")
        cfg = AIEditorConfig.load()
        # Apply cut aggressiveness to editorial rules
        if req.cut_aggressiveness == "aggressive":
            cfg.editorial_rules.min_pause_cut_duration = 0.6
        elif req.cut_aggressiveness == "conservative":
            cfg.editorial_rules.min_pause_cut_duration = 1.5
        else:
            cfg.editorial_rules.min_pause_cut_duration = 1.0

        # Apply zoom scale
        zoom_scales = {"none": 1.0, "subtle": 1.1, "standard": 1.25, "punchy": 1.4}
        cfg.editorial_rules.zoom_scale = zoom_scales.get(req.zoom_intensity, 1.25)

        engine = AutonomousEditingEngine(config=cfg)

        probe = engine._probe_video(target_video)
        duration = float(probe.get("duration", 20.0))
        # Check pre-aligned captions to prevent unnecessary network downloads during tests
        sample_captions = REPO_ROOT / "media" / "sample" / "captions_aligned.json"
        captions_file = None
        if (target_video.parent / "captions_aligned.json").is_file():
            captions_file = target_video.parent / "captions_aligned.json"
        elif target_video.with_suffix(".json").is_file():
            captions_file = target_video.with_suffix(".json")
        elif sample_captions.is_file() and ("sample_raw" in target_video.name or "sample_edited" in target_video.name):
            captions_file = sample_captions

        transcript = engine._load_or_extract_transcript(target_video, captions_file)

        progress_cb(35.0, "Performing multimodal video understanding...")
        sample_frames = 5 if req.quality_preset == "fast" else 8
        vu = engine.understanding_engine.analyze(
            video_path=target_video,
            transcript=transcript,
            sample_frame_count=sample_frames,
        )

        style_profile = None
        if req.reference_video_path:
            ref_path = (pdir / req.reference_video_path).resolve()
            if ref_path.is_file():
                progress_cb(55.0, "Extracting reference video style profile...")
                from lib.ai.style_analyzer import ReferenceStyleAnalyzer
                analyzer = ReferenceStyleAnalyzer()
                style_profile = analyzer.analyze_reference(ref_path)

        progress_cb(75.0, "Synthesizing AI editing cuts, zooms and motion graphics...")
        video_meta = {
            "source_path": str(target_video),
            "duration": duration,
            "width": probe.get("width", 1920),
            "height": probe.get("height", 1080),
            "fps": probe.get("fps", 30.0),
        }

        plan_res = engine.planner.plan(
            understanding=vu,
            transcript=transcript,
            user_prompt=req.user_instruction,
            video_metadata=video_meta,
            style_profile=style_profile,
            enable_personalization=bool(req.enable_personalization) if req.enable_personalization is not None else True,
        )

        edits = plan_res.edit_decisions
        edits["metadata"]["target_aspect"] = req.target_aspect
        edits["metadata"]["caption_preset"] = req.caption_preset
        edits["metadata"]["user_instruction"] = req.user_instruction

        # Ensure subtitles words exist for timeline display
        if "subtitles" in edits and "words" not in edits["subtitles"]:
            edits["subtitles"]["words"] = [
                {
                    "word": w.get("word", ""),
                    "start": round(float(w.get("start", 0.0)), 3),
                    "end": round(float(w.get("end", 0.0)), 3),
                }
                for w in transcript
            ]

        # Ensure all overlays have an id attribute
        for idx, ov in enumerate(edits.get("overlays", [])):
            if "id" not in ov:
                ov["id"] = ov.get("asset_id") or f"overlay_{idx + 1}"

        # Retarget crops if 9:16 target aspect requested
        if req.target_aspect == "9:16" and probe.get("width", 1920) > probe.get("height", 1080):
            reframer = IntelligentReframer()
            rf = reframer.compute_reframe(
                video_width=probe.get("width", 1920),
                video_height=probe.get("height", 1080),
                target_aspect="9:16",
            )
            for c in edits.get("cuts", []):
                t = c.setdefault("transform", {})
                t["crop"] = {
                    "x": rf.crop_x,
                    "y": rf.crop_y,
                    "width": rf.crop_width,
                    "height": rf.crop_height,
                }

        # Sanitize timeline: eliminate gaps, overlaps, zero/negative durations and subtitle drift
        edits = TimelineSanitizer.sanitize(edits, duration)

        # Backup previous edit decisions or save baseline AI plan to history
        artifacts_dir = pdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        ed_path = artifacts_dir / "edit_decisions.json"

        history_dir = pdir / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        ts_gen = int(time.time() * 1000)
        snap_gen = history_dir / f"edit_decisions_{ts_gen}.json"
        if ed_path.exists():
            shutil.copy2(ed_path, snap_gen)
        else:
            write_json_atomic(snap_gen, edits)

        meta_file = history_dir / "history_meta.json"
        meta_data: dict[str, Any] = read_json_with_recovery(meta_file, default={})
        meta_data[snap_gen.stem] = {
            "commit_message": "AI Generated Editorial Plan",
            "timestamp": ts_gen / 1000.0,
        }
        write_json_atomic(meta_file, meta_data)
        write_json_atomic(ed_path, edits)

        progress_cb(95.0, "Checkpointing editorial decisions...")
        write_checkpoint(
            pipeline_dir=PROJECTS_DIR,
            project_id=project_id,
            stage="edit",
            status="completed",
            artifacts={"edit_decisions": edits},
            enforce_prerequisites=False,
        )

        return {
            "cuts_count": len(edits.get("cuts", [])),
            "overlays_count": len(edits.get("overlays", [])),
            "subtitles_count": len(edits.get("subtitles", {}).get("words", [])),
            "decision_source": plan_res.decision_source,
            "edit_decisions": edits,
        }

    job = job_manager.submit_job(
        project_id,
        "generate_edit",
        run_plan_task,
        input_metadata=req.model_dump(),
    )
    return {"ok": True, "job_id": job.job_id, "status": job.status}


# ---------------------------------------------------------------------------
# 5. Timeline Synchronization & Undo/History
# ---------------------------------------------------------------------------

@router.get("/project/{project_id}/edit-decisions")
async def get_edit_decisions(project_id: str) -> dict[str, Any]:
    """Retrieve the current structured editing plan for timeline display."""
    pdir = get_safe_project_dir(project_id)
    ed_path = pdir / "artifacts" / "edit_decisions.json"
    if not ed_path.is_file():
        # Generate baseline default template
        media_items = list_project_media(project_id)
        vids = [m for m in media_items if m["is_video"]]
        vsrc = vids[0]["relative_path"] if vids else ""
        dur = 10.0
        if vids:
            probe = probe_media_file(pdir / vsrc)
            dur = probe.get("duration", 10.0)

        default_edits = {
            "version": "1.0",
            "render_runtime": "remotion",
            "renderer_family": "presenter",
            "cuts": [
                {
                    "id": "cut_1",
                    "source": vsrc,
                    "in_seconds": 0.0,
                    "out_seconds": round(dur, 2),
                    "speed": 1.0,
                    "transform": {"scale": 1.0, "x": 0, "y": 0},
                }
            ],
            "overlays": [],
            "subtitles": {"enabled": True, "style": "word_highlight", "words": []},
            "metadata": {
                "talking_head_props": {
                    "videoSrc": vsrc,
                    "overlays": [],
                    "subtitles": [],
                }
            },
        }
        return {"ok": True, "is_default": True, "edit_decisions": default_edits}

    edits = read_json_with_recovery(ed_path, default={})
    return {"ok": True, "is_default": False, "edit_decisions": edits}


def _detect_and_record_corrections(
    project_id: str,
    prev_edits: Optional[dict[str, Any]],
    new_edits: dict[str, Any],
    commit_message: Optional[str],
) -> list[Any]:
    if not prev_edits or not isinstance(prev_edits, dict):
        return []

    from lib.ai.memory.models import ApprovalStatus, CorrectionRecord, EditingPreferenceCategory
    from lib.ai.memory.preference_store import PreferenceStore

    store = PreferenceStore()
    msg = (commit_message or "").lower()
    is_undo_redo = "undo" in msg or "redo" in msg
    approval_status = ApprovalStatus.UNDO_OP.value if is_undo_redo else ApprovalStatus.PENDING_REVIEW.value

    records: list[Any] = []
    aspect = new_edits.get("metadata", {}).get("target_aspect", "9:16")

    # 1. Detect Zoom scale changes
    prev_cuts = prev_edits.get("cuts", [])
    new_cuts = new_edits.get("cuts", [])
    for p_cut, n_cut in zip(prev_cuts, new_cuts):
        p_scale = p_cut.get("transform", {}).get("scale", 1.0)
        n_scale = n_cut.get("transform", {}).get("scale", 1.0)
        if abs(p_scale - n_scale) > 0.01:
            rec = CorrectionRecord(
                correction_id=f"corr_{int(time.time()*1000)}_zoom_{p_cut.get('id', 'cut')}",
                project_id=project_id,
                category=EditingPreferenceCategory.ZOOM.value,
                parameter_key="zoom_scale",
                original_ai_value=p_scale,
                user_corrected_value=n_scale,
                editing_context={"aspect_ratio": aspect, "cut_id": p_cut.get("id")},
                approval_status=approval_status,
                original_decision_provenance=p_cut.get("transform", {}).get("zoom_provenance", {}),
                user_note=commit_message,
                timestamp=time.time(),
            )
            store.record_correction(rec)
            records.append(rec)
            break

    # 2. Detect Caption Highlight changes
    p_th = prev_edits.get("metadata", {}).get("talking_head_props", {})
    n_th = new_edits.get("metadata", {}).get("talking_head_props", {})
    p_color = p_th.get("highlightColor")
    n_color = n_th.get("highlightColor")
    if p_color and n_color and p_color != n_color:
        rec = CorrectionRecord(
            correction_id=f"corr_{int(time.time()*1000)}_caption_color",
            project_id=project_id,
            category=EditingPreferenceCategory.CAPTION.value,
            parameter_key="caption_highlight_color",
            original_ai_value=p_color,
            user_corrected_value=n_color,
            editing_context={"aspect_ratio": aspect},
            approval_status=approval_status,
            original_decision_provenance=p_th.get("color_provenance", {}),
            user_note=commit_message,
            timestamp=time.time(),
        )
        store.record_correction(rec)
        records.append(rec)

    # 3. Detect Overlay Type changes
    p_ovs = p_th.get("overlays", [])
    n_ovs = n_th.get("overlays", [])
    for p_ov, n_ov in zip(p_ovs, n_ovs):
        if p_ov.get("type") != n_ov.get("type"):
            rec = CorrectionRecord(
                correction_id=f"corr_{int(time.time()*1000)}_overlay_{p_ov.get('id', 'ov')}",
                project_id=project_id,
                category=EditingPreferenceCategory.MOTION_GRAPHIC.value,
                parameter_key="preferred_overlay_types",
                original_ai_value=[p_ov.get("type")],
                user_corrected_value=[n_ov.get("type")],
                editing_context={"aspect_ratio": aspect},
                approval_status=approval_status,
                original_decision_provenance={"original_type": p_ov.get("type")},
                user_note=commit_message,
                timestamp=time.time(),
            )
            store.record_correction(rec)
            records.append(rec)
            break

    return records


@router.put("/project/{project_id}/edit-decisions")
async def update_edit_decisions(project_id: str, req: EditDecisionsUpdateRequest) -> dict[str, Any]:
    """Persist manual timeline edits and create an undo checkpoint snapshot."""
    pdir = get_safe_project_dir(project_id)
    artifacts_dir = pdir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ed_path = artifacts_dir / "edit_decisions.json"

    # Save snapshot for undo/redo
    history_dir = pdir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    snap_file = history_dir / f"edit_decisions_{ts}.json"
    prev_edits = read_json_with_recovery(ed_path, default=None)
    if prev_edits:
        write_json_atomic(snap_file, prev_edits)
    else:
        write_json_atomic(snap_file, req.edit_decisions)

    meta_file = history_dir / "history_meta.json"
    meta_data: dict[str, Any] = read_json_with_recovery(meta_file, default={})
    meta_data[snap_file.stem] = {
        "commit_message": req.commit_message or "Manual timeline adjustment",
        "timestamp": ts / 1000.0,
    }
    write_json_atomic(meta_file, meta_data)

    # Keep at most 20 history snapshots
    snapshots = sorted(history_dir.glob("edit_decisions_*.json"), key=lambda p: p.stat().st_mtime)
    if len(snapshots) > 20:
        for old in snapshots[:-20]:
            try:
                old.unlink()
            except Exception:
                pass

    # Audit modifications & log pending corrections (Phase 10)
    detected_corrections = _detect_and_record_corrections(
        project_id=project_id,
        prev_edits=prev_edits,
        new_edits=req.edit_decisions,
        commit_message=req.commit_message,
    )

    write_json_atomic(ed_path, req.edit_decisions)

    return {
        "ok": True,
        "saved_at": ts,
        "message": req.commit_message,
        "recorded_corrections": len(detected_corrections),
    }


@router.get("/project/{project_id}/history")
async def get_project_history(project_id: str) -> list[dict[str, Any]]:
    """List available timeline history checkpoints for undo/redo."""
    pdir = get_safe_project_dir(project_id)
    history_dir = pdir / "history"
    if not history_dir.is_dir():
        return []

    meta_file = history_dir / "history_meta.json"
    meta_data: dict[str, Any] = read_json_with_recovery(meta_file, default={})

    items = []
    for f in sorted(history_dir.glob("edit_decisions_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        m = meta_data.get(f.stem, {})
        items.append({
            "snapshot_id": f.stem,
            "filename": f.name,
            "timestamp": f.stat().st_mtime,
            "size_bytes": f.stat().st_size,
            "commit_message": m.get("commit_message", "Timeline edit"),
        })
    return items


@router.post("/project/{project_id}/history/revert")
async def revert_to_history_snapshot(project_id: str, snapshot_id: str) -> dict[str, Any]:
    """Revert timeline state to a specific history checkpoint snapshot."""
    pdir = get_safe_project_dir(project_id)
    history_file = pdir / "history" / f"{snapshot_id}.json"
    if not history_file.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    target_ed = pdir / "artifacts" / "edit_decisions.json"
    reverted = read_json_with_recovery(history_file, default=None)
    if reverted is None:
        raise HTTPException(status_code=500, detail="Failed to read history snapshot")

    write_json_atomic(target_ed, reverted)
    return {"ok": True, "reverted_to": snapshot_id, "edit_decisions": reverted}


# ---------------------------------------------------------------------------
# 6. Video Rendering & Job Management
# ---------------------------------------------------------------------------

@router.post("/project/{project_id}/render")
async def trigger_render(project_id: str, req: RenderJobRequest) -> dict[str, Any]:
    """Queue a video render job (preview draft or final export)."""
    pdir = get_safe_project_dir(project_id)
    ed_path = pdir / "artifacts" / "edit_decisions.json"
    if not ed_path.is_file():
        raise HTTPException(status_code=400, detail="No edit decisions found. Generate or customize an edit first.")

    edits = read_json_with_recovery(ed_path, default=None)
    if not edits:
        raise HTTPException(status_code=400, detail="Could not read valid edit decisions. Please generate or customize an edit first.")

    # Determine output filename
    out_dir = pdir / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    if req.output_filename:
        out_name = req.output_filename if req.output_filename.endswith(".mp4") else f"{req.output_filename}.mp4"
    elif req.mode == "preview":
        out_name = f"preview_{int(time.time())}.mp4"
    else:
        out_name = f"final_{int(time.time())}.mp4"
    output_path = out_dir / out_name

    job_type = f"render_{req.mode}"

    def run_render_task(record, progress_cb):
        from tools.video.video_compose import VideoCompose

        progress_cb(10.0, "Preparing Remotion composition properties...")
        composer = VideoCompose()

        # Adapt TalkingHead props
        th_props = edits.setdefault("metadata", {}).setdefault("talking_head_props", {})
        if "overlays" in edits:
            flattened_overlays = []
            for ov in edits["overlays"]:
                item = dict(ov)
                in_s = item.get("in_seconds") if item.get("in_seconds") is not None else item.get("start_seconds", 0.0)
                out_s = item.get("out_seconds") if item.get("out_seconds") is not None else item.get("end_seconds", in_s + 3.0)
                item["in_seconds"] = float(in_s)
                item["out_seconds"] = float(out_s)
                if "content" in item and isinstance(item["content"], dict):
                    cnt = item["content"]
                    if "value" in cnt and "stat" not in item:
                        item["stat"] = cnt["value"]
                    if "label" in cnt and "subtitle" not in item:
                        item["subtitle"] = cnt["label"]
                    if "text" in cnt and "text" not in item:
                        item["text"] = cnt["text"]
                    if "title" in cnt and "title" not in item:
                        item["title"] = cnt["title"]
                    if "subtitle" in cnt and "subtitle" not in item:
                        item["subtitle"] = cnt["subtitle"]
                    if "trend" in cnt and "trend" not in item:
                        item["trend"] = cnt["trend"]
                    if "callout_type" in cnt and "callout_type" not in item:
                        item["callout_type"] = cnt["callout_type"]
                flattened_overlays.append(item)
            th_props["overlays"] = flattened_overlays
        if "subtitles" in edits and "words" in edits["subtitles"]:
            th_props["subtitles"] = edits["subtitles"]["words"]
            th_props["captions"] = edits["subtitles"]["words"]

        # Ensure video source is absolute or project-resolved
        video_src = th_props.get("videoSrc") or (edits.get("cuts", [{}])[0].get("source"))
        if video_src:
            abs_vsrc = (pdir / video_src).resolve()
            if abs_vsrc.is_file():
                th_props["videoSrc"] = str(abs_vsrc)

        progress_cb(25.0, f"Invoking Remotion CLI for {req.composition_id}...")

        render_preset = getattr(req, "render_preset", None) or ("fast_preview" if req.mode == "preview" else "balanced")
        render_inputs: dict[str, Any] = {
            "operation": "remotion_render",
            "composition_id": req.composition_id,
            "edit_decisions": edits,
            "output_path": str(output_path),
            "render_preset": render_preset,
            "job_id": record.job_id,
        }
        if req.resolution:
            render_inputs["resolution"] = req.resolution

        res = composer.execute(render_inputs)

        if not res.success:
            raise RuntimeError(f"Remotion render failed: {res.error}")

        progress_cb(90.0, "Verifying exported MP4...")
        probe = probe_media_file(output_path)

        # Checkpoint compose stage if final render
        if req.mode == "final":
            write_checkpoint(
                pipeline_dir=PROJECTS_DIR,
                project_id=project_id,
                stage="compose",
                status="completed",
                artifacts={"render_report": {"output_path": str(output_path), "probe": probe}},
                enforce_prerequisites=False,
            )

        return {
            "output_path": str(output_path),
            "output_filename": out_name,
            "media_url": f"/media/{project_id}/renders/{out_name}",
            "probe": probe,
        }

    render_priority = 5 if req.mode == "preview" else 10
    job = job_manager.submit_job(
        project_id,
        job_type,
        run_render_task,
        input_metadata=req.model_dump(),
        priority=render_priority,
    )
    return {"ok": True, "job_id": job.job_id, "status": job.status, "output_path": str(output_path)}


@router.get("/jobs")
async def list_jobs(project_id: Optional[str] = None) -> list[dict[str, Any]]:
    """List active and historical background jobs with queue positions."""
    jobs_data = []
    for j in job_manager.list_jobs(project_id):
        d = j.to_dict()
        pdir = PROJECTS_DIR / j.project_id
        if not pdir.is_dir():
            d["recoverable"] = False
            if j.status in ("interrupted", "recoverable"):
                d["stage"] = "Project directory missing (cannot recover)"
        if j.status == "queued":
            q_info = job_manager.get_queue_info(j.job_id)
            if q_info:
                d["queue_position"] = q_info["queue_position"]
                d["total_queued"] = q_info["total_queued"]
        jobs_data.append(d)
    return jobs_data


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Get status and progress telemetry for a specific job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    d = job.to_dict()
    if job.status == "queued":
        q_info = job_manager.get_queue_info(job_id)
        if q_info:
            d["queue_position"] = q_info["queue_position"]
            d["total_queued"] = q_info["total_queued"]
    return d


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    """Cancel an active or queued background job."""
    ok = job_manager.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found or already finished")
    return {"ok": True, "job_id": job_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# 7. Quality Inspection (QA) & Automatic Revisions
# ---------------------------------------------------------------------------

@router.post("/project/{project_id}/qa-inspect")
async def inspect_rendered_video(project_id: str, req: QaInspectRequest) -> dict[str, Any]:
    """Execute post-render QA Inspector and compute quality score."""
    pdir = get_safe_project_dir(project_id)
    renders_dir = pdir / "renders"

    if req.video_path:
        target_video = (pdir / req.video_path).resolve()
    else:
        # Find latest render
        renders = sorted(renders_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not renders:
            raise HTTPException(status_code=400, detail="No rendered video found to inspect. Please render first.")
        target_video = renders[0]

    if not target_video.is_file():
        raise HTTPException(status_code=404, detail=f"Target video not found: {target_video}")

    ed_path = pdir / "artifacts" / "edit_decisions.json"
    edits = {}
    if ed_path.is_file():
        edits = read_json_with_recovery(ed_path, default={})

    from lib.ai.qa_inspector import QAInspector
    inspector = QAInspector()
    report = inspector.inspect(video_path=target_video, edit_decisions=edits)

    # Save report
    artifacts_dir = pdir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_dict = report.to_dict()
    write_json_atomic(artifacts_dir / "qa_report.json", report_dict)

    return {"ok": True, "qa_report": report_dict}


@router.get("/project/{project_id}/qa-report")
async def get_latest_qa_report(project_id: str) -> dict[str, Any]:
    """Retrieve the latest post-render quality report."""
    pdir = get_safe_project_dir(project_id)
    qa_path = pdir / "artifacts" / "qa_report.json"
    if not qa_path.is_file():
        return {"ok": False, "message": "No QA report exists yet for this project."}
    data = read_json_with_recovery(qa_path, default={})
    return {"ok": True, "qa_report": data}


@router.post("/project/{project_id}/qa-apply-fixes")
async def apply_qa_fixes(project_id: str, req: QaApplyFixesRequest) -> dict[str, Any]:
    """Apply automatic corrections to edit_decisions based on active defects."""
    pdir = get_safe_project_dir(project_id)
    qa_path = pdir / "artifacts" / "qa_report.json"
    ed_path = pdir / "artifacts" / "edit_decisions.json"
    if not qa_path.is_file() or not ed_path.is_file():
        raise HTTPException(status_code=400, detail="Both QA report and edit decisions must exist to apply fixes.")

    qa_data = read_json_with_recovery(qa_path, default={})
    edits = read_json_with_recovery(ed_path, default={})

    from lib.ai.qa_fixer import IntelligentQAFixer as QAFixer
    from lib.ai.qa_models import QAIssue

    fixer = QAFixer()
    raw_issues = qa_data.get("issues", [])
    if req.issue_ids:
        raw_issues = [i for i in raw_issues if i.get("issue_id") in req.issue_ids]

    issues = [QAIssue.from_dict(i) for i in raw_issues]
    dur = float(qa_data.get("duration_seconds", 30.0))

    corrected_edits, fix_records = fixer.apply_fixes(
        edit_decisions=edits,
        issues=issues,
        video_duration=dur,
    )

    # Save backup before writing corrected edits
    history_dir = pdir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    write_json_atomic(history_dir / f"edit_decisions_pre_fix_{ts}.json", edits)
    write_json_atomic(ed_path, corrected_edits)

    return {
        "ok": True,
        "fixes_applied_count": len(fix_records),
        "fixes": [r.to_dict() for r in fix_records],
        "edit_decisions": corrected_edits,
    }


# ---------------------------------------------------------------------------
# 8. Cache Management & Job Recovery (Phase 11)
# ---------------------------------------------------------------------------

@router.get("/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """Retrieve telemetry on multi-tier cached assets and disk consumption."""
    return cache_manager.get_cache_stats()


@router.post("/cache/clear")
async def clear_cache(scope: str = "all") -> dict[str, Any]:
    """Safely clear cached artifacts without touching source footage or renders."""
    return cache_manager.clear_cache(scope=scope)


@router.post("/jobs/clear-completed")
async def clear_completed_jobs(project_id: Optional[str] = None) -> dict[str, Any]:
    """Prune finished, cancelled, or failed jobs from persistent SQLite store."""
    count = job_manager.clear_completed_jobs(project_id)
    return {"ok": True, "cleared_count": count}


@router.post("/jobs/{job_id}/recover")
async def recover_job(job_id: str) -> dict[str, Any]:
    """Recover an interrupted or failed job, resuming from valid completed checkpoints."""
    record = job_manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")

    if record.status not in ("interrupted", "failed", "cancelled", "recoverable"):
        raise HTTPException(status_code=400, detail=f"Job cannot be recovered in state: {record.status}")

    meta = record.input_metadata or {}
    project_id = record.project_id

    # Verify project exists on disk before attempting recovery
    try:
        get_safe_project_dir(project_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot recover job: Project '{project_id}' was a temporary test fixture and no longer exists on disk.",
        )

    if record.job_type == "analyze":
        req_an = AiAnalyzeRequest(**meta)
        return await analyze_footage(project_id, req_an)
    elif record.job_type == "generate_edit":
        req_ge = AiGenerateEditRequest(**meta)
        return await generate_editorial_plan(project_id, req_ge)
    elif record.job_type.startswith("render_"):
        req_rn = RenderJobRequest(**meta)
        return await trigger_render(project_id, req_rn)
    elif record.job_type == "qa_inspect":
        req_qa = QaInspectRequest(**meta)
        return await inspect_rendered_video(project_id, req_qa)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported job type for recovery: {record.job_type}")


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str) -> dict[str, Any]:
    """Retry a failed or cancelled background job."""
    return await recover_job(job_id)


@router.delete("/jobs/{job_id}")
async def delete_job_record(job_id: str) -> dict[str, Any]:
    """Delete a single job record from SQLite store."""
    deleted = job_manager.store.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "job_id": job_id}


# ---------------------------------------------------------------------------
# 11. Waveform Visualization, Incremental Audit & System Models (Phase 12)
# ---------------------------------------------------------------------------

@router.get("/project/{project_id}/waveform")
async def get_project_audio_waveform(
    project_id: str,
    video_path: Optional[str] = None,
    points: int = 800,
) -> dict[str, Any]:
    try:
        pdir = get_safe_project_dir(project_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    target_media = None

    if video_path:
        candidate = (pdir / video_path).resolve()
        if candidate.is_file():
            target_media = candidate

    if not target_media:
        # Locate first available video or audio asset in project
        media_items = list_project_media(project_id)
        if media_items:
            target_media = (pdir / media_items[0]["relative_path"]).resolve()

    if not target_media or not target_media.is_file():
        raise HTTPException(status_code=404, detail="No media file found for waveform generation")

    from lib.ai.waveform_extractor import WaveformExtractor
    extractor = WaveformExtractor()
    points_clamped = max(100, min(2000, points))
    data = extractor.extract_peaks(target_media, target_points=points_clamped)
    return {
        "ok": True,
        "media_file": target_media.name,
        "duration": data["duration"],
        "points_count": data["points_count"],
        "peaks": data["peaks"],
    }


@router.get("/project/{project_id}/incremental-render-audit")
async def audit_incremental_render(
    project_id: str,
    render_preset: str = "fast_preview",
    resolution: str = "540x960",
) -> dict[str, Any]:
    """Evaluate timeline cuts to identify cached vs dirty segments for fast incremental re-renders."""
    pdir = get_safe_project_dir(project_id)
    ed_path = pdir / "artifacts" / "edit_decisions.json"
    if not ed_path.is_file():
        raise HTTPException(status_code=404, detail="No edit decisions found to audit")

    edits = read_json_with_recovery(ed_path, default={})
    cuts = edits.get("cuts", [])
    overlays = edits.get("overlays", [])
    captions = edits.get("subtitles", {}).get("words", [])

    from lib.render.segmented_engine import SegmentedRenderEngine
    engine = SegmentedRenderEngine()
    audit_res = engine.evaluate_incremental_plan(
        cuts=cuts,
        overlays=overlays,
        captions=captions,
        render_preset=render_preset,
        target_resolution=resolution,
    )
    return {"ok": True, "audit": audit_res}


@router.get("/system/models")
async def get_system_model_status() -> dict[str, Any]:
    """Audit local model directory, offline readiness, and missing model diagnostics."""
    from lib.storage_paths import get_storage
    storage = get_storage()
    models_dir = storage.models_dir

    # Check SmolVLM-500M
    smol_local = (models_dir / "SmolVLM-500M-Instruct").is_dir() or (REPO_ROOT / "models" / "SmolVLM-500M-Instruct").is_dir()
    
    # Check Whisper
    whisper_local = (models_dir / "whisper").is_dir() or (REPO_ROOT / "models" / "whisper").is_dir() or (Path.home() / ".cache" / "huggingface" / "hub").is_dir()

    return {
        "ok": True,
        "models_directory": str(models_dir),
        "smolvlm_500m": {
            "name": "HuggingFaceTB/SmolVLM-500M-Instruct",
            "is_installed_locally": smol_local,
            "required_for": "Local visual video understanding",
            "instructions": "Place SmolVLM-500M-Instruct in models/ or download via huggingface-cli",
        },
        "whisper": {
            "name": "Systran/faster-whisper-base.en",
            "is_installed_locally": whisper_local,
            "required_for": "Local speech transcription",
            "instructions": "faster-whisper caches models in ~/.cache/huggingface/hub or models/whisper",
        },
        "hardware": {
            "device": "Intel Core i7-13620H (CPU / AVX2)",
            "cuda_available": False,
            "ram_recommended_gb": 16,
        },
    }


# ---------------------------------------------------------------------------
# 13. Kinetic Typography & AI Subtitle Engine (Phases 10, 11, 13)
# ---------------------------------------------------------------------------

@router.get("/caption-presets")
async def get_all_caption_presets() -> dict[str, Any]:
    """Return all available caption style presets with full style configurations."""
    preset_dir = REPO_ROOT / "config" / "caption_presets"
    presets: list[dict[str, Any]] = []

    if preset_dir.is_dir():
        for p_file in sorted(preset_dir.glob("*.json")):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    presets.append(data)
            except Exception as e:
                logger.warning(f"Failed to load preset {p_file.name}: {e}")

    # Ensure reference preset is first
    presets.sort(key=lambda p: 0 if p.get("style_id") == "kinetic_podcast_reference" else 1)
    return {"ok": True, "presets": presets}


@router.post("/project/{project_id}/captions/generate")
async def generate_kinetic_captions(
    project_id: str,
    req: KineticCaptionGenerateRequest,
) -> dict[str, Any]:
    """Execute AI kinetic caption generator: transcribe, segment 1-4 words, detect emphasis, and update timeline."""
    pdir = get_safe_project_dir(project_id)

    # Resolve target video
    if req.video_path:
        target_video = (pdir / req.video_path).resolve()
        if not target_video.is_file():
            # Check if relative to REPO_ROOT
            repo_candidate = (REPO_ROOT / req.video_path).resolve()
            if repo_candidate.is_file():
                target_video = repo_candidate
            else:
                raise HTTPException(status_code=404, detail=f"Target video not found: {req.video_path}")
    else:
        media_items = list_project_media(project_id)
        vids = [m for m in media_items if m["is_video"] and m["category"] != "render"]
        if not vids:
            vids = [m for m in media_items if m["is_video"]]
        if not vids:
            raise HTTPException(
                status_code=400,
                detail="No video footage found in project. Please upload footage first.",
            )
        target_video = (pdir / vids[0]["relative_path"]).resolve()

    def run_kinetic_task(record, progress_cb):
        from tools.subtitle.kinetic_caption_engine import KineticCaptionEngine

        progress_cb(10.0, "Initializing Faster-Whisper and typography engine...")
        engine = KineticCaptionEngine()

        export_formats = ["srt", "vtt", "ass"]
        if req.render_video:
            export_formats.append("mp4")

        rendered_output = pdir / "renders" / f"kinetic_captions_{req.preset_id}.mp4"
        rendered_output.parent.mkdir(parents=True, exist_ok=True)

        progress_cb(25.0, "Transcribing speech and extracting word-level timestamps...")
        result = engine.execute({
            "video_path": str(target_video),
            "output_path": str(rendered_output) if req.render_video else None,
            "preset_id": req.preset_id,
            "video_style": req.video_style,
            "zoom_intensity": req.zoom_intensity,
            "model_size": req.model_size,
            "language": req.language,
            "words_per_cue": req.words_per_cue,
            "emphasis_frequency": req.emphasis_frequency,
            "vertical_position": req.vertical_position,
            "export_formats": export_formats,
        })

        if not result.success:
            raise RuntimeError(f"Kinetic caption generation failed: {result.error}")

        progress_cb(80.0, "Updating timeline edit decisions with kinetic cues...")
        cues = result.data.get("cues", [])
        words = result.data.get("words", [])
        cuts = result.data.get("cuts", [])
        overlays = result.data.get("overlays", [])
        edl_v3 = result.data.get("edl")

        # Update edit_decisions.json
        artifacts_dir = pdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        ed_path = artifacts_dir / "edit_decisions.json"

        # Save EDL v3 if planned
        if edl_v3:
            edl_path = artifacts_dir / "edit_plan_v3.json"
            write_json_atomic(edl_path, edl_v3)

        edits = read_json_with_recovery(ed_path, default={})
        if not edits:
            probe = probe_media_file(target_video)
            dur = probe.get("duration", 10.0)
            vrel = str(target_video.relative_to(pdir)) if str(target_video).startswith(str(pdir)) else target_video.name
            edits = {
                "version": "1.0",
                "render_runtime": "remotion",
                "renderer_family": "presenter",
                "cuts": [
                    {
                        "id": "cut_1",
                        "source": vrel,
                        "in_seconds": 0.0,
                        "out_seconds": round(dur, 2),
                        "speed": 1.0,
                        "transform": {"scale": 1.0, "x": 0, "y": 0},
                    }
                ],
                "overlays": [],
            }

        # Apply dynamic punch zoom cuts if selected
        if cuts and req.video_style in ("dynamic_zoom", "punch_zoom"):
            edits["cuts"] = cuts

        if overlays:
            edits["overlays"] = overlays

        edits["subtitles"] = {
            "enabled": True,
            "style": req.preset_id,
            "preset_id": req.preset_id,
            "words": words,
            "cues": cues,
            "exports": result.data.get("exports", {}),
        }

        # Sync talking head props
        if "metadata" not in edits or not isinstance(edits["metadata"], dict):
            edits["metadata"] = {}
        if "talking_head_props" not in edits["metadata"] or not isinstance(edits["metadata"]["talking_head_props"], dict):
            edits["metadata"]["talking_head_props"] = {}

        edits["metadata"]["caption_preset"] = req.preset_id
        edits["metadata"]["video_style"] = req.video_style
        edits["metadata"]["talking_head_props"]["subtitles"] = words
        edits["metadata"]["talking_head_props"]["kineticCues"] = cues
        edits["metadata"]["talking_head_props"]["cuts"] = edits.get("cuts", [])
        if overlays:
            edits["metadata"]["talking_head_props"]["overlays"] = overlays

        # Save to history & disk
        history_dir = pdir / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        ts_now = int(time.time() * 1000)
        snap_path = history_dir / f"edit_decisions_{ts_now}.json"
        write_json_atomic(snap_path, edits)

        meta_file = history_dir / "history_meta.json"
        meta_data: dict[str, Any] = read_json_with_recovery(meta_file, default={})
        meta_data[snap_path.stem] = {
            "commit_message": f"Generated {len(cues)} Kinetic Captions ({req.preset_id})",
            "timestamp": ts_now / 1000.0,
        }
        write_json_atomic(meta_file, meta_data)
        write_json_atomic(ed_path, edits)

        progress_cb(100.0, f"Successfully created {len(cues)} kinetic caption cues.")
        return {
            "cues_count": len(cues),
            "emphasis_count": result.data.get("emphasis_count", 0),
            "cues": cues,
            "words": words,
            "exports": result.data.get("exports", {}),
            "preset": result.data.get("preset", {}),
        }

    job = job_manager.submit_job(
        project_id,
        "kinetic_captions",
        run_kinetic_task,
        input_metadata=req.model_dump(),
    )
    return {"ok": True, "job_id": job.job_id, "status": job.status}


@router.post("/project/{project_id}/captions/export")
async def export_project_captions(
    project_id: str,
    req: KineticCaptionExportRequest,
) -> dict[str, Any]:
    """Export project captions as .srt, .vtt, or .ass file."""
    pdir = get_safe_project_dir(project_id)
    artifacts_dir = pdir / "artifacts"
    ed_path = artifacts_dir / "edit_decisions.json"

    cues = req.cues
    if not cues:
        if ed_path.is_file():
            edits = read_json_with_recovery(ed_path, default={})
            cues = edits.get("subtitles", {}).get("cues", [])

    if not cues:
        raise HTTPException(status_code=400, detail="No caption cues found to export.")

    from tools.subtitle.kinetic_caption_engine import KineticCaptionEngine
    engine = KineticCaptionEngine()
    preset = engine.load_preset(req.preset_id or "kinetic_podcast_reference")

    assets_dir = pdir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    out_file = assets_dir / f"subtitles_{req.preset_id}.{req.format.lower()}"

    content = ""
    fmt = req.format.lower()
    if fmt == "srt":
        content = engine.export_srt(cues, out_file)
    elif fmt == "vtt":
        content = engine.export_vtt(cues, out_file)
    elif fmt == "ass":
        content = engine.export_ass(cues, out_file, preset)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    return {
        "ok": True,
        "format": fmt,
        "file_path": str(out_file),
        "relative_path": str(out_file.relative_to(pdir)),
        "content_length": len(content),
        "content_preview": content[:1000],
    }


