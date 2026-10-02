import { useEffect, useState } from "react";
import { Panel } from "../components/common/Panel";
import { Loading } from "../components/common/Loading";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { useRuns } from "../hooks/useRuns";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import { navigate } from "../hooks/useHashRoute";
import styles from "./ArtifactsView.module.css";

interface ArtifactRow {
  runId: string;
  eventId: number;
  data: Record<string, unknown>;
}

const SCAN_LIMIT = 12;

function summarize(data: Record<string, unknown>): string {
  const name = data["name"] ?? data["path"] ?? data["filename"] ?? data["uri"];
  return typeof name === "string" ? name : JSON.stringify(data).slice(0, 80);
}

/**
 * There is no dedicated `/artifacts` listing endpoint on the current backend.
 * Rather than inventing one, this view honestly derives the closest real
 * signal available: `artifact.created` events from recently loaded runs.
 */
export function ArtifactsView() {
  const { runs, loading: runsLoading, error: runsError } = useRuns({ limit: SCAN_LIMIT });
  const { client } = useApi();
  const [artifacts, setArtifacts] = useState<ArtifactRow[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (runs.length === 0) {
      setArtifacts([]);
      return;
    }
    let cancelled = false;
    setScanning(true);
    setScanError(null);
    Promise.all(
      runs.map((run) =>
        client.getRun(run.id).catch((cause: unknown) => {
          if (cause instanceof ApiError && cause.status === 404) return null;
          throw cause;
        }),
      ),
    )
      .then((details) => {
        if (cancelled) return;
        const rows: ArtifactRow[] = [];
        for (const detail of details) {
          if (!detail) continue;
          for (const event of detail.events) {
            if (event.type === "artifact.created") {
              rows.push({ runId: detail.id, eventId: event.id, data: event.data });
            }
          }
        }
        setArtifacts(rows);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setScanError(
            cause instanceof ApiError
              ? cause
              : new ApiError(0, { code: "network_error", message: "Failed to scan runs for artifacts" }),
          );
        }
      })
      .finally(() => {
        if (!cancelled) setScanning(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runs, client]);

  const loading = runsLoading || scanning;
  const error = runsError ?? scanError;

  return (
    <Panel
      title="Artifacts"
      description={`Derived from artifact.created events across the last ${SCAN_LIMIT} runs. There is no dedicated artifacts index on the backend yet.`}
    >
      {loading ? (
        <Loading label="Scanning recent runs for artifacts" rows={3} />
      ) : error ? (
        <ErrorState error={error} />
      ) : artifacts.length === 0 ? (
        <EmptyState
          title="No artifacts observed"
          description="No artifact.created events were found in the most recently loaded runs."
          notConfigured
        />
      ) : (
        <ul className={styles.list}>
          {artifacts.map((row) => (
            <li key={`${row.runId}-${row.eventId}`} className={styles.item}>
              <button
                type="button"
                className={styles.link}
                onClick={() => navigate(`/runs/${row.runId}`)}
              >
                {summarize(row.data)}
              </button>
              <span className={styles.runRef}>from run {row.runId}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
