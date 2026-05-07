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
                    "description": "Maximum number of VMs to return (default: 50)",
                    "default": 50,
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
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_list_vms(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List VMs using v4 vmm API."""
    filter_expr = arguments.get("filter")
    limit = arguments.get("limit", 50)

    result = await client.v4_list(
        namespace="vmm",
        path="ahv/config/vms",
        filter=filter_expr,
        top=limit,
    )

    # Normalize response
    vms = result.get("data", [])
    return {
        "count": len(vms),
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


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

VM_HANDLERS: dict[str, Any] = {
    "list_vms": handle_list_vms,
    "get_vm": handle_get_vm,
    "power_on_vm": handle_power_on_vm,
    "power_off_vm": handle_power_off_vm,
    "create_vm": handle_create_vm,
}
