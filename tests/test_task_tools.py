"""Tests for task tracking tools (Issue #1)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nutanix_mcp.tools.task import handle_get_task, handle_list_tasks


@pytest.fixture
def mock_client():
    """Create a mock NutanixClient with SDK."""
    client = AsyncMock()
    sdk = AsyncMock()
    client.sdk = sdk
    return client


def _make_task_obj(**kwargs):
    """Create a mock task object with SDK-style attributes."""
    task = MagicMock()
    task.ext_id = kwargs.get("ext_id")
    task.status = kwargs.get("status")
    task.operation = kwargs.get("operation")
    task.percentage_complete = kwargs.get("percentage_complete")
    task.created_time = kwargs.get("created_time")
    task.started_time = kwargs.get("started_time")
    task.completed_time = kwargs.get("completed_time")
    task.last_updated_time = kwargs.get("last_updated_time")
    task.entities_affected = kwargs.get("entities_affected", [])
    task.error_messages = kwargs.get("error_messages")
    task.warnings = kwargs.get("warnings")
    task.parent_task = kwargs.get("parent_task")
    task.sub_tasks = kwargs.get("sub_tasks")
    return task


@pytest.mark.asyncio
async def test_list_tasks_default(mock_client):
    """list_tasks with no arguments returns recent tasks."""
    task = _make_task_obj(
        ext_id="task-uuid-1",
        status="SUCCEEDED",
        operation="VmCreate",
        percentage_complete=100,
        created_time="2026-05-07T10:00:00Z",
        completed_time="2026-05-07T10:01:00Z",
        last_updated_time="2026-05-07T10:01:00Z",
        entities_affected=[{"extId": "vm-uuid-1", "rel": "vmm:ahv:config:vm"}],
    )
    response = MagicMock()
    response.data = [task]
    mock_client.sdk.call.return_value = response

    result = await handle_list_tasks(mock_client, {})

    mock_client.sdk.call.assert_called_once()
    assert result["count"] == 1
    assert result["tasks"][0]["extId"] == "task-uuid-1"
    assert result["tasks"][0]["status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_list_tasks_with_filter(mock_client):
    """list_tasks passes filter and limit to the SDK."""
    response = MagicMock()
    response.data = []
    mock_client.sdk.call.return_value = response

    result = await handle_list_tasks(mock_client, {"filter": "status eq 'RUNNING'", "limit": 5})

    mock_client.sdk.call.assert_called_once()
    call_kwargs = mock_client.sdk.call.call_args.kwargs
    assert call_kwargs["_filter"] == "status eq 'RUNNING'"
    assert call_kwargs["_limit"] == 5
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_get_task(mock_client):
    """get_task retrieves a single task by UUID."""
    task = _make_task_obj(
        ext_id="task-uuid-1",
        status="FAILED",
        operation="VmPowerOn",
        percentage_complete=50,
        created_time="2026-05-07T10:00:00Z",
        started_time="2026-05-07T10:00:01Z",
        completed_time=None,
        last_updated_time="2026-05-07T10:00:30Z",
        entities_affected=[],
        error_messages=[{"message": "VM not found"}],
        warnings=None,
        parent_task=None,
        sub_tasks=None,
    )
    response = MagicMock()
    response.data = task
    mock_client.sdk.call.return_value = response

    result = await handle_get_task(mock_client, {"task_uuid": "task-uuid-1"})

    assert result["status"] == "FAILED"
    assert result["errorMessages"] == [{"message": "VM not found"}]
    assert result["percentageComplete"] == 50
