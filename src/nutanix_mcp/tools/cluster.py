"""Cluster management tools using Nutanix v4 clustermgmt namespace."""

from typing import Any, Optional

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

CLUSTER_TOOLS: list[dict] = [
    {
        "name": "list_clusters",
        "description": (
            "List all Nutanix clusters registered with Prism Central. "
            "Returns cluster names, UUIDs, versions, and health status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "OData filter expression. Example: \"name eq 'prod-cluster'\"",
                },
            },
        },
    },
    {
        "name": "get_cluster",
        "description": (
            "Get detailed information about a specific cluster by UUID. "
            "Returns configuration, network, storage, and health details."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the cluster",
                },
            },
            "required": ["cluster_uuid"],
        },
    },
    {
        "name": "list_hosts",
        "description": (
            "List hypervisor hosts across clusters. Returns host names, IPs, "
            "resource capacity, and health. Optionally filter by cluster."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_uuid": {
                    "type": "string",
                    "description": "Filter hosts to a specific cluster UUID",
                },
                "filter": {
                    "type": "string",
                    "description": "OData filter expression",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of hosts to return. Omit to retrieve all (auto-paginates).",
                },
            },
        },
    },
    {
        "name": "get_host",
        "description": (
            "Get detailed information about a specific host by UUID. "
            "Returns hardware specs, hypervisor info, and resource usage."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "host_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the host",
                },
            },
            "required": ["host_uuid"],
        },
    },
    {
        "name": "list_storage_containers",
        "description": (
            "List storage containers available across clusters. "
            "Returns names, capacity, usage, and associated cluster."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_uuid": {
                    "type": "string",
                    "description": "Filter to a specific cluster UUID",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results. Omit to retrieve all (auto-paginates).",
                },
            },
        },
    },
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_list_clusters(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List clusters using v4 clustermgmt API."""
    filter_expr = arguments.get("filter")

    result = await client.v4_list_all(
        namespace="clustermgmt",
        path="config/clusters",
        filter=filter_expr,
    )

    clusters = result.get("data", [])
    return {
        "count": len(clusters),
        "clusters": [
            {
                "name": c.get("name"),
                "extId": c.get("extId"),
                "clusterFunction": c.get("config", {}).get("clusterFunction"),
                "hypervisorTypes": c.get("config", {}).get("hypervisorTypes"),
                "operationMode": c.get("config", {}).get("operationMode"),
                "redundancyFactor": c.get("config", {}).get("redundancyFactor"),
            }
            for c in clusters
        ],
    }


async def handle_get_cluster(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get cluster details using v4 clustermgmt API."""
    cluster_uuid = arguments["cluster_uuid"]
    result = await client.v4_get(
        namespace="clustermgmt",
        path=f"config/clusters/{cluster_uuid}",
    )
    return result.get("data", result)


async def handle_list_hosts(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List hosts using v4 clustermgmt API."""
    cluster_uuid = arguments.get("cluster_uuid")
    filter_expr = arguments.get("filter")
    limit = arguments.get("limit")

    # If cluster_uuid provided, filter to that cluster's hosts
    if cluster_uuid:
        path = f"config/clusters/{cluster_uuid}/hosts"
    else:
        path = "config/hosts"

    result = await client.v4_list_all(
        namespace="clustermgmt",
        path=path,
        filter=filter_expr,
        max_results=limit,
    )

    hosts = result.get("data", [])
    metadata = result.get("metadata", {})
    return {
        "count": len(hosts),
        "truncated": metadata.get("truncated", False),
        "hosts": [
            {
                "name": h.get("name"),
                "extId": h.get("extId"),
                "hypervisorType": h.get("hypervisor", {}).get("type"),
                "ipAddress": h.get("hypervisor", {}).get("ip"),
                "cpuModel": h.get("cpu", {}).get("model"),
                "numCpuSockets": h.get("cpu", {}).get("numSockets"),
                "numCpuCores": h.get("cpu", {}).get("numCores"),
                "memoryCapacityBytes": h.get("memoryCapacityBytes"),
                "cluster": h.get("cluster", {}).get("extId"),
            }
            for h in hosts
        ],
    }


async def handle_get_host(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get host details using v4 clustermgmt API."""
    host_uuid = arguments["host_uuid"]
    result = await client.v4_get(
        namespace="clustermgmt",
        path=f"config/hosts/{host_uuid}",
    )
    return result.get("data", result)


async def handle_list_storage_containers(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List storage containers using v4 clustermgmt API."""
    cluster_uuid = arguments.get("cluster_uuid")
    limit = arguments.get("limit")

    if cluster_uuid:
        path = f"config/clusters/{cluster_uuid}/storage-containers"
    else:
        path = "config/storage-containers"

    result = await client.v4_list_all(
        namespace="clustermgmt",
        path=path,
        max_results=limit,
    )

    containers = result.get("data", [])
    metadata = result.get("metadata", {})
    return {
        "count": len(containers),
        "truncated": metadata.get("truncated", False),
        "storageContainers": [
            {
                "name": sc.get("name"),
                "extId": sc.get("extId"),
                "maxCapacityBytes": sc.get("maxCapacityBytes"),
                "usedBytes": sc.get("usageStats", {}).get("usedBytes"),
                "cluster": sc.get("cluster", {}).get("extId"),
            }
            for sc in containers
        ],
    }


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

CLUSTER_HANDLERS: dict[str, Any] = {
    "list_clusters": handle_list_clusters,
    "get_cluster": handle_get_cluster,
    "list_hosts": handle_list_hosts,
    "get_host": handle_get_host,
    "list_storage_containers": handle_list_storage_containers,
}
