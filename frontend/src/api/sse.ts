/**
 * Manual Server-Sent Events client.
 *
 * We don't use `EventSource` because it can't send custom headers (no
 * Authorization support) and its native `Last-Event-ID` resumption is opaque.
 * Instead we drive the stream with `fetch` + `ReadableStream`, parse frames
 * ourselves, and track the last event id so callers can resume a dropped
 * connection with an explicit `Last-Event-ID` header — the same mechanism
 * `api/routes/runs.py` honors server-side (header takes precedence over the
 * `?last_event_id=` query fallback, which we also set for proxies that strip
 * custom headers).
 */

export interface ParsedSseEvent {
  id: number | null;
  event: string;
  data: string;
}

interface ParseResult {
  events: ParsedSseEvent[];
  remainder: string;
}

/**
 * Pure frame parser: splits a raw SSE text buffer into complete `\n\n`
 * terminated frames, returning parsed events plus any trailing partial
 * frame that should be prepended to the next chunk. Exported standalone so
 * it can be unit tested without any network/stream plumbing.
 */
export function extractSseEvents(buffer: string): ParseResult {
  const frames = buffer.split("\n\n");
  // The last element is either "" (buffer ended exactly on a boundary) or an
  // incomplete trailing frame — either way it doesn't belong in this batch.
  const remainder = frames.pop() ?? "";

  const events: ParsedSseEvent[] = [];
  for (const frame of frames) {
    if (!frame.trim()) continue;
    let id: number | null = null;
    let event = "message";
    const dataLines: string[] = [];

    for (const rawLine of frame.split("\n")) {
      const line = rawLine.replace(/\r$/, "");
      if (line.startsWith(":")) continue; // comment / keep-alive
      if (line.startsWith("id:")) {
        const value = line.slice(3).trim();
        const parsed = Number(value);
        id = Number.isFinite(parsed) ? parsed : null;
      } else if (line.startsWith("event:")) {
        event = line.slice(6).trim() || "message";
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^ /, ""));
      }
    }

    if (dataLines.length > 0) {
      events.push({ id, event, data: dataLines.join("\n") });
    }
  }

  return { events, remainder };
}

export interface RunStreamEvent {
  id: number | null;
  type: string;
  data: unknown;
  raw: string;
}

export interface StreamRunEventsOptions {
  /** Absolute stream URL, e.g. `${baseUrl}/api/v1/runs/{id}/events`. */
  url: string;
  /** Additional headers (auth, etc.) merged with SSE Accept header. */
  headers?: Record<string, string>;
  credentials?: RequestCredentials;
  /** Resume from this event id (both header and query param are sent). */
  lastEventId?: number | null;
  signal?: AbortSignal;
}

/**
 * Opens the SSE stream and yields parsed, JSON-decoded events one at a time.
 * Throws on non-2xx responses (caller decides whether to reconnect). Ends
 * normally when the server closes the stream (run reached a terminal state).
 */
export async function* streamRunEvents(
  options: StreamRunEventsOptions,
): AsyncGenerator<RunStreamEvent, void, void> {
  const { url, headers = {}, credentials, lastEventId, signal } = options;

  const target = new URL(url);
  if (lastEventId != null) {
    target.searchParams.set("last_event_id", String(lastEventId));
  }

  const requestHeaders: Record<string, string> = {
    Accept: "text/event-stream",
    ...headers,
  };
  if (lastEventId != null) {
    requestHeaders["Last-Event-ID"] = String(lastEventId);
  }

  const response = await fetch(target.toString(), {
    method: "GET",
    headers: requestHeaders,
    credentials,
    signal,
  });

  if (!response.ok) {
    const err = new Error(`Stream request failed with status ${response.status}`);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }
  if (!response.body) {
    throw new Error("Stream response had no body (unsupported environment)");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const { events, remainder } = extractSseEvents(buffer);
      buffer = remainder;

      for (const evt of events) {
        yield {
          id: evt.id,
          type: evt.event,
          data: safeJsonParse(evt.data),
          raw: evt.data,
        };
      }
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      // Reader already closed/aborted — nothing to do.
    }
  }
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
