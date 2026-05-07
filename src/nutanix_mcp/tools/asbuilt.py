"""AsBuilt report generation tools.

Generates comprehensive infrastructure documentation from live Nutanix
Prism Element data. Returns structured Markdown with Mermaid diagrams.
Also provides HTML export with print CSS for PDF generation.
"""

import html
import json
from datetime import datetime, timezone
from typing import Any

from nutanix_mcp.client import NutanixClient

# ─── Available report sections ────────────────────────────────────────────────

ALL_SECTIONS = [
    "overview",
    "hosts",
    "vms",
    "networks",
    "storage",
    "protection_domains",
    "alerts",
    "health",
]

# ─── Tool Definitions ─────────────────────────────────────────────────────────

ASBUILT_TOOLS: list[dict] = [
    {
        "name": "generate_asbuilt",
        "description": (
            "Generate an infrastructure AsBuilt report from a Nutanix Prism Element cluster. "
            "Queries live cluster data and returns a structured Markdown report with tables "
            "and Mermaid topology diagrams. Use 'sections' to include only specific parts. "
            "Available sections: overview, hosts, vms, networks, storage, protection_domains, alerts, health."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
                "sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Which sections to include in the report. "
                        "Defaults to all sections if omitted. "
                        "Options: overview, hosts, vms, networks, storage, "
                        "protection_domains, alerts, health"
                    ),
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "export_asbuilt_html",
        "description": (
            "Convert an AsBuilt Markdown report to a self-contained HTML file "
            "with print-optimized CSS. Open in a browser and use Ctrl+P / Cmd+P "
            "to save as PDF. Includes Mermaid diagram rendering via CDN. "
            "Pass the markdown string from generate_asbuilt output."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {
                    "type": "string",
                    "description": "The Markdown report content from generate_asbuilt",
                },
                "title": {
                    "type": "string",
                    "description": "Report title (defaults to 'Nutanix AsBuilt Report')",
                },
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "get_project_architecture",
        "description": (
            "Get the Nutanix MCP Server project architecture documentation. "
            "Returns a Markdown document with component diagrams, API layer details, "
            "tool inventory, design decisions, deployment topology, and file structure."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ─── Data Collection Helpers ──────────────────────────────────────────────────


async def _collect_overview(client: NutanixClient, pe_host: str) -> dict[str, Any]:
    """Collect cluster overview data."""
    result = await client.pe_get(pe_host, "cluster")
    return {
        "name": result.get("name", "Unknown"),
        "uuid": result.get("cluster_uuid", ""),
        "version": result.get("version", ""),
        "numNodes": result.get("num_nodes", 0),
        "storageType": result.get("storage_type", ""),
        "hypervisorTypes": result.get("hypervisor_types", []),
        "externalIp": result.get("cluster_external_ipaddress", ""),
        "timezone": result.get("timezone", ""),
        "nccVersion": result.get("ncc_version", ""),
        "blockSerials": result.get("rackable_units", []),
    }


async def _collect_hosts(client: NutanixClient, pe_host: str) -> list[dict]:
    """Collect host inventory."""
    result = await client.pe_list(pe_host, "hosts")
    entities = result.get("entities", [])
    return [
        {
            "name": h.get("name", ""),
            "uuid": h.get("uuid", ""),
            "hypervisorAddress": h.get("hypervisor_address", ""),
            "cvmAddress": h.get("controller_vm_backplane_ip", ""),
            "ipmiAddress": h.get("ipmi_address", ""),
            "cpuModel": h.get("cpu_model", ""),
            "numCpuSockets": h.get("num_cpu_sockets", 0),
            "numCpuCores": h.get("num_cpu_cores", 0),
            "memoryCapacityGb": (h.get("memory_capacity_in_bytes", 0)) // (1024**3),
            "hypervisorType": h.get("hypervisor_type", ""),
            "hypervisorVersion": h.get("hypervisor_full_name", ""),
            "serial": h.get("serial", ""),
            "blockModel": h.get("block_model_name", ""),
            "blockSerial": h.get("block_serial", ""),
        }
        for h in entities
    ]


async def _collect_vms(client: NutanixClient, pe_host: str) -> list[dict]:
    """Collect VM inventory."""
    result = await client.pe_list(pe_host, "vms")
    entities = result.get("entities", [])
    return [
        {
            "name": vm.get("name", ""),
            "uuid": vm.get("uuid", ""),
            "powerState": vm.get("power_state", ""),
            "numVcpus": vm.get("num_vcpus", 0),
            "memoryMb": vm.get("memory_mb", 0),
            "hostUuid": vm.get("host_uuid", ""),
            "ipAddresses": vm.get("ip_addresses", []),
            "diskCapacityGb": sum(
                (d.get("disk_capacity_in_bytes", 0) or 0) // (1024**3)
                for d in vm.get("vm_disk_info", [])
                if not d.get("is_cdrom", False)
            ),
        }
        for vm in entities
    ]


async def _collect_networks(client: NutanixClient, pe_host: str) -> list[dict]:
    """Collect network configuration."""
    result = await client.pe_list(pe_host, "networks")
    entities = result.get("entities", [])
    return [
        {
            "name": n.get("name", ""),
            "uuid": n.get("uuid", ""),
            "vlanId": n.get("vlan_id"),
            "networkType": "Managed" if n.get("ip_config") else "Unmanaged",
            "subnet": _extract_subnet_info(n),
        }
        for n in entities
    ]


def _extract_subnet_info(network: dict) -> str:
    """Extract subnet CIDR from network IP config."""
    ip_config = network.get("ip_config", {})
    if not ip_config:
        return ""
    prefix = ip_config.get("prefix_length", "")
    addr = ip_config.get("network_address", "")
    if addr and prefix:
        return f"{addr}/{prefix}"
    return ip_config.get("subnet_mask", "")


async def _collect_storage(client: NutanixClient, pe_host: str) -> dict[str, Any]:
    """Collect storage configuration."""
    containers_result = await client.pe_list(pe_host, "containers")
    pools_result = await client.pe_list(pe_host, "storage_pools")
    disks_result = await client.pe_list(pe_host, "disks")

    containers = containers_result.get("entities", [])
    pools = pools_result.get("entities", [])
    disks = disks_result.get("entities", [])

    return {
        "containers": [
            {
                "name": c.get("name", ""),
                "uuid": c.get("container_uuid", ""),
                "maxCapacityTb": round((c.get("max_capacity", 0) or 0) / (1024**4), 2),
                "replicationFactor": c.get("replication_factor", ""),
                "compressionEnabled": c.get("compression_enabled", False),
                "dedupEnabled": c.get("on_disk_dedup"),
                "erasureCoded": c.get("erasure_coded", False),
            }
            for c in containers
        ],
        "pools": [
            {
                "name": sp.get("name", ""),
                "uuid": sp.get("storage_pool_uuid", ""),
                "capacityTb": round((sp.get("capacity", 0) or 0) / (1024**4), 2),
                "numDisks": len(sp.get("disks", [])),
            }
            for sp in pools
        ],
        "diskSummary": _summarize_disks(disks),
    }


def _summarize_disks(disks: list[dict]) -> dict:
    """Summarize disk tiers and counts."""
    tiers: dict[str, dict] = {}
    for d in disks:
        tier = d.get("storage_tier_name", "Unknown")
        if tier not in tiers:
            tiers[tier] = {"count": 0, "totalCapacityTb": 0.0}
        tiers[tier]["count"] += 1
        tiers[tier]["totalCapacityTb"] += (d.get("disk_size", 0) or 0) / (1024**4)

    for tier_data in tiers.values():
        tier_data["totalCapacityTb"] = round(tier_data["totalCapacityTb"], 2)

    return {"tiers": tiers, "totalDisks": len(disks)}


async def _collect_protection_domains(client: NutanixClient, pe_host: str) -> list[dict]:
    """Collect protection domain configuration."""
    result = await client.pe_list(pe_host, "protection_domains")
    entities = result.get("entities", [])
    return [
        {
            "name": pd.get("name", ""),
            "active": pd.get("active", False),
            "vmCount": len(pd.get("vms", [])),
            "cronSchedules": len(pd.get("cron_schedules", [])),
            "replicationLinks": [
                {
                    "remoteSite": rl.get("remote_site_name", ""),
                }
                for rl in pd.get("replication_links", [])
            ],
        }
        for pd in entities
    ]


async def _collect_alerts(client: NutanixClient, pe_host: str) -> dict[str, Any]:
    """Collect active alert summary."""
    result = await client.pe_get(pe_host, "alerts", params={"count": "100", "resolved": "false"})
    entities = result.get("entities", [])

    severity_counts: dict[str, int] = {}
    for a in entities:
        sev = a.get("severity", "UNKNOWN")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return {
        "totalActive": len(entities),
        "bySeverity": severity_counts,
        "recent": [
            {
                "title": a.get("alert_title", ""),
                "severity": a.get("severity", ""),
                "message": a.get("message", ""),
            }
            for a in entities[:10]
        ],
    }


async def _collect_health(client: NutanixClient, pe_host: str) -> dict[str, Any]:
    """Collect health check results."""
    result = await client.pe_get(pe_host, "health_checks")
    entities = result.get("entities", [])

    status_counts: dict[str, int] = {}
    failed_checks: list[dict] = []
    for check in entities:
        status = check.get("last_execution_status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
        if status in ("FAIL", "WARN", "ERROR"):
            failed_checks.append({
                "name": check.get("name", ""),
                "description": check.get("description", ""),
                "status": status,
            })

    return {
        "totalChecks": len(entities),
        "byStatus": status_counts,
        "failedChecks": failed_checks[:20],
    }


# ─── Markdown Report Generation ──────────────────────────────────────────────


def _generate_markdown(
    cluster_name: str,
    pe_host: str,
    data: dict[str, Any],
    sections: list[str],
) -> str:
    """Generate the full Markdown report from collected data."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.append(f"# AsBuilt Report — {cluster_name}")
    lines.append("")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Prism Element:** {pe_host}  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    if "overview" in sections and "overview" in data:
        lines.extend(_section_overview(data["overview"]))

    if "hosts" in sections and "hosts" in data:
        lines.extend(_section_hosts(data["hosts"]))

    if "vms" in sections and "vms" in data:
        lines.extend(_section_vms(data["vms"]))

    if "networks" in sections and "networks" in data:
        lines.extend(_section_networks(data["networks"]))

    if "storage" in sections and "storage" in data:
        lines.extend(_section_storage(data["storage"]))

    if "protection_domains" in sections and "protection_domains" in data:
        lines.extend(_section_protection_domains(data["protection_domains"]))

    if "alerts" in sections and "alerts" in data:
        lines.extend(_section_alerts(data["alerts"]))

    if "health" in sections and "health" in data:
        lines.extend(_section_health(data["health"]))

    # Topology diagram (needs overview + hosts)
    if "overview" in data and "hosts" in data:
        lines.extend(_section_topology_diagram(data["overview"], data.get("hosts", [])))

    return "\n".join(lines)


def _section_overview(overview: dict) -> list[str]:
    """Generate the cluster overview section."""
    lines = [
        "## Cluster Overview",
        "",
        "| Property | Value |",
        "|----------|-------|",
        f"| **Cluster Name** | {overview['name']} |",
        f"| **Cluster UUID** | `{overview['uuid']}` |",
        f"| **AOS Version** | {overview['version']} |",
        f"| **NCC Version** | {overview.get('nccVersion', 'N/A')} |",
        f"| **Node Count** | {overview['numNodes']} |",
        f"| **Storage Type** | {overview['storageType']} |",
        f"| **Hypervisor** | {', '.join(overview.get('hypervisorTypes', []))} |",
        f"| **External IP** | {overview['externalIp']} |",
        f"| **Timezone** | {overview.get('timezone', 'N/A')} |",
        "",
    ]
    return lines


def _section_hosts(hosts: list[dict]) -> list[str]:
    """Generate the host inventory section."""
    lines = [
        "## Host Inventory",
        "",
        f"**Total Hosts:** {len(hosts)}",
        "",
        "| Host Name | IP Address | CPU Model | Sockets | Cores | RAM (GB) | Hypervisor | Block Model | Serial |",
        "|-----------|-----------|-----------|---------|-------|----------|------------|-------------|--------|",
    ]
    for h in hosts:
        lines.append(
            f"| {h['name']} | {h['hypervisorAddress']} | {h['cpuModel']} | "
            f"{h['numCpuSockets']} | {h['numCpuCores']} | {h['memoryCapacityGb']} | "
            f"{h['hypervisorType']} | {h.get('blockModel', '')} | {h.get('serial', '')} |"
        )
    lines.append("")

    # Host resource summary
    total_cores = sum(h.get("numCpuCores", 0) for h in hosts)
    total_ram = sum(h.get("memoryCapacityGb", 0) for h in hosts)
    lines.extend([
        "### Resource Summary",
        "",
        f"- **Total CPU Cores:** {total_cores}",
        f"- **Total RAM:** {total_ram} GB ({round(total_ram / 1024, 1)} TB)",
        "",
    ])
    return lines


def _section_vms(vms: list[dict]) -> list[str]:
    """Generate the VM inventory section."""
    powered_on = [v for v in vms if v.get("powerState") == "ON" or v.get("powerState") == "on"]
    powered_off = [v for v in vms if v not in powered_on]

    lines = [
        "## Virtual Machine Inventory",
        "",
        f"**Total VMs:** {len(vms)} (🟢 {len(powered_on)} on, 🔴 {len(powered_off)} off)",
        "",
        "| VM Name | Power | vCPUs | RAM (MB) | Disk (GB) | IP Addresses |",
        "|---------|-------|-------|----------|-----------|--------------|",
    ]
    for vm in sorted(vms, key=lambda v: v.get("name", "")):
        state = "🟢" if vm in powered_on else "🔴"
        ips = ", ".join(vm.get("ipAddresses", [])) or "—"
        lines.append(
            f"| {vm['name']} | {state} | {vm['numVcpus']} | "
            f"{vm['memoryMb']} | {vm.get('diskCapacityGb', '—')} | {ips} |"
        )
    lines.append("")

    # VM resource summary
    total_vcpus = sum(v.get("numVcpus", 0) for v in powered_on)
    total_ram_mb = sum(v.get("memoryMb", 0) for v in powered_on)
    lines.extend([
        "### VM Resource Allocation (powered on only)",
        "",
        f"- **Total vCPUs Allocated:** {total_vcpus}",
        f"- **Total RAM Allocated:** {total_ram_mb} MB ({round(total_ram_mb / 1024, 1)} GB)",
        "",
    ])
    return lines


def _section_networks(networks: list[dict]) -> list[str]:
    """Generate the network configuration section."""
    lines = [
        "## Network Configuration",
        "",
        f"**Total Networks:** {len(networks)}",
        "",
        "| Network Name | VLAN ID | Type | Subnet |",
        "|-------------|---------|------|--------|",
    ]
    for n in networks:
        lines.append(
            f"| {n['name']} | {n.get('vlanId', '—')} | {n['networkType']} | {n.get('subnet', '—')} |"
        )
    lines.append("")
    return lines


def _section_storage(storage: dict) -> list[str]:
    """Generate the storage section."""
    lines = [
        "## Storage Configuration",
        "",
    ]

    # Storage Pools
    pools = storage.get("pools", [])
    if pools:
        lines.extend([
            "### Storage Pools",
            "",
            "| Pool Name | Capacity (TB) | Disks |",
            "|-----------|--------------|-------|",
        ])
        for p in pools:
            lines.append(f"| {p['name']} | {p['capacityTb']} | {p['numDisks']} |")
        lines.append("")

    # Storage Containers
    containers = storage.get("containers", [])
    if containers:
        lines.extend([
            "### Storage Containers",
            "",
            "| Container Name | Max Capacity (TB) | RF | Compression | Dedup | Erasure Coding |",
            "|---------------|-------------------|-----|-------------|-------|----------------|",
        ])
        for c in containers:
            lines.append(
                f"| {c['name']} | {c['maxCapacityTb']} | {c['replicationFactor']} | "
                f"{'✅' if c['compressionEnabled'] else '❌'} | "
                f"{'✅' if c.get('dedupEnabled') else '❌'} | "
                f"{'✅' if c['erasureCoded'] else '❌'} |"
            )
        lines.append("")

    # Disk Summary
    disk_summary = storage.get("diskSummary", {})
    tiers = disk_summary.get("tiers", {})
    if tiers:
        lines.extend([
            "### Disk Inventory",
            "",
            f"**Total Disks:** {disk_summary.get('totalDisks', 0)}",
            "",
            "| Tier | Count | Total Capacity (TB) |",
            "|------|-------|-------------------|",
        ])
        for tier_name, tier_data in tiers.items():
            lines.append(f"| {tier_name} | {tier_data['count']} | {tier_data['totalCapacityTb']} |")
        lines.append("")

    return lines


def _section_protection_domains(pds: list[dict]) -> list[str]:
    """Generate the protection domains section."""
    lines = [
        "## Data Protection",
        "",
        f"**Total Protection Domains:** {len(pds)}",
        "",
        "| PD Name | Active | VMs | Schedules | Remote Sites |",
        "|---------|--------|-----|-----------|--------------|",
    ]
    for pd in pds:
        remote_sites = ", ".join(rl.get("remoteSite", "") for rl in pd.get("replicationLinks", []))
        lines.append(
            f"| {pd['name']} | {'✅' if pd['active'] else '❌'} | "
            f"{pd['vmCount']} | {pd['cronSchedules']} | {remote_sites or '—'} |"
        )
    lines.append("")
    return lines


def _section_alerts(alerts: dict) -> list[str]:
    """Generate the alerts summary section."""
    lines = [
        "## Active Alerts",
        "",
        f"**Total Active:** {alerts['totalActive']}",
        "",
    ]
    by_sev = alerts.get("bySeverity", {})
    if by_sev:
        lines.extend([
            "| Severity | Count |",
            "|----------|-------|",
        ])
        for sev, count in sorted(by_sev.items()):
            lines.append(f"| {sev} | {count} |")
        lines.append("")

    recent = alerts.get("recent", [])
    if recent:
        lines.extend([
            "### Recent Alerts",
            "",
            "| Title | Severity | Message |",
            "|-------|----------|---------|",
        ])
        for a in recent[:10]:
            msg = (a.get("message", "") or "")[:80]
            lines.append(f"| {a['title']} | {a['severity']} | {msg} |")
        lines.append("")
    return lines


def _section_health(health: dict) -> list[str]:
    """Generate the health check section."""
    lines = [
        "## Health Checks",
        "",
        f"**Total Checks:** {health['totalChecks']}",
        "",
    ]
    by_status = health.get("byStatus", {})
    if by_status:
        lines.extend([
            "| Status | Count |",
            "|--------|-------|",
        ])
        for status, count in sorted(by_status.items()):
            lines.append(f"| {status} | {count} |")
        lines.append("")

    failed = health.get("failedChecks", [])
    if failed:
        lines.extend([
            "### Failed/Warning Checks",
            "",
            "| Check Name | Status | Description |",
            "|------------|--------|-------------|",
        ])
        for c in failed:
            desc = (c.get("description", "") or "")[:80]
            lines.append(f"| {c['name']} | {c['status']} | {desc} |")
        lines.append("")
    return lines


def _section_topology_diagram(overview: dict, hosts: list[dict]) -> list[str]:
    """Generate a Mermaid topology diagram."""
    cluster_name = overview.get("name", "Cluster")
    lines = [
        "## Cluster Topology",
        "",
        "```mermaid",
        "graph TD",
        f'    PC["🖥️ Prism Central"]',
        f'    CLUSTER["{cluster_name}<br/>AOS {overview.get("version", "")}<br/>{overview.get("numNodes", 0)} Nodes"]',
        "    PC --> CLUSTER",
        "",
    ]
    for i, h in enumerate(hosts):
        host_id = f"H{i}"
        ram = h.get("memoryCapacityGb", 0)
        cores = h.get("numCpuCores", 0)
        lines.append(
            f'    {host_id}["{h["name"]}<br/>{h["hypervisorAddress"]}<br/>'
            f'{cores} cores / {ram} GB"]'
        )
        lines.append(f"    CLUSTER --> {host_id}")

    lines.extend([
        "```",
        "",
    ])
    return lines


# ─── HTML Export ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad: true, theme: 'neutral'}});</script>
<style>
  :root {{
    --primary: #1a56db;
    --bg: #ffffff;
    --text: #1f2937;
    --border: #e5e7eb;
    --header-bg: #f9fafb;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: var(--text);
    background: var(--bg);
    line-height: 1.6;
    padding: 40px;
    max-width: 1100px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 28px;
    color: var(--primary);
    border-bottom: 3px solid var(--primary);
    padding-bottom: 10px;
    margin-bottom: 20px;
  }}
  h2 {{
    font-size: 22px;
    color: var(--primary);
    margin-top: 30px;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
    page-break-after: avoid;
  }}
  h3 {{
    font-size: 17px;
    margin-top: 18px;
    margin-bottom: 8px;
    page-break-after: avoid;
  }}
  p {{ margin-bottom: 10px; }}
  strong {{ font-weight: 600; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
    font-size: 13px;
    page-break-inside: auto;
  }}
  thead {{ background: var(--header-bg); }}
  th, td {{
    border: 1px solid var(--border);
    padding: 8px 10px;
    text-align: left;
  }}
  th {{ font-weight: 600; white-space: nowrap; }}
  tr {{ page-break-inside: avoid; }}
  tr:nth-child(even) {{ background: #f9fafb; }}
  code {{
    background: #f3f4f6;
    padding: 2px 5px;
    border-radius: 3px;
    font-size: 12px;
  }}
  ul {{ margin: 8px 0 16px 24px; }}
  li {{ margin-bottom: 4px; }}
  hr {{ border: none; border-top: 1px solid var(--border); margin: 20px 0; }}
  .mermaid {{ margin: 20px 0; text-align: center; }}
  .page-break {{ page-break-before: always; }}
  .footer {{
    margin-top: 40px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    font-size: 11px;
    color: #9ca3af;
    text-align: center;
  }}

  @media print {{
    body {{ padding: 20px; font-size: 11px; }}
    h1 {{ font-size: 22px; }}
    h2 {{ font-size: 17px; margin-top: 16px; }}
    table {{ font-size: 10px; }}
    th, td {{ padding: 4px 6px; }}
    .no-print {{ display: none; }}
    @page {{
      size: A4 landscape;
      margin: 15mm;
    }}
  }}
</style>
</head>
<body>
{body}
<div class="footer">
  Generated by Nutanix MCP Server &mdash; {timestamp}
</div>
</body>
</html>"""


def _markdown_to_html_body(markdown: str) -> str:
    """Convert Markdown to HTML body content.

    Handles: headings, tables, lists, code blocks, mermaid blocks,
    bold, inline code, horizontal rules, and paragraphs.
    """
    lines = markdown.split("\n")
    html_parts: list[str] = []
    i = 0
    in_table = False
    in_list = False

    while i < len(lines):
        line = lines[i]

        # Mermaid code blocks
        if line.strip() == "```mermaid":
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            mermaid_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                mermaid_lines.append(lines[i])
                i += 1
            html_parts.append(f'<div class="mermaid">\n' + "\n".join(mermaid_lines) + "\n</div>")
            i += 1
            continue

        # Regular code blocks
        if line.strip().startswith("```"):
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(html.escape(lines[i]))
                i += 1
            html_parts.append("<pre><code>" + "\n".join(code_lines) + "</code></pre>")
            i += 1
            continue

        # Horizontal rule
        if line.strip() == "---":
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("<hr>")
            i += 1
            continue

        # Headings
        if line.startswith("#"):
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            level = len(line) - len(line.lstrip("#"))
            level = min(level, 6)
            text = _inline_format(line.lstrip("#").strip())
            html_parts.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # Table rows
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().split("|")[1:-1]]

            # Skip separator rows
            if all(c.replace("-", "").replace(":", "") == "" for c in cells):
                i += 1
                continue

            if not in_table:
                in_table = True
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append("<table><thead><tr>")
                for cell in cells:
                    html_parts.append(f"<th>{_inline_format(cell)}</th>")
                html_parts.append("</tr></thead><tbody>")
                i += 1
                continue

            html_parts.append("<tr>")
            for cell in cells:
                html_parts.append(f"<td>{_inline_format(cell)}</td>")
            html_parts.append("</tr>")
            i += 1
            continue

        # End table if no longer in table rows
        if in_table and not line.strip().startswith("|"):
            html_parts.append("</tbody></table>")
            in_table = False

        # List items
        if line.strip().startswith("- "):
            if not in_list:
                in_list = True
                html_parts.append("<ul>")
            text = _inline_format(line.strip()[2:])
            html_parts.append(f"<li>{text}</li>")
            i += 1
            continue

        if in_list and not line.strip().startswith("- "):
            html_parts.append("</ul>")
            in_list = False

        # Empty lines
        if not line.strip():
            i += 1
            continue

        # Regular paragraphs
        text = _inline_format(line.strip())
        html_parts.append(f"<p>{text}</p>")
        i += 1

    if in_table:
        html_parts.append("</tbody></table>")
    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _inline_format(text: str) -> str:
    """Apply inline Markdown formatting (bold, inline code)."""
    import re as _re

    # Inline code
    text = _re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Bold
    text = _re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_generate_asbuilt(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Generate a full AsBuilt report from a Prism Element cluster."""
    pe_host = arguments["pe_host"]
    requested = arguments.get("sections") or ALL_SECTIONS

    # Validate sections
    invalid = [s for s in requested if s not in ALL_SECTIONS]
    if invalid:
        return {
            "error": f"Invalid sections: {invalid}",
            "validSections": ALL_SECTIONS,
        }

    sections = [s for s in ALL_SECTIONS if s in requested]

    # Collect data for each requested section
    data: dict[str, Any] = {}
    errors: dict[str, str] = {}

    # Overview is needed for topology diagram even if not explicitly requested
    collect_overview = "overview" in sections or "hosts" in sections
    if collect_overview:
        try:
            data["overview"] = await _collect_overview(client, pe_host)
        except Exception as e:
            errors["overview"] = str(e)
            data["overview"] = {"name": pe_host, "uuid": "", "version": "N/A", "numNodes": 0}

    collectors = {
        "hosts": _collect_hosts,
        "vms": _collect_vms,
        "networks": _collect_networks,
        "protection_domains": _collect_protection_domains,
    }

    for section_name, collector_fn in collectors.items():
        if section_name in sections:
            try:
                data[section_name] = await collector_fn(client, pe_host)
            except Exception as e:
                errors[section_name] = str(e)

    if "storage" in sections:
        try:
            data["storage"] = await _collect_storage(client, pe_host)
        except Exception as e:
            errors["storage"] = str(e)

    if "alerts" in sections:
        try:
            data["alerts"] = await _collect_alerts(client, pe_host)
        except Exception as e:
            errors["alerts"] = str(e)

    if "health" in sections:
        try:
            data["health"] = await _collect_health(client, pe_host)
        except Exception as e:
            errors["health"] = str(e)

    cluster_name = data.get("overview", {}).get("name", pe_host)
    markdown = _generate_markdown(cluster_name, pe_host, data, sections)

    result: dict[str, Any] = {
        "clusterName": cluster_name,
        "peHost": pe_host,
        "sectionsIncluded": sections,
        "markdown": markdown,
    }

    if errors:
        result["sectionErrors"] = errors

    # Include raw data for Excalidraw diagram generation by the AI
    result["topologyData"] = {
        "cluster": data.get("overview", {}),
        "hosts": data.get("hosts", []),
        "vmCount": len(data.get("vms", [])),
        "networkCount": len(data.get("networks", [])),
    }

    return result


async def handle_export_asbuilt_html(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Convert Markdown report to self-contained HTML with print CSS."""
    markdown = arguments["markdown"]
    title = arguments.get("title", "Nutanix AsBuilt Report")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    body_html = _markdown_to_html_body(markdown)

    full_html = HTML_TEMPLATE.format(
        title=html.escape(title),
        body=body_html,
        timestamp=now,
    )

    return {
        "html": full_html,
        "title": title,
        "note": (
            "Open this HTML in a browser and use Ctrl+P (Cmd+P on Mac) to save as PDF. "
            "The print CSS is optimized for A4 landscape with proper page breaks."
        ),
    }


async def handle_get_project_architecture(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the project architecture documentation."""
    from nutanix_mcp.resources import _project_architecture_doc

    return {
        "markdown": _project_architecture_doc(),
        "note": "This is the Nutanix MCP Server project architecture. Use export_asbuilt_html to convert to PDF.",
    }


ASBUILT_HANDLERS: dict[str, Any] = {
    "generate_asbuilt": handle_generate_asbuilt,
    "export_asbuilt_html": handle_export_asbuilt_html,
    "get_project_architecture": handle_get_project_architecture,
}
