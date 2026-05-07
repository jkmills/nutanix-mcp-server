"""MCP Resource Templates for browseable URI-based access to Nutanix entities."""

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

import json


async def resolve_resource(
    client: NutanixClient, uri: str
) -> list[TextResourceContents]:
    """Resolve a nutanix:// URI to resource contents."""
    parts = uri.replace("nutanix://", "").strip("/").split("/")
    resource_type = parts[0] if parts else ""
    resource_id = parts[1] if len(parts) > 1 else None

    data: Any

    if resource_type == "vms":
        if resource_id:
            data = await client.v4_get(namespace="vmm", path=f"ahv/config/vms/{resource_id}")
        else:
            data = await client.v4_list(namespace="vmm", path="ahv/config/vms", top=100)
    elif resource_type == "clusters":
        if resource_id:
            data = await client.v4_get(namespace="clustermgmt", path=f"config/clusters/{resource_id}")
        else:
            data = await client.v4_list(namespace="clustermgmt", path="config/clusters")
    elif resource_type == "hosts":
        if resource_id:
            data = await client.v4_get(namespace="clustermgmt", path=f"config/hosts/{resource_id}")
        else:
            data = await client.v4_list(namespace="clustermgmt", path="config/hosts", top=100)
    elif resource_type == "subnets":
        if resource_id:
            data = await client.v4_get(namespace="networking", path=f"config/subnets/{resource_id}")
        else:
            data = await client.v4_list(namespace="networking", path="config/subnets", top=100)
    elif resource_type == "images":
        if resource_id:
            data = await client.v4_get(namespace="vmm", path=f"content/images/{resource_id}")
        else:
            data = await client.v4_list(namespace="vmm", path="content/images", top=100)
    else:
        data = {"error": f"Unknown resource type: {resource_type}"}

    return [
        TextResourceContents(
            uri=uri,
            mimeType="application/json",
            text=json.dumps(data.get("data", data), indent=2),
        )
    ]
