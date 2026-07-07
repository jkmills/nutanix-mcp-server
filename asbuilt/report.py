"""AsBuilt report generation from Nutanix MCP tool outputs.

Collectors call the MCP server's pe_* tools through a caller-supplied
``call_tool`` coroutine (``async (tool_name, arguments) -> dict``) and
shape the results for the Markdown renderers. The renderers produce a
report with tables and a Mermaid topology diagram; ``render_html``
wraps it in a self-contained page with an interactive TOC and print CSS.
"""

import html
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

ToolCaller = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]

ALL_SECTIONS = [
    "overview",
    "system",
    "hosts",
    "vms",
    "networks",
    "storage",
    "protection_domains",
    "alerts",
    "health",
]

# ─── Nutanix API Value Mappings ────────────────────────────────────────────────

HYPERVISOR_NAMES: dict[str, str] = {
    "kKvm": "AHV",
    "kVMware": "ESXi",
    "kHyperv": "Hyper-V",
    "kXen": "Xen",
    "AHV": "AHV",
    "ESXi": "ESXi",
}

STORAGE_TYPE_NAMES: dict[str, str] = {
    "all_flash": "All Flash",
    "hybrid": "Hybrid (SSD + HDD)",
    "all_hdd": "All HDD",
    "DAS-SATA": "DAS-SATA",
}


def _friendly_hypervisor(raw: str | None) -> str:
    """Map API hypervisor type to friendly display name."""
    if not raw:
        return "Unknown"
    return HYPERVISOR_NAMES.get(raw, raw)


def _friendly_storage_type(raw: str | None) -> str:
    """Map API storage type to friendly display name."""
    if not raw:
        return "Unknown"
    return STORAGE_TYPE_NAMES.get(raw, raw)


def _strip_k_prefix(value: str | None) -> str:
    """Strip Nutanix 'k' prefix from enum values (kInfo → Info, kWarning → Warning)."""
    if not value:
        return value or ""
    if len(value) > 1 and value[0] == "k" and value[1].isupper():
        return value[1:]
    return value


# ─── Collectors (consume MCP tool outputs) ────────────────────────────────────


async def _collect_overview(call_tool: ToolCaller, pe_host: str) -> dict[str, Any]:
    """Collect cluster overview via pe_get_cluster_info."""
    info = await call_tool("pe_get_cluster_info", {"pe_host": pe_host})
    return {
        "name": info.get("name") or "Unknown",
        "uuid": info.get("clusterUuid") or "",
        "version": info.get("version") or "",
        "nccVersion": info.get("nccVersion") or "",
        "numNodes": info.get("numNodes") or 0,
        "storageType": _friendly_storage_type(info.get("storageType")),
        "hypervisorTypes": [_friendly_hypervisor(h) for h in (info.get("hypervisorTypes") or [])],
        "externalIp": info.get("clusterExternalIp") or "",
        "externalDataServicesIp": info.get("externalDataServicesIp") or "",
        "externalSubnet": info.get("externalSubnet") or "",
        "internalSubnet": info.get("internalSubnet") or "",
        "nameServers": info.get("nameServers") or [],
        "ntpServers": info.get("ntpServers") or [],
        "timezone": info.get("timezone") or "",
        "operationMode": info.get("operationMode") or "",
        "clusterRedundancyFactor": info.get("redundancyFactor") or "",
        "faultToleranceDomainType": info.get("faultToleranceDomainType") or "",
    }


async def _collect_hosts(call_tool: ToolCaller, pe_host: str) -> list[dict]:
    """Collect host inventory via pe_list_hosts."""
    result = await call_tool("pe_list_hosts", {"pe_host": pe_host})
    hosts = []
    for h in result.get("hosts") or []:
        hosts.append(
            {
                **h,
                "name": h.get("name") or "",
                "uuid": h.get("uuid") or "",
                "hypervisorType": _friendly_hypervisor(h.get("hypervisorType")),
                "cpuCapacityGhz": h.get("cpuCapacityGhz") or 0,
                "memoryCapacityGb": h.get("memoryCapacityGb") or 0,
                "numCpuSockets": h.get("numCpuSockets") or 0,
                "numCpuCores": h.get("numCpuCores") or 0,
                "numVms": h.get("numVms") or 0,
            }
        )
    return hosts


