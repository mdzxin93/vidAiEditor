"""Provider factory for instantiating model providers."""

from __future__ import annotations

import logging
from typing import Optional

from lib.ai.config import AIEditorConfig
from lib.ai.providers.base import BaseModelProvider
from lib.ai.providers.local_vlm import LocalVLMProvider
from lib.ai.providers.local_llm import LocalLLMProvider
from lib.ai.providers.remote_api import RemoteAPIProvider
from lib.ai.providers.rule_engine import HeuristicRuleProvider

logger = logging.getLogger(__name__)


def get_model_provider(config: AIEditorConfig | None = None) -> BaseModelProvider:
    """Return configured model provider, falling back to heuristic engine if unavailable."""
    cfg = config or AIEditorConfig.load()
    provider_name = (cfg.provider or "heuristic_engine").lower()

    if provider_name == "local_vlm":
        prov = LocalVLMProvider(cfg.local_vlm)
        if prov.is_available():
            return prov
        logger.warning(
            "Local VLM provider requested but weights/dependencies are not ready. "
            "Falling back to heuristic engine baseline."
        )
        return HeuristicRuleProvider(cfg.editorial_rules)

    if provider_name == "local_llm":
        prov = LocalLLMProvider(cfg.local_llm)
        if prov.is_available():
            return prov
        logger.warning(
            "Local LLM provider requested but endpoint is unreachable. "
            "Falling back to heuristic engine baseline."
        )
        return HeuristicRuleProvider(cfg.editorial_rules)

    if provider_name == "remote_api":
        prov = RemoteAPIProvider(cfg.remote_api)
        if prov.is_available():
            return prov
        logger.warning(
            "Remote API provider requested but API key environment variable is missing. "
            "Falling back to heuristic engine baseline."
        )
        return HeuristicRuleProvider(cfg.editorial_rules)

    # Default
    return HeuristicRuleProvider(cfg.editorial_rules)
