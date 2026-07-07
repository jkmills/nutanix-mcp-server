"""Standalone AsBuilt report generator for Nutanix clusters.

This package is an MCP *client*: it spawns the nutanix-mcp server over
stdio and composes an infrastructure report from the server's granular
pe_* tools. It is intentionally not part of the MCP tool surface —
report generation is a workflow, not a primitive.
"""

__version__ = "0.5.0"
