# NPM And GitHub Install

Use this when you want the Skill from GitHub without manually unpacking release
zips.

## Install From GitHub

```bash
npm install -g github:HabrielStark/brilliant-blender-skill
brilliant-blender-skill install
```

The installer copies the Skill into:

```text
%USERPROFILE%\.codex\skills\blender-cinematic-scene
```

On macOS/Linux it uses:

```text
~/.codex/skills/blender-cinematic-scene
```

The npm package is intentionally a small launcher plus the GLB validator. When
the complete skill payload is not bundled in the npm package, `install` clones
`https://github.com/HabrielStark/brilliant-blender-skill.git` and copies the
payload from that checkout. This keeps `npm install -g github:...` reliable on
Windows while preserving a full source-backed install.

Override the target when needed:

```bash
brilliant-blender-skill install --target /absolute/path/to/blender-cinematic-scene
brilliant-blender-skill install --codex-home /absolute/path/to/.codex
```

## One-Shot NPX

```bash
npx github:HabrielStark/brilliant-blender-skill install
```

## Check The Package

```bash
brilliant-blender-skill doctor
bcas-validate-glb examples/web-demo/scene.glb --max-mb 20
```

## Blender Add-On And MCP

`brilliant-blender-skill install` gives agents the Skill instructions,
references, scripts, benchmarks, add-on source, and web validator. For
MCP/server commands from the Python package, install the wheel or source package
as well:

```bash
pip install blender-cinematic-agent-skill
blender-cinematic-mcp
```

For local development from this repository:

```bash
pip install -e ".[dev]"
npm install
npm test
```
