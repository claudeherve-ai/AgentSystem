import { useEffect, useState } from "react";
import { Panel } from "../components/common/Panel";
import { Loading } from "../components/common/Loading";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import type { ObservabilityStats, ObservabilityTraces, ObservabilitySpan } from "../api/types";
import styles from "./EvaluationsView.module.css";

interface LoadState {
  stats: ObservabilityStats | null;
  traces: ObservabilityTraces | null;
  notConfigured: boolean;
  loading: boolean;
  error: ApiError | null;
}

function pick(span: ObservabilitySpan, keys: string[]): string {
  for (const key of keys) {
    const value = span[key];
    if (typeof value === "string" || typeof value === "number") return String(value);
  }
  return "—";
}

/** Quality/latency/cost signals sourced from the observability endpoints, rendered defensively. */
export function EvaluationsView() {
  const { client } = useApi();
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState<LoadState>({
    stats: null,
    traces: null,
    notConfigured: false,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));

    Promise.allSettled([client.getObservabilityStats(), client.getObservabilityTraces(50)]).then(
      ([statsResult, tracesResult]) => {
        if (cancelled) return;

        const notFound = (r: PromiseSettledResult<unknown>) =>
          r.status === "rejected" && r.reason instanceof ApiError && r.reason.status === 404;

        if (notFound(statsResult) && notFound(tracesResult)) {
          setState({ stats: null, traces: null, notConfigured: true, loading: false, error: null });
          return;
        }

        const hardError = [statsResult, tracesResult].find(
          (r): r is PromiseRejectedResult => r.status === "rejected" && !notFound(r),
        );
        if (hardError) {
          setState({
            stats: null,
            traces: null,
            notConfigured: false,
            loading: false,
            error:
              hardError.reason instanceof ApiError
                ? hardError.reason
                : new ApiError(0, { code: "network_error", message: "Failed to load evaluation data" }),
          });
          return;
        }

        setState({
          stats: statsResult.status === "fulfilled" ? statsResult.value : null,
          traces: tracesResult.status === "fulfilled" ? tracesResult.value : null,
          notConfigured: false,
          loading: false,
          error: null,
        });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [client, nonce]);

  const { stats, traces, notConfigured, loading, error } = state;
  const statsEntries = stats ? Object.entries(stats) : [];

  return (
    <Panel
      title="Evaluations"
      description="Quality, latency, and cost signals reported by the observability endpoints."
      actions={
        <button type="button" className={styles.refresh} onClick={() => setNonce((n) => n + 1)}>
          Refresh
        </button>
      }
    >
      {loading ? (
        <Loading label="Loading evaluation data" rows={4} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => setNonce((n) => n + 1)} />
      ) : notConfigured ? (
        <EmptyState
          title="Observability endpoints are not configured"
          description="This deployment does not expose /api/v1/observability/stats or /traces."
          notConfigured
        />
      ) : (
        <div className={styles.stack}>
          <section>
            <h3 className={styles.sectionTitle}>Stats</h3>
            {statsEntries.length === 0 ? (
              <EmptyState title="No stats reported" notConfigured />
            ) : (
              <dl className={styles.statGrid}>
                {statsEntries.map(([key, value]) => (
                  <div key={key} className={styles.statCard}>
                    <dt>{key}</dt>
                    <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          <section>
            <h3 className={styles.sectionTitle}>
              Recent traces {traces ? `(${traces.count})` : ""}
            </h3>
            {!traces || traces.spans.length === 0 ? (
              <EmptyState title="No traces reported" notConfigured />
            ) : (
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Status</th>
                    <th scope="col">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {traces.spans.map((span, i) => (
                    <tr key={i}>
                      <td>{pick(span, ["name", "span_name", "operation"])}</td>
                      <td>{pick(span, ["status", "status_code"])}</td>
                      <td>{pick(span, ["duration_ms", "latency_ms", "duration"])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      )}
    </Panel>
  );
}
