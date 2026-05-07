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
            "List recovery points (snapshots) for a specific VM. "
            "Returns snapshot names, creation times, and IDs for restore operations."
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
                    "description": "Maximum number of snapshots to return. Default: 20.",
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
    """Create a VM recovery point (snapshot)."""
    vm_uuid = arguments["vm_uuid"]
    name = arguments.get("name", "")
    expiration_days = arguments.get("expiration_days", 30)

    body: dict[str, Any] = {
        "vmRecoveryPoints": [
            {
                "vmExtId": vm_uuid,
            }
        ],
    }

    if name:
        body["name"] = name

    if expiration_days:
        body["expirationTime"] = f"P{expiration_days}D"

    result = await client.v4_post(
        namespace="dataprotection",
        path="config/recovery-points",
        body=body,
    )

    data = result.get("data", result)
    task_id = data.get("extId") or result.get("taskExtId", "")

    return {
        "status": "snapshot_initiated",
        "recovery_point_id": data.get("extId", ""),
        "task_id": task_id,
        "vm_uuid": vm_uuid,
        "name": name or "(auto-generated)",
    }


async def handle_list_vm_snapshots(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List recovery points for a specific VM."""
    vm_uuid = arguments["vm_uuid"]
    limit = arguments.get("limit", 20)

    # Filter recovery points that contain the specified VM
    result = await client.v4_list(
        namespace="dataprotection",
        path="config/recovery-points",
        filter=f"vmRecoveryPoints/any(v:v/vmExtId eq '{vm_uuid}')",
        top=limit,
    )

    snapshots = result.get("data", [])

    formatted = []
    for snap in snapshots:
        formatted.append(
            {
                "recovery_point_id": snap.get("extId", ""),
                "name": snap.get("name", ""),
                "status": snap.get("status", ""),
                "creation_time": snap.get("creationTime", ""),
                "expiration_time": snap.get("expirationTime", ""),
                "recovery_point_type": snap.get("recoveryPointType", ""),
            }
        )

    return {
        "vm_uuid": vm_uuid,
        "total_snapshots": len(formatted),
        "snapshots": formatted,
    }


async def handle_restore_vm_snapshot(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Restore a VM from a recovery point."""
    recovery_point_id = arguments["recovery_point_id"]
    vm_uuid = arguments["vm_uuid"]

    body = {
        "vmRecoveryPointRestoreOverrides": [
            {
                "vmExtId": vm_uuid,
            }
        ],
    }

    result = await client.v4_post(
        namespace="dataprotection",
        path=f"config/recovery-points/{recovery_point_id}/$actions/restore",
        body=body,
    )

    data = result.get("data", result)
    task_id = data.get("extId") or result.get("taskExtId", "")

    return {
        "status": "restore_initiated",
        "recovery_point_id": recovery_point_id,
        "vm_uuid": vm_uuid,
        "task_id": task_id,
    }


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

SNAPSHOT_HANDLERS: dict[str, Any] = {
    "snapshot_vm": handle_snapshot_vm,
    "list_vm_snapshots": handle_list_vm_snapshots,
    "restore_vm_snapshot": handle_restore_vm_snapshot,
}
