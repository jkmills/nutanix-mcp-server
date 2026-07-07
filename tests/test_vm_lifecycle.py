"""Tests for VM lifecycle tools: update_vm, delete_vm, clone_vm, power ops.

All v4 mutating operations must pass the ETag from a preceding GET as
if_match — Nutanix rejects mutations without it (HTTP 428).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nutanix_mcp.tools.vm import (
    handle_clone_vm,
    handle_delete_vm,
    handle_power_off_vm,
    handle_power_on_vm,
    handle_update_vm,
)


@pytest.fixture
def mock_client():
    """Create a mock NutanixClient with SDK."""
    client = MagicMock()
    sdk = MagicMock()
    sdk.call = AsyncMock()
    sdk.get_etag = MagicMock(return_value="vm-etag-1")
    client.sdk = sdk
    return client


def _task_response(task_uuid: str) -> MagicMock:
    task_obj = MagicMock()
    task_obj.ext_id = task_uuid
    response = MagicMock()
    response.data = task_obj
    return response


@pytest.mark.asyncio
async def test_update_vm_name(mock_client):
    """update_vm fetches current state, applies changes, and updates with if_match."""
    vm_obj = MagicMock()
    vm_obj.name = "old-name"
    vm_obj.description = None
    vm_obj.num_sockets = 1
    vm_obj.num_cores_per_socket = 2
    vm_obj.memory_size_bytes = 4294967296
    get_response = MagicMock()
    get_response.data = vm_obj

    mock_client.sdk.call.side_effect = [get_response, _task_response("task-uuid-1")]

    result = await handle_update_vm(mock_client, {"vm_uuid": "vm-uuid-1", "name": "new-name"})

    assert result["status"] == "vm_update_initiated"
    assert result["taskExtId"] == "task-uuid-1"
    # Verify name was updated on the object
    assert vm_obj.name == "new-name"
    # Verify the ETag was passed as if_match
    update_call = mock_client.sdk.call.call_args_list[1]
    assert update_call.kwargs["if_match"] == "vm-etag-1"


@pytest.mark.asyncio
async def test_update_vm_cpu_memory(mock_client):
    """update_vm can change CPU and memory."""
    vm_obj = MagicMock()
    vm_obj.name = "my-vm"
    vm_obj.num_sockets = 1
    vm_obj.num_cores_per_socket = 2
    vm_obj.memory_size_bytes = 4294967296
    get_response = MagicMock()
    get_response.data = vm_obj

    mock_client.sdk.call.side_effect = [get_response, _task_response("task-uuid-2")]

    result = await handle_update_vm(mock_client, {"vm_uuid": "vm-uuid-1", "num_vcpus": 4, "memory_mb": 8192})

    assert vm_obj.num_cores_per_socket == 4
    assert vm_obj.memory_size_bytes == 8192 * 1024 * 1024
    assert result["status"] == "vm_update_initiated"


@pytest.mark.asyncio
async def test_delete_vm_without_confirm(mock_client):
    """delete_vm refuses without confirm=True."""
    result = await handle_delete_vm(mock_client, {"vm_uuid": "vm-uuid-1", "confirm": False})

    assert result["status"] == "error"
    assert "confirm" in result["message"].lower()
    mock_client.sdk.call.assert_not_called()


@pytest.mark.asyncio
async def test_delete_vm_with_confirm(mock_client):
    """delete_vm fetches the ETag then deletes with if_match."""
    get_response = MagicMock()
    mock_client.sdk.call.side_effect = [get_response, _task_response("task-uuid-3")]

    result = await handle_delete_vm(mock_client, {"vm_uuid": "vm-uuid-1", "confirm": True})

    assert result["status"] == "vm_deletion_initiated"
    assert result["taskExtId"] == "task-uuid-3"
    assert mock_client.sdk.call.call_count == 2
    delete_call = mock_client.sdk.call.call_args_list[1]
    assert delete_call.kwargs["if_match"] == "vm-etag-1"


@pytest.mark.asyncio
async def test_clone_vm(mock_client):
    """clone_vm sends clone request with new name and if_match."""
    get_response = MagicMock()
    mock_client.sdk.call.side_effect = [get_response, _task_response("task-uuid-4")]

    result = await handle_clone_vm(mock_client, {"vm_uuid": "vm-uuid-1", "new_name": "my-vm-clone"})

    assert result["status"] == "vm_clone_initiated"
    assert result["taskExtId"] == "task-uuid-4"
    assert mock_client.sdk.call.call_count == 2
    clone_call = mock_client.sdk.call.call_args_list[1]
    assert clone_call.kwargs["if_match"] == "vm-etag-1"


@pytest.mark.asyncio
async def test_power_on_vm(mock_client):
    """power_on_vm fetches the ETag then powers on with if_match."""
    get_response = MagicMock()
    mock_client.sdk.call.side_effect = [get_response, _task_response("task-uuid-5")]

    result = await handle_power_on_vm(mock_client, {"vm_uuid": "vm-uuid-1"})

    assert result["status"] == "power_on_initiated"
    power_call = mock_client.sdk.call.call_args_list[1]
    assert power_call.kwargs["if_match"] == "vm-etag-1"


@pytest.mark.asyncio
async def test_power_off_vm_force(mock_client):
    """power_off_vm with force uses hard power-off with if_match."""
    get_response = MagicMock()
    mock_client.sdk.call.side_effect = [get_response, _task_response("task-uuid-6")]

    result = await handle_power_off_vm(mock_client, {"vm_uuid": "vm-uuid-1", "force": True})

    assert result["status"] == "power-off_initiated"
    power_call = mock_client.sdk.call.call_args_list[1]
    assert power_call.kwargs["if_match"] == "vm-etag-1"


@pytest.mark.asyncio
async def test_power_off_vm_guest_shutdown(mock_client):
    """power_off_vm without force uses ACPI guest shutdown with if_match."""
    get_response = MagicMock()
    mock_client.sdk.call.side_effect = [get_response, _task_response("task-uuid-7")]

    result = await handle_power_off_vm(mock_client, {"vm_uuid": "vm-uuid-1"})

    assert result["status"] == "guest-shutdown_initiated"
    power_call = mock_client.sdk.call.call_args_list[1]
    assert power_call.kwargs["if_match"] == "vm-etag-1"
