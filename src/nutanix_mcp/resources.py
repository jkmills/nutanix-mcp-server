"""MCP Resource Templates for browseable URI-based access to Nutanix entities."""

import json
from typing import Any

from mcp.types import Resource, ResourceTemplate, TextResourceContents

from nutanix_mcp.client import NutanixClient

# ─── Resource Template Definitions ────────────────────────────────────────────

RESOURCE_TEMPLATES: list[ResourceTemplate] = [
    ResourceTemplate(
        uriTemplate="nutanix://vms/{vm_uuid}",
        name="Virtual Machine",
        description="Access a Nutanix VM by UUID. Returns full configuration.",
        mimeType="application/json",
    ),
    ResourceTemplate(
        uriTemplate="nutanix://clusters/{cluster_uuid}",
        name="Cluster",
        description="Access a Nutanix cluster by UUID. Returns cluster details.",
        mimeType="application/json",
    ),
    ResourceTemplate(
        uriTemplate="nutanix://hosts/{host_uuid}",
        name="Host",
        description="Access a hypervisor host by UUID. Returns hardware and config.",
        mimeType="application/json",
    ),
    ResourceTemplate(
        uriTemplate="nutanix://subnets/{subnet_uuid}",
        name="Subnet",
        description="Access a subnet by UUID. Returns VLAN, CIDR, and DHCP config.",
        mimeType="application/json",
    ),
    ResourceTemplate(
        uriTemplate="nutanix://images/{image_uuid}",
        name="Image",
        description="Access a disk image by UUID. Returns image metadata.",
        mimeType="application/json",
    ),
]

# ─── Static Resource Listings ─────────────────────────────────────────────────

STATIC_RESOURCES: list[Resource] = [
    Resource(
        uri="nutanix://vms",
        name="All Virtual Machines",
        description="List all VMs registered with Prism Central",
        mimeType="application/json",
    ),
    Resource(
        uri="nutanix://clusters",
        name="All Clusters",
        description="List all clusters registered with Prism Central",
        mimeType="application/json",
    ),
    Resource(
        uri="nutanix://hosts",
        name="All Hosts",
        description="List all hypervisor hosts",
        mimeType="application/json",
    ),
    Resource(
        uri="nutanix://subnets",
        name="All Subnets",
        description="List all subnets/networks",
        mimeType="application/json",
    ),
    Resource(
        uri="nutanix://images",
        name="All Images",
        description="List all disk images (ISO, QCOW2)",
        mimeType="application/json",
    ),
]


# ─── Resource Handlers ────────────────────────────────────────────────────────


async def resolve_resource(client: NutanixClient, uri: str) -> list[TextResourceContents]:
    """Resolve a nutanix:// URI to resource contents."""
    parts = uri.replace("nutanix://", "").strip("/").split("/")
    resource_type = parts[0] if parts else ""
    resource_id = parts[1] if len(parts) > 1 else None

    sdk = client.sdk
    data: Any

    if resource_type == "vms":
        if resource_id:
            response = await sdk.call(sdk.vm_api.get_vm_by_id, resource_id)
            data = response.data.to_dict() if response.data else {}
        else:
            vms = await sdk.list_all(sdk.vm_api.list_vms)
            data = [vm.to_dict() for vm in vms]
    elif resource_type == "clusters":
        if resource_id:
            response = await sdk.call(sdk.cluster_api.get_cluster_by_id, resource_id)
            data = response.data.to_dict() if response.data else {}
        else:
            clusters = await sdk.list_all(sdk.cluster_api.list_clusters)
            data = [c.to_dict() for c in clusters]
    elif resource_type == "hosts":
        if resource_id:
            # SDK requires clusterExtId for get_host_by_id; use httpx fallback
            result = await client.v4_get(namespace="clustermgmt", path=f"config/hosts/{resource_id}")
            data = result.get("data", result)
        else:
            hosts = await sdk.list_all(sdk.cluster_api.list_hosts)
            data = [h.to_dict() for h in hosts]
    elif resource_type == "subnets":
        if resource_id:
            response = await sdk.call(sdk.subnet_api.get_subnet_by_id, resource_id)
            data = response.data.to_dict() if response.data else {}
        else:
            subnets = await sdk.list_all(sdk.subnet_api.list_subnets)
            data = [s.to_dict() for s in subnets]
    elif resource_type == "images":
        if resource_id:
            response = await sdk.call(sdk.image_api.get_image_by_id, resource_id)
            data = response.data.to_dict() if response.data else {}
        else:
            images = await sdk.list_all(sdk.image_api.list_images)
            data = [img.to_dict() for img in images]
    else:
        data = {"error": f"Unknown resource type: {resource_type}"}

    return [
        TextResourceContents(
            uri=uri,
            mimeType="application/json",
            text=json.dumps(data, indent=2, default=str),
        )
    ]
