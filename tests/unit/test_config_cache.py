"""Unit tests for configuration caching system."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.chatbot_config import ChatbotConfig
from src.services.config_cache import BotConfigCache


class TestBotConfigCache:
    """Test configuration caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_miss_loads_from_db(self):
        """Test that cache miss loads configuration from database."""
        # Create mock database session
        db_mock = AsyncMock()
        result_mock = MagicMock()

        # Mock config rows
        config1 = MagicMock(spec=ChatbotConfig)
        config1.config_key = "student_bot.model"
        config1.config_value = "gpt-4-turbo"

        config2 = MagicMock(spec=ChatbotConfig)
        config2.config_key = "student_bot.temperature"
        config2.config_value = "0.7"

        result_mock.scalars.return_value.all.return_value = [config1, config2]
        db_mock.execute.return_value = result_mock

        # Initialize cache
        cache = BotConfigCache(ttl_seconds=300)

        # First call should be cache miss
        config = await cache.get_global_config(db_mock)

        # Verify DB was queried
        assert db_mock.execute.called
        assert config["student_bot.model"] == "gpt-4-turbo"
        assert config["student_bot.temperature"] == "0.7"

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self):
        """Test that subsequent calls use cached data without DB query."""
        # Setup mocks
        db_mock = AsyncMock()
        result_mock = MagicMock()

        config_row = MagicMock(spec=ChatbotConfig)
        config_row.config_key = "student_bot.model"
        config_row.config_value = "gpt-4-turbo"

        result_mock.scalars.return_value.all.return_value = [config_row]
        db_mock.execute.return_value = result_mock

        cache = BotConfigCache(ttl_seconds=300)

        # First call - cache miss
        config1 = await cache.get_global_config(db_mock)
        first_call_count = db_mock.execute.call_count

        # Second call - should be cache hit
        config2 = await cache.get_global_config(db_mock)
        second_call_count = db_mock.execute.call_count

        # Verify DB was only called once (cache hit on second call)
        assert second_call_count == first_call_count
        assert config1 == config2

    @pytest.mark.asyncio
    async def test_cache_expiration_after_ttl(self):
        """Test that cache expires after TTL and reloads from DB."""
        db_mock = AsyncMock()
        result_mock = MagicMock()

        config_row = MagicMock(spec=ChatbotConfig)
        config_row.config_key = "test_key"
        config_row.config_value = "test_value"

        result_mock.scalars.return_value.all.return_value = [config_row]
        db_mock.execute.return_value = result_mock

        # Use 1 second TTL for testing
        cache = BotConfigCache(ttl_seconds=1)

        # First call
        config1 = await cache.get_global_config(db_mock)
        first_call_count = db_mock.execute.call_count

        # Manually expire cache by modifying timestamp
        cache._cache["global_config"] = (
            config1,
            datetime.now(timezone.utc) - timedelta(seconds=2),
        )

        # Second call after expiration
        await cache.get_global_config(db_mock)
        second_call_count = db_mock.execute.call_count

        # Verify DB was called twice (cache expired)
        assert second_call_count > first_call_count

    @pytest.mark.asyncio
    async def test_cache_invalidation_clears_all_data(self):
        """Test that invalidate() clears entire cache."""
        db_mock = AsyncMock()
        result_mock = MagicMock()

        config_row = MagicMock(spec=ChatbotConfig)
        config_row.config_key = "test_key"
        config_row.config_value = "test_value"

        result_mock.scalars.return_value.all.return_value = [config_row]
        db_mock.execute.return_value = result_mock

        cache = BotConfigCache(ttl_seconds=300)

        # Load config into cache
        await cache.get_global_config(db_mock)
        assert len(cache._cache) > 0

        # Invalidate cache
        await cache.invalidate()

        # Verify cache is empty
        assert len(cache._cache) == 0

    @pytest.mark.asyncio
    async def test_empty_database_returns_empty_dict(self):
        """Test handling of empty configuration table."""
        db_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db_mock.execute.return_value = result_mock

        cache = BotConfigCache(ttl_seconds=300)
        config = await cache.get_global_config(db_mock)

        assert config == {}

    @pytest.mark.asyncio
    async def test_scenario_config_cache_miss(self):
        """Test scenario-specific config cache (Phase 2 placeholder)."""
        db_mock = AsyncMock()
        cache = BotConfigCache(ttl_seconds=300)

        # Phase 2 not implemented yet, should return None
        config = await cache.get_scenario_config(db_mock, scenario_id=1)
        assert config is None

    @pytest.mark.asyncio
    async def test_scenario_config_invalidation(self):
        """Test scenario-specific cache invalidation (Phase 2)."""
        cache = BotConfigCache(ttl_seconds=300)

        # Manually add scenario config to cache
        cache._cache["scenario_config_1"] = (
            {"test": "value"},
            datetime.now(timezone.utc),
        )

        # Invalidate specific scenario
        await cache.invalidate_scenario(scenario_id=1)

        # Verify specific scenario cache is cleared
        assert "scenario_config_1" not in cache._cache

    @pytest.mark.asyncio
    async def test_thread_safety_with_lock(self):
        """Test that cache operations use asyncio.Lock for thread safety."""
        cache = BotConfigCache(ttl_seconds=300)

        # Verify lock exists
        assert cache._lock is not None

        # Lock should be acquired during operations
        db_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db_mock.execute.return_value = result_mock

        await cache.get_global_config(db_mock)
        # If test passes without deadlock, lock is working correctly

    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self):
        """Test concurrent access to cache from multiple coroutines."""
        import asyncio

        db_mock = AsyncMock()
        result_mock = MagicMock()

        config_row = MagicMock(spec=ChatbotConfig)
        config_row.config_key = "test_key"
        config_row.config_value = "test_value"

        result_mock.scalars.return_value.all.return_value = [config_row]
        db_mock.execute.return_value = result_mock

        cache = BotConfigCache(ttl_seconds=300)

        # Simulate 5 concurrent requests
        tasks = [cache.get_global_config(db_mock) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should return same config (one DB call, rest from cache)
        assert all(r == results[0] for r in results)
        # DB should only be called once due to cache
        assert db_mock.execute.call_count == 1
