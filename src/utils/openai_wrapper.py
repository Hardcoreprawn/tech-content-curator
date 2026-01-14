"""Instrumented wrapper around OpenAI SDK calls.

All LLM/image traffic must flow through this module so we can:
- enforce explicit stage + model selection
- capture standardized telemetry and ledger entries per run/article
- estimate costs using ``data/model_pricing.json``
- enforce optional spend caps defined in configuration
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletion

from ..config import get_config, get_data_dir
from ..models import PipelineConfig
from .logging import get_logger
from .openai_client import create_chat_completion
from .pricing import estimate_image_cost, estimate_text_cost  # type: ignore[import]

logger = get_logger(__name__)

_RUN_ID = os.getenv("GITHUB_RUN_ID") or datetime.now(UTC).strftime("%Y%m%dT%H%M%S")


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _ensure_run_dirs() -> tuple[Path, Path, Path]:
    data_dir = get_data_dir()
    run_dir = data_dir / "runs" / _RUN_ID
    articles_dir = run_dir / "articles"
    run_dir.mkdir(parents=True, exist_ok=True)
    articles_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, articles_dir, run_dir / "model_usage.json"


_RUN_DIR, _ARTICLES_DIR, _MODEL_USAGE_FILE = _ensure_run_dirs()
_RUN_COST_TOTAL = 0.0
_ARTICLE_COSTS: dict[str, float] = {}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _append_json_entry(file_path: Path, entry: dict[str, Any], root_key: str) -> None:
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Resetting corrupt telemetry file %s: %s", file_path, exc)
            data = {}
    else:
        data = {}

    data.setdefault("run_id", _RUN_ID)
    data.setdefault(root_key, [])
    data[root_key].append(entry)
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _append_article_entry(article_id: str, entry: dict[str, Any]) -> None:
    safe_article = article_id.replace(os.sep, "-")
    file_path = _ARTICLES_DIR / f"{safe_article}.json"
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning(
                "Resetting corrupt article ledger %s: %s",
                file_path,
                exc,
            )
            data = {"article_id": article_id, "entries": []}
    else:
        data = {"article_id": article_id, "entries": []}

    data.setdefault("article_id", article_id)
    data.setdefault("entries", [])
    data["entries"].append(entry)
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _resolve_config(config: PipelineConfig | None) -> PipelineConfig:
    return config or get_config()


def _expected_model(stage: str, config: PipelineConfig) -> str | None:
    return config.stage_models.as_mapping().get(stage)


def _register_cost(
    *,
    stage: str,
    cost: float,
    config: PipelineConfig,
    article_id: str | None,
) -> None:
    global _RUN_COST_TOTAL
    _RUN_COST_TOTAL += cost

    if (
        config.max_cost_per_run is not None
        and _RUN_COST_TOTAL > config.max_cost_per_run
    ):
        raise RuntimeError(
            f"Run cost cap exceeded ({_RUN_COST_TOTAL:.4f} > {config.max_cost_per_run:.4f})"
        )

    if not article_id:
        return

    article_total = _ARTICLE_COSTS.get(article_id, 0.0) + cost
    _ARTICLE_COSTS[article_id] = article_total
    if (
        config.max_cost_per_article is not None
        and article_total > config.max_cost_per_article
    ):
        raise RuntimeError(
            "Article cost cap exceeded for "
            f"{article_id} ({article_total:.4f} > {config.max_cost_per_article:.4f})"
        )


def _build_entry(
    *,
    stage: str,
    model: str,
    call_type: str,
    cost: float,
    article_id: str | None,
    revision: int | None,
    context: dict[str, Any] | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "timestamp": _utc_now(),
        "stage": stage,
        "model": model,
        "call_type": call_type,
        "cost": cost,
        "run_id": _RUN_ID,
    }
    if article_id:
        entry["article_id"] = article_id
    if revision is not None:
        entry["revision"] = revision
    if context:
        entry["context"] = context
    entry.update(extra)
    return entry


def chat_completion(
    *,
    client: OpenAI,
    model: str,
    messages: list[dict[str, Any]],
    stage: str,
    config: PipelineConfig | None = None,
    article_id: str | None = None,
    revision: int | None = None,
    context: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    **kwargs: Any,
) -> ChatCompletion:
    """Call OpenAI chat completions with telemetry and governance."""

    if not model:
        raise ValueError("Model must be specified for chat completion")

    cfg = _resolve_config(config)
    expected = _expected_model(stage, cfg)
    if expected and expected != model:
        logger.warning("Stage %s expected model %s but got %s", stage, expected, model)

    response = create_chat_completion(
        client=client,
        model=model,
        messages=messages,
        **kwargs,
    )

    usage = getattr(response, "usage", None)
    prompt_tokens = _as_int(getattr(usage, "prompt_tokens", 0) if usage else 0)
    completion_tokens = _as_int(getattr(usage, "completion_tokens", 0) if usage else 0)
    total_tokens = _as_int(
        getattr(usage, "total_tokens", prompt_tokens + completion_tokens)
    )

    cost = estimate_text_cost(model, prompt_tokens or 0, completion_tokens or 0)
    _register_cost(stage=stage, cost=cost, config=cfg, article_id=article_id)

    entry = _build_entry(
        stage=stage,
        model=model,
        call_type="chat_completion",
        cost=cost,
        article_id=article_id,
        revision=revision,
        context=context,
        extra={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    )

    _append_json_entry(_MODEL_USAGE_FILE, entry, root_key="calls")
    if article_id:
        ledger_entry = entry.copy()
        if artifacts:
            ledger_entry["artifacts"] = artifacts
        _append_article_entry(article_id, ledger_entry)

    return response


def create_image(
    *,
    client: OpenAI,
    model: str,
    prompt: str,
    stage: str,
    config: PipelineConfig | None = None,
    article_id: str | None = None,
    revision: int | None = None,
    size: str = "1024x1024",
    quality: str = "standard",
    n: int = 1,
    context: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    **kwargs: Any,
):
    """Call OpenAI image generation with telemetry and governance."""

    if not model:
        raise ValueError("Model must be specified for image generation")

    cfg = _resolve_config(config)
    expected = _expected_model(stage, cfg)
    if expected and expected != model:
        logger.warning("Stage %s expected model %s but got %s", stage, expected, model)

    response = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,  # type: ignore[arg-type]
        quality=quality,  # type: ignore[arg-type]
        n=n,
        **kwargs,
    )

    cost = estimate_image_cost(model, size=size, quality=quality, count=n)
    _register_cost(stage=stage, cost=cost, config=cfg, article_id=article_id)

    entry = _build_entry(
        stage=stage,
        model=model,
        call_type="image_generation",
        cost=cost,
        article_id=article_id,
        revision=revision,
        context=context,
        extra={
            "size": size,
            "quality": quality,
            "count": n,
            "prompt_length": len(prompt),
        },
    )

    _append_json_entry(_MODEL_USAGE_FILE, entry, root_key="calls")
    if article_id:
        ledger_entry = entry.copy()
        if artifacts:
            ledger_entry["artifacts"] = artifacts
        _append_article_entry(article_id, ledger_entry)

    return response
