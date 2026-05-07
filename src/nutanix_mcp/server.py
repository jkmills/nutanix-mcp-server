"""MCP Server implementation for Nutanix Prism Central & Element."""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from nutanix_mcp.client import NutanixClient, NutanixAPIError
from nutanix_mcp.config import Settings, get_settings
from nutanix_mcp.tools import get_all_tools
from nutanix_mcp.tools.vm import VM_HANDLERS
from nutanix_mcp.tools.cluster import CLUSTER_HANDLERS
from nutanix_mcp.tools.prism_element import PE_HANDLERS
from nutanix_mcp.tools.report import REPORT_HANDLERS

# Merge all handler dispatch tables
ALL_HANDLERS: dict[str, Any] = {
    **VM_HANDLERS,
    **CLUSTER_HANDLERS,
    **PE_HANDLERS,
    **REPORT_HANDLERS,
}


def create_server(settings: Settings) -> tuple[Server, NutanixClient]:
    """Create and configure the MCP server."""
    server = Server("nutanix-mcp")
    client = NutanixClient(settings)
    all_tools = get_all_tools()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return the list of available tools."""
        return [
            Tool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"],
            )
            for tool in all_tools
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute a tool and return the result."""
        handler = ALL_HANDLERS.get(name)
        if not handler:
            return [TextContent(
                type="text",
                text=f"Error: Unknown tool '{name}'",
            )]

        try:
            result = await handler(client, arguments or {})
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except NutanixAPIError as e:
            error_text = f"Error: {e.message}"
            if e.status_code:
                error_text += f" (HTTP {e.status_code})"
            return [TextContent(type="text", text=error_text)]
        except Exception:
            return [TextContent(type="text", text="An unexpected error occurred")]

    return server, client


async def run_server() -> None:
    """Run the MCP server."""
    settings = get_settings()

    if not settings.has_credentials:
        print(
            "Error: No credentials configured. "
            "Set NUTANIX_USERNAME and NUTANIX_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"Starting Nutanix MCP server for {settings.host}:{settings.port}",
        file=sys.stderr,
    )

    server, client = create_server(settings)

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await client.close()


def main() -> None:
    """Entry point for the MCP server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
