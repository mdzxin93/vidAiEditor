"""Local text LLM provider (e.g. Ollama, llama-cpp-python)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any
import urllib.request
import urllib.error

from lib.ai.config import LocalLLMConfig
from lib.ai.providers.base import (
    BaseModelProvider,
    EditDecisionResult,
    VideoUnderstandingResult,
)

logger = logging.getLogger(__name__)


class LocalLLMProvider(BaseModelProvider):
    """Local text reasoning model provider (Ollama / llama-server)."""

    name = "local_llm"
    is_neural_model = True

    def __init__(self, config: LocalLLMConfig | None = None):
        self.config = config or LocalLLMConfig()

    def is_available(self) -> bool:
        """Check if local LLM server (e.g. Ollama) is running."""
        try:
            req = urllib.request.Request(f"{self.config.endpoint}/api/tags", headers={"User-Agent": "OpenMontage"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_status(self) -> dict[str, Any]:
        available = self.is_available()
        return {
            "provider": self.name,
            "backend": self.config.provider,
            "model_name": self.config.model_name,
            "endpoint": self.config.endpoint,
            "is_ready": available,
        }

    def understand_video(
        self,
        video_path: str,
        frames: list[dict[str, Any]],
        transcript: list[dict[str, Any]],
    ) -> VideoUnderstandingResult:
        """Text-only LLM defers raw visual frame analysis to heuristic rule provider."""
        from lib.ai.providers.rule_engine import HeuristicRuleProvider
        rule_prov = HeuristicRuleProvider()
        res = rule_prov.understand_video(video_path, frames, transcript)
        res.provider_name = f"local_llm:{self.config.model_name}(heuristic_frames)"
        return res

    def plan_edits(
        self,
        understanding: VideoUnderstandingResult,
        transcript: list[dict[str, Any]],
        user_prompt: str,
        video_metadata: dict[str, Any],
        style_name: str = "clean-professional",
        style_directives: Any = None,
    ) -> EditDecisionResult:
        t0 = time.time()
        if not self.is_available():
            logger.warning(
                "Local LLM endpoint at %s is not reachable; falling back to heuristic editorial intelligence.",
                self.config.endpoint,
            )
            from lib.ai.providers.rule_engine import HeuristicRuleProvider
            rule_prov = HeuristicRuleProvider()
            res = rule_prov.plan_edits(
                understanding=understanding,
                transcript=transcript,
                user_prompt=user_prompt,
                video_metadata=video_metadata,
                style_name=style_name,
            )
            res.provider_name = f"local_llm_fallback:{self.config.model_name}"
            res.decision_source = "heuristic_fallback"
            return res

        # Post prompt to Ollama / local server and parse JSON response
        prompt = (
            f"You are an automated video editor. Given the following video understanding "
            f"and word-level transcript, generate edit decisions conforming to OpenMontage schema.\n"
            f"User request: {user_prompt}\n"
            f"Return ONLY valid JSON."
        )
        payload = json.dumps({
            "model": self.config.model_name,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.config.endpoint}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            edits = json.loads(data.get("response", "{}"))

        return EditDecisionResult(
            edit_decisions=edits,
            provider_name=f"local_llm:{self.config.model_name}",
            decision_source="model_generated",
            planning_duration_sec=time.time() - t0,
        )
