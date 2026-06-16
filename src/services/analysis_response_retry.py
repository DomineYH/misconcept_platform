from __future__ import annotations

import logging
from typing import Protocol, TypeAlias

from src.services.analysis_response_schemas import TextFormat
from src.utils.openai_helpers import (
    IncompleteResponseError,
    extract_response_text,
    extract_usage_dict,
)

logger = logging.getLogger(__name__)

InputMessages: TypeAlias = list[dict[str, str]]


class ResponsePayload(Protocol):
    status: str | None


class ResponsesResource(Protocol):
    async def create(
        self,
        *,
        model: str,
        input: InputMessages,
        max_output_tokens: int,
        reasoning: dict[str, str],
        text: TextFormat,
    ) -> ResponsePayload:
        raise NotImplementedError


def _merge_usage_dicts(
    *usages: dict[str, int] | None,
) -> dict[str, int] | None:
    merged: dict[str, int] = {}
    for usage in usages:
        if usage is None:
            continue
        for key, value in usage.items():
            if isinstance(value, int):
                merged[key] = merged.get(key, 0) + value
    return merged or None


async def create_response_text_with_incomplete_retry(
    *,
    responses: ResponsesResource,
    model: str,
    input_messages: InputMessages,
    text_format: TextFormat,
    operation: str,
    max_output_tokens: int,
    retry_max_output_tokens: int,
    reasoning_effort: str,
) -> tuple[str, dict[str, int] | None]:
    response = await responses.create(
        model=model,
        input=input_messages,
        max_output_tokens=max_output_tokens,
        reasoning={"effort": reasoning_effort},
        text=text_format,
    )
    usage = extract_usage_dict(response)
    try:
        return extract_response_text(response), usage
    except IncompleteResponseError as exc:
        reasoning_tokens = usage.get("reasoning_tokens") if usage else None
        logger.warning(
            "%s response incomplete; reason=%s max_output_tokens=%d "
            "reasoning_effort=%s reasoning_tokens=%s. Retrying with "
            "max_output_tokens=%d.",
            operation,
            exc.reason,
            max_output_tokens,
            reasoning_effort,
            reasoning_tokens,
            retry_max_output_tokens,
        )

    retry_response = await responses.create(
        model=model,
        input=input_messages,
        max_output_tokens=retry_max_output_tokens,
        reasoning={"effort": reasoning_effort},
        text=text_format,
    )
    retry_usage = extract_usage_dict(retry_response)
    content = extract_response_text(retry_response)
    return content, _merge_usage_dicts(usage, retry_usage)
