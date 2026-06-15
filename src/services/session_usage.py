import logging
from collections.abc import Callable, Mapping
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ApiUsageLog, calculate_cost
from src.services.session_lifecycle import (
    StaleSessionError,
    ensure_session_writable,
    flush_with_stale_session_check,
)

logger = logging.getLogger(__name__)

BotType = Literal["student", "tutor"]
UsageData = Mapping[str, int]
CostCalculator = Callable[[str, int, int], float]


async def log_api_usage(
    db: AsyncSession,
    session_id: int,
    bot_type: BotType,
    model: str,
    usage_dict: UsageData | None,
    cost_calculator: CostCalculator = calculate_cost,
) -> None:
    if usage_dict is None:
        logger.warning("No usage info for %s bot (model: %s)", bot_type, model)
        return

    await ensure_session_writable(db, session_id)

    try:
        prompt_tokens = usage_dict["prompt_tokens"]
        completion_tokens = usage_dict["completion_tokens"]
        total_tokens = usage_dict["total_tokens"]
        cost = cost_calculator(model, prompt_tokens, completion_tokens)

        log_entry = ApiUsageLog(
            session_id=session_id,
            bot_type=bot_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
        )

        db.add(log_entry)
        await flush_with_stale_session_check(db, session_id)

        logger.debug(
            "API usage logged: %s bot, %s tokens, $%.6f",
            bot_type,
            total_tokens,
            cost,
        )
    except StaleSessionError:
        raise
    except IntegrityError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to log API usage for %s bot: %s", bot_type, str(exc)
        )
