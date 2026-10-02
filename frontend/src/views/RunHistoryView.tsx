import { useState } from "react";
import { Panel } from "../components/common/Panel";
import { Loading } from "../components/common/Loading";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { RunList } from "../components/runs/RunList";
import { useRuns } from "../hooks/useRuns";
import styles from "./RunHistoryView.module.css";

const STATUS_OPTIONS = ["", "pending", "queued", "running", "completed", "failed", "cancelled"];

/** Full run history with reproducibility-relevant filters (session, status). */
export function RunHistoryView() {
  const [sessionId, setSessionId] = useState("");
  const [status, setStatus] = useState("");
  const { runs, loading, error, refresh } = useRuns({
    sessionId: sessionId.trim() || undefined,
    status: status || undefined,
    limit: 100,
  });

  return (
    <Panel
      title="Run history"
      description="Every run this client has visibility into, with its inputs for reproducibility."
      actions={
        <button type="button" className={styles.refresh} onClick={refresh}>
          Refresh
        </button>
      }
    >
      <form
        className={styles.filters}
        onSubmit={(e) => e.preventDefault()}
        role="search"
        aria-label="Filter run history"
      >
        <div className={styles.field}>
          <label htmlFor="filter-session">Session ID</label>
          <input
            id="filter-session"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Filter by session"
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="filter-status">Status</label>
          <select id="filter-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt || "any"} value={opt}>
                {opt || "Any status"}
              </option>
            ))}
          </select>
        </div>
      </form>

      {loading ? (
        <Loading label="Loading run history" rows={6} />
      ) : error ? (
        <ErrorState error={error} onRetry={refresh} />
      ) : runs.length === 0 ? (
        <EmptyState
          title="No runs match these filters"
          description="Try clearing the session or status filter."
        />
      ) : (
        <RunList runs={runs} />
      )}
    </Panel>
  );
}
