"""Analyze reference video frame by frame for Phase 2."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def analyze():
    video_path = Path("projects/sample-1/assets/reference/Video-42679.mp4")
    if not video_path.exists():
        video_path = Path("projects/zain/assets/reference/Video-42679.mp4")
    print(f"Analyzing {video_path}...")

    frames_dir = Path("remotion-composer/scratch_extracted/ref_frames")
    frames_dir.mkdir(parents=True, exist_ok=True)

    timestamps = ["0.8", "2.0", "3.6", "4.2", "5.2", "7.0", "8.8", "10.8", "13.0", "15.0", "18.8", "21.0"]
    for ts in timestamps:
        safe_ts = ts.replace(".", "_")
        out = frames_dir / f"frame_{safe_ts}.jpg"
        cmd = ["ffmpeg", "-y", "-ss", ts, "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(out)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if out.exists():
            print(f"Extracted {out.name} ({out.stat().st_size} bytes)")

    # Run transcriber to inspect spoken audio
    from tools.analysis.transcriber import Transcriber
    t = Transcriber()
    res = t.execute({"input_path": str(video_path), "model_size": "base", "output_dir": str(frames_dir)})
    print("Transcription success:", res.success)
    if res.success:
        transcript_path = frames_dir / f"{video_path.stem}_transcript.json"
        print("Transcript saved to:", transcript_path)
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(res.data, f, indent=2)

if __name__ == "__main__":
    analyze()
