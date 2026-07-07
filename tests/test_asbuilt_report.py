"""Tests for the standalone AsBuilt report tool (asbuilt package).

The collectors consume MCP tool outputs through a fake call_tool, so these
tests double as a contract check between the pe_* tools and the report.
"""

from unittest.mock import MagicMock

import pytest

from asbuilt.cli import ToolCallError, parse_tool_result
from asbuilt.report import (
    ALL_SECTIONS,
    _friendly_hypervisor,
    _friendly_storage_type,
    _strip_k_prefix,
    collect_report_data,
    render_html,
    render_markdown,
)

# ─── Canned MCP tool outputs (shape-matched to the pe_* handlers) ─────────────

TOOL_OUTPUTS: dict[str, dict] = {
    "pe_get_cluster_info": {
        "name": "prod-cluster",
        "clusterUuid": "c-uuid-1",
        "version": "6.8.1",
        "nccVersion": "5.1.0",
        "numNodes": 3,
        "storageType": "all_flash",
        "hypervisorTypes": ["kKvm"],
        "clusterExternalIp": "10.0.0.10",
        "externalDataServicesIp": "10.0.0.11",
        "externalSubnet": "10.0.0.0/24",
        "internalSubnet": "192.168.5.0/24",
        "nameServers": ["10.0.0.2"],
        "ntpServers": ["pool.ntp.org"],
        "timezone": "UTC",
        "operationMode": "Normal",
        "redundancyFactor": 2,
        "faultToleranceDomainType": "NODE",
    },
    "pe_list_hosts": {
        "count": 1,
        "hosts": [
            {
                "name": "node-01",
                "uuid": "h-uuid-1",
                "hypervisorAddress": "10.0.0.21",
                "cvmAddress": "10.0.0.31",
                "ipmiAddress": "10.0.0.41",
                "cpuModel": "Xeon Gold 6338",
                "numCpuSockets": 2,
                "numCpuCores": 64,
                "cpuCapacityGhz": 128.0,
                "memoryCapacityGb": 512,
                "hypervisorType": "kKvm",
                "hypervisorVersion": "Nutanix 20230302.100",
                "serial": "NODE-SER-1",
                "blockModel": "NX-3060-G8",
                "blockSerial": "BLK-SER-1",
                "bmcVersion": "7.10",
                "biosVersion": "G8-2.1",
                "numVms": 12,
            }
        ],
    },
    "pe_get_host_disks": {
        "hostUuid": "h-uuid-1",
        "count": 1,
        "disks": [
            {
                "location": 1,
                "id": "disk-1",
                "serialNumber": "S123",
                "model": "SAMSUNG MZ7LH",
                "vendor": "Samsung",
                "firmware": "904Q",
                "storageTierName": "kSSD",
                "diskStatus": "NORMAL",
                "capacityBytes": 1920 * 1024**3,
                "onlineStatus": True,
            }
        ],
    },
    "pe_list_vms": {
        "count": 2,
        "vms": [
            {
                "name": "web-01",
                "uuid": "vm-1",
                "powerState": "on",
                "numVcpus": 4,
                "memoryMb": 8192,
                "hostUuid": "h-uuid-1",
                "ipAddresses": ["10.0.1.5"],
                "diskCapacityGb": 100,
            },
            {
                "name": "db-01",
                "uuid": "vm-2",
                "powerState": "off",
                "numVcpus": 8,
                "memoryMb": 16384,
                "hostUuid": "h-uuid-1",
                "ipAddresses": [],
                "diskCapacityGb": 500,
            },
        ],
    },
    "pe_list_networks": {
        "count": 1,
        "networks": [
            {
                "name": "vlan-100",
                "uuid": "net-1",
                "vlanId": 100,
                "networkType": "kVlan",
                "ipConfig": {
                    "networkAddress": "10.0.1.0",
                    "prefixLength": 24,
                    "defaultGateway": "10.0.1.1",
                },
            }
        ],
    },
    "pe_list_containers": {
        "count": 1,
        "containers": [
            {
                "name": "default-container",
                "containerUuid": "sc-1",
                "maxCapacityBytes": 10 * 1024**4,
                "replicationFactor": 2,
                "compressionEnabled": True,
                "dedupEnabled": False,
                "erasureCoded": False,
            }
        ],
    },
    "pe_list_storage_pools": {
        "count": 1,
        "storagePools": [
            {"name": "default-pool", "uuid": "sp-1", "capacityBytes": 20 * 1024**4, "numDisks": 6}
        ],
    },
    "pe_list_disks": {
        "count": 2,
        "disks": [
            {"storageTierName": "kSSD", "capacityBytes": 2 * 1024**4},
            {"storageTierName": "kSSD", "capacityBytes": 2 * 1024**4},
        ],
    },
    "pe_get_auth_config": {
        "authTypes": ["LOCAL", "DIRECTORY_SERVICE"],
        "directories": [
            {
                "name": "corp-ad",
                "directoryType": "ACTIVE_DIRECTORY",
                "domain": "corp.example.com",
                "directoryUrl": "ldaps://dc01.corp.example.com",
            }
        ],
    },
    "pe_get_smtp_config": {
        "address": "smtp.example.com",
        "port": 587,
        "secureMode": "STARTTLS",
        "fromEmailAddress": "nutanix@example.com",
    },
    "pe_get_snmp_config": {
        "enabled": True,
        "traps": [{"address": "10.0.0.50"}],
        "users": [{"username": "monitor"}],
        "transports": [],
    },
    "pe_get_syslog_config": {"count": 1, "servers": [{"serverName": "syslog01"}]},
    "pe_get_licensing_info": {"category": "Ultimate"},
    "pe_list_images": {
        "count": 1,
        "images": [
            {"name": "ubuntu-22.04", "imageType": "DISK_IMAGE", "imageState": "ACTIVE", "sizeMb": 2048}
        ],
    },
    "pe_get_nfs_whitelists": {"count": 1, "whitelists": ["10.0.0.0/24"]},
    "pe_list_protection_domains": {
        "count": 1,
        "protectionDomains": [
            {
                "name": "pd-gold",
                "active": True,
                "vmCount": 5,
                "cronSchedules": [{"id": "s1"}, {"id": "s2"}],
                "replicationLinks": [{"remote_site_name": "dr-site"}],
            }
        ],
    },
    "pe_list_remote_sites": {
        "count": 1,
        "remoteSites": [
            {
                "name": "dr-site",
                "remoteIpPorts": {"10.9.0.10": 2020},
                "capabilities": ["BACKUP"],
                "metroReady": False,
                "compressOnWire": True,
                "bandwidthPolicyEnabled": False,
            }
        ],
    },
    "pe_list_unprotected_vms": {
        "unprotectedCount": 2,
        "unprotectedVms": [
            {"name": "dev-01", "powerState": "on", "numVcpus": 2, "memoryMb": 4096},
            {"name": "off-01", "powerState": "off", "numVcpus": 2, "memoryMb": 4096},
        ],
    },
    "pe_list_alerts": {
        "count": 2,
        "alerts": [
            {"alertTitle": "Disk failure", "severity": "kCritical", "message": "Disk S123 failed"},
            {"alertTitle": "CPU high", "severity": "kWarning", "message": "CPU above 90%"},
        ],
    },
    "pe_list_health_checks": {
        "count": 2,
        "healthChecks": [
            {"name": "disk_online_check", "description": "Disks online", "lastExecutionStatus": "PASS"},
            {"name": "cvm_memory_check", "description": "CVM memory pressure", "lastExecutionStatus": "FAIL"},
        ],
    },
}