async def _collect_host_disks(
    call_tool: ToolCaller, pe_host: str, hosts: list[dict]
) -> dict[str, list[dict]]:
    """Collect per-host physical disk inventory via pe_get_host_disks."""
    host_disks: dict[str, list[dict]] = {}
    for h in hosts:
        host_uuid = h.get("uuid", "")
        if not host_uuid:
            continue
        try:
            result = await call_tool("pe_get_host_disks", {"pe_host": pe_host, "host_uuid": host_uuid})
            host_disks[host_uuid] = [
                {
                    "location": d.get("location") or "",
                    "id": d.get("id") or "",
                    "serial": d.get("serialNumber") or "",
                    "model": d.get("model") or "",
                    "vendor": d.get("vendor") or "",
                    "firmware": d.get("firmware") or "",
                    "tier": _strip_k_prefix(d.get("storageTierName") or ""),
                    "capacityTb": round((d.get("capacityBytes") or 0) / (1024**4), 2),
                    "status": d.get("diskStatus") or "",
                    "online": d.get("onlineStatus", True),
                }
                for d in result.get("disks") or []
            ]
        except Exception:
            pass
    return host_disks


async def _collect_vms(call_tool: ToolCaller, pe_host: str) -> list[dict]:
    """Collect VM inventory via pe_list_vms with disk config."""
    result = await call_tool("pe_list_vms", {"pe_host": pe_host, "include_disk_config": True})
    return [
        {
            "name": vm.get("name") or "",
            "uuid": vm.get("uuid") or "",
            "powerState": vm.get("powerState") or "",
            "numVcpus": vm.get("numVcpus") or 0,
            "memoryMb": vm.get("memoryMb") or 0,
            "hostUuid": vm.get("hostUuid") or "",
            "ipAddresses": vm.get("ipAddresses") or [],
            "diskCapacityGb": vm.get("diskCapacityGb", 0),
        }
        for vm in result.get("vms") or []
    ]


async def _collect_networks(call_tool: ToolCaller, pe_host: str) -> list[dict]:
    """Collect network configuration via pe_list_networks."""
    result = await call_tool("pe_list_networks", {"pe_host": pe_host})
    networks = []
    for n in result.get("networks") or []:
        ip_config = n.get("ipConfig") or {}
        addr = ip_config.get("networkAddress") or ""
        prefix = ip_config.get("prefixLength") or ""
        subnet = f"{addr}/{prefix}" if addr and prefix else ""
        networks.append(
            {
                "name": n.get("name") or "",
                "uuid": n.get("uuid") or "",
                "vlanId": n.get("vlanId"),
                "networkType": "Managed" if ip_config else "Unmanaged",
                "subnet": subnet,
            }
        )
    return networks


async def _collect_storage(call_tool: ToolCaller, pe_host: str) -> dict[str, Any]:
    """Collect storage configuration via container/pool/disk tools."""
    containers_result = await call_tool("pe_list_containers", {"pe_host": pe_host})
    pools_result = await call_tool("pe_list_storage_pools", {"pe_host": pe_host})
    disks_result = await call_tool("pe_list_disks", {"pe_host": pe_host})

    return {
        "containers": [
            {
                "name": c.get("name") or "",
                "uuid": c.get("containerUuid") or "",
                "maxCapacityTb": round((c.get("maxCapacityBytes") or 0) / (1024**4), 2),
                "replicationFactor": c.get("replicationFactor") or "",
                "compressionEnabled": c.get("compressionEnabled") or False,
                "dedupEnabled": c.get("dedupEnabled"),
                "erasureCoded": c.get("erasureCoded") or False,
            }
            for c in containers_result.get("containers") or []
        ],
        "pools": [
            {
                "name": sp.get("name") or "",
                "uuid": sp.get("uuid") or "",
                "capacityTb": round((sp.get("capacityBytes") or 0) / (1024**4), 2),
                "numDisks": sp.get("numDisks") or 0,
            }
            for sp in pools_result.get("storagePools") or []
        ],
        "diskSummary": _summarize_disks(disks_result.get("disks") or []),
    }


