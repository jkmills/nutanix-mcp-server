"""Nutanix MCP Server - MCP server for Nutanix Prism Central & Element APIs."""

__version__ = "0.5.0"

from nutanix_mcp.server import main  # noqa: E402

__all__ = ["main", "__version__"]
