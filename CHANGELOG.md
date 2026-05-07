# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-05-07

### Added

- **VM snapshot tools** (`snapshot_vm`, `list_vm_snapshots`, `restore_vm_snapshot`) —
  create, list, and restore recovery points via the dataprotection namespace (#3)
- **Alert management tools** (`list_alerts`, `get_alert`, `acknowledge_alert`) —
  centralized alert monitoring with severity/status filtering and ETag-safe ack (#4)
- **Category assignment tools** (`assign_category`, `remove_category`,
  `list_entities_by_category`) — tag VMs with key:value categories for
  microsegmentation and DR policy targeting (#5)
- **GitHub Actions CI pipeline** — lint (ruff), typecheck (mypy), tests on
  Python 3.10/3.12/3.13 (#6)
- **Streamable HTTP transport** (`--http` flag) — remote deployment via
  `POST /mcp` using MCP SDK's StreamableHTTPSessionManager (#7)
- **Dockerfile** — containerized deployment with python:3.12-slim + uv (#8)
- `.dockerignore` for lean container builds

### Changed

- Bumped ruff line-length to 120, added E501 ignore for string literals
- Relaxed mypy config for untyped MCP/httpx stubs (non-blocking in CI)
- Moved `json` import to top of `resources.py` (E402 fix)
- Applied consistent ruff formatting across codebase

## [0.2.0] - 2026-05-07

### Added

- **Task tracking tools** (`list_tasks`, `get_task`) — monitor async operation
  status, progress, and errors via the Nutanix v4 prism namespace (#1)
- **VM lifecycle tools** (`update_vm`, `delete_vm`, `clone_vm`) — full day-2 VM
  management with ETag concurrency control and confirmation guards (#2)
- `v4_put` and `v4_delete` HTTP methods on `NutanixClient`
- Unit tests for all new tools

## [0.1.0] - 2026-05-07

### Added

- Initial release with core MCP server
- VM tools: `list_vms`, `get_vm`, `create_vm`, `power_on_vm`, `power_off_vm`
- Cluster tools: `list_clusters`, `get_cluster`, `list_hosts`, `list_storage_containers`
- Networking tools: `list_subnets`, `get_subnet`
- Prism Element tools: `pe_list_vms`, `pe_list_hosts`
- Report generation: `generate_as_built_report`
- Resource templates and prompts
- Auto-pagination with 429 retry
- OData filter validation
