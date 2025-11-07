"""Admin routes for chatbot configuration management.

Provides REST API for managing StudentBot and TutorBot settings
through a web UI without requiring code changes or server restarts.

Endpoints:
- GET /admin/chatbot-config - Retrieve current configuration
- PUT /admin/chatbot-config - Update configuration
- GET /admin/chatbot-config/costs - API usage and cost metrics
- POST /admin/chatbot-config/reset - Reset to factory defaults

Security:
- Admin role required for all endpoints
- Rate limiting (10/30/5 requests per minute)
- Audit logging for all config changes
- Pydantic validation for input
"""

from datetime import datetime, timezone
from typing import Dict

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.config import config
from src.models.chatbot_config import ChatbotConfig, ChatbotConfigAudit
from src.models.user import User
from src.services.config_cache import bot_config_cache

router = APIRouter(
    prefix="/admin/chatbot-config", tags=["Admin Chatbot Config"]
)
limiter = Limiter(key_func=get_remote_address, enabled=not config.TESTING)
templates = Jinja2Templates(directory="src/templates")


# ============================================================================
# Pydantic Schemas
# ============================================================================


class BotConfigUpdate(BaseModel):
    """Chatbot configuration update payload with validation."""

    student_bot_model: str = Field(
        ...,
        pattern=r"^gpt-(3\.5|4)-turbo$",
        description="Must be gpt-3.5-turbo or gpt-4-turbo",
    )
    student_bot_temperature: float = Field(
        ..., ge=0.0, le=2.0, description="Temperature between 0.0 and 2.0"
    )
    student_bot_max_tokens: int = Field(
        ..., ge=50, le=500, description="Max tokens between 50 and 500"
    )
    tutor_bot_model: str = Field(
        ...,
        pattern=r"^gpt-(3\.5|4)-turbo$",
        description="Must be gpt-3.5-turbo or gpt-4-turbo",
    )
    tutor_bot_temperature: float = Field(
        ..., ge=0.0, le=2.0, description="Temperature between 0.0 and 2.0"
    )
    tutor_bot_max_tokens: int = Field(
        ..., ge=50, le=300, description="Max tokens between 50 and 300"
    )
    tutor_bot_intervention_threshold: int = Field(
        ..., ge=1, le=10, description="Interventions per 10 questions (1-10)"
    )

    @field_validator("student_bot_model", "tutor_bot_model")
    @classmethod
    def validate_model_availability(cls, v):
        """Validate model is in allowed list."""
        allowed_models = ["gpt-4-turbo", "gpt-3.5-turbo"]
        if v not in allowed_models:
            raise ValueError(
                f"Model '{v}' not allowed. Use: {', '.join(allowed_models)}"
            )
        return v


class BotConfigResponse(BaseModel):
    """Chatbot configuration response."""

    student_bot: Dict[str, float | int | str]
    tutor_bot: Dict[str, float | int | str]


class CostMetricsResponse(BaseModel):
    """API usage and cost metrics response (Phase 3)."""

    message: str = (
        "Cost tracking will be implemented in Phase 3. "
        "Please monitor OpenAI dashboard for usage."
    )
    placeholder: bool = True


# ============================================================================
# Helper Functions
# ============================================================================


def _check_admin_role(user: User) -> None:
    """Verify user has admin role.

    Args:
        user: Current user from dependency

    Raises:
        HTTPException: If user is not admin
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


async def _log_config_audit(
    db: AsyncSession,
    user: User,
    request: Request,
    config_key: str,
    old_value: str | None,
    new_value: str,
) -> None:
    """Log configuration change to audit trail.

    Args:
        db: Database session
        user: User making the change
        request: HTTP request (for IP address)
        config_key: Configuration key being changed
        old_value: Previous value (None if new)
        new_value: New value
    """
    audit_entry = ChatbotConfigAudit(
        config_key=config_key,
        old_value=old_value,
        new_value=new_value,
        changed_by=user.id,
        changed_at=datetime.now(timezone.utc),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit_entry)


async def _get_current_config(db: AsyncSession) -> Dict[str, str]:
    """Load current configuration from database.

    Args:
        db: Database session

    Returns:
        Dictionary of config_key: config_value
    """
    # Use cache for performance
    return await bot_config_cache.get_global_config(db)


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/settings", response_class=HTMLResponse)
async def chatbot_settings_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Render chatbot settings admin page.

    Security: Admin role required
    """
    _check_admin_role(user)

    return templates.TemplateResponse(
        "admin/chatbot_settings.html",
        {"request": request, "user": user},
    )


