"""OpenAI API client wrapper with config-driven parameter mapping.

This module provides a consistent interface for calling OpenAI's API across
different model families (GPT-4, GPT-5, o1, etc.) by automatically translating
our parameter names to the correct API parameter names.

Design Philosophy:
- Configuration over code - model differences defined in MODEL_CONFIGS
- Type-safe with TypedDict definitions
- Easy to extend when new models are released
- Single source of truth for all OpenAI interactions

Usage:
    from src.utils.openai_client import create_chat_completion

    response = create_chat_completion(
        client=client,
        model="gpt-5-mini",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=500,  # Automatically translated to max_completion_tokens
        temperature=0.7,
    )
"""

import logging
from typing import Any, Literal, TypedDict

from openai import OpenAI
from openai.types.chat import ChatCompletion

logger = logging.getLogger(__name__)


class ModelConfig(TypedDict):
    """Configuration for a model family's parameter mappings."""

    prefix: str  # Model name prefix (e.g., "gpt-5")
    param_map: dict[str, str]  # our_param_name -> api_param_name
    unsupported: list[str]  # Parameters this model doesn't support


# Model family configurations - add new models here
MODEL_CONFIGS: list[ModelConfig] = [
    {
        "prefix": "gpt-5",
        "param_map": {
            # NOTE: GPT-5 models have a bug where specifying max_completion_tokens
            # causes them to use all tokens for internal reasoning, returning empty content.
            # We intentionally DON'T map max_tokens to prevent this issue.
            # "max_tokens": "max_completion_tokens",  # DISABLED - causes empty responses
            "messages": "messages",
            "response_format": "response_format",
            "stop": "stop",
            "stream": "stream",
        },
        "unsupported": [
            "max_tokens",  # CRITICAL: Causes empty responses in GPT-5
            "temperature",  # GPT-5 mini only supports default (1.0)
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "seed",
            "logprobs",
            "top_logprobs",
        ],
    },
    {
        "prefix": "gpt-4",
        "param_map": {
            "max_tokens": "max_tokens",
            "temperature": "temperature",
            "messages": "messages",
            "response_format": "response_format",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "presence_penalty": "presence_penalty",
            "seed": "seed",
            "stop": "stop",
            "stream": "stream",
            "logprobs": "logprobs",
            "top_logprobs": "top_logprobs",
        },
        "unsupported": [],
    },
    {
        "prefix": "gpt-3.5-turbo",
        "param_map": {
            "max_tokens": "max_tokens",
            "temperature": "temperature",
            "messages": "messages",
            "response_format": "response_format",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "presence_penalty": "presence_penalty",
            "stop": "stop",
            "stream": "stream",
        },
        "unsupported": [],
    },
    {
        "prefix": "o1",
        "param_map": {
            "max_tokens": "max_completion_tokens",
            "messages": "messages",
        },
        "unsupported": [
            "temperature",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
        ],
    },
    {
        "prefix": "o3",
        "param_map": {
            "max_tokens": "max_completion_tokens",
            "messages": "messages",
        },
        "unsupported": [
            "temperature",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
        ],
    },
]


# GPT-5 to GPT-4 fallback mapping (for empty response handling)
GPT5_TO_GPT4_FALLBACK: dict[str, str] = {
    "gpt-5": "gpt-4o",
    "gpt-5-mini": "gpt-4o-mini",
    "gpt-5-nano": "gpt-4o-mini",
    "gpt-5-pro": "gpt-4o",  # Pro falls back to standard gpt-4o
    # Versioned models
    "gpt-5-2025-08-07": "gpt-4o",
    "gpt-5-mini-2025-08-07": "gpt-4o-mini",
    "gpt-5-nano-2025-08-07": "gpt-4o-mini",
    "gpt-5-pro-2025-10-06": "gpt-4o",
}


def get_fallback_model(model: str) -> str | None:
    """Get GPT-4 fallback model for a GPT-5 model.

    Args:
        model: Original model name

    Returns:
        Fallback model name, or None if no fallback available
    """
    # Check exact match first
    if model in GPT5_TO_GPT4_FALLBACK:
        return GPT5_TO_GPT4_FALLBACK[model]

    # Check if it starts with any GPT-5 prefix
    for gpt5_prefix, gpt4_fallback in GPT5_TO_GPT4_FALLBACK.items():
        if model.startswith(gpt5_prefix):
            return gpt4_fallback

    return None


