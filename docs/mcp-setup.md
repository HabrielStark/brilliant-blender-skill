# MCP Setup

The server speaks **stdio** MCP and exposes structured, sandboxed tools, doc
resources and workflow prompts. Raw Python is disabled by default; every write
stays inside the workspace root.

## Run

```bash
pip install -e ".[mcp]"
blender-cinematic-mcp          # stdio transport
```

## Environment

| Var | Default | Meaning |
|---|---|---|
| `BCAS_WORKSPACE_ROOT` | `./artifacts` | sandbox root for all writes |
| `BLENDER_EXECUTABLE` | auto-detect | Blender binary for render/inspect/export |
| `BCAS_SAFETY_MODE` | `strict` | `strict` (structured ops only) or `dev` |
| `BCAS_ALLOW_NETWORK` | `0` | network is refused in strict mode |
| `BCAS_RAW_PYTHON` | `0` | raw Blender Python (dev mode only) |
| `BCAS_BRIDGE_HOST` / `BCAS_BRIDGE_PORT` | `127.0.0.1` / `8765` | add-on bridge |

## Host configuration

Most hosts accept a command + args + env block. Example (Claude Code / Cursor
style `mcpServers` entry):

```json
{
  "mcpServers": {
    "blender-cinematic": {
      "command": "blender-cinematic-mcp",
      "env": {
        "BCAS_WORKSPACE_ROOT": "/abs/path/to/artifacts",
        "BLENDER_EXECUTABLE": "/abs/path/to/blender"
      }
    }
  }
}
```

Codex / Gemini CLI and other Agent-Skills hosts use the same idea: register a
stdio server whose command is `blender-cinematic-mcp`. Point the host at the
skill folder (`SKILL.md`) so the agent loads the workflow rules too.

## Tools (underscored names; dotted SRS namespace in each docstring)

`preflight_system_check`, `project_create_scene_workspace`, `project_final_report`,
`scene_validate_manifest`, `scene_initialize_blend`, `scene_apply_recipe`,
`scene_inspect`, `scene_execute_python_safe` (disabled by default),
`evaluate_scene_lint`, `evaluate_preview`, `camera_plan_and_create`,
`lighting_create_setup`, `material_create_pbr`, `geometry_estimate_complexity`,
`render_budget`, `render_preview`, `render_final`, `export_glb`,
`web_validate_glb`, `web_generate_integration`, `security_scan_python`,
`security_policy`.

## Resources & prompts

- `docs://camera-language`, `docs://visual-critique-rubric`, … (the playbooks).
- `project://{task_id}/scene_manifest.json`, `project://{task_id}/final_report.md`,
  `blender://{task_id}/hardware_report.json`, `blender://{task_id}/current_scene.json`.
- Prompts: `cinematic_scene_workflow`, `reference_match_workflow`,
  `web_3d_hero_workflow`, `safe_laptop_workflow`, `scene_repair_workflow`,
  `benchmark_run_workflow`.
