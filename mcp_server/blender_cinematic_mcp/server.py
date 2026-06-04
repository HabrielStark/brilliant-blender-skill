"""MCP server entrypoint (SRS 12.1: stdio transport).

``build_server`` is importable by tests; ``main`` runs the stdio transport so
hosts (Claude Code / Cursor / Codex / Gemini CLI) can launch it as
``blender-cinematic-mcp``.
"""
from __future__ import annotations

from .prompts import register_prompts
from .resources import register_resources
from .security import ServerContext
from .tools import register_tools


def build_server(ctx: ServerContext | None = None):
    from mcp.server.fastmcp import FastMCP

    ctx = ctx or ServerContext.from_env()
    mcp = FastMCP(
        "blender-cinematic",
        instructions=(
            "Structured, sandboxed Blender production tools. Prefer structured "
            "operations; raw Python is disabled by default. Every write stays inside "
            "the workspace root. Follow the mandatory workflow in SKILL.md."
        ),
    )
    register_tools(mcp, ctx)
    register_resources(mcp, ctx)
    register_prompts(mcp, ctx)
    return mcp, ctx


def main() -> None:
    mcp, _ = build_server()
    mcp.run()  # stdio transport by default


if __name__ == "__main__":  # pragma: no cover
    main()
