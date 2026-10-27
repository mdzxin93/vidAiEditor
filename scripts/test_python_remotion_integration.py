"""Integration test verifying Python -> Remotion -> FFmpeg pipeline in OpenMontage.

Tests:
1. Python generating structured JSON editing instructions.
2. Direct composition selection in Remotion (Explainer).
3. Passing cuts, animations, captions, overlays, and audio into Remotion.
4. Executing Remotion rendering via Python VideoCompose.
5. Verifying the resulting MP4 container, video stream, and audio stream with FFprobe.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Ensure OpenMontage root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.video.video_compose import VideoCompose


def main() -> int:
    print("=" * 60)
    print("OpenMontage: Python + Remotion Integration Test")
    print("=" * 60)

    # 1. Locate sample media assets
    speaker_img = ROOT_DIR / "media" / "sample" / "preview_speaker_intro.jpg"
    drop_stat_img = ROOT_DIR / "media" / "sample" / "preview_drop_stat.jpg"
    voiceover_audio = ROOT_DIR / "projects" / "sample_edit" / "voiceover.mp3"
    ambient_music = ROOT_DIR / "projects" / "sample_edit" / "ambient_bed.mp3"
    captions_file = ROOT_DIR / "media" / "sample" / "captions_aligned.json"

    for asset in [speaker_img, drop_stat_img, voiceover_audio, ambient_music, captions_file]:
        if not asset.exists():
            print(f"Error: Required sample asset not found: {asset}")
            return 1

    # Load first 20 word captions (covering 0.5s to ~8.0s)
    with captions_file.open("r", encoding="utf-8") as f:
        all_captions = json.load(f)
    test_captions = [c for c in all_captions if c.get("start", 0) <= 8.5]

    output_dir = ROOT_DIR / "projects" / "integration_test" / "renders"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_mp4 = output_dir / "python_remotion_test.mp4"

    # 2. Build structured JSON editing instructions
    edit_decisions = {
        "version": "1.0",
        "render_runtime": "remotion",
        "renderer_family": "explainer-data",
        "theme": "flat-motion-graphics",
        "cuts": [
            # Cut 1: Zoom In + Transition
            {
                "id": "cut-1",
                "source": str(speaker_img),
                "in_seconds": 0.0,
                "out_seconds": 3.0,
                "animation": "zoom-in",
                "transition_in": "fade",
                "transition_duration": 0.5,
                "reason": "Establish speaker introduction with subtle push-in",
            },
            # Cut 2: Motion Graphics & Text Animation (Stat Card)
            {
                "id": "cut-2",
                "type": "stat_card",
                "stat": "90 min",
                "subtitle": "Optimal Focus Window",
                "accentColor": "#F59E0B",
                "in_seconds": 3.0,
                "out_seconds": 6.0,
                "transition_in": "dissolve",
                "transition_out": "fade",
                "transition_duration": 0.4,
                "reason": "Motion graphic stat card highlighting the 90 minute rule",
            },
            # Cut 3: Zoom Out + Transition
            {
                "id": "cut-3",
                "source": str(drop_stat_img),
                "in_seconds": 6.0,
                "out_seconds": 8.5,
                "animation": "zoom-out",
                "transition_in": "fade",
                "transition_duration": 0.5,
                "reason": "Concluding graphic showing capacity curve with pull-out",
            },
        ],
        "overlays": [
            {
                "type": "section_title",
                "in_seconds": 0.2,
                "out_seconds": 3.0,
                "text": "FOCUS SCIENCE",
                "accentColor": "#22D3EE",
                "position": "top-left",
            }
        ],
        "captions": test_captions,
        "audio": {
            "narration": {
                "src": str(voiceover_audio),
                "volume": 1.0,
            },
            "music": {
                "src": str(ambient_music),
                "volume": 0.25,
                "fadeInSeconds": 1.0,
                "fadeOutSeconds": 1.5,
            },
        },
    }

    print(f"Target Output: {output_mp4}")
    print(f"Cuts count:    {len(edit_decisions['cuts'])}")
    print(f"Captions:      {len(edit_decisions['captions'])} words")
    print(f"Narration:     {voiceover_audio.name}")
    print(f"Music:         {ambient_music.name}")
    print()

    # 3. Trigger Python VideoCompose tool
    print("Step 1: Invoking VideoCompose.execute() from Python...")
    composer = VideoCompose()
    result = composer.execute({
        "operation": "remotion_render",
        "composition_id": "Explainer",
        "edit_decisions": edit_decisions,
        "output_path": str(output_mp4),
        "remotion_timeout_ms": 60000,
    })

    if not result.success:
        print(f"[FAIL] VideoCompose failed: {result.error}")
        return 1

    print(f"[SUCCESS] VideoCompose succeeded!")
    print(f"Exported path: {output_mp4}")
    print(f"File size:     {output_mp4.stat().st_size:,} bytes")
    print()

    # 4. Verify output using FFprobe
    print("Step 2: Probing output video using FFprobe...")
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(output_mp4),
    ]
    probe_run = subprocess.run(cmd, capture_output=True, text=True)
    if probe_run.returncode != 0:
        print(f"[FAIL] FFprobe failed: {probe_run.stderr}")
        return 1

    probe_data = json.loads(probe_run.stdout)
    fmt = probe_data.get("format", {})
    streams = probe_data.get("streams", [])

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not video_streams:
        print("[FAIL] No video stream found in output!")
        return 1

    v = video_streams[0]
    print(f"[OK] Video Stream Verified:")
    print(f"   Codec:      {v.get('codec_name')} ({v.get('codec_long_name')})")
    print(f"   Resolution: {v.get('width')}x{v.get('height')}")
    print(f"   Frame Rate: {v.get('r_frame_rate')} ({v.get('nb_frames')} frames)")
    print(f"   Duration:   {v.get('duration')}s")

    if not audio_streams:
        print("[FAIL] No audio stream found in output!")
        return 1

    a = audio_streams[0]
    print(f"[OK] Audio Stream Verified:")
    print(f"   Codec:      {a.get('codec_name')} ({a.get('codec_long_name')})")
    print(f"   Sample Rate:{a.get('sample_rate')} Hz")
    print(f"   Channels:   {a.get('channels')} ({a.get('channel_layout')})")
    print(f"   Duration:   {a.get('duration')}s")

    print()
    print("=" * 60)
    print("ALL TESTS PASSED: Python-to-Remotion integration verified!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
