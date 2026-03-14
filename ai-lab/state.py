"""
state.py — The explicit, mutable State Object.

This is the single source of truth for the system at any moment.
No model holds state in its context window — everything is here.
Passed between nodes by the workflow engine (LangGraph or main.py).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from memory import EpisodicMemory


@dataclass
class ExperimentResult:
    hypothesis: str
    outcome: str       # "success" | "failure" | "partial"
    output: str        # raw tool output or model response
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Episodic Memory (Layer 3 — persistent across runs) ─────────

@dataclass
class EpisodicEntry:
    """A single episode: one experiment cycle's outcome, persisted to episodic.json."""
    cycle_id: str
    goal: str
    hypothesis: str
    action: str          # what was actually done
    outcome: str         # "success" | "failure" | "partial"
    score_before: float | None = None
    score_after: float | None = None
    score_delta: float | None = None
    kept: bool | None = None   # True = kept, False = reverted, None = no git discipline yet
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)




@dataclass
class SystemState:
    """
    The 5-layer memory hierarchy collapsed into one serialisable object.

    Identity   → system_role (permanent, set once)
    Working    → current_goal, current_design, active_hypothesis
    Episodic   → recent_actions, recent_errors
    Semantic   → constraints, heuristics (injected from skills DB)
    Artifact   → handled by Paths.ARTIFACTS, referenced here by path
    """

    # ── Identity / Working memory ────────────────────────────────
    system_role: str = "autonomous-engineering-lab"
    current_goal: str = ""
    current_design: dict[str, Any] = field(default_factory=dict)
    active_hypothesis: str = ""

    # ── Project-level tracking ───────────────────────────────────
    project_graph: list[dict[str, Any]] = field(default_factory=list)
    task_queue: list[str] = field(default_factory=list)
    completed_tasks: list[str] = field(default_factory=list)
    task_replan_counts: dict[str, int] = field(default_factory=dict)

    # ── Episodic memory ──────────────────────────────────────────
    recent_experiments: list[ExperimentResult] = field(default_factory=list)
    failure_count: int = 0
    last_error: str = ""

    # ── Constraints & heuristics (semantic memory snapshot) ──────
    constraints: list[str] = field(default_factory=list)
    heuristics: list[str] = field(default_factory=list)

    # ── Loop metadata ────────────────────────────────────────────
    strategic_plan: str = ""       # last o1 plan (markdown/JSON)
    loop_iteration: int = 0
    escalated: bool = False        # True when handed off to o1

    def record_experiment(self, result: ExperimentResult) -> None:
        """Append an experiment result and bump the failure counter if needed."""
        self.recent_experiments.append(result)
        if result.outcome == "failure":
            self.failure_count += 1
            self.last_error = result.output
        else:
            self.failure_count = 0  # reset on success

    def context_summary(
        self,
        max_experiments: int = 5,
        episodic: EpisodicMemory | None = None,
    ) -> str:
        """
        Returns a compact, token-efficient summary injected into each
        worker's prompt. Keeps context fresh without bloat.

        If an EpisodicMemory is provided, includes persistent history
        from prior runs (Layer 3).
        """
        recent = self.recent_experiments[-max_experiments:]
        lines = [
            f"GOAL: {self.current_goal}",
            f"CURRENT DESIGN: {json.dumps(self.current_design, indent=2)}",
            f"ACTIVE HYPOTHESIS: {self.active_hypothesis}",
            f"FAILURES THIS CYCLE: {self.failure_count}",
            "",
            "CONSTRAINTS:",
            *[f"  - {c}" for c in self.constraints],
            "",
            "HEURISTICS:",
            *[f"  - {h}" for h in self.heuristics],
        ]
        if episodic and episodic.entries:
            lines.append("")
            lines.append(episodic.summary())
        lines.append("")
        lines.append("RECENT EXPERIMENTS (this run):")
        for ex in recent:
            lines.append(
                f"  [{ex.outcome.upper()}] {ex.hypothesis}: {ex.output[:200]}"
            )
        return "\n".join(lines)

    # ── Serialisation ────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemState":
        experiments = [
            ExperimentResult(**e)
            for e in data.pop("recent_experiments", [])
        ]
        obj = cls(**data)
        obj.recent_experiments = experiments
        return obj

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))

    @classmethod
    def load(cls, path: Path) -> "SystemState":
        return cls.from_dict(json.loads(path.read_text()))
