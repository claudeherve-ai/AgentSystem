import { useCallback, useEffect, useState } from "react";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import type { HealthReport } from "../api/types";

const DEFAULT_POLL_MS = 15_000;

function pollIntervalMs(): number {
  const raw = import.meta.env.VITE_HEALTH_POLL_MS;
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_POLL_MS;
}

export interface UseHealthResult {
  report: HealthReport | null;
  loading: boolean;
  error: ApiError | null;
  refresh: () => void;
}

/** Polls `/health/ready` on an interval, tolerating the legitimate 503 "degraded" body. */
export function useHealth(): UseHealthResult {
  const { client } = useApi();
  const [report, setReport] = useState<HealthReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function tick() {
      try {
        const result = await client.getHealthReady();
        if (cancelled) return;
        setReport(result);
        setError(null);
      } catch (cause) {
        if (cancelled) return;
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError(0, { code: "network_error", message: "Failed to load health status" }),
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
          timer = setTimeout(tick, pollIntervalMs());
        }
      }
    }

    setLoading(true);
    void tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [client, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return { report, loading, error, refresh };
}
