import { extractSseEvents, streamRunEvents } from "../src/api/sse";

describe("SSE parsing", () => {
  it("parses complete events and preserves a partial frame", () => {
    const parsed = extractSseEvents(
      'id: 4\nevent: run.started\ndata: {"ok":true}\n\nid: 5\nevent: message.delta',
    );

    expect(parsed.events).toEqual([
      { id: 4, event: "run.started", data: '{"ok":true}' },
    ]);
    expect(parsed.remainder).toContain("id: 5");
  });

  it("sends Last-Event-ID in the header and query string", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("id: 8\nevent: run.completed\ndata: {}\n\n", {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );

    const received = [];
    for await (const event of streamRunEvents({
      url: "https://example.test/api/v1/runs/run-1/events",
      lastEventId: 7,
    })) {
      received.push(event);
    }

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("last_event_id=7");
    expect(new Headers(init?.headers).get("Last-Event-ID")).toBe("7");
    expect(received[0]?.id).toBe(8);
  });
});