def _summarize_disks(disks: list[dict]) -> dict:
    """Summarize disk tiers and counts from pe_list_disks output."""
    tiers: dict[str, dict] = {}
    for d in disks:
        tier = _strip_k_prefix(d.get("storageTierName") or "Unknown")
        if tier not in tiers:
            tiers[tier] = {"count": 0, "totalCapacityTb": 0.0}
        tiers[tier]["count"] += 1
        tiers[tier]["totalCapacityTb"] += (d.get("capacityBytes") or 0) / (1024**4)

    for tier_data in tiers.values():
        tier_data["totalCapacityTb"] = round(tier_data["totalCapacityTb"], 2)

    return {"tiers": tiers, "totalDisks": len(disks)}


async def _collect_system(call_tool: ToolCaller, pe_host: str) -> dict[str, Any]:
    """Collect system configuration via the pe_get_* config tools."""
    system: dict[str, Any] = {}
    args = {"pe_host": pe_host}

    try:
        auth = await call_tool("pe_get_auth_config", args)
        system["auth"] = {
            "authTypes": auth.get("authTypes") or [],
            "directories": [
                {
                    "name": d.get("name") or "",
                    "type": d.get("directoryType") or "",
                    "domain": d.get("domain") or "",
                    "url": d.get("directoryUrl") or "",
                }
                for d in auth.get("directories") or []
            ],
        }
    except Exception:
        pass

    try:
        smtp = await call_tool("pe_get_smtp_config", args)
        if smtp and smtp.get("address"):
            system["smtp"] = {
                "address": smtp.get("address") or "",
                "port": smtp.get("port") or "",
                "secureMode": smtp.get("secureMode") or "",
                "fromEmail": smtp.get("fromEmailAddress") or "",
            }
    except Exception:
        pass

    try:
        snmp = await call_tool("pe_get_snmp_config", args)
        if snmp and snmp.get("enabled"):
            system["snmp"] = {
                "enabled": snmp.get("enabled", False),
                "traps": len(snmp.get("traps") or []),
                "users": len(snmp.get("users") or []),
            }
    except Exception:
        pass

    try:
        syslog = await call_tool("pe_get_syslog_config", args)
        if syslog.get("count"):
            system["syslog"] = {"serverCount": syslog["count"]}
    except Exception:
        pass

    try:
        license_info = await call_tool("pe_get_licensing_info", args)
        system["license"] = {"category": license_info.get("category") or "Unknown"}
    except Exception:
        pass

    try:
        images_result = await call_tool("pe_list_images", args)
        system["images"] = [
            {
                "name": img.get("name") or "",
                "type": img.get("imageType") or "",
                "state": img.get("imageState") or "",
                "sizeGb": round((img.get("sizeMb") or 0) / 1024, 1),
            }
            for img in images_result.get("images") or []
        ]
    except Exception:
        pass

    try:
        nfs = await call_tool("pe_get_nfs_whitelists", args)
        wl = nfs.get("whitelists") or []
        if wl:
            system["nfsWhitelist"] = wl
    except Exception:
        pass

    return system


