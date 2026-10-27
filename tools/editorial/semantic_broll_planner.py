"""OpenMontage v3 Semantic B-Roll & Visual Decision Planner Tool.

Connects the OpenMontage v3 stock catalog to the editorial pipeline.
Ranks licensed vector illustrations, B-roll clips, and motion graphics
using script meaning, keyword alignment, and reference editorial rules.
Produces validated openmontage.edl.v3 timelines with frame-accurate timing.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_ROOT = REPO_ROOT / "assets" / "editing-stock"

STOP_WORDS = set(
    "a an and are as at be been but by can do for from had has have he her his i in is it its my not of on or our she so that the their them there these they this to was we were what when where who will with you your".split()
)

SYNONYMS: dict[str, list[str]] = {
    "time": ["clock", "hours", "calendar", "productivity", "schedule", "deadline", "day"],
    "money": ["revenue", "profit", "earnings", "income", "cash", "sales", "finance", "price"],
    "business": ["company", "entrepreneur", "customers", "sales", "startup", "clients"],
    "growth": ["increase", "progress", "scaling", "growth", "rise", "improvement", "scale"],
    "problem": ["struggle", "challenge", "failure", "difficulty", "issue", "pain"],
    "technology": ["ai", "automation", "software", "digital", "cloud", "robot", "machine", "tech", "chip"],
    "social": ["social", "media", "instagram", "content", "creator", "marketing"],
    "work": ["job", "working", "labor", "effort", "hustle", "hours", "office", "code"],
    "result": ["results", "outcome", "success", "impact", "performance", "metrics"],
    "team": ["team", "people", "collaboration", "meeting", "staff", "connect"],
    "communication": ["call", "phone", "chat", "message", "email", "talk"],
    "comparison": ["compare", "versus", "difference", "before", "after", "alternative"],
    "security": ["privacy", "secure", "password", "protection", "lock"],
}

REVERSE_SYNONYMS = {w: k for k, words in SYNONYMS.items() for w in words}


def _tokenize(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 1 and w not in STOP_WORDS]


def _enrich_tokens(words: list[str]) -> list[str]:
    out = list(words)
    for w in words:
        c = REVERSE_SYNONYMS.get(w)
        if c:
            out.append(c)
        if w in SYNONYMS:
            out.extend(SYNONYMS[w][:4])
    return out


def _index_asset(asset: dict[str, Any]) -> list[str]:
    combined = " ".join([
        asset.get("id", "").replace("_", " "),
        " ".join(asset.get("tags", [])),
        " ".join(asset.get("script_signals", [])),
        asset.get("kind", ""),
    ])
    return _enrich_tokens(_tokenize(combined))


class BM25CatalogRanker:
    """Offline BM25 ranker over catalog assets with optional CPU semantic embeddings."""

    def __init__(self, catalog_path: Optional[Path] = None, use_semantic: bool = False):
        self.catalog_path = catalog_path or (CATALOG_ROOT / "catalog" / "assets.json")
        self.assets: list[dict[str, Any]] = []
        if self.catalog_path.is_file():
            try:
                raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
                self.assets = raw.get("assets", [])
            except Exception as e:
                logger.warning(f"Failed to load catalog from {self.catalog_path}: {e}")

        self.docs = [_index_asset(a) for a in self.assets]
        self.doc_freq = Counter(w for d in self.docs for w in set(d))
        self.avg_doc_len = sum(map(len, self.docs)) / max(1, len(self.docs))
        self.semantic_embedder = None

        if use_semantic:
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
                descriptions = [
                    " ".join([a.get("id", "").replace("_", " "), " ".join(a.get("tags", []))])
                    for a in self.assets
                ]
                emb = model.encode(descriptions, normalize_embeddings=True, show_progress_bar=False)
                self.semantic_embedder = (model, emb)
            except Exception as e:
                logger.debug(f"Optional sentence-transformers unavailable ({e}); using offline BM25")

    def _score_bm25(self, query: list[str], doc: list[str]) -> float:
        freq = Counter(doc)
        n = len(self.docs)
        score = 0.0
        for w in set(query):
            if w not in freq:
                continue
            df = self.doc_freq[w]
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            f = freq[w]
            score += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(doc) / max(1, self.avg_doc_len)))
        return score

    def rank(self, text: str) -> list[float]:
        q = _enrich_tokens(_tokenize(text))
        lex = [self._score_bm25(q, d) for d in self.docs]
        mx = max(lex, default=0.0) or 1.0
        lex = [v / mx for v in lex]

        if self.semantic_embedder:
            try:
                model, emb = self.semantic_embedder
                vec = model.encode([text], normalize_embeddings=True)[0]
                sem = [max(0.0, float(x)) for x in emb @ vec]
                return [round(0.6 * l + 0.4 * s, 4) for l, s in zip(lex, sem)]
            except Exception:
                pass

        return [round(x, 4) for x in lex]


class SemanticBRollPlanner(BaseTool):
    """OpenMontage v3 Script-Guided B-Roll and Overlay Decision Tool."""

    name = "semantic_broll_planner"
    version = "3.0.0"
    tier = ToolTier.CORE
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    capability = "broll_planning"
    provider = "openmontage_v3"
    capabilities = ["broll_planning", "editorial_intelligence", "edl_generation"]

    best_for = [
        "script-guided B-roll selection",
        "OpenMontage EDL v3 timeline generation",
        "licensed catalog asset matching",
        "cinematic explainer motion graphics planning",
    ]

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=256,
        vram_mb=0,
    )
    retry_policy = RetryPolicy(max_retries=1)

    def __init__(self, catalog_root: Optional[Path] = None):
        super().__init__()
        self.catalog_root = Path(catalog_root) if catalog_root else CATALOG_ROOT
        self.ranker = BM25CatalogRanker(self.catalog_root / "catalog" / "assets.json")

    def _transcript_to_segments(self, source: Any) -> list[dict[str, Any]]:
        """Normalize transcript input (str, dict, or list) into timed segments."""
        if isinstance(source, str):
            # If string is a JSON file path
            p = Path(source)
            if p.is_file() and p.suffix.lower() == ".json":
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    return self._transcript_to_segments(data)
                except Exception:
                    pass

            # Plain-text script with estimated timing
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", source) if s.strip()]
            t = 0.0
            out = []
            for s in sentences:
                dur = max(1.0, len(re.findall(r"\b[\w']+\b", s)) / 2.4)
                out.append({"start": round(t, 3), "end": round(t + dur, 3), "text": s, "estimated": True})
                t += dur
            return out

        if isinstance(source, dict):
            if "segments" in source:
                # If segments contain word-level timing, segment into natural clauses
                clause_out = []
                for seg in source["segments"]:
                    words = seg.get("words", [])
                    if words and len(words) > 3:
                        c_words = []
                        for i, w in enumerate(words):
                            c_words.append(w)
                            w_text = w.get("word", "")
                            has_pause = False
                            if i < len(words) - 1:
                                has_pause = (words[i+1].get("start", 0) - w.get("end", 0)) > 0.25
                            if (w_text.rstrip().endswith((",", ".", "!", "?")) or has_pause) and len(c_words) >= 2:
                                s_start = float(c_words[0]["start"])
                                s_end = float(c_words[-1]["end"])
                                s_text = " ".join(x.get("word", "").strip() for x in c_words).strip()
                                clause_out.append({"start": s_start, "end": s_end, "text": s_text, "estimated": False})
                                c_words = []
                        if c_words:
                            s_start = float(c_words[0]["start"])
                            s_end = float(c_words[-1]["end"])
                            s_text = " ".join(x.get("word", "").strip() for x in c_words).strip()
                            clause_out.append({"start": s_start, "end": s_end, "text": s_text, "estimated": False})
                    else:
                        clause_out.append({"start": float(seg["start"]), "end": float(seg["end"]), "text": seg.get("text", "").strip(), "estimated": False})
                if clause_out:
                    clause_out.sort(key=lambda v: v["start"])
                    return clause_out
                source = source["segments"]
            elif "words" in source:
                source = source["words"]
            else:
                raise ValueError("Expected 'segments' or 'words' in transcript dict")

        if not isinstance(source, list):
            raise ValueError("Expected list of timed segments")

        out = []
        for item in source:
            if "start" not in item or "end" not in item:
                continue
            start, end = float(item["start"]), float(item["end"])
            if start < 0 or end <= start:
                continue
            text = (item.get("text") or item.get("word") or "").strip()
            out.append({"start": start, "end": end, "text": text, "estimated": False})

        out.sort(key=lambda v: v["start"])
        return out

    def _merge_short_segments(self, segs: list[dict[str, Any]], minimum: float = 1.1) -> list[dict[str, Any]]:
        if not segs:
            return []
        result = []
        curr = dict(segs[0])
        for s in segs[1:]:
            is_intro = bool(re.search(r"\b(i'm|my name is|i am)\b", curr["text"].lower()))
            if not is_intro and (curr["end"] - curr["start"] < minimum and s["start"] - curr["end"] < 0.5 and s["end"] - curr["start"] < 4.5):
                curr["end"] = s["end"]
                curr["text"] = (curr["text"] + " " + s["text"]).strip()
            else:
                result.append(curr)
                curr = dict(s)
        result.append(curr)
        return result

    def _choose_asset(
        self,
        seg: dict[str, Any],
        used: list[str],
        last_end: dict[str, float],
        threshold: float = 0.19,
    ) -> Optional[tuple[float, dict[str, Any], list[tuple[float, float, dict[str, Any]]]]]:
        candidates = self.ranker.rank(seg["text"])
        ranked = []
        for i, asset in enumerate(self.ranker.assets):
            kind = asset.get("kind", "")
            path = asset.get("path", "")
            if kind not in ("illustration", "video", "motion", "overlay") and not path.endswith((".mp4", ".svg", ".png")):
                continue
            raw = candidates[i]
            if raw < threshold:
                continue
            penalty = 0.65 if asset.get("id") in used[-3:] else 0.0
            if last_end.get(asset.get("id", ""), -100) + 12 > seg["start"]:
                penalty += 0.65
            if kind != "illustration":
                penalty += 0.06
            ranked.append((raw - penalty, raw, asset))

        ranked.sort(key=lambda r: r[0], reverse=True)
        if not ranked or ranked[0][0] < threshold:
            return None
        return ranked[0][1], ranked[0][2], ranked[:3]

    def plan(
        self,
        source: Any,
        max_broll_duration: float = 2.7,
        threshold: float = 0.19,
    ) -> dict[str, Any]:
        """Generate openmontage.edl.v3 compliant editing decision list."""
        raw_segments = self._transcript_to_segments(source)
        segments = self._merge_short_segments(raw_segments)

        events: list[dict[str, Any]] = []
        broll_overlays: list[dict[str, Any]] = []
        used: list[str] = []
        last_end: dict[str, float] = {}
        count = 0

        for seg in segments:
            start, end = seg["start"], seg["end"]
            duration = end - start
            choice = self._choose_asset(seg, used, last_end, threshold)

            if choice and duration >= 1.25:
                score, asset, alts = choice
                bdur = min(max_broll_duration, duration * 0.65)
                bstart = start + (duration - bdur) * 0.50
                bend = bstart + bdur

                if bstart - start >= 0.12:
                    events.append({
                        "type": "a_roll",
                        "start_s": round(start, 3),
                        "end_s": round(bstart, 3),
                        "script_text": seg["text"],
                    })

                overlay_event = {
                    "type": "b_roll_overlay",
                    "start_s": round(bstart, 3),
                    "end_s": round(bend, 3),
                    "asset_id": asset.get("id"),
                    "asset_path": asset.get("path"),
                    "asset_kind": asset.get("kind"),
                    "confidence": round(score, 3),
                    "script_text": seg["text"],
                    "transition": "hard_cut",
                    "motion": "subtle_scale_pop" if asset.get("kind") == "illustration" else "original_asset_motion",
                    "sfx": "soft_swoosh",
                    "alternatives": [{"id": a.get("id"), "score": round(s, 3)} for _, s, a in alts[:3]],
                    "requires_review": score < 0.44,
                }
                events.append(overlay_event)
                broll_overlays.append({
                    "id": f"overlay_{count+1}",
                    "asset_path": asset.get("path"),
                    "asset_id": asset.get("id"),
                    "asset_kind": asset.get("kind"),
                    "start_seconds": round(bstart, 3),
                    "end_seconds": round(bend, 3),
                    "motion": overlay_event["motion"],
                    "sfx": overlay_event["sfx"],
                    "transition": overlay_event["transition"],
                    "confidence": overlay_event["confidence"],
                    "script_text": seg["text"],
                })

                if end - bend >= 0.12:
                    events.append({
                        "type": "a_roll",
                        "start_s": round(bend, 3),
                        "end_s": round(end, 3),
                        "script_text": seg["text"],
                    })

                last_end[asset.get("id", "")] = bend
                used.append(asset.get("id", ""))
                count += 1
            else:
                events.append({
                    "type": "a_roll",
                    "start_s": round(start, 3),
                    "end_s": round(end, 3),
                    "script_text": seg["text"],
                })

        duration_s = round(max((s["end"] for s in segments), default=0.0), 3)

        edl = {
            "schema": "openmontage.edl.v3",
            "style_preset": "presets/cinematic_explainer.json",
            "time_unit": "seconds",
            "source_timing": "estimated_script" if any(s.get("estimated") for s in segments) else "asr_timed",
            "status": "draft_review_before_render",
            "duration_s": duration_s,
            "asset_root": "assets/editing-stock",
            "settings": {
                "max_broll_duration_s": max_broll_duration,
                "hard_cuts_default": True,
                "repeat_cooldown_s": 12,
                "audio": "preserve_original_dialogue",
                "external_stock_licensed_only": True,
            },
            "stats": {
                "segments": len(segments),
                "broll_events": count,
                "reviews_needed": sum(e.get("requires_review", False) for e in events),
            },
            "events": events,
            "overlays": broll_overlays,
        }
        return edl

    def validate_edl(self, edl: dict[str, Any]) -> list[str]:
        """Verify that timings are sorted, bounded, and all assets exist."""
        errors = []
        items = edl.get("events", [])
        dur = edl.get("duration_s", 0.0)

        for j, e in enumerate(items):
            if not (0 <= e["start_s"] < e["end_s"] <= dur + 0.005):
                errors.append(f"Bad timing in event {j}: [{e.get('start_s')} - {e.get('end_s')}]")
            if e["type"] == "b_roll_overlay":
                rel = e.get("asset_path", "")
                full = self.catalog_root / rel
                if not full.is_file():
                    errors.append(f"Missing referenced catalog asset: {rel}")

        for x, y in zip(items, items[1:]):
            if y["start_s"] < x["start_s"]:
                errors.append(f"Unsorted events: {x['start_s']} > {y['start_s']}")

        return errors

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        source = inputs.get("transcript") or inputs.get("script") or inputs.get("script_text")
        video_path = inputs.get("video_path")

        if not source and video_path:
            # Look for cached transcript
            vp = Path(video_path)
            tcand = vp.parent / f"{vp.stem}_transcript.json"
            if tcand.is_file():
                source = json.loads(tcand.read_text(encoding="utf-8"))
            else:
                from tools.analysis.transcriber import Transcriber
                t = Transcriber()
                res = t.execute({"input_path": str(vp), "model_size": "base"})
                if res.success:
                    source = res.data
                else:
                    return ToolResult(success=False, error=f"Could not transcribe video: {res.error}")

        if not source:
            return ToolResult(success=False, error="Requires 'transcript', 'script', or 'video_path'")

        max_broll_dur = float(inputs.get("max_broll_duration", 2.7))
        threshold = float(inputs.get("threshold", 0.19))

        try:
            edl = self.plan(source, max_broll_duration=max_broll_dur, threshold=threshold)
            errors = self.validate_edl(edl)
            if errors:
                return ToolResult(success=False, error="; ".join(errors))

            output_path = inputs.get("output_path")
            artifacts = []
            if output_path:
                op = Path(output_path)
                op.parent.mkdir(parents=True, exist_ok=True)
                op.write_text(json.dumps(edl, indent=2), encoding="utf-8")
                artifacts.append(str(op))

            return ToolResult(
                success=True,
                data={
                    "edl": edl,
                    "stats": edl["stats"],
                    "duration_s": edl["duration_s"],
                    "timing": edl["source_timing"],
                    "events": edl["events"],
                    "overlays": edl["overlays"],
                },
                artifacts=artifacts,
            )
        except Exception as e:
            logger.exception("Semantic B-roll planning failed")
            return ToolResult(success=False, error=str(e))
