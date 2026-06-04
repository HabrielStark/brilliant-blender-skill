"""Server-side security context (SRS 12.1 / 18.2).

Centralises the policy every tool must honour: a workspace-root allowlist (path
sandbox), the located Blender executable, the safety mode (strict/dev), and the
network / raw-Python switches (both off by default). The Blender bridge binds
localhost only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from blender_cinematic.blender import locate_blender
from blender_cinematic.security import STRICT, assert_safety_mode
from blender_cinematic.workspace import WorkspaceResolver


@dataclass
class ServerContext:
    workspace_root: Path
    blender_exe: str | None = None
    safety_mode: str = STRICT
    allow_network: bool = False
    raw_python_enabled: bool = False
    bridge_host: str = "127.0.0.1"
    bridge_port: int = 8765
    resolver: WorkspaceResolver = field(init=False)

    def __post_init__(self) -> None:
        assert_safety_mode(self.safety_mode)
        self.workspace_root = Path(self.workspace_root).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.resolver = WorkspaceResolver([self.workspace_root])
        if self.bridge_host not in ("127.0.0.1", "localhost", "::1") and self.safety_mode == STRICT:
            raise ValueError("strict mode binds localhost only; remote host requires dev mode")

    @classmethod
    def from_env(cls) -> "ServerContext":
        root = os.environ.get("BCAS_WORKSPACE_ROOT", str(Path.cwd() / "artifacts"))
        return cls(
            workspace_root=Path(root),
            blender_exe=locate_blender(os.environ.get("BLENDER_EXECUTABLE")),
            safety_mode=os.environ.get("BCAS_SAFETY_MODE", STRICT),
            allow_network=os.environ.get("BCAS_ALLOW_NETWORK", "0") == "1",
            raw_python_enabled=os.environ.get("BCAS_RAW_PYTHON", "0") == "1",
            bridge_host=os.environ.get("BCAS_BRIDGE_HOST", "127.0.0.1"),
            bridge_port=int(os.environ.get("BCAS_BRIDGE_PORT", "8765")),
        )

    def task_dir(self, task_id: str) -> Path:
        if "/" in task_id or "\\" in task_id or ".." in task_id:
            raise ValueError(f"invalid task_id: {task_id!r}")
        return self.resolver.resolve(self.workspace_root / task_id)

    def policy(self) -> dict:
        return {
            "workspace_root": str(self.workspace_root),
            "safety_mode": self.safety_mode,
            "allow_network": self.allow_network,
            "raw_python_enabled": self.raw_python_enabled,
            "bridge_host": self.bridge_host,
            "bridge_port": self.bridge_port,
            "blender_exe": self.blender_exe,
            "structured_operations_only": not self.raw_python_enabled,
        }