async def _collect_protection_domains(call_tool: ToolCaller, pe_host: str) -> dict[str, Any]:
    """Collect protection domains, remote sites, and unprotected VMs."""
    args = {"pe_host": pe_host}
    pd_result = await call_tool("pe_list_protection_domains", args)

    pds = [
        {
            "name": pd.get("name") or "",
            "active": pd.get("active") or False,
            "vmCount": pd.get("vmCount") or 0,
            "cronSchedules": len(pd.get("cronSchedules") or []),
            "replicationLinks": [
                {"remoteSite": rl.get("remote_site_name") or rl.get("remoteSite") or ""}
                for rl in pd.get("replicationLinks") or []
            ],
        }
        for pd in pd_result.get("protectionDomains") or []
    ]

    remote_sites: list[dict] = []
    try:
        rs_result = await call_tool("pe_list_remote_sites", args)
        for rs in rs_result.get("remoteSites") or []:
            remote_sites.append(
                {
                    "name": rs.get("name") or "",
                    "remoteAddresses": rs.get("remoteIpPorts") or {},
                    "capabilities": rs.get("capabilities") or [],
                    "metroReady": rs.get("metroReady") or False,
                    "compressOnWire": rs.get("compressOnWire") or False,
                    "bandwidthThrottling": rs.get("bandwidthPolicyEnabled") or False,
                }
            )
    except Exception:
        pass

    unprotected_vms: list[dict] = []
    try:
        up_result = await call_tool("pe_list_unprotected_vms", args)
        for vm in up_result.get("unprotectedVms") or []:
            if (vm.get("powerState") or "").lower() == "on":
                unprotected_vms.append(
                    {
                        "name": vm.get("name") or "",
                        "powerState": vm.get("powerState") or "",
                        "numVcpus": vm.get("numVcpus") or 0,
                        "memoryMb": vm.get("memoryMb") or 0,
                    }
                )
    except Exception:
        pass

    return {
        "domains": pds,
        "remoteSites": remote_sites,
        "unprotectedVms": unprotected_vms,
    }


async def _collect_alerts(call_tool: ToolCaller, pe_host: str) -> dict[str, Any]:
    """Collect active alert summary via pe_list_alerts."""
    result = await call_tool("pe_list_alerts", {"pe_host": pe_host, "count": 100})
    alerts = result.get("alerts") or []

    severity_counts: dict[str, int] = {}
    for a in alerts:
        sev = _strip_k_prefix(a.get("severity") or "UNKNOWN")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return {
        "totalActive": len(alerts),
        "bySeverity": severity_counts,
        "recent": [
            {
                "title": a.get("alertTitle") or "",
                "severity": _strip_k_prefix(a.get("severity") or ""),
                "message": (a.get("message") or "")[:120],
            }
            for a in alerts[:10]
        ],
    }


async def _collect_health(call_tool: ToolCaller, pe_host: str) -> dict[str, Any]:
    """Collect health check results via pe_list_health_checks."""
    result = await call_tool("pe_list_health_checks", {"pe_host": pe_host})
    checks = result.get("healthChecks") or []

    status_counts: dict[str, int] = {}
    failed_checks: list[dict] = []
    for check in checks:
        status = check.get("lastExecutionStatus") or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1
        if status in ("FAIL", "WARN", "ERROR"):
            failed_checks.append(
                {
                    "name": check.get("name") or "",
                    "description": check.get("description") or "",
                    "status": status,
                }
            )

    return {
        "totalChecks": len(checks),
        "byStatus": status_counts,
        "failedChecks": failed_checks[:20],
    }


