import { useCallback, useEffect, useState } from "react";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import type { RunSummary } from "../api/types";

export interface UseRunsResult {
  runs: RunSummary[];
  loading: boolean;
  error: ApiError | null;
  refresh: () => void;
}

/** Lists runs (optionally filtered), with manual refresh — no polling by default. */
export function useRuns(params: { sessionId?: string; status?: string; limit?: number } = {}): UseRunsResult {
  const { client } = useApi();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [nonce, setNonce] = useState(0);

  const sessionId = params.sessionId;
  const status = params.status;
  const limit = params.limit;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    client
      .listRuns({ sessionId, status, limit })
      .then((res) => {
        if (cancelled) return;
        setRuns(res.runs);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(cause instanceof ApiError ? cause : new ApiError(0, { code: "network_error", message: "Failed to load runs" }));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, sessionId, status, limit, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return { runs, loading, error, refresh };
}
