"""Tests for task tracking tools (Issue #1)."""

from unittest.mock import AsyncMock

import pytest

from nutanix_mcp.tools.task import handle_get_task, handle_list_tasks


@pytest.fixture
def mock_client():
    """Create a mock NutanixClient."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_list_tasks_default(mock_client):
    """list_tasks with no arguments returns recent tasks."""
    mock_client.v4_list.return_value = {
        "data": [
            {
                "extId": "task-uuid-1",
                "status": "SUCCEEDED",
                "operation": "VmCreate",
                "percentageComplete": 100,
                "createdTime": "2026-05-07T10:00:00Z",
                "completedTime": "2026-05-07T10:01:00Z",
                "lastUpdatedTime": "2026-05-07T10:01:00Z",
                "entitiesAffected": [{"extId": "vm-uuid-1", "rel": "vmm:ahv:config:vm"}],
            }
        ]
    }

    result = await handle_list_tasks(mock_client, {})

    mock_client.v4_list.assert_called_once_with(
        namespace="prism",
        path="config/tasks",
        filter=None,
        orderby="createdTime desc",
        top=20,
    )
    assert result["count"] == 1
    assert result["tasks"][0]["extId"] == "task-uuid-1"
    assert result["tasks"][0]["status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_list_tasks_with_filter(mock_client):
    """list_tasks passes filter and limit to the API."""
    mock_client.v4_list.return_value = {"data": []}

    result = await handle_list_tasks(mock_client, {"filter": "status eq 'RUNNING'", "limit": 5})

    mock_client.v4_list.assert_called_once_with(
        namespace="prism",
        path="config/tasks",
        filter="status eq 'RUNNING'",
        orderby="createdTime desc",
        top=5,
    )
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_get_task(mock_client):
    """get_task retrieves a single task by UUID."""
    mock_client.v4_get.return_value = {
        "data": {
            "extId": "task-uuid-1",
            "status": "FAILED",
            "operation": "VmPowerOn",
            "percentageComplete": 50,
            "createdTime": "2026-05-07T10:00:00Z",
            "startedTime": "2026-05-07T10:00:01Z",
            "completedTime": None,
            "lastUpdatedTime": "2026-05-07T10:00:30Z",
            "entitiesAffected": [],
            "errorMessages": [{"message": "VM not found"}],
            "warnings": None,
            "parentTask": None,
            "subTasks": None,
        }
    }

    result = await handle_get_task(mock_client, {"task_uuid": "task-uuid-1"})

    mock_client.v4_get.assert_called_once_with(
        namespace="prism",
        path="config/tasks/task-uuid-1",
    )
    assert result["status"] == "FAILED"
    assert result["errorMessages"] == [{"message": "VM not found"}]
    assert result["percentageComplete"] == 50
