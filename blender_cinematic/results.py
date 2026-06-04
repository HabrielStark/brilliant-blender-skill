"""Uniform result types shared by validators, linters and the evaluator."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .constants import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARN


@dataclass
class Issue:
    """A single validation/lint finding."""

    severity: str  # SEVERITY_ERROR | SEVERITY_WARN | SEVERITY_INFO
    code: str
    message: str
    location: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def error(code: str, message: str, location: str | None = None) -> Issue:
    return Issue(SEVERITY_ERROR, code, message, location)


def warn(code: str, message: str, location: str | None = None) -> Issue:
    return Issue(SEVERITY_WARN, code, message, location)


def info(code: str, message: str, location: str | None = None) -> Issue:
    return Issue(SEVERITY_INFO, code, message, location)


@dataclass
class CheckResult:
    """Aggregated issues for one named check (e.g. one linter)."""

    name: str
    issues: list[Issue] = field(default_factory=list)

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    def extend(self, issues: list[Issue]) -> None:
        self.issues.extend(issues)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARN]

    @property
    def passed(self) -> bool:
        """A check passes when it produced no errors (warnings allowed)."""
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [i.to_dict() for i in self.issues],
        }


def merge(name: str, results: list[CheckResult]) -> CheckResult:
    """Flatten several CheckResults into one aggregate result."""
    out = CheckResult(name=name)
    for r in results:
        for i in r.issues:
            loc = i.location or r.name
            out.add(Issue(i.severity, i.code, i.message, loc))
    return out
