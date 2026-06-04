# Security Policy

## Supported Versions

Security fixes are maintained for the current `main` branch and tagged releases
published from it.

## Reporting a Vulnerability

Do not open a public issue for exploitable vulnerabilities. Email the maintainers
or use the repository host's private vulnerability reporting feature when it is
available. Include:

- affected version or commit;
- reproduction steps;
- expected impact;
- any logs that do not contain secrets.

The project is local-first and does not require paid APIs. Never include API
keys, tokens, `.env` contents, or private scene assets in reports.

## Security Boundaries

- `blender_cinematic/` must remain free of `bpy` imports.
- Scene changes must use structured allowlisted operations.
- Raw Python execution is disabled in strict mode.
- Subprocess calls must use argument arrays through `run_checked`.
- Writes must stay inside a `WorkspaceResolver` workspace.
- The MCP server and Blender bridge bind to localhost by default.

## Dependency Policy

Production dependencies are pinned exactly in `pyproject.toml` and
`package.json`, with `package-lock.json` committed for Node installs. CI runs
Python and Node dependency audits and fails on high-risk Node advisories.
