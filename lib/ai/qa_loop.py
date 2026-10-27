"""Autonomous QA Revision Loop Engine (Phase 8).

Orchestrates the closed-loop cycle:
Render -> Inspect -> Identify Issues -> Apply Safe Fixes -> Re-render -> Recheck

Enforces strict termination guarantees:
- Maximum revision limit (default 2 passes)
- Monotonic improvement requirement (aborts if revisions do not resolve defects)
- Cyclic fix prevention (never repeats identical adjustments)
- Preserves best-verified artifact and outputs comprehensive audit reports
"""

from __future__ import annotations

import copy
import json
import logging
import time
from pathlib import Path
from typing import Any

from lib.ai.qa_fixer import IntelligentQAFixer
from lib.ai.qa_inspector import PostRenderQAInspector
from lib.ai.qa_models import QAReport, QASeverity

logger = logging.getLogger(__name__)


class AutonomousQALoop:
    """Executes closed-loop post-render quality assurance and bounded automatic repair."""

    def __init__(
        self,
        inspector: PostRenderQAInspector | None = None,
        fixer: IntelligentQAFixer | None = None,
    ):
        self.inspector = inspector or PostRenderQAInspector()
        self.fixer = fixer or IntelligentQAFixer()

    def run_revision_loop(
        self,
        video_path: Path | str,
        edit_decisions: dict[str, Any],
        composer: Any,
        transcript: list[dict[str, Any]] | None = None,
        understanding: Any | None = None,
        max_revisions: int = 2,
    ) -> tuple[Path, QAReport, dict[str, Any]]:
        """Run the automated QA inspection and bounded revision loop.

        Returns:
            (final_video_path, final_qa_report, final_edit_decisions)
        """
        t0 = time.time()
        video_path = Path(video_path).resolve()
        current_video_path = video_path
        current_edits = copy.deepcopy(edit_decisions)

        # 1. Initial Pass 0: Inspect original rendered video
        logger.info("Executing QA Pass 0: Post-render inspection on %s", video_path.name)
        initial_report = self.inspector.inspect(
            video_path=current_video_path,
            edit_decisions=current_edits,
            transcript=transcript,
            understanding=understanding,
        )
        initial_report.revision_count = 0

        # Save initial report
        init_json_path = video_path.parent / f"{video_path.stem}_initial_qa_report.json"
        initial_report.save(init_json_path)

        if initial_report.passed:
            logger.info("Video %s PASSED initial QA with score %.1f/100", video_path.name, initial_report.quality_score)
            return current_video_path, initial_report, current_edits

        logger.warning(
            "Video %s identified %d defect(s) (score: %.1f/100). Commencing automatic revision loop (max %d passes)...",
            video_path.name,
            len(initial_report.issues),
            initial_report.quality_score,
            max_revisions,
        )

        best_video_path = current_video_path
        best_report = initial_report
        best_edits = current_edits
        applied_fix_keys: set[str] = set()

        for rev in range(1, max_revisions + 1):
            logger.info("--- Commencing Revision Pass %d / %d ---", rev, max_revisions)

            # Filter unattempted auto-fixable issues
            fixable_issues = [
                i for i in best_report.issues
                if i.auto_fix_allowed and f"{i.category}_{i.suggested_fix}" not in applied_fix_keys
            ]

            if not fixable_issues:
                logger.info("Pass %d: No remaining eligible auto-fixable issues. Halting loop.", rev)
                break

            # Apply safe fixes to edit_decisions
            revised_edits, fix_records = self.fixer.apply_fixes(
                edit_decisions=best_edits,
                issues=fixable_issues,
                video_duration=best_report.duration_seconds,
            )

            if not fix_records:
                logger.info("Pass %d: Fixer produced 0 applicable corrections. Halting loop.", rev)
                break

            for r in fix_records:
                applied_fix_keys.add(f"{r.action}_{r.target_element}")
                logger.info("Applied Fix [%s]: %s -> %s (%s)", r.action, r.original_value, r.corrected_value, r.rationale)

            # Render revised video
            revised_output_path = video_path.parent / f"{video_path.stem}_revised.mp4"
            logger.info("Rendering revised video composition to %s...", revised_output_path.name)
            render_res = composer.execute({
                "operation": "remotion_render",
                "composition_id": "TalkingHead",
                "edit_decisions": revised_edits,
                "output_path": str(revised_output_path),
            })

            if not render_res.success:
                logger.error("Pass %d render failed: %s. Reverting to best verified version.", rev, render_res.error)
                break

            # Re-inspect revised video
            revised_report = self.inspector.inspect(
                video_path=revised_output_path,
                edit_decisions=revised_edits,
                transcript=transcript,
                understanding=understanding,
            )
            revised_report.revision_count = rev
            revised_report.fixes_applied = best_report.fixes_applied + fix_records

            logger.info(
                "Pass %d Inspection: Quality Score changed %.1f -> %.1f (Issues: %d -> %d)",
                rev,
                best_report.quality_score,
                revised_report.quality_score,
                len(best_report.issues),
                len(revised_report.issues),
            )

            # Monotonic improvement check
            if revised_report.quality_score >= best_report.quality_score:
                best_video_path = revised_output_path
                best_report = revised_report
                best_edits = revised_edits

                if revised_report.passed:
                    logger.info("Pass %d: Quality target achieved! Zero critical/high issues remaining.", rev)
                    break
            else:
                logger.warning("Pass %d: No measurable score improvement (%.1f < %.1f). Halting loop to prevent cycling.", rev, revised_report.quality_score, best_report.quality_score)
                break

        # Save final report and revised decision artifact
        final_json_path = video_path.parent / f"{video_path.stem}_qa_report.json"
        best_report.timing_sec["revision_loop_sec"] = round(time.time() - t0, 3)
        best_report.save(final_json_path)

        final_md_path = video_path.parent / f"{video_path.stem}_qa_report.md"
        with open(final_md_path, "w", encoding="utf-8") as f:
            f.write(best_report.to_markdown_summary())

        # Overwrite final decision JSON with verified edits
        final_decisions_path = video_path.parent / f"{video_path.stem}_edit_decisions.json"
        with open(final_decisions_path, "w", encoding="utf-8") as f:
            json.dump(best_edits, f, indent=2)

        return best_video_path, best_report, best_edits
