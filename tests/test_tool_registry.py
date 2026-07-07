"""Tests for the tool registry: MCP metadata on every tool definition."""

from mcp.types import ToolAnnotations

from nutanix_mcp.tools import _WRITE_TOOL_HINTS, get_all_tools

WRITE_TOOLS = set(_WRITE_TOOL_HINTS)


def test_all_tools_have_required_fields():
    tools = get_all_tools()
    assert len(tools) == 63
    for tool in tools:
        assert tool["name"], "tool missing name"
        assert tool["description"], f"{tool['name']} missing description"
        assert tool["inputSchema"]["type"] == "object", f"{tool['name']} bad schema"
        assert tool["title"], f"{tool['name']} missing title"
        assert isinstance(tool["annotations"], ToolAnnotations)


def test_tool_names_are_unique():
    names = [t["name"] for t in get_all_tools()]
    assert len(names) == len(set(names))


def test_read_only_tools_flagged():
    for tool in get_all_tools():
        ann = tool["annotations"]
        if tool["name"] in WRITE_TOOLS:
            assert ann.readOnlyHint is False, f"{tool['name']} should not be read-only"
            assert ann.destructiveHint is not None
            assert ann.idempotentHint is not None
        else:
            assert ann.readOnlyHint is True, f"{tool['name']} should be read-only"


def test_destructive_tools_flagged():
    """The tools that can destroy data or interrupt workloads carry destructiveHint."""
    by_name = {t["name"]: t["annotations"] for t in get_all_tools()}
    for name in ("delete_vm", "power_off_vm", "update_vm", "restore_vm_snapshot"):
        assert by_name[name].destructiveHint is True, f"{name} must be destructive"
    for name in ("create_vm", "clone_vm", "snapshot_vm", "power_on_vm"):
        assert by_name[name].destructiveHint is False


def test_titles_are_human_readable():
    by_name = {t["name"]: t["title"] for t in get_all_tools()}
    assert by_name["list_vms"] == "List VMs"
    assert by_name["pe_list_cvms"] == "PE: List CVMs"
    assert by_name["pe_get_smtp_config"] == "PE: Get SMTP Config"
    assert by_name["wait_task"] == "Wait Task"


def test_every_tool_has_a_handler():
    from nutanix_mcp.server import ALL_HANDLERS

    tool_names = {t["name"] for t in get_all_tools()}
    handler_names = set(ALL_HANDLERS)
    assert tool_names == handler_names
