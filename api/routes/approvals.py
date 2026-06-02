"""
AgentSystem — Durable Human-in-the-Loop Approval Routes (PR4)

REST surface over the durable approval store (``tools/approvals_store``). When
``APPROVAL_MODE=durable`` a sensitive agent action persists a PENDING approval
and blocks; an operator resolves it here and the waiting agent unblocks on its
next poll.

Endpoints (mounted under ``/api/v1/approvals``):
    GET  ""                Recent approvals, optionally filtered by ``?status=``.
    GET  /{approval_id}     One approval (404 if unknown).
    POST /{approval_id}/approve   Approve a PENDING approval (optional feedback).
    POST /{approval_id}/reject    Reject a PENDING approval (optional feedback).

Decisions are atomic in the store. The route disambiguates the store's single
``None`` return by pre-fetching: unknown id -> 404; known but already terminal
-> 409. Sits behind ``AuthMiddleware`` like every other ``/api/v1`` route, and
degrades to a clean error rather than crashing if the store is unavailable.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tools import approvals_store

router = APIRouter()

_VALID_STATUSES = set(approvals_store.APPROVAL_STATUSES)


class DecisionRequest(BaseModel):
    """Optional body for approve/reject: free-text feedback + who decided."""

    feedback: str = ""
    decided_by: str = ""


@router.get("")
async def list_approvals(status: Optional[str] = None):
    """List recent approvals, newest first, optionally filtered by ``status``."""
    if status:
        normalized = status.strip().lower()
        if normalized not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid status '{status}'. "
                    f"Expected one of: {sorted(_VALID_STATUSES)}."
                ),
            )
        rows = approvals_store.list_approvals(status=normalized)
    else:
        rows = approvals_store.list_approvals()
    return {"approvals": [r.to_dict() for r in rows], "count": len(rows)}


@router.get("/{approval_id}")
async def get_approval(approval_id: str):
    """Fetch one approval, including its decision/feedback, or 404."""
    row = approvals_store.get_approval(approval_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Approval '{approval_id}' not found."
        )
    return row.to_dict()


def _decide(approval_id: str, approved: bool, body: Optional[DecisionRequest]):
    """Shared approve/reject handler with 404 (unknown) vs 409 (terminal)."""
    existing = approvals_store.get_approval(approval_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Approval '{approval_id}' not found."
        )
    if existing.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Approval '{approval_id}' is already {existing.status}; "
                "it can no longer be decided."
            ),
        )

    feedback = body.feedback if body else ""
    decided_by = body.decided_by if body else ""
    row = approvals_store.decide_approval(
        approval_id,
        approved=approved,
        feedback=feedback,
        decided_by=decided_by,
    )
    if row is None:
        # Lost a race: it went terminal between our pre-fetch and the UPDATE.
        raise HTTPException(
            status_code=409,
            detail=(
                f"Approval '{approval_id}' was decided concurrently; "
                "no change applied."
            ),
        )
    return row.to_dict()


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, body: Optional[DecisionRequest] = None):
    """Approve a PENDING approval (404 unknown, 409 already terminal)."""
    return _decide(approval_id, approved=True, body=body)


@router.post("/{approval_id}/reject")
async def reject(approval_id: str, body: Optional[DecisionRequest] = None):
    """Reject a PENDING approval (404 unknown, 409 already terminal)."""
    return _decide(approval_id, approved=False, body=body)