async def fake_call_tool(name: str, arguments: dict) -> dict:
    return TOOL_OUTPUTS[name]


@pytest.mark.asyncio
async def test_collect_all_sections():
    data, errors = await collect_report_data(fake_call_tool, "prod-cluster", ALL_SECTIONS)

    assert errors == {}
    assert data["overview"]["name"] == "prod-cluster"
    assert data["overview"]["storageType"] == "All Flash"
    assert data["overview"]["hypervisorTypes"] == ["AHV"]
    assert data["hosts"][0]["hypervisorType"] == "AHV"
    assert data["host_disks"]["h-uuid-1"][0]["tier"] == "SSD"
    assert data["vms"][0]["diskCapacityGb"] == 100
    assert data["networks"][0]["subnet"] == "10.0.1.0/24"
    assert data["networks"][0]["networkType"] == "Managed"
    assert data["storage"]["containers"][0]["maxCapacityTb"] == 10.0
    assert data["storage"]["diskSummary"]["tiers"]["SSD"]["count"] == 2
    assert data["system"]["license"]["category"] == "Ultimate"
    assert data["system"]["smtp"]["fromEmail"] == "nutanix@example.com"
    assert data["protection_domains"]["domains"][0]["cronSchedules"] == 2
    assert data["protection_domains"]["domains"][0]["replicationLinks"][0]["remoteSite"] == "dr-site"
    # only powered-on unprotected VMs are flagged
    assert [v["name"] for v in data["protection_domains"]["unprotectedVms"]] == ["dev-01"]
    assert data["alerts"]["bySeverity"] == {"Critical": 1, "Warning": 1}
    assert data["health"]["failedChecks"][0]["name"] == "cvm_memory_check"


