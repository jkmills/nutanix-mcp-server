"""Task tracking tools using Nutanix v4 prism namespace."""

from typing import Any

from nutanix_mcp.client import NutanixClient

# ─── Tool Definitions ─────────────────────────────────────────────────────────

TASK_TOOLS: list[dict] = [
    {
        "name": "list_tasks",
        "description": (
            "List recent Nutanix tasks (async operations). Returns task status, "
            "progress, and associated entity info. Useful for monitoring the outcome "
            "of write operations (create_vm, power_on_vm, etc.)."
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
                    "description": "Maximum number of tasks to return (default: 20).",
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


async def handle_list_tasks(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List tasks using v4 prism API."""
    filter_expr = arguments.get("filter")
    limit = arguments.get("limit", 20)

    result = await client.v4_list(
        namespace="prism",
        path="config/tasks",
        filter=filter_expr,
        orderby="createdTime desc",
        top=limit,
    )

    tasks = result.get("data", [])
    return {
        "count": len(tasks),
        "tasks": [
            {
                "extId": task.get("extId"),
                "status": task.get("status"),
                "operation": task.get("operation"),
                "percentageComplete": task.get("percentageComplete"),
                "createdTime": task.get("createdTime"),
                "completedTime": task.get("completedTime"),
                "lastUpdatedTime": task.get("lastUpdatedTime"),
                "entityRefs": task.get("entitiesAffected", []),
            }
            for task in tasks
        ],
    }


async def handle_get_task(
    client: NutanixClient, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get task details using v4 prism API."""
    task_uuid = arguments["task_uuid"]
    result = await client.v4_get(
        namespace="prism",
        path=f"config/tasks/{task_uuid}",
    )

    task = result.get("data", result)
    return {
        "extId": task.get("extId"),
        "status": task.get("status"),
        "operation": task.get("operation"),
        "percentageComplete": task.get("percentageComplete"),
        "createdTime": task.get("createdTime"),
        "startedTime": task.get("startedTime"),
        "completedTime": task.get("completedTime"),
        "lastUpdatedTime": task.get("lastUpdatedTime"),
        "entitiesAffected": task.get("entitiesAffected", []),
        "errorMessages": task.get("errorMessages"),
        "warnings": task.get("warnings"),
        "parentTask": task.get("parentTask"),
        "subTasks": task.get("subTasks"),
    }


# ─── Handler Dispatch ─────────────────────────────────────────────────────────

TASK_HANDLERS: dict[str, Any] = {
    "list_tasks": handle_list_tasks,
    "get_task": handle_get_task,
}
