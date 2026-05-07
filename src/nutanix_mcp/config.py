"""Configuration management for the Nutanix MCP server."""

import base64
import sys
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables.

    All settings are prefixed with NUTANIX_ in environment variables.
    Example: NUTANIX_HOST, NUTANIX_USERNAME, etc.
    """

    model_config = SettingsConfigDict(
        env_prefix="NUTANIX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(
        default="prism-central.example.com",
        description="Prism Central hostname or IP",
    )
    port: int = Field(default=9440, description="Prism Central API port")
    username: Optional[str] = Field(default=None, description="Username for basic auth")
    password: Optional[str] = Field(default=None, description="Password for basic auth")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    timeout: int = Field(default=30, description="Request timeout in seconds")

    @field_validator("host", mode="before")
    @classmethod
    def validate_host(cls, v: Optional[str]) -> str:
        if not v:
            raise ValueError(
                "NUTANIX_HOST is required. "
                "Set it as an environment variable or in a .env file."
            )
        return v

    @property
    def base_url(self) -> str:
        """Base URL for Prism Central API requests."""
        return f"https://{self.host}:{self.port}/api"

    @property
    def has_credentials(self) -> bool:
        """Check if valid credentials are configured."""
        return bool(self.username and self.password)

    def get_auth_header(self) -> dict[str, str]:
        """Build the authorization header."""
        if self.username and self.password:
            credentials = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            return {"Authorization": f"Basic {credentials}"}
        raise ValueError(
            "No credentials configured. Set NUTANIX_USERNAME and NUTANIX_PASSWORD."
        )


def get_settings() -> Settings:
    """Load and validate settings."""
    try:
        return Settings()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
