import { useEffect, useMemo, useRef, useState } from "react";
import { useApi } from "../state/ApiProvider";
import type { RunEvent } from "../api/types";

export type StreamStatus = "connecting" | "open" | "reconnecting" | "closed" | "error";

export interface UseRunStreamResult {
  events: RunEvent[];
  status: StreamStatus;
  /** Set once a terminal run.* event has been observed on the stream. */
  terminal: boolean;
  lastError: string | null;
  /** Force a fresh connection attempt (e.g. after the user comes back online). */
  reconnect: () => void;
}

const TERMINAL_TYPES = new Set(["run.completed", "run.failed", "run.cancelled"]);
const MAX_BACKOFF_MS = 15_000;
const BASE_BACKOFF_MS = 750;

/**
 * Subscribes to a run's live SSE event stream, merging it with any events
 * already known (e.g. from an initial `GET /runs/{id}` snapshot), and
 * automatically reconnects with capped exponential backoff — resuming via
 * `Last-Event-ID` so no events are lost or duplicated across a reconnect.
 *
 * Stops reconnecting once a terminal event (`run.completed` / `run.failed` /
 * `run.cancelled`) has been observed, since the server closes the stream for
 * good at that point.
 */
export function useRunStream(runId: string | null, initialEvents: RunEvent[] = []): UseRunStreamResult {
  const { client } = useApi();
  const [events, setEvents] = useState<RunEvent[]>(initialEvents);
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [lastError, setLastError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const seenIds = useRef(new Set<number>());
  const syntheticIdCounter = useRef(-1);
  const terminalRef = useRef(false);

  // Reset local buffers whenever we switch to a different run.
  useEffect(() => {
    setEvents(initialEvents);
    seenIds.current = new Set(initialEvents.map((e) => e.id));
    terminalRef.current = initialEvents.some((e) => TERMINAL_TYPES.has(e.type));
    setAttempt(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const terminal = useMemo(
    () => events.some((e) => TERMINAL_TYPES.has(e.type)),
    [events],
  );

  useEffect(() => {
    if (!runId || terminalRef.current) {
      setStatus(terminalRef.current ? "closed" : "connecting");
      return;
    }

    const controller = new AbortController();
    let cancelled = false;
    let backoffTimer: ReturnType<typeof setTimeout> | undefined;

    setStatus(attempt === 0 ? "connecting" : "reconnecting");

    const highestKnownId = (): number | null => {
      let max: number | null = null;
      for (const id of seenIds.current) {
        if (id >= 0 && (max === null || id > max)) max = id;
      }
      return max;
    };

    async function run() {
      try {
        const stream = client.streamRunEvents(runId as string, {
          lastEventId: highestKnownId(),
          signal: controller.signal,
        });
        setStatus("open");
        for await (const evt of stream) {
          if (cancelled) return;
          const id = evt.id ?? syntheticIdCounter.current--;
          if (seenIds.current.has(id)) continue;
          seenIds.current.add(id);
          const data =
            evt.data && typeof evt.data === "object" && !Array.isArray(evt.data)
              ? (evt.data as Record<string, unknown>)
              : {};
          const runEvent: RunEvent = { id, type: evt.type, data };
          setEvents((prev) => [...prev, runEvent].sort((a, b) => a.id - b.id));
          if (TERMINAL_TYPES.has(evt.type)) {
            terminalRef.current = true;
          }
        }
        // The API intentionally closes idle streams. Reconnect unless a terminal
        // event was observed so later durable events are still delivered.
        if (!cancelled) {
          if (terminalRef.current) {
            setStatus("closed");
            return;
          }
          setStatus("reconnecting");
          const delay = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS);
          backoffTimer = setTimeout(() => {
            if (!cancelled) setAttempt((n) => n + 1);
          }, delay);
        }
      } catch (cause) {
        if (cancelled || controller.signal.aborted) return;
        setLastError(cause instanceof Error ? cause.message : "Stream connection lost");
        if (terminalRef.current) {
          setStatus("closed");
          return;
        }
        setStatus("error");
        const delay = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS);
        backoffTimer = setTimeout(() => {
          if (!cancelled) setAttempt((n) => n + 1);
        }, delay);
      }
    }

    void run();

    return () => {
      cancelled = true;
      controller.abort();
      if (backoffTimer) clearTimeout(backoffTimer);
    };
  }, [client, runId, attempt]);

  return {
    events,
    status,
    terminal,
    lastError,
    reconnect: () => setAttempt((n) => n + 1),
  };
}
