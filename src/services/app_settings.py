"""Global application settings service.

A row's absence is treated as the default value, so adding a new
setting never requires a data migration.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.app_setting import AppSetting

# Key for the analysis synthesis on/off toggle (Issue #55).
SYNTHESIS_ENABLED_KEY = "analysis_synthesis_enabled"


async def is_synthesis_enabled(db: AsyncSession) -> bool:
    """Return True when synthesis is enabled.

    Defaults to True when no row exists yet (toggle ON by default).
    Parses the stored value case-insensitively as "true"/"false".
    """
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == SYNTHESIS_ENABLED_KEY)
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        return True
    return setting.value.strip().lower() == "true"


async def set_synthesis_enabled(db: AsyncSession, enabled: bool) -> None:
    """Upsert the analysis_synthesis_enabled setting."""
    value = "true" if enabled else "false"
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == SYNTHESIS_ENABLED_KEY)
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        db.add(AppSetting(key=SYNTHESIS_ENABLED_KEY, value=value))
    else:
        setting.value = value
    await db.commit()
