"""Path sandbox helpers for the interactive bridge.

This module intentionally avoids importing ``bpy`` so the bridge write boundary
can be unit-tested outside Blender.
"""
from pathlib import Path


class BridgePathSandboxError(ValueError):
    """Raised when a bridge output path escapes the configured workspace."""


class BridgeWorkspaceResolver:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve_output(self, path):
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = self.root / target
        target = target.resolve()
        if target == self.root or self.root in target.parents:
            return target
        raise BridgePathSandboxError(f"bridge output escapes workspace: {target}")