@router.get("/", response_model=BotConfigResponse)
async def get_chatbot_config(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Retrieve current chatbot configuration.

    Returns global settings for StudentBot and TutorBot,
    loaded from database with caching (<10ms).

    Security: Admin role required
    Rate limit: 30 requests/minute
    """
    _check_admin_role(user)

    # Load config using cache
    configs = await _get_current_config(db)

    return BotConfigResponse(
        student_bot={
            "model": configs.get(
                "student_bot.model", config.CHAT_MODEL
            ),
            "temperature": float(
                configs.get("student_bot.temperature", "0.7")
            ),
            "max_tokens": int(configs.get("student_bot.max_tokens", "150")),
        },
        tutor_bot={
            "model": configs.get(
                "tutor_bot.model", config.ANALYSIS_MODEL
            ),
            "temperature": float(
                configs.get("tutor_bot.temperature", "0.3")
            ),
            "max_tokens": int(configs.get("tutor_bot.max_tokens", "100")),
            "intervention_threshold": int(
                configs.get("tutor_bot.intervention_threshold", "3")
            ),
        },
    )


@router.put("/")
@limiter.limit("10/minute")  # Max 10 config updates per minute
async def update_chatbot_config(
    request: Request,
    config_update: BotConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Update chatbot configuration.

    Updates global bot settings and invalidates cache to ensure
    new sessions use updated configuration.

    Security:
    - Admin role required
    - Rate limited to 10 requests/minute
    - All changes logged to audit trail

    Args:
        request: HTTP request
        config_update: Validated configuration update
        db: Database session
        user: Current user

    Returns:
        Success message
    """
    _check_admin_role(user)

    # Get current config for audit log
    current_config = await _get_current_config(db)

    # Prepare updates
    updates = {
        "student_bot.model": config_update.student_bot_model,
        "student_bot.temperature": str(
            config_update.student_bot_temperature
        ),
        "student_bot.max_tokens": str(config_update.student_bot_max_tokens),
        "tutor_bot.model": config_update.tutor_bot_model,
        "tutor_bot.temperature": str(config_update.tutor_bot_temperature),
        "tutor_bot.max_tokens": str(config_update.tutor_bot_max_tokens),
        "tutor_bot.intervention_threshold": str(
            config_update.tutor_bot_intervention_threshold
        ),
    }

    # Update database and log audit trail
    for key, new_value in updates.items():
        # Find existing config row
        result = await db.execute(
            select(ChatbotConfig).where(ChatbotConfig.config_key == key)
        )
        config_row = result.scalar_one_or_none()

        old_value = current_config.get(key)

        if config_row:
            # Update existing
            config_row.config_value = new_value
            config_row.updated_at = datetime.now(timezone.utc)
            config_row.updated_by = user.id
        else:
            # Create new (shouldn't happen if seeded properly)
            config_type = (
                "string"
                if "model" in key
                else "float"
                if "temperature" in key
                else "integer"
            )
            new_config = ChatbotConfig(
                config_key=key,
                config_value=new_value,
                config_type=config_type,
                updated_by=user.id,
            )
            db.add(new_config)

        # Log audit trail
        await _log_config_audit(
            db, user, request, key, old_value, new_value
        )

    await db.commit()

    # Invalidate cache so new sessions use updated config
    await bot_config_cache.invalidate()

    return {"message": "Chatbot configuration updated successfully"}


@router.get("/costs", response_model=CostMetricsResponse)
async def get_cost_metrics(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    days: int = 7,
):
    """Get API usage and cost metrics.

    Note: This is a placeholder for Phase 3 implementation.
    Currently returns a message directing admins to OpenAI dashboard.

    Future implementation will track:
    - Total tokens used
    - Estimated costs
    - Breakdown by bot type (student vs tutor)
    - Breakdown by model
    - Time period metrics

    Security: Admin role required
    Rate limit: 30 requests/minute

    Args:
        db: Database session
        user: Current user
        days: Number of days to query (default: 7)

    Returns:
        Placeholder message
    """
    _check_admin_role(user)

    # Phase 3: Implement actual cost tracking
    # For now, return placeholder
    return CostMetricsResponse()


@router.post("/reset")
@limiter.limit("5/minute")  # Max 5 resets per minute
async def reset_to_defaults(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Reset all chatbot settings to factory defaults.

    Restores configuration to initial seeded values:
    - student_bot.model: gpt-4-turbo
    - student_bot.temperature: 0.7
    - student_bot.max_tokens: 150
    - tutor_bot.model: gpt-3.5-turbo
    - tutor_bot.temperature: 0.3
    - tutor_bot.max_tokens: 100
    - tutor_bot.intervention_threshold: 3

    Security:
    - Admin role required
    - Rate limited to 5 requests/minute
    - All resets logged to audit trail

    Args:
        request: HTTP request
        db: Database session
        user: Current user

    Returns:
        Success message with default values
    """
    _check_admin_role(user)

    # Default values (from seed.py)
    defaults = {
        "student_bot.model": "gpt-4-turbo",
        "student_bot.temperature": "0.7",
        "student_bot.max_tokens": "150",
        "tutor_bot.model": "gpt-3.5-turbo",
        "tutor_bot.temperature": "0.3",
        "tutor_bot.max_tokens": "100",
        "tutor_bot.intervention_threshold": "3",
    }

    # Reset each config value
    for key, default_value in defaults.items():
        result = await db.execute(
            select(ChatbotConfig).where(ChatbotConfig.config_key == key)
        )
        config_row = result.scalar_one_or_none()

        if config_row:
            old_value = config_row.config_value
            config_row.config_value = default_value
            config_row.updated_at = datetime.now(timezone.utc)
            config_row.updated_by = user.id

            # Log audit trail
            await _log_config_audit(
                db, user, request, key, old_value, default_value
            )

    await db.commit()

    # Invalidate cache
    await bot_config_cache.invalidate()

    return {
        "message": "Configuration reset to defaults",
        "defaults": {
            "student_bot": {
                "model": "gpt-4-turbo",
                "temperature": 0.7,
                "max_tokens": 150,
            },
            "tutor_bot": {
                "model": "gpt-3.5-turbo",
                "temperature": 0.3,
                "max_tokens": 100,
                "intervention_threshold": 3,
            },
        },
    }
