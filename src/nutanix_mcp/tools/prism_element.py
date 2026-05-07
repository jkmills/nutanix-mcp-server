"""Prism Element tools using Nutanix v2.0 API (direct cluster access).

These tools connect directly to individual Prism Element CVMs,
which are discovered via Prism Central's cluster list.
"""

from typing import Any

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

PE_TOOLS: list[dict] = [
    {
        "name": "pe_get_cluster_info",
        "description": (
            "Get cluster info directly from a Prism Element node. "
            "Returns AOS version, cluster name, storage capacity, and health."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "pe_list_vms",
        "description": (
            "List VMs on a specific Prism Element cluster. "
            "Returns VM names, UUIDs, power states, and resource allocation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
                "count": {
                    "type": "integer",
                    "description": "Maximum number of VMs to return",
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "pe_list_hosts",
        "description": (
            "List hypervisor hosts on a Prism Element cluster. Returns host names, IPs, hardware specs, and CVM info."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "pe_list_containers",
        "description": (
            "List storage containers on a Prism Element cluster. "
            "Returns names, capacity, usage, replication factor, and policies."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "pe_list_storage_pools",
        "description": (
            "List storage pools on a Prism Element cluster. Returns pool names, capacity, and disk composition."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "pe_list_disks",
        "description": (
            "List physical disks on a Prism Element cluster. "
            "Returns disk type (SSD/HDD), status, capacity, and location."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "pe_list_alerts",
        "description": (
            "List alerts on a Prism Element cluster. Returns alert titles, severity, timestamps, and affected entities."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
                "resolved": {
                    "type": "boolean",
                    "description": "Include resolved alerts (default: false, only active)",
                    "default": False,
                },
                "count": {
                    "type": "integer",
                    "description": "Maximum number of alerts to return (default: 50)",
                    "default": 50,
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "pe_list_protection_domains",
        "description": (
            "List protection domains on a Prism Element cluster. "
            "Returns PD names, protected entities, schedules, and replication state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
            },
            "required": ["pe_host"],
        },
    },
    {
        "name": "pe_list_snapshots",
        "description": ("List snapshots for a protection domain on a Prism Element cluster."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pe_host": {
                    "type": "string",
                    "description": "Prism Element CVM IP address or hostname",
                },
                "protection_domain": {
                    "type": "string",
                    "description": "Name of the protection domain",
                },
            },
            "required": ["pe_host", "protection_domain"],
        },
    },
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_pe_get_cluster_info(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Get cluster info from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    result = await client.pe_get(pe_host, "cluster")

    return {
        "name": result.get("name"),
        "clusterUuid": result.get("cluster_uuid"),
        "version": result.get("version"),
        "numNodes": result.get("num_nodes"),
        "storageType": result.get("storage_type"),
        "hypervisorTypes": result.get("hypervisor_types"),
        "clusterExternalIp": result.get("cluster_external_ipaddress"),
    }


async def handle_pe_list_vms(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List VMs from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    count = arguments.get("count")

    result = await client.pe_list(pe_host, "vms", count=count)
    entities = result.get("entities", [])

    return {
        "count": len(entities),
        "vms": [
            {
                "name": vm.get("name"),
                "uuid": vm.get("uuid"),
                "powerState": vm.get("power_state"),
                "numVcpus": vm.get("num_vcpus"),
                "memoryMb": vm.get("memory_mb"),
                "hostUuid": vm.get("host_uuid"),
                "ipAddresses": vm.get("ip_addresses", []),
            }
            for vm in entities
        ],
    }


async def handle_pe_list_hosts(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List hosts from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    result = await client.pe_list(pe_host, "hosts")
    entities = result.get("entities", [])

    return {
        "count": len(entities),
        "hosts": [
            {
                "name": h.get("name"),
                "uuid": h.get("uuid"),
                "hypervisorAddress": h.get("hypervisor_address"),
                "cvmAddress": h.get("controller_vm_backplane_ip"),
                "cpuModel": h.get("cpu_model"),
                "numCpuSockets": h.get("num_cpu_sockets"),
                "numCpuCores": h.get("num_cpu_cores"),
                "memoryCapacityGb": (h.get("memory_capacity_in_bytes", 0)) // (1024**3),
                "hypervisorType": h.get("hypervisor_type"),
            }
            for h in entities
        ],
    }


async def handle_pe_list_containers(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List storage containers from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    result = await client.pe_list(pe_host, "containers")
    entities = result.get("entities", [])

    return {
        "count": len(entities),
        "containers": [
            {
                "name": c.get("name"),
                "containerUuid": c.get("container_uuid"),
                "storagePoolUuid": c.get("storage_pool_uuid"),
                "maxCapacityBytes": c.get("max_capacity"),
                "replicationFactor": c.get("replication_factor"),
                "compressionEnabled": c.get("compression_enabled"),
                "erasureCoded": c.get("erasure_coded"),
            }
            for c in entities
        ],
    }


async def handle_pe_list_storage_pools(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List storage pools from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    result = await client.pe_list(pe_host, "storage_pools")
    entities = result.get("entities", [])

    return {
        "count": len(entities),
        "storagePools": [
            {
                "name": sp.get("name"),
                "uuid": sp.get("storage_pool_uuid"),
                "capacityBytes": sp.get("capacity"),
                "usageBytes": sp.get("usage_stats", {}).get("storage.usage_bytes"),
                "numDisks": len(sp.get("disks", [])),
            }
            for sp in entities
        ],
    }


async def handle_pe_list_disks(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List physical disks from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    result = await client.pe_list(pe_host, "disks")
    entities = result.get("entities", [])

    return {
        "count": len(entities),
        "disks": [
            {
                "id": d.get("id"),
                "uuid": d.get("disk_uuid"),
                "serialNumber": d.get("disk_hardware_config", {}).get("serial_number"),
                "storageTierName": d.get("storage_tier_name"),
                "diskStatus": d.get("disk_status"),
                "hostName": d.get("host_name"),
                "capacityBytes": d.get("disk_size"),
                "onlineStatus": d.get("online"),
            }
            for d in entities
        ],
    }


async def handle_pe_list_alerts(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List alerts from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    resolved = arguments.get("resolved", False)
    count = arguments.get("count", 50)

    params: dict[str, str] = {"count": str(count)}
    if not resolved:
        params["resolved"] = "false"

    result = await client.pe_get(pe_host, "alerts", params=params)
    entities = result.get("entities", [])

    return {
        "count": len(entities),
        "alerts": [
            {
                "id": a.get("id"),
                "alertTitle": a.get("alert_title"),
                "severity": a.get("severity"),
                "message": a.get("message"),
                "resolved": a.get("resolved"),
                "createdTimeStamp": a.get("created_time_stamp_in_usecs"),
                "affectedEntities": a.get("affected_entities", []),
            }
            for a in entities
        ],
    }


async def handle_pe_list_protection_domains(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List protection domains from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    result = await client.pe_list(pe_host, "protection_domains")
    entities = result.get("entities", [])

    return {
        "count": len(entities),
        "protectionDomains": [
            {
                "name": pd.get("name"),
                "active": pd.get("active"),
                "cronSchedules": pd.get("cron_schedules", []),
                "replicationLinks": pd.get("replication_links", []),
                "vmCount": len(pd.get("vms", [])),
            }
            for pd in entities
        ],
    }


async def handle_pe_list_snapshots(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List snapshots for a protection domain from Prism Element v2 API."""
    pe_host = arguments["pe_host"]
    pd_name = arguments["protection_domain"]

    result = await client.pe_get(pe_host, f"protection_domains/{pd_name}/dr_snapshots")
    entities = result.get("entities", [])

    return {
        "count": len(entities),
        "snapshots": [
            {
                "snapshotId": s.get("snapshot_id"),
                "snapshotName": s.get("snapshot_name"),
                "createdTimestamp": s.get("created_time_stamp_in_usecs"),
                "expiryTimestamp": s.get("expiry_time_stamp_in_usecs"),
                "state": s.get("state"),
            }
            for s in entities
        ],
    }


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

PE_HANDLERS: dict[str, Any] = {
    "pe_get_cluster_info": handle_pe_get_cluster_info,
    "pe_list_vms": handle_pe_list_vms,
    "pe_list_hosts": handle_pe_list_hosts,
    "pe_list_containers": handle_pe_list_containers,
    "pe_list_storage_pools": handle_pe_list_storage_pools,
    "pe_list_disks": handle_pe_list_disks,
    "pe_list_alerts": handle_pe_list_alerts,
    "pe_list_protection_domains": handle_pe_list_protection_domains,
    "pe_list_snapshots": handle_pe_list_snapshots,
}
