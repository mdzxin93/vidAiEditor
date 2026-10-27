"""End-to-End Autonomous Editing Engine Pipeline.

Orchestrates:
Raw footage
→ transcription
→ scene analysis
→ multimodal understanding
→ AI editing plan
→ schema validation
→ Remotion / FFmpeg rendering
→ MP4 verification
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from lib.ai.autonomous_editor import AutonomousEditingPlanner
from lib.ai.config import AIEditorConfig
from lib.ai.observability import ObservabilityTracker
from lib.ai.providers.factory import get_model_provider
from lib.ai.video_understanding import VideoUnderstandingEngine
from lib.ai.qa_loop import AutonomousQALoop
from tools.video.video_compose import VideoCompose

logger = logging.getLogger(__name__)


class AutonomousEditingEngine:
    """Full autonomous video editing pipeline for OpenMontage."""

    def __init__(self, config: AIEditorConfig | None = None):
        self.config = config or AIEditorConfig.load()
        self.provider = get_model_provider(self.config)
        self.understanding_engine = VideoUnderstandingEngine(self.provider)
        self.planner = AutonomousEditingPlanner(self.provider, self.config)
        self.composer = VideoCompose()
        self.qa_loop = AutonomousQALoop()

    def run(
        self,
        video_path: str | Path,
        user_instruction: str,
        output_path: str | Path,
        transcript_path: str | Path | None = None,
        reference_video_path: str | Path | None = None,
        quality_preset: str = "balanced",
        job_id: str | None = None,
        auto_qa: bool = False,
        max_revisions: int = 2,
    ) -> dict[str, Any]:
        """Execute the full autonomous editing pipeline."""
        video_path = Path(video_path).resolve()
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if job_id is None:
            job_id = f"auto_edit_{int(time.time())}"

        tracker = ObservabilityTracker(job_id=job_id, log_dir=output_path.parent / "logs")
        tracker.metrics.user_instruction = user_instruction
        tracker.metrics.source_video = str(video_path)
        tracker.metrics.selected_provider = self.provider.name
        tracker.metrics.status = "in_progress"
        tracker.save()

        # Step 1: Probe video properties
        probe_meta = self._probe_video(video_path)
        video_duration = probe_meta.get("duration", 20.0)

        # Step 2: Acquire word-aligned transcript
        transcript = self._load_or_extract_transcript(video_path, transcript_path)

        # Step 3: Reference Video Style Analysis (Phase 6: Style Intelligence)
        style_profile = None
        style_profile_path = None
        if reference_video_path and Path(reference_video_path).exists():
            from lib.ai.style_analyzer import ReferenceStyleAnalyzer
            analyzer = ReferenceStyleAnalyzer()
            style_profile = analyzer.analyze_reference(reference_video_path)
            style_profile_path = output_path.parent / f"{output_path.stem}_style_profile.json"
            style_profile.save(style_profile_path)
            logger.info("Extracted style profile from reference: %s (pacing=%s) -> %s", reference_video_path, style_profile.pacing, style_profile_path)

        # Step 4: Multimodal Video Understanding (Phase C & K presets)
        sample_counts = {"fast": 5, "balanced": 8, "quality": 15}
        sample_frames = sample_counts.get(quality_preset, 8)

        t_start_vu = time.time()
        understanding_report = self.understanding_engine.analyze(
            video_path=video_path,
            transcript=transcript,
            sample_frame_count=sample_frames,
        )
        tracker.record_analysis_complete(time.time() - t_start_vu)

        # Step 5: Autonomous AI Editing Planning & Schema Conformance (Phase D & E)
        t_start_plan = time.time()
        video_meta = {
            "source_path": str(video_path),
            "duration": video_duration,
            "width": probe_meta.get("width", 3840),
            "height": probe_meta.get("height", 2160),
            "fps": probe_meta.get("fps", 25.0),
        }

        plan_result = self.planner.plan(
            understanding=understanding_report,
            transcript=transcript,
            user_prompt=user_instruction,
            video_metadata=video_meta,
            style_profile=style_profile,
        )
        plan_duration = time.time() - t_start_plan
        tracker.metrics.decision_source = plan_result.decision_source

        cuts = plan_result.edit_decisions.get("cuts", [])
        overlays = plan_result.edit_decisions.get("overlays", [])
        tracker.record_planning_complete(
            duration=plan_duration,
            cuts=len(cuts),
            zooms=plan_result.metrics.get("zooms_count", 0),
            overlays=len(overlays),
            val_failures=len(plan_result.errors),
        )

        # Save generated editing-decisions JSON
        decisions_json_path = output_path.parent / f"{output_path.stem}_edit_decisions.json"
        with open(decisions_json_path, "w", encoding="utf-8") as f:
            json.dump(plan_result.edit_decisions, f, indent=2)
        logger.info("Saved edit decisions to %s", decisions_json_path)

        # Step 5: Render via VideoCompose & Remotion
        t_start_render = time.time()
        logger.info("Submitting plan to VideoCompose (Remotion / TalkingHead)...")
        render_res = self.composer.execute({
            "operation": "remotion_render",
            "composition_id": "TalkingHead",
            "edit_decisions": plan_result.edit_decisions,
            "output_path": str(output_path),
        })

        render_duration = time.time() - t_start_render
        if not render_res.success:
            err_msg = f"Rendering failed: {render_res.error}"
            logger.error(err_msg)
            tracker.record_error(err_msg)
            return {
                "success": False,
                "error": err_msg,
                "edit_decisions_path": str(decisions_json_path),
                "telemetry_path": str(tracker.log_file),
            }

        # Step 6: Post-Render Autonomous QA & Bounded Revision Loop (Phase 8)
        qa_report_dict = None
        if auto_qa:
            logger.info("Auto-QA enabled: commencing post-render quality inspection...")
            final_path, qa_rep, final_edits = self.qa_loop.run_revision_loop(
                video_path=output_path,
                edit_decisions=plan_result.edit_decisions,
                composer=self.composer,
                transcript=transcript,
                understanding=understanding_report,
                max_revisions=max_revisions,
            )
            output_path = final_path
            plan_result.edit_decisions = final_edits
            qa_report_dict = qa_rep.to_dict()

        # Step 7: Verify Rendered MP4 via FFprobe
        verification = self._verify_mp4(output_path)
        tracker.record_render_complete(render_duration, str(output_path))

        return {
            "success": True,
            "output_path": str(output_path),
            "edit_decisions_path": str(decisions_json_path),
            "telemetry_path": str(tracker.log_file),
            "style_profile_path": str(style_profile_path) if style_profile_path else None,
            "style_similarity": plan_result.metrics.get("style_similarity"),
            "conflict_resolutions": plan_result.edit_decisions.get("metadata", {}).get("conflict_resolutions", []),
            "style_similarity_report": plan_result.edit_decisions.get("metadata", {}).get("style_similarity_report"),
            "decision_source": plan_result.decision_source,
            "provider": self.provider.name,
            "cuts_count": len(cuts),
            "zooms_count": plan_result.metrics.get("zooms_count", 0),
            "overlays_count": len(plan_result.edit_decisions.get("overlays", [])),
            "semantic_visual_plan": plan_result.edit_decisions.get("metadata", {}).get("semantic_visual_plan"),
            "broll_placements": plan_result.edit_decisions.get("metadata", {}).get("broll_placements", []),
            "provenance_breakdown": plan_result.edit_decisions.get("metadata", {}).get("provenance_breakdown", {}),
            "rejected_candidates_count": len(plan_result.edit_decisions.get("metadata", {}).get("rejected_candidates", [])),
            "verification": verification,
            "qa_report": qa_report_dict,
            "durations": {
                "analysis_sec": tracker.metrics.video_analysis_duration_sec,
                "planning_sec": tracker.metrics.planning_duration_sec,
                "render_sec": tracker.metrics.render_duration_sec,
                "total_sec": tracker.metrics.total_pipeline_duration_sec,
            },
        }

    def inspect_video(
        self,
        video_path: str | Path,
        edit_decisions_path: str | Path | None = None,
        transcript_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Perform standalone QA inspection on an existing rendered video."""
        video_path = Path(video_path).resolve()
        edits = {}
        if edit_decisions_path and Path(edit_decisions_path).exists():
            with open(edit_decisions_path, "r", encoding="utf-8") as f:
                edits = json.load(f)
        transcript = self._load_or_extract_transcript(video_path, transcript_path)
        rep = self.qa_loop.inspector.inspect(
            video_path=video_path,
            edit_decisions=edits,
            transcript=transcript,
        )
        return rep.to_dict()

    def _probe_video(self, video_path: Path) -> dict[str, Any]:
        """Probe video streams and format using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,r_frame_rate,duration:format=duration",
            "-of", "json", str(video_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            dur = float(data.get("format", {}).get("duration", 0.0))
            w = 1920
            h = 1080
            fps = 30.0
            if streams:
                w = int(streams[0].get("width", 1920))
                h = int(streams[0].get("height", 1080))
                fps_str = streams[0].get("r_frame_rate", "30/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    fps = float(num) / max(1.0, float(den))
                dur = float(streams[0].get("duration", dur))
            return {"width": w, "height": h, "fps": fps, "duration": dur}
        except Exception as e:
            logger.warning("ffprobe failed on %s: %s", video_path, e)
            return {"width": 1920, "height": 1080, "fps": 30.0, "duration": 20.0}

    def _load_or_extract_transcript(
        self, video_path: Path, transcript_path: str | Path | None
    ) -> list[dict[str, Any]]:
        """Load pre-aligned transcript JSON or run Transcriber tool."""
        if transcript_path and Path(transcript_path).exists():
            with open(transcript_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, list):
                    return raw
                if isinstance(raw, dict) and "words" in raw:
                    return raw["words"]

        # Check for adjacent captions file
        cand = video_path.parent / "captions_aligned.json"
        if cand.exists():
            with open(cand, "r", encoding="utf-8") as f:
                return json.load(f)

        # Fallback to faster-whisper transcriber tool
        from tools.analysis.transcriber import Transcriber
        t = Transcriber()
        r = t.execute({"input_path": str(video_path), "word_timestamps": True})
        if r.success and "words" in r.data:
            return r.data["words"]
        return []

    def _verify_mp4(self, output_path: Path) -> dict[str, Any]:
        """Verify output MP4 container and stream parameters."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,codec_type,width,height:format=duration,size",
            "-of", "json", str(output_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        
        streams = data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
        
        return {
            "file_size_bytes": int(data.get("format", {}).get("size", 0)),
            "duration_seconds": float(data.get("format", {}).get("duration", 0.0)),
            "video_codec": v_stream.get("codec_name"),
            "resolution": f"{v_stream.get('width')}x{v_stream.get('height')}",
            "audio_codec": a_stream.get("codec_name"),
            "valid": bool(v_stream.get("codec_name") == "h264" and v_stream.get("width") == 1080 and v_stream.get("height") == 1920),
        }
