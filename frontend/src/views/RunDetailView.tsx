import { useState } from "react";
import { Panel } from "../components/common/Panel";
import { Loading } from "../components/common/Loading";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { StatusPill } from "../components/common/StatusPill";
import { RunTopology } from "../components/timeline/RunTopology";
import { deriveTopology } from "../components/timeline/deriveTopology";
import { useRunDetail } from "../hooks/useRunDetail";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import styles from "./RunDetailView.module.css";

interface RunDetailViewProps {
  runId: string;
}

const ACTIVE_STATUSES = new Set(["pending", "queued", "running"]);

/** Live run detail: plan/agent/tool/approval/artifact topology, transcript, and controls. */
export function RunDetailView({ runId }: RunDetailViewProps) {
  const { client } = useApi();
  const { run, loading, error, streamStatus, streamError, refresh, reconnectStream } =
    useRunDetail(runId);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  async function handleCancel() {
    if (!run || cancelling) return;
    setCancelling(true);
    setCancelError(null);
    try {
      await client.cancelRun(run.id);
      refresh();
    } catch (cause) {
      setCancelError(cause instanceof ApiError ? cause.message : "Failed to cancel run");
    } finally {
      setCancelling(false);
    }
  }

  if (loading) {
    return (
      <Panel title="Run detail">
        <Loading label="Loading run" rows={6} />
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel title="Run detail">
        <ErrorState error={error} onRetry={refresh} />
      </Panel>
    );
  }

  if (!run) {
    return (
      <Panel title="Run detail">
        <EmptyState title="Run not found" description={`No run with id "${runId}" is visible to this client.`} />
      </Panel>
    );
  }

  const topology = deriveTopology(run.events);
  const canCancel = ACTIVE_STATUSES.has(run.status.toLowerCase());

  return (
    <div className={styles.stack}>
      <Panel
        title={`Run ${run.id}`}
        description={run.input ?? undefined}
        actions={
          <div className={styles.actionRow}>
            <StatusPill label={run.status} status={run.status} />
            {canCancel ? (
              <button type="button" className={styles.cancel} onClick={handleCancel} disabled={cancelling}>
                {cancelling ? "Cancelling…" : "Cancel run"}
              </button>
            ) : null}
          </div>
        }
      >
        <dl className={styles.meta}>
          <div>
            <dt>Agent</dt>
            <dd>{run.selected_agent ?? "Not yet routed"}</dd>
          </div>
          <div>
            <dt>Session</dt>
            <dd className={styles.mono}>{run.session_id ?? "—"}</dd>
          </div>
          <div>
            <dt>Stream</dt>
            <dd>
              <span aria-live="polite">{describeStreamStatus(streamStatus)}</span>
              {streamStatus === "error" || streamStatus === "reconnecting" ? (
                <button type="button" className={styles.reconnect} onClick={reconnectStream}>
                  Reconnect
                </button>
              ) : null}
            </dd>
          </div>
        </dl>
        {streamError ? (
          <p className={styles.warning} role="status">
            Live updates interrupted: {streamError}
          </p>
        ) : null}
        {cancelError ? (
          <p className={styles.warning} role="alert">
            {cancelError}
          </p>
        ) : null}
      </Panel>

      <Panel title="Run topology" description="Planner, agent, tool, approval, and artifact activity in sequence.">
        <RunTopology model={topology} />
      </Panel>

      <Panel title="Event transcript" description="Raw events as received, most recent last.">
        {run.events.length === 0 ? (
          <EmptyState title="No events yet" description="Events will appear here as the run progresses." />
        ) : (
          <ol className={styles.transcript}>
            {run.events.map((event) => (
              <li key={event.id} className={styles.transcriptItem}>
                <span className={styles.transcriptType}>{event.type}</span>
                <pre className={styles.transcriptData}>{safeStringify(event.data)}</pre>
              </li>
            ))}
          </ol>
        )}
      </Panel>

      {run.output ? (
        <Panel title="Output">
          <p className={styles.output}>{run.output}</p>
        </Panel>
      ) : null}
    </div>
  );
}

function describeStreamStatus(status: string): string {
  switch (status) {
    case "connecting":
      return "Connecting to live updates…";
    case "open":
      return "Live";
    case "reconnecting":
      return "Reconnecting…";
    case "closed":
      return "Closed (run finished)";
    case "error":
      return "Disconnected";
    default:
      return status;
  }
}

function safeStringify(data: Record<string, unknown>): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return "[unserializable event data]";
  }
}
