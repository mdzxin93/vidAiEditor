"""OpenMontage Autonomous AI Editing Engine."""

from lib.ai.autonomous_editor import AutonomousEditingPlanner
from lib.ai.config import AIEditorConfig
from lib.ai.observability import ObservabilityTracker
from lib.ai.providers.base import (
    BaseModelProvider,
    EditDecisionResult,
    ObservationItem,
    VideoUnderstandingResult,
)
from lib.ai.providers.factory import get_model_provider
from lib.ai.video_understanding import VideoUnderstandingEngine
from lib.ai.qa_models import QAIssue, QAReport, QASeverity, QACategory, QAFixType, FixRecord
from lib.ai.qa_inspector import PostRenderQAInspector
from lib.ai.qa_fixer import IntelligentQAFixer
from lib.ai.qa_loop import AutonomousQALoop

__all__ = [
    "AutonomousEditingPlanner",
    "VideoUnderstandingEngine",
    "ObservabilityTracker",
    "AIEditorConfig",
    "BaseModelProvider",
    "VideoUnderstandingResult",
    "EditDecisionResult",
    "ObservationItem",
    "get_model_provider",
    "QAIssue",
    "QAReport",
    "QASeverity",
    "QACategory",
    "QAFixType",
    "FixRecord",
    "PostRenderQAInspector",
    "IntelligentQAFixer",
    "AutonomousQALoop",
]
