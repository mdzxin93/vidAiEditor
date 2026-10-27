"""Media Asset Manager & Security Inspector (Phase 9).

Handles:
- Uploading and validating raw footage, B-roll, reference videos, and audio.
- Strict path confinement to prevent path traversal.
- File integrity checks and probe metadata via FFprobe.
- Media listings and deduplication to prevent accidental overwriting.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from lib.paths import PROJECTS_DIR
from lib.api.cache_manager import cache_manager

logger = logging.getLogger("openmontage.media")

ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
ALLOWED_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
ALL_ALLOWED_EXTS = ALLOWED_VIDEO_EXTS | ALLOWED_AUDIO_EXTS | ALLOWED_IMAGE_EXTS

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB limit


def sanitize_filename(name: str) -> str:
    """Sanitize filename to prevent directory traversal and invalid characters."""
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
    clean = clean.lstrip("._")
    return clean or "unnamed_media"


def get_safe_project_dir(project_id: str) -> Path:
    """Ensure project_id is safe and returns existing project dir."""
    if any(c in project_id for c in "/\\:") or project_id in (".", ".."):
        raise ValueError(f"Invalid project id: {project_id}")
    pdir = (PROJECTS_DIR / project_id).resolve()
    if not pdir.is_dir():
        if project_id == "project_demo":
            try:
                from lib.checkpoint import init_project
                init_project("project_demo", title="Demo Project", pipeline_type="animated-explainer")
                if pdir.is_dir():
                    return pdir
            except Exception:
                pass
        raise FileNotFoundError(f"Project directory not found: {project_id}")
    return pdir


def probe_media_file(file_path: Path) -> dict[str, Any]:
    """Inspect video/audio stream properties using FFprobe with deterministic caching."""
    if not file_path.is_file():
        return {"error": "File not found"}

    cached = cache_manager.get_cached_probe(file_path)
    if cached:
        return cached

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_name,codec_type,width,height,r_frame_rate,duration,channels,sample_rate,bit_rate:format=duration,size,bit_rate,format_name",
        "-of", "json",
        str(file_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15)
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        duration = float(fmt.get("duration", 0.0))
        if duration == 0.0 and video_stream and "duration" in video_stream:
            duration = float(video_stream["duration"])

        w = int(video_stream.get("width", 0)) if video_stream else 0
        h = int(video_stream.get("height", 0)) if video_stream else 0

        fps = 30.0
        if video_stream and "r_frame_rate" in video_stream:
            r = video_stream["r_frame_rate"]
            if "/" in r:
                num, den = r.split("/")
                fps = round(float(num) / max(1.0, float(den)), 2)

        aspect = "unknown"
        if w > 0 and h > 0:
            ratio = w / h
            if abs(ratio - 9/16) < 0.05:
                aspect = "9:16"
            elif abs(ratio - 16/9) < 0.05:
                aspect = "16:9"
            elif abs(ratio - 1.0) < 0.05:
                aspect = "1:1"
            elif abs(ratio - 4/5) < 0.05:
                aspect = "4:5"
            else:
                aspect = f"{w}:{h}"

        result = {
            "file_name": file_path.name,
            "size_bytes": file_path.stat().st_size,
            "duration": round(duration, 3),
            "width": w,
            "height": h,
            "fps": fps,
            "aspect_ratio": aspect,
            "video_codec": video_stream.get("codec_name") if video_stream else None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "audio_channels": int(audio_stream.get("channels", 0)) if audio_stream else 0,
            "sample_rate": int(audio_stream.get("sample_rate", 0)) if audio_stream else 0,
            "format": fmt.get("format_name", file_path.suffix.lstrip(".")),
        }
        cache_manager.store_cached_probe(file_path, result)
        return result
    except Exception as e:
        logger.warning("ffprobe failed on %s: %s", file_path, e)
        return {
            "file_name": file_path.name,
            "size_bytes": file_path.stat().st_size,
            "duration": 0.0,
            "error": str(e),
        }


def save_uploaded_media(
    project_id: str,
    filename: str,
    content: bytes,
    category: str = "video",  # "video", "broll", "reference", "audio", "music"
    overwrite: bool = False,
) -> dict[str, Any]:
    """Store uploaded media file securely in project asset directory."""
    project_dir = get_safe_project_dir(project_id)
    clean_name = sanitize_filename(filename)
    ext = Path(clean_name).suffix.lower()

    if ext not in ALL_ALLOWED_EXTS:
        raise ValueError(f"Unsupported media format '{ext}'. Allowed: {sorted(ALL_ALLOWED_EXTS)}")

    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File exceeds maximum size limit of 2 GB")

    sub_dir_map = {
        "video": "assets/video",
        "broll": "assets/broll",
        "reference": "assets/reference",
        "audio": "assets/audio",
        "music": "assets/music",
        "images": "assets/images",
    }
    target_sub = sub_dir_map.get(category, "assets/video")
    dest_dir = (project_dir / target_sub).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / clean_name
    if dest_file.exists() and not overwrite:
        # Prevent accidental overwrite by disambiguating filename
        stem = Path(clean_name).stem
        count = 1
        while (dest_dir / f"{stem}_{count}{ext}").exists():
            count += 1
        dest_file = dest_dir / f"{stem}_{count}{ext}"

    with open(dest_file, "wb") as f:
        f.write(content)

    rel_path = dest_file.relative_to(project_dir).as_posix()
    probe_info = probe_media_file(dest_file)
    probe_info["name"] = dest_file.name
    probe_info["relative_path"] = rel_path
    probe_info["category"] = category
    probe_info["is_primary"] = (category == "video")
    return probe_info


def list_project_media(project_id: str) -> list[dict[str, Any]]:
    """Enumerate all media assets in the project with metadata and thumbnail endpoints."""
    project_dir = get_safe_project_dir(project_id)
    media_list = []

    scan_folders = [
        ("assets/video", "video"),
        ("assets/broll", "broll"),
        ("assets/reference", "reference"),
        ("assets/audio", "audio"),
        ("assets/music", "music"),
        ("assets/images", "image"),
        ("renders", "render"),
    ]

    for sub, cat in scan_folders:
        folder = project_dir / sub
        if not folder.is_dir():
            continue
        for item in sorted(folder.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not item.is_file():
                continue
            ext = item.suffix.lower()
            if ext not in ALL_ALLOWED_EXTS:
                continue

            rel_path = item.relative_to(project_dir).as_posix()
            stat = item.stat()

            thumb_url = f"/thumb/{project_id}/{rel_path}?w=320" if ext in ALLOWED_VIDEO_EXTS | ALLOWED_IMAGE_EXTS else None
            media_url = f"/media/{project_id}/{rel_path}"

            media_list.append({
                "name": item.name,
                "relative_path": rel_path,
                "category": cat,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "thumbnail_url": thumb_url,
                "media_url": media_url,
                "is_video": ext in ALLOWED_VIDEO_EXTS,
                "is_audio": ext in ALLOWED_AUDIO_EXTS,
                "is_image": ext in ALLOWED_IMAGE_EXTS,
            })

    return media_list
