"""Configuration management for the Nutanix MCP server."""

import base64
import re
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
        description="Prism Central hostname or IP (required — set NUTANIX_HOST)",
    )
    port: int = Field(default=9440, description="Prism Central API port")
    username: Optional[str] = Field(default=None, description="Username for basic auth")
    password: Optional[str] = Field(default=None, description="Password for basic auth")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    timeout: int = Field(default=30, description="Request timeout in seconds")

    # Security: restrict which PE hosts can be targeted
    allowed_pe_hosts: list[str] = Field(
        default_factory=list,
        description=(
            "Allowlist of Prism Element hosts (IPs or hostnames). "
            "If empty, PE tools will only accept hosts discovered via list_hosts. "
            "Set NUTANIX_ALLOWED_PE_HOSTS as comma-separated values."
        ),
    )

    @field_validator("host", mode="before")
    @classmethod
    def validate_host(cls, v: Optional[str]) -> str:
        if not v:
            raise ValueError(
                "NUTANIX_HOST is required. "
                "Set it as an environment variable or in a .env file."
            )
        return v

    @field_validator("allowed_pe_hosts", mode="before")
    @classmethod
    def parse_pe_hosts(cls, v):
        if isinstance(v, str):
            return [h.strip() for h in v.split(",") if h.strip()]
        return v or []

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

    def is_pe_host_allowed(self, pe_host: str) -> bool:
        """Check if a PE host is in the allowlist.

        Returns True if:
        - The allowlist is empty (permissive mode — relies on network controls)
        - The host matches an entry in the allowlist
        """
        if not self.allowed_pe_hosts:
            return True
        return pe_host in self.allowed_pe_hosts


def get_settings() -> Settings:
    """Load and validate settings."""
    try:
        return Settings()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
