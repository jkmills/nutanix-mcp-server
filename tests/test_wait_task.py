"""Tests for the wait_task tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nutanix_mcp.tools.task import handle_wait_task


def _task_response(status: str) -> MagicMock:
    task = MagicMock()
    task.ext_id = "task-1"
    task.status = status
    task.operation = "CreateVm"
    task.percentage_complete = 100
    task.created_time = None
    task.started_time = None
    task.completed_time = None
    task.last_updated_time = None
    task.entities_affected = []
    task.error_messages = None
    task.warnings = None
    task.parent_task = None
    task.sub_tasks = None
    response = MagicMock()
    response.data = task
    return response


@pytest.fixture
def mock_client():
    client = MagicMock()
    sdk = MagicMock()
    sdk.call = AsyncMock()
    client.sdk = sdk
    return client


@pytest.mark.asyncio
async def test_wait_task_returns_immediately_when_terminal(mock_client):
    mock_client.sdk.call.return_value = _task_response("SUCCEEDED")

    result = await handle_wait_task(mock_client, {"task_uuid": "task-1"})

    assert result["status"] == "SUCCEEDED"
    assert result["timedOut"] is False
    assert mock_client.sdk.call.await_count == 1


@pytest.mark.asyncio
async def test_wait_task_polls_until_done(mock_client, monkeypatch):
    async def instant_sleep(_seconds):
        pass

    monkeypatch.setattr("nutanix_mcp.tools.task.asyncio.sleep", instant_sleep)
    mock_client.sdk.call.side_effect = [
        _task_response("RUNNING"),
        _task_response("RUNNING"),
        _task_response("FAILED"),
    ]

    result = await handle_wait_task(mock_client, {"task_uuid": "task-1", "timeout_seconds": 60})

    assert result["status"] == "FAILED"
    assert result["timedOut"] is False
    assert mock_client.sdk.call.await_count == 3


@pytest.mark.asyncio
async def test_wait_task_times_out(mock_client, monkeypatch):
    async def instant_sleep(_seconds):
        pass

    monkeypatch.setattr("nutanix_mcp.tools.task.asyncio.sleep", instant_sleep)

    # Simulate the deadline passing after the first poll. time is the stdlib
    # module, so the fake must keep working after the sequence is consumed.
    times = [0.0, 100.0]

    def fake_monotonic() -> float:
        return times.pop(0) if len(times) > 1 else times[0]

    monkeypatch.setattr("nutanix_mcp.tools.task.time.monotonic", fake_monotonic)
    mock_client.sdk.call.return_value = _task_response("RUNNING")

    result = await handle_wait_task(mock_client, {"task_uuid": "task-1", "timeout_seconds": 10})

    assert result["timedOut"] is True
    assert "still RUNNING" in result["note"]


@pytest.mark.asyncio
async def test_wait_task_strips_enum_prefix(mock_client):
    """SDK enums may stringify as 'TaskStatus.SUCCEEDED'."""
    mock_client.sdk.call.return_value = _task_response("TaskStatus.SUCCEEDED")

    result = await handle_wait_task(mock_client, {"task_uuid": "task-1"})

    assert result["timedOut"] is False
