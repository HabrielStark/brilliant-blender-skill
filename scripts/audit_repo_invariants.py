#!/usr/bin/env python
"""Audit repository-level invariants required by AGENTS.md."""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "artifacts",
    "build",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
}
PRODUCTION_DIRS = {"addon", "benchmarks", "blender_cinematic", "mcp_server", "scripts"}
PIN_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[^<>=!~*\\s]+$")
SHA_ACTION_RE = re.compile(r"uses:\s*[^@\s]+@([0-9a-f]{40})\s*$")
USES_RE = re.compile(r"uses:\s*([^@\s]+)(?:@([^\s]+))?\s*$")


def _iter_files(root: Path, suffix: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        current = Path(dirpath)
        for filename in filenames:
            if filename.endswith(suffix):
                yield current / filename


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_production_python(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return bool(parts) and parts[0] in PRODUCTION_DIRS


class _PythonInvariantVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, root: Path) -> None:
        self.path = path
        self.root = root
        self.rel = _rel(path, root)
        self.errors: list[str] = []
        self.class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        if self.rel.startswith("blender_cinematic/"):
            for alias in node.names:
                if alias.name == "bpy" or alias.name.startswith("bpy."):
                    self.errors.append(f"{self.rel}:{node.lineno} imports bpy in pure-Python core")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self.rel.startswith("blender_cinematic/") and node.module:
            if node.module == "bpy" or node.module.startswith("bpy."):
                self.errors.append(f"{self.rel}:{node.lineno} imports bpy in pure-Python core")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        production = _is_production_python(self.path, self.root)
        if production:
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                    if keyword.value.value is True:
                        self.errors.append(f"{self.rel}:{node.lineno} passes shell=True")

            if isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                value = node.func.value
                if (
                    isinstance(value, ast.Name)
                    and value.id == "subprocess"
                    and attr in {"run", "Popen", "call", "check_call", "check_output"}
                    and self.rel != "blender_cinematic/security.py"
                ):
                    self.errors.append(
                        f"{self.rel}:{node.lineno} calls subprocess.{attr}; use run_checked"
                    )
                if attr in {"write_text", "write_bytes"} and "WorkspaceResolver" not in self.class_stack:
                    if not self._write_receiver_is_resolver(value):
                        self.errors.append(
                            f"{self.rel}:{node.lineno} writes via {attr}; use WorkspaceResolver"
                        )
        self.generic_visit(node)

    @staticmethod
    def _write_receiver_is_resolver(value: ast.AST) -> bool:
        if isinstance(value, ast.Name):
            return value.id in {"resolver", "writer", "results_resolver", "ctx"}
        if isinstance(value, ast.Attribute):
            return value.attr in {"resolver"}
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            return value.func.id == "WorkspaceResolver"
        return False


def _audit_python(root: Path) -> list[str]:
    errors: list[str] = []
    for path in _iter_files(root, ".py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{_rel(path, root)}:{exc.lineno or 0} cannot parse: {exc.msg}")
            continue
        visitor = _PythonInvariantVisitor(path, root)
        visitor.visit(tree)
        errors.extend(visitor.errors)
    return errors


def _audit_python_pins(root: Path) -> list[str]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    deps: list[str] = []
    deps.extend(pyproject.get("build-system", {}).get("requires", []))
    deps.extend(pyproject.get("project", {}).get("dependencies", []))
    for values in pyproject.get("project", {}).get("optional-dependencies", {}).values():
        deps.extend(values)
    return [f"pyproject.toml dependency is not exact-pinned: {dep}" for dep in deps if not PIN_RE.match(dep)]


def _audit_node_pins(root: Path) -> list[str]:
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, version in package.get(section, {}).items():
            if not re.fullmatch(r"[^<>=!~^*\\s]+", version):
                errors.append(f"package.json {section}.{name} is not exact-pinned: {version}")
    return errors


def _audit_actions(root: Path) -> list[str]:
    errors: list[str] = []
    workflows = root / ".github" / "workflows"
    if not workflows.exists():
        return ["missing .github/workflows"]
    for path in sorted(workflows.glob("*.yml")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_RE.search(line.strip())
            if not match:
                continue
            if not SHA_ACTION_RE.search(line.strip()):
                errors.append(f"{_rel(path, root)}:{lineno} action is not pinned by commit SHA: {line.strip()}")
    return errors


def audit_repo(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    errors.extend(_audit_python(root))
    errors.extend(_audit_python_pins(root))
    errors.extend(_audit_node_pins(root))
    errors.extend(_audit_actions(root))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    errors = audit_repo(Path(args.root))
    if errors:
        print("REPOSITORY INVARIANT AUDIT FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("REPOSITORY INVARIANT AUDIT PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
