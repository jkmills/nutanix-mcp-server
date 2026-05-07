"""Category assignment tools using Nutanix v4 prism namespace."""

from typing import Any

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

CATEGORY_TOOLS: list[dict] = [
    {
        "name": "assign_category",
        "description": (
            "Assign a category key:value pair to a VM. Categories are Nutanix's "
            "primary mechanism for resource organization, security policy targeting "
            "(Flow microsegmentation), and DR policy assignment."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the VM to tag.",
                },
                "category_key": {
                    "type": "string",
                    "description": "Category key (e.g., 'Environment', 'AppType', 'Backup').",
                },
                "category_value": {
                    "type": "string",
                    "description": "Category value (e.g., 'Production', 'WebServer', 'Gold').",
                },
            },
            "required": ["vm_uuid", "category_key", "category_value"],
        },
    },
    {
        "name": "remove_category",
        "description": (
            "Remove a category key:value assignment from a VM. "
            "Only removes the specified category; other categories remain intact."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the VM.",
                },
                "category_key": {
                    "type": "string",
                    "description": "Category key to remove.",
                },
                "category_value": {
                    "type": "string",
                    "description": "Category value to remove.",
                },
            },
            "required": ["vm_uuid", "category_key", "category_value"],
        },
    },
    {
        "name": "list_entities_by_category",
        "description": (
            "Find all VMs tagged with a specific category key:value pair. "
            "Useful for discovering resources by their organizational tags."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category_key": {
                    "type": "string",
                    "description": "Category key to query (e.g., 'Environment').",
                },
                "category_value": {
                    "type": "string",
                    "description": "Category value to query (e.g., 'Production').",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entities to return. Default: 50.",
                },
            },
            "required": ["category_key", "category_value"],
        },
    },
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_assign_category(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Assign a category to a VM by updating its category list."""
    vm_uuid = arguments["vm_uuid"]
    category_key = arguments["category_key"]
    category_value = arguments["category_value"]

    # Get current VM to preserve existing categories and obtain ETag
    current = await client.v4_get(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}",
    )
    vm_data = current.get("data", {})
    etag = vm_data.get("$metadata", {}).get("ETag")

    # Get existing categories and add new one (avoid duplicates)
    categories = vm_data.get("categories", [])
    already_assigned = any(c.get("key") == category_key and c.get("value") == category_value for c in categories)

    if already_assigned:
        return {
            "status": "already_assigned",
            "vm_uuid": vm_uuid,
            "category": f"{category_key}:{category_value}",
            "message": "Category is already assigned to this VM.",
        }

    categories.append({"key": category_key, "value": category_value})

    # Update VM with new categories
    update_body = {**vm_data}
    update_body["categories"] = categories
    # Remove metadata fields that shouldn't be sent back
    update_body.pop("$metadata", None)
    update_body.pop("links", None)
    update_body.pop("tenantId", None)

    headers = {}
    if etag:
        headers["If-Match"] = etag

    await client.v4_put(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}",
        body=update_body,
        headers=headers if headers else None,
    )

    return {
        "status": "category_assigned",
        "vm_uuid": vm_uuid,
        "category": f"{category_key}:{category_value}",
        "total_categories": len(categories),
    }


async def handle_remove_category(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Remove a category from a VM."""
    vm_uuid = arguments["vm_uuid"]
    category_key = arguments["category_key"]
    category_value = arguments["category_value"]

    # Get current VM state
    current = await client.v4_get(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}",
    )
    vm_data = current.get("data", {})
    etag = vm_data.get("$metadata", {}).get("ETag")

    categories = vm_data.get("categories", [])
    original_count = len(categories)

    # Remove matching category
    categories = [c for c in categories if not (c.get("key") == category_key and c.get("value") == category_value)]

    if len(categories) == original_count:
        return {
            "status": "not_found",
            "vm_uuid": vm_uuid,
            "category": f"{category_key}:{category_value}",
            "message": "Category was not assigned to this VM.",
        }

    # Update VM
    update_body = {**vm_data}
    update_body["categories"] = categories
    update_body.pop("$metadata", None)
    update_body.pop("links", None)
    update_body.pop("tenantId", None)

    headers = {}
    if etag:
        headers["If-Match"] = etag

    await client.v4_put(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}",
        body=update_body,
        headers=headers if headers else None,
    )

    return {
        "status": "category_removed",
        "vm_uuid": vm_uuid,
        "category": f"{category_key}:{category_value}",
        "remaining_categories": len(categories),
    }


async def handle_list_entities_by_category(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List VMs matching a category key:value pair."""
    category_key = arguments["category_key"]
    category_value = arguments["category_value"]
    limit = arguments.get("limit", 50)

    # Use OData filter on VMs endpoint to find matching entities
    filter_expr = f"categories/any(c:c/key eq '{category_key}' and c/value eq '{category_value}')"

    result = await client.v4_list(
        namespace="vmm",
        path="ahv/config/vms",
        filter=filter_expr,
        top=limit,
    )

    vms = result.get("data", [])

    formatted = []
    for vm in vms:
        formatted.append(
            {
                "vm_uuid": vm.get("extId", ""),
                "name": vm.get("name", ""),
                "power_state": vm.get("powerState", ""),
                "cluster": vm.get("cluster", {}).get("extId", ""),
            }
        )

    return {
        "category": f"{category_key}:{category_value}",
        "total_matches": len(formatted),
        "vms": formatted,
    }


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

CATEGORY_HANDLERS: dict[str, Any] = {
    "assign_category": handle_assign_category,
    "remove_category": handle_remove_category,
    "list_entities_by_category": handle_list_entities_by_category,
}
