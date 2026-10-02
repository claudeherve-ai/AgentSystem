import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import type { RunDetail } from "../api/types";
import { useRunStream } from "./useRunStream";

export interface UseRunDetailResult {
  run: RunDetail | null;
  loading: boolean;
  error: ApiError | null;
  streamStatus: ReturnType<typeof useRunStream>["status"];
  streamError: string | null;
  refresh: () => void;
  reconnectStream: () => void;
}

/**
 * Loads a run's snapshot via `GET /api/v1/runs/{id}` and layers the live SSE
 * stream on top so the events list keeps growing while the run is active.
 */
export function useRunDetail(runId: string | null): UseRunDetailResult {
  const { client } = useApi();
  const [snapshot, setSnapshot] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [nonce, setNonce] = useState(0);
  const terminalRefresh = useRef<{ runId: string; eventId: number } | null>(null);

  useEffect(() => {
    terminalRefresh.current = null;
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      setSnapshot(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    client
      .getRun(runId)
      .then((detail) => {
        if (!cancelled) {
          if (terminalRefresh.current === null && runId) {
            const terminalEvent = findLastTerminal(detail.events);
            terminalRefresh.current = {
              runId,
              eventId: terminalEvent?.id ?? 0,
            };
          }
          setSnapshot(detail);
        }
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError(0, { code: "network_error", message: "Failed to load run" }),
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, runId, nonce]);

  const stream = useRunStream(runId, snapshot?.events ?? []);

  useEffect(() => {
    if (!runId) return;
    const terminalEvent = findLastTerminal(stream.events);
    if (!terminalEvent) return;
    const refreshed = terminalRefresh.current;
    if (
      refreshed?.runId === runId &&
      terminalEvent.id <= refreshed.eventId
    ) {
      return;
    }
    terminalRefresh.current = { runId, eventId: terminalEvent.id };
    setNonce((n) => n + 1);
  }, [runId, stream.events]);

  const run: RunDetail | null = snapshot
    ? {
        ...snapshot,
        events: stream.events,
        status: deriveDisplayStatus(snapshot.status, stream),
      }
    : null;

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return {
    run,
    loading,
    error,
    streamStatus: stream.status,
    streamError: stream.lastError,
    refresh,
    reconnectStream: stream.reconnect,
  };
}

function deriveDisplayStatus(
  snapshotStatus: string,
  stream: ReturnType<typeof useRunStream>,
): string {
  const lastTerminal = [...stream.events].reverse().find((e) =>
    ["run.completed", "run.failed", "run.cancelled"].includes(e.type),
  );
  if (lastTerminal) {
    if (lastTerminal.type === "run.completed") return "completed";
    if (lastTerminal.type === "run.failed") return "failed";
    return "cancelled";
  }
  return snapshotStatus;
}

function findLastTerminal(events: RunDetail["events"]) {
  return [...events].reverse().find((event) =>
    ["run.completed", "run.failed", "run.cancelled"].includes(event.type),
  );
}
