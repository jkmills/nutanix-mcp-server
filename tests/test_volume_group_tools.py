"""Tests for volume group tools (Issue #19)."""

from unittest.mock import AsyncMock

import pytest

from nutanix_mcp.tools.prism_element import (
    handle_pe_get_volume_group,
    handle_pe_list_volume_groups,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_list_volume_groups(mock_client):
    """Test listing volume groups."""
    mock_client.pe_list.return_value = {
        "entities": [
            {
                "name": "vg-oracle-data",
                "uuid": "vg-uuid-1",
                "disk_list": [
                    {"index": 0, "vmdisk_size_mb": 102400, "storage_container_uuid": "sc-uuid-1"},
                    {"index": 1, "vmdisk_size_mb": 204800, "storage_container_uuid": "sc-uuid-1"},
                ],
                "iscsi_target": "iqn.2010-06.com.nutanix:vg-oracle-data",
                "attachment_list": ["vm-uuid-1", "vm-uuid-2"],
                "flash_mode_enabled": True,
            },
            {
                "name": "vg-sql-logs",
                "uuid": "vg-uuid-2",
                "disk_list": [
                    {"index": 0, "vmdisk_size_mb": 51200, "storage_container_uuid": "sc-uuid-2"},
                ],
                "iscsi_target": "iqn.2010-06.com.nutanix:vg-sql-logs",
                "attachment_list": ["vm-uuid-3"],
                "flash_mode_enabled": False,
            },
        ]
    }

    result = await handle_pe_list_volume_groups(mock_client, {"pe_host": "10.0.0.1"})

    assert result["count"] == 2
    assert result["volumeGroups"][0]["name"] == "vg-oracle-data"
    assert len(result["volumeGroups"][0]["diskList"]) == 2
    assert result["volumeGroups"][0]["diskList"][0]["sizeMb"] == 102400
    assert result["volumeGroups"][0]["iscsiTarget"] == "iqn.2010-06.com.nutanix:vg-oracle-data"
    assert result["volumeGroups"][0]["flashModeEnabled"] is True
    assert result["volumeGroups"][1]["name"] == "vg-sql-logs"
    mock_client.pe_list.assert_called_once_with("10.0.0.1", "volume_groups")


@pytest.mark.asyncio
async def test_get_volume_group(mock_client):
    """Test getting detailed volume group config."""
    mock_client.pe_get.return_value = {
        "name": "vg-oracle-data",
        "uuid": "vg-uuid-1",
        "description": "Oracle database data disks",
        "disk_list": [
            {
                "index": 0,
                "vmdisk_size_mb": 102400,
                "storage_container_uuid": "sc-uuid-1",
                "vmdisk_uuid": "vmdisk-uuid-1",
            },
        ],
        "iscsi_target": "iqn.2010-06.com.nutanix:vg-oracle-data",
        "attachment_list": [{"vm_uuid": "vm-uuid-1"}],
        "flash_mode_enabled": True,
        "created_time_stamp_in_usecs": 1700000000000000,
    }

    result = await handle_pe_get_volume_group(mock_client, {"pe_host": "10.0.0.1", "uuid": "vg-uuid-1"})

    assert result["name"] == "vg-oracle-data"
    assert result["description"] == "Oracle database data disks"
    assert len(result["diskList"]) == 1
    assert result["diskList"][0]["vmdiskUuid"] == "vmdisk-uuid-1"
    assert result["flashModeEnabled"] is True
    assert result["createdTimestamp"] == 1700000000000000
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "volume_groups/vg-uuid-1")