def get_model_config(model: str) -> ModelConfig:
    """Get parameter mapping configuration for a model.

    Args:
        model: Model name (e.g., "gpt-5-mini", "gpt-4o", "o1-preview")

    Returns:
        ModelConfig with parameter mappings for this model family

    Raises:
        ValueError: If model family is not recognized
    """
    for config in MODEL_CONFIGS:
        if model.startswith(config["prefix"]):
            return config

    raise ValueError(
        f"Unknown model family: {model}. "
        f"Supported prefixes: {[c['prefix'] for c in MODEL_CONFIGS]}"
    )


def get_model_family(
    model: str,
) -> Literal["gpt5", "gpt4", "gpt35", "o1", "o3", "unknown"]:
    """Detect which model family a model belongs to.

    Args:
        model: Model name to check

    Returns:
        Model family identifier or "unknown"
    """
    # Map prefix to family name (single source of truth with MODEL_CONFIGS)
    PREFIX_TO_FAMILY: dict[str, Literal["gpt5", "gpt4", "gpt35", "o1", "o3"]] = {
        "gpt-5": "gpt5",
        "gpt-4": "gpt4",
        "gpt-3.5-turbo": "gpt35",
        "o1": "o1",
        "o3": "o3",
    }

    for config in MODEL_CONFIGS:
        if model.startswith(config["prefix"]):
            family = PREFIX_TO_FAMILY.get(config["prefix"])
            if family:
                return family

    return "unknown"


