"""Render TalkingHead professional preview video for Mohammad Zain intro."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.video.video_compose import VideoCompose

def render_preview():
    pdir = Path("projects/mohammad-zain-intro").resolve()
    video_path = pdir / "assets" / "video" / "raw_footage.mp4"
    captions_path = pdir / "assets" / "captions.json"
    captions = json.loads(captions_path.read_text(encoding="utf-8"))

    # Natural cuts synced to speech pause boundaries with subtle, elegant framing
    cuts = [
        {
            "id": "cut-01",
            "source": str(video_path),
            "in_seconds": 0.0,
            "out_seconds": 1.15,
            "speed": 1.0,
            "transform": {"scale": 1.0, "position": "center"},
        },
        {
            "id": "cut-02",
            "source": str(video_path),
            "in_seconds": 1.15,
            "out_seconds": 3.00,
            "speed": 1.0,
            "transform": {"scale": 1.12, "position": "center"},
        },
        {
            "id": "cut-03",
            "source": str(video_path),
            "in_seconds": 3.00,
            "out_seconds": 4.10,
            "speed": 1.0,
            "transform": {"scale": 1.0, "position": "center"},
        },
        {
            "id": "cut-04",
            "source": str(video_path),
            "in_seconds": 4.10,
            "out_seconds": 6.45,
            "speed": 1.0,
            "transform": {"scale": 1.12, "position": "center"},
        },
        {
            "id": "cut-05",
            "source": str(video_path),
            "in_seconds": 6.45,
            "out_seconds": 9.88,
            "speed": 1.0,
            "transform": {"scale": 1.0, "position": "center"},
        },
    ]

    # No intrusive top overlay cards encroaching on presenter
    overlays = []

    comp_data = {
        "composition_id": "TalkingHead",
        "videoSrc": str(video_path),
        "cuts": cuts,
        "overlays": overlays,
        "captions": captions,
        "wordsPerPage": 6,
        "fontSize": 52,
        "highlightColor": "#22D3EE",
        "captionColor": "#FFFFFF",
        "captionBackgroundColor": "rgba(10, 15, 29, 0.70)",
        "captionPaddingBottom": 340,
        "durationInSeconds": 9.88,
        "metadata": {"duration": 9.88},
    }

    tool = VideoCompose()
    out_file = pdir / "renders" / "final_preview.mp4"
    final_file = pdir / "renders" / "final.mp4"

    res = tool._remotion_render({
        "composition_data": comp_data,
        "output_path": str(out_file),
        "render_preset": "balanced",
    })

    print("Result success:", res.success)
    if not res.success:
        print("Error:", res.error)
        return False

    print("Render complete:", out_file)
    print("File size bytes:", out_file.stat().st_size)

    # Copy to canonical deliverables
    shutil.copy2(out_file, final_file)
    print("Copied to canonical final:", final_file)

    # Copy to artifact directory
    artifact_dir = Path(r"C:\Users\moham\.gemini\antigravity-ide\brain\aa58768c-9b92-4d97-841e-2543be3b92af")
    artifact_preview = artifact_dir / "preview.mp4"
    shutil.copy2(out_file, artifact_preview)
    print("Copied to artifact preview:", artifact_preview)

    # Extract keyframes to inspect
    frames_dir = pdir / "renders" / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    timestamps = [
        ("0.6", "frame_01_hook.jpg"),
        ("2.1", "frame_02_mern.jpg"),
        ("3.5", "frame_03_ai.jpg"),
        ("5.3", "frame_04_seo.jpg"),
        ("7.1", "frame_05_zain.jpg"),
        ("8.9", "frame_06_cta.jpg"),
    ]
    for ts, name in timestamps:
        frame_out = frames_dir / name
        cmd = [
            "ffmpeg", "-y", "-ss", ts, "-i", str(out_file),
            "-vframes", "1", "-q:v", "2", str(frame_out)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if frame_out.exists():
            shutil.copy2(frame_out, artifact_dir / name)
            print(f"Extracted frame at {ts}s -> {frame_out.name}")

    return True

if __name__ == "__main__":
    render_preview()
