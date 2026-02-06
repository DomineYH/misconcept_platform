"""Configuration module for loading environment variables."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration from environment variables."""

    # OpenAI API Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # Supported: gpt-5 (Responses API with reasoning)
    # Recommended: gpt-5 (latest, Aug 2025)
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-5-mini")
    ANALYSIS_MODEL: str = os.getenv("ANALYSIS_MODEL", "gpt-5.2")
    # Model for dialogue similarity analysis
    DIALOGUE_ANALYSIS_MODEL: str = os.getenv(
        "DIALOGUE_ANALYSIS_MODEL", "gpt-5.2"
    )

    # ===== GPT-5 Reasoning Effort Configuration =====
    # Valid values: minimal, low, medium, high
    ANALYSIS_REASONING: str = os.getenv("ANALYSIS_REASONING", "high")
    STUDENT_REASONING: str = os.getenv("STUDENT_REASONING", "medium")
    TUTOR_REASONING: str = os.getenv("TUTOR_REASONING", "low")

    # ===== Bot Token Limits =====
    # Note: GPT-5 reasoning consumes tokens from max_output_tokens
    # Minimum recommended: 300 (reasoning) + 200 (actual output) = 500
    STUDENT_MAX_TOKENS: int = int(
        os.getenv("STUDENT_MAX_TOKENS", "750")
    )
    TUTOR_MAX_TOKENS: int = int(os.getenv("TUTOR_MAX_TOKENS", "1125"))
    TUTOR_INTERVENTION_THRESHOLD: int = int(
        os.getenv("TUTOR_INTERVENTION_THRESHOLD", "3")
    )

    # Session Security
    SESSION_SECRET: str = os.getenv(
        "SESSION_SECRET", "change-this-insecure-default"
    )

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./dialogue_sim.db"
    )

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # CORS - allowed frontend origins (comma-separated for multiple)
    # In production, this MUST be set to your actual frontend URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "")

    # Environment (T112: Security hardening)
    ENV: str = os.getenv("ENV", "development")  # development or production

    # Testing
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENV == "production"

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.OPENAI_API_KEY or cls.OPENAI_API_KEY.startswith(
            "sk-your"
        ):
            raise ValueError(
                "OPENAI_API_KEY must be set in .env file"
            )
        if cls.SESSION_SECRET == "change-this-insecure-default":
            raise ValueError(
                "SESSION_SECRET must be changed in .env file"
            )

        # Validate Reasoning Effort values
        # GPT-5: minimal, low, medium, high
        # GPT-5.1: none, low, medium, high
        valid_reasoning = ["none", "minimal", "low", "medium", "high"]
        if cls.ANALYSIS_REASONING not in valid_reasoning:
            raise ValueError(
                f"ANALYSIS_REASONING must be one of {valid_reasoning}, "
                f"got {cls.ANALYSIS_REASONING}"
            )
        if cls.STUDENT_REASONING not in valid_reasoning:
            raise ValueError(
                f"STUDENT_REASONING must be one of {valid_reasoning}, "
                f"got {cls.STUDENT_REASONING}"
            )
        if cls.TUTOR_REASONING not in valid_reasoning:
            raise ValueError(
                f"TUTOR_REASONING must be one of {valid_reasoning}, "
                f"got {cls.TUTOR_REASONING}"
            )

        # Validate Token Limits
        if cls.STUDENT_MAX_TOKENS <= 0:
            raise ValueError(
                f"STUDENT_MAX_TOKENS must be positive, "
                f"got {cls.STUDENT_MAX_TOKENS}"
            )
        if cls.TUTOR_MAX_TOKENS <= 0:
            raise ValueError(
                f"TUTOR_MAX_TOKENS must be positive, "
                f"got {cls.TUTOR_MAX_TOKENS}"
            )
        if not (1 <= cls.TUTOR_INTERVENTION_THRESHOLD <= 10):
            raise ValueError(
                f"TUTOR_INTERVENTION_THRESHOLD must be between 1 and "
                f"10, got {cls.TUTOR_INTERVENTION_THRESHOLD}"
            )


config = Config()
