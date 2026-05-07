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
            "Get an overview of the connected Nutanix environment — clusters, hosts, VMs, and storage summary."
        ),
        arguments=[],
    ),
    Prompt(
        name="as_built_report",
        description=(
            "Generate an As-Built documentation report for the Nutanix environment. "
            "Supports three scope levels: full environment, specific cluster(s), or "
            "specific VM(s). The AI will call the appropriate tools and format a "
            "comprehensive Markdown report."
        ),
        arguments=[
            PromptArgument(
                name="scope",
                description=(
                    "Report scope: 'environment' (all clusters/hosts/VMs/networking), "
                    "'cluster' (specific cluster UUID or name), or 'vm' (specific VM UUID or name)"
                ),
                required=True,
            ),
            PromptArgument(
                name="target",
                description=(
                    "Target identifier — cluster name/UUID or VM name/UUID. Leave empty for environment-level scope."
                ),
                required=False,
            ),
        ],
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


def handle_as_built_report(arguments: dict[str, str]) -> GetPromptResult:
    """Return a prompt that guides the LLM to produce an As-Built report."""
    scope = arguments.get("scope", "environment").lower()
    target = arguments.get("target", "")

    if scope == "cluster":
        instructions = (
            f"Generate a detailed As-Built report for the Nutanix cluster: {target or '(all clusters)'}.\n\n"
            "Use the available tools in this order:\n"
            "1. list_clusters — find the cluster(s) matching the target\n"
            "2. get_cluster — get full config for each cluster (redundancy, AOS version, fault domain)\n"
            "3. list_hosts — get all hosts in the cluster (CPU model, sockets, cores, memory)\n"
            "4. list_vms with cluster filter — get VMs running on this cluster\n"
            "5. list_subnets — get networking for this cluster (VLAN, CIDR, gateway, DHCP)\n"
            "6. pe_list_storage_containers — get storage containers (capacity, RF, compression)\n\n"
            "Format as a Markdown document with these sections:\n"
            "- **Header** — cluster name, UUID, generation timestamp\n"
            "- **Cluster Configuration** — table of cluster properties (function, hypervisor, operation mode, redundancy factor, AOS version, fault tolerance domain)\n"
            "- **Network Configuration** — external IP, data services IP, NTP, DNS\n"
            "- **Hosts** — table with name, IP, hypervisor type, CPU model, sockets, cores/socket, total cores, memory. Include totals row.\n"
            "- **Storage Containers** — table with name, max capacity, replication factor, compression, dedup\n"
            "- **Subnets** — table with name, type, VLAN ID, subnet CIDR, gateway, DHCP enabled\n"
            "- **Virtual Machines** — table with name, power state, vCPUs, memory, disk count, NIC count. Include powered-on/off summary."
        )
    elif scope == "vm":
        instructions = (
            f"Generate a detailed As-Built report for the Nutanix VM(s): {target or '(specify target)'}.\n\n"
            "Use the available tools:\n"
            "1. list_vms — find the VM(s) matching the target name or UUID\n"
            "2. get_vm — get full details for each VM\n\n"
            "Format as a Markdown document with these sections per VM:\n"
            "- **Header** — VM name, UUID, power state, generation timestamp\n"
            "- **Configuration** — table of properties (description, machine type, guest OS, hardware clock timezone)\n"
            "- **Compute** — CPU sockets, cores/socket, threads/core, total vCPUs, memory\n"
            "- **Placement** — cluster name/UUID, host name/UUID\n"
            "- **Disks** — table with disk#, type, size, bus type, controller address, storage container\n"
            "- **Network Interfaces** — table with NIC#, type, subnet, MAC, IP address, VLAN mode\n"
            "- **Categories** — key:value pairs assigned to the VM\n"
            "- **Boot Configuration** — boot type, boot device order\n"
            "- **GPUs** — if present, mode/vendor/device"
        )
    else:  # environment
        instructions = (
            "Generate a comprehensive As-Built report for the full Nutanix environment.\n\n"
            "Use the available tools in this order:\n"
            "1. list_clusters — get all clusters\n"
            "2. get_cluster for each — get detailed config\n"
            "3. list_hosts — get all hosts (grouped by cluster)\n"
            "4. list_vms — get full VM inventory\n"
            "5. list_subnets — get all subnets\n"
            "6. pe_list_storage_containers — get storage containers\n\n"
            "Format as a Markdown document with these sections:\n"
            "- **Title** — 'Nutanix As-Built Report — Full Environment' with generation timestamp\n"
            "- **Executive Summary** — table with counts: clusters, hosts, VMs, storage containers, subnets\n"
            "- **Clusters** — for each cluster: config table, hosts sub-table, network settings (NTP/DNS/external IP)\n"
            "- **Storage** — all containers with name, capacity, used, cluster association\n"
            "- **Networking** — all subnets with name, type, VLAN, CIDR, gateway, cluster\n"
            "- **VM Inventory** — full table with name, power state, vCPUs, memory, cluster. Include powered-on/off summary.\n\n"
            "Keep tables aligned and use backticks for UUIDs."
        )

    return GetPromptResult(
        description=f"Nutanix As-Built report ({scope} scope)",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=instructions,
                ),
            ),
        ],
    )


# ─── Prompt Dispatch ──────────────────────────────────────────────────────────

PROMPT_HANDLERS: dict[str, callable] = {
    "set_credentials": handle_set_credentials,
    "nutanix_overview": handle_nutanix_overview,
    "as_built_report": handle_as_built_report,
}
