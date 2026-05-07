"""Tests for data protection tools (Issue #17)."""

from unittest.mock import AsyncMock

import pytest

from nutanix_mcp.tools.prism_element import (
    handle_pe_get_protection_domain,
    handle_pe_get_replication_status,
    handle_pe_list_remote_sites,
    handle_pe_list_unprotected_vms,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_get_protection_domain(mock_client):
    """Test retrieving detailed protection domain config."""
    mock_client.pe_get.return_value = {
        "name": "pd-prod",
        "active": True,
        "cron_schedules": [{"every_nth_minute": 60, "type": "HOURLY"}],
        "replication_links": [{"remote_site_name": "dr-site", "id": "link-1"}],
        "vms": [
            {"vm_name": "web-server-01", "vm_id": "vm-uuid-1", "consistency_group_name": "web-cg"},
            {"vm_name": "db-server-01", "vm_id": "vm-uuid-2", "consistency_group_name": "db-cg"},
        ],
        "nfs_files": [],
        "volume_groups": [],
        "marked_for_removal": False,
    }

    result = await handle_pe_get_protection_domain(mock_client, {"pe_host": "10.0.0.1", "name": "pd-prod"})

    assert result["name"] == "pd-prod"
    assert result["active"] is True
    assert len(result["vms"]) == 2
    assert result["vms"][0]["vmName"] == "web-server-01"
    assert result["vms"][0]["consistencyGroup"] == "web-cg"
    assert result["markedForRemoval"] is False
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "protection_domains/pd-prod")


@pytest.mark.asyncio
async def test_list_remote_sites(mock_client):
    """Test listing remote sites."""
    mock_client.pe_list.return_value = {
        "entities": [
            {
                "name": "dr-site-east",
                "uuid": "rs-uuid-1",
                "remote_ip_ports": {"10.1.0.1": 2020},
                "capabilities": ["BACKUP", "DISASTER_RECOVERY"],
                "compression_enabled": True,
                "bandwidth_policy_enabled": True,
                "max_bandwidth_kbps": 102400,
                "proxy_enabled": False,
                "ssh_enabled": True,
                "vstore_name_map": {"default": "default"},
            }
        ]
    }

    result = await handle_pe_list_remote_sites(mock_client, {"pe_host": "10.0.0.1"})

    assert result["count"] == 1
    assert result["remoteSites"][0]["name"] == "dr-site-east"
    assert result["remoteSites"][0]["compressionEnabled"] is True
    assert result["remoteSites"][0]["maxBandwidthMbps"] == 100
    mock_client.pe_list.assert_called_once_with("10.0.0.1", "remote_sites")


@pytest.mark.asyncio
async def test_get_replication_status(mock_client):
    """Test getting replication status for a protection domain."""
    mock_client.pe_get.return_value = {
        "entities": [
            {
                "id": "repl-1",
                "protection_domain_name": "pd-prod",
                "remote_site_name": "dr-site-east",
                "snapshot_id": "snap-123",
                "replication_status": "IN_PROGRESS",
                "completed_percentage": 75,
                "completed_bytes": 7516192768,
                "total_bytes": 10021923840,
            }
        ]
    }

    result = await handle_pe_get_replication_status(
        mock_client, {"pe_host": "10.0.0.1", "protection_domain": "pd-prod"}
    )

    assert result["count"] == 1
    assert result["replications"][0]["status"] == "IN_PROGRESS"
    assert result["replications"][0]["completedPercentage"] == 75
    assert result["replications"][0]["remoteSiteName"] == "dr-site-east"
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "protection_domains/pd-prod/replications")


@pytest.mark.asyncio
async def test_list_unprotected_vms(mock_client):
    """Test listing VMs not in any protection domain."""
    mock_client.pe_list.side_effect = [
        # First call: all VMs
        {
            "entities": [
                {"name": "web-01", "uuid": "vm-1", "power_state": "on", "host_uuid": "h1", "controller_vm": False},
                {"name": "db-01", "uuid": "vm-2", "power_state": "on", "host_uuid": "h1", "controller_vm": False},
                {"name": "app-01", "uuid": "vm-3", "power_state": "off", "host_uuid": "h2", "controller_vm": False},
                {"name": "CVM", "uuid": "vm-cvm", "power_state": "on", "host_uuid": "h1", "controller_vm": True},
            ]
        },
        # Second call: protection domains
        {
            "entities": [
                {
                    "name": "pd-prod",
                    "vms": [{"vm_id": "vm-1"}, {"vm_id": "vm-2"}],
                }
            ]
        },
    ]

    result = await handle_pe_list_unprotected_vms(mock_client, {"pe_host": "10.0.0.1"})

    assert result["totalVms"] == 4
    assert result["protectedVms"] == 2
    assert result["unprotectedCount"] == 1  # vm-3 (app-01); CVM excluded
    assert result["unprotectedVms"][0]["name"] == "app-01"
    assert result["unprotectedVms"][0]["uuid"] == "vm-3"
