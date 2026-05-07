"""Tool registry and definitions."""

from nutanix_mcp.tools.vm import VM_TOOLS
from nutanix_mcp.tools.cluster import CLUSTER_TOOLS
from nutanix_mcp.tools.prism_element import PE_TOOLS
from nutanix_mcp.tools.report import REPORT_TOOLS


def get_all_tools() -> list[dict]:
    """Return all registered tool definitions."""
    return VM_TOOLS + CLUSTER_TOOLS + PE_TOOLS + REPORT_TOOLS
