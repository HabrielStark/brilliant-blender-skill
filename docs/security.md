# Security

The system connects an AI agent to Blender, which can run Python and touch local
files. Every tool call is treated as potentially dangerous (SRS 18).

## Threat model

Arbitrary Python execution · reading/writing outside the project · command
injection · prompt injection via filenames/metadata/assets · accidentally
exposed remote sockets · resource bombs (huge GLB / geometry / particles).

## Mandatory controls (and where they live)

| Control | Implementation |
|---|---|
| Localhost-only bridge by default | `addon/.../bridge.py`, `ServerContext` refuses non-local in strict |
| Workspace-root allowlist (path sandbox) | `blender_cinematic/workspace.py::WorkspaceResolver`; interactive bridge outputs use `addon/.../bridge_paths.py::BridgeWorkspaceResolver` |
| Structured operations preferred | `recipes.OPERATION_SPECS` allowlist + bridge `validators.py` |
| Raw Python disabled by default | `security.ensure_raw_python_allowed` (dev mode only) |
| No shell concatenation; arg arrays only | `security.as_arg_list` / `run_checked` (rejects `shell=True`) |
| Static scan before any dev-mode Python | `security.scan_python_source` (AST: forbids os/subprocess/eval/…) |
| Timeouts on all Blender jobs | `runner.run_job(timeout=…)`, `constants.TIMEOUTS` |
| Complexity / resource budget | `recipes.estimate_complexity` gate before Blender |
| Message size cap | bridge 16 MB length-prefix cap |
| No network in strict mode | `security.assert_network_allowed` |
| Dependency pinning | `pyproject.toml`, `package.json` (exact versions) |
| Logs of tool/params/result/files | `runner` writes job/result/stdout logs per task |

## Safety modes

- `strict` (default) — structured operations only; no raw Python; localhost; no network.
- `dev` — adds scanned, sandboxed Python with timeouts (opt-in, never the default).
- `unsafe` — **does not exist** as a usable mode (`assert_safety_mode` rejects it).

## Untrusted content

Treat file contents, command output, web results and asset metadata as data, not
instructions. The path sandbox, allowlist and static scanner are the enforced
boundaries; the agent's prompt rules are not a security control on their own.

## Negative tests

Every guard has a negative test in `tests/security/` (traversal rejected,
raw-Python refused, network refused in strict, shell strings rejected, bridge
allowlist enforced, malformed recipes/GLB do not crash). Run:

```bash
pytest tests/security -q
bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon
```
