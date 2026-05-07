"""Cluster management tools using Nutanix v4 clustermgmt namespace."""

from typing import Any

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

CLUSTER_TOOLS: list[dict] = [
    {
        "name": "list_clusters",
        "description": (
            "List ALL Nutanix clusters registered with Prism Central (auto-paginates internally). "
            "Returns complete results in one call — no manual pagination needed."
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
            "List ALL hypervisor hosts (auto-paginates internally). "
            "Returns complete results in one call — no manual pagination needed. "
            "Optionally filter by cluster UUID."
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
                    "description": "Optional cap on results. Omit to get ALL hosts (default behavior).",
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
            "List ALL storage containers (auto-paginates internally). "
            "Returns complete results in one call — no manual pagination needed."
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
                    "description": "Optional cap on results. Omit to get ALL containers (default behavior).",
                },
            },
        },
    },
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_list_clusters(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List clusters using v4 clustermgmt API."""
    filter_expr = arguments.get("filter")

    result = await client.v4_list_all(
        namespace="clustermgmt",
        path="config/clusters",
        filter=filter_expr,
    )

    clusters = result.get("data", [])
    return {
        "totalReturned": len(clusters),
        "note": "All matching clusters returned. No further pagination needed.",
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


async def handle_get_cluster(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Get cluster details using v4 clustermgmt API."""
    cluster_uuid = arguments["cluster_uuid"]
    result = await client.v4_get(
        namespace="clustermgmt",
        path=f"config/clusters/{cluster_uuid}",
    )
    return result.get("data", result)


async def handle_list_hosts(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
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

    def _extract_host(h: dict) -> dict:
        hypervisor = h.get("hypervisor") or {}
        ext_addr = hypervisor.get("externalAddress") or {}
        ipv4 = ext_addr.get("ipv4") or {}
        cluster_ref = h.get("cluster") or {}
        return {
            "name": h.get("hostName"),
            "extId": h.get("extId"),
            "hypervisorType": hypervisor.get("type"),
            "ipAddress": ipv4.get("value"),
            "cpuModel": h.get("cpuModel"),
            "numCpuSockets": h.get("numberOfCpuSockets"),
            "numCpuCores": h.get("numberOfCpuCores"),
            "memorySizeBytes": h.get("memorySizeBytes"),
            "cluster": cluster_ref.get("uuid") or cluster_ref.get("extId"),
            "clusterName": cluster_ref.get("name"),
        }

    return {
        "totalReturned": len(hosts),
        "note": "All matching hosts returned. No further pagination needed.",
        "hosts": [_extract_host(h) for h in hosts],
    }


async def handle_get_host(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Get host details using v4 clustermgmt API."""
    host_uuid = arguments["host_uuid"]
    result = await client.v4_get(
        namespace="clustermgmt",
        path=f"config/hosts/{host_uuid}",
    )
    return result.get("data", result)


async def handle_list_storage_containers(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
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
    return {
        "totalReturned": len(containers),
        "note": "All matching storage containers returned. No further pagination needed.",
        "storageContainers": [
            {
                "name": sc.get("name"),
                "extId": sc.get("containerExtId"),
                "maxCapacityBytes": sc.get("maxCapacityBytes"),
                "replicationFactor": sc.get("replicationFactor"),
                "compressionEnabled": sc.get("isCompressionEnabled"),
                "encrypted": sc.get("isEncrypted"),
                "clusterExtId": sc.get("clusterExtId"),
                "clusterName": sc.get("clusterName"),
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
