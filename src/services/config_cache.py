"""Configuration caching system for chatbot settings.

This module provides in-memory caching for chatbot configuration
to achieve <10ms load times and reduce database queries.

Features:
- 5-minute TTL (time-to-live)
- Manual cache invalidation on config updates
- Thread-safe implementation
- Performance target: <10ms
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.chatbot_config import ChatbotConfig


class BotConfigCache:
    """In-memory cache for bot configuration with TTL and invalidation."""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize config cache.

        Args:
            ttl_seconds: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: Dict[str, Tuple[dict, datetime]] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    async def get_global_config(self, db: AsyncSession) -> dict:
        """Get global bot config with caching.

        Performance target: <10ms (cache hit), <50ms (cache miss)

        Args:
            db: Database session

        Returns:
            Dictionary of config key-value pairs
        """
        cache_key = "global_config"

        # Thread-safe cache access
        async with self._lock:
            # Check cache
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if datetime.now(timezone.utc) - timestamp < timedelta(
                    seconds=self._ttl
                ):
                    return cached_data

        # Cache miss - load from DB
        result = await db.execute(select(ChatbotConfig))
        configs = {
            row.config_key: row.config_value
            for row in result.scalars().all()
        }

        # Update cache
        async with self._lock:
            self._cache[cache_key] = (configs, datetime.now(timezone.utc))

        return configs

    async def invalidate(self) -> None:
        """Clear cache when configuration is updated.

        Called after PUT /admin/chatbot-config to ensure
        new sessions use updated configuration.
        """
        async with self._lock:
            self._cache.clear()

    async def get_scenario_config(
        self, db: AsyncSession, scenario_id: int
    ) -> Optional[dict]:
        """Get scenario-specific config with caching (Phase 2).

        Args:
            db: Database session
            scenario_id: Scenario ID

        Returns:
            Scenario config overrides or None
        """
        cache_key = f"scenario_config_{scenario_id}"

        # Check cache
        async with self._lock:
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if datetime.now(timezone.utc) - timestamp < timedelta(
                    seconds=self._ttl
                ):
                    return cached_data

        # Note: Phase 2 implementation will load scenario overrides here
        return None

    async def invalidate_scenario(self, scenario_id: int) -> None:
        """Invalidate cache for specific scenario (Phase 2).

        Args:
            scenario_id: Scenario ID to invalidate
        """
        cache_key = f"scenario_config_{scenario_id}"
        async with self._lock:
            self._cache.pop(cache_key, None)


# Global cache instance (singleton pattern)
bot_config_cache = BotConfigCache()
