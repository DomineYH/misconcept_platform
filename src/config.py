"""Configuration module for loading environment variables."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration from environment variables."""

    # OpenAI API Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4-turbo")
    ANALYSIS_MODEL: str = os.getenv(
        "ANALYSIS_MODEL", "gpt-3.5-turbo"
    )

    # ===== Chatbot Parameter Configuration =====
    # StudentBot settings
    STUDENT_TEMPERATURE: float = float(
        os.getenv("STUDENT_TEMPERATURE", "0.7")
    )
    STUDENT_MAX_TOKENS: int = int(
        os.getenv("STUDENT_MAX_TOKENS", "150")
    )

    # TutorBot settings
    TUTOR_TEMPERATURE: float = float(
        os.getenv("TUTOR_TEMPERATURE", "0.3")
    )
    TUTOR_MAX_TOKENS: int = int(os.getenv("TUTOR_MAX_TOKENS", "100"))
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

        # Validate StudentBot parameters
        if not (0.0 <= cls.STUDENT_TEMPERATURE <= 2.0):
            raise ValueError(
                f"STUDENT_TEMPERATURE must be between 0.0 and 2.0, "
                f"got {cls.STUDENT_TEMPERATURE}"
            )
        if cls.STUDENT_MAX_TOKENS <= 0:
            raise ValueError(
                f"STUDENT_MAX_TOKENS must be positive, "
                f"got {cls.STUDENT_MAX_TOKENS}"
            )

        # Validate TutorBot parameters
        if not (0.0 <= cls.TUTOR_TEMPERATURE <= 2.0):
            raise ValueError(
                f"TUTOR_TEMPERATURE must be between 0.0 and 2.0, "
                f"got {cls.TUTOR_TEMPERATURE}"
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
