"""Tests for health check tools (Issue #20)."""

from unittest.mock import AsyncMock

import pytest

from nutanix_mcp.tools.prism_element import (
    handle_pe_get_cluster_health,
    handle_pe_list_health_checks,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_get_cluster_health(mock_client):
    """Test retrieving cluster health / fault tolerance status."""
    mock_client.pe_get.return_value = {
        "domain_fault_tolerance_status": [
            {
                "domain_type": "NODE",
                "component_fault_tolerance_status": {
                    "static_configuration": {
                        "current_max_fault_tolerance": 1,
                        "desired_max_fault_tolerance": 1,
                    },
                    "dynamic_configuration": {
                        "can_rebuild": True,
                    },
                },
            },
            {
                "domain_type": "DISK",
                "component_fault_tolerance_status": {
                    "static_configuration": {
                        "current_max_fault_tolerance": 2,
                        "desired_max_fault_tolerance": 2,
                    },
                    "dynamic_configuration": {
                        "can_rebuild": True,
                    },
                },
            },
        ]
    }

    result = await handle_pe_get_cluster_health(mock_client, {"pe_host": "10.0.0.1"})

    assert len(result["faultToleranceStatus"]) == 2
    node_status = result["faultToleranceStatus"][0]
    assert node_status["domainType"] == "NODE"
    assert node_status["currentTolerance"] == 1
    assert node_status["rebuildCapacity"] is True
    disk_status = result["faultToleranceStatus"][1]
    assert disk_status["domainType"] == "DISK"
    assert disk_status["currentTolerance"] == 2
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "cluster/domain_fault_tolerance_status")


@pytest.mark.asyncio
async def test_list_health_checks(mock_client):
    """Test listing health check results."""
    mock_client.pe_v1_get.return_value = {
        "entities": [
            {
                "id": "hc-001",
                "name": "CVM Memory Usage",
                "description": "Checks if CVM memory usage exceeds threshold",
                "affected_entity_types": ["CVM"],
                "check_type": "RESOURCE",
                "severity": "WARNING",
                "last_execution_status": "PASS",
                "last_passed_time_stamp_in_usecs": 1700000000000000,
            },
            {
                "id": "hc-002",
                "name": "Disk Space Usage",
                "description": "Checks cluster disk space utilization",
                "affected_entity_types": ["DISK"],
                "check_type": "CAPACITY",
                "severity": "CRITICAL",
                "last_execution_status": "PASS",
                "last_passed_time_stamp_in_usecs": 1700000000000000,
            },
        ]
    }

    result = await handle_pe_list_health_checks(mock_client, {"pe_host": "10.0.0.1"})

    assert result["count"] == 2
    assert result["healthChecks"][0]["name"] == "CVM Memory Usage"
    assert result["healthChecks"][0]["severity"] == "WARNING"
    assert result["healthChecks"][0]["lastExecutionStatus"] == "PASS"
    assert result["healthChecks"][1]["checkType"] == "CAPACITY"
    mock_client.pe_v1_get.assert_called_once_with("10.0.0.1", "health_checks")
