"""Tests for category assignment tools."""

from unittest.mock import AsyncMock

import pytest

from nutanix_mcp.tools.category import (
    handle_assign_category,
    handle_list_entities_by_category,
    handle_remove_category,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_assign_category(mock_client):
    """Test assigning a category to a VM."""
    mock_client.v4_get.return_value = {
        "data": {
            "extId": "vm-uuid-1",
            "name": "web-01",
            "categories": [{"key": "AppType", "value": "Web"}],
            "$metadata": {"ETag": "etag-1"},
        }
    }
    mock_client.v4_put.return_value = {"data": {"extId": "vm-uuid-1"}}

    result = await handle_assign_category(
        mock_client,
        {
            "vm_uuid": "vm-uuid-1",
            "category_key": "Environment",
            "category_value": "Production",
        },
    )

    assert result["status"] == "category_assigned"
    assert result["category"] == "Environment:Production"
    assert result["total_categories"] == 2

    # Verify the PUT body includes both old and new categories
    put_body = mock_client.v4_put.call_args.kwargs["body"]
    assert len(put_body["categories"]) == 2
    assert {"key": "Environment", "value": "Production"} in put_body["categories"]
    assert {"key": "AppType", "value": "Web"} in put_body["categories"]


@pytest.mark.asyncio
async def test_assign_category_already_exists(mock_client):
    """Test assigning a category that's already assigned."""
    mock_client.v4_get.return_value = {
        "data": {
            "extId": "vm-uuid-1",
            "categories": [{"key": "Environment", "value": "Production"}],
            "$metadata": {"ETag": "etag-1"},
        }
    }

    result = await handle_assign_category(
        mock_client,
        {
            "vm_uuid": "vm-uuid-1",
            "category_key": "Environment",
            "category_value": "Production",
        },
    )

    assert result["status"] == "already_assigned"
    mock_client.v4_put.assert_not_called()


@pytest.mark.asyncio
async def test_remove_category(mock_client):
    """Test removing a category from a VM."""
    mock_client.v4_get.return_value = {
        "data": {
            "extId": "vm-uuid-1",
            "categories": [
                {"key": "Environment", "value": "Production"},
                {"key": "AppType", "value": "Web"},
            ],
            "$metadata": {"ETag": "etag-2"},
        }
    }
    mock_client.v4_put.return_value = {"data": {"extId": "vm-uuid-1"}}

    result = await handle_remove_category(
        mock_client,
        {
            "vm_uuid": "vm-uuid-1",
            "category_key": "Environment",
            "category_value": "Production",
        },
    )

    assert result["status"] == "category_removed"
    assert result["remaining_categories"] == 1

    put_body = mock_client.v4_put.call_args.kwargs["body"]
    assert len(put_body["categories"]) == 1
    assert put_body["categories"][0] == {"key": "AppType", "value": "Web"}


@pytest.mark.asyncio
async def test_remove_category_not_found(mock_client):
    """Test removing a category that isn't assigned."""
    mock_client.v4_get.return_value = {
        "data": {
            "extId": "vm-uuid-1",
            "categories": [{"key": "AppType", "value": "Web"}],
            "$metadata": {"ETag": "etag-3"},
        }
    }

    result = await handle_remove_category(
        mock_client,
        {
            "vm_uuid": "vm-uuid-1",
            "category_key": "Environment",
            "category_value": "Production",
        },
    )

    assert result["status"] == "not_found"
    mock_client.v4_put.assert_not_called()


@pytest.mark.asyncio
async def test_list_entities_by_category(mock_client):
    """Test listing VMs by category."""
    mock_client.v4_list.return_value = {
        "data": [
            {"extId": "vm-1", "name": "web-01", "powerState": "ON", "cluster": {"extId": "c-1"}},
            {"extId": "vm-2", "name": "web-02", "powerState": "ON", "cluster": {"extId": "c-1"}},
        ]
    }

    result = await handle_list_entities_by_category(
        mock_client,
        {
            "category_key": "Environment",
            "category_value": "Production",
        },
    )

    assert result["category"] == "Environment:Production"
    assert result["total_matches"] == 2
    assert result["vms"][0]["name"] == "web-01"

    # Verify correct OData filter
    call_args = mock_client.v4_list.call_args
    assert "Environment" in call_args.kwargs["filter"]
    assert "Production" in call_args.kwargs["filter"]
