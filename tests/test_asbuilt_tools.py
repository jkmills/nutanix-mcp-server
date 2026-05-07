"""Tests for AsBuilt report generation tools."""

from unittest.mock import AsyncMock

import pytest

from nutanix_mcp.tools.asbuilt import (
    ALL_SECTIONS,
    _generate_markdown,
    _markdown_to_html_body,
    handle_export_asbuilt_html,
    handle_generate_asbuilt,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


# ─── Sample PE API responses ─────────────────────────────────────────────────

CLUSTER_RESPONSE = {
    "name": "test-cluster",
    "cluster_uuid": "uuid-1234",
    "version": "6.5.1",
    "num_nodes": 4,
    "storage_type": "mixed",
    "hypervisor_types": ["AHV"],
    "cluster_external_ipaddress": "10.0.0.100",
    "timezone": "UTC",
    "ncc_version": "4.6.0",
}

HOSTS_RESPONSE = {
    "entities": [
        {
            "name": "host-01",
            "uuid": "host-uuid-1",
            "hypervisor_address": "10.0.0.1",
            "controller_vm_backplane_ip": "10.0.0.11",
            "ipmi_address": "10.0.0.21",
            "cpu_model": "Intel Xeon Gold 6248",
            "num_cpu_sockets": 2,
            "num_cpu_cores": 40,
            "memory_capacity_in_bytes": 274877906944,
            "hypervisor_type": "AHV",
            "hypervisor_full_name": "AHV 20220304.342",
            "serial": "SN001",
            "block_model_name": "NX-3060-G7",
            "block_serial": "BLK001",
        },
        {
            "name": "host-02",
            "uuid": "host-uuid-2",
            "hypervisor_address": "10.0.0.2",
            "controller_vm_backplane_ip": "10.0.0.12",
            "ipmi_address": "10.0.0.22",
            "cpu_model": "Intel Xeon Gold 6248",
            "num_cpu_sockets": 2,
            "num_cpu_cores": 40,
            "memory_capacity_in_bytes": 274877906944,
            "hypervisor_type": "AHV",
            "hypervisor_full_name": "AHV 20220304.342",
            "serial": "SN002",
            "block_model_name": "NX-3060-G7",
            "block_serial": "BLK002",
        },
    ]
}

VMS_RESPONSE = {
    "entities": [
        {
            "name": "vm-01",
            "uuid": "vm-uuid-1",
            "power_state": "ON",
            "num_vcpus": 4,
            "memory_mb": 8192,
            "host_uuid": "host-uuid-1",
            "ip_addresses": ["10.0.1.10"],
            "vm_disk_info": [
                {"disk_capacity_in_bytes": 107374182400, "is_cdrom": False},
                {"disk_capacity_in_bytes": 0, "is_cdrom": True},
            ],
        },
        {
            "name": "vm-02",
            "uuid": "vm-uuid-2",
            "power_state": "OFF",
            "num_vcpus": 2,
            "memory_mb": 4096,
            "host_uuid": "host-uuid-2",
            "ip_addresses": [],
            "vm_disk_info": [
                {"disk_capacity_in_bytes": 53687091200, "is_cdrom": False},
            ],
        },
    ]
}

NETWORKS_RESPONSE = {
    "entities": [
        {
            "name": "VLAN100",
            "uuid": "net-uuid-1",
            "vlan_id": 100,
            "ip_config": {
                "network_address": "10.0.1.0",
                "prefix_length": "24",
            },
        },
        {
            "name": "VLAN200",
            "uuid": "net-uuid-2",
            "vlan_id": 200,
        },
    ]
}

CONTAINERS_RESPONSE = {
    "entities": [
        {
            "name": "default-container",
            "container_uuid": "ctr-uuid-1",
            "storage_pool_uuid": "sp-uuid-1",
            "max_capacity": 10995116277760,
            "replication_factor": 2,
            "compression_enabled": True,
            "on_disk_dedup": False,
            "erasure_coded": False,
        },
    ]
}

POOLS_RESPONSE = {
    "entities": [
        {
            "name": "default-pool",
            "storage_pool_uuid": "sp-uuid-1",
            "capacity": 10995116277760,
            "disks": ["d1", "d2", "d3", "d4"],
        },
    ]
}

DISKS_RESPONSE = {
    "entities": [
        {
            "id": "0:0",
            "disk_uuid": "disk-uuid-1",
            "storage_tier_name": "SSD",
            "disk_status": "NORMAL",
            "disk_size": 1099511627776,
            "host_name": "host-01",
            "online": True,
            "disk_hardware_config": {"serial_number": "DSK001"},
        },
        {
            "id": "0:1",
            "disk_uuid": "disk-uuid-2",
            "storage_tier_name": "HDD",
            "disk_status": "NORMAL",
            "disk_size": 4398046511104,
            "host_name": "host-01",
            "online": True,
            "disk_hardware_config": {"serial_number": "DSK002"},
        },
    ]
}

PD_RESPONSE = {
    "entities": [
        {
            "name": "pd-01",
            "active": True,
            "vms": [{"vm_name": "vm-01"}],
            "cron_schedules": [{"every_nth_minute": 60}],
            "replication_links": [{"remote_site_name": "remote-dc"}],
        },
    ]
}

ALERTS_RESPONSE = {
    "entities": [
        {
            "id": "alert-1",
            "alert_title": "Disk space low",
            "severity": "WARNING",
            "message": "Storage container usage above 80%",
            "resolved": False,
        },
    ]
}

HEALTH_RESPONSE = {
    "entities": [
        {"name": "check-1", "description": "NTP sync", "last_execution_status": "PASS"},
        {"name": "check-2", "description": "Disk health", "last_execution_status": "FAIL"},
    ]
}


def _setup_pe_mocks(client: AsyncMock):
    """Configure mock client to return sample PE data."""
    async def mock_pe_get(pe_host, path, params=None):
        responses = {
            "cluster": CLUSTER_RESPONSE,
            "alerts": ALERTS_RESPONSE,
            "health_checks": HEALTH_RESPONSE,
        }
        return responses.get(path, {})

    async def mock_pe_list(pe_host, resource, count=None):
        responses = {
            "hosts": HOSTS_RESPONSE,
            "vms": VMS_RESPONSE,
            "networks": NETWORKS_RESPONSE,
            "containers": CONTAINERS_RESPONSE,
            "storage_pools": POOLS_RESPONSE,
            "disks": DISKS_RESPONSE,
            "protection_domains": PD_RESPONSE,
        }
        return responses.get(resource, {"entities": []})

    client.pe_get = AsyncMock(side_effect=mock_pe_get)
    client.pe_list = AsyncMock(side_effect=mock_pe_list)


# ─── generate_asbuilt tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_asbuilt_all_sections(mock_client):
    """Full report with all sections."""
    _setup_pe_mocks(mock_client)

    result = await handle_generate_asbuilt(mock_client, {"pe_host": "10.0.0.100"})

    assert result["clusterName"] == "test-cluster"
    assert result["peHost"] == "10.0.0.100"
    assert result["sectionsIncluded"] == ALL_SECTIONS
    assert "sectionErrors" not in result

    md = result["markdown"]
    assert "# AsBuilt Report" in md
    assert "test-cluster" in md
    assert "## Cluster Overview" in md
    assert "## Host Inventory" in md
    assert "## Virtual Machine Inventory" in md
    assert "## Network Configuration" in md
    assert "## Storage Configuration" in md
    assert "## Data Protection" in md
    assert "## Active Alerts" in md
    assert "## Health Checks" in md
    assert "```mermaid" in md

    # Verify topology data for Excalidraw
    topo = result["topologyData"]
    assert topo["cluster"]["name"] == "test-cluster"
    assert len(topo["hosts"]) == 2
    assert topo["vmCount"] == 2
    assert topo["networkCount"] == 2


@pytest.mark.asyncio
async def test_generate_asbuilt_selected_sections(mock_client):
    """Report with only overview and hosts."""
    _setup_pe_mocks(mock_client)

    result = await handle_generate_asbuilt(
        mock_client,
        {"pe_host": "10.0.0.100", "sections": ["overview", "hosts"]},
    )

    assert result["sectionsIncluded"] == ["overview", "hosts"]
    md = result["markdown"]
    assert "## Cluster Overview" in md
    assert "## Host Inventory" in md
    assert "## Virtual Machine Inventory" not in md
    assert "## Storage Configuration" not in md


@pytest.mark.asyncio
async def test_generate_asbuilt_invalid_section(mock_client):
    """Invalid section name returns error."""
    result = await handle_generate_asbuilt(
        mock_client,
        {"pe_host": "10.0.0.100", "sections": ["bogus"]},
    )

    assert "error" in result
    assert "bogus" in str(result["error"])
    assert result["validSections"] == ALL_SECTIONS


@pytest.mark.asyncio
async def test_generate_asbuilt_section_error_partial(mock_client):
    """Section errors don't crash the whole report."""
    _setup_pe_mocks(mock_client)
    # Make alerts fail
    original_pe_get = mock_client.pe_get.side_effect

    async def failing_pe_get(pe_host, path, params=None):
        if path == "alerts":
            raise RuntimeError("Connection refused")
        return await original_pe_get(pe_host, path, params)

    mock_client.pe_get = AsyncMock(side_effect=failing_pe_get)

    result = await handle_generate_asbuilt(
        mock_client,
        {"pe_host": "10.0.0.100", "sections": ["overview", "alerts"]},
    )

    # overview should still work
    assert "## Cluster Overview" in result["markdown"]
    assert "sectionErrors" in result
    assert "alerts" in result["sectionErrors"]


# ─── Markdown content tests ──────────────────────────────────────────────────


def test_markdown_host_table_content():
    """Host table includes resource summary."""
    data = {
        "overview": {"name": "test", "uuid": "u", "version": "6.5", "numNodes": 2},
        "hosts": [
            {
                "name": "h1", "hypervisorAddress": "10.0.0.1", "cpuModel": "Xeon",
                "numCpuSockets": 2, "numCpuCores": 40, "memoryCapacityGb": 256,
                "hypervisorType": "AHV", "blockModel": "NX-3060", "serial": "S1",
            },
            {
                "name": "h2", "hypervisorAddress": "10.0.0.2", "cpuModel": "Xeon",
                "numCpuSockets": 2, "numCpuCores": 40, "memoryCapacityGb": 256,
                "hypervisorType": "AHV", "blockModel": "NX-3060", "serial": "S2",
            },
        ],
    }

    md = _generate_markdown("test", "10.0.0.100", data, ["hosts"])
    assert "**Total CPU Cores:** 80" in md
    assert "**Total RAM:** 512 GB" in md


def test_markdown_vm_power_state_counts():
    """VM section shows power state counts."""
    data = {
        "vms": [
            {"name": "v1", "powerState": "ON", "numVcpus": 4, "memoryMb": 8192,
             "ipAddresses": ["10.0.0.1"], "diskCapacityGb": 100},
            {"name": "v2", "powerState": "OFF", "numVcpus": 2, "memoryMb": 4096,
             "ipAddresses": [], "diskCapacityGb": 50},
        ],
    }

    md = _generate_markdown("test", "10.0.0.100", data, ["vms"])
    assert "🟢 1 on" in md
    assert "🔴 1 off" in md


# ─── HTML export tests ───────────────────────────────────────────────────────


def test_markdown_to_html_headings():
    """Headings convert correctly."""
    md = "# Title\n## Section\n### Subsection"
    html_out = _markdown_to_html_body(md)
    assert "<h1>Title</h1>" in html_out
    assert "<h2>Section</h2>" in html_out
    assert "<h3>Subsection</h3>" in html_out


def test_markdown_to_html_table():
    """Tables convert with thead/tbody."""
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
    html_out = _markdown_to_html_body(md)
    assert "<thead>" in html_out
    assert "<th>A</th>" in html_out
    assert "<td>1</td>" in html_out
    assert "<td>4</td>" in html_out


def test_markdown_to_html_mermaid():
    """Mermaid blocks become div.mermaid."""
    md = "```mermaid\ngraph TD\n    A-->B\n```"
    html_out = _markdown_to_html_body(md)
    assert 'class="mermaid"' in html_out
    assert "A-->B" in html_out


def test_markdown_to_html_list():
    """Lists convert to ul/li."""
    md = "- Item one\n- Item two"
    html_out = _markdown_to_html_body(md)
    assert "<ul>" in html_out
    assert "<li>Item one</li>" in html_out


def test_markdown_to_html_bold_and_code():
    """Inline bold and code formatting."""
    md = "This is **bold** and `code`"
    html_out = _markdown_to_html_body(md)
    assert "<strong>bold</strong>" in html_out
    assert "<code>code</code>" in html_out


@pytest.mark.asyncio
async def test_export_asbuilt_html(mock_client):
    """Export produces valid HTML with print CSS."""
    result = await handle_export_asbuilt_html(
        mock_client,
        {
            "markdown": "# Test Report\n\n## Section One\n\n| Col | Val |\n|-----|-----|\n| a | b |",
            "title": "My Report",
        },
    )

    html_out = result["html"]
    assert "<!DOCTYPE html>" in html_out
    assert "<title>My Report</title>" in html_out
    assert "@media print" in html_out
    assert "mermaid" in html_out
    assert "<h1>Test Report</h1>" in html_out
    assert "<th>Col</th>" in html_out
    assert result["title"] == "My Report"
