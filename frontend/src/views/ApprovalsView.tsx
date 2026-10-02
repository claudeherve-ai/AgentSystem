import { useState } from "react";
import { Panel } from "../components/common/Panel";
import { Loading } from "../components/common/Loading";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { StatusPill } from "../components/common/StatusPill";
import { useApprovals } from "../hooks/useApprovals";
import type { Approval } from "../api/types";
import styles from "./ApprovalsView.module.css";

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

interface ApprovalCardProps {
  approval: Approval;
  decidingId: string | null;
  onDecide: (id: string, decision: "approve" | "reject", feedback?: string) => Promise<void>;
}

function ApprovalCard({ approval, decidingId, onDecide }: ApprovalCardProps) {
  const [feedback, setFeedback] = useState("");
  const busy = decidingId === approval.id;
  const pending = approval.status === "pending";

  return (
    <li className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <p className={styles.agent}>{approval.agent_name}</p>
          <p className={styles.action}>{approval.action}</p>
        </div>
        <StatusPill label={approval.status} status={approval.status} />
      </div>
      {approval.details ? <p className={styles.details}>{approval.details}</p> : null}
      <p className={styles.meta}>
        Requested {formatTimestamp(approval.requested_at)}
        {approval.decided_at ? ` · Decided ${formatTimestamp(approval.decided_at)}` : ""}
        {approval.decided_by ? ` by ${approval.decided_by}` : ""}
      </p>
      {approval.feedback ? <p className={styles.feedback}>Feedback: {approval.feedback}</p> : null}

      {pending ? (
        <div className={styles.form}>
          <label className={styles.feedbackLabel} htmlFor={`feedback-${approval.id}`}>
            Feedback (optional)
          </label>
          <input
            id={`feedback-${approval.id}`}
            className={styles.feedbackInput}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Add context for this decision"
          />
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.approve}
              disabled={busy}
              onClick={() => void onDecide(approval.id, "approve", feedback.trim() || undefined)}
            >
              {busy ? "Working…" : "Approve"}
            </button>
            <button
              type="button"
              className={styles.reject}
              disabled={busy}
              onClick={() => void onDecide(approval.id, "reject", feedback.trim() || undefined)}
            >
              {busy ? "Working…" : "Reject"}
            </button>
          </div>
        </div>
      ) : null}
    </li>
  );
}

/** Human-in-the-loop approval inbox: review, approve, or reject pending agent actions. */
export function ApprovalsView() {
  const { approvals, loading, error, refresh, decide, decidingId, decideError } = useApprovals();

  return (
    <Panel
      title="Approvals"
      description="Actions awaiting human sign-off before an agent proceeds."
      actions={
        <button type="button" className={styles.refresh} onClick={refresh}>
          Refresh
        </button>
      }
    >
      {decideError ? (
        <p className={styles.error} role="alert">
          {decideError.message}
        </p>
      ) : null}
      {loading ? (
        <Loading label="Loading approvals" rows={3} />
      ) : error ? (
        <ErrorState error={error} onRetry={refresh} />
      ) : approvals.length === 0 ? (
        <EmptyState title="No approvals pending" description="Nothing is waiting for a human decision right now." />
      ) : (
        <ul className={styles.list}>
          {approvals.map((approval) => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              decidingId={decidingId}
              onDecide={decide}
            />
          ))}
        </ul>
      )}
    </Panel>
  );
}
