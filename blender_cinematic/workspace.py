"""Workspace path sandbox (SRS 18.2: "Workspace root allowlist").

Every file the system reads or writes on behalf of an agent must pass through a
:class:`WorkspaceResolver`. Paths are resolved (following symlinks) and then
checked against an allowlist of root directories; anything outside is rejected.
This is the single choke point for the path-traversal threat.
"""
from __future__ import annotations

import os
from pathlib import Path


class PathSandboxError(Exception):
    """Raised when a path escapes the workspace allowlist."""


class WorkspaceResolver:
    def __init__(self, roots: list[str | os.PathLike] | str | os.PathLike) -> None:
        if isinstance(roots, (str, os.PathLike)):
            roots = [roots]
        if not roots:
            raise ValueError("WorkspaceResolver requires at least one root")
        # Resolve roots up-front; they must exist or be creatable later.
        self.roots: list[Path] = []
        for r in roots:
            p = Path(r).expanduser().resolve()
            self.roots.append(p)

    def _resolved(self, path: str | os.PathLike) -> Path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            # Relative paths are interpreted against the first root.
            p = self.roots[0] / p
        # strict=False: target may not exist yet (we are about to create it).
        return p.resolve()

    def is_within(self, path: str | os.PathLike) -> bool:
        try:
            resolved = self._resolved(path)
        except (OSError, RuntimeError):
            return False
        for root in self.roots:
            if resolved == root or resolved.is_relative_to(root):
                return True
        return False

    def resolve(self, path: str | os.PathLike) -> Path:
        """Resolve and assert the path stays inside the allowlist."""
        resolved = self._resolved(path)
        if not self.is_within(resolved):
            raise PathSandboxError(
                f"path {resolved} is outside workspace roots {[str(r) for r in self.roots]}"
            )
        return resolved

    def ensure_dir(self, path: str | os.PathLike) -> Path:
        resolved = self.resolve(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def write_text(self, path: str | os.PathLike, text: str, encoding: str = "utf-8") -> Path:
        resolved = self.resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(text, encoding=encoding)
        return resolved

    def write_bytes(self, path: str | os.PathLike, data: bytes) -> Path:
        resolved = self.resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(data)
        return resolved


def task_workspace(project_root: str | os.PathLike, task_id: str) -> tuple[WorkspaceResolver, Path]:
    """Create the canonical ``artifacts/<task_id>/`` layout (SRS 7.3)."""
    root = Path(project_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    resolver = WorkspaceResolver([root])
    base = resolver.ensure_dir(root / task_id)
    for sub in ("iterations", "final", "logs"):
        resolver.ensure_dir(base / sub)
    return resolver, base
