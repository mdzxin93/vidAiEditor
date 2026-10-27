"""AI Model Provider Interface package."""

from lib.ai.providers.base import (
    BaseModelProvider,
    EditDecisionResult,
    ObservationItem,
    VideoUnderstandingResult,
)
from lib.ai.providers.factory import get_model_provider
from lib.ai.providers.local_llm import LocalLLMProvider
from lib.ai.providers.local_vlm import LocalVLMProvider
from lib.ai.providers.remote_api import RemoteAPIProvider
from lib.ai.providers.rule_engine import HeuristicRuleProvider

__all__ = [
    "BaseModelProvider",
    "ObservationItem",
    "VideoUnderstandingResult",
    "EditDecisionResult",
    "LocalVLMProvider",
    "LocalLLMProvider",
    "RemoteAPIProvider",
    "HeuristicRuleProvider",
    "get_model_provider",
]
