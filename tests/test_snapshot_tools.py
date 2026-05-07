"""Tests for VM snapshot tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nutanix_mcp.tools.snapshot import (
    handle_list_vm_snapshots,
    handle_restore_vm_snapshot,
    handle_snapshot_vm,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    sdk = AsyncMock()
    client.sdk = sdk
    return client


@pytest.mark.asyncio
async def test_snapshot_vm(mock_client):
    """Test creating a VM snapshot."""
    task_data = MagicMock()
    task_data.ext_id = "rp-uuid-123"
    response = MagicMock()
    response.data = task_data
    mock_client.sdk.call.return_value = response

    result = await handle_snapshot_vm(
        mock_client,
        {
            "vm_uuid": "12345678-1234-1234-1234-123456789abc",
            "name": "pre-update-snapshot",
            "expiration_days": 7,
        },
    )

    assert result["status"] == "snapshot_initiated"
    assert result["recovery_point_id"] == "rp-uuid-123"
    assert result["vm_uuid"] == "12345678-1234-1234-1234-123456789abc"
    assert result["name"] == "pre-update-snapshot"
    mock_client.sdk.call.assert_called_once()


@pytest.mark.asyncio
async def test_list_vm_snapshots(mock_client):
    """Test listing VM snapshots."""
    snap1 = MagicMock()
    snap1.ext_id = "rp-1"
    snap1.name = "snapshot-1"
    snap1.status = "COMPLETE"
    snap1.creation_time = "2026-05-01T10:00:00Z"
    snap1.expiration_time = "2026-06-01T10:00:00Z"
    snap1.recovery_point_type = "APPLICATION_CONSISTENT"

    snap2 = MagicMock()
    snap2.ext_id = "rp-2"
    snap2.name = "snapshot-2"
    snap2.status = "COMPLETE"
    snap2.creation_time = "2026-05-05T14:30:00Z"
    snap2.expiration_time = "2026-06-05T14:30:00Z"
    snap2.recovery_point_type = "CRASH_CONSISTENT"

    response = MagicMock()
    response.data = [snap1, snap2]
    mock_client.sdk.call.return_value = response

    result = await handle_list_vm_snapshots(
        mock_client,
        {
            "vm_uuid": "12345678-1234-1234-1234-123456789abc",
            "limit": 10,
        },
    )

    assert result["vm_uuid"] == "12345678-1234-1234-1234-123456789abc"
    assert result["total_snapshots"] == 2
    assert result["snapshots"][0]["recovery_point_id"] == "rp-1"
    assert result["snapshots"][1]["name"] == "snapshot-2"


@pytest.mark.asyncio
async def test_restore_vm_snapshot(mock_client):
    """Test restoring a VM from a snapshot."""
    task_data = MagicMock()
    task_data.ext_id = "task-uuid-789"
    response = MagicMock()
    response.data = task_data
    mock_client.sdk.call.return_value = response

    result = await handle_restore_vm_snapshot(
        mock_client,
        {
            "recovery_point_id": "rp-uuid-123",
            "vm_uuid": "12345678-1234-1234-1234-123456789abc",
        },
    )

    assert result["status"] == "restore_initiated"
    assert result["recovery_point_id"] == "rp-uuid-123"
    assert result["vm_uuid"] == "12345678-1234-1234-1234-123456789abc"
    mock_client.sdk.call.assert_called_once()
