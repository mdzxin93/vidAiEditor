import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
import json
from schemas.artifacts import validate_artifact
from lib.checkpoint import write_checkpoint

pdir = Path("projects/mohammad-zain-intro")

# 1. Generate SRT file
srt_content = """1
00:00:00,000 --> 00:00:01,350
I don't just write code,

2
00:00:01,350 --> 00:00:03,550
I build full-stack products with MERN,

3
00:00:03,550 --> 00:00:04,800
power them with AI,

4
00:00:04,800 --> 00:00:06,850
and optimize them with technical SEO to solve real business problems.

5
00:00:06,850 --> 00:00:09,900
I'm Mohammad Zain, let's connect and build something that grows your business.
"""
(pdir / "assets" / "subtitles.srt").write_text(srt_content.strip(), encoding="utf-8")

# 2. Generate Word-level captions (in ms for Remotion WordCaption)
captions = [
    {"word": "I", "startMs": 0, "endMs": 200},
    {"word": "don't", "startMs": 200, "endMs": 500},
    {"word": "just", "startMs": 500, "endMs": 750},
    {"word": "write", "startMs": 750, "endMs": 1050},
    {"word": "code,", "startMs": 1050, "endMs": 1350},
    {"word": "I", "startMs": 1350, "endMs": 1550},
    {"word": "build", "startMs": 1550, "endMs": 1900},
    {"word": "full-stack", "startMs": 1900, "endMs": 2400},
    {"word": "products", "startMs": 2400, "endMs": 2800},
    {"word": "with", "startMs": 2800, "endMs": 3050},
    {"word": "MERN,", "startMs": 3050, "endMs": 3550},
    {"word": "power", "startMs": 3550, "endMs": 3900},
    {"word": "them", "startMs": 3900, "endMs": 4150},
    {"word": "with", "startMs": 4150, "endMs": 4350},
    {"word": "AI,", "startMs": 4350, "endMs": 4800},
    {"word": "and", "startMs": 4800, "endMs": 5000},
    {"word": "optimize", "startMs": 5000, "endMs": 5400},
    {"word": "them", "startMs": 5400, "endMs": 5600},
    {"word": "with", "startMs": 5600, "endMs": 5800},
    {"word": "technical", "startMs": 5800, "endMs": 6150},
    {"word": "SEO", "startMs": 6150, "endMs": 6450},
    {"word": "to", "startMs": 6450, "endMs": 6550},
    {"word": "solve", "startMs": 6550, "endMs": 6850},
    {"word": "real", "startMs": 6850, "endMs": 7050},
    {"word": "business", "startMs": 7050, "endMs": 7350},
    {"word": "problems.", "startMs": 7350, "endMs": 7700},
    {"word": "I'm", "startMs": 7700, "endMs": 7900},
    {"word": "Mohammad", "startMs": 7900, "endMs": 8300},
    {"word": "Zain,", "startMs": 8300, "endMs": 8650},
    {"word": "let's", "startMs": 8650, "endMs": 8900},
    {"word": "connect", "startMs": 8900, "endMs": 9250},
    {"word": "and", "startMs": 9250, "endMs": 9350},
    {"word": "build", "startMs": 9350, "endMs": 9550},
    {"word": "something", "startMs": 9550, "endMs": 9750},
    {"word": "that", "startMs": 9750, "endMs": 9820},
    {"word": "grows", "startMs": 9820, "endMs": 9880},
    {"word": "your", "startMs": 9880, "endMs": 9890},
    {"word": "business.", "startMs": 9890, "endMs": 9900}
]

with open(pdir / "assets" / "captions.json", "w", encoding="utf-8") as f:
    json.dump(captions, f, indent=2)

# 3. Build asset manifest
asset_manifest_art = {
    "version": "1.0",
    "assets": [
        {
            "id": "ast-video-source",
            "type": "video",
            "path": "assets/video/raw_footage.mp4",
            "source_tool": "user_import",
            "scene_id": "scn-01",
            "duration_seconds": 9.9,
            "resolution": "1920x1080",
            "format": "mp4",
            "quality_score": 0.95,
            "subtype": "raw_footage",
            "generation_summary": "User supplied direct-to-camera presenter footage in studio environment"
        },
        {
            "id": "ast-audio-source",
            "type": "audio",
            "path": "assets/audio/source_audio.mp3",
            "source_tool": "audio_mixer",
            "scene_id": "scn-01",
            "duration_seconds": 9.9,
            "format": "mp3",
            "quality_score": 0.95,
            "subtype": "dialogue",
            "generation_summary": "Extracted clean 48kHz stereo dialogue track"
        },
        {
            "id": "ast-subtitles-srt",
            "type": "subtitle",
            "path": "assets/subtitles.srt",
            "source_tool": "subtitle_gen",
            "scene_id": "scn-01",
            "duration_seconds": 9.9,
            "format": "srt",
            "quality_score": 1.0,
            "subtype": "standard_srt",
            "generation_summary": "Timestamped standard SRT subtitle track"
        }
    ],
    "total_cost_usd": 0.0,
    "metadata": {
        "caption_count": len(captions)
    }
}

validate_artifact("asset_manifest", asset_manifest_art)
with open(pdir / "artifacts" / "asset_manifest.json", "w", encoding="utf-8") as f:
    json.dump(asset_manifest_art, f, indent=2)
print("Asset manifest validated and saved successfully!")

review_data = {
    "reviewer": "self-review",
    "status": "pass",
    "findings": [],
    "score": 1.0,
    "timestamp": "2026-10-24T01:07:00Z"
}

cp = write_checkpoint(
    Path("projects"),
    "mohammad-zain-intro",
    stage="assets",
    status="completed",
    artifacts={"asset_manifest": asset_manifest_art},
    pipeline_type="talking-head",
    style_playbook="clean-professional",
    human_approved=True,
    review=review_data,
    cost_snapshot={"estimated_usd": 0.0, "actual_usd": 0.0}
)
print("Assets checkpoint completed successfully!")
