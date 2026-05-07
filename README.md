# Nutanix MCP Server

An MCP (Model Context Protocol) server that exposes Nutanix Prism Central and Prism Element APIs as tools for AI assistants like GitHub Copilot, Claude, and others.

## Features

- **Prism Central (v4 API)** — VM management, cluster inventory, host management
- **Prism Element (v2 API)** — Direct cluster access for storage, disks, alerts, protection domains
- **As-Built Reports** — Generate comprehensive Markdown documentation with Excalidraw diagrams at environment, cluster, or VM scope
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

### Networking & Images (Prism Central v4)
| Tool | Description |
|------|-------------|
| `list_subnets` | List subnets/VLANs with CIDR, VLAN ID, and cluster |
| `get_subnet` | Get subnet details including IP pools and DHCP config |
| `list_images` | List disk images (ISOs, QCOW2) in the image library |
| `get_image` | Get image details — size, type, source |
| `list_categories` | List category keys and values for resource tagging |
| `get_category` | Get all values for a category key |

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

### As-Built Reports
| Tool | Description |
|------|-------------|
| `generate_environment_report` | Full environment report — all clusters, hosts, storage, networking, VMs with topology diagram |
| `generate_cluster_report` | Detailed report for one or more clusters — config, hosts, containers, subnets, VMs with architecture diagram |
| `generate_vm_report` | Detailed report for specific VMs — compute, disks, NICs, categories, boot config with layout diagram |

Reports output Markdown documentation and Excalidraw JSON diagrams for visual topology representation.

### MCP Resources (URI-based browsing)

The server exposes resources via `nutanix://` URIs, allowing LLMs to browse
entities without explicit tool calls:

| URI Pattern | Description |
|-------------|-------------|
| `nutanix://vms` | Browse all VMs |
| `nutanix://vms/{uuid}` | Get a specific VM |
| `nutanix://clusters` | Browse all clusters |
| `nutanix://clusters/{uuid}` | Get a specific cluster |
| `nutanix://hosts/{uuid}` | Get a specific host |
| `nutanix://subnets/{uuid}` | Get a specific subnet |
| `nutanix://images/{uuid}` | Get a specific image |

### MCP Prompts

| Prompt | Description |
|--------|-------------|
| `set_credentials` | Interactive credential configuration (for clients without env var support) |
| `nutanix_overview` | Guided environment overview — clusters, hosts, storage, alerts |

## Setup

### Prerequisites
- Python 3.10+
- Network access to your Prism Central instance (port 9440)
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
NUTANIX_HOST=your-prism-central.example.com
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

This server uses **stdio transport** — it communicates via stdin/stdout. Each client
configures a command to launch the server process.

> **Tip:** Store credentials in environment variables or a `.env` file, never in config files committed to source control.

---

### Claude Code (CLI)

Add the server to your project with the `claude mcp add` command:

```bash
claude mcp add nutanix -- python -m nutanix_mcp
```

Or manually create/edit `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "nutanix": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "nutanix_mcp"],
      "cwd": "/path/to/mcp/nutanix-mcp-server",
      "env": {
        "NUTANIX_HOST": "your-prism-central.example.com",
        "NUTANIX_USERNAME": "your-username",
        "NUTANIX_PASSWORD": "your-password",
        "NUTANIX_VERIFY_SSL": "true"
      }
    }
  }
}
```

For user-wide availability (all projects), add to `~/.claude.json` instead.

---

### Claude Desktop

Edit the config file at:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "nutanix": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "nutanix_mcp"],
      "cwd": "/path/to/mcp/nutanix-mcp-server",
      "env": {
        "NUTANIX_HOST": "your-prism-central.example.com",
        "NUTANIX_USERNAME": "your-username",
        "NUTANIX_PASSWORD": "your-password",
        "NUTANIX_VERIFY_SSL": "true"
      }
    }
  }
}
```

Restart Claude Desktop fully after editing.

---

### GitHub Copilot (VS Code)

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "nutanix": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "nutanix_mcp"],
      "cwd": "${workspaceFolder}/mcp/nutanix-mcp-server",
      "env": {
        "NUTANIX_HOST": "your-prism-central.example.com",
        "NUTANIX_USERNAME": "your-username",
        "NUTANIX_PASSWORD": "your-password",
        "NUTANIX_VERIFY_SSL": "true"
      }
    }
  }
}
```

---

### OpenCode (sst/opencode)

Add to `opencode.json` (or `opencode.jsonc`) in your project root:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "nutanix": {
      "type": "local",
      "command": ["python", "-m", "nutanix_mcp"],
      "environment": {
        "NUTANIX_HOST": "your-prism-central.example.com",
        "NUTANIX_USERNAME": "your-username",
        "NUTANIX_PASSWORD": "your-password",
        "NUTANIX_VERIFY_SSL": "true"
      },
      "enabled": true
    }
  }
}
```

Note: OpenCode uses `"command"` as an array and `"environment"` instead of `"env"`.

---

### Docker MCP Gateway

The [Docker MCP Gateway](https://docs.docker.com/ai/mcp-catalog-and-toolkit/mcp-gateway/)
can proxy this server inside a container. Two approaches:

#### Option A: Run directly via Docker

Build a container image and reference it in your MCP client config:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY mcp/nutanix-mcp-server/ .
RUN pip install --no-cache-dir -e .
CMD ["python", "-m", "nutanix_mcp"]
```

Then in any MCP client config:

```json
{
  "mcpServers": {
    "nutanix": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "NUTANIX_HOST=your-prism-central.example.com",
        "-e", "NUTANIX_USERNAME=your-username",
        "-e", "NUTANIX_PASSWORD=your-password",
        "-e", "NUTANIX_VERIFY_SSL=true",
        "nutanix-mcp-server"
      ]
    }
  }
}
```

#### Option B: Register with Docker MCP Gateway

If you have Docker Desktop with the MCP Toolkit:

```bash
docker mcp gateway run
```

Configure the gateway profile to include the nutanix server. The gateway then
exposes all registered MCP servers as a single unified endpoint.

In your AI client, point to the gateway:

```json
{
  "mcpServers": {
    "MCP_DOCKER": {
      "command": "docker",
      "args": ["mcp", "gateway", "run"]
    }
  }
}
```

The gateway handles routing, lifecycle management, and credential isolation.

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
