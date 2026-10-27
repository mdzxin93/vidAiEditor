"""Remote API provider for cloud multimodal/reasoning models (optional, fallback)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from lib.ai.config import RemoteAPIConfig
from lib.ai.providers.base import (
    BaseModelProvider,
    EditDecisionResult,
    ObservationItem,
    VideoUnderstandingResult,
)

logger = logging.getLogger(__name__)


class RemoteAPIProvider(BaseModelProvider):
    """Optional remote provider (OpenAI, Gemini, OpenRouter) for multimodal reasoning."""

    name = "remote_api"
    is_neural_model = True

    def __init__(self, config: RemoteAPIConfig | None = None):
        self.config = config or RemoteAPIConfig()

    def is_available(self) -> bool:
        """Check if relevant API key environment variable is set."""
        key = os.environ.get(self.config.api_key_env)
        return bool(key and key.strip())

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "api_provider": self.config.provider,
            "model_name": self.config.model_name,
            "api_key_env": self.config.api_key_env,
            "is_ready": self.is_available(),
        }

    def understand_video(
        self,
        video_path: str,
        frames: list[dict[str, Any]],
        transcript: list[dict[str, Any]],
    ) -> VideoUnderstandingResult:
        if not self.is_available():
            raise RuntimeError(f"Remote API key environment variable '{self.config.api_key_env}' not set.")
        # Implementation via OpenAI / Gemini SDK
        raise NotImplementedError("Remote multimodal video understanding stub.")

    def plan_edits(
        self,
        understanding: VideoUnderstandingResult,
        transcript: list[dict[str, Any]],
        user_prompt: str,
        video_metadata: dict[str, Any],
        style_name: str = "clean-professional",
        style_directives: Any = None,
    ) -> EditDecisionResult:
        if not self.is_available():
            raise RuntimeError(f"Remote API key environment variable '{self.config.api_key_env}' not set.")
        # Implementation via OpenAI / Gemini SDK
        raise NotImplementedError("Remote editing plan stub.")
