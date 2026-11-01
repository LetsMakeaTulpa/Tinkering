"""A tiny, durable step runner.

A workflow is an ordered list of (agent, function). Each step's output is saved in the task_steps table and merged
into run.state, so a run can pause (human approval), crash, or restart and continue from the next step.
Phase 2 moves execution into a Redis-backed worker (arq/Celery); the step functions stay the same.
"""

import traceback
from datetime import datetime, timezone
from typing import Awaitable, Callable

from sqlalchemy.orm import Session

from ..models import Project, TaskRun, TaskStep

StepFn = Callable[["Ctx"], Awaitable[dict]]
WORKFLOWS: dict[str, list[tuple[str, StepFn]]] = {}
PAUSE = "_pause"  # a step returns {PAUSE: True, ...} to wait for a human


class Ctx:
    def __init__(self, db: Session, run: TaskRun, project: Project):
        self.db, self.run, self.project = db, run, project

    @property
    def input(self) -> dict:
        return self.run.input

    @property
    def state(self) -> dict:
        return self.run.state


def workflow(name: str, steps: list[tuple[str, StepFn]]):
    WORKFLOWS[name] = steps


def _now():
    return datetime.now(timezone.utc)


async def run_workflow(db: Session, run_id: str) -> TaskRun:
    run = db.get(TaskRun, run_id)
    project = db.get(Project, run.project_id)
    steps = WORKFLOWS[run.workflow]
    run.status = "running"
    db.commit()
    done = {s.idx for s in run.steps if s.status == "done"}
    for idx, (agent, fn) in enumerate(steps):
        if idx in done:
            continue
        step = next((s for s in run.steps if s.idx == idx), None) or TaskStep(run_id=run.id, idx=idx, agent=agent)
        step.status, step.started_at, step.error = "running", _now(), None
        db.add(step)
        db.commit()
        try:
            out = await fn(Ctx(db, run, project))
        except Exception as e:  # noqa: BLE001
            step.status, step.error, step.ended_at = "failed", f"{type(e).__name__}: {e}", _now()
            run.status, run.error = "failed", f"{agent}: {e}\n{traceback.format_exc(limit=3)}"
            db.commit()
            return run
        pause = out.pop(PAUSE, False)
        step.output, step.ended_at = out, _now()
        run.state = {**run.state, **out}  # reassign so SQLAlchemy sees the JSON change
        if pause:
            step.status, run.status = "awaiting_approval", "awaiting_approval"
            db.commit()
            return run
        step.status = "done"
        db.commit()
    run.status = "done"
    db.commit()
    return run


def approve(db: Session, run: TaskRun, edits: dict | None = None) -> None:
    """Mark the paused step done (optionally with human edits merged into state) so the run can continue."""
    step = next(s for s in run.steps if s.status == "awaiting_approval")
    step.status = "done"
    run.state = {**run.state, **(edits or {}), "approved": True}
    run.status = "pending"
    db.commit()
