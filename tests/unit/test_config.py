"""Unit tests for Config validation."""

from unittest.mock import patch

import pytest


class TestConfigContextWindow:
    """Tests for CONTEXT_WINDOW_TURNS validation."""

    def test_default_value(self):
        """Should default to 20."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
            },
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()
            assert c.CONTEXT_WINDOW_TURNS == 20

    def test_valid_range(self):
        """Should accept values between 4 and 200."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "CONTEXT_WINDOW_TURNS": "50",
            },
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()
            assert c.CONTEXT_WINDOW_TURNS == 50

    def test_rejects_too_small(self):
        """Should reject values below 4."""
        from importlib import reload

        import src.config

        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "CONTEXT_WINDOW_TURNS": "2",
            },
        ):
            with pytest.raises(Exception):
                reload(src.config)

    def test_rejects_too_large(self):
        """Should reject values above 200."""
        from importlib import reload

        import src.config

        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "CONTEXT_WINDOW_TURNS": "300",
            },
        ):
            with pytest.raises(Exception):
                reload(src.config)


class TestConfigModelValidation:
    """Tests for model name validation."""

    def test_accepts_gpt5_models(self):
        """Should accept gpt-5 family models."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "CHAT_MODEL": "gpt-5",
            },
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()
            assert c.CHAT_MODEL == "gpt-5"

    def test_accepts_gpt4_models(self):
        """Should accept gpt-4 family models."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "CHAT_MODEL": "gpt-4-turbo",
            },
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()
            assert c.CHAT_MODEL == "gpt-4-turbo"

    def test_rejects_invalid_model(self):
        """Should reject non gpt-4/gpt-5 models."""
        from importlib import reload

        import src.config

        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "CHAT_MODEL": "claude-3-opus",
            },
        ):
            with pytest.raises(Exception):
                reload(src.config)

    def test_validate_method_is_noop(self):
        """validate() should not raise for valid config."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
            },
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()
            c.validate()  # Should not raise


class TestAnalysisLLMConfig:
    """Tests for issue #47 analysis-specific LLM settings."""

    def test_analysis_llm_defaults_are_split(self):
        """Classification/greeting/synthesis should not share one setting."""
        with patch.dict(
            "os.environ",
            {
                "TESTING": "true",
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
            },
            clear=True,
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()

            assert c.ANALYSIS_REASONING == "high"
            assert c.ANALYSIS_CLASSIFICATION_REASONING == "low"
            assert c.ANALYSIS_GREETING_REASONING == "low"
            assert c.ANALYSIS_SYNTHESIS_REASONING == "high"
            assert c.ANALYSIS_CLASSIFICATION_MAX_TOKENS == 2500
            assert c.ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS == 4000
            assert c.ANALYSIS_GREETING_MAX_TOKENS == 1000
            assert c.ANALYSIS_GREETING_RETRY_MAX_TOKENS == 1500

    def test_analysis_llm_settings_can_be_overridden(self):
        """New env vars should override only their matching operation."""
        with patch.dict(
            "os.environ",
            {
                "TESTING": "true",
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "ANALYSIS_REASONING": "high",
                "ANALYSIS_CLASSIFICATION_REASONING": "minimal",
                "ANALYSIS_GREETING_REASONING": "none",
                "ANALYSIS_SYNTHESIS_REASONING": "medium",
                "ANALYSIS_CLASSIFICATION_MAX_TOKENS": "3000",
                "ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS": "5000",
                "ANALYSIS_GREETING_MAX_TOKENS": "900",
                "ANALYSIS_GREETING_RETRY_MAX_TOKENS": "1800",
            },
            clear=True,
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()

            assert c.ANALYSIS_REASONING == "high"
            assert c.ANALYSIS_CLASSIFICATION_REASONING == "minimal"
            assert c.ANALYSIS_GREETING_REASONING == "none"
            assert c.ANALYSIS_SYNTHESIS_REASONING == "medium"
            assert c.ANALYSIS_CLASSIFICATION_MAX_TOKENS == 3000
            assert c.ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS == 5000
            assert c.ANALYSIS_GREETING_MAX_TOKENS == 900
            assert c.ANALYSIS_GREETING_RETRY_MAX_TOKENS == 1800

    def test_analysis_token_limits_must_be_positive(self):
        """New analysis token budgets should reject zero and negative values."""
        from importlib import reload

        import src.config

        with patch.dict(
            "os.environ",
            {
                "TESTING": "true",
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "ANALYSIS_CLASSIFICATION_MAX_TOKENS": "0",
            },
            clear=True,
        ):
            with pytest.raises(Exception):
                reload(src.config)
