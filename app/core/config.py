"""
Application Configuration
-------------------------
Central configuration and settings for the application.
"""

import os
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
    oauth_use_https: bool | None = Field(
        default=None,
        description="Force HTTPS (True) or HTTP (False) for OAuth redirect. "
        "When None, automatically uses HTTP for localhost/Docker hosts, HTTPS otherwise.",
    )

    @field_validator("oauth_use_https", mode="before")
    @classmethod
    def validate_oauth_use_https(cls, v) -> bool | None:
        """Convert string environment variable to boolean or None."""
        if v is None or v == "":
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            normalized = v.lower().strip()
            if normalized in ("true", "1", "yes", "on"):
                return True
            if normalized in ("false", "0", "no", "off"):
                return False
            raise ValueError(
                f"Invalid value '{v}' for oauth_use_https. "
                "Expected one of: true, 1, yes, on, false, 0, no, off, or empty to unset."
            )
        raise ValueError(
            f"Invalid type for oauth_use_https: {type(v).__name__}. "
            "Expected bool, string, or None."
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

    def __init__(self, **kwargs):
        """Initialize settings and auto-detect data directory for token persistence."""
        super().__init__(**kwargs)
        # Auto-detect /app/data directory in Docker and use it for token_file
        # This allows token.json to persist across container restarts
        if os.path.exists("/app/data") and os.path.isdir("/app/data"):
            # Normalize the base directory path
            base_dir = os.path.abspath(os.path.realpath("/app/data"))

            if os.path.isabs(self.token_file):
                # If token_file is absolute, verify it's within /app/data
                resolved_path = os.path.abspath(os.path.realpath(self.token_file))
                # Unsafe conditions: path traversal, points to base_dir, or is a directory
                if (
                    not resolved_path.startswith(base_dir + os.sep)
                    or resolved_path == base_dir
                    or os.path.isdir(resolved_path)
                ):
                    # Absolute path unsafe - use safe fallback
                    name = os.path.basename(self.token_file)
                    if name in ("", "."):
                        name = "token.json"
                    self.token_file = os.path.join(base_dir, name)
                else:
                    # Valid absolute path within /app/data (file, not directory)
                    self.token_file = resolved_path
            else:
                # Relative path - join and validate
                candidate_path = os.path.join(base_dir, self.token_file)
                resolved_path = os.path.abspath(os.path.realpath(candidate_path))

                # Verify resolved path is within base_dir and is a file (prevents path traversal)
                # Unsafe conditions: path traversal, points to base_dir, or is a directory
                if (
                    not resolved_path.startswith(base_dir + os.sep)
                    or resolved_path == base_dir
                    or os.path.isdir(resolved_path)
                ):
                    # Path traversal detected or directory path - use safe fallback with basename only
                    name = os.path.basename(self.token_file)
                    if name in ("", "."):
                        name = "token.json"
                    self.token_file = os.path.join(base_dir, name)
                else:
                    # Safe path - use resolved path (file, not directory)
                    self.token_file = resolved_path

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
