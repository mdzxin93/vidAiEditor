"""Script-Driven Editing Engine (Phase E).

Supports:
- Mode 1: Automatic Editing (high-level directive, e.g. "fast-paced Instagram Reel")
- Mode 2: Detailed Script Editing (precise phrase-triggered directives, e.g.:
  "When I mention '90 minutes', introduce a focus stat card.
   Highlight the phrase 'conversion rate' in yellow.
   Zoom in when I explain the main problem.")

Matches spoken phrases against word-aligned transcripts, calculates exact timestamps,
maps them to Remotion presets, and prioritizes explicit script instructions.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScriptDirective:
    """An explicit user script instruction matched to footage."""
    action: str  # "zoom", "highlight", "overlay", "cut", "transition"
    trigger_phrase: str
    matched_start: float = 0.0
    matched_end: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)
    matched: bool = False
    reason: str = ""


class ScriptDrivenEditor:
    """Interprets user editing instructions and aligns them with speech transcripts."""

    def __init__(self):
        pass

    def parse_and_align_script(
        self,
        instruction_text: str,
        transcript: list[dict[str, Any]],
        video_duration: float,
    ) -> tuple[list[ScriptDirective], list[str]]:
        """Parse natural language instructions and locate target phrases in transcript."""
        directives: list[ScriptDirective] = []
        unsupported: list[str] = []

        if not instruction_text or not instruction_text.strip():
            return directives, unsupported

        # Pre-clean transcript text for phrase matching
        words = [w.get("word", "").strip().lower() for w in transcript]
        raw_text = " ".join(words)

        # Pattern 1: Phrase Highlight -> "highlight [phrase] in [color]" or "highlight [phrase]"
        hl_matches = re.finditer(
            r"(?:highlight|emphasize)\s+(?:the\s+phrase\s+|words?\s+)?['\"]?([^'\",\.]+?)['\"]?\s+(?:in\s+([a-zA-Z#0-9]+))?",
            instruction_text,
            re.IGNORECASE,
        )
        for m in hl_matches:
            target_phrase = m.group(1).strip()
            color = m.group(2) or "#FACC15"
            start_t, end_t = self._find_phrase_timing(target_phrase, transcript)
            if start_t is not None:
                directives.append(
                    ScriptDirective(
                        action="highlight",
                        trigger_phrase=target_phrase,
                        matched_start=start_t,
                        matched_end=end_t,
                        parameters={"color": color, "words": target_phrase.split()},
                        matched=True,
                        reason=f"Explicit highlight instruction for '{target_phrase}'",
                    )
                )
            else:
                unsupported.append(f"Phrase '{target_phrase}' not found in spoken dialogue.")

        # Pattern 2: Zoom on Phrase -> "zoom in when [phrase]" or "zoom on [phrase]"
        zoom_matches = re.finditer(
            r"zoom(?:\s+in)?\s+(?:when(?:\s+I(?:\s+mention|\s+explain|\s+say)?)?|on|at)\s+['\"]?([^'\",\.]+?)['\"]?(?:\.|\,|$)",
            instruction_text,
            re.IGNORECASE,
        )
        for m in zoom_matches:
            target_phrase = m.group(1).strip()
            start_t, end_t = self._find_phrase_timing(target_phrase, transcript)
            if start_t is not None:
                directives.append(
                    ScriptDirective(
                        action="zoom",
                        trigger_phrase=target_phrase,
                        matched_start=start_t,
                        matched_end=max(end_t, start_t + 2.5),
                        parameters={"scale": 1.15},
                        matched=True,
                        reason=f"Explicit zoom instruction triggered by '{target_phrase}'",
                    )
                )
            else:
                unsupported.append(f"Zoom trigger phrase '{target_phrase}' not located in transcript.")

        # Pattern 3: Graphic Overlay -> "when I mention [phrase], (show|introduce|add) [graphic]"
        ov_matches = re.finditer(
            r"(?:when\s+(?:I\s+)?(?:mention|say|introduce|reach)\s+['\"]?([^'\",\.]+?)['\"]?[\,\s]+(?:show|introduce|add|display)\s+(?:an?\s+)?([^'\"\.]+?))(?:\.|\,|$)",
            instruction_text,
            re.IGNORECASE,
        )
        for m in ov_matches:
            target_phrase = m.group(1).strip()
            graphic_desc = m.group(2).strip()
            start_t, end_t = self._find_phrase_timing(target_phrase, transcript)
            if start_t is not None:
                # Classify graphic type from description
                g_type, g_props = self._resolve_graphic_preset(graphic_desc, target_phrase)
                directives.append(
                    ScriptDirective(
                        action="overlay",
                        trigger_phrase=target_phrase,
                        matched_start=start_t,
                        matched_end=min(video_duration, start_t + 3.5),
                        parameters={"type": g_type, **g_props},
                        matched=True,
                        reason=f"Explicit overlay '{graphic_desc}' triggered by phrase '{target_phrase}'",
                    )
                )
            else:
                unsupported.append(f"Overlay trigger phrase '{target_phrase}' not found in transcript.")

        return directives, unsupported

    def _find_phrase_timing(
        self, phrase: str, transcript: list[dict[str, Any]]
    ) -> tuple[float | None, float | None]:
        """Find start and end seconds of a multi-word phrase in word-aligned transcript."""
        clean_phrase_words = [re.sub(r"[^\w]", "", w).lower() for w in phrase.split()]
        if not clean_phrase_words or not transcript:
            return None, None

        n = len(clean_phrase_words)
        for i in range(len(transcript) - n + 1):
            window = [
                re.sub(r"[^\w]", "", transcript[i + j].get("word", "")).lower()
                for j in range(n)
            ]
            if window == clean_phrase_words:
                start_s = transcript[i].get("start", 0.0)
                end_s = transcript[i + n - 1].get("end", start_s + 0.5)
                return start_s, end_s

        # Fuzzy single-word fallback
        target = clean_phrase_words[0]
        for w in transcript:
            clean_w = re.sub(r"[^\w]", "", w.get("word", "")).lower()
            if target == clean_w:
                return w.get("start", 0.0), w.get("end", 0.0)

        return None, None

    def _resolve_graphic_preset(self, desc: str, trigger_phrase: str) -> tuple[str, dict[str, Any]]:
        """Map user graphic description to supported Remotion preset components."""
        desc_lower = desc.lower()
        if "stat" in desc_lower or "metric" in desc_lower or "percentage" in desc_lower or "number" in desc_lower:
            return "stat_card", {
                "stat": trigger_phrase.upper(),
                "subtitle": desc.title(),
                "accentColor": "#F59E0B",
            }
        if "comparison" in desc_lower or "versus" in desc_lower:
            return "comparison", {
                "title": desc.title(),
                "leftLabel": "Current",
                "rightLabel": "Target",
                "leftValue": "Before",
                "rightValue": "After",
            }
        if "chart" in desc_lower or "graph" in desc_lower:
            return "bar_chart", {
                "title": desc.title(),
                "chartData": [{"label": "A", "value": 30}, {"label": "B", "value": 70}],
            }
        # Default callout box
        return "callout", {
            "title": desc.upper(),
            "text": f"Context: {trigger_phrase}",
            "callout_type": "info",
            "accentColor": "#38BDF8",
        }
