"""Configuration schema and loader for the Autonomous AI Editor."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
from dataclasses import dataclass, field
import yaml


@dataclass
class LocalVLMConfig:
    model_name: str = "HuggingFaceTB/SmolVLM-500M-Instruct"
    model_format: str = "transformers"
    model_path: str | None = "models/SmolVLM-500M-Instruct"
    device: str = "cpu"
    quantization: str = "none"
    max_frames: int = 10
    frame_resolution: list[int] = field(default_factory=lambda: [640, 360])
    temperature: float = 0.2


@dataclass
class LocalLLMConfig:
    provider: str = "ollama"
    model_name: str = "llama3.2:3b"
    endpoint: str = "http://localhost:11434"
    temperature: float = 0.3


@dataclass
class RemoteAPIConfig:
    provider: str = "openai"
    model_name: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.3


@dataclass
class EditorialRulesConfig:
    min_pause_cut_duration: float = 0.5
    breath_pause_target: float = 0.20
    boundary_padding_seconds: float = 0.05
    zoom_frequency: str = "sparing"
    zoom_scale: float = 1.25
    min_zoom_duration: float = 1.5
    max_zoom_duration: float = 4.5
    export_aspect_ratio: str = "9:16"
    words_per_page: int = 3
    highlight_color: str = "#22D3EE"
    overlay_region: str = "upper_third"
    rest_interval_seconds: float = 2.0


@dataclass
class AIEditorConfig:
    provider: str = "heuristic_engine"
    local_vlm: LocalVLMConfig = field(default_factory=LocalVLMConfig)
    local_llm: LocalLLMConfig = field(default_factory=LocalLLMConfig)
    remote_api: RemoteAPIConfig = field(default_factory=RemoteAPIConfig)
    editorial_rules: EditorialRulesConfig = field(default_factory=EditorialRulesConfig)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "AIEditorConfig":
        """Load configuration from YAML file or return defaults."""
        if config_path is None:
            # Look in config/ai_editor.yaml then config.yaml
            cand = Path("config/ai_editor.yaml")
            if not cand.exists():
                cand = Path(__file__).resolve().parent.parent.parent / "config" / "ai_editor.yaml"
            if cand.exists():
                config_path = cand

        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            
            # If wrapped in ai_editor key
            data = raw.get("ai_editor", raw)
            
            vlm_raw = data.get("local_vlm", {})
            llm_raw = data.get("local_llm", {})
            remote_raw = data.get("remote_api", {})
            rules_raw = data.get("editorial_rules", {})

            return cls(
                provider=data.get("provider", "heuristic_engine"),
                local_vlm=LocalVLMConfig(**{k: v for k, v in vlm_raw.items() if hasattr(LocalVLMConfig, k)}),
                local_llm=LocalLLMConfig(**{k: v for k, v in llm_raw.items() if hasattr(LocalLLMConfig, k)}),
                remote_api=RemoteAPIConfig(**{k: v for k, v in remote_raw.items() if hasattr(RemoteAPIConfig, k)}),
                editorial_rules=EditorialRulesConfig(**{k: v for k, v in rules_raw.items() if hasattr(EditorialRulesConfig, k)}),
            )

        return cls()
