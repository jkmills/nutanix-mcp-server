"""Networking tools using Nutanix v4 networking namespace."""

from typing import Any

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

NETWORKING_TOOLS: list[dict] = [
    {
        "name": "list_subnets",
        "description": (
            "List subnets/VLANs configured in Prism Central. Returns subnet names, "
            "VLAN IDs, CIDRs, IP pools, and associated clusters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": (
                        "OData filter expression. Examples: "
                        "\"name eq 'production-vlan'\", \"vlanId eq 100\""
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of subnets to return (default: 50)",
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "get_subnet",
        "description": (
            "Get detailed subnet configuration including IP pools, DHCP config, "
            "and virtual switch assignment."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "subnet_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the subnet",
                },
            },
            "required": ["subnet_uuid"],
        },
    },
    {
        "name": "list_images",
        "description": (
            "List disk images (ISOs, QCOW2) available in the image library. "
            "Returns image names, types, sizes, and source URIs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": (
                        "OData filter expression. Examples: "
                        "\"name eq 'ubuntu-22.04'\", \"type eq 'DISK_IMAGE'\""
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of images to return (default: 50)",
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "get_image",
        "description": (
            "Get detailed information about a specific disk image by UUID. "
            "Returns size, type, source, and cluster placement."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the image",
                },
            },
            "required": ["image_uuid"],
        },
    },
    {
        "name": "list_categories",
        "description": (
            "List category keys and their values used for resource tagging. "
            "Categories enable policy-based management (Flow, DR, etc.)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "OData filter expression. Example: \"key eq 'Environment'\"",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of categories to return (default: 50)",
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "get_category",
        "description": (
            "Get all values for a specific category key. "
            "Example: category 'Environment' may have values 'Production', 'Dev', 'Test'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the category",
                },
            },
            "required": ["category_uuid"],
        },
    },
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_list_subnets(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List subnets using v4 networking API."""
    filter_expr = arguments.get("filter")
    limit = arguments.get("limit", 50)

    result = await client.v4_list(
        namespace="networking",
        path="config/subnets",
        filter=filter_expr,
        top=limit,
    )

    subnets = result.get("data", [])
    return {
        "count": len(subnets),
        "subnets": [
            {
                "name": s.get("name"),
                "extId": s.get("extId"),
                "subnetType": s.get("subnetType"),
                "vlanId": s.get("networkId"),
                "cidr": _extract_cidr(s),
                "cluster": s.get("clusterReference"),
            }
            for s in subnets
        ],
    }


def _extract_cidr(subnet: dict) -> str | None:
    """Extract CIDR from subnet IP config."""
    ip_config = subnet.get("ipConfig")
    if not ip_config:
        return None
    ipv4 = ip_config.get("ipv4", {})
    ip = ipv4.get("ipSubnet", {}).get("ip", {}).get("value")
    prefix = ipv4.get("ipSubnet", {}).get("prefixLength")
    if ip and prefix:
        return f"{ip}/{prefix}"
    return None


async def handle_get_subnet(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get subnet details using v4 networking API."""
    subnet_uuid = arguments["subnet_uuid"]
    result = await client.v4_get(
        namespace="networking",
        path=f"config/subnets/{subnet_uuid}",
    )
    return result.get("data", result)


async def handle_list_images(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List images using v4 vmm API."""
    filter_expr = arguments.get("filter")
    limit = arguments.get("limit", 50)

    result = await client.v4_list(
        namespace="vmm",
        path="content/images",
        filter=filter_expr,
        top=limit,
    )

    images = result.get("data", [])
    return {
        "count": len(images),
        "images": [
            {
                "name": img.get("name"),
                "extId": img.get("extId"),
                "type": img.get("type"),
                "sizeBytes": img.get("sizeBytes"),
                "sourceUri": img.get("source", {}).get("url") if img.get("source") else None,
                "description": img.get("description"),
            }
            for img in images
        ],
    }


async def handle_get_image(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get image details using v4 vmm API."""
    image_uuid = arguments["image_uuid"]
    result = await client.v4_get(
        namespace="vmm",
        path=f"content/images/{image_uuid}",
    )
    return result.get("data", result)


async def handle_list_categories(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List categories using v4 prism API."""
    filter_expr = arguments.get("filter")
    limit = arguments.get("limit", 50)

    result = await client.v4_list(
        namespace="prism",
        path="config/categories",
        filter=filter_expr,
        top=limit,
    )

    categories = result.get("data", [])
    return {
        "count": len(categories),
        "categories": [
            {
                "key": cat.get("key"),
                "extId": cat.get("extId"),
                "value": cat.get("value"),
                "description": cat.get("description"),
                "type": cat.get("type"),
            }
            for cat in categories
        ],
    }


async def handle_get_category(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get category details using v4 prism API."""
    category_uuid = arguments["category_uuid"]
    result = await client.v4_get(
        namespace="prism",
        path=f"config/categories/{category_uuid}",
    )
    return result.get("data", result)


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

NETWORKING_HANDLERS: dict[str, Any] = {
    "list_subnets": handle_list_subnets,
    "get_subnet": handle_get_subnet,
    "list_images": handle_list_images,
    "get_image": handle_get_image,
    "list_categories": handle_list_categories,
    "get_category": handle_get_category,
}
