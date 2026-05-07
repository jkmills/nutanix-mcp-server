"""Task tracking tools using Nutanix v4 prism namespace."""

from typing import Any

from nutanix_mcp.client import NutanixClient

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


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

TASK_HANDLERS: dict[str, Any] = {
    "list_tasks": handle_list_tasks,
    "get_task": handle_get_task,
}
