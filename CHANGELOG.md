# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-07-07

### Changed

- **AsBuilt moved out of the MCP tool surface.** Report generation is a
  workflow, not a primitive: `generate_asbuilt` fired dozens of API calls and
  returned a large document through model context, and `export_asbuilt_html`
  was pure text transformation. Both (plus `get_project_architecture`, which
  duplicated the `nutanix://asbuilt/project` resource) are removed from the
  server. The replacement is `nutanix-asbuilt` — a standalone CLI in
  `asbuilt/` that runs as a real **MCP client**: it spawns the server over
  stdio and composes the same 9-section report (with Mermaid topology and
  print-to-PDF HTML) from the granular `pe_*` tools. AI-assisted reports are
  still available via the `as_built_report` MCP prompt. Tool count: 63.

### Added

- **PE host resolution on every `pe_*` tool** — `pe_host` now accepts a
  cluster name or cluster UUID in addition to an IP/hostname; names and UUIDs
  are resolved to the cluster's external IP via Prism Central and cached
  (previously only `generate_asbuilt` could do this). The
  `NUTANIX_ALLOWED_PE_HOSTS` allowlist matches either the resolved address or
  the original input.
- **`wait_task` tool** — blocks until an async task reaches a terminal state
  (with timeout), so agents no longer hand-roll `get_task` polling loops.
- **Richer PE tool output for documentation parity**:
  - `pe_get_cluster_info`: NCC version, data-services IP, subnets, DNS/NTP,
    timezone, operation mode, redundancy factor, fault tolerance domain
  - `pe_list_hosts`: IPMI address, node serial, block model/serial, BMC and
    BIOS versions, CPU capacity (GHz), hypervisor version, VM count
  - `pe_list_vms`: optional `include_disk_config` returns total disk capacity
  - `pe_list_containers`: dedup setting; `pe_list_remote_sites`: metro
    readiness and wire compression; `pe_list_unprotected_vms`: vCPU/memory
- `pe_get_auth_config` / `pe_get_snmp_config` tolerate both camelCase and
  snake_case field names across AOS builds.
- MCP catalog (`mcp-catalog/nutanix-mcp-server.yaml`) regenerated from the
  live tool registry.

## [0.4.0] - 2026-07-07

### Fixed

- **Resource reads crashed**: `resources/read` returned `TextResourceContents`
  where the MCP SDK expects `ReadResourceContents`, so every `nutanix://` URI
  read raised `AttributeError`. All resource reads now work.
- **Missing If-Match on v4 mutations**: `power_on_vm`, `power_off_vm`,
  `update_vm`, `delete_vm`, and `clone_vm` never sent the ETag required by
  Nutanix v4 APIs (HTTP 428 Precondition Required). Each handler now fetches
  the entity and passes `if_match` from `ApiClient.get_etag()`.
- **ETag source for httpx paths**: `acknowledge_alert`, `assign_category`, and
  `remove_category` read the ETag only from body `$metadata`; the authoritative
  HTTP response header is now used first with body fallback
  (new `NutanixClient.v4_get_with_etag`).
- **Tool errors were invisible to clients**: failures were returned as plain
  text without `isError`, so MCP clients treated errors as successful results.
  Errors now return proper `CallToolResult(isError=True)`.
- **Non-JSON-serializable tool output**: handlers returning SDK datetimes
  (e.g. `get_task`) crashed serialization; output is now sanitized centrally.
- License classifier corrected to AGPLv3+ (was MIT, contradicting the license).

### Added

- **Tool annotations on all 65 tools** — `readOnlyHint`, `destructiveHint`,
  `idempotentHint`, `openWorldHint`, and human-readable titles, so MCP clients
  can gate destructive operations (`delete_vm`, `power_off_vm`, `update_vm`,
  `restore_vm_snapshot`) and fast-track read-only ones.
- **Structured tool output** — tool results are returned as
  `structuredContent` with a JSON text fallback for older clients.
- **Server metadata** — the initialize response now advertises the server
  version and usage `instructions` (PC vs PE tool split, task polling,
  snapshot-before-mutation guidance).
- **Friendly error mapping** — SDK/transport failures (auth, 404, ETag
  conflict, unreachable host) are translated into actionable messages.
- `NUTANIX_LOG_LEVEL` env var; diagnostics go through `logging` to stderr.
- Pagination safety cap in `list_all` (200 pages / 20k entities).
- End-to-end coverage: tool registry metadata tests, server plumbing tests
  (structured output, isError, resource contract).

### Changed

- Password is stored as a Pydantic `SecretStr` (masked in repr/logs).
- `mcp` dependency floor raised to 1.10 (annotations + structured content).
- `v4_get`/`v4_put` refactored onto a shared retrying `_v4_request` helper.
- `list_vm_snapshots` description no longer claims auto-pagination.

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
