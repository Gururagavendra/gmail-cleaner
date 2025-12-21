"""
Application Configuration
-------------------------
Central configuration and settings for the application.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    app_name: str = "Gmail Cleaner"
    app_version: str = "1.0.0"
    debug: bool = False
    port: int = 8766
    oauth_port: int = 8767
    oauth_external_port: int | None = Field(
        default=None,
        description="External port for OAuth redirect URI (when different from oauth_port, e.g., Docker port mapping)",
    )

    # Auth
    web_auth: bool = Field(
        default=False,
        description="Enable web-based authentication mode",
    )
    oauth_host: str = Field(
        default="localhost",
        description="Custom host for OAuth redirect (e.g., your domain or IP)",
    )

    @field_validator("web_auth", mode="before")
    @classmethod
    def validate_web_auth(cls, v) -> bool:
        """Convert string environment variable to boolean (case-insensitive)."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            normalized = v.lower().strip()
            return normalized in ("true", "1", "yes", "on")
        return bool(v)

    credentials_file: str = "credentials.json"
    token_file: str = "token.json"

    # Gmail API
    scopes: list[str] = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
