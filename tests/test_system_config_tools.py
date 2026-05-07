"""Tests for system configuration tools (Issue #16)."""

from unittest.mock import AsyncMock

import pytest

from nutanix_mcp.tools.prism_element import (
    handle_pe_get_alert_email_config,
    handle_pe_get_auth_config,
    handle_pe_get_licensing_info,
    handle_pe_get_nfs_whitelists,
    handle_pe_get_smtp_config,
    handle_pe_get_snmp_config,
    handle_pe_get_syslog_config,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_get_auth_config(mock_client):
    """Test retrieving authentication configuration."""
    mock_client.pe_v1_get.return_value = {
        "authTypeList": ["LOCAL", "LDAP"],
        "directoryList": [
            {
                "name": "corp-ad",
                "directory_type": "ACTIVE_DIRECTORY",
                "domain": "corp.example.com",
                "directory_url": "ldaps://ad.corp.example.com:636",
                "connection_type": "LDAP",
                "group_search_type": "RECURSIVE",
            }
        ],
        "clientAuth": "NONE",
    }

    result = await handle_pe_get_auth_config(mock_client, {"pe_host": "10.0.0.1"})

    assert result["authTypes"] == ["LOCAL", "LDAP"]
    assert len(result["directories"]) == 1
    assert result["directories"][0]["name"] == "corp-ad"
    assert result["directories"][0]["directoryType"] == "ACTIVE_DIRECTORY"
    assert result["directories"][0]["domain"] == "corp.example.com"
    mock_client.pe_v1_get.assert_called_once_with("10.0.0.1", "authconfig")


@pytest.mark.asyncio
async def test_get_smtp_config(mock_client):
    """Test retrieving SMTP configuration."""
    mock_client.pe_get.return_value = {
        "address": "smtp.corp.example.com",
        "port": 587,
        "username": "alerts@corp.example.com",
        "secure_mode": "STARTTLS",
        "from_email_address": "nutanix@corp.example.com",
        "email_status": "VERIFIED",
    }

    result = await handle_pe_get_smtp_config(mock_client, {"pe_host": "10.0.0.1"})

    assert result["address"] == "smtp.corp.example.com"
    assert result["port"] == 587
    assert result["secureMode"] == "STARTTLS"
    assert result["fromEmailAddress"] == "nutanix@corp.example.com"
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "smtp_server")


@pytest.mark.asyncio
async def test_get_snmp_config(mock_client):
    """Test retrieving SNMP configuration."""
    mock_client.pe_get.return_value = {
        "enabled": True,
        "trap_list": [
            {
                "address": "10.1.1.100",
                "port": 162,
                "community_string": "public",
                "version": "V2C",
                "inform": False,
            }
        ],
        "user_list": [
            {
                "username": "snmpuser",
                "auth_type": "SHA",
                "priv_type": "AES",
            }
        ],
        "transport_list": [
            {
                "port": 161,
                "protocol": "UDP",
            }
        ],
    }

    result = await handle_pe_get_snmp_config(mock_client, {"pe_host": "10.0.0.1"})

    assert result["enabled"] is True
    assert len(result["traps"]) == 1
    assert result["traps"][0]["address"] == "10.1.1.100"
    assert result["traps"][0]["version"] == "V2C"
    assert len(result["users"]) == 1
    assert result["users"][0]["username"] == "snmpuser"
    assert len(result["transports"]) == 1
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "snmp")


@pytest.mark.asyncio
async def test_get_syslog_config(mock_client):
    """Test retrieving syslog server configuration."""
    mock_client.pe_get.return_value = {
        "entities": [
            {
                "server_name": "syslog-prod",
                "ip_address": "10.2.0.50",
                "port": 514,
                "network_protocol": "UDP",
                "module_list": ["ACROPOLIS", "GENESIS", "PRISM"],
            }
        ]
    }

    result = await handle_pe_get_syslog_config(mock_client, {"pe_host": "10.0.0.1"})

    assert result["count"] == 1
    assert result["servers"][0]["serverName"] == "syslog-prod"
    assert result["servers"][0]["ipAddress"] == "10.2.0.50"
    assert result["servers"][0]["networkProtocol"] == "UDP"
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "remote_syslog_servers")


@pytest.mark.asyncio
async def test_get_alert_email_config(mock_client):
    """Test retrieving alert email configuration."""
    mock_client.pe_get.return_value = {
        "email_contact_list": ["ops@corp.example.com", "admin@corp.example.com"],
        "enable": True,
        "enable_default_nutanix_email": False,
        "enable_email_digest": True,
    }

    result = await handle_pe_get_alert_email_config(mock_client, {"pe_host": "10.0.0.1"})

    assert result["emailContactList"] == ["ops@corp.example.com", "admin@corp.example.com"]
    assert result["enable"] is True
    assert result["enableDefaultNutanixEmail"] is False
    assert result["enableEmailDigest"] is True
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "alerts/configuration")


@pytest.mark.asyncio
async def test_get_nfs_whitelists(mock_client):
    """Test retrieving NFS whitelist configuration."""
    mock_client.pe_get.return_value = {
        "nfs_whitelist_address": ["10.0.0.0/24", "192.168.1.0/24", "10.1.0.100"],
        "name": "test-cluster",
    }

    result = await handle_pe_get_nfs_whitelists(mock_client, {"pe_host": "10.0.0.1"})

    assert result["count"] == 3
    assert "10.0.0.0/24" in result["whitelists"]
    assert "192.168.1.0/24" in result["whitelists"]
    mock_client.pe_get.assert_called_once_with("10.0.0.1", "cluster")


@pytest.mark.asyncio
async def test_get_licensing_info(mock_client):
    """Test retrieving licensing information."""
    mock_client.pe_v1_get.return_value = {
        "category": "ULTIMATE",
        "license_type": "PRISM_PRO",
        "expiry_date": "2027-01-15",
        "cluster_uuid": "cluster-uuid-123",
        "enabled_feature_list": ["DEDUPLICATION", "COMPRESSION", "ENCRYPTION"],
    }

    result = await handle_pe_get_licensing_info(mock_client, {"pe_host": "10.0.0.1"})

    assert result["category"] == "ULTIMATE"
    assert result["licenseType"] == "PRISM_PRO"
    assert result["expiryDate"] == "2027-01-15"
    assert "DEDUPLICATION" in result["enabledFeatures"]
    mock_client.pe_v1_get.assert_called_once_with("10.0.0.1", "license")
