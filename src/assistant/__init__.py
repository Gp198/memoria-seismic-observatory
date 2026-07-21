"""Context-aware explanatory assistant for the MEMÓRIA dashboard."""

from src.assistant.context import build_assistant_context, context_to_text
from src.assistant.mistral_client import (
    MistralAssistantClient,
    MistralAssistantConfig,
    MistralAssistantError,
    MistralAssistantResponse,
)

__all__ = [
    "build_assistant_context",
    "context_to_text",
    "MistralAssistantClient",
    "MistralAssistantConfig",
    "MistralAssistantError",
    "MistralAssistantResponse",
]

from src.assistant.identity import (
    PROJECT_IDENTITY_ANSWER,
    answer_identity_question,
    contains_false_ipma_attribution,
    enforce_identity_guard,
)
