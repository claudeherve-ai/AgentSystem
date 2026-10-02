import { act, renderHook } from "@testing-library/react";
import { useRunStream } from "../src/hooks/useRunStream";

const mocks = vi.hoisted(() => ({
  streamRunEvents: vi.fn(),
}));

vi.mock("../src/state/ApiProvider", () => ({
  useApi: () => ({
    client: mocks,
  }),
}));

describe("useRunStream", () => {
  it("reconnects after a normal idle close until a terminal event arrives", async () => {
    vi.useFakeTimers();
    mocks.streamRunEvents
      .mockImplementationOnce(async function* () {
        yield { id: 1, type: "run.started", data: {} };
      })
      .mockImplementationOnce(async function* () {
        yield { id: 2, type: "run.completed", data: {} };
      });

    const { result } = renderHook(() => useRunStream("run-1"));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.events).toHaveLength(1);
    expect(result.current.status).toBe("reconnecting");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(750);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.terminal).toBe(true);
    expect(mocks.streamRunEvents).toHaveBeenCalledTimes(2);
    expect(result.current.status).toBe("closed");
    vi.useRealTimers();
  });
});
