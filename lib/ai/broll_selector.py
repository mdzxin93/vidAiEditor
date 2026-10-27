"""Intelligent Local B-Roll Selector (Phase 7).

Upgraded media indexing, semantic metadata extraction, candidate relevance ranking,
duration/aspect-ratio matching, duplicate suppression, and licensing provenance.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BRollPlacement:
    asset_path: str
    asset_type: str  # "video", "image"
    start_seconds: float
    end_seconds: float
    matched_keyword: str
    relevance_score: float
    reason: str
    # Phase 7 additions
    width: int = 1920
    height: int = 1080
    aspect_ratio: str = "16:9"
    duration_seconds: float = 0.0
    license: str = "authorized_local_project_asset"
    source_origin: str = "local_repository"

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_path": self.asset_path,
            "asset_type": self.asset_type,
            "start_seconds": round(self.start_seconds, 2),
            "end_seconds": round(self.end_seconds, 2),
            "matched_keyword": self.matched_keyword,
            "relevance_score": round(self.relevance_score, 3),
            "reason": self.reason,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "duration_seconds": round(self.duration_seconds, 2),
            "license": self.license,
            "source_origin": self.source_origin,
        }


@dataclass
class IndexedMediaAsset:
    path: str
    name: str
    stem: str
    is_video: bool
    size_bytes: int
    width: int
    height: int
    aspect_ratio: str
    duration_seconds: float
    tags: list[str]
    description: str
    license: str = "authorized_local_project_asset"


class BRollSelector:
    """Scans, indexes, and semantically ranks local authorized B-roll media."""

    # Semantic concept ontology mapping keywords to related contextual themes
    CONCEPT_ONTOLOGY: dict[str, list[str]] = {
        "focus": ["focus", "brain", "neuro", "protocol", "deep", "work", "mind", "concentration", "habit"],
        "analytics": ["analytics", "chart", "data", "stats", "graph", "metric", "revenue", "throughput", "drop", "growth"],
        "tech": ["code", "tech", "data-flow", "cyber", "screen", "terminal", "software", "demo", "interface", "app"],
        "nature": ["nature", "walk", "outdoor", "world", "landscape", "calm", "morning"],
        "future": ["tomorrow", "signal", "futuristic", "preview", "concept", "vision"],
        "product": ["showcase", "preview", "product", "demo", "feature", "ui"],
    }

    def __init__(
        self,
        media_dirs: list[str | Path] | None = None,
        cache_dir: str | Path = ".cache/broll",
    ):
        if media_dirs is None:
            media_dirs = [Path("media"), Path("assets"), Path("remotion-composer/public")]
        self.media_dirs = [Path(d) for d in media_dirs if Path(d).exists()]
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_cache: list[IndexedMediaAsset] | None = None

    def _extract_media_probe(self, file_path: Path, is_video: bool) -> tuple[int, int, float]:
        """Extract media dimensions and duration using ffprobe with graceful fallback."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-show_entries", "format=duration",
                "-of", "json",
                str(file_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            data = json.loads(res.stdout)
            width = 1920
            height = 1080
            duration = 0.0

            streams = data.get("streams", [])
            if streams:
                width = int(streams[0].get("width", 1920))
                height = int(streams[0].get("height", 1080))
                duration = float(streams[0].get("duration", 0.0) or 0.0)

            if duration <= 0.0:
                duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)

            return width, height, duration
        except Exception:
            return 1920, 1080, 5.0 if is_video else 0.0

    def index_media_library(self, force_refresh: bool = False) -> list[IndexedMediaAsset]:
        """Index local authorized video and image assets with caching."""
        if self._index_cache is not None and not force_refresh:
            return self._index_cache

        cache_file = self.cache_dir / "media_index.json"
        if not force_refresh and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    self._index_cache = [IndexedMediaAsset(**item) for item in raw_data]
                    return self._index_cache
            except Exception as e:
                logger.debug(f"B-roll cache read failure: {e}")

        candidates: list[IndexedMediaAsset] = []
        extensions = {".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"}

        for md in self.media_dirs:
            for root, _, files in os.walk(md):
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in extensions and not f.startswith(".") and not f.startswith(".remotion"):
                        full_p = Path(root) / f
                        is_vid = ext in {".mp4", ".mov", ".webm"}
                        width, height, duration = self._extract_media_probe(full_p, is_vid)
                        
                        aspect = "16:9"
                        if width > 0 and height > 0:
                            ratio = width / height
                            if abs(ratio - 9/16) < 0.1:
                                aspect = "9:16"
                            elif abs(ratio - 1.0) < 0.1:
                                aspect = "1:1"
                            elif abs(ratio - 16/9) < 0.1:
                                aspect = "16:9"

                        # Extract tags from stem and parent directories
                        stem = full_p.stem.lower()
                        rel_parts = full_p.parts
                        tags = [t for t in re.split(r"[_\-\s]+", stem) if len(t) > 2]
                        for p in rel_parts:
                            tags.extend([t for t in re.split(r"[_\-\s]+", p.lower()) if len(t) > 2])
                        tags = list(set(tags))

                        # Build semantic description
                        desc = f"{'Video clip' if is_vid else 'Still graphic'} depicting {', '.join(tags[:4])}"

                        candidates.append(
                            IndexedMediaAsset(
                                path=str(full_p.resolve()),
                                name=f.lower(),
                                stem=stem,
                                is_video=is_vid,
                                size_bytes=full_p.stat().st_size,
                                width=width,
                                height=height,
                                aspect_ratio=aspect,
                                duration_seconds=duration,
                                tags=tags,
                                description=desc,
                            )
                        )

        self._index_cache = candidates
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump([asdict(c) for c in candidates], f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to cache B-roll index: {e}")

        return candidates

    def find_candidates(self) -> list[dict[str, Any]]:
        """Legacy-compatible candidate dictionary list."""
        indexed = self.index_media_library()
        return [
            {
                "path": item.path,
                "name": item.name,
                "stem": item.stem,
                "is_video": item.is_video,
                "size_bytes": item.size_bytes,
                "width": item.width,
                "height": item.height,
                "aspect_ratio": item.aspect_ratio,
                "duration_seconds": item.duration_seconds,
            }
            for item in indexed
        ]

    def compute_relevance_score(
        self,
        asset: IndexedMediaAsset,
        phrase: str,
        target_aspect: str = "9:16",
    ) -> float:
        """Score candidate relevance against spoken phrase and target constraints."""
        phrase_words = set(re.findall(r"\w+", phrase.lower()))
        if not phrase_words:
            return 0.0

        # Don't match the raw camera source as B-roll over itself
        if "sample_raw" in asset.stem or "talking_head" in asset.stem:
            return 0.0

        score = 0.0

        # 1. Direct tag & stem token match
        direct_matches = set(asset.tags).intersection(phrase_words)
        if direct_matches:
            score += len(direct_matches) * 0.35

        # 2. Ontology concept expansion
        for concept, kw_list in self.CONCEPT_ONTOLOGY.items():
            phrase_has_concept = any(k in phrase_words for k in kw_list)
            asset_has_concept = any(k in asset.tags for k in kw_list) or any(k in asset.stem for k in kw_list)
            if phrase_has_concept and asset_has_concept:
                score += 0.45
                break

        # 3. Format preference (videos preferred for dynamic B-roll)
        if asset.is_video:
            score += 0.10

        # 4. Aspect ratio bonus (if matches target format)
        if asset.aspect_ratio == target_aspect:
            score += 0.08

        return min(1.0, score)

    def match_broll_for_transcript(
        self,
        transcript: list[dict[str, Any]],
        video_duration: float,
        target_max_placements: int = 1,
        target_aspect: str = "9:16",
        min_relevance_threshold: float = 0.60,
    ) -> list[BRollPlacement]:
        """Identify moments needing visual support and assign matched local assets."""
        candidates = self.index_media_library()
        if not candidates or video_duration < 4.0:
            return []

        placements: list[BRollPlacement] = []
        used_paths: set[str] = set()

        # Build sentence-level context windows from transcript
        window_size = 5
        for i in range(0, len(transcript), 3):
            if len(placements) >= target_max_placements:
                break

            window = transcript[i : i + window_size]
            if not window:
                continue

            phrase = " ".join([w.get("word", "") for w in window])
            w_start = float(window[0].get("start", 0.0))
            w_end = float(window[-1].get("end", w_start + 2.5))

            # Protect intro (< 2.0s) and outro (> duration - 3.0s)
            if w_start < 2.0 or w_start > video_duration - 3.5:
                continue

            # Rank candidate assets
            scored_candidates: list[tuple[float, IndexedMediaAsset, str]] = []
            for asset in candidates:
                if asset.path in used_paths:
                    continue
                score = self.compute_relevance_score(asset, phrase, target_aspect)
                if score >= min_relevance_threshold:
                    scored_candidates.append((score, asset, phrase))

            scored_candidates.sort(key=lambda x: x[0], reverse=True)

            if scored_candidates:
                best_score, best_asset, matched_phrase = scored_candidates[0]
                placement_duration = 3.0
                if best_asset.is_video and best_asset.duration_seconds > 0.0:
                    placement_duration = min(4.0, max(2.0, best_asset.duration_seconds))

                end_sec = min(video_duration, w_start + placement_duration)

                placements.append(
                    BRollPlacement(
                        asset_path=best_asset.path,
                        asset_type="video" if best_asset.is_video else "image",
                        start_seconds=round(w_start, 2),
                        end_seconds=round(end_sec, 2),
                        matched_keyword=best_asset.stem,
                        relevance_score=round(best_score, 3),
                        reason=f"Context-aware B-roll matched for spoken topic '{matched_phrase[:35]}...'",
                        width=best_asset.width,
                        height=best_asset.height,
                        aspect_ratio=best_asset.aspect_ratio,
                        duration_seconds=round(placement_duration, 2),
                    )
                )
                used_paths.add(best_asset.path)

        return placements
