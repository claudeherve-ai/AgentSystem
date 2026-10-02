import { useHealth } from "../hooks/useHealth";
import { Panel } from "../components/common/Panel";
import { Loading } from "../components/common/Loading";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { StatusPill } from "../components/common/StatusPill";
import styles from "./OperationsView.module.css";

/** Dependency/system health, sourced directly from `/health/ready`. */
export function OperationsView() {
  const { report, loading, error, refresh } = useHealth();
  const deps = report ? Object.entries(report.dependencies) : [];

  return (
    <Panel
      title="Operations & dependency health"
      description="Live readiness report from the backend's /health/ready endpoint."
      actions={
        <button type="button" className={styles.refresh} onClick={refresh}>
          Refresh
        </button>
      }
    >
      {loading && !report ? (
        <Loading label="Loading health report" rows={3} />
      ) : error && !report ? (
        <ErrorState error={error} onRetry={refresh} />
      ) : !report ? (
        <EmptyState title="No health report available" notConfigured />
      ) : (
        <div className={styles.stack}>
          <div className={styles.summary} role="status" aria-live="polite">
            <StatusPill
              label={report.ready ? "Ready" : "Not ready"}
              tone={report.ready ? "positive" : "danger"}
            />
            <span className={styles.statusText}>{report.status}</span>
            {error ? (
              <span className={styles.staleNotice}>
                Last refresh failed — showing previous report.
              </span>
            ) : null}
          </div>

          {deps.length === 0 ? (
            <EmptyState title="No dependencies reported" notConfigured />
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Dependency</th>
                  <th scope="col">Status</th>
                  <th scope="col">Required</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {deps.map(([name, dep]) => (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>
                      <StatusPill
                        label={dep.healthy ? "Healthy" : "Unhealthy"}
                        tone={dep.healthy ? "positive" : "danger"}
                      />
                    </td>
                    <td>{dep.required ? "Yes" : "No"}</td>
                    <td className={styles.detail}>{dep.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </Panel>
  );
}
