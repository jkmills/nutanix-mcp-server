# Future Tools Roadmap

Potential tools to add to the Nutanix MCP server, organized by API namespace.

---

## Networking (`networking` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_subnets` | List subnets/VLANs with CIDR, VLAN ID, and associated cluster |
| `get_subnet` | Get subnet details including IP pools and DHCP config |
| `create_subnet` | Create a new subnet with VLAN/overlay config |
| `list_floating_ips` | List allocated floating IPs |
| `list_vpc` | List virtual private clouds (Flow Virtual Networking) |

## VM Lifecycle (`vmm` namespace, v4)

| Tool | Description |
|------|-------------|
| `clone_vm` | Clone an existing VM |
| `snapshot_vm` | Create a VM snapshot |
| `list_vm_snapshots` | List snapshots for a VM |
| `restore_vm_snapshot` | Restore a VM to a previous snapshot |
| `update_vm` | Modify VM config (CPU, memory, disks, NICs) |
| `delete_vm` | Delete a virtual machine |
| `attach_disk` | Add a disk to an existing VM |
| `attach_nic` | Add a NIC to an existing VM |
| `list_vm_nics` | List network interfaces on a VM |
| `migrate_vm` | Live-migrate a VM to another host |
| `get_vm_console_url` | Get VNC/console access URL |

## Images & Templates (`vmm` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_images` | List available disk images (ISOs, QCOW2) |
| `get_image` | Get image details and download info |
| `create_vm_from_image` | Create a VM from a disk image |
| `list_vm_templates` | List available VM templates |
| `deploy_vm_template` | Deploy a VM from a template |

## Data Protection (`dataprotection` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_protection_policies` | List data protection policies |
| `list_recovery_points` | List available recovery points |
| `create_recovery_point` | Create an on-demand recovery point |
| `list_replication_targets` | List configured replication targets |

## Storage (`storage` / `volumes` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_volume_groups` | List volume groups |
| `get_volume_group` | Get volume group details |
| `create_volume_group` | Create a new volume group |
| `attach_volume_to_vm` | Attach a volume group to a VM |

## Identity & Access (`iam` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_users` | List configured users |
| `list_roles` | List RBAC roles |
| `list_projects` | List projects and their resource quotas |
| `get_project` | Get project details and member list |

## Categories & Tags (`prism` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_categories` | List category keys and values |
| `get_category` | Get all values for a category key |
| `assign_category` | Tag a VM or resource with a category |
| `list_entities_by_category` | Find all resources with a given tag |

## Tasks & Monitoring (`prism` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_tasks` | List recent/running tasks |
| `get_task` | Get task progress and status |
| `list_alerts` | List active alerts with severity |
| `acknowledge_alert` | Acknowledge/resolve an alert |
| `list_audit_events` | List recent audit trail events |

## Lifecycle Management (`lifecycle` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_available_updates` | Check for AOS/firmware updates |
| `get_lcm_inventory` | Get LCM software/firmware inventory |

## Prism Element (v2 — per-cluster direct access)

| Tool | Description |
|------|-------------|
| `pe_get_cluster_health` | Get health summary from a PE node directly |
| `pe_list_vms` | List VMs on a specific PE cluster (v2) |
| `pe_list_storage_pools` | List storage pools on a PE cluster |
| `pe_get_hardware_info` | Get disk/node hardware details |

## Flow Microsegmentation (`microseg` namespace, v4)

| Tool | Description |
|------|-------------|
| `list_security_policies` | List network security policies |
| `get_security_policy` | Get policy details and rules |
| `list_address_groups` | List address groups used in policies |

---

## Priority Suggestions

**High value, low effort (next batch):**
1. `list_subnets` / `get_subnet` — essential for VM creation workflows
2. `list_images` — needed to create VMs from templates/images
3. `list_tasks` / `get_task` — track async operations
4. `list_alerts` — monitoring and incident response

**High value, moderate effort:**
5. `snapshot_vm` / `list_vm_snapshots` — data protection workflows
6. `update_vm` — modify running infrastructure
7. `list_categories` / `assign_category` — resource organization
