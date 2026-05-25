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
    reload: bool = False
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

    @field_validator("debug", mode="before")
    @classmethod
    def validate_debug(cls, v) -> bool:
        """Convert debug environment values to boolean safely."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            normalized = v.lower().strip()
            return normalized in ("true", "1", "yes", "on", "debug")
        return bool(v)

    @field_validator("reload", mode="before")
    @classmethod
    def validate_reload(cls, v) -> bool:
        """Convert reload environment values to boolean safely."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            normalized = v.lower().strip()
            return normalized in ("true", "1", "yes", "on", "reload")
        return bool(v)

    credentials_file: str = "credentials.json"
    token_file: str = "token.json"
    ai_token_file: str = "ai_token.json"
    ai_classification_cache_file: str = "ai_classifications.json"

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

            self.ai_token_file = self._resolve_data_file_path(
                self.ai_token_file, "ai_token.json", base_dir
            )
            self.ai_classification_cache_file = self._resolve_data_file_path(
                self.ai_classification_cache_file,
                "ai_classifications.json",
                base_dir,
            )

    def _resolve_data_file_path(
        self, file_path: str, fallback_name: str, base_dir: str
    ) -> str:
        """Resolve a data file path safely inside the Docker data directory."""
        if os.path.isabs(file_path):
            resolved_path = os.path.abspath(os.path.realpath(file_path))
        else:
            resolved_path = os.path.abspath(
                os.path.realpath(os.path.join(base_dir, file_path))
            )

        if (
            not resolved_path.startswith(base_dir + os.sep)
            or resolved_path == base_dir
            or os.path.isdir(resolved_path)
        ):
            name = os.path.basename(file_path)
            if name in ("", "."):
                name = fallback_name
            return os.path.join(base_dir, name)

        return resolved_path

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
