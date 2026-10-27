"""CLI runner for OpenMontage Autonomous AI Editing Engine (Phase 3)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.ai.config import AIEditorConfig
from lib.ai.pipeline import AutonomousEditingEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    parser = argparse.ArgumentParser(description="OpenMontage Autonomous AI Video Editor")
    parser.add_argument(
        "--input", "-i",
        default="media/sample/sample_raw.mp4",
        help="Path to source raw video file",
    )
    parser.add_argument(
        "--instruction", "-m",
        default="Edit this 30-second talking-head video into an engaging Instagram Reel. Remove long pauses, highlight important words, use zooms sparingly, add relevant motion graphics, and export in 9:16.",
        help="Natural language editing instruction",
    )
    parser.add_argument(
        "--output", "-o",
        default="projects/phase3_autonomous/renders/autonomous_reel.mp4",
        help="Path for rendered output MP4",
    )
    parser.add_argument(
        "--transcript", "-t",
        default="media/sample/captions_aligned.json",
        help="Optional path to word-aligned transcript JSON",
    )
    parser.add_argument(
        "--provider", "-p",
        default=None,
        help="Override provider: heuristic_engine | local_vlm | local_llm | remote_api",
    )
    parser.add_argument(
        "--reference", "-r",
        default=None,
        help="Optional path to reference video for style profile analysis",
    )
    parser.add_argument(
        "--preset",
        default="balanced",
        choices=["fast", "balanced", "quality"],
        help="Performance and analysis quality preset (fast | balanced | quality)",
    )
    parser.add_argument(
        "--auto-qa",
        action="store_true",
        help="Enable post-render autonomous QA inspection and bounded revision loop (Phase 8)",
    )
    parser.add_argument(
        "--max-revisions",
        type=int,
        default=2,
        help="Maximum automatic revision passes allowed in closed-loop QA (default: 2)",
    )
    parser.add_argument(
        "--qa-only",
        action="store_true",
        help="Inspect existing rendered video without executing full editorial pipeline",
    )
    parser.add_argument(
        "--edit-decisions",
        default=None,
        help="Optional path to edit decisions JSON (used with --qa-only)",
    )

    args = parser.parse_args()

    cfg = AIEditorConfig.load()
    if args.provider:
        cfg.provider = args.provider

    print("=" * 70)
    print(" OPENMONTAGE — AUTONOMOUS AI EDITING & QA ENGINE (PHASE 8)")
    print("=" * 70)

    engine = AutonomousEditingEngine(config=cfg)

    # Standalone QA-Only Inspection Mode
    if args.qa_only:
        print(f" Mode:           QA-Only Video Inspection")
        print(f" Target Video:   {args.input}")
        print(f" Edit Decisions: {args.edit_decisions or 'Inferred/None'}")
        print("-" * 70)
        qa_res = engine.inspect_video(
            video_path=args.input,
            edit_decisions_path=args.edit_decisions,
            transcript_path=args.transcript,
        )
        sev = qa_res.get("severity_counts", {})
        print(" QA INSPECTION RESULTS:")
        print(f" Overall Status: {'PASSED [OK]' if qa_res.get('passed') else 'FAILED [DEFECTS DETECTED]'}")
        print(f" Quality Score:  {qa_res.get('quality_score', 0)} / 100")
        print(f" Total Issues:   {len(qa_res.get('issues', []))} (Critical: {sev.get('critical', 0)}, High: {sev.get('high', 0)}, Medium: {sev.get('medium', 0)}, Low: {sev.get('low', 0)})")
        print(f" Stream Specs:   {qa_res.get('resolution')} ({qa_res.get('duration_seconds')}s, {qa_res.get('frames_inspected')} frames inspected)")
        print(" Issue Breakdown:")
        for iss in qa_res.get("issues", []):
            fix_str = f" [Auto-Fix: {iss.get('suggested_fix')}]" if iss.get('auto_fix_allowed') else " [Manual Review]"
            print(f"   * [{iss.get('severity').upper()}] @ {iss.get('start_seconds')}s-{iss.get('end_seconds')}s ({iss.get('category')}): {iss.get('description')}{fix_str}")
        print("=" * 70)
        return

    print(f" Input Video:   {args.input}")
    print(f" Instruction:   {args.instruction}")
    print(f" Reference:     {args.reference or 'None (Baseline Mode)'}")
    print(f" Preset:        {args.preset}")
    print(f" Output Target: {args.output}")
    print(f" Provider:      {cfg.provider}")
    print(f" Auto-QA:       {'Enabled (Max Revisions: ' + str(args.max_revisions) + ')' if args.auto_qa else 'Disabled'}")
    print("-" * 70)

    result = engine.run(
        video_path=args.input,
        user_instruction=args.instruction,
        output_path=args.output,
        transcript_path=args.transcript,
        reference_video_path=args.reference,
        quality_preset=args.preset,
        auto_qa=args.auto_qa,
        max_revisions=args.max_revisions,
        job_id="phase8_autonomous_run",
    )

    print("-" * 70)
    if result["success"]:
        print(" SUCCESS! Autonomous Editing & Rendering Completed.")
        print(f" Output MP4:         {result['output_path']}")
        print(f" Decision Artifact:  {result['edit_decisions_path']}")
        print(f" Telemetry Log:      {result['telemetry_path']}")
        if result.get("qa_report"):
            qa = result["qa_report"]
            print(f" QA Verification:    Status={'PASSED' if qa.get('passed') else 'NEEDS_REVIEW'}, Score={qa.get('quality_score')}/100, Revisions={qa.get('revision_count')}, Fixes Applied={len(qa.get('fixes_applied', []))}")
            for fix in qa.get("fixes_applied", []):
                print(f"   -> Applied Fix: [{fix.get('fix_type')}] {fix.get('description')}")
            if qa.get("remaining_issues"):
                print(f"   -> Remaining Unresolved Issues: {len(qa['remaining_issues'])}")
        if result.get("style_profile_path"):
            print(f" Style Profile:      {result['style_profile_path']}")
        if result.get("style_similarity") is not None:
            sim_pct = int(result["style_similarity"] * 100)
            print(f" Style Similarity:   {sim_pct}% objective match to reference")
        conflicts = result.get("conflict_resolutions", [])
        if conflicts:
            print(" Conflict Hierarchy: Resolved 4-Tier Prioritization:")
            for c in conflicts[:4]:
                print(f"   * [{c.get('winning_tier_name', 'tier')}] {c.get('parameter')}: {c.get('chosen_value')} (Reason: {c.get('reason')})")
        sim_rep = result.get("style_similarity_report")
        if sim_rep and sim_rep.get("shared_style_traits"):
            print(" Transferred Traits:")
            for trait in sim_rep["shared_style_traits"][:3]:
                print(f"   + {trait}")
        if sim_rep and sim_rep.get("intentional_deviations"):
            print(" Intentional Deviations:")
            for dev in sim_rep["intentional_deviations"][:2]:
                print(f"   - {dev}")
        print(f" Decision Source:    {result['decision_source']}")
        print(f" Cuts Applied:       {result['cuts_count']}")
        print(f" Zooms Applied:      {result['zooms_count']}")
        print(f" Overlays Created:   {result['overlays_count']}")
        svp = result.get("semantic_visual_plan")
        if svp:
            print(f" Visual Plan:        {svp.get('total_visuals_placed')} supporting visual(s) ({svp.get('visuals_per_minute')}/min), {svp.get('total_candidates_evaluated')} candidates evaluated")
            for ve in svp.get("visual_events", [])[:3]:
                print(f"   * [{ve.get('treatment_type')}] @ {ve.get('start_seconds')}s-{ve.get('end_seconds')}s (rel: {ve.get('relevance_score')}) -> '{ve.get('source_phrase', '')[:40]}...'")
        broll = result.get("broll_placements", [])
        if broll:
            print(f" B-Roll Placements:  {len(broll)} clip(s) matched")
            for b in broll[:2]:
                print(f"   * [{b.get('type')}] '{b.get('keyword')}' @ {b.get('start')}s-{b.get('end')}s ({b.get('reason')})")
        bd = result.get("provenance_breakdown", {})
        if bd:
            print(f" Provenance:         Neural VLM={bd.get('neural_vlm', 0)}, Heuristics={bd.get('deterministic_heuristic', 0)}, Script={bd.get('script_directive', 0)}, Defaults={bd.get('template_default', 0)} (Neural Ratio: {bd.get('neural_ratio', 0.0)})")
        if result.get("rejected_candidates_count", 0) > 0:
            print(f" Pacing Rest (Neg):  {result['rejected_candidates_count']} treatments rejected or silenced for temporal spacing (>=2.5s rest interval)")
        v = result["verification"]
        print(f" Verified Stream:    {v.get('video_codec')} {v.get('resolution')} ({v.get('duration_seconds')}s, {round(v.get('file_size_bytes', 0)/(1024**2), 2)} MB)")
        d = result["durations"]
        print(f" Timing: Analysis={d['analysis_sec']}s, Plan={d['planning_sec']}s, Render={d['render_sec']}s, Total={d['total_sec']}s")
    else:
        print(" FAILED:", result["error"])
        sys.exit(1)
    print("=" * 70)


if __name__ == "__main__":
    main()
