"""Tests for NutanixClient.resolve_pe_host — cluster name/UUID → PE IP."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nutanix_mcp.client import NutanixClient, ValidationError
from nutanix_mcp.config import Settings


def _client(**settings_overrides) -> NutanixClient:
    settings = Settings(host="pc.example.com", username="admin", password="secret", **settings_overrides)
    return NutanixClient(settings)


def _cluster(name: str, ext_id: str, ip: str | None) -> MagicMock:
    cluster = MagicMock()
    cluster.name = name
    cluster.ext_id = ext_id
    if ip:
        cluster.network.external_address.ipv4.value = ip
    else:
        cluster.network = None
    return cluster


@pytest.mark.asyncio
async def test_ip_passes_through_without_pc_lookup():
    client = _client()
    client.sdk = MagicMock()
    assert await client.resolve_pe_host("10.0.0.5") == "10.0.0.5"
    client.sdk.call.assert_not_called()


@pytest.mark.asyncio
async def test_uuid_resolves_to_external_ip():
    client = _client()
    sdk = MagicMock()
    response = MagicMock()
    response.data = _cluster("prod", "c-1", "10.0.0.9")
    sdk.call = AsyncMock(return_value=response)
    client.sdk = sdk

    resolved = await client.resolve_pe_host("12345678-abcd-abcd-abcd-1234567890ab")
    assert resolved == "10.0.0.9"


@pytest.mark.asyncio
async def test_name_resolves_via_filter():
    client = _client()
    sdk = MagicMock()
    sdk.list_all = AsyncMock(return_value=[_cluster("prod-cluster", "c-1", "10.0.0.7")])
    client.sdk = sdk

    resolved = await client.resolve_pe_host("prod-cluster")
    assert resolved == "10.0.0.7"


@pytest.mark.asyncio
async def test_name_falls_back_to_substring_match():
    client = _client()
    sdk = MagicMock()
    sdk.list_all = AsyncMock(
        side_effect=[
            [],  # exact filter match: nothing
            [_cluster("PROD-Cluster-01", "c-1", "10.0.0.8")],
        ]
    )
    client.sdk = sdk

    resolved = await client.resolve_pe_host("prod-cluster")
    assert resolved == "10.0.0.8"


@pytest.mark.asyncio
async def test_unresolvable_hostname_passes_through():
    """A plain DNS hostname keeps working even if PC has no matching cluster."""
    client = _client()
    sdk = MagicMock()
    sdk.list_all = AsyncMock(return_value=[])
    client.sdk = sdk

    assert await client.resolve_pe_host("cvm01.lab.local") == "cvm01.lab.local"


@pytest.mark.asyncio
async def test_resolution_is_cached():
    client = _client()
    sdk = MagicMock()
    sdk.list_all = AsyncMock(return_value=[_cluster("prod", "c-1", "10.0.0.7")])
    client.sdk = sdk

    await client.resolve_pe_host("prod")
    await client.resolve_pe_host("prod")
    assert sdk.list_all.await_count == 1


@pytest.mark.asyncio
async def test_invalid_format_rejected():
    client = _client()
    with pytest.raises(ValidationError):
        await client.resolve_pe_host("bad host; rm -rf /")


def test_allowlist_accepts_resolved_or_raw():
    client = _client(allowed_pe_hosts="10.0.0.7,prod-cluster")
    # resolved IP on allowlist
    client._validate_pe_host("10.0.0.7", raw_input="prod-cluster")
    # raw name on allowlist even if resolved IP isn't
    client._validate_pe_host("10.9.9.9", raw_input="prod-cluster")
    # neither on the allowlist
    with pytest.raises(ValidationError):
        client._validate_pe_host("10.9.9.9", raw_input="other")
