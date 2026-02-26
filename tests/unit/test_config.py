"""Unit tests for Config validation."""

import pytest
from unittest.mock import patch


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
