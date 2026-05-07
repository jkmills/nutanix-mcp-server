"""VM management tools using Nutanix v4 vmm namespace."""

from typing import Any, Optional

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

VM_TOOLS: list[dict] = [
    {
        "name": "list_vms",
        "description": (
            "List virtual machines on Nutanix. Returns VM names, UUIDs, power states, "
            "and resource allocation. Supports OData filtering."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": (
                        "OData filter expression. Examples: "
                        "\"name eq 'my-vm'\", \"powerState eq 'ON'\""
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of VMs to return. Omit to retrieve all (auto-paginates).",
                },
            },
        },
    },
    {
        "name": "get_vm",
        "description": (
            "Get detailed information about a specific VM by its UUID. "
            "Returns full configuration including CPU, memory, disks, and NICs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the virtual machine",
                },
            },
            "required": ["vm_uuid"],
        },
    },
    {
        "name": "power_on_vm",
        "description": "Power on a virtual machine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the virtual machine",
                },
            },
            "required": ["vm_uuid"],
        },
    },
    {
        "name": "power_off_vm",
        "description": (
            "Power off a virtual machine. Uses ACPI shutdown by default (guest-initiated)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the virtual machine",
                },
                "force": {
                    "type": "boolean",
                    "description": "Force power off (hard shutdown) instead of ACPI guest shutdown",
                    "default": False,
                },
            },
            "required": ["vm_uuid"],
        },
    },
    {
        "name": "create_vm",
        "description": (
            "Create a new virtual machine. Requires name, cluster UUID, and basic specs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the new VM",
                },
                "cluster_uuid": {
                    "type": "string",
                    "description": "UUID of the cluster to create the VM on",
                },
                "num_vcpus": {
                    "type": "integer",
                    "description": "Number of vCPUs (default: 2)",
                    "default": 2,
                },
                "memory_mb": {
                    "type": "integer",
                    "description": "Memory in MB (default: 4096)",
                    "default": 4096,
                },
                "disk_size_gb": {
                    "type": "integer",
                    "description": "Boot disk size in GB (default: 40)",
                    "default": 40,
                },
            },
            "required": ["name", "cluster_uuid"],
        },
    },
    {
        "name": "update_vm",
        "description": (
            "Update a virtual machine's configuration (CPU, memory, name, description). "
            "The VM should be powered off for CPU/memory changes. Uses ETag-based "
            "concurrency control. Returns a task UUID for status tracking."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the virtual machine to update",
                },
                "name": {
                    "type": "string",
                    "description": "New name for the VM (optional)",
                },
                "description": {
                    "type": "string",
                    "description": "New description for the VM (optional)",
                },
                "num_vcpus": {
                    "type": "integer",
                    "description": "New total number of vCPUs (optional, VM must be off)",
                },
                "memory_mb": {
                    "type": "integer",
                    "description": "New memory in MB (optional, VM must be off)",
                },
            },
            "required": ["vm_uuid"],
        },
    },
    {
        "name": "delete_vm",
        "description": (
            "Delete a virtual machine permanently. This action cannot be undone. "
            "Requires explicit confirmation. Returns a task UUID for status tracking."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the virtual machine to delete",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true to confirm deletion. Safety guard against accidental deletes.",
                },
            },
            "required": ["vm_uuid", "confirm"],
        },
    },
    {
        "name": "clone_vm",
        "description": (
            "Clone an existing virtual machine. Creates a copy with a new name. "
            "Returns a task UUID for status tracking."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the source VM to clone",
                },
                "new_name": {
                    "type": "string",
                    "description": "Name for the cloned VM",
                },
            },
            "required": ["vm_uuid", "new_name"],
        },
    },
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_list_vms(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List VMs using v4 vmm API."""
    filter_expr = arguments.get("filter")
    limit = arguments.get("limit")

    result = await client.v4_list_all(
        namespace="vmm",
        path="ahv/config/vms",
        filter=filter_expr,
        max_results=limit,
    )

    # Normalize response
    vms = result.get("data", [])
    metadata = result.get("metadata", {})
    return {
        "count": len(vms),
        "truncated": metadata.get("truncated", False),
        "vms": [
            {
                "name": vm.get("name"),
                "extId": vm.get("extId"),
                "powerState": vm.get("powerState"),
                "numVcpus": vm.get("numSockets", 0) * vm.get("numCoresPerSocket", 0),
                "memorySizeMb": vm.get("memorySizeBytes", 0) // (1024 * 1024),
                "cluster": vm.get("cluster", {}).get("extId"),
            }
            for vm in vms
        ],
    }


async def handle_get_vm(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get VM details using v4 vmm API."""
    vm_uuid = arguments["vm_uuid"]
    result = await client.v4_get(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}",
    )
    return result.get("data", result)


