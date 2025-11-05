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


config = Config()
