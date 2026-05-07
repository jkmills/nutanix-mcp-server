"""Tests for VM lifecycle tools (Issue #2): update_vm, delete_vm, clone_vm."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nutanix_mcp.tools.vm import handle_clone_vm, handle_delete_vm, handle_update_vm


@pytest.fixture
def mock_client():
    """Create a mock NutanixClient with SDK."""
    client = AsyncMock()
    sdk = AsyncMock()
    client.sdk = sdk
    return client


@pytest.mark.asyncio
async def test_update_vm_name(mock_client):
    """update_vm fetches current state, applies changes, and updates."""
    # Mock get_vm_by_id response
    vm_obj = MagicMock()
    vm_obj.name = "old-name"
    vm_obj.description = None
    vm_obj.num_sockets = 1
    vm_obj.num_cores_per_socket = 2
    vm_obj.memory_size_bytes = 4294967296
    get_response = MagicMock()
    get_response.data = vm_obj

    # Mock update response
    task_obj = MagicMock()
    task_obj.ext_id = "task-uuid-1"
    update_response = MagicMock()
    update_response.data = task_obj

    mock_client.sdk.call.side_effect = [get_response, update_response]

    result = await handle_update_vm(mock_client, {"vm_uuid": "vm-uuid-1", "name": "new-name"})

    assert result["status"] == "vm_update_initiated"
    assert result["taskExtId"] == "task-uuid-1"
    # Verify name was updated on the object
    assert vm_obj.name == "new-name"


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

    task_obj = MagicMock()
    task_obj.ext_id = "task-uuid-2"
    update_response = MagicMock()
    update_response.data = task_obj

    mock_client.sdk.call.side_effect = [get_response, update_response]

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
    """delete_vm proceeds when confirm=True."""
    task_obj = MagicMock()
    task_obj.ext_id = "task-uuid-3"
    response = MagicMock()
    response.data = task_obj
    mock_client.sdk.call.return_value = response

    result = await handle_delete_vm(mock_client, {"vm_uuid": "vm-uuid-1", "confirm": True})

    assert result["status"] == "vm_deletion_initiated"
    assert result["taskExtId"] == "task-uuid-3"
    mock_client.sdk.call.assert_called_once()


@pytest.mark.asyncio
async def test_clone_vm(mock_client):
    """clone_vm sends clone request with new name."""
    task_obj = MagicMock()
    task_obj.ext_id = "task-uuid-4"
    response = MagicMock()
    response.data = task_obj
    mock_client.sdk.call.return_value = response

    result = await handle_clone_vm(mock_client, {"vm_uuid": "vm-uuid-1", "new_name": "my-vm-clone"})

    assert result["status"] == "vm_clone_initiated"
    assert result["taskExtId"] == "task-uuid-4"
    mock_client.sdk.call.assert_called_once()
