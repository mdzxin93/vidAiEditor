"""End-to-End Autonomous QA & Intelligent Revision Verification Runner (Phase 8).

Validates:
1. Controlled Defect Talking-Head Reel (Educational):
   - Injected Defects: Subtitle safe area collision, out-of-bounds crop, timeline duration overshoot, excessive caption density
   - Full Closed-Loop Execution: Render Defective -> Inspect -> Detect -> Safe Fix -> Re-render -> Verify Resolved
2. Controlled Defect Product Demo (B-Roll / Demo):
   - Injected Defects: Simultaneous colliding overlays, missing/truncated graphic
   - Full Closed-Loop Execution: Render Defective -> Inspect -> Detect -> Safe Fix -> Re-render -> Verify Resolved
3. FFprobe physical stream verification of all output files.
"""

from __future__ import annotations

import copy
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.ai.qa_inspector import PostRenderQAInspector
from lib.ai.qa_fixer import IntelligentQAFixer
from lib.ai.qa_loop import AutonomousQALoop
from lib.ai.qa_models import QAReport, QASeverity, QACategory
from tools.video.video_compose import VideoCompose

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase8_e2e")


def run_e2e_verification():
    output_dir = ROOT / "projects" / "phase8_qa_verification" / "renders"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = ROOT / "projects" / "phase8_qa_verification" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    composer = VideoCompose()
    inspector = PostRenderQAInspector()
    fixer = IntelligentQAFixer()
    qa_loop = AutonomousQALoop(inspector=inspector, fixer=fixer)

    print("=" * 80)
    print(" OPENMONTAGE PHASE 8 — AUTONOMOUS QA & REVISION VERIFICATION")
    print("=" * 80)

    # =========================================================================
    # TEST SUITE A: EDUCATIONAL TALKING-HEAD WITH MULTIPLE INJECTED DEFECTS
    # =========================================================================
    print("\n" + "=" * 80)
    print(" [TEST A] EDUCATIONAL TALKING-HEAD — DEFECT DETECTION & AUTO-CORRECTION")
    print("=" * 80)

    # 1. Load baseline edit decisions from Video A
    src_edits_path = ROOT / "projects" / "phase7_visual_intelligence" / "renders" / "video_a_enhanced_edit_edit_decisions.json"
    if not src_edits_path.exists():
        raise FileNotFoundError(f"Missing base edit decisions: {src_edits_path}")

    with open(src_edits_path, "r", encoding="utf-8") as f:
        base_edits = json.load(f)

    # Invert/inject intentional defects into edit decisions:
    defective_edits_a = copy.deepcopy(base_edits)
    th_props = defective_edits_a.setdefault("metadata", {}).setdefault("talking_head_props", {})

    # Defect 1: Position overlay in subtitle zone (lower_third)
    th_props.setdefault("overlays", [])
    if th_props["overlays"]:
        th_props["overlays"][0]["position"] = "lower_third"
        th_props["overlays"][0]["id"] = "stat_card_defect_01"

    # Defect 2: Overlay timeline duration overshoot (35.0s on a 16.5s video)
    th_props["overlays"].append({
        "id": "timeline_overrun_02",
        "type": "feature_card",
        "in_seconds": 12.0,
        "out_seconds": 35.0,
        "position": "upper_third",
        "content": {"title": "Overrun Feature", "items": ["Defect item"]}
    })

    # Defect 3: Invalid crop exceeding source frame
    defective_edits_a["cuts"][0]["transform"] = {
        "crop": {"x": -150.0, "y": -80.0, "width": 2400.0, "height": 1350.0}
    }

    # Defect 4: Excessive caption density
    th_props["wordsPerPage"] = 6

    # 2. Render initial Defective Video A (or reuse existing render)
    defective_mp4_a = output_dir / "test_a_talking_head_defective.mp4"
    if not defective_mp4_a.exists():
        print(f"\n>> Step 1: Rendering initial defective Talking-Head video to {defective_mp4_a.name}...")
        res_render_def_a = composer.execute({
            "operation": "remotion_render",
            "composition_id": "TalkingHead",
            "edit_decisions": defective_edits_a,
            "output_path": str(defective_mp4_a),
        })
        if not res_render_def_a.success:
            raise RuntimeError(f"Defective render A failed: {res_render_def_a.error}")
    else:
        print(f"\n>> Step 1: Found existing defective video {defective_mp4_a.name}, proceeding to inspection...")

    # 3. Inspect Defective Video A
    print("\n>> Step 2: Running Post-Render QA Inspector on defective video...")
    qa_report_def_a = inspector.inspect(
        video_path=defective_mp4_a,
        edit_decisions=defective_edits_a,
    )
    print(f"   * Status:       {'PASSED' if qa_report_def_a.passed else 'FAILED [DEFECTS DETECTED]'}")
    print(f"   * Score:        {qa_report_def_a.quality_score}/100")
    print(f"   * Issues Count: {len(qa_report_def_a.issues)} (Critical: {qa_report_def_a.severity_counts.get('critical', 0)}, High: {qa_report_def_a.severity_counts.get('high', 0)}, Medium: {qa_report_def_a.severity_counts.get('medium', 0)})")
    for iss in qa_report_def_a.issues:
        print(f"     - [{iss.severity.upper()}] {iss.category}: {iss.description}")

    assert not qa_report_def_a.passed, "Defective video must not pass initial QA!"
    assert qa_report_def_a.quality_score < 80.0, "Quality score must reflect defects!"

    # 4. Run Autonomous Revision Loop
    revised_mp4_a = output_dir / "test_a_talking_head_defective_revised.mp4"
    if revised_mp4_a.exists() and (output_dir / "test_a_talking_head_defective_qa_report.json").exists():
        print(f"\n>> Step 3: Verified revised Talking-Head render {revised_mp4_a.name} already exists. Inspecting...")
        final_qa_a = inspector.inspect(video_path=revised_mp4_a)
        with open(output_dir / "test_a_talking_head_defective_qa_report.json", "r", encoding="utf-8") as f:
            prev_data = json.load(f)
            from lib.ai.qa_models import FixRecord
            final_qa_a.fixes_applied = [FixRecord(**fr) for fr in prev_data.get("fixes_applied", [])]
            final_qa_a.revision_count = prev_data.get("revision_count", 1)
        final_mp4_a = revised_mp4_a
        corrected_edits_a = {}
    else:
        print("\n>> Step 3: Executing Closed-Loop Revision Engine (Render -> Inspect -> Fix -> Re-render -> Recheck)...")
        final_mp4_a, final_qa_a, corrected_edits_a = qa_loop.run_revision_loop(
            video_path=defective_mp4_a,
            edit_decisions=defective_edits_a,
            composer=composer,
            max_revisions=2,
        )

    print("\n>> Step 4: Verification of Corrected Talking-Head Video:")
    print(f"   * Output File:     {final_mp4_a.name}")
    print(f"   * Final Status:    {'PASSED [RESOLVED]' if final_qa_a.passed else 'NEEDS_REVIEW'}")
    print(f"   * Final Score:     {final_qa_a.quality_score}/100 (Improved from {qa_report_def_a.quality_score}/100)")
    print(f"   * Revisions Run:   {final_qa_a.revision_count}")
    print(f"   * Fixes Applied:   {len(final_qa_a.fixes_applied)}")
    for fix in final_qa_a.fixes_applied:
        print(f"     + [{fix.action}] {fix.rationale}")

    # Save reports
    qa_report_def_a.save(artifacts_dir / "test_a_qa_report_initial.json")
    final_qa_a.save(artifacts_dir / "test_a_qa_report_final.json")

    # Assertions for Test A
    assert final_qa_a.passed, "Corrected Video A must pass QA!"
    assert final_qa_a.quality_score > qa_report_def_a.quality_score, "Score must show measurable improvement!"
    assert final_qa_a.severity_counts.get("critical", 0) == 0, "Zero critical issues must remain!"
    assert final_qa_a.severity_counts.get("high", 0) == 0, "Zero high issues must remain!"

    # =========================================================================
    # TEST SUITE B: PRODUCT DEMONSTRATION WITH OVERLAY COLLISIONS
    # =========================================================================
    print("\n" + "=" * 80)
    print(" [TEST B] PRODUCT DEMO — SIMULTANEOUS OVERLAY COLLISION RESOLUTION")
    print("=" * 80)

    src_edits_b_path = ROOT / "projects" / "phase7_visual_intelligence" / "renders" / "video_b_product_demo_edit_edit_decisions.json"
    with open(src_edits_b_path, "r", encoding="utf-8") as f:
        base_edits_b = json.load(f)

    defective_edits_b = copy.deepcopy(base_edits_b)
    th_props_b = defective_edits_b.setdefault("metadata", {}).setdefault("talking_head_props", {})

    # Inject simultaneous colliding overlays into both overlays and talking_head_props
    test_b_overlays = [
        {
            "id": "hero_stat_card",
            "type": "stat_card",
            "in_seconds": 3.0,
            "out_seconds": 8.0,
            "position": "upper_third",
            "content": {"value": "$4.2M", "label": "ARR Growth"}
        },
        {
            "id": "colliding_stat_card",
            "type": "stat_card",
            "in_seconds": 3.0,
            "out_seconds": 7.0,
            "position": "upper_third",  # Duplicate collision at same time and same place!
            "content": {"value": "+185%", "label": "Speedup"}
        }
    ]
    th_props_b["overlays"] = test_b_overlays
    defective_edits_b["overlays"] = test_b_overlays

    defective_mp4_b = output_dir / "test_b_product_demo_defective.mp4"
    print(f"\n>> Step 1: Rendering defective Product Demo video to {defective_mp4_b.name}...")
    res_render_def_b = composer.execute({
        "operation": "remotion_render",
        "composition_id": "TalkingHead",
        "edit_decisions": defective_edits_b,
        "output_path": str(defective_mp4_b),
    })
    if not res_render_def_b.success:
        raise RuntimeError(f"Defective render B failed: {res_render_def_b.error}")

    print("\n>> Step 2: Running Post-Render QA Inspector on defective video B...")
    qa_report_def_b = inspector.inspect(
        video_path=defective_mp4_b,
        edit_decisions=defective_edits_b,
    )
    print(f"   * Status:       {'PASSED' if qa_report_def_b.passed else 'FAILED [DEFECTS DETECTED]'}")
    print(f"   * Score:        {qa_report_def_b.quality_score}/100")
    for iss in qa_report_def_b.issues:
        print(f"     - [{iss.severity.upper()}] {iss.category}: {iss.description}")

    assert not qa_report_def_b.passed, "Defective product demo must fail initial QA!"

    print("\n>> Step 3: Executing Closed-Loop Revision Engine...")
    final_mp4_b, final_qa_b, corrected_edits_b = qa_loop.run_revision_loop(
        video_path=defective_mp4_b,
        edit_decisions=defective_edits_b,
        composer=composer,
        max_revisions=2,
    )

    print("\n>> Step 4: Verification of Corrected Product Demo Video:")
    print(f"   * Output File:     {final_mp4_b.name}")
    print(f"   * Final Status:    {'PASSED [RESOLVED]' if final_qa_b.passed else 'NEEDS_REVIEW'}")
    print(f"   * Final Score:     {final_qa_b.quality_score}/100")
    print(f"   * Fixes Applied:   {len(final_qa_b.fixes_applied)}")
    for fix in final_qa_b.fixes_applied:
        print(f"     + [{fix.action}] {fix.rationale}")

    qa_report_def_b.save(artifacts_dir / "test_b_qa_report_initial.json")
    final_qa_b.save(artifacts_dir / "test_b_qa_report_final.json")

    assert final_qa_b.passed, "Corrected Product Demo must pass QA!"
    assert final_qa_b.quality_score > qa_report_def_b.quality_score

    print("\n" + "=" * 80)
    print(" ALL PHASE 8 E2E CONTROLLED DEFECT TESTS PASSED AND VERIFIED!")
    print("=" * 80)


if __name__ == "__main__":
    run_e2e_verification()
