"""Tests for VM lifecycle tools (Issue #2): update_vm, delete_vm, clone_vm."""

import pytest
from unittest.mock import AsyncMock

from nutanix_mcp.tools.vm import handle_update_vm, handle_delete_vm, handle_clone_vm


@pytest.fixture
def mock_client():
    """Create a mock NutanixClient."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_update_vm_name(mock_client):
    """update_vm fetches current state, applies changes, PUTs with ETag."""
    mock_client.v4_get.return_value = {
        "data": {
            "extId": "vm-uuid-1",
            "name": "old-name",
            "numSockets": 1,
            "numCoresPerSocket": 2,
            "memorySizeBytes": 4294967296,
        },
        "metadata": {"ETag": "etag-123"},
    }
    mock_client.v4_put.return_value = {
        "data": {"extId": "task-uuid-1"}
    }

    result = await handle_update_vm(mock_client, {"vm_uuid": "vm-uuid-1", "name": "new-name"})

    mock_client.v4_get.assert_called_once_with(
        namespace="vmm",
        path="ahv/config/vms/vm-uuid-1",
    )
    call_kwargs = mock_client.v4_put.call_args
    assert call_kwargs.kwargs.get("headers") == {"If-Match": "etag-123"}
    assert result["status"] == "vm_update_initiated"
    assert result["taskExtId"] == "task-uuid-1"


@pytest.mark.asyncio
async def test_update_vm_cpu_memory(mock_client):
    """update_vm can change CPU and memory."""
    mock_client.v4_get.return_value = {
        "data": {
            "extId": "vm-uuid-1",
            "name": "my-vm",
            "numSockets": 1,
            "numCoresPerSocket": 2,
            "memorySizeBytes": 4294967296,
        },
        "metadata": {},
    }
    mock_client.v4_put.return_value = {"data": {"extId": "task-uuid-2"}}

    result = await handle_update_vm(
        mock_client, {"vm_uuid": "vm-uuid-1", "num_vcpus": 4, "memory_mb": 8192}
    )

    put_body = mock_client.v4_put.call_args.kwargs["body"]
    assert put_body["numCoresPerSocket"] == 4
    assert put_body["memorySizeBytes"] == 8192 * 1024 * 1024
    assert result["status"] == "vm_update_initiated"


@pytest.mark.asyncio
async def test_delete_vm_without_confirm(mock_client):
    """delete_vm refuses without confirm=True."""
    result = await handle_delete_vm(mock_client, {"vm_uuid": "vm-uuid-1", "confirm": False})

    assert result["status"] == "error"
    assert "confirm" in result["message"].lower()
    mock_client.v4_delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_vm_with_confirm(mock_client):
    """delete_vm proceeds when confirm=True."""
    mock_client.v4_delete.return_value = {"data": {"extId": "task-uuid-3"}}

    result = await handle_delete_vm(mock_client, {"vm_uuid": "vm-uuid-1", "confirm": True})

    mock_client.v4_delete.assert_called_once_with(
        namespace="vmm",
        path="ahv/config/vms/vm-uuid-1",
    )
    assert result["status"] == "vm_deletion_initiated"
    assert result["taskExtId"] == "task-uuid-3"


@pytest.mark.asyncio
async def test_clone_vm(mock_client):
    """clone_vm sends POST to $actions/clone with new name."""
    mock_client.v4_post.return_value = {"data": {"extId": "task-uuid-4"}}

    result = await handle_clone_vm(
        mock_client, {"vm_uuid": "vm-uuid-1", "new_name": "my-vm-clone"}
    )

    mock_client.v4_post.assert_called_once_with(
        namespace="vmm",
        path="ahv/config/vms/vm-uuid-1/$actions/clone",
        body={"name": "my-vm-clone"},
    )
    assert result["status"] == "vm_clone_initiated"
    assert result["taskExtId"] == "task-uuid-4"
