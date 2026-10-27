"""Supervised Training Dataset & Style Adaptation System for OpenMontage (Phase 12).

Separates:
1. Speech transcription (Faster-Whisper)
2. Script understanding (entity & emphasis extraction)
3. Editing decision prediction (A-roll/B-roll classification & cut placement)
4. Asset recommendation (catalog ranking)
5. Visual style generation (color, typography, motion curves)
6. Rendering (Remotion / FFmpeg)

Builds and validates machine-readable supervised datasets from approved and corrected edits.
Provides held-out split validation and metrics (asset recall, boundary precision, dialogue continuity).
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = REPO_ROOT / "config" / "supervised_editing_dataset.jsonl"


@dataclass
class SupervisedExample:
    """A standardized, machine-readable training/evaluation record for AI editing decisions."""

    example_id: str
    video_source: str
    duration_seconds: float
    reference_frame_info: dict[str, Any]
    transcript_segments: list[dict[str, Any]]
    shot_classifications: list[dict[str, Any]]  # "a_roll" vs "b_roll_overlay"
    selected_assets: list[dict[str, Any]]       # id, kind, path, confidence, rank
    timing_boundaries: list[dict[str, float]]   # start_s, end_s
    motion_effects: list[dict[str, Any]]        # punch_zoom scales, scale_pops, transitions
    caption_layout: dict[str, Any]              # placement, font, colors, vertical_position
    approved_editing_decisions: dict[str, Any]  # final validated EDL/cuts/overlays
    user_review_status: str                     # "approved", "rejected", "corrected"
    provenance: str = "human_supervised_review"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SupervisedExample:
        return cls(**data)


class SupervisedDatasetManager:
    """Manages appending, validating, and splitting supervised editing examples."""

    def __init__(self, dataset_path: Optional[Path] = None):
        self.dataset_path = Path(dataset_path) if dataset_path else DATASET_PATH
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)

    def append_example(self, example: SupervisedExample) -> bool:
        """Append an approved or corrected editing session to the supervised dataset."""
        try:
            line = json.dumps(example.to_dict(), ensure_ascii=False)
            with open(self.dataset_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            logger.info(f"Recorded supervised editing example: {example.example_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to record supervised example: {e}")
            return False

    def load_all_examples(self) -> list[SupervisedExample]:
        """Load all valid supervised examples from JSONL."""
        if not self.dataset_path.is_file():
            return []
        examples = []
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    examples.append(SupervisedExample.from_dict(data))
                except Exception as e:
                    logger.warning(f"Skipping malformed dataset entry: {e}")
        return examples

    def export_train_val_split(
        self,
        val_ratio: float = 0.2,
        seed: int = 42,
    ) -> tuple[list[SupervisedExample], list[SupervisedExample]]:
        """Split examples by video source to prevent data leakage across cutframes."""
        all_examples = self.load_all_examples()
        if not all_examples:
            return [], []

        # Group by video_source
        by_source: dict[str, list[SupervisedExample]] = {}
        for ex in all_examples:
            by_source.setdefault(ex.video_source, []).append(ex)

        sources = list(by_source.keys())
        rng = random.Random(seed)
        rng.shuffle(sources)

        val_count = max(1, round(len(sources) * val_ratio)) if len(sources) > 1 else 0
        val_sources = set(sources[:val_count])

        train_examples = []
        val_examples = []
        for s, ex_list in by_source.items():
            if s in val_sources:
                val_examples.extend(ex_list)
            else:
                train_examples.extend(ex_list)

        return train_examples, val_examples

    def evaluate_predictions(
        self,
        predicted_edl: dict[str, Any],
        ground_truth_edl: dict[str, Any],
        tolerance_sec: float = 0.35,
    ) -> dict[str, float]:
        """Measure boundary precision, recall, and asset matching against ground truth."""
        pred_events = [e for e in predicted_edl.get("events", []) if e.get("type") == "b_roll_overlay"]
        gt_events = [e for e in ground_truth_edl.get("events", []) if e.get("type") == "b_roll_overlay"]

        if not gt_events and not pred_events:
            return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "asset_accuracy": 1.0}
        if not gt_events:
            return {"precision": 0.0, "recall": 1.0, "f1": 0.0, "asset_accuracy": 0.0}
        if not pred_events:
            return {"precision": 1.0, "recall": 0.0, "f1": 0.0, "asset_accuracy": 0.0}

        true_positives = 0
        correct_assets = 0

        for gt in gt_events:
            gt_start = gt.get("start_s", 0.0)
            gt_end = gt.get("end_s", 0.0)
            gt_asset = gt.get("asset_id", "")

            # Match with closest prediction within tolerance
            best_match = None
            best_diff = 999.0
            for pr in pred_events:
                p_start = pr.get("start_s", 0.0)
                diff = abs(p_start - gt_start)
                if diff < best_diff and diff <= tolerance_sec:
                    best_diff = diff
                    best_match = pr

            if best_match:
                true_positives += 1
                if best_match.get("asset_id") == gt_asset:
                    correct_assets += 1

        precision = true_positives / len(pred_events) if pred_events else 0.0
        recall = true_positives / len(gt_events) if gt_events else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        asset_acc = correct_assets / true_positives if true_positives > 0 else 0.0

        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "asset_accuracy": round(asset_acc, 3),
        }
