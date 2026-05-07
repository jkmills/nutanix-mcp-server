"""As-Built report generation tools for Nutanix environments.

Generates comprehensive Markdown documentation with Excalidraw diagrams
at three scope levels: full environment, cluster, and VM.
"""

from typing import Any, Optional
from datetime import datetime, timezone
import json

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

REPORT_TOOLS: list[dict] = [
    {
        "name": "generate_environment_report",
        "description": (
            "Generate a comprehensive As-Built report for the full Nutanix environment. "
            "Covers all clusters, hosts, storage, networking, and VM inventory registered "
            "with Prism Central. Returns Markdown with an Excalidraw topology diagram."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_vms": {
                    "type": "boolean",
                    "description": "Include full VM inventory in the report (default: true)",
                    "default": True,
                },
                "include_diagram": {
                    "type": "boolean",
                    "description": "Include Excalidraw topology diagram JSON (default: true)",
                    "default": True,
                },
            },
        },
    },
    {
        "name": "generate_cluster_report",
        "description": (
            "Generate a detailed As-Built report for one or more Nutanix clusters. "
            "Covers cluster configuration, hosts, storage containers, VMs, and networking. "
            "Returns Markdown with an Excalidraw cluster architecture diagram."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_uuids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of cluster UUIDs to report on. If empty, reports on all clusters.",
                },
                "include_diagram": {
                    "type": "boolean",
                    "description": "Include Excalidraw cluster diagram JSON (default: true)",
                    "default": True,
                },
            },
        },
    },
    {
        "name": "generate_vm_report",
        "description": (
            "Generate a detailed As-Built report for one or more VMs. "
            "Covers VM configuration, compute resources, disks, NICs, categories, "
            "and host placement. Returns Markdown with an Excalidraw VM layout diagram."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of VM UUIDs to report on (required).",
                },
                "include_diagram": {
                    "type": "boolean",
                    "description": "Include Excalidraw VM diagram JSON (default: true)",
                    "default": True,
                },
            },
            "required": ["vm_uuids"],
        },
    },
]


# ─── Helper functions ─────────────────────────────────────────────────────────


def _format_bytes(num_bytes: int | None) -> str:
    """Format bytes to human-readable string."""
    if num_bytes is None or num_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    value = float(num_bytes)
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{value:.2f} {units[idx]}"


