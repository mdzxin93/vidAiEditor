"""Render autonomous edit with dynamic punch zoom, v3 B-roll overlays, SFX, and kinetic captions."""

import json
import logging
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    from tools.subtitle.kinetic_caption_engine import KineticCaptionEngine

    video_path = REPO_ROOT / "lib" / "Video Project.mp4"
    output_dir = REPO_ROOT / "projects" / "sample-1" / "renders"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_mp4 = output_dir / "Video_Project_Autonomous_Edit.mp4"

    engine = KineticCaptionEngine()
    print(f"Executing autonomous edit on {video_path}...")
    t0 = time.time()

    result = engine.execute({
        "video_path": str(video_path),
        "output_path": str(output_mp4),
        "preset_id": "kinetic_podcast_reference",
        "video_style": "dynamic_zoom",
        "zoom_intensity": "dynamic",
        "enable_broll": True,
        "words_per_cue": 2,
        "emphasis_frequency": 0.25,
        "export_formats": ["mp4", "srt", "vtt", "ass"],
    })

    elapsed = round(time.time() - t0, 2)
    print(f"Finished in {elapsed}s. Success: {result.success}")

    if not result.success:
        print(f"Error: {result.error}")
        sys.exit(1)

    print("Result data keys:", list(result.data.keys()))
    print("Overlays planned:", len(result.data.get("overlays", [])))
    print("Cuts planned:", len(result.data.get("cuts", [])))
    print("Exports:", result.data.get("exports"))

    # Also save EDL v3 to project artifacts
    artifacts_dir = REPO_ROOT / "projects" / "sample-1" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    if result.data.get("edl"):
        edl_file = artifacts_dir / "edit_plan_v3.json"
        with open(edl_file, "w", encoding="utf-8") as f:
            json.dump(result.data["edl"], f, indent=2)
        print("Saved EDL v3 to:", edl_file)

    if output_mp4.exists():
        print(f"Rendered video created: {output_mp4} ({output_mp4.stat().st_size} bytes)")
    else:
        print(f"Warning: Output file does not exist at {output_mp4}")

if __name__ == "__main__":
    main()
