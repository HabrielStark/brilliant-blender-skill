"""Security helpers shared by scripts, the runner and the MCP server.

Implements the non-Blender half of the SRS 18 controls:
* subprocess calls are argument arrays, never shell strings;
* raw Python execution is disabled unless an explicit dev flag is set;
* network is disabled in strict mode;
* a conservative static analyzer rejects dangerous dev-mode Python.
"""
from __future__ import annotations

import ast
import shlex
import subprocess  # nosec B404
from dataclasses import dataclass

from .results import Issue, error

STRICT = "strict"
DEV = "dev"
SAFETY_MODES = (STRICT, DEV)  # "unsafe" intentionally absent (SRS 13.2).

RAW_PYTHON_ENABLED_DEFAULT = False

# Names/attributes that must never appear in dev-mode Blender Python.
_FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "open", "input", "breakpoint", "memoryview",
}
_FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "ssl", "http", "urllib",
    "requests", "ftplib", "telnetlib", "ctypes", "multiprocessing", "pickle",
    "marshal", "importlib", "pathlib", "asyncio", "threading", "signal",
    "smtplib", "webbrowser",
}
_FORBIDDEN_ATTR = {"system", "popen", "spawn", "fork", "remove", "rmtree", "unlink"}


class SecurityError(Exception):
    """Raised when a security control is violated."""


def assert_safety_mode(mode: str) -> str:
    if mode not in SAFETY_MODES:
        raise SecurityError(f"unknown/forbidden safety mode: {mode!r} (allowed: {SAFETY_MODES})")
    return mode


def ensure_raw_python_allowed(enabled: bool, mode: str = STRICT) -> None:
    """Gate raw Python execution (SRS 12.4 / 18.2)."""
    if not enabled:
        raise SecurityError("raw Blender Python execution is disabled by default")
    if mode != DEV:
        raise SecurityError("raw Python requires safety mode 'dev' with explicit opt-in")


def assert_network_allowed(allow_network: bool, mode: str = STRICT) -> None:
    if mode == STRICT and allow_network:
        raise SecurityError("network access is disabled in strict mode")


def as_arg_list(args) -> list[str]:
    """Reject shell strings; force an argument array (SRS 18.2 / 26)."""
    if isinstance(args, str):
        raise SecurityError(
            "subprocess commands must be argument arrays, not shell strings; "
            f"got {args!r}"
        )
    out = [str(a) for a in args]
    if not out:
        raise SecurityError("empty argument array")
    return out


def run_checked(args, timeout: float, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run wrapper that forbids shell=True and requires a timeout."""
    if kwargs.pop("shell", False):
        raise SecurityError("shell=True is forbidden")
    arglist = as_arg_list(args)
    return subprocess.run(  # nosec B603
        arglist,
        timeout=timeout,
        shell=False,
        capture_output=kwargs.pop("capture_output", True),
        text=kwargs.pop("text", True),
        **kwargs,
    )


def looks_like_shell_injection(value: str) -> bool:
    """Heuristic for metacharacters that only matter if something later builds a shell string."""
    try:
        tokens = shlex.split(value)
    except ValueError:
        return True
    return any(ch in value for ch in (";", "|", "&", "$(", "`", ">", "<", "\n")) or len(tokens) == 0 and value.strip() != ""


@dataclass
class ScanReport:
    issues: list[Issue]

    @property
    def safe(self) -> bool:
        return not self.issues


def scan_python_source(source: str) -> ScanReport:
    """Static analysis for dev-mode Blender Python (SRS 18.3 import restrictions).

    Conservative: flags imports of dangerous modules, dangerous builtins,
    and dangerous attribute access. Not a sandbox by itself — it is the
    pre-flight gate before any dev-mode execution is even considered.
    """
    issues: list[Issue] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover - defensive
        return ScanReport([error("py.syntax", f"cannot parse source: {exc}")])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _FORBIDDEN_IMPORTS:
                    issues.append(error("py.import", f"forbidden import: {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _FORBIDDEN_IMPORTS:
                issues.append(error("py.import", f"forbidden import from: {node.module}"))
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in _FORBIDDEN_CALLS:
                issues.append(error("py.call", f"forbidden call: {fn.id}()"))
            if isinstance(fn, ast.Attribute) and fn.attr in _FORBIDDEN_ATTR:
                issues.append(error("py.attr", f"forbidden attribute call: .{fn.attr}()"))
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"):
            if node.attr in ("__globals__", "__builtins__", "__subclasses__", "__bases__", "__mro__"):
                issues.append(error("py.dunder", f"forbidden dunder access: {node.attr}"))
    return ScanReport(issues)
