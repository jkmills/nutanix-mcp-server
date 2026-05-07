"""Tests for VM snapshot tools."""

import pytest
from unittest.mock import AsyncMock, patch

from nutanix_mcp.tools.snapshot import (
    handle_snapshot_vm,
    handle_list_vm_snapshots,
    handle_restore_vm_snapshot,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_snapshot_vm(mock_client):
    """Test creating a VM snapshot."""
    mock_client.v4_post.return_value = {
        "data": {
            "extId": "rp-uuid-123",
        },
        "taskExtId": "task-uuid-456",
    }

    result = await handle_snapshot_vm(mock_client, {
        "vm_uuid": "vm-uuid-abc",
        "name": "pre-update-snapshot",
        "expiration_days": 7,
    })

    assert result["status"] == "snapshot_initiated"
    assert result["recovery_point_id"] == "rp-uuid-123"
    assert result["vm_uuid"] == "vm-uuid-abc"
    assert result["name"] == "pre-update-snapshot"

    # Verify API call
    mock_client.v4_post.assert_called_once()
    call_args = mock_client.v4_post.call_args
    assert call_args.kwargs["namespace"] == "dataprotection"
    assert "recovery-points" in call_args.kwargs["path"]
    body = call_args.kwargs["body"]
    assert body["vmRecoveryPoints"][0]["vmExtId"] == "vm-uuid-abc"
    assert body["name"] == "pre-update-snapshot"
    assert body["expirationTime"] == "P7D"


@pytest.mark.asyncio
async def test_list_vm_snapshots(mock_client):
    """Test listing VM snapshots."""
    mock_client.v4_list.return_value = {
        "data": [
            {
                "extId": "rp-1",
                "name": "snapshot-1",
                "status": "COMPLETE",
                "creationTime": "2026-05-01T10:00:00Z",
                "expirationTime": "2026-06-01T10:00:00Z",
                "recoveryPointType": "APPLICATION_CONSISTENT",
            },
            {
                "extId": "rp-2",
                "name": "snapshot-2",
                "status": "COMPLETE",
                "creationTime": "2026-05-05T14:30:00Z",
                "expirationTime": "2026-06-05T14:30:00Z",
                "recoveryPointType": "CRASH_CONSISTENT",
            },
        ]
    }

    result = await handle_list_vm_snapshots(mock_client, {
        "vm_uuid": "vm-uuid-abc",
        "limit": 10,
    })

    assert result["vm_uuid"] == "vm-uuid-abc"
    assert result["total_snapshots"] == 2
    assert result["snapshots"][0]["recovery_point_id"] == "rp-1"
    assert result["snapshots"][1]["name"] == "snapshot-2"

    # Verify filter was applied
    mock_client.v4_list.assert_called_once()
    call_args = mock_client.v4_list.call_args
    assert "vm-uuid-abc" in call_args.kwargs["filter"]


@pytest.mark.asyncio
async def test_restore_vm_snapshot(mock_client):
    """Test restoring a VM from a snapshot."""
    mock_client.v4_post.return_value = {
        "data": {
            "extId": "task-uuid-789",
        },
    }

    result = await handle_restore_vm_snapshot(mock_client, {
        "recovery_point_id": "rp-uuid-123",
        "vm_uuid": "vm-uuid-abc",
    })

    assert result["status"] == "restore_initiated"
    assert result["recovery_point_id"] == "rp-uuid-123"
    assert result["vm_uuid"] == "vm-uuid-abc"

    # Verify API call
    mock_client.v4_post.assert_called_once()
    call_args = mock_client.v4_post.call_args
    assert "$actions/restore" in call_args.kwargs["path"]
    assert "rp-uuid-123" in call_args.kwargs["path"]
    body = call_args.kwargs["body"]
    assert body["vmRecoveryPointRestoreOverrides"][0]["vmExtId"] == "vm-uuid-abc"