def _now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _safe_get(d: dict, *keys, default="N/A"):
    """Safely navigate nested dicts."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, {})
        else:
            return default
    return d if d and d != {} else default


# ─── Excalidraw diagram generators ───────────────────────────────────────────


def _generate_environment_diagram(
    clusters: list[dict], hosts_by_cluster: dict[str, list[dict]]
) -> list[dict]:
    """Generate Excalidraw elements for environment topology."""
    elements = []
    elem_id = 100

    # Prism Central node (top center)
    pc_x, pc_y = 400, 50
    elements.append({
        "id": str(elem_id),
        "type": "rectangle",
        "x": pc_x, "y": pc_y,
        "width": 200, "height": 60,
        "strokeColor": "#1864ab",
        "backgroundColor": "#d0ebff",
        "fillStyle": "solid",
        "roundness": {"type": 3},
    })
    elem_id += 1
    elements.append({
        "id": str(elem_id),
        "type": "text",
        "x": pc_x + 20, "y": pc_y + 15,
        "width": 160, "height": 30,
        "text": "Prism Central",
        "fontSize": 16,
        "fontFamily": 1,
        "textAlign": "center",
    })
    elem_id += 1

    # Cluster nodes
    cluster_spacing = 300
    start_x = max(0, 400 - (len(clusters) - 1) * cluster_spacing // 2)
    cluster_y = 200

    for i, cluster in enumerate(clusters):
        cx = start_x + i * cluster_spacing
        cy = cluster_y
        cluster_name = cluster.get("name", f"Cluster {i+1}")
        cluster_id = cluster.get("extId", "")

        # Cluster box
        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": cx, "y": cy,
            "width": 220, "height": 60,
            "strokeColor": "#2b8a3e",
            "backgroundColor": "#d3f9d8",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        cluster_box_id = str(elem_id)
        elem_id += 1
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": cx + 10, "y": cy + 10,
            "width": 200, "height": 40,
            "text": cluster_name,
            "fontSize": 14,
            "fontFamily": 1,
            "textAlign": "center",
        })
        elem_id += 1

        # Connection line from PC to cluster
        elements.append({
            "id": str(elem_id),
            "type": "arrow",
            "x": pc_x + 100, "y": pc_y + 60,
            "width": cx + 110 - (pc_x + 100),
            "height": cy - (pc_y + 60),
            "points": [[0, 0], [cx + 110 - (pc_x + 100), cy - (pc_y + 60)]],
            "strokeColor": "#495057",
        })
        elem_id += 1

        # Host nodes under each cluster
        hosts = hosts_by_cluster.get(cluster_id, [])
        host_y = cy + 100
        host_spacing = 150
        host_start_x = cx - (len(hosts) - 1) * host_spacing // 2

        for j, host in enumerate(hosts[:6]):  # limit to 6 hosts per cluster
            hx = host_start_x + j * host_spacing
            hy = host_y
            host_name = host.get("name", f"Host {j+1}")

            elements.append({
                "id": str(elem_id),
                "type": "rectangle",
                "x": hx, "y": hy,
                "width": 130, "height": 45,
                "strokeColor": "#e67700",
                "backgroundColor": "#fff3bf",
                "fillStyle": "solid",
                "roundness": {"type": 3},
            })
            elem_id += 1
            elements.append({
                "id": str(elem_id),
                "type": "text",
                "x": hx + 5, "y": hy + 10,
                "width": 120, "height": 25,
                "text": host_name[:18],
                "fontSize": 11,
                "fontFamily": 1,
                "textAlign": "center",
            })
            elem_id += 1

            # Arrow from cluster to host
            elements.append({
                "id": str(elem_id),
                "type": "arrow",
                "x": cx + 110, "y": cy + 60,
                "width": hx + 65 - (cx + 110),
                "height": hy - (cy + 60),
                "points": [[0, 0], [hx + 65 - (cx + 110), hy - (cy + 60)]],
                "strokeColor": "#868e96",
            })
            elem_id += 1

    return elements


def _generate_cluster_diagram(
    cluster: dict, hosts: list[dict], vms: list[dict], containers: list[dict]
) -> list[dict]:
    """Generate Excalidraw elements for a single cluster architecture."""
    elements = []
    elem_id = 200

    cluster_name = cluster.get("name", "Cluster")

    # Cluster header
    elements.append({
        "id": str(elem_id),
        "type": "rectangle",
        "x": 50, "y": 30,
        "width": 900, "height": 50,
        "strokeColor": "#2b8a3e",
        "backgroundColor": "#d3f9d8",
        "fillStyle": "solid",
        "roundness": {"type": 3},
    })
    elem_id += 1
    elements.append({
        "id": str(elem_id),
        "type": "text",
        "x": 60, "y": 42,
        "width": 880, "height": 30,
        "text": f"Cluster: {cluster_name}",
        "fontSize": 18,
        "fontFamily": 1,
        "textAlign": "center",
    })
    elem_id += 1

    # Hosts row
    host_y = 120
    for i, host in enumerate(hosts[:8]):
        hx = 60 + i * 110
        host_name = host.get("name", f"Host {i+1}")
        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": hx, "y": host_y,
            "width": 100, "height": 50,
            "strokeColor": "#e67700",
            "backgroundColor": "#fff3bf",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elem_id += 1
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": hx + 5, "y": host_y + 12,
            "width": 90, "height": 26,
            "text": host_name[:14],
            "fontSize": 10,
            "fontFamily": 1,
            "textAlign": "center",
        })
        elem_id += 1

    # Storage containers row
    container_y = 210
    elements.append({
        "id": str(elem_id),
        "type": "text",
        "x": 60, "y": container_y - 20,
        "width": 200, "height": 20,
        "text": "Storage Containers",
        "fontSize": 12,
        "fontFamily": 1,
    })
    elem_id += 1

    for i, sc in enumerate(containers[:6]):
        sx = 60 + i * 140
        sc_name = sc.get("name", f"Container {i+1}")
        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": sx, "y": container_y,
            "width": 125, "height": 40,
            "strokeColor": "#5c940d",
            "backgroundColor": "#e9fac8",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elem_id += 1
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": sx + 5, "y": container_y + 10,
            "width": 115, "height": 20,
            "text": sc_name[:18],
            "fontSize": 10,
            "fontFamily": 1,
            "textAlign": "center",
        })
        elem_id += 1

    # VMs row (summary)
    vm_y = 300
    elements.append({
        "id": str(elem_id),
        "type": "text",
        "x": 60, "y": vm_y - 20,
        "width": 200, "height": 20,
        "text": f"VMs ({len(vms)} total)",
        "fontSize": 12,
        "fontFamily": 1,
    })
    elem_id += 1

    for i, vm in enumerate(vms[:10]):
        vx = 60 + (i % 5) * 170
        vy = vm_y + (i // 5) * 50
        vm_name = vm.get("name", f"VM {i+1}")
        power_color = "#2b8a3e" if vm.get("powerState") == "ON" else "#c92a2a"

        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": vx, "y": vy,
            "width": 155, "height": 38,
            "strokeColor": power_color,
            "backgroundColor": "#f8f9fa",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elem_id += 1
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": vx + 5, "y": vy + 9,
            "width": 145, "height": 20,
            "text": vm_name[:22],
            "fontSize": 10,
            "fontFamily": 1,
            "textAlign": "center",
        })
        elem_id += 1

    return elements


def _generate_vm_diagram(vms: list[dict]) -> list[dict]:
    """Generate Excalidraw elements for VM details."""
    elements = []
    elem_id = 300

    for i, vm in enumerate(vms[:6]):
        base_x = 50 + (i % 2) * 480
        base_y = 30 + (i // 2) * 250

        vm_name = vm.get("name", f"VM {i+1}")
        power_state = vm.get("powerState", "UNKNOWN")
        border_color = "#2b8a3e" if power_state == "ON" else "#c92a2a"

        # VM outer box
        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": base_x, "y": base_y,
            "width": 440, "height": 210,
            "strokeColor": border_color,
            "backgroundColor": "#f8f9fa",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elem_id += 1

        # VM name header
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": base_x + 10, "y": base_y + 10,
            "width": 420, "height": 25,
            "text": f"{vm_name} [{power_state}]",
            "fontSize": 14,
            "fontFamily": 1,
        })
        elem_id += 1

        # CPU box
        num_vcpus = vm.get("numSockets", 1) * vm.get("numCoresPerSocket", 1)
        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": base_x + 15, "y": base_y + 45,
            "width": 120, "height": 50,
            "strokeColor": "#1864ab",
            "backgroundColor": "#d0ebff",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elem_id += 1
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": base_x + 25, "y": base_y + 55,
            "width": 100, "height": 30,
            "text": f"CPU\n{num_vcpus} vCPUs",
            "fontSize": 11,
            "fontFamily": 1,
            "textAlign": "center",
        })
        elem_id += 1

        # Memory box
        mem_bytes = vm.get("memorySizeBytes", 0)
        mem_str = _format_bytes(mem_bytes)
        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": base_x + 150, "y": base_y + 45,
            "width": 120, "height": 50,
            "strokeColor": "#5f3dc4",
            "backgroundColor": "#e5dbff",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elem_id += 1
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": base_x + 160, "y": base_y + 55,
            "width": 100, "height": 30,
            "text": f"Memory\n{mem_str}",
            "fontSize": 11,
            "fontFamily": 1,
            "textAlign": "center",
        })
        elem_id += 1

        # Disks box
        disks = vm.get("disks", [])
        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": base_x + 285, "y": base_y + 45,
            "width": 140, "height": 50,
            "strokeColor": "#e67700",
            "backgroundColor": "#fff3bf",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elem_id += 1
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": base_x + 295, "y": base_y + 55,
            "width": 120, "height": 30,
            "text": f"Disks\n{len(disks)} disk(s)",
            "fontSize": 11,
            "fontFamily": 1,
            "textAlign": "center",
        })
        elem_id += 1

        # NICs row
        nics = vm.get("nics", [])
        elements.append({
            "id": str(elem_id),
            "type": "rectangle",
            "x": base_x + 15, "y": base_y + 110,
            "width": 410, "height": 40,
            "strokeColor": "#862e9c",
            "backgroundColor": "#f3d9fa",
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elem_id += 1
        nic_text = f"NICs: {len(nics)}"
        if nics:
            nic_ips = [
                n.get("ipAddress", {}).get("ip", "no IP")
                for n in nics[:3]
            ]
            nic_text += f" — {', '.join(nic_ips)}"
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": base_x + 25, "y": base_y + 120,
            "width": 390, "height": 20,
            "text": nic_text,
            "fontSize": 11,
            "fontFamily": 1,
        })
        elem_id += 1

        # Cluster/host info
        cluster_name = _safe_get(vm, "cluster", "name")
        host_name = _safe_get(vm, "host", "name")
        elements.append({
            "id": str(elem_id),
            "type": "text",
            "x": base_x + 15, "y": base_y + 165,
            "width": 410, "height": 35,
            "text": f"Cluster: {cluster_name}\nHost: {host_name}",
            "fontSize": 10,
            "fontFamily": 1,
        })
        elem_id += 1

    return elements


# ─── Report content generators ───────────────────────────────────────────────


def _build_environment_markdown(
    clusters: list[dict],
    hosts_by_cluster: dict[str, list[dict]],
    vms: list[dict],
    containers: list[dict],
    subnets: list[dict],
) -> str:
    """Build full environment Markdown report."""
    lines = []
    lines.append("# Nutanix As-Built Report — Full Environment")
    lines.append(f"\n**Generated:** {_now_iso()}")
    lines.append(f"**Report Scope:** Full Environment (All Clusters)")
    lines.append("")

    # Executive Summary
    total_hosts = sum(len(h) for h in hosts_by_cluster.values())
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Clusters | {len(clusters)} |")
    lines.append(f"| Hosts | {total_hosts} |")
    lines.append(f"| Virtual Machines | {len(vms)} |")
    lines.append(f"| Storage Containers | {len(containers)} |")
    lines.append(f"| Subnets | {len(subnets)} |")
    lines.append("")

    # Clusters section
    lines.append("## Clusters")
    lines.append("")
    for cluster in clusters:
        name = cluster.get("name", "N/A")
        ext_id = cluster.get("extId", "N/A")
        config = cluster.get("config", {})
        network = cluster.get("network", {})

        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"| Property | Value |")
        lines.append(f"|----------|-------|")
        lines.append(f"| UUID | `{ext_id}` |")
        lines.append(f"| Cluster Function | {config.get('clusterFunction', 'N/A')} |")
        lines.append(f"| Hypervisor Types | {', '.join(config.get('hypervisorTypes', []))} |")
        lines.append(f"| Operation Mode | {config.get('operationMode', 'N/A')} |")
        lines.append(f"| Redundancy Factor | {config.get('redundancyFactor', 'N/A')} |")

        # Network info
        ext_ip = _safe_get(network, "externalIp")
        ntp_servers = network.get("ntpServerIpList", [])
        dns_servers = network.get("nameServerIpList", [])
        if ext_ip != "N/A":
            lines.append(f"| External IP | {ext_ip} |")
        if ntp_servers:
            lines.append(f"| NTP Servers | {', '.join(str(n) for n in ntp_servers)} |")
        if dns_servers:
            lines.append(f"| DNS Servers | {', '.join(str(d) for d in dns_servers)} |")
        lines.append("")

        # Hosts in this cluster
        cluster_hosts = hosts_by_cluster.get(ext_id, [])
        if cluster_hosts:
            lines.append(f"#### Hosts ({len(cluster_hosts)})")
            lines.append("")
            lines.append("| Name | IP | CPU Model | Sockets | Cores | Memory |")
            lines.append("|------|-----|-----------|---------|-------|--------|")
            for h in cluster_hosts:
                h_name = h.get("name", "N/A")
                h_ip = _safe_get(h, "hypervisor", "ip")
                cpu = h.get("cpu", {})
                cpu_model = cpu.get("model", "N/A")
                sockets = cpu.get("numSockets", "N/A")
                cores = cpu.get("numCores", "N/A")
                mem = _format_bytes(h.get("memoryCapacityBytes"))
                lines.append(f"| {h_name} | {h_ip} | {cpu_model} | {sockets} | {cores} | {mem} |")
            lines.append("")

    # Storage section
    lines.append("## Storage Containers")
    lines.append("")
    if containers:
        lines.append("| Name | Capacity | Used | Cluster |")
        lines.append("|------|----------|------|---------|")
        for sc in containers:
            sc_name = sc.get("name", "N/A")
            capacity = _format_bytes(sc.get("maxCapacityBytes"))
            used = _format_bytes(_safe_get(sc, "usageStats", "usedBytes") if isinstance(_safe_get(sc, "usageStats", "usedBytes"), int) else 0)
            sc_cluster = _safe_get(sc, "cluster", "extId")
            lines.append(f"| {sc_name} | {capacity} | {used} | `{sc_cluster}` |")
        lines.append("")

    # Networking section
    lines.append("## Networking (Subnets)")
    lines.append("")
    if subnets:
        lines.append("| Name | Type | VLAN | Subnet | Cluster |")
        lines.append("|------|------|------|--------|---------|")
        for sn in subnets:
            sn_name = sn.get("name", "N/A")
            sn_type = sn.get("subnetType", "N/A")
            vlan = sn.get("vlanId", "N/A")
            ip_config = sn.get("ipConfig", {})
            subnet_cidr = f"{ip_config.get('subnetIp', '')}/{ip_config.get('prefixLength', '')}" if ip_config else "N/A"
            sn_cluster = _safe_get(sn, "cluster", "extId")
            lines.append(f"| {sn_name} | {sn_type} | {vlan} | {subnet_cidr} | `{sn_cluster}` |")
        lines.append("")

    # VM inventory
    lines.append("## Virtual Machine Inventory")
    lines.append("")
    lines.append(f"**Total VMs:** {len(vms)}")
    lines.append("")
    vm_on = sum(1 for v in vms if v.get("powerState") == "ON")
    vm_off = len(vms) - vm_on
    lines.append(f"- Powered On: {vm_on}")
    lines.append(f"- Powered Off: {vm_off}")
    lines.append("")
    if vms:
        lines.append("| Name | Power | vCPUs | Memory | Cluster |")
        lines.append("|------|-------|-------|--------|---------|")
        for vm in vms:
            vm_name = vm.get("name", "N/A")
            power = vm.get("powerState", "N/A")
            vcpus = vm.get("numSockets", 1) * vm.get("numCoresPerSocket", 1)
            mem = _format_bytes(vm.get("memorySizeBytes"))
            vm_cluster = _safe_get(vm, "cluster", "extId")
            lines.append(f"| {vm_name} | {power} | {vcpus} | {mem} | `{vm_cluster}` |")
        lines.append("")

    return "\n".join(lines)


def _build_cluster_markdown(
    cluster: dict,
    hosts: list[dict],
    vms: list[dict],
    containers: list[dict],
    subnets: list[dict],
) -> str:
    """Build detailed cluster Markdown report."""
    lines = []
    name = cluster.get("name", "N/A")
    ext_id = cluster.get("extId", "N/A")
    config = cluster.get("config", {})
    network = cluster.get("network", {})

    lines.append(f"# Nutanix As-Built Report — Cluster: {name}")
    lines.append(f"\n**Generated:** {_now_iso()}")
    lines.append(f"**Cluster UUID:** `{ext_id}`")
    lines.append("")

    # Cluster config
    lines.append("## Cluster Configuration")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("|----------|-------|")
    lines.append(f"| Name | {name} |")
    lines.append(f"| UUID | `{ext_id}` |")
    lines.append(f"| Cluster Function | {config.get('clusterFunction', 'N/A')} |")
    lines.append(f"| Hypervisor Types | {', '.join(config.get('hypervisorTypes', []))} |")
    lines.append(f"| Operation Mode | {config.get('operationMode', 'N/A')} |")
    lines.append(f"| Redundancy Factor | {config.get('redundancyFactor', 'N/A')} |")
    lines.append(f"| Fault Tolerance Domain | {config.get('faultToleranceDomainType', 'N/A')} |")

    build_info = config.get("buildInfo", {})
    if build_info:
        lines.append(f"| AOS Version | {build_info.get('version', 'N/A')} |")
        lines.append(f"| Build Type | {build_info.get('buildType', 'N/A')} |")

    lines.append("")

    # Network configuration
    lines.append("## Network Configuration")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("|----------|-------|")
    ext_ip = _safe_get(network, "externalIp")
    lines.append(f"| External IP | {ext_ip} |")
    lines.append(f"| External Data Services IP | {_safe_get(network, 'externalDataServicesIp')} |")
    ntp_servers = network.get("ntpServerIpList", [])
    dns_servers = network.get("nameServerIpList", [])
    lines.append(f"| NTP Servers | {', '.join(str(n) for n in ntp_servers) if ntp_servers else 'N/A'} |")
    lines.append(f"| DNS Servers | {', '.join(str(d) for d in dns_servers) if dns_servers else 'N/A'} |")
    lines.append("")

    # Hosts
    lines.append(f"## Hosts ({len(hosts)})")
    lines.append("")
    if hosts:
        lines.append("| Name | IP Address | Hypervisor | CPU Model | Sockets | Cores/Socket | Total Cores | Memory |")
        lines.append("|------|-----------|------------|-----------|---------|--------------|-------------|--------|")
        for h in hosts:
            h_name = h.get("name", "N/A")
            hyp = h.get("hypervisor", {})
            h_ip = hyp.get("ip", "N/A")
            h_type = hyp.get("type", "N/A")
            cpu = h.get("cpu", {})
            cpu_model = cpu.get("model", "N/A")
            sockets = cpu.get("numSockets", 0)
            cores_per = cpu.get("numCoresPerSocket", 0)
            total_cores = sockets * cores_per if sockets and cores_per else "N/A"
            mem = _format_bytes(h.get("memoryCapacityBytes"))
            lines.append(f"| {h_name} | {h_ip} | {h_type} | {cpu_model} | {sockets} | {cores_per} | {total_cores} | {mem} |")
        lines.append("")

        # Host summary
        total_sockets = sum(h.get("cpu", {}).get("numSockets", 0) for h in hosts)
        total_cores = sum(
            h.get("cpu", {}).get("numSockets", 0) * h.get("cpu", {}).get("numCoresPerSocket", 0)
            for h in hosts
        )
        total_mem = sum(h.get("memoryCapacityBytes", 0) for h in hosts)
        lines.append("**Totals:**")
        lines.append(f"- Total Sockets: {total_sockets}")
        lines.append(f"- Total Cores: {total_cores}")
        lines.append(f"- Total Memory: {_format_bytes(total_mem)}")
        lines.append("")

    # Storage containers
    lines.append(f"## Storage Containers ({len(containers)})")
    lines.append("")
    if containers:
        lines.append("| Name | Max Capacity | Replication Factor | Compression | Dedup |")
        lines.append("|------|-------------|-------------------|-------------|-------|")
        for sc in containers:
            sc_name = sc.get("name", "N/A")
            capacity = _format_bytes(sc.get("maxCapacityBytes"))
            rf = sc.get("replicationFactor", "N/A")
            compression = sc.get("compressionEnabled", "N/A")
            dedup = sc.get("onDiskDedup", "N/A")
            lines.append(f"| {sc_name} | {capacity} | {rf} | {compression} | {dedup} |")
        lines.append("")

    # Subnets
    lines.append(f"## Subnets ({len(subnets)})")
    lines.append("")
    if subnets:
        lines.append("| Name | Type | VLAN ID | Subnet | Gateway | DHCP |")
        lines.append("|------|------|---------|--------|---------|------|")
        for sn in subnets:
            sn_name = sn.get("name", "N/A")
            sn_type = sn.get("subnetType", "N/A")
            vlan = sn.get("vlanId", "N/A")
            ip_config = sn.get("ipConfig", {})
            subnet_str = f"{ip_config.get('subnetIp', 'N/A')}/{ip_config.get('prefixLength', '')}" if ip_config else "N/A"
            gateway = ip_config.get("defaultGatewayIp", "N/A") if ip_config else "N/A"
            dhcp = "Yes" if sn.get("dhcpOptions") else "No"
            lines.append(f"| {sn_name} | {sn_type} | {vlan} | {subnet_str} | {gateway} | {dhcp} |")
        lines.append("")

    # VMs
    lines.append(f"## Virtual Machines ({len(vms)})")
    lines.append("")
    vm_on = sum(1 for v in vms if v.get("powerState") == "ON")
    lines.append(f"**Powered On:** {vm_on} | **Powered Off:** {len(vms) - vm_on}")
    lines.append("")
    if vms:
        lines.append("| Name | Power State | vCPUs | Memory | Disks | NICs |")
        lines.append("|------|-------------|-------|--------|-------|------|")
        for vm in vms:
            vm_name = vm.get("name", "N/A")
            power = vm.get("powerState", "N/A")
            vcpus = vm.get("numSockets", 1) * vm.get("numCoresPerSocket", 1)
            mem = _format_bytes(vm.get("memorySizeBytes"))
            num_disks = len(vm.get("disks", []))
            num_nics = len(vm.get("nics", []))
            lines.append(f"| {vm_name} | {power} | {vcpus} | {mem} | {num_disks} | {num_nics} |")
        lines.append("")

    return "\n".join(lines)


def _build_vm_markdown(vms: list[dict]) -> str:
    """Build detailed VM Markdown report."""
    lines = []
    lines.append("# Nutanix As-Built Report — Virtual Machines")
    lines.append(f"\n**Generated:** {_now_iso()}")
    lines.append(f"**VMs in Report:** {len(vms)}")
    lines.append("")

    for vm in vms:
        vm_name = vm.get("name", "N/A")
        ext_id = vm.get("extId", "N/A")
        power_state = vm.get("powerState", "N/A")

        lines.append(f"## {vm_name}")
        lines.append("")

        # Basic info
        lines.append("### Configuration")
        lines.append("")
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        lines.append(f"| Name | {vm_name} |")
        lines.append(f"| UUID | `{ext_id}` |")
        lines.append(f"| Power State | {power_state} |")
        lines.append(f"| Description | {vm.get('description', 'N/A')} |")
        lines.append(f"| Guest OS | {vm.get('guestCustomization', {}).get('config', {}).get('sysprep', {}).get('installType', 'N/A')} |")
        lines.append(f"| Machine Type | {vm.get('machineType', 'N/A')} |")
        lines.append(f"| Hardware Clock Timezone | {vm.get('hardwareClockTimezone', 'N/A')} |")

        # Compute
        num_sockets = vm.get("numSockets", 1)
        cores_per_socket = vm.get("numCoresPerSocket", 1)
        threads_per_core = vm.get("numThreadsPerCore", 1)
        total_vcpus = num_sockets * cores_per_socket
        mem_bytes = vm.get("memorySizeBytes", 0)

        lines.append(f"| CPU Sockets | {num_sockets} |")
        lines.append(f"| Cores per Socket | {cores_per_socket} |")
        lines.append(f"| Threads per Core | {threads_per_core} |")
        lines.append(f"| Total vCPUs | {total_vcpus} |")
        lines.append(f"| Memory | {_format_bytes(mem_bytes)} |")

        # Cluster/Host
        cluster_info = vm.get("cluster", {})
        host_info = vm.get("host", {})
        lines.append(f"| Cluster | {cluster_info.get('name', cluster_info.get('extId', 'N/A'))} |")
        lines.append(f"| Host | {host_info.get('name', host_info.get('extId', 'N/A'))} |")

        # Categories
        categories = vm.get("categories", [])
        if categories:
            cat_str = ", ".join(f"{c.get('key', '')}:{c.get('value', '')}" for c in categories)
            lines.append(f"| Categories | {cat_str} |")

        lines.append("")

        # Disks
        disks = vm.get("disks", [])
        if disks:
            lines.append("### Disks")
            lines.append("")
            lines.append("| # | Type | Size | Bus | Controller | Storage Container |")
            lines.append("|---|------|------|-----|------------|-------------------|")
            for idx, disk in enumerate(disks):
                d_type = disk.get("diskType", "N/A")
                d_size = _format_bytes(disk.get("diskSizeBytes"))
                bus = disk.get("busType", "N/A")
                addr = disk.get("deviceAddress", {})
                controller = f"{addr.get('busType', '')}{addr.get('index', '')}" if addr else "N/A"
                sc_ref = _safe_get(disk, "storageConfig", "storageContainerReference", "extId")
                lines.append(f"| {idx+1} | {d_type} | {d_size} | {bus} | {controller} | `{sc_ref}` |")
            lines.append("")

        # NICs
        nics = vm.get("nics", [])
        if nics:
            lines.append("### Network Interfaces")
            lines.append("")
            lines.append("| # | Type | Subnet | MAC | IP Address | VLAN Mode |")
            lines.append("|---|------|--------|-----|------------|-----------|")
            for idx, nic in enumerate(nics):
                n_type = nic.get("nicType", "N/A")
                subnet = _safe_get(nic, "subnet", "name")
                mac = nic.get("macAddress", "N/A")
                ip = _safe_get(nic, "ipAddress", "ip")
                vlan_mode = nic.get("vlanMode", "N/A")
                lines.append(f"| {idx+1} | {n_type} | {subnet} | {mac} | {ip} | {vlan_mode} |")
            lines.append("")

        # GPU
        gpus = vm.get("gpus", [])
        if gpus:
            lines.append("### GPUs")
            lines.append("")
            lines.append("| Mode | Vendor | Device |")
            lines.append("|------|--------|--------|")
            for gpu in gpus:
                lines.append(f"| {gpu.get('mode', 'N/A')} | {gpu.get('vendor', 'N/A')} | {gpu.get('deviceName', 'N/A')} |")
            lines.append("")

        # Boot config
        boot_config = vm.get("bootConfig", {})
        if boot_config:
            lines.append("### Boot Configuration")
            lines.append("")
            lines.append(f"- Boot Type: {boot_config.get('bootType', 'N/A')}")
            boot_device = boot_config.get("bootDeviceOrder", [])
            if boot_device:
                lines.append(f"- Boot Device Order: {', '.join(boot_device)}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_generate_environment_report(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Generate full environment As-Built report."""
    include_vms = arguments.get("include_vms", True)
    include_diagram = arguments.get("include_diagram", True)

    # Collect all environment data
    clusters_result = await client.v4_list(
        namespace="clustermgmt", path="config/clusters"
    )
    clusters = clusters_result.get("data", [])

    # Get detailed info for each cluster
    detailed_clusters = []
    hosts_by_cluster: dict[str, list[dict]] = {}
    for cluster in clusters:
        ext_id = cluster.get("extId", "")
        # Get full cluster details
        try:
            detail = await client.v4_get(
                namespace="clustermgmt", path=f"config/clusters/{ext_id}"
            )
            detailed_clusters.append(detail.get("data", cluster))
        except Exception:
            detailed_clusters.append(cluster)

        # Get hosts for this cluster
        try:
            hosts_result = await client.v4_list(
                namespace="clustermgmt",
                path=f"config/clusters/{ext_id}/hosts",
            )
            hosts_by_cluster[ext_id] = hosts_result.get("data", [])
        except Exception:
            hosts_by_cluster[ext_id] = []

    # Get storage containers
    try:
        containers_result = await client.v4_list(
            namespace="clustermgmt", path="config/storage-containers"
        )
        containers = containers_result.get("data", [])
    except Exception:
        containers = []

    # Get subnets
    try:
        subnets_result = await client.v4_list(
            namespace="networking", path="config/subnets"
        )
        subnets = subnets_result.get("data", [])
    except Exception:
        subnets = []

    # Get VMs
    vms = []
    if include_vms:
        try:
            vms_result = await client.v4_list(
                namespace="vmm", path="ahv/config/vms"
            )
            vms = vms_result.get("data", [])
        except Exception:
            vms = []

    # Build markdown report
    markdown = _build_environment_markdown(
        detailed_clusters, hosts_by_cluster, vms, containers, subnets
    )

    result: dict[str, Any] = {"report_markdown": markdown}

    # Build diagram
    if include_diagram:
        diagram_elements = _generate_environment_diagram(
            detailed_clusters, hosts_by_cluster
        )
        result["excalidraw_diagram"] = {
            "type": "excalidraw",
            "version": 2,
            "elements": diagram_elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
        }

    return result


