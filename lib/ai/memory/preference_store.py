"""Local-First Preference Store & Correction Learning Engine (Phase 10).

Provides atomic, thread-safe, local file persistence for:
1. Approved editing preferences (preferences.json)
2. Correction audit logs (corrections.json)
3. Built-in and user-defined style presets (presets.json)

Zero cloud dependencies, zero external network calls.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Optional

from lib.ai.memory.models import (
    ApprovalStatus,
    CorrectionRecord,
    EditingPreference,
    EditingPreferenceCategory,
    StylePreset,
)

logger = logging.getLogger(__name__)

DEFAULT_PREFERENCES_DIR = Path("config/preferences")


BUILTIN_PRESETS: list[StylePreset] = [
    StylePreset(
        preset_id="educational-explainer",
        title="Educational Explainer",
        description="Clear, authoritative pacing with subtle zooms and high-legibility captions.",
        is_builtin=True,
        target_aspect="9:16",
        caption_preset="word_highlight",
        caption_font_family="Inter, sans-serif",
        caption_font_size=48,
        caption_highlight_color="#38BDF8",
        caption_background_color="rgba(15, 23, 42, 0.75)",
        words_per_page=4,
        zoom_intensity="subtle",
        zoom_scale=1.10,
        cut_aggressiveness="balanced",
        min_pause_cut_duration=1.2,
        pacing_rest_interval=2.5,
        graphic_density="medium",
        preferred_overlay_types=["stat_card", "callout", "comparison"],
        color_palette={"primary": "#2563EB", "accent": "#38BDF8", "background": "#0F172A"},
        audio_settings={"bgm_enabled": True, "bgm_volume": 0.20},
    ),
    StylePreset(
        preset_id="high-energy-short",
        title="High-Energy Viral Short",
        description="Snappy dead-air cuts, punchy 1.4x emphasis zooms, and dynamic Hormozi captions.",
        is_builtin=True,
        target_aspect="9:16",
        caption_preset="viral_dynamic",
        caption_font_family="Montserrat, sans-serif",
        caption_font_size=56,
        caption_highlight_color="#FACC15",
        caption_background_color="rgba(0, 0, 0, 0.85)",
        words_per_page=3,
        zoom_intensity="punchy",
        zoom_scale=1.40,
        cut_aggressiveness="aggressive",
        min_pause_cut_duration=0.55,
        pacing_rest_interval=1.8,
        graphic_density="data_heavy",
        preferred_overlay_types=["stat_card", "stat_reveal", "callout"],
        color_palette={"primary": "#7C3AED", "accent": "#FACC15", "background": "#000000"},
        audio_settings={"bgm_enabled": True, "bgm_volume": 0.35},
    ),
    StylePreset(
        preset_id="minimal-professional",
        title="Minimal Professional",
        description="Executive, corporate look with clean typography, conservative cuts, and no aggressive zooms.",
        is_builtin=True,
        target_aspect="16:9",
        caption_preset="clean_lower_third",
        caption_font_family="Inter, sans-serif",
        caption_font_size=42,
        caption_highlight_color="#2563EB",
        caption_background_color="rgba(255, 255, 255, 0.90)",
        words_per_page=5,
        zoom_intensity="none",
        zoom_scale=1.00,
        cut_aggressiveness="conservative",
        min_pause_cut_duration=1.8,
        pacing_rest_interval=3.5,
        graphic_density="minimal",
        preferred_overlay_types=["callout"],
        color_palette={"primary": "#1E293B", "accent": "#2563EB", "background": "#FFFFFF"},
        audio_settings={"bgm_enabled": False, "bgm_volume": 0.0},
    ),
    StylePreset(
        preset_id="technology-demo",
        title="Technology Demonstration",
        description="Balanced rhythm suited for code walkthroughs, UI flows, and KPI benchmarks.",
        is_builtin=True,
        target_aspect="16:9",
        caption_preset="word_highlight",
        caption_font_family="JetBrains Mono, monospace",
        caption_font_size=44,
        caption_highlight_color="#10B981",
        caption_background_color="rgba(17, 24, 39, 0.85)",
        words_per_page=4,
        zoom_intensity="subtle",
        zoom_scale=1.12,
        cut_aggressiveness="balanced",
        min_pause_cut_duration=1.0,
        pacing_rest_interval=2.2,
        graphic_density="medium",
        preferred_overlay_types=["stat_card", "kpi_grid", "callout"],
        color_palette={"primary": "#059669", "accent": "#10B981", "background": "#111827"},
        audio_settings={"bgm_enabled": True, "bgm_volume": 0.18},
    ),
]


class PreferenceStore:
    """Thread-safe, versioned local preference manager."""

    def __init__(self, storage_dir: Path | str | None = None):
        self.storage_dir = Path(storage_dir or DEFAULT_PREFERENCES_DIR).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        self.pref_file = self.storage_dir / "preferences.json"
        self.corr_file = self.storage_dir / "corrections.json"
        self.preset_file = self.storage_dir / "presets.json"
        self.settings_file = self.storage_dir / "settings.json"

        self._ensure_files()

    def _ensure_files(self) -> None:
        """Initialize files if not present."""
        if not self.pref_file.exists():
            self._atomic_write(self.pref_file, {"version": "1.0", "preferences": []})
        if not self.corr_file.exists():
            self._atomic_write(self.corr_file, {"version": "1.0", "corrections": []})
        if not self.preset_file.exists():
            builtin_dicts = [p.to_dict() for p in BUILTIN_PRESETS]
            self._atomic_write(self.preset_file, {"version": "1.0", "presets": builtin_dicts})
        if not self.settings_file.exists():
            self._atomic_write(
                self.settings_file,
                {
                    "personalization_enabled": True,
                    "active_preset_id": "educational-explainer",
                    "preference_influence_weight": 0.85,
                    "auto_learn_from_approved_only": True,
                },
            )

    def _atomic_write(self, target_path: Path, data: Any) -> None:
        """Atomically write JSON data to prevent corruptions during power loss."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_fd, temp_path = tempfile.mkstemp(dir=target_path.parent, prefix="tmp_pref_")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            shutil.move(temp_path, target_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            raise

    # ------------------------------------------------------------------------
    # 1. Global Settings
    # ------------------------------------------------------------------------

    def get_settings(self) -> dict[str, Any]:
        with self._lock:
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {
                    "personalization_enabled": True,
                    "active_preset_id": "educational-explainer",
                    "preference_influence_weight": 0.85,
                }

    def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            curr = self.get_settings()
            curr.update(updates)
            self._atomic_write(self.settings_file, curr)
            return curr

    def is_personalization_enabled(self) -> bool:
        return bool(self.get_settings().get("personalization_enabled", True))

    def set_personalization_enabled(self, enabled: bool) -> None:
        self.update_settings({"personalization_enabled": enabled})

    # ------------------------------------------------------------------------
    # 2. Preferences CRUD
    # ------------------------------------------------------------------------

    def list_preferences(
        self,
        category: Optional[str] = None,
        enabled_only: bool = False,
    ) -> list[EditingPreference]:
        with self._lock:
            try:
                with open(self.pref_file, "r", encoding="utf-8") as f:
                    raw = json.load(f).get("preferences", [])
            except Exception:
                raw = []

            prefs = [EditingPreference.from_dict(d) for d in raw]
            if category:
                prefs = [p for p in prefs if p.category == category]
            if enabled_only:
                prefs = [p for p in prefs if p.enabled]
            return prefs

    def get_preference(self, preference_id: str) -> Optional[EditingPreference]:
        for p in self.list_preferences():
            if p.preference_id == preference_id:
                return p
        return None

    def find_matching_preference(
        self,
        parameter_key: str,
        context: dict[str, Any] | None = None,
    ) -> Optional[EditingPreference]:
        """Find the most confident active preference for a given parameter key that satisfies context."""
        candidates = [
            p for p in self.list_preferences(enabled_only=True)
            if p.parameter_key == parameter_key
        ]
        if not candidates:
            return None

        # Filter by context if provided
        if context:
            matching = [p for p in candidates if p.matches_context(context)]
            if matching:
                candidates = matching

        # Sort by confidence and times_approved
        candidates.sort(key=lambda p: (p.confidence, p.times_approved), reverse=True)
        return candidates[0]

    def save_preference(self, pref: EditingPreference) -> EditingPreference:
        with self._lock:
            try:
                with open(self.pref_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"version": "1.0", "preferences": []}

            items = data.get("preferences", [])
            existing_idx = next(
                (i for i, item in enumerate(items) if item.get("preference_id") == pref.preference_id),
                None,
            )

            pref_dict = pref.to_dict()
            if existing_idx is not None:
                items[existing_idx] = pref_dict
            else:
                items.append(pref_dict)

            data["preferences"] = items
            self._atomic_write(self.pref_file, data)
            return pref

    def delete_preference(self, preference_id: str) -> bool:
        """Persistently delete an approved preference from disk."""
        with self._lock:
            try:
                with open(self.pref_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                return False

            items = data.get("preferences", [])
            initial_len = len(items)
            items = [item for item in items if item.get("preference_id") != preference_id]
            if len(items) == initial_len:
                return False

            data["preferences"] = items
            self._atomic_write(self.pref_file, data)
            return True

    def reset_all_preferences(self) -> bool:
        """Purge all learned preferences and reset store to factory defaults."""
        with self._lock:
            self._atomic_write(self.pref_file, {"version": "1.0", "preferences": []})
            self._atomic_write(self.corr_file, {"version": "1.0", "corrections": []})
            builtin_dicts = [p.to_dict() for p in BUILTIN_PRESETS]
            self._atomic_write(self.preset_file, {"version": "1.0", "presets": builtin_dicts})
            return True

    # ------------------------------------------------------------------------
    # 3. Corrections & Approval-Based Learning
    # ------------------------------------------------------------------------

    def record_correction(self, correction: CorrectionRecord) -> CorrectionRecord:
        """Log a user modification for audit and potential approval."""
        with self._lock:
            try:
                with open(self.corr_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"version": "1.0", "corrections": []}

            corrs = data.get("corrections", [])
            # Avoid duplicate recordings for identical correction_id
            existing = next((i for i in corrs if i.get("correction_id") == correction.correction_id), None)
            if existing is None:
                corrs.insert(0, correction.to_dict())
                # Keep up to 200 recent corrections
                data["corrections"] = corrs[:200]
                self._atomic_write(self.corr_file, data)
            return correction

    def list_corrections(self, project_id: Optional[str] = None) -> list[CorrectionRecord]:
        with self._lock:
            try:
                with open(self.corr_file, "r", encoding="utf-8") as f:
                    raw = json.load(f).get("corrections", [])
            except Exception:
                raw = []

            corrs = [CorrectionRecord.from_dict(d) for d in raw]
            if project_id:
                corrs = [c for c in corrs if c.project_id == project_id]
            return corrs

    def approve_correction(
        self,
        correction_id: str,
        apply_to_future: bool = True,
        context_constraints: Optional[dict[str, Any]] = None,
    ) -> Optional[EditingPreference]:
        """Approve a recorded correction. If apply_to_future is True, creates/reinforces an EditingPreference."""
        with self._lock:
            try:
                with open(self.corr_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                return None

            corrs = data.get("corrections", [])
            target = next((c for c in corrs if c.get("correction_id") == correction_id), None)
            if not target:
                return None

            target["approval_status"] = ApprovalStatus.APPROVED.value if apply_to_future else ApprovalStatus.ONE_TIME.value
            self._atomic_write(self.corr_file, data)

        if not apply_to_future:
            return None

        # Build or reinforce editing preference
        pref_id = f"pref_{target['category']}_{target['parameter_key'].replace('.', '_')}"
        existing_pref = self.get_preference(pref_id)

        constraints = context_constraints or {}
        # If no constraints explicitly provided, infer target_aspect if available
        if not constraints and "aspect_ratio" in target.get("editing_context", {}):
            constraints["target_aspect"] = target["editing_context"]["aspect_ratio"]

        if existing_pref:
            existing_pref.preferred_value = target["user_corrected_value"]
            existing_pref.times_approved += 1
            existing_pref.confidence = min(0.99, existing_pref.confidence + 0.03)
            existing_pref.updated_at = time.time()
            existing_pref.source_correction_id = correction_id
            if constraints:
                existing_pref.context_constraints.update(constraints)
            return self.save_preference(existing_pref)
        else:
            new_pref = EditingPreference(
                preference_id=pref_id,
                category=target["category"],
                parameter_key=target["parameter_key"],
                preferred_value=target["user_corrected_value"],
                confidence=0.92,
                times_approved=1,
                context_constraints=constraints,
                enabled=True,
                created_at=time.time(),
                updated_at=time.time(),
                source_correction_id=correction_id,
                description=f"User approved preference for {target['parameter_key']} (originally {target['original_ai_value']})",
            )
            return self.save_preference(new_pref)

    def reject_correction(self, correction_id: str) -> bool:
        """Mark a correction as one-time / rejected so it will never form a preference."""
        with self._lock:
            try:
                with open(self.corr_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                return False

            corrs = data.get("corrections", [])
            target = next((c for c in corrs if c.get("correction_id") == correction_id), None)
            if not target:
                return False

            target["approval_status"] = ApprovalStatus.REJECTED.value
            self._atomic_write(self.corr_file, data)
            return True

    # ------------------------------------------------------------------------
    # 4. Style Presets Management
    # ------------------------------------------------------------------------

    def list_presets(self) -> list[StylePreset]:
        with self._lock:
            try:
                with open(self.preset_file, "r", encoding="utf-8") as f:
                    raw = json.load(f).get("presets", [])
            except Exception:
                raw = []
            return [StylePreset.from_dict(d) for d in raw]

    def get_preset(self, preset_id: str) -> Optional[StylePreset]:
        for p in self.list_presets():
            if p.preset_id == preset_id:
                return p
        return None

    def save_preset(self, preset: StylePreset) -> StylePreset:
        with self._lock:
            try:
                with open(self.preset_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"version": "1.0", "presets": []}

            items = data.get("presets", [])
            existing_idx = next((i for i, p in enumerate(items) if p.get("preset_id") == preset.preset_id), None)
            if existing_idx is not None:
                items[existing_idx] = preset.to_dict()
            else:
                items.append(preset.to_dict())

            data["presets"] = items
            self._atomic_write(self.preset_file, data)
            return preset

    def delete_preset(self, preset_id: str) -> bool:
        with self._lock:
            try:
                with open(self.preset_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                return False

            items = data.get("presets", [])
            target = next((p for p in items if p.get("preset_id") == preset_id), None)
            if not target or target.get("is_builtin"):
                # Cannot delete built-in presets
                return False

            data["presets"] = [p for p in items if p.get("preset_id") != preset_id]
            self._atomic_write(self.preset_file, data)
            return True

    # ------------------------------------------------------------------------
    # 5. Export & Import Security
    # ------------------------------------------------------------------------

    def export_all(self) -> dict[str, Any]:
        """Export all preferences and non-builtin presets as a clean JSON payload."""
        return {
            "version": "1.0",
            "exported_at": time.time(),
            "settings": self.get_settings(),
            "preferences": [p.to_dict() for p in self.list_preferences()],
            "presets": [p.to_dict() for p in self.list_presets() if not p.is_builtin],
        }

    def export_data(self) -> dict[str, Any]:
        return self.export_all()

    def import_payload(self, data: dict[str, Any], merge: bool = True) -> dict[str, int]:
        """Safely import preferences and presets from an exported JSON bundle."""
        if not isinstance(data, dict) or "version" not in data:
            raise ValueError("Invalid preference bundle: missing version identifier.")

        imported_prefs = 0
        imported_presets = 0

        raw_prefs = data.get("preferences", [])
        if isinstance(raw_prefs, list):
            for rp in raw_prefs:
                if isinstance(rp, dict) and "preference_id" in rp and "parameter_key" in rp:
                    pref_id = str(rp["preference_id"])
                    if ".." in pref_id or "/" in pref_id or "\\" in pref_id:
                        raise ValueError(f"Invalid preference identifier '{pref_id}': path traversal characters forbidden.")
                    p = EditingPreference.from_dict(rp)
                    self.save_preference(p)
                    imported_prefs += 1

        raw_presets = data.get("presets", [])
        if isinstance(raw_presets, list):
            for rps in raw_presets:
                if isinstance(rps, dict) and "preset_id" in rps and "title" in rps:
                    preset_id = str(rps["preset_id"])
                    if ".." in preset_id or "/" in preset_id or "\\" in preset_id:
                        raise ValueError(f"Invalid preset identifier '{preset_id}': path traversal characters forbidden.")
                    rps["is_builtin"] = False  # Custom presets from import are never builtin
                    preset = StylePreset.from_dict(rps)
                    self.save_preset(preset)
                    imported_presets += 1

        return {
            "preferences_imported": imported_prefs,
            "presets_imported": imported_presets,
            "imported_preferences": imported_prefs,
            "imported_presets": imported_presets,
        }

    def import_data(self, data: dict[str, Any], overwrite: bool = False) -> dict[str, int]:
        return self.import_payload(data, merge=not overwrite)


# Global singleton instance for store access
preference_store = PreferenceStore()
