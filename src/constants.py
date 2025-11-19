"""Application-wide constants and configuration values.

This module defines supported models, API configurations, and other
constants used across the application. This serves as the single
source of truth for model support policy.
"""

from typing import Dict, Literal

# ===== Supported Models (Single Source of Truth) =====

# Model support policy: Responses API ONLY
# GPT-3.5 is NOT supported (Responses API limitation)

SupportedModel = Literal[
    "gpt-5",
    "gpt-5.1",
    "gpt-5.1-chat-latest",
    "gpt-4-turbo",
]

SUPPORTED_MODELS: Dict[str, Dict[str, any]] = {
    # Primary Models (recommended)
    "gpt-5": {
        "api": "responses",
        "reasoning": True,
        "description": "GPT-5 base model (Aug 2025)",
        "priority": "primary",
    },
    "gpt-5.1": {
        "api": "responses",
        "reasoning": True,
        "description": "GPT-5.1 Thinking (adaptive reasoning)",
        "priority": "primary",
    },
    "gpt-5.1-chat-latest": {
        "api": "responses",
        "reasoning": True,
        "description": "GPT-5.1 Instant (fast, conversational)",
        "priority": "primary",
    },
    # Fallback Models (supported)
    "gpt-4-turbo": {
        "api": "responses",
        "reasoning": False,
        "description": "GPT-4 Turbo (fallback if GPT-5 unavailable)",
        "priority": "fallback",
    },
}


def is_model_supported(model: str) -> bool:
    """Check if a model is supported by the application.

    Args:
        model: Model identifier (e.g., "gpt-5", "gpt-4-turbo")

    Returns:
        True if model is supported, False otherwise
    """
    return model in SUPPORTED_MODELS


def get_model_info(model: str) -> Dict[str, any]:
    """Get information about a supported model.

    Args:
        model: Model identifier

    Returns:
        Dictionary with model information

    Raises:
        ValueError: If model is not supported
    """
    if not is_model_supported(model):
        raise ValueError(
            f"Model '{model}' is not supported. "
            f"Supported models: {list(SUPPORTED_MODELS.keys())}"
        )
    return SUPPORTED_MODELS[model]


def get_primary_models() -> list[str]:
    """Get list of primary (recommended) models.

    Returns:
        List of primary model identifiers
    """
    return [
        model
        for model, info in SUPPORTED_MODELS.items()
        if info["priority"] == "primary"
    ]


def get_fallback_models() -> list[str]:
    """Get list of fallback models.

    Returns:
        List of fallback model identifiers
    """
    return [
        model
        for model, info in SUPPORTED_MODELS.items()
        if info["priority"] == "fallback"
    ]


# ===== Reasoning Effort Configuration =====

VALID_REASONING_EFFORTS = ["minimal", "low", "medium", "high"]

DEFAULT_REASONING_EFFORT = "medium"


# ===== API Configuration =====

# All services use Responses API (Phase 1 & 1.5)
API_TYPE = "responses"

# Temperature is NOT configurable in Responses API (fixed at 1.0)
TEMPERATURE_CONFIGURABLE = False

# Default max output tokens
DEFAULT_MAX_OUTPUT_TOKENS = 150