async def collect_report_data(
    call_tool: ToolCaller,
    pe_host: str,
    sections: list[str],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Collect all requested report sections. Returns (data, per-section errors)."""
    data: dict[str, Any] = {}
    errors: dict[str, str] = {}

    # Overview is needed for the topology diagram even if not requested
    if "overview" in sections or "hosts" in sections:
        try:
            data["overview"] = await _collect_overview(call_tool, pe_host)
        except Exception as e:
            errors["overview"] = str(e)
            data["overview"] = {"name": pe_host, "uuid": "", "version": "N/A", "numNodes": 0}

    simple_collectors: dict[str, Any] = {
        "hosts": _collect_hosts,
        "vms": _collect_vms,
        "networks": _collect_networks,
        "storage": _collect_storage,
        "system": _collect_system,
        "protection_domains": _collect_protection_domains,
        "alerts": _collect_alerts,
        "health": _collect_health,
    }
    for section_name, collector_fn in simple_collectors.items():
        if section_name in sections:
            try:
                data[section_name] = await collector_fn(call_tool, pe_host)
            except Exception as e:
                errors[section_name] = str(e)

    if "hosts" in sections and "hosts" in data:
        try:
            data["host_disks"] = await _collect_host_disks(call_tool, pe_host, data["hosts"])
        except Exception as e:
            errors["host_disks"] = str(e)

    return data, errors


# ─── Markdown Report Generation ──────────────────────────────────────────────


def render_markdown(
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

    if "system" in sections and "system" in data:
        lines.extend(_section_system(data["system"]))

    if "hosts" in sections and "hosts" in data:
        lines.extend(_section_hosts(data["hosts"], data.get("host_disks")))

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
    rf = overview.get("clusterRedundancyFactor", "")
    rf_display = f"RF {rf}" if rf else "N/A"
    ft_domain = overview.get("faultToleranceDomainType") or "N/A"

    lines = [
        "## Cluster Overview",
        "",
        "### Hardware",
        "",
        "| Property | Value |",
        "|----------|-------|",
        f"| **Cluster Name** | {overview['name']} |",
        f"| **Cluster UUID** | `{overview['uuid']}` |",
        f"| **AOS Version** | {overview['version']} |",
        f"| **NCC Version** | {overview.get('nccVersion') or 'N/A'} |",
        f"| **Node Count** | {overview['numNodes']} |",
        f"| **Storage Type** | {overview.get('storageType') or 'N/A'} |",
        f"| **Hypervisor** | {', '.join(overview.get('hypervisorTypes') or [])} |",
        f"| **Redundancy Factor** | {rf_display} |",
        f"| **Fault Tolerance Domain** | {ft_domain} |",
        f"| **Timezone** | {overview.get('timezone') or 'N/A'} |",
        "",
        "### Network",
        "",
        "| Property | Value |",
        "|----------|-------|",
        f"| **Virtual IP (VIP)** | {overview.get('externalIp') or 'N/A'} |",
        f"| **iSCSI Data Services IP** | {overview.get('externalDataServicesIp') or 'N/A'} |",
        f"| **External Subnet** | {overview.get('externalSubnet') or 'N/A'} |",
        f"| **Internal Subnet** | {overview.get('internalSubnet') or 'N/A'} |",
        f"| **DNS Servers** | {', '.join(overview.get('nameServers') or []) or 'N/A'} |",
        f"| **NTP Servers** | {', '.join(overview.get('ntpServers') or []) or 'N/A'} |",
        "",
    ]
    return lines


def _section_system(system: dict) -> list[str]:
    """Generate the system configuration section."""
    lines = ["## System Configuration", ""]

    lic = system.get("license")
    if lic:
        lines.extend([
            "### Licensing",
            "",
            f"- **License Type:** {lic.get('category', 'Unknown')}",
            "",
        ])

    auth = system.get("auth")
    if auth:
        auth_types = ", ".join(auth.get("authTypes") or []) or "N/A"
        lines.extend(["### Authentication", "", f"- **Auth Types:** {auth_types}", ""])
        dirs = auth.get("directories") or []
        if dirs:
            lines.extend([
                "| Directory Name | Type | Domain | URL |",
                "|---------------|------|--------|-----|",
            ])
            for d in dirs:
                lines.append(
                    f"| {d['name']} | {d['type']} | {d['domain']} | {d['url']} |"
                )
            lines.append("")

    smtp = system.get("smtp")
    if smtp:
        lines.extend([
            "### SMTP Configuration",
            "",
            f"- **Server:** {smtp['address']}:{smtp['port']}",
            f"- **Secure Mode:** {smtp.get('secureMode') or 'None'}",
            f"- **From Email:** {smtp.get('fromEmail') or 'N/A'}",
            "",
        ])

    snmp = system.get("snmp")
    if snmp:
        lines.extend([
            "### SNMP Configuration",
            "",
            f"- **Enabled:** {'✅' if snmp.get('enabled') else '❌'}",
            f"- **Trap Destinations:** {snmp.get('traps', 0)}",
            f"- **Users:** {snmp.get('users', 0)}",
            "",
        ])

    syslog = system.get("syslog")
    if syslog:
        lines.extend([
            "### Syslog Configuration",
            "",
            f"- **Remote Servers:** {syslog.get('serverCount', 0)}",
            "",
        ])

    nfs_wl = system.get("nfsWhitelist")
    if nfs_wl:
        lines.extend([
            "### Global Filesystem Whitelists",
            "",
            "- " + ", ".join(f"`{w}`" for w in nfs_wl),
            "",
        ])

    images = system.get("images")
    if images:
        lines.extend([
            "### Image Library",
            "",
            f"**Total Images:** {len(images)}",
            "",
            "| Image Name | Type | State | Size (GB) |",
            "|-----------|------|-------|-----------|",
        ])
        for img in images:
            lines.append(
                f"| {img['name']} | {img['type']} | {img['state']} | {img['sizeGb']} |"
            )
        lines.append("")

    return lines


def _section_hosts(hosts: list[dict], host_disks: dict[str, list[dict]] | None = None) -> list[str]:
    """Generate the host inventory section with per-host detail cards."""
    lines = [
        "## Host Inventory",
        "",
        f"**Total Hosts:** {len(hosts)}",
        "",
    ]

    total_cores = sum(h.get("numCpuCores", 0) for h in hosts)
    total_cpu_ghz = sum(h.get("cpuCapacityGhz", 0) for h in hosts)
    total_ram = sum(h.get("memoryCapacityGb", 0) for h in hosts)
    total_vms = sum(h.get("numVms", 0) for h in hosts)
    lines.extend([
        "### Resource Summary",
        "",
        f"- **Total CPU Cores:** {total_cores} ({round(total_cpu_ghz, 1)} GHz)",
        f"- **Total RAM:** {total_ram} GB ({round(total_ram / 1024, 1)} TB)",
        f"- **Total VMs:** {total_vms}",
        "",
    ])

    for h in hosts:
        lines.extend([
            f"### {h['name']}",
            "",
            "#### Hardware",
            "",
            "| Property | Value |",
            "|----------|-------|",
            f"| **Node Serial** | {h.get('serial') or 'N/A'} |",
            f"| **Block Model** | {h.get('blockModel') or 'N/A'} |",
            f"| **Block Serial** | {h.get('blockSerial') or 'N/A'} |",
            f"| **CPU Model** | {h.get('cpuModel') or 'N/A'} |",
            f"| **CPU Sockets** | {h.get('numCpuSockets', 0)} |",
            f"| **CPU Cores** | {h.get('numCpuCores', 0)} |",
            f"| **CPU Capacity** | {h.get('cpuCapacityGhz', 0)} GHz |",
            f"| **RAM** | {h.get('memoryCapacityGb', 0)} GB |",
            f"| **Hypervisor** | {h.get('hypervisorType') or 'N/A'} |",
            f"| **Hypervisor Version** | {h.get('hypervisorVersion') or 'N/A'} |",
            f"| **BMC Version** | {h.get('bmcVersion') or 'N/A'} |",
            f"| **BIOS Version** | {h.get('biosVersion') or 'N/A'} |",
            f"| **VMs Running** | {h.get('numVms', 0)} |",
            "",
            "#### Network",
            "",
            "| Interface | IP Address |",
            "|-----------|-----------|",
            f"| **Hypervisor** | {h.get('hypervisorAddress') or 'N/A'} |",
            f"| **CVM** | {h.get('cvmAddress') or 'N/A'} |",
            f"| **IPMI/BMC** | {h.get('ipmiAddress') or 'N/A'} |",
            "",
        ])

        uuid = h.get("uuid", "")
        disks = (host_disks or {}).get(uuid, [])
        if disks:
            lines.extend([
                "#### Disks",
                "",
                f"**Disks on this host:** {len(disks)}",
                "",
                "| Location | Tier | Model | Serial | Firmware | Capacity (TB) | Status |",
                "|----------|------|-------|--------|----------|--------------|--------|",
            ])
            for d in disks:
                status = "🟢 Online" if d.get("online", True) else "🔴 Offline"
                lines.append(
                    f"| {d.get('location', '')} | {d.get('tier', '')} | {d.get('model', '')} | "
                    f"{d.get('serial', '')} | {d.get('firmware', '')} | {d.get('capacityTb', 0)} | {status} |"
                )
            lines.append("")

    return lines


def _section_vms(vms: list[dict]) -> list[str]:
    """Generate the VM inventory section."""
    powered_on = [v for v in vms if (v.get("powerState") or "").lower() == "on"]
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
            f"| {n['name']} | {n.get('vlanId', '—')} | {n['networkType']} | {n.get('subnet', '—') or '—'} |"
        )
    lines.append("")
    return lines


def _section_storage(storage: dict) -> list[str]:
    """Generate the storage section."""
    lines = [
        "## Storage Configuration",
        "",
    ]

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


def _section_protection_domains(pd_data: dict | list) -> list[str]:
    """Generate the protection domains section."""
    if isinstance(pd_data, list):
        pds = pd_data
        remote_sites: list[dict] = []
        unprotected_vms: list[dict] = []
    else:
        pds = pd_data.get("domains", [])
        remote_sites = pd_data.get("remoteSites", [])
        unprotected_vms = pd_data.get("unprotectedVms", [])

    lines = [
        "## Data Protection",
        "",
        f"**Total Protection Domains:** {len(pds)}",
        "",
        "| PD Name | Active | VMs | Schedules | Remote Sites |",
        "|---------|--------|-----|-----------|--------------|",
    ]
    for pd in pds:
        rs_names = ", ".join(rl.get("remoteSite", "") for rl in pd.get("replicationLinks", []))
        lines.append(
            f"| {pd['name']} | {'✅' if pd['active'] else '❌'} | "
            f"{pd['vmCount']} | {pd['cronSchedules']} | {rs_names or '—'} |"
        )
    lines.append("")

    if remote_sites:
        lines.extend([
            "### Remote Sites",
            "",
            "| Site Name | Metro Ready | Compress on Wire | Bandwidth Throttle |",
            "|-----------|-------------|-----------------|-------------------|",
        ])
        for rs in remote_sites:
            lines.append(
                f"| {rs['name']} | {'✅' if rs.get('metroReady') else '❌'} | "
                f"{'✅' if rs.get('compressOnWire') else '❌'} | "
                f"{'✅' if rs.get('bandwidthThrottling') else '❌'} |"
            )
        lines.append("")

    if unprotected_vms:
        lines.extend([
            "### Unprotected VMs (powered on)",
            "",
            f"**Count:** {len(unprotected_vms)}",
            "",
            "| VM Name | vCPUs | RAM (MB) |",
            "|---------|-------|----------|",
        ])
        for vm in unprotected_vms[:30]:
            lines.append(f"| {vm['name']} | {vm['numVcpus']} | {vm['memoryMb']} |")
        if len(unprotected_vms) > 30:
            lines.append(f"| *...and {len(unprotected_vms) - 30} more* | | |")
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
    """Generate a Mermaid topology diagram with distinct shapes."""
    cluster_name = overview.get("name", "Cluster")
    version = overview.get("version", "")
    hyp = ", ".join(overview.get("hypervisorTypes") or [])
    storage_type = overview.get("storageType", "")
    num_nodes = overview.get("numNodes", 0)

    lines = [
        "## Cluster Topology",
        "",
        "```mermaid",
        "graph TD",
        '    PC(["☁️ Prism Central"]):::pcStyle',
        f'    CLUSTER{{"🏢 {cluster_name}<br/>'
        f"AOS {version} | {hyp}<br/>"
        f'{storage_type} | {num_nodes} Nodes"}}:::clusterStyle',
        "    PC --- CLUSTER",
        "",
    ]
    for i, h in enumerate(hosts):
        host_id = f"H{i}"
        name = h.get("name", "")
        ip = h.get("hypervisorAddress", "")
        cores = h.get("numCpuCores", 0)
        sockets = h.get("numCpuSockets", 0)
        ram = h.get("memoryCapacityGb", 0)
        model = h.get("blockModel") or ""
        lines.append(
            f'    {host_id}["🖥️ {name}<br/>'
            f"{ip}<br/>"
            f"CPU: {sockets}S / {cores}C<br/>"
            f'RAM: {ram} GB<br/>'
            f'{model}"]:::hostStyle'
        )
        lines.append(f"    CLUSTER --- {host_id}")

    lines.extend([
        "",
        "    classDef pcStyle fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#1e1b4b",
        "    classDef clusterStyle fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f",
        "    classDef hostStyle fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#064e3b",
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
    --toc-width: 260px;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: var(--text);
    background: var(--bg);
    line-height: 1.6;
    padding: 40px 40px 40px calc(var(--toc-width) + 60px);
    max-width: calc(1100px + var(--toc-width) + 60px);
    margin: 0 auto;
  }}
  /* ─── Table of Contents Sidebar ─── */
  #toc {{
    position: fixed;
    top: 0;
    left: 0;
    width: var(--toc-width);
    height: 100vh;
    overflow-y: auto;
    background: #f8fafc;
    border-right: 1px solid var(--border);
    padding: 20px 16px;
    font-size: 13px;
    z-index: 100;
  }}
  #toc h3 {{
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}
  #toc ul {{ list-style: none; margin: 0; padding: 0; }}
  #toc li {{ margin-bottom: 2px; }}
  #toc a {{
    display: block;
    padding: 4px 8px;
    color: var(--text);
    text-decoration: none;
    border-radius: 4px;
    transition: background 0.15s;
  }}
  #toc a:hover {{ background: #e5e7eb; }}
  #toc a.active {{
    background: #dbeafe;
    color: var(--primary);
    font-weight: 600;
  }}
  #toc .toc-h3 {{ padding-left: 20px; font-size: 12px; color: #6b7280; }}
  #toc .toc-h4 {{ padding-left: 32px; font-size: 11px; color: #9ca3af; }}
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
  h4 {{
    font-size: 15px;
    margin-top: 14px;
    margin-bottom: 6px;
    color: #374151;
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
    #toc {{ display: none; }}
    body {{ padding: 20px; font-size: 11px; max-width: none; }}
    h1 {{ font-size: 22px; }}
    h2 {{ font-size: 17px; margin-top: 16px; }}
    h3 {{ font-size: 14px; margin-top: 12px; }}
    h4 {{ font-size: 12px; margin-top: 10px; }}
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
<nav id="toc"><h3>Contents</h3><ul id="toc-list"></ul></nav>
{body}
<div class="footer">
  Generated by the Nutanix MCP AsBuilt tool &mdash; {timestamp}
</div>
<script>
(function() {{
  // Build TOC from headings
  var headings = document.querySelectorAll('h2, h3, h4');
  var tocList = document.getElementById('toc-list');
  var tocItems = [];
  headings.forEach(function(h, idx) {{
    var id = 'section-' + idx;
    h.id = id;
    var li = document.createElement('li');
    var a = document.createElement('a');
    a.href = '#' + id;
    a.textContent = h.textContent;
    a.dataset.target = id;
    if (h.tagName === 'H3') a.className = 'toc-h3';
    if (h.tagName === 'H4') a.className = 'toc-h4';
    li.appendChild(a);
    tocList.appendChild(li);
    tocItems.push({{ el: h, link: a }});
  }});
  // Highlight active section on scroll
  var ticking = false;
  window.addEventListener('scroll', function() {{
    if (!ticking) {{
      window.requestAnimationFrame(function() {{
        var scrollY = window.scrollY + 80;
        var active = null;
        for (var i = tocItems.length - 1; i >= 0; i--) {{
          if (tocItems[i].el.offsetTop <= scrollY) {{ active = i; break; }}
        }}
        tocItems.forEach(function(item) {{ item.link.classList.remove('active'); }});
        if (active !== null) tocItems[active].link.classList.add('active');
        ticking = false;
      }});
      ticking = true;
    }}
  }});
}})();
</script>
</body>
</html>"""


def render_html(markdown: str, title: str = "Nutanix AsBuilt Report") -> str:
    """Convert a Markdown report to a self-contained HTML page."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body_html = _markdown_to_html_body(markdown)
    return HTML_TEMPLATE.format(
        title=html.escape(title),
        body=body_html,
        timestamp=now,
    )


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
            html_parts.append('<div class="mermaid">\n' + "\n".join(mermaid_lines) + "\n</div>")
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
