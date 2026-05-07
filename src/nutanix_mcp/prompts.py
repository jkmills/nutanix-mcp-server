"""MCP Prompts for interactive credential configuration."""

from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
)


# ─── Prompt Definitions ───────────────────────────────────────────────────────

PROMPTS: list[Prompt] = [
    Prompt(
        name="set_credentials",
        description=(
            "Configure Nutanix Prism Central credentials for this session. "
            "Use this when environment variables are not set."
        ),
        arguments=[
            PromptArgument(
                name="host",
                description="Prism Central hostname or IP address",
                required=True,
            ),
            PromptArgument(
                name="username",
                description="API username",
                required=True,
            ),
            PromptArgument(
                name="password",
                description="API password",
                required=True,
            ),
            PromptArgument(
                name="port",
                description="API port (default: 9440)",
                required=False,
            ),
        ],
    ),
    Prompt(
        name="nutanix_overview",
        description=(
            "Get an overview of the connected Nutanix environment — "
            "clusters, hosts, VMs, and storage summary."
        ),
        arguments=[],
    ),
]


# ─── Prompt Handlers ──────────────────────────────────────────────────────────


def handle_set_credentials(arguments: dict[str, str]) -> GetPromptResult:
    """Return instructions for the LLM to configure credentials."""
    host = arguments.get("host", "")
    username = arguments.get("username", "")
    port = arguments.get("port", "9440")

    return GetPromptResult(
        description="Nutanix credential configuration",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        f"Configure connection to Nutanix Prism Central:\n"
                        f"  Host: {host}\n"
                        f"  Port: {port}\n"
                        f"  Username: {username}\n\n"
                        "Please verify connectivity by listing clusters. "
                        "If authentication fails, check that the credentials "
                        "have API access to Prism Central."
                    ),
                ),
            ),
        ],
    )


def handle_nutanix_overview(arguments: dict[str, str]) -> GetPromptResult:
    """Return a prompt that guides the LLM to gather environment info."""
    return GetPromptResult(
        description="Nutanix environment overview",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        "Give me a comprehensive overview of this Nutanix environment. "
                        "Use the available tools to:\n"
                        "1. List all clusters and their health status\n"
                        "2. Count total hosts and VMs\n"
                        "3. Summarize storage capacity and usage\n"
                        "4. List any active alerts\n\n"
                        "Present the information as a concise summary table."
                    ),
                ),
            ),
        ],
    )


# ─── Prompt Dispatch ──────────────────────────────────────────────────────────

PROMPT_HANDLERS: dict[str, callable] = {
    "set_credentials": handle_set_credentials,
    "nutanix_overview": handle_nutanix_overview,
}
