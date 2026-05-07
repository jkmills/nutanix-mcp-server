"""VM snapshot/recovery point tools using Nutanix v4 dataprotection namespace."""

from typing import Any

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

SNAPSHOT_TOOLS: list[dict] = [
    {
        "name": "snapshot_vm",
        "description": (
            "Create an on-demand snapshot (recovery point) of a VM. "
            "Returns the recovery point ID and task UUID for tracking. "
            "Use before mutating operations as a safety net."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the VM to snapshot.",
                },
                "name": {
                    "type": "string",
                    "description": "Optional name for the recovery point. Defaults to auto-generated.",
                },
                "expiration_days": {
                    "type": "integer",
                    "description": "Number of days before the recovery point expires. Default: 30.",
                },
            },
            "required": ["vm_uuid"],
        },
    },
    {
        "name": "list_vm_snapshots",
        "description": (
            "List ALL recovery points (snapshots) for a specific VM (auto-paginates internally). "
            "Returns complete results in one call — no manual pagination needed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the VM whose snapshots to list.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional cap on results. Default: 20.",
                },
            },
            "required": ["vm_uuid"],
        },
    },
    {
        "name": "restore_vm_snapshot",
        "description": (
            "Restore a VM to a previous recovery point (snapshot). "
            "This reverts the VM's disks and configuration to the snapshot state. "
            "The VM should be powered off before restore."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "recovery_point_id": {
                    "type": "string",
                    "description": "The UUID of the recovery point to restore from.",
                },
                "vm_uuid": {
                    "type": "string",
                    "description": "The UUID of the VM to restore.",
                },
            },
            "required": ["recovery_point_id", "vm_uuid"],
        },
    },
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_snapshot_vm(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Create a VM recovery point (snapshot) using official Nutanix SDK."""
    from ntnx_dataprotection_py_client.models.dataprotection.v4.config.RecoveryPoint import RecoveryPoint
    from ntnx_dataprotection_py_client.models.dataprotection.v4.config.VmRecoveryPoint import VmRecoveryPoint

    vm_uuid = arguments["vm_uuid"]
    name = arguments.get("name", "")
    expiration_days = arguments.get("expiration_days", 30)
    sdk = client.sdk

    vm_rp = VmRecoveryPoint()
    vm_rp.vm_ext_id = vm_uuid

    rp = RecoveryPoint()
    rp.vm_recovery_points = [vm_rp]
    if name:
        rp.name = name
    if expiration_days:
        rp.expiration_time = f"P{expiration_days}D"

    response = await sdk.call(sdk.recovery_point_api.create_recovery_point, rp)
    data = response.data
    task_id = data.ext_id if data else ""

    return {
        "status": "snapshot_initiated",
        "recovery_point_id": data.ext_id if data else "",
        "task_id": task_id,
        "vm_uuid": vm_uuid,
        "name": name or "(auto-generated)",
    }


async def handle_list_vm_snapshots(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List recovery points for a specific VM using official Nutanix SDK."""
    vm_uuid = arguments["vm_uuid"]
    limit = arguments.get("limit", 20)
    sdk = client.sdk

    filter_expr = f"vmRecoveryPoints/any(v:v/vmExtId eq '{vm_uuid}')"
    response = await sdk.call(
        sdk.recovery_point_api.list_recovery_points, _limit=limit, _filter=filter_expr
    )
    snapshots = response.data or []

    formatted = []
    for snap in snapshots:
        formatted.append(
            {
                "recovery_point_id": snap.ext_id or "",
                "name": snap.name or "",
                "status": snap.status or "",
                "creation_time": snap.creation_time or "",
                "expiration_time": snap.expiration_time or "",
                "recovery_point_type": snap.recovery_point_type or "",
            }
        )

    return {
        "vm_uuid": vm_uuid,
        "total_snapshots": len(formatted),
        "snapshots": formatted,
    }


async def handle_restore_vm_snapshot(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Restore a VM from a recovery point using official Nutanix SDK."""
    recovery_point_id = arguments["recovery_point_id"]
    sdk = client.sdk

    # Pass None body to restore all VMs in the recovery point
    response = await sdk.call(sdk.recovery_point_api.restore_recovery_point, recovery_point_id)
    data = response.data
    task_id = data.ext_id if data else ""

    return {
        "status": "restore_initiated",
        "recovery_point_id": recovery_point_id,
        "vm_uuid": arguments["vm_uuid"],
        "task_id": task_id,
    }


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

SNAPSHOT_HANDLERS: dict[str, Any] = {
    "snapshot_vm": handle_snapshot_vm,
    "list_vm_snapshots": handle_list_vm_snapshots,
    "restore_vm_snapshot": handle_restore_vm_snapshot,
}
