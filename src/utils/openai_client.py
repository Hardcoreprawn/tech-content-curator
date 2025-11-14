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

from typing import Any, Literal, TypedDict

from openai import OpenAI
from openai.types.chat import ChatCompletion


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
            "max_tokens": "max_completion_tokens",
            "messages": "messages",
            "response_format": "response_format",
            "stop": "stop",
            "stream": "stream",
        },
        "unsupported": [
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
        return client.chat.completions.create(**api_params)
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
