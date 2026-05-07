# Nutanix MCP Server

An MCP (Model Context Protocol) server that exposes Nutanix Prism Central and Prism Element APIs as tools for AI assistants like GitHub Copilot, Claude, and others.

## Features

- **Prism Central (v4 API)** — VM management, cluster inventory, host management
- **Prism Element (v2 API)** — Direct cluster access for storage, disks, alerts, protection domains
- **API version routing** — Prefers v4, falls back to v3/v2 when needed
- **Async** — Non-blocking HTTP client using httpx

## Available Tools

### VM Management (Prism Central v4)
| Tool | Description |
|------|-------------|
| `list_vms` | List VMs with OData filtering |
| `get_vm` | Get full VM configuration by UUID |
| `power_on_vm` | Power on a VM |
| `power_off_vm` | Power off (ACPI or force) |
| `create_vm` | Create a new VM |

### Cluster Management (Prism Central v4)
| Tool | Description |
|------|-------------|
| `list_clusters` | List registered clusters |
| `get_cluster` | Get cluster details |
| `list_hosts` | List hypervisor hosts |
| `get_host` | Get host details |
| `list_storage_containers` | List storage containers |

### Prism Element (v2 — direct cluster access)
| Tool | Description |
|------|-------------|
| `pe_get_cluster_info` | Cluster health, version, and capacity |
| `pe_list_vms` | VMs on a specific PE cluster |
| `pe_list_hosts` | Hosts with hardware details |
| `pe_list_containers` | Storage containers with replication info |
| `pe_list_storage_pools` | Storage pools and disk composition |
| `pe_list_disks` | Physical disk inventory and status |
| `pe_list_alerts` | Active/resolved alerts |
| `pe_list_protection_domains` | Data protection policies |
| `pe_list_snapshots` | Snapshots per protection domain |

## Setup

### Prerequisites
- Python 3.10+
- Network access to Prism Central (`prism-central.example.com:9440`)
- Nutanix credentials with API access

### Install

```bash
cd mcp/nutanix-mcp-server
pip install -e .
```

Or with dev dependencies:
```bash
pip install -e ".[dev]"
```

### Configure

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
NUTANIX_HOST=prism-central.example.com
NUTANIX_PORT=9440
NUTANIX_USERNAME=your-username
NUTANIX_PASSWORD=your-password
NUTANIX_VERIFY_SSL=true
NUTANIX_TIMEOUT=30
```

### Run

```bash
nutanix-mcp
```

Or directly:
```bash
python -m nutanix_mcp
```

## MCP Client Configuration

### Claude Desktop / Claude Code

Add to your MCP settings:

```json
{
  "mcpServers": {
    "nutanix": {
      "command": "python",
      "args": ["-m", "nutanix_mcp"],
      "cwd": "/path/to/mcp/nutanix-mcp-server",
      "env": {
        "NUTANIX_HOST": "prism-central.example.com",
        "NUTANIX_USERNAME": "your-username",
        "NUTANIX_PASSWORD": "your-password",
        "NUTANIX_VERIFY_SSL": "true"
      }
    }
  }
}
```

### GitHub Copilot (VS Code)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "nutanix": {
      "command": "python",
      "args": ["-m", "nutanix_mcp"],
      "cwd": "${workspaceFolder}/mcp/nutanix-mcp-server",
      "env": {
        "NUTANIX_HOST": "prism-central.example.com",
        "NUTANIX_USERNAME": "your-username",
        "NUTANIX_PASSWORD": "your-password"
      }
    }
  }
}
```

## API Version Strategy

| Version | Endpoint Pattern | Use Case |
|---------|-----------------|----------|
| v4 (preferred) | `/api/{namespace}/v4.0/{path}` | VMs, clusters, hosts, networking |
| v3 (fallback) | `/api/nutanix/v3/{resource}/list` | Resources not yet in v4 |
| v2 (PE direct) | `https://{pe_ip}:9440/api/nutanix/v2.0/{resource}` | Per-cluster storage, disks, alerts |

## Discovering Prism Element Hosts

Use `list_clusters` to find cluster UUIDs, then `list_hosts` to find CVM IPs.
Those CVM IPs can be used as `pe_host` in the Prism Element tools.

## Development

```bash
# Lint
ruff check src/

# Type check
mypy src/

# Test
pytest
```

## References

- [Nutanix v4 API Documentation](https://developers.nutanix.com)
- [Nutanix Developer Portal](https://www.nutanix.dev)
- [Prism Central v3 API](https://www.nutanix.dev/api_reference/apis/prism_v3.html)
- [Prism Element v2 API](https://www.nutanix.dev/api_reference/apis/prism_v2.html)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