def create_chat_completion(
    client: OpenAI,
    model: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    response_format: dict[str, Any] | None = None,
    top_p: float | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
    seed: int | None = None,
    stop: str | list[str] | None = None,
    stream: bool = False,
    logprobs: bool | None = None,
    top_logprobs: int | None = None,
) -> ChatCompletion:
    """Create a chat completion with automatic parameter mapping.

    This function automatically translates parameter names based on the model
    being used. For example, max_tokens becomes max_completion_tokens for GPT-5
    models but stays as max_tokens for GPT-4 models.

    Args:
        client: OpenAI client instance
        model: Model name (e.g., "gpt-5-mini", "gpt-4o-mini", "o1-preview")
        messages: List of message dicts with 'role' and 'content' keys
        max_tokens: Maximum tokens to generate (auto-translated per model)
        temperature: Sampling temperature (0-2), not supported by o1/o3
        response_format: For JSON mode, e.g., {"type": "json_object"}
        top_p: Nucleus sampling parameter (0-1)
        frequency_penalty: Frequency penalty (-2 to 2)
        presence_penalty: Presence penalty (-2 to 2)
        seed: Random seed for deterministic output
        stop: Stop sequences (string or list of strings)
        stream: Whether to stream responses
        logprobs: Whether to return log probabilities
        top_logprobs: Number of most likely tokens to return at each position

    Returns:
        ChatCompletion response from OpenAI API

    Raises:
        ValueError: If model is not recognized or unsupported parameters are used

    Example:
        >>> response = create_chat_completion(
        ...     client=client,
        ...     model="gpt-5-mini",
        ...     messages=[{"role": "user", "content": "Hello!"}],
        ...     max_tokens=100,
        ...     temperature=0.7,
        ... )
    """
    # Get model configuration
    config = get_model_config(model)

    # Start building API parameters
    api_params: dict[str, Any] = {"model": model}

    # Map messages parameter
    api_params[config["param_map"]["messages"]] = messages

    # Collect all our parameters
    our_params = {
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": response_format,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "seed": seed,
        "stop": stop,
        "stream": stream,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
    }

    # Translate each parameter using the model's configuration
    for our_name, value in our_params.items():
        if value is None:
            continue

        # Skip known unsupported parameters
        if our_name in config["unsupported"]:
            continue

        # Check if we have a mapping for this parameter
        if our_name in config["param_map"]:
            api_name = config["param_map"][our_name]
            api_params[api_name] = value

    # Make the API call with automatic fallback on parameter errors
    try:
        response = client.chat.completions.create(**api_params)

        # Check for empty response content (known GPT-5 bug)
        if response.choices and response.choices[0].message.content is not None:
            content = response.choices[0].message.content.strip()
            if content:
                return response  # Valid response

        # Empty response detected
        logger.warning(
            f"Empty response from model '{model}' "
            f"(tokens: {response.usage.prompt_tokens if response.usage else 0}/"
            f"{response.usage.completion_tokens if response.usage else 0})"
        )

        # Try fallback to GPT-4 if available
        fallback_model = get_fallback_model(model)
        if fallback_model:
            logger.info(
                f"Attempting fallback: {model} -> {fallback_model} due to empty response"
            )

            # Update api_params with fallback model and adjust parameters
            fallback_config = get_model_config(fallback_model)
            fallback_params: dict[str, Any] = {"model": fallback_model}

            # Re-map all parameters for the fallback model
            fallback_params[fallback_config["param_map"]["messages"]] = messages

            our_params = {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "response_format": response_format,
                "top_p": top_p,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty,
                "seed": seed,
                "stop": stop,
                "stream": stream,
                "logprobs": logprobs,
                "top_logprobs": top_logprobs,
            }

            for our_name, value in our_params.items():
                if value is None:
                    continue
                if our_name in fallback_config["unsupported"]:
                    continue
                if our_name in fallback_config["param_map"]:
                    api_name = fallback_config["param_map"][our_name]
                    fallback_params[api_name] = value

            # Retry with fallback model
            fallback_response = client.chat.completions.create(**fallback_params)

            # Check fallback response
            if (
                fallback_response.choices
                and fallback_response.choices[0].message.content
            ):
                fallback_content = fallback_response.choices[0].message.content.strip()
                if fallback_content:
                    logger.info(
                        f"Fallback successful: {fallback_model} returned "
                        f"{len(fallback_content)} chars"
                    )
                    return fallback_response

            logger.error(f"Fallback to {fallback_model} also returned empty response")

        # No fallback available or fallback also failed
        logger.error(
            f"No valid response from {model}"
            + (f" or fallback {fallback_model}" if fallback_model else "")
        )
        return response  # Return original empty response

    except Exception as e:
        error_msg = str(e).lower()

        # Check if it's an unsupported parameter error
        if "unsupported" in error_msg or "does not support" in error_msg:
            # Try to extract which parameter failed
            failed_params = []
            for param_name in [
                "temperature",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
                "seed",
                "logprobs",
                "top_logprobs",
            ]:
                if param_name in error_msg:
                    failed_params.append(param_name)

            # If we identified failed params, retry without them
            if failed_params:
                logger.warning(
                    f"Model {model} doesn't support parameters: {failed_params}. Retrying without them."
                )
                # Remove failed parameters from api_params
                for param in failed_params:
                    api_params.pop(param, None)

                # Retry the call
                return client.chat.completions.create(**api_params)

        # If not a parameter error, or retry failed, raise original error
        raise


def validate_model_config() -> list[str]:
    """Validate MODEL_CONFIGS for completeness and consistency.

    Returns:
        List of validation warnings (empty if all valid)

    Example:
        >>> warnings = validate_model_config()
        >>> if warnings:
        ...     print("Configuration issues:", warnings)
    """
    warnings = []

    # Check for duplicate prefixes
    prefixes = [config["prefix"] for config in MODEL_CONFIGS]
    if len(prefixes) != len(set(prefixes)):
        warnings.append("Duplicate model prefixes found")

    # Check that all configs have required keys
    required_keys = {"prefix", "param_map", "unsupported"}
    for config in MODEL_CONFIGS:
        missing = required_keys - set(config.keys())
        if missing:
            warnings.append(
                f"Config for '{config.get('prefix', 'UNKNOWN')}' "
                f"missing keys: {missing}"
            )

    # Check that messages is always mapped
    for config in MODEL_CONFIGS:
        if "messages" not in config["param_map"]:
            warnings.append(
                f"Config for '{config['prefix']}' missing 'messages' mapping"
            )

    return warnings
