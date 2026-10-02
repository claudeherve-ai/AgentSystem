import { Panel } from "../components/common/Panel";
import { Loading } from "../components/common/Loading";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { TaskComposer } from "../components/composer/TaskComposer";
import { RunList } from "../components/runs/RunList";
import { useRuns } from "../hooks/useRuns";
import styles from "./CommandView.module.css";

/** The default landing view: compose a new task and see recent activity. */
export function CommandView() {
  const { runs, loading, error, refresh } = useRuns({ limit: 8 });

  return (
    <div className={styles.grid}>
      <Panel title="Compose a task" description="Describe the outcome; routing can be automatic or pinned to an agent.">
        <TaskComposer onCreated={refresh} />
      </Panel>

      <Panel title="Recent runs" description="The most recent runs across every session.">
        {loading ? (
          <Loading label="Loading recent runs" rows={4} />
        ) : error ? (
          <ErrorState error={error} onRetry={refresh} />
        ) : runs.length === 0 ? (
          <EmptyState title="No runs yet" description="Dispatch a task above to see it appear here in real time." />
        ) : (
          <RunList runs={runs} />
        )}
      </Panel>
    </div>
  );
}
