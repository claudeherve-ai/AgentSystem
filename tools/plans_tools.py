"""
Plans tools — durable, audit-logged, agent-callable plan/task management.

These tools sit on top of `plans_store.py` and give the orchestrator (and any
specialist) the ability to:
  - create a multi-step plan from a goal,
  - list / inspect existing plans,
  - mark steps in_progress / done / blocked,
  - append additional steps as work expands,
  - resume a plan (returns the next pending step + full context),
  - cancel a plan with a reason.

All tools NEVER raise — they return clean strings. Every public call writes a
parent-correlated audit-log lifecycle (started → completed | error).
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Optional

from pydantic import Field

from .audit import audit_log
from .plans_store import (
    PLAN_STATUSES,
    PLANS_DB,
    STEP_STATUSES,
    StepSpec,
    add_step,
    cancel_plan,
    create_plan,
    get_events,
    get_plan,
    list_plans,
    next_pending_step,
    update_step,
)

logger = logging.getLogger(__name__)


def _format_plan_summary(plan) -> str:
    if plan is None:
        return "(no plan)"
    done = sum(1 for s in plan.steps if s.status in {"done", "skipped"})
    total = len(plan.steps)
    tags = ", ".join(t for t in (plan.tags or "").split(",") if t)
    head = (
        f"plan_id   : {plan.id}\n"
        f"title     : {plan.title}\n"
        f"goal      : {plan.goal}\n"
        f"status    : {plan.status}  ({done}/{total} steps complete)\n"
        f"owner     : {plan.owner or '<unset>'}\n"
        f"tags      : {tags or '<none>'}\n"
        f"created   : {plan.created_at}\n"
        f"updated   : {plan.updated_at}\n"
    )
    if not plan.steps:
        return head + "  (no steps yet — call plan_add_step to extend)\n"
    rows = ["Steps:"]
    for s in plan.steps:
        owner = f" → {s.owner_agent}" if s.owner_agent else ""
        line = f"  [{s.step_index:>2}] {s.status:<11} {s.title}{owner}"
        rows.append(line)
        if s.description and s.status != "done":
            rows.append(f"        {s.description.strip().splitlines()[0][:160]}")
        if s.result and s.status == "done":
            preview = s.result.strip().splitlines()[0][:160]
            rows.append(f"        → {preview}")
    return head + "\n".join(rows) + "\n"


def _parse_steps_payload(steps_json: str) -> list[StepSpec]:
    """Accept either a JSON list of objects or a newline-separated list of titles."""
    text = (steps_json or "").strip()
    if not text:
        return []
    # Try JSON first
    if text.startswith("[") or text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"steps_json was not valid JSON: {exc}") from exc
        if isinstance(payload, dict):
            payload = [payload]
        out: list[StepSpec] = []
        for item in payload:
            if isinstance(item, str):
                out.append(StepSpec(title=item.strip()))
            elif isinstance(item, dict):
                out.append(
                    StepSpec(
                        title=str(item.get("title", "")).strip() or "Untitled step",
                        description=str(item.get("description", "") or ""),
                        owner_agent=str(item.get("owner_agent", "") or ""),
                    )
                )
        return out
    # Otherwise newline-separated titles
    return [StepSpec(title=line.strip()) for line in text.splitlines() if line.strip()]


async def plan_create(
    title: Annotated[str, Field(description="Short human-readable title for the plan.")],
    goal: Annotated[str, Field(description="Concrete outcome the plan is supposed to achieve.")],
    steps_json: Annotated[
        str,
        Field(
            default="",
            description=(
                "Optional initial steps. Either a JSON list — e.g. "
                "'[{\"title\": \"step 1\", \"owner_agent\": \"ResearchAgent\"}]' — "
                "or a newline-separated list of step titles. Empty = create an empty plan."
            ),
        ),
    ] = "",
    owner: Annotated[
        str,
        Field(default="", description="Optional owner label (defaults to 'Orchestrator')."),
    ] = "",
    tags: Annotated[
        str,
        Field(default="", description="Optional comma-separated tags for filtering."),
    ] = "",
) -> str:
    """Create a durable, resumable multi-step plan."""
    audit_id = audit_log(
        "Plans.create",
        "started",
        {"title": title[:120], "step_blob_len": len(steps_json or "")},
    )
    try:
        steps = _parse_steps_payload(steps_json)
    except ValueError as exc:
        audit_log("Plans.create", "error", {"reason": str(exc)}, parent_id=audit_id)
        return f"plan_create failed: {exc}"
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    plan = create_plan(
        title=title,
        goal=goal,
        steps=steps,
        owner=owner.strip() or "Orchestrator",
        tags=tag_list,
    )
    audit_log(
        "Plans.create",
        "completed",
        {"plan_id": plan.id, "step_count": len(plan.steps)},
        parent_id=audit_id,
    )
    return (
        f"Created plan {plan.id} with {len(plan.steps)} step(s).\n\n"
        + _format_plan_summary(plan)
    )


async def plan_list(
    status: Annotated[
        str,
        Field(
            default="",
            description=(
                "Optional filter — one of: pending, in_progress, done, blocked, cancelled. "
                "Empty = all plans."
            ),
        ),
    ] = "",
    limit: Annotated[int, Field(default=20, ge=1, le=100, description="Max plans to return.")] = 20,
) -> str:
    """List recent plans, newest first."""
    audit_id = audit_log("Plans.list", "started", {"status": status, "limit": limit})
    if status and status not in PLAN_STATUSES:
        audit_log("Plans.list", "error", {"reason": "bad_status"}, parent_id=audit_id)
        return f"plan_list: invalid status {status!r}. Allowed: {sorted(PLAN_STATUSES)}"
    plans = list_plans(status=status, limit=limit)
    audit_log("Plans.list", "completed", {"count": len(plans)}, parent_id=audit_id)
    if not plans:
        suffix = f" (status={status})" if status else ""
        return f"No plans found{suffix}. Store: {PLANS_DB}"
    lines = [f"Plans ({len(plans)}):"]
    for p in plans:
        done = sum(1 for s in p.steps if s.status in {"done", "skipped"})
        lines.append(
            f"  - {p.id}  [{p.status:<11}] {done}/{len(p.steps)}  "
            f"{p.title}  (updated {p.updated_at})"
        )
    lines.append(f"\nStore: {PLANS_DB}")
    return "\n".join(lines)


async def plan_get(
    plan_id: Annotated[str, Field(description="Plan ID returned by plan_create / plan_list.")],
) -> str:
    """Retrieve a plan with all of its steps and current status."""
    audit_id = audit_log("Plans.get", "started", {"plan_id": plan_id})
    plan = get_plan(plan_id)
    if not plan:
        audit_log("Plans.get", "error", {"reason": "not_found"}, parent_id=audit_id)
        return f"plan_get: no plan with id {plan_id!r}"
    audit_log("Plans.get", "completed", {"step_count": len(plan.steps)}, parent_id=audit_id)
    return _format_plan_summary(plan)


async def plan_step_update(
    plan_id: Annotated[str, Field(description="Plan ID.")],
    step_index: Annotated[int, Field(ge=0, description="Zero-based step index.")],
    status: Annotated[
        str,
        Field(
            default="",
            description=(
                "Optional new step status. One of: pending, in_progress, done, "
                "blocked, skipped. Empty = leave unchanged."
            ),
        ),
    ] = "",
    result: Annotated[
        str,
        Field(default="", description="Optional result text to store on the step."),
    ] = "",
    owner_agent: Annotated[
        str,
        Field(default="", description="Optional specialist agent assigned to this step."),
    ] = "",
) -> str:
    """Update a single step on a plan (status / result / owner / description)."""
    audit_id = audit_log(
        "Plans.step_update",
        "started",
        {"plan_id": plan_id, "step_index": step_index, "status": status},
    )
    if status and status not in STEP_STATUSES:
        audit_log(
            "Plans.step_update",
            "error",
            {"reason": "bad_status", "status": status},
            parent_id=audit_id,
        )
        return f"plan_step_update: invalid status {status!r}. Allowed: {sorted(STEP_STATUSES)}"
    try:
        new_step = update_step(
            plan_id=plan_id,
            step_index=step_index,
            status=status,
            result=result,
            owner_agent=owner_agent,
        )
    except ValueError as exc:
        audit_log("Plans.step_update", "error", {"reason": str(exc)}, parent_id=audit_id)
        return f"plan_step_update failed: {exc}"
    if new_step is None:
        audit_log(
            "Plans.step_update",
            "error",
            {"reason": "step_not_found"},
            parent_id=audit_id,
        )
        return f"plan_step_update: no step #{step_index} on plan {plan_id!r}"
    audit_log(
        "Plans.step_update",
        "completed",
        {"new_status": new_step.status},
        parent_id=audit_id,
    )
    plan = get_plan(plan_id)
    return (
        f"Updated step #{new_step.step_index} → {new_step.status}.\n\n"
        + _format_plan_summary(plan)
    )


async def plan_add_step(
    plan_id: Annotated[str, Field(description="Plan ID.")],
    title: Annotated[str, Field(description="Step title.")],
    description: Annotated[str, Field(default="", description="Optional longer description.")] = "",
    owner_agent: Annotated[
        str,
        Field(default="", description="Optional specialist agent to assign."),
    ] = "",
) -> str:
    """Append a new step to an existing plan."""
    audit_id = audit_log(
        "Plans.add_step",
        "started",
        {"plan_id": plan_id, "title": title[:120]},
    )
    new_step = add_step(
        plan_id=plan_id,
        title=title,
        description=description,
        owner_agent=owner_agent,
    )
    if new_step is None:
        audit_log("Plans.add_step", "error", {"reason": "plan_not_found"}, parent_id=audit_id)
        return f"plan_add_step: no plan with id {plan_id!r}"
    audit_log(
        "Plans.add_step",
        "completed",
        {"step_index": new_step.step_index},
        parent_id=audit_id,
    )
    plan = get_plan(plan_id)
    return (
        f"Added step #{new_step.step_index} to plan {plan_id}.\n\n"
        + _format_plan_summary(plan)
    )


async def plan_resume(
    plan_id: Annotated[str, Field(description="Plan ID to resume.")],
) -> str:
    """Return the next actionable step on a plan + full plan context.

    Use this after a restart, a content-filter blip, or whenever the
    orchestrator wants to pick a paused plan back up.
    """
    audit_id = audit_log("Plans.resume", "started", {"plan_id": plan_id})
    plan = get_plan(plan_id)
    if not plan:
        audit_log("Plans.resume", "error", {"reason": "not_found"}, parent_id=audit_id)
        return f"plan_resume: no plan with id {plan_id!r}"
    if plan.status in {"done", "cancelled"}:
        audit_log(
            "Plans.resume",
            "completed",
            {"reason": f"plan_{plan.status}"},
            parent_id=audit_id,
        )
        return f"Plan {plan_id} is {plan.status}; nothing to resume.\n\n" + _format_plan_summary(plan)
    next_step = next_pending_step(plan_id)
    audit_log(
        "Plans.resume",
        "completed",
        {"next_step": next_step.step_index if next_step else None},
        parent_id=audit_id,
    )
    if next_step is None:
        return (
            f"Plan {plan_id} has no pending or in-progress steps.\n\n"
            + _format_plan_summary(plan)
        )
    owner = f" (owner: {next_step.owner_agent})" if next_step.owner_agent else ""
    head = (
        f"Next step on plan {plan_id}{owner}:\n"
        f"  [{next_step.step_index}] {next_step.status:<11} {next_step.title}\n"
        f"  description: {next_step.description or '<none>'}\n\n"
    )
    return head + _format_plan_summary(plan)


async def plan_cancel(
    plan_id: Annotated[str, Field(description="Plan ID to cancel.")],
    reason: Annotated[str, Field(default="", description="Optional reason recorded on the plan.")] = "",
) -> str:
    """Cancel a plan and skip every still-open step."""
    audit_id = audit_log("Plans.cancel", "started", {"plan_id": plan_id})
    plan = cancel_plan(plan_id, reason=reason)
    if not plan:
        audit_log("Plans.cancel", "error", {"reason": "not_found"}, parent_id=audit_id)
        return f"plan_cancel: no plan with id {plan_id!r}"
    audit_log("Plans.cancel", "completed", {"plan_id": plan_id}, parent_id=audit_id)
    return f"Plan {plan_id} cancelled. Reason: {reason or '<none>'}\n\n" + _format_plan_summary(plan)


async def plan_events(
    plan_id: Annotated[str, Field(description="Plan ID.")],
    limit: Annotated[int, Field(default=20, ge=1, le=100, description="Max events to return.")] = 20,
) -> str:
    """Show the most recent audit events for a plan (newest first)."""
    audit_id = audit_log("Plans.events", "started", {"plan_id": plan_id})
    plan = get_plan(plan_id)
    if not plan:
        audit_log("Plans.events", "error", {"reason": "not_found"}, parent_id=audit_id)
        return f"plan_events: no plan with id {plan_id!r}"
    events = get_events(plan_id, limit=limit)
    audit_log("Plans.events", "completed", {"count": len(events)}, parent_id=audit_id)
    if not events:
        return f"No events recorded for plan {plan_id} yet."
    lines = [f"Events for {plan_id} (newest first):"]
    for e in events:
        payload = json.dumps(e["payload"], ensure_ascii=False) if e["payload"] else ""
        lines.append(f"  {e['ts']}  {e['kind']:<14} {payload}")
    return "\n".join(lines)


PLANS_TOOLS = [
    plan_create,
    plan_list,
    plan_get,
    plan_step_update,
    plan_add_step,
    plan_resume,
    plan_cancel,
    plan_events,
]
