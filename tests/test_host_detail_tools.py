"""Tests for host detail tools (Issue #18)."""

from unittest.mock import AsyncMock

import pytest

from nutanix_mcp.tools.prism_element import (
    handle_pe_get_host_disks,
    handle_pe_get_host_nics,
    handle_pe_list_cvms,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_get_host_disks(mock_client):
    """Test retrieving disk inventory for a host."""
    mock_client.pe_get.return_value = {
        "entities": [
            {
                "id": "disk-1",
                "disk_uuid": "d-uuid-1",
                "disk_hardware_config": {
                    "serial_number": "SN123456",
                    "model": "Samsung PM1733",
                    "current_firmware_version": "1.2.3",
                    "vendor": "Samsung",
                },
                "storage_tier_name": "SSD-SATA",
                "disk_status": "NORMAL",
                "disk_size": 1920383410176,
                "online": True,
                "mount_path": "/home/nutanix/data/stargate-storage/disks/disk-1",
                "location": 1,
            },
            {
                "id": "disk-2",
                "disk_uuid": "d-uuid-2",
                "disk_hardware_config": {
                    "serial_number": "SN789012",
                    "model": "Seagate Exos",
                    "current_firmware_version": "2.0.1",
                    "vendor": "Seagate",
                },
                "storage_tier_name": "DAS-SATA",
                "disk_status": "NORMAL",
                "disk_size": 8001563222016,
                "online": True,
                "mount_path": "/home/nutanix/data/stargate-storage/disks/disk-2",
                "location": 2,
            },
        ]
    }

    result = await handle_pe_get_host_disks(mock_client, {"pe_host": "10.0.0.1", "host_uuid": "host-uuid-1"})

    assert result["hostUuid"] == "host-uuid-1"
    assert result["count"] == 2
    assert result["disks"][0]["serialNumber"] == "SN123456"
    assert result["disks"][0]["model"] == "Samsung PM1733"
    assert result["disks"][0]["storageTierName"] == "SSD-SATA"
    assert result["disks"][1]["vendor"] == "Seagate"
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "hosts/host-uuid-1/host_disks")


@pytest.mark.asyncio
async def test_get_host_nics(mock_client):
    """Test retrieving NIC details for a host."""
    mock_client.pe_get.return_value = {
        "entities": [
            {
                "name": "eth0",
                "uuid": "nic-uuid-1",
                "mac_address": "00:11:22:33:44:55",
                "ip_address": "10.0.0.10",
                "link_speed_in_kbps": 10000000,
                "mtu_in_bytes": 9000,
                "interface_status": "UP",
                "dhcp_enabled": False,
                "switch_management_address": "10.0.0.254",
                "switch_port_id": "Ethernet1/1",
                "switch_vlan_id": 100,
            },
            {
                "name": "eth1",
                "uuid": "nic-uuid-2",
                "mac_address": "00:11:22:33:44:56",
                "ip_address": None,
                "link_speed_in_kbps": 10000000,
                "mtu_in_bytes": 1500,
                "interface_status": "UP",
                "dhcp_enabled": False,
                "switch_management_address": "10.0.0.254",
                "switch_port_id": "Ethernet1/2",
                "switch_vlan_id": 200,
            },
        ]
    }

    result = await handle_pe_get_host_nics(mock_client, {"pe_host": "10.0.0.1", "host_uuid": "host-uuid-1"})

    assert result["hostUuid"] == "host-uuid-1"
    assert result["count"] == 2
    assert result["nics"][0]["name"] == "eth0"
    assert result["nics"][0]["macAddress"] == "00:11:22:33:44:55"
    assert result["nics"][0]["linkSpeedMbps"] == 10000
    assert result["nics"][0]["mtu"] == 9000
    assert result["nics"][0]["switchPortId"] == "Ethernet1/1"
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "hosts/host-uuid-1/host_nics")


@pytest.mark.asyncio
async def test_list_cvms(mock_client):
    """Test listing Controller VMs."""
    mock_client.pe_list.return_value = {
        "entities": [
            {
                "name": "NTNX-node1-CVM",
                "uuid": "cvm-uuid-1",
                "power_state": "on",
                "memory_mb": 32768,
                "num_vcpus": 12,
                "host_uuid": "host-uuid-1",
                "ip_addresses": ["10.0.0.11"],
            },
            {
                "name": "NTNX-node2-CVM",
                "uuid": "cvm-uuid-2",
                "power_state": "on",
                "memory_mb": 32768,
                "num_vcpus": 12,
                "host_uuid": "host-uuid-2",
                "ip_addresses": ["10.0.0.12"],
            },
        ]
    }

    result = await handle_pe_list_cvms(mock_client, {"pe_host": "10.0.0.1"})

    assert result["count"] == 2
    assert result["cvms"][0]["name"] == "NTNX-node1-CVM"
    assert result["cvms"][0]["memoryMb"] == 32768
    assert result["cvms"][0]["ipAddresses"] == ["10.0.0.11"]
    mock_client.pe_list.assert_called_once_with("10.0.0.1", "vms", filter_criteria="is_cvm==true")
