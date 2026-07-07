# Nutanix AsBuilt Report Tool

A standalone CLI that generates comprehensive AsBuilt documentation for a
Nutanix cluster — cluster config, system settings, per-host hardware and
disk inventory, VMs, networks, storage, data protection, alerts, health
checks, and a Mermaid topology diagram.

## Why is this not an MCP tool?

It used to be (`generate_asbuilt` / `export_asbuilt_html` in ≤ 0.4.x).
Report generation is a *workflow*, not a primitive: it fires dozens of API
calls and produces a large document that has no business flowing through an
LLM's context window twice. So it now lives here as an **MCP client** — it
spawns the nutanix-mcp server over stdio and composes the report from the
same granular `pe_*` tools any AI assistant would use. The server stays
lean; the report needs no model in the loop.

If you want an AI-assisted report instead, use the server's
`as_built_report` MCP prompt, which guides the model through the same tools.

## Usage

Connection settings come from the same `NUTANIX_*` environment variables
the server uses (`NUTANIX_HOST`, `NUTANIX_USERNAME`, `NUTANIX_PASSWORD`, ...).

```bash
# From the repo root (or anywhere after `pip install -e .`)
nutanix-asbuilt <target>                    # writes asbuilt-<cluster>.md
nutanix-asbuilt <target> --html             # also writes asbuilt-<cluster>.html
nutanix-asbuilt <target> --sections overview hosts storage
nutanix-asbuilt <target> -o report.md --html report.html --title "Prod Cluster"

# Without installing:
python -m asbuilt.cli <target> --html
```

`<target>` may be a Prism Element IP, hostname, **cluster name**, or
**cluster UUID** — names and UUIDs are resolved to the cluster's external IP
via Prism Central automatically.

Open the HTML report in a browser and print (Ctrl+P / Cmd+P) for a PDF with
proper page breaks; the interactive table of contents is hidden in print.

## Sections

`overview`, `system`, `hosts` (with per-host disk inventory), `vms`,
`networks`, `storage`, `protection_domains`, `alerts`, `health`.

Sections that fail to collect (permissions, unsupported AOS version) are
reported as warnings and skipped — the rest of the report still renders.