async def handle_generate_cluster_report(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Generate detailed cluster As-Built report."""
    cluster_uuids = arguments.get("cluster_uuids", [])
    include_diagram = arguments.get("include_diagram", True)

    # If no UUIDs provided, get all clusters
    if not cluster_uuids:
        clusters_result = await client.v4_list(
            namespace="clustermgmt", path="config/clusters"
        )
        clusters_data = clusters_result.get("data", [])
        cluster_uuids = [c.get("extId") for c in clusters_data if c.get("extId")]

    reports = []
    all_diagrams = []

    for cluster_uuid in cluster_uuids:
        # Get cluster details
        try:
            cluster_result = await client.v4_get(
                namespace="clustermgmt", path=f"config/clusters/{cluster_uuid}"
            )
            cluster = cluster_result.get("data", {})
        except Exception as e:
            reports.append(f"# Error fetching cluster {cluster_uuid}\n\n{e}\n")
            continue

        # Get hosts
        try:
            hosts_result = await client.v4_list(
                namespace="clustermgmt",
                path=f"config/clusters/{cluster_uuid}/hosts",
            )
            hosts = hosts_result.get("data", [])
        except Exception:
            hosts = []

        # Get VMs on this cluster
        try:
            vms_result = await client.v4_list(
                namespace="vmm",
                path="ahv/config/vms",
                filter=f"cluster/extId eq '{cluster_uuid}'",
            )
            vms = vms_result.get("data", [])
        except Exception:
            vms = []

        # Get storage containers for this cluster
        try:
            containers_result = await client.v4_list(
                namespace="clustermgmt",
                path=f"config/clusters/{cluster_uuid}/storage-containers",
            )
            containers = containers_result.get("data", [])
        except Exception:
            containers = []

        # Get subnets for this cluster
        try:
            subnets_result = await client.v4_list(
                namespace="networking",
                path="config/subnets",
                filter=f"cluster/extId eq '{cluster_uuid}'",
            )
            subnets = subnets_result.get("data", [])
        except Exception:
            subnets = []

        # Build markdown
        report_md = _build_cluster_markdown(cluster, hosts, vms, containers, subnets)
        reports.append(report_md)

        # Build diagram
        if include_diagram:
            diagram_elems = _generate_cluster_diagram(cluster, hosts, vms, containers)
            all_diagrams.extend(diagram_elems)

    combined_markdown = "\n\n---\n\n".join(reports)

    result: dict[str, Any] = {"report_markdown": combined_markdown}

    if include_diagram and all_diagrams:
        result["excalidraw_diagram"] = {
            "type": "excalidraw",
            "version": 2,
            "elements": all_diagrams,
            "appState": {"viewBackgroundColor": "#ffffff"},
        }

    return result


async def handle_generate_vm_report(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Generate detailed VM As-Built report."""
    vm_uuids = arguments["vm_uuids"]
    include_diagram = arguments.get("include_diagram", True)

    # Fetch detailed info for each VM
    vms = []
    for vm_uuid in vm_uuids:
        try:
            vm_result = await client.v4_get(
                namespace="vmm", path=f"ahv/config/vms/{vm_uuid}"
            )
            vms.append(vm_result.get("data", {}))
        except Exception as e:
            vms.append({"name": f"Error: {vm_uuid}", "extId": vm_uuid, "error": str(e)})

    # Build markdown
    markdown = _build_vm_markdown(vms)

    result: dict[str, Any] = {"report_markdown": markdown}

    # Build diagram
    if include_diagram:
        diagram_elements = _generate_vm_diagram(vms)
        result["excalidraw_diagram"] = {
            "type": "excalidraw",
            "version": 2,
            "elements": diagram_elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
        }

    return result


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

REPORT_HANDLERS: dict[str, Any] = {
    "generate_environment_report": handle_generate_environment_report,
    "generate_cluster_report": handle_generate_cluster_report,
    "generate_vm_report": handle_generate_vm_report,
}
