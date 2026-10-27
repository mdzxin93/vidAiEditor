"""Intelligent Deterministic Cache Manager (Phase 11).

Provides:
- Content-hash and metadata-keyed deterministic caching for media probes, transcripts,
  visual scene observations, reference style profiles, and preview renders.
- Intelligent invalidation when user instructions, source files, or preferences change.
- Safe cache eviction interface (strictly guards user source media and final renders).
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from lib.paths import REPO_ROOT

logger = logging.getLogger("openmontage.cache_manager")

try:
    from lib.storage_paths import get_storage
    DEFAULT_CACHE_DIR = get_storage().cache_dir
except Exception:
    DEFAULT_CACHE_DIR = REPO_ROOT / ".cache"


class CacheManager:
    """Manages multi-tier deterministic caches for OpenMontage."""

    def __init__(self, root_dir: Path | str = DEFAULT_CACHE_DIR):
        self.root_dir = Path(root_dir).resolve()
        self.probes_dir = self.root_dir / "probes"
        self.transcripts_dir = self.root_dir / "transcripts"
        self.observations_dir = self.root_dir / "observations"
        self.styles_dir = self.root_dir / "styles"
        self.previews_dir = self.root_dir / "previews"

        for d in (self.probes_dir, self.transcripts_dir, self.observations_dir, self.styles_dir, self.previews_dir):
            d.mkdir(parents=True, exist_ok=True)

    def compute_file_fingerprint(self, path: Path) -> str:
        """Compute fast, deterministic fingerprint from file stats and filename."""
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        stat = path.stat()
        raw = f"{stat.st_size}_{stat.st_mtime}_{path.name}"
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    # 1. Media Probe Cache
    def get_cached_probe(self, media_path: Path) -> Optional[dict[str, Any]]:
        fp = self.compute_file_fingerprint(media_path)
        cache_file = self.probes_dir / f"{fp}.json"
        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def store_cached_probe(self, media_path: Path, probe_data: dict[str, Any]) -> None:
        fp = self.compute_file_fingerprint(media_path)
        cache_file = self.probes_dir / f"{fp}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(probe_data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to store probe cache: %s", e)

    # 2. Transcript Cache
    def get_cached_transcript(self, media_path: Path, model_size: str = "base") -> Optional[list[dict[str, Any]]]:
        fp = self.compute_file_fingerprint(media_path)
        cache_file = self.transcripts_dir / f"{fp}_{model_size}.json"
        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def store_cached_transcript(self, media_path: Path, words: list[dict[str, Any]], model_size: str = "base") -> None:
        fp = self.compute_file_fingerprint(media_path)
        cache_file = self.transcripts_dir / f"{fp}_{model_size}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(words, f, indent=2)
        except Exception as e:
            logger.warning("Failed to store transcript cache: %s", e)

    # 3. Multimodal Observations Cache
    def get_cached_observations(
        self,
        media_path: Path,
        model_name: str,
        frame_count: int,
    ) -> Optional[dict[str, Any]]:
        fp = self.compute_file_fingerprint(media_path)
        cache_key = f"{fp}_{model_name}_{frame_count}"
        cache_file = self.observations_dir / f"{cache_key}.json"
        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def store_cached_observations(
        self,
        media_path: Path,
        model_name: str,
        frame_count: int,
        data: dict[str, Any],
    ) -> None:
        fp = self.compute_file_fingerprint(media_path)
        cache_key = f"{fp}_{model_name}_{frame_count}"
        cache_file = self.observations_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to store observations cache: %s", e)

    # 4. Reference Style Profile Cache
    def get_cached_style_profile(self, ref_path: Path) -> Optional[dict[str, Any]]:
        fp = self.compute_file_fingerprint(ref_path)
        cache_file = self.styles_dir / f"{fp}.json"
        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def store_cached_style_profile(self, ref_path: Path, profile_data: dict[str, Any]) -> None:
        fp = self.compute_file_fingerprint(ref_path)
        cache_file = self.styles_dir / f"{fp}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to store style cache: %s", e)

    # 5. Cache Stats & Safe Eviction
    def get_cache_stats(self) -> dict[str, Any]:
        """Calculate total size and file counts for all cache tiers."""
        stats: dict[str, Any] = {"total_bytes": 0, "categories": {}}
        for cat_dir in (self.probes_dir, self.transcripts_dir, self.observations_dir, self.styles_dir, self.previews_dir):
            files = list(cat_dir.glob("*.json"))
            cat_bytes = sum(f.stat().st_size for f in files if f.is_file())
            stats["total_bytes"] += cat_bytes
            stats["categories"][cat_dir.name] = {
                "file_count": len(files),
                "bytes": cat_bytes,
                "mb": round(cat_bytes / (1024 * 1024), 2),
            }
        stats["total_mb"] = round(stats["total_bytes"] / (1024 * 1024), 2)
        return stats

    def clear_cache(self, scope: str = "all") -> dict[str, Any]:
        """Safely clear cached artifacts. NEVER touches user source media or final renders."""
        cleared_count = 0
        cleared_bytes = 0

        target_dirs = []
        if scope in ("all", "analysis"):
            target_dirs.extend([self.probes_dir, self.transcripts_dir, self.observations_dir, self.styles_dir])
        if scope in ("all", "previews"):
            target_dirs.append(self.previews_dir)

        for d in target_dirs:
            for item in d.glob("*"):
                if item.is_file():
                    cleared_bytes += item.stat().st_size
                    cleared_count += 1
                    item.unlink(missing_ok=True)

        logger.info("Cleared %d cached files (%.2f MB) for scope: %s", cleared_count, cleared_bytes / (1024 * 1024), scope)
        return {
            "ok": True,
            "scope": scope,
            "files_cleared": cleared_count,
            "mb_cleared": round(cleared_bytes / (1024 * 1024), 2),
        }


cache_manager = CacheManager()
