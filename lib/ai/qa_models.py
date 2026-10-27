"""Structured Data Models and Versioned Issue Schema for QA Inspection (Phase 8).

Defines:
- QAIssue: structured defect descriptor with timestamps, severity, detection source, and suggested fix
- QAReport: comprehensive post-render quality report with before/after tracking
- FixRecord: audit provenance record for every applied automatic revision
- Quality score calculation rules based on measured defect penalties
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class QASeverity(str, Enum):
    CRITICAL = "critical"  # Corrupt render, black screen, extreme audio blowout, total occlusion
    HIGH = "high"          # Subtitle collision, face occlusion, severe clipping
    MEDIUM = "medium"      # Safe area margin overrun, temporal rest violation, audio peak > 0dB
    LOW = "low"            # Minor contrast, non-standard aspect, slight padding
    INFO = "info"          # Observational telemetry / baseline properties


class QACategory(str, Enum):
    BLACK_FRAMES = "black_frames"
    FROZEN_FRAMES = "frozen_frames"
    VISUAL_DISCONTINUITY = "visual_discontinuity"
    SUBJECT_CROPPING = "subject_cropping"
    TEXT_CLIPPING = "text_clipping"
    CAPTION_SAFE_ZONE_VIOLATION = "caption_safe_zone_violation"
    PRESENTER_OCCLUSION = "presenter_occlusion"
    OVERLAY_COLLISION = "overlay_collision"
    CONTRAST_UNREADABLE = "contrast_unreadable"
    EXCESSIVE_VISUAL_CLUTTER = "excessive_visual_clutter"
    UNNECESSARY_TRANSITION = "unnecessary_transition"
    TRUNCATED_GRAPHIC = "truncated_graphic"
    CAPTION_SYNC_OFFSET = "caption_sync_offset"
    AUDIO_CLIPPING = "audio_clipping"
    AUDIO_SILENCE = "audio_silence"
    AUDIO_VOLUME_IMBALANCE = "audio_volume_imbalance"
    AUDIO_DURATION_MISMATCH = "audio_duration_mismatch"
    BROLL_INTEGRATION_FAILURE = "broll_integration_failure"


class QAFixType(str, Enum):
    MOVE_OVERLAY = "move_overlay"
    SCALE_OVERLAY = "scale_overlay"
    ADJUST_CAPTION_POSITION = "adjust_caption_position"
    SHORTEN_INTERVAL = "shorten_interval"
    RETARGET_CROP = "retarget_crop"
    NORMALIZE_AUDIO = "normalize_audio"
    SUPPRESS_REDUNDANT_GRAPHIC = "suppress_redundant_graphic"
    RETIME_SUBTITLE = "retime_subtitle"
    NONE = "none"


@dataclass
class QAIssue:
    """Structured defect record identified during video/audio inspection."""

    issue_id: str
    category: str
    start_seconds: float
    end_seconds: float
    severity: str
    confidence: float
    detection_source: str
    description: str
    suggested_fix: str
    auto_fix_allowed: bool = True
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "category": self.category,
            "start_seconds": round(float(self.start_seconds), 3),
            "end_seconds": round(float(self.end_seconds), 3),
            "severity": self.severity,
            "confidence": round(float(self.confidence), 3),
            "detection_source": self.detection_source,
            "description": self.description,
            "suggested_fix": self.suggested_fix,
            "auto_fix_allowed": self.auto_fix_allowed,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAIssue:
        return cls(
            issue_id=data["issue_id"],
            category=data["category"],
            start_seconds=float(data["start_seconds"]),
            end_seconds=float(data["end_seconds"]),
            severity=data["severity"],
            confidence=float(data.get("confidence", 0.85)),
            detection_source=data.get("detection_source", "heuristic_inspector"),
            description=data.get("description", ""),
            suggested_fix=data.get("suggested_fix", "none"),
            auto_fix_allowed=data.get("auto_fix_allowed", True),
            evidence=data.get("evidence", {}),
        )


@dataclass
class FixRecord:
    """Audit record of a concrete correction applied to edit decisions."""

    fix_id: str
    issue_id: str
    action: str
    target_element: str
    original_value: Any
    corrected_value: Any
    rationale: str
    applied_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QAReport:
    """Comprehensive inspection report for an exported video file."""

    report_id: str
    version: str = "1.0"
    video_path: str = ""
    duration_seconds: float = 0.0
    resolution: str = "1080x1920"
    frames_inspected: int = 0
    audio_checks_performed: list[str] = field(default_factory=list)
    captions_validated: int = 0
    issues: list[QAIssue] = field(default_factory=list)
    fixes_applied: list[FixRecord] = field(default_factory=list)
    revision_count: int = 0
    quality_score: float = 100.0
    quality_score_formula: str = "100 - (critical*30 + high*15 + medium*5 + low*2)"
    passed: bool = True
    timing_sec: dict[str, float] = field(default_factory=dict)
    model_usage: dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def compute_quality_score(self) -> float:
        """Calculate quality score out of 100 based on remaining active issues."""
        weights = {
            QASeverity.CRITICAL.value: 30.0,
            QASeverity.HIGH.value: 15.0,
            QASeverity.MEDIUM.value: 5.0,
            QASeverity.LOW.value: 2.0,
            QASeverity.INFO.value: 0.0,
        }
        total_deduction = sum(weights.get(i.severity, 2.0) for i in self.issues)
        score = max(0.0, round(100.0 - total_deduction, 1))
        self.quality_score = score
        # Dual-gate evaluation: Video passes QA only if score >= 80 AND zero critical or high blocker issues
        crit_count = sum(1 for i in self.issues if i.severity == QASeverity.CRITICAL.value)
        high_count = sum(1 for i in self.issues if i.severity == QASeverity.HIGH.value)
        blocker_count = crit_count + high_count
        has_blocker = blocker_count > 0
        self.passed = (score >= 80.0) and not has_blocker

        if self.passed:
            self.summary = f"Passed QA with quality score {score}/100. Meets score threshold (≥80) with zero critical/high blockers."
        elif has_blocker and score >= 80.0:
            self.summary = (
                f"Failed QA: Quality score {score}/100 meets score threshold (≥80), "
                f"but failed due to {blocker_count} blocking defect(s) ({crit_count} critical, {high_count} high). "
                f"Zero critical or high severity defects permitted."
            )
        elif not has_blocker and score < 80.0:
            self.summary = f"Failed QA: Quality score {score}/100 is below the passing threshold of 80.0."
        else:
            self.summary = (
                f"Failed QA: Quality score {score}/100 is below 80.0 threshold and has "
                f"{blocker_count} blocking defect(s) ({crit_count} critical, {high_count} high)."
            )
        return score

    @property
    def severity_counts(self) -> dict[str, int]:
        counts = {s.value: 0 for s in QASeverity}
        for i in self.issues:
            counts[i.severity] = counts.get(i.severity, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        crit_count = sum(1 for i in self.issues if i.severity == QASeverity.CRITICAL.value)
        high_count = sum(1 for i in self.issues if i.severity == QASeverity.HIGH.value)
        blocker_count = crit_count + high_count
        return {
            "report_id": self.report_id,
            "version": self.version,
            "video_path": self.video_path,
            "duration_seconds": round(self.duration_seconds, 3),
            "resolution": self.resolution,
            "frames_inspected": self.frames_inspected,
            "audio_checks_performed": self.audio_checks_performed,
            "captions_validated": self.captions_validated,
            "quality_score": self.quality_score,
            "quality_score_formula": self.quality_score_formula,
            "passing_threshold": 80.0,
            "has_blockers": blocker_count > 0,
            "blocking_issues_count": blocker_count,
            "passed": self.passed,
            "revision_count": self.revision_count,
            "severity_counts": self.severity_counts,
            "issues": [i.to_dict() for i in self.issues],
            "fixes_applied": [f.to_dict() for f in self.fixes_applied],
            "timing_sec": self.timing_sec,
            "model_usage": self.model_usage,
            "summary": self.summary,
        }

    def save(self, output_path: Path | str) -> None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_markdown_summary(self) -> str:
        status_badge = "✅ PASSED" if self.passed else "⚠️ ACTION REQUIRED"
        crit_count = self.severity_counts.get("critical", 0)
        high_count = self.severity_counts.get("high", 0)
        lines = [
            f"# QA Quality Inspection Report: `{Path(self.video_path).name}`",
            f"**Status:** {status_badge} | **Quality Score:** {self.quality_score}/100 | **Revisions:** {self.revision_count}",
            f"**Evaluation:** Dual-Gate (Required: Score ≥ 80.0 AND zero critical/high blockers)",
            f"**Verdict Reason:** {self.summary}",
            f"**Stream:** {self.resolution} ({self.duration_seconds:.2f}s) | **Frames Inspected:** {self.frames_inspected}",
            "",
            "### Defect Severity Breakdown",
            f"- **Critical (Blocker):** {crit_count}",
            f"- **High (Blocker):** {high_count}",
            f"- **Medium:** {self.severity_counts.get('medium', 0)}",
            f"- **Low:** {self.severity_counts.get('low', 0)}",
            "",
        ]

        if self.issues:
            lines.append("### Detected Issues")
            for idx, iss in enumerate(self.issues, 1):
                fix_tag = f" [Auto-Fix: {iss.suggested_fix}]" if iss.auto_fix_allowed else " [Manual Review]"
                lines.append(
                    f"{idx}. **[{iss.severity.upper()}]** `{iss.category}` ({iss.start_seconds:.2f}s - {iss.end_seconds:.2f}s): "
                    f"{iss.description} (Source: `{iss.detection_source}`, Conf: {iss.confidence:.2f}){fix_tag}"
                )
            lines.append("")

        if self.fixes_applied:
            lines.append("### Automatic Corrections Applied")
            for idx, fix in enumerate(self.fixes_applied, 1):
                lines.append(
                    f"{idx}. **{fix.action}** on `{fix.target_element}`: {fix.rationale} "
                    f"(Original: `{fix.original_value}` -> Corrected: `{fix.corrected_value}`)"
                )
            lines.append("")

        return "\n".join(lines)
