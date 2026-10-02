import { ApiClient } from "../src/api/client";
import { NoAuthProvider } from "../src/api/auth/authProvider";

describe("ApiClient", () => {
  it("creates runs with the versioned API contract", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ id: "run_1", status: "pending", events: [] }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = new ApiClient({
      baseUrl: "https://example.test/",
      authProvider: new NoAuthProvider(),
    });

    await client.createRun({ message: "Design a service" });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/api/v1/runs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "Design a service" }),
      }),
    );
  });

  it("returns a degraded readiness report from a 503 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          ready: false,
          status: "degraded",
          dependencies: {},
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = new ApiClient({
      baseUrl: "https://example.test",
      authProvider: new NoAuthProvider(),
    });

    await expect(client.getHealthReady()).resolves.toMatchObject({
      ready: false,
      status: "degraded",
    });
  });

  it("requests cooperative run cancellation", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "run_1", status: "running" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = new ApiClient({
      baseUrl: "https://example.test",
      authProvider: new NoAuthProvider(),
    });

    await client.cancelRun("run_1");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/api/v1/runs/run_1/cancel",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("surfaces structured authorization failures", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "forbidden",
            message: "approval role required",
            request_id: "req_1",
          },
        }),
        { status: 403, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = new ApiClient({
      baseUrl: "https://example.test",
      authProvider: new NoAuthProvider(),
    });

    await expect(client.listApprovals()).rejects.toMatchObject({
      status: 403,
      code: "forbidden",
    });
  });
});
