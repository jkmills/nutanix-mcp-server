"""Task tracking tools using Nutanix v4 prism namespace."""

import asyncio
import time
from typing import Any

from nutanix_mcp.client import NutanixClient

# Task statuses that mean the task is still in flight
_PENDING_STATUSES = {"QUEUED", "RUNNING", "SUSPENDED"}

# ─── Tool Definitions ─────────────────────────────────────────────────────────

TASK_TOOLS: list[dict] = [
    {
        "name": "list_tasks",
        "description": (
            "List ALL recent Nutanix tasks (auto-paginates internally). "
            "Returns complete results in one call — no manual pagination needed. "
            "Use filter to narrow by status (RUNNING, FAILED, SUCCEEDED)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": (
                        "OData filter expression. Examples: "
                        "\"status eq 'RUNNING'\", "
                        "\"status eq 'FAILED'\", "
                        "\"status eq 'SUCCEEDED'\""
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional cap on results (default: 20).",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "get_task",
        "description": (
            "Get detailed status of a specific task by its UUID. Returns completion "
            "percentage, status, error details, and associated entities. Use this to "
            "verify whether an async operation (VM create, power on, etc.) succeeded."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the task to check",
                },
            },
            "required": ["task_uuid"],
        },
    },
    {
        "name": "wait_task",
        "description": (
            "Wait for an async Nutanix task to reach a terminal state "
            "(SUCCEEDED, FAILED, CANCELED). Polls internally so you don't have "
            "to call get_task in a loop. Returns the final task status, or the "
            "latest status with timedOut=true if the timeout elapses first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_uuid": {
                    "type": "string",
                    "description": "The UUID (extId) of the task to wait for",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum time to wait before returning (default: 60, max: 300)",
                    "default": 60,
                },
            },
            "required": ["task_uuid"],
        },
    },
]


# ─── Tool Handlers ────────────────────────────────────────────────────────────


async def handle_list_tasks(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """List tasks using official Nutanix SDK."""
    filter_expr = arguments.get("filter")
    limit = arguments.get("limit", 20)
    sdk = client.sdk

    kwargs: dict[str, Any] = {"_orderby": "createdTime desc", "_limit": limit}
    if filter_expr:
        kwargs["_filter"] = filter_expr

    response = await sdk.call(sdk.task_api.list_tasks, **kwargs)
    tasks = response.data or []

    return {
        "count": len(tasks),
        "tasks": [
            {
                "extId": task.ext_id,
                "status": task.status,
                "operation": task.operation,
                "percentageComplete": task.percentage_complete,
                "createdTime": task.created_time,
                "completedTime": task.completed_time,
                "lastUpdatedTime": task.last_updated_time,
                "entityRefs": task.entities_affected or [],
            }
            for task in tasks
        ],
    }


async def handle_get_task(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Get task details using official Nutanix SDK."""
    task_uuid = arguments["task_uuid"]
    sdk = client.sdk

    response = await sdk.call(sdk.task_api.get_task_by_id, task_uuid)
    task = response.data
    if not task:
        return {}

    return {
        "extId": task.ext_id,
        "status": task.status,
        "operation": task.operation,
        "percentageComplete": task.percentage_complete,
        "createdTime": task.created_time,
        "startedTime": task.started_time,
        "completedTime": task.completed_time,
        "lastUpdatedTime": task.last_updated_time,
        "entitiesAffected": task.entities_affected or [],
        "errorMessages": task.error_messages,
        "warnings": task.warnings,
        "parentTask": task.parent_task,
        "subTasks": task.sub_tasks,
    }


async def handle_wait_task(client: NutanixClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Poll a task until it reaches a terminal state or the timeout elapses."""
    task_uuid = arguments["task_uuid"]
    timeout_seconds = min(int(arguments.get("timeout_seconds", 60)), 300)
    poll_interval = 3.0

    deadline = time.monotonic() + timeout_seconds
    while True:
        result = await handle_get_task(client, {"task_uuid": task_uuid})
        status = str(result.get("status") or "").upper()
        # SDK enums may render as e.g. "TaskStatus.SUCCEEDED"
        status = status.rsplit(".", 1)[-1]

        if status and status not in _PENDING_STATUSES:
            result["timedOut"] = False
            return result

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            result["timedOut"] = True
            result["note"] = (
                f"Task still {status or 'PENDING'} after {timeout_seconds}s. "
                "Call wait_task or get_task again to keep tracking it."
            )
            return result

        await asyncio.sleep(min(poll_interval, remaining))


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

TASK_HANDLERS: dict[str, Any] = {
    "list_tasks": handle_list_tasks,
    "get_task": handle_get_task,
    "wait_task": handle_wait_task,
}
