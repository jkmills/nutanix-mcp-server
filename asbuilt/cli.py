"""AsBuilt CLI — generate a Nutanix cluster report through the MCP server.

Spawns `python -m nutanix_mcp` as a stdio MCP server, calls its pe_* tools
to collect live cluster data, and renders a Markdown (and optionally HTML)
AsBuilt report.

Usage:
    nutanix-asbuilt <target> [--sections overview hosts ...]
                    [-o report.md] [--html report.html] [--title TITLE]

<target> may be a Prism Element IP, hostname, cluster name, or cluster UUID
(names/UUIDs are resolved via Prism Central by the server). Connection
settings come from the same NUTANIX_* environment variables the server uses.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from asbuilt.report import ALL_SECTIONS, collect_report_data, render_html, render_markdown


class ToolCallError(RuntimeError):
    """A tool call returned isError."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nutanix-asbuilt",
        description="Generate an AsBuilt report for a Nutanix cluster via the MCP server.",
    )
    parser.add_argument(
        "target",
        help="Prism Element IP, hostname, cluster name, or cluster UUID",
    )
    parser.add_argument(
        "--sections",
        nargs="+",
        choices=ALL_SECTIONS,
        default=ALL_SECTIONS,
        metavar="SECTION",
        help=f"Sections to include (default: all). Choices: {', '.join(ALL_SECTIONS)}",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Markdown output path (default: asbuilt-<cluster>.md)",
    )
    parser.add_argument(
        "--html",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help="Also write an HTML report (default path: asbuilt-<cluster>.html)",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Report title for the HTML export (default: 'AsBuilt Report — <cluster>')",
    )
    parser.add_argument(
        "--server-command",
        default=None,
        help=f"Command to launch the MCP server (default: '{sys.executable} -m nutanix_mcp')",
    )
    return parser.parse_args(argv)


def parse_tool_result(result: Any, tool_name: str) -> dict[str, Any]:
    """Extract structured output from a CallToolResult, raising on isError."""
    if getattr(result, "isError", False):
        message = ""
        for block in result.content or []:
            if getattr(block, "text", None):
                message = block.text
                break
        raise ToolCallError(f"{tool_name}: {message or 'tool call failed'}")

    if getattr(result, "structuredContent", None) is not None:
        return result.structuredContent

    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    return {}


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "cluster"


async def generate(args: argparse.Namespace) -> int:
    if args.server_command:
        command, *cmd_args = args.server_command.split()
    else:
        command, cmd_args = sys.executable, ["-m", "nutanix_mcp"]

    server_params = StdioServerParameters(
        command=command,
        args=cmd_args,
        env={**os.environ},
    )

    print(f"Connecting to MCP server ({command} {' '.join(cmd_args)}) ...", file=sys.stderr)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(
                f"Connected: {init.serverInfo.name} v{init.serverInfo.version}",
                file=sys.stderr,
            )

            async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                result = await session.call_tool(name, arguments)
                return parse_tool_result(result, name)

            print(f"Collecting sections: {', '.join(args.sections)}", file=sys.stderr)
            data, errors = await collect_report_data(call_tool, args.target, args.sections)

    cluster_name = (data.get("overview") or {}).get("name") or args.target
    markdown = render_markdown(cluster_name, args.target, data, args.sections)

    for section, error in errors.items():
        print(f"warning: section '{section}' failed: {error}", file=sys.stderr)

    md_path = args.output or f"asbuilt-{_slug(cluster_name)}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"Markdown report: {md_path}")

    if args.html is not None:
        title = args.title or f"AsBuilt Report — {cluster_name}"
        html_path = args.html or f"asbuilt-{_slug(cluster_name)}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(render_html(markdown, title))
        print(f"HTML report:     {html_path} (open in a browser, Ctrl+P to save as PDF)")

    return 1 if errors and not data else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(generate(args))
    except ToolCallError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
