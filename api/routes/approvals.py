"""Tenant-scoped durable human-in-the-loop approval routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from agentsystem.db.models import APPROVAL_STATUSES, Approval
from agentsystem.db.session import session_scope
from agentsystem.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from agentsystem.repositories import ApprovalRepository
from api.context import resolve_context
from api.dependencies import get_run_service

router = APIRouter()
_APPROVER_ROLES = frozenset({"owner", "admin", "approver"})


class DecisionRequest(BaseModel):
    feedback: str = Field(default="", max_length=4000)


def _approval_dict(row: Approval) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "workspace_id": row.workspace_id,
        "agent_name": row.agent_name,
        "action": row.action,
        "details": row.details,
        "status": row.status,
        "feedback": row.feedback,
        "decided_by": row.decided_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }


def _require_approver(ctx) -> None:
    if not _APPROVER_ROLES.intersection(ctx.roles):
        raise ForbiddenError("approval role required")


@router.get("")
async def list_approvals(
    request: Request, status: Optional[str] = None, limit: int = 100
):
    ctx = await resolve_context(request)
    _require_approver(ctx)
    normalized = (status or "").strip().lower()
    if normalized and normalized not in APPROVAL_STATUSES:
        raise ValidationError(
            "invalid approval status",
            details={"allowed": list(APPROVAL_STATUSES)},
        )
    async with session_scope() as session:
        rows = await ApprovalRepository(session).list(
            ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            status=normalized,
            limit=max(1, min(limit, 200)),
        )
    return {"approvals": [_approval_dict(row) for row in rows], "count": len(rows)}


@router.get("/{approval_id}")
async def get_approval(request: Request, approval_id: str):
    ctx = await resolve_context(request)
    _require_approver(ctx)
    async with session_scope() as session:
        row = await ApprovalRepository(session).get(
            ctx.tenant_id, approval_id, workspace_id=ctx.workspace_id
        )
    return _approval_dict(row)


async def _decide(
    request: Request,
    approval_id: str,
    *,
    approved: bool,
    body: Optional[DecisionRequest],
):
    ctx = await resolve_context(request)
    _require_approver(ctx)
    async with session_scope() as session:
        approval = await ApprovalRepository(session).get(
            ctx.tenant_id,
            approval_id,
            workspace_id=ctx.workspace_id,
        )
        run_id = approval.run_id

    if run_id:
        decision = await get_run_service().decide_run_approval(
            ctx.tenant_id,
            run_id,
            approval_id,
            approved=approved,
            feedback=body.feedback if body else "",
            decided_by=ctx.user_id,
        )
    else:
        async with session_scope() as session:
            decision = await ApprovalRepository(session).decide(
                ctx.tenant_id,
                approval_id,
                approved=approved,
                feedback=body.feedback if body else "",
                decided_by=ctx.user_id,
            )
    if decision.outcome == "not_found":
        raise NotFoundError("approval not found")
    if decision.outcome == "conflict":
        raise ConflictError("approval is already terminal or expired")
    return _approval_dict(decision.approval)


@router.post("/{approval_id}/approve")
async def approve(
    request: Request,
    approval_id: str,
    body: Optional[DecisionRequest] = None,
):
    return await _decide(
        request, approval_id, approved=True, body=body
    )


@router.post("/{approval_id}/reject")
async def reject(
    request: Request,
    approval_id: str,
    body: Optional[DecisionRequest] = None,
):
    return await _decide(
        request, approval_id, approved=False, body=body
    )


__all__ = ["router"]