@pytest.mark.asyncio
async def test_collect_section_error_is_partial():
    async def flaky_call_tool(name: str, arguments: dict) -> dict:
        if name == "pe_list_health_checks":
            raise RuntimeError("NCC not available")
        return TOOL_OUTPUTS[name]

    data, errors = await collect_report_data(flaky_call_tool, "prod-cluster", ALL_SECTIONS)

    assert "health" in errors
    assert "hosts" in data  # other sections still collected


@pytest.mark.asyncio
async def test_markdown_report_content():
    data, _ = await collect_report_data(fake_call_tool, "prod-cluster", ALL_SECTIONS)
    md = render_markdown("prod-cluster", "prod-cluster", data, ALL_SECTIONS)

    assert "# AsBuilt Report — prod-cluster" in md
    assert "| **AOS Version** | 6.8.1 |" in md
    assert "### node-01" in md
    assert "| **Node Serial** | NODE-SER-1 |" in md
    assert "SAMSUNG MZ7LH" in md
    assert "**Total VMs:** 2 (🟢 1 on, 🔴 1 off)" in md
    assert "| vlan-100 | 100 | Managed | 10.0.1.0/24 |" in md
    assert "| pd-gold | ✅ | 5 | 2 | dr-site |" in md
    assert "```mermaid" in md
    assert "prod-cluster<br/>" in md


@pytest.mark.asyncio
async def test_selected_sections_only():
    sections = ["overview", "storage"]
    data, _ = await collect_report_data(fake_call_tool, "prod-cluster", sections)
    md = render_markdown("prod-cluster", "prod-cluster", data, sections)

    assert "## Cluster Overview" in md
    assert "## Storage Configuration" in md
    assert "## Virtual Machine Inventory" not in md
    assert "## Health Checks" not in md


def test_render_html_structure():
    md = "# Title\n\n## Section\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```mermaid\ngraph TD\nA --- B\n```\n\n- item\n"
    html_out = render_html(md, "My Report")

    assert "<title>My Report</title>" in html_out
    assert '<nav id="toc">' in html_out
    assert "#toc { display: none; }" in html_out.replace("  ", " ")  # hidden in print
    assert "<table><thead><tr>" in html_out.replace("\n", "")
    assert '<div class="mermaid">' in html_out
    assert "<li>item</li>" in html_out


class TestValueMappings:
    def test_kkvm_maps_to_ahv(self):
        assert _friendly_hypervisor("kKvm") == "AHV"

    def test_unknown_passthrough(self):
        assert _friendly_hypervisor("kSomethingNew") == "kSomethingNew"

    def test_none_hypervisor(self):
        assert _friendly_hypervisor(None) == "Unknown"

    def test_storage_type(self):
        assert _friendly_storage_type("all_flash") == "All Flash"
        assert _friendly_storage_type(None) == "Unknown"

    def test_strip_k_prefix(self):
        assert _strip_k_prefix("kWarning") == "Warning"
        assert _strip_k_prefix("kubernetes") == "kubernetes"
        assert _strip_k_prefix(None) == ""


class TestParseToolResult:
    def test_prefers_structured_content(self):
        result = MagicMock()
        result.isError = False
        result.structuredContent = {"count": 1}
        assert parse_tool_result(result, "t") == {"count": 1}

    def test_falls_back_to_text_json(self):
        block = MagicMock()
        block.text = '{"count": 2}'
        result = MagicMock()
        result.isError = False
        result.structuredContent = None
        result.content = [block]
        assert parse_tool_result(result, "t") == {"count": 2}

    def test_raises_on_error(self):
        block = MagicMock()
        block.text = "Cannot reach Prism Central"
        result = MagicMock()
        result.isError = True
        result.content = [block]
        with pytest.raises(ToolCallError, match="Cannot reach"):
            parse_tool_result(result, "pe_list_hosts")