async def handle_power_on_vm(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Power on a VM using v4 vmm API."""
    vm_uuid = arguments["vm_uuid"]
    result = await client.v4_post(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}/$actions/power-on",
        body={},
    )
    return {"status": "power_on_initiated", "taskExtId": result.get("data", {}).get("extId")}


async def handle_power_off_vm(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Power off a VM using v4 vmm API."""
    vm_uuid = arguments["vm_uuid"]
    force = arguments.get("force", False)

    action = "power-off" if force else "guest-shutdown"
    result = await client.v4_post(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}/$actions/{action}",
        body={},
    )
    return {"status": f"{action}_initiated", "taskExtId": result.get("data", {}).get("extId")}


async def handle_create_vm(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create a VM using v4 vmm API."""
    name = arguments["name"]
    cluster_uuid = arguments["cluster_uuid"]
    num_vcpus = arguments.get("num_vcpus", 2)
    memory_mb = arguments.get("memory_mb", 4096)
    disk_size_gb = arguments.get("disk_size_gb", 40)

    body = {
        "name": name,
        "cluster": {"extId": cluster_uuid},
        "numSockets": 1,
        "numCoresPerSocket": num_vcpus,
        "memorySizeBytes": memory_mb * 1024 * 1024,
        "disks": [
            {
                "diskSizeBytes": disk_size_gb * 1024 * 1024 * 1024,
                "storageConfig": {
                    "storageContainerReference": None,
                },
            }
        ],
    }

    result = await client.v4_post(
        namespace="vmm",
        path="ahv/config/vms",
        body=body,
    )
    return {
        "status": "vm_creation_initiated",
        "taskExtId": result.get("data", {}).get("extId"),
    }


async def handle_update_vm(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update a VM using v4 vmm API with ETag concurrency control."""
    vm_uuid = arguments["vm_uuid"]

    # First, fetch the current VM to get its ETag and current config
    current = await client.v4_get(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}",
    )
    vm_data = current.get("data", current)

    # Build the update body from current state + requested changes
    if "name" in arguments:
        vm_data["name"] = arguments["name"]
    if "description" in arguments:
        vm_data["description"] = arguments["description"]
    if "num_vcpus" in arguments:
        vm_data["numCoresPerSocket"] = arguments["num_vcpus"]
        vm_data["numSockets"] = 1
    if "memory_mb" in arguments:
        vm_data["memorySizeBytes"] = arguments["memory_mb"] * 1024 * 1024

    # Extract ETag from metadata for concurrency control
    etag = current.get("metadata", {}).get("ETag")
    headers = {}
    if etag:
        headers["If-Match"] = etag

    result = await client.v4_put(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}",
        body=vm_data,
        headers=headers or None,
    )
    return {
        "status": "vm_update_initiated",
        "taskExtId": result.get("data", {}).get("extId"),
    }


async def handle_delete_vm(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete a VM using v4 vmm API."""
    vm_uuid = arguments["vm_uuid"]
    confirm = arguments.get("confirm", False)

    if not confirm:
        return {
            "status": "error",
            "message": "Deletion not confirmed. Set 'confirm: true' to proceed with VM deletion.",
        }

    result = await client.v4_delete(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}",
    )
    return {
        "status": "vm_deletion_initiated",
        "taskExtId": result.get("data", {}).get("extId") if result else None,
    }


async def handle_clone_vm(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Clone a VM using v4 vmm API."""
    vm_uuid = arguments["vm_uuid"]
    new_name = arguments["new_name"]

    body = {
        "name": new_name,
    }

    result = await client.v4_post(
        namespace="vmm",
        path=f"ahv/config/vms/{vm_uuid}/$actions/clone",
        body=body,
    )
    return {
        "status": "vm_clone_initiated",
        "taskExtId": result.get("data", {}).get("extId"),
    }


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

VM_HANDLERS: dict[str, Any] = {
    "list_vms": handle_list_vms,
    "get_vm": handle_get_vm,
    "power_on_vm": handle_power_on_vm,
    "power_off_vm": handle_power_off_vm,
    "create_vm": handle_create_vm,
    "update_vm": handle_update_vm,
    "delete_vm": handle_delete_vm,
    "clone_vm": handle_clone_vm,
}
