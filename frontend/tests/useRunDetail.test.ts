import { act, renderHook, waitFor } from "@testing-library/react";
import type { RunDetail, RunEvent } from "../src/api/types";
import { useRunDetail } from "../src/hooks/useRunDetail";

const mocks = vi.hoisted(() => {
  const getRun = vi.fn();
  return {
    getRun,
    client: { getRun },
    streamEvents: [] as RunEvent[],
  };
});

vi.mock("../src/state/ApiProvider", () => ({
  useApi: () => ({
    client: mocks.client,
  }),
}));

vi.mock("../src/hooks/useRunStream", () => ({
  useRunStream: () => ({
    events: mocks.streamEvents,
    status: "open",
    terminal: mocks.streamEvents.some((event) =>
      ["run.completed", "run.failed", "run.cancelled"].includes(event.type),
    ),
    lastError: null,
    reconnect: vi.fn(),
  }),
}));

const snapshot: RunDetail = {
  id: "run-1",
  status: "running",
  session_id: "session-1",
  workspace_id: "workspace-1",
  project_id: "project-1",
  input: "input",
  output: null,
  selected_agent: null,
  route: null,
  error_code: null,
  usage: {
    prompt_tokens: 0,
    completion_tokens: 0,
    latency_ms: 0,
    cost_usd: 0,
  },
  created_at: null,
  updated_at: null,
  events: [{ id: 1, type: "run.started", data: {} }],
};

describe("useRunDetail", () => {
  it("refetches the authoritative snapshot once after a terminal SSE event", async () => {
    mocks.streamEvents = snapshot.events;
    mocks.getRun.mockResolvedValue(snapshot);
    const { rerender } = renderHook(() => useRunDetail("run-1"));

    await waitFor(() => expect(mocks.getRun).toHaveBeenCalledTimes(1));

    await act(async () => {
      mocks.streamEvents = [
        ...snapshot.events,
        { id: 2, type: "run.completed", data: {} },
      ];
      rerender();
    });

    await waitFor(() => expect(mocks.getRun).toHaveBeenCalledTimes(2));
    rerender();
    await Promise.resolve();
    expect(mocks.getRun).toHaveBeenCalledTimes(2);
  });
});
