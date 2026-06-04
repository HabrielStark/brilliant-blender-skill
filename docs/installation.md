# Installation

## Requirements

- Python **3.11+**
- (optional) Node **20+** for GLB validation / web codegen
- (optional) **Blender 4.2+** (tested on 5.0) to *execute* scenes — render/export.
  The skill, schemas, linters, evaluation and MCP server run **without** Blender.

## Python (pip)

```bash
python -m venv .venv
. .venv/Scripts/activate            # Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"             # core + tests + imaging + mcp
```

Extras: `.[mcp]` (server), `.[imaging]` (Pillow+numpy), `.[ssim]` (scikit-image),
`.[nvidia]` (`nvidia-ml-py`), `.[all]`.

## Python (uv)

```bash
uv sync --all-extras
uv run python scripts/validate_skill.py
```

## Node (optional, web tooling)

```bash
npm install
npm run build      # compiles web/*.ts -> web/dist
npm test           # node --test (GLB validator)
```

## NPM GitHub Skill install

```bash
npm install -g github:HabrielStark/brilliant-blender-skill
brilliant-blender-skill install
```

This copies the Skill to the default Codex skills directory. See
`docs/npm-github-install.md` for `npx`, custom target paths, the launcher/full
payload split, and package checks.

## Verify

```bash
python scripts/validate_skill.py            # SKILL VALIDATION PASSED
python scripts/blender_locator.py           # finds Blender if installed
pytest tests/unit tests/security -q         # core suite, no Blender needed
ruff check blender_cinematic mcp_server scripts tests
bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon
```

## Blender

Blender is auto-located from PATH, the `BLENDER_EXECUTABLE` env var, or the
standard install folders. To point at a specific build:

```bash
export BLENDER_EXECUTABLE="/path/to/blender"      # Windows: set BLENDER_EXECUTABLE=...
```

See `docs/blender-addon.md` to install the interactive add-on, and
`docs/mcp-setup.md` to wire the MCP server into your agent host.
