"""Memory and Personalization Module for OpenMontage (Phase 10)."""

from lib.ai.memory.context_matcher import ContextMatcher, ContextMatchResult
from lib.ai.memory.models import (
    ApprovalStatus,
    CorrectionRecord,
    EditingPreference,
    EditingPreferenceCategory,
    PreferenceTier,
    StylePreset,
)
from lib.ai.memory.preference_resolver import (
    AppliedPreferenceRecord,
    PreferenceResolver,
    ResolvedEditorialPlan,
)
from lib.ai.memory.preference_store import BUILTIN_PRESETS, PreferenceStore

__all__ = [
    "ApprovalStatus",
    "CorrectionRecord",
    "EditingPreference",
    "EditingPreferenceCategory",
    "PreferenceTier",
    "StylePreset",
    "ContextMatcher",
    "ContextMatchResult",
    "PreferenceResolver",
    "ResolvedEditorialPlan",
    "AppliedPreferenceRecord",
    "PreferenceStore",
    "BUILTIN_PRESETS",
]
