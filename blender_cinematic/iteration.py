"""Iteration manager (SRS 7.2 / 43.2).

Owns the improvement loop policy: per-mode budget, early stop on pass, and the
"3 iterations without improvement -> stop with failure" rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MIN_ITERATIONS,
    ITERATION_BUDGETS,
    PASS_THRESHOLD,
)
from .evaluation import IterationEval


@dataclass
class IterationManager:
    output_mode: str = "still"
    max_iterations: int | None = None
    min_iterations: int = DEFAULT_MIN_ITERATIONS
    pass_threshold: int = PASS_THRESHOLD
    stall_limit: int = 3
    history: list[IterationEval] = field(default_factory=list)

    def __post_init__(self) -> None:
        budget = ITERATION_BUDGETS.get(self.output_mode, DEFAULT_MAX_ITERATIONS)
        if self.max_iterations is None:
            self.max_iterations = budget
        # Never exceed the global hard cap unless explicitly overridden upstream.
        self.max_iterations = min(self.max_iterations, max(budget, DEFAULT_MAX_ITERATIONS))

    def record(self, ev: IterationEval) -> None:
        self.history.append(ev)

    @property
    def best(self) -> IterationEval | None:
        if not self.history:
            return None
        return max(self.history, key=lambda e: (e.passed, not e.hard_fail, e.total))

    def _stalled(self) -> bool:
        if len(self.history) <= self.stall_limit:
            return False
        recent = self.history[-(self.stall_limit + 1):]
        # No strict improvement across the last `stall_limit` steps.
        return all(b.total <= a.total for a, b in zip(recent, recent[1:]))

    def should_continue(self) -> tuple[bool, str]:
        n = len(self.history)
        if n == 0:
            return True, "no iterations yet"
        last = self.history[-1]
        if last.passed and n >= self.min_iterations:
            return False, f"passed at iteration {last.iteration} (score {last.total})"
        if last.passed and n < self.min_iterations:
            return True, f"passed but below minimum {self.min_iterations} iterations"
        if n >= self.max_iterations:
            return False, f"reached iteration budget {self.max_iterations}"
        if self._stalled():
            return False, f"no score improvement over {self.stall_limit} iterations -> stop with failure"
        return True, "below pass threshold; continue improving"

    def summary(self) -> dict:
        cont, reason = self.should_continue()
        best = self.best
        return {
            "output_mode": self.output_mode,
            "max_iterations": self.max_iterations,
            "iterations_run": len(self.history),
            "best_score": best.total if best else None,
            "best_iteration": best.iteration if best else None,
            "passed": bool(best and best.passed),
            "should_continue": cont,
            "stop_reason": None if cont else reason,
            "history": [e.to_dict() for e in self.history],
        }
