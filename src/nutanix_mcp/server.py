"""MCP Server implementation for Nutanix Prism Central & Element."""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    Resource,
    ResourceTemplate,
    TextContent,
    TextResourceContents,
    Tool,
)

from nutanix_mcp.client import NutanixAPIError, NutanixClient
from nutanix_mcp.config import Settings, get_settings
from nutanix_mcp.prompts import PROMPT_HANDLERS, PROMPTS
from nutanix_mcp.resources import (
    RESOURCE_TEMPLATES,
    STATIC_RESOURCES,
    resolve_resource,
)
from nutanix_mcp.tools import get_all_tools
from nutanix_mcp.tools.cluster import CLUSTER_HANDLERS
from nutanix_mcp.tools.networking import NETWORKING_HANDLERS
from nutanix_mcp.tools.prism_element import PE_HANDLERS
from nutanix_mcp.tools.task import TASK_HANDLERS
from nutanix_mcp.tools.vm import VM_HANDLERS

# Merge all handler dispatch tables
ALL_HANDLERS: dict[str, Any] = {
    **VM_HANDLERS,
    **CLUSTER_HANDLERS,
    **PE_HANDLERS,
    **NETWORKING_HANDLERS,
    **TASK_HANDLERS,
}


def create_server(settings: Settings) -> tuple[Server, NutanixClient]:
    """Create and configure the MCP server."""
    server = Server("nutanix-mcp")
    client = NutanixClient(settings)
    all_tools = get_all_tools()

    # ─── Tools ────────────────────────────────────────────────────────────

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
            return [
                TextContent(
                    type="text",
                    text=f"Error: Unknown tool '{name}'",
                )
            ]

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

    # ─── Resources ────────────────────────────────────────────────────────

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """Return browseable static resources."""
        return STATIC_RESOURCES

    @server.list_resource_templates()
    async def list_resource_templates() -> list[ResourceTemplate]:
        """Return URI templates for parameterized resource access."""
        return RESOURCE_TEMPLATES

    @server.read_resource()
    async def read_resource(uri: str) -> list[TextResourceContents]:
        """Resolve a nutanix:// URI to resource contents."""
        try:
            return await resolve_resource(client, str(uri))
        except NutanixAPIError as e:
            error_text = f"Error: {e.message}"
            if e.status_code:
                error_text += f" (HTTP {e.status_code})"
            return [
                TextResourceContents(
                    uri=str(uri),
                    mimeType="application/json",
                    text=json.dumps({"error": error_text}),
                )
            ]

    # ─── Prompts ──────────────────────────────────────────────────────────

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """Return available prompts."""
        return PROMPTS

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
        """Handle a prompt request."""
        handler = PROMPT_HANDLERS.get(name)
        if not handler:
            return GetPromptResult(
                description="Unknown prompt",
                messages=[],
            )
        return handler(arguments or {})

    return server, client


async def run_server() -> None:
    """Run the MCP server."""
    settings = get_settings()

    if not settings.has_credentials:
        print(
            "Error: No credentials configured. Set NUTANIX_USERNAME and NUTANIX_PASSWORD.",
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
