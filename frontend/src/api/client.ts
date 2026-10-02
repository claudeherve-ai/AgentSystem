/**
 * Typed fetch client for the AgentSystem API.
 *
 * Every method maps 1:1 to a real backend route (see `api/routes/*.py`).
 * There is no mocked/stubbed backend behind this client — if a route
 * doesn't exist yet (artifacts listing, memory config, integrations), that
 * capability is simply absent from this client, and calling code is
 * expected to derive an honest view from the routes that *do* exist.
 */
import { toApiError, networkApiError, ApiError } from "./errors";
import { streamRunEvents, type RunStreamEvent } from "./sse";
import type { AuthProvider } from "./auth/authProvider";
import type {
  AgentInfo,
  Approval,
  ApprovalListResponse,
  CreateRunRequest,
  HealthReport,
  ModelsDescribe,
  ObservabilityStats,
  ObservabilityTraces,
  RunDetail,
  RunListResponse,
  RunSummary,
} from "./types";

export interface ApiClientOptions {
  baseUrl: string;
  authProvider: AuthProvider;
}

export interface ListRunsParams {
  sessionId?: string;
  status?: string;
  limit?: number;
}

export interface StreamRunOptions {
  lastEventId?: number | null;
  signal?: AbortSignal;
}

export class ApiClient {
  private baseUrl: string;
  private authProvider: AuthProvider;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.authProvider = options.authProvider;
  }

  setAuthProvider(provider: AuthProvider): void {
    this.authProvider = provider;
  }

  // ---- Runs ---------------------------------------------------------

  async listRuns(params: ListRunsParams = {}): Promise<RunListResponse> {
    const query = new URLSearchParams();
    if (params.sessionId) query.set("session_id", params.sessionId);
    if (params.status) query.set("status", params.status);
    if (params.limit != null) query.set("limit", String(params.limit));
    const qs = query.toString();
    return this.request<RunListResponse>(`/api/v1/runs${qs ? `?${qs}` : ""}`);
  }

  async createRun(body: CreateRunRequest): Promise<RunSummary> {
    return this.request<RunSummary>("/api/v1/runs", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async getRun(id: string): Promise<RunDetail> {
    return this.request<RunDetail>(`/api/v1/runs/${encodeURIComponent(id)}`);
  }

  async cancelRun(id: string): Promise<RunSummary> {
    return this.request<RunSummary>(
      `/api/v1/runs/${encodeURIComponent(id)}/cancel`,
      { method: "POST" },
    );
  }

  /** Streams parsed run events, honoring Last-Event-ID resumption. */
  streamRunEvents(
    id: string,
    options: StreamRunOptions = {},
  ): AsyncGenerator<RunStreamEvent, void, void> {
    const context$ = this.authProvider.getRequestContext();
    return this.deferredStream(
      `${this.baseUrl}/api/v1/runs/${encodeURIComponent(id)}/events`,
      context$,
      options,
    );
  }

  private async *deferredStream(
    url: string,
    contextPromise: ReturnType<AuthProvider["getRequestContext"]>,
    options: StreamRunOptions,
  ): AsyncGenerator<RunStreamEvent, void, void> {
    const context = await contextPromise;
    yield* streamRunEvents({
      url,
      headers: context.headers,
      credentials: context.credentials,
      lastEventId: options.lastEventId,
      signal: options.signal,
    });
  }

  // ---- Agents ---------------------------------------------------------

  async listAgents(): Promise<{ agents: AgentInfo[]; count: number }> {
    return this.request(`/api/v1/agents`);
  }

  // ---- Approvals ---------------------------------------------------------

  async listApprovals(status?: string): Promise<ApprovalListResponse> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request(`/api/v1/approvals${qs}`);
  }

  async getApproval(id: string): Promise<Approval> {
    return this.request(`/api/v1/approvals/${encodeURIComponent(id)}`);
  }

  async approveApproval(
    id: string,
    body: { feedback?: string } = {},
  ): Promise<Approval> {
    return this.request(`/api/v1/approvals/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async rejectApproval(
    id: string,
    body: { feedback?: string } = {},
  ): Promise<Approval> {
    return this.request(`/api/v1/approvals/${encodeURIComponent(id)}/reject`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  // ---- Models / Health / Observability ------------------------------

  async getModelsDescribe(): Promise<ModelsDescribe> {
    return this.request(`/api/v1/models`);
  }

  async getHealthReady(): Promise<HealthReport> {
    return this.request(`/health/ready`, {}, { allowDegraded: true });
  }

  async getObservabilityStats(): Promise<ObservabilityStats> {
    return this.request(`/api/v1/observability/stats`);
  }

  async getObservabilityTraces(limit = 50): Promise<ObservabilityTraces> {
    return this.request(`/api/v1/observability/traces?limit=${limit}`);
  }

  // ---- core request -----------------------------------------------------

  private async request<T>(
    path: string,
    init: RequestInit = {},
    opts: { allowDegraded?: boolean } = {},
  ): Promise<T> {
    let context;
    try {
      context = await this.authProvider.getRequestContext();
    } catch (cause) {
      throw networkApiError(cause);
    }

    const headers: Record<string, string> = {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...context.headers,
      ...(init.headers as Record<string, string> | undefined),
    };

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers,
        credentials: context.credentials ?? init.credentials,
      });
    } catch (cause) {
      throw networkApiError(cause);
    }

    // `/health/ready` legitimately returns 503 for a *degraded* (not
    // erroring) system — the body is still the real report, just render it.
    if (!response.ok && !(opts.allowDegraded && response.status === 503)) {
      throw await toApiError(response);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    try {
      return (await response.json()) as T;
    } catch (cause) {
      throw new ApiError(response.status, {
        code: "parse_error",
        message: cause instanceof Error ? cause.message : "Failed to parse response",
      });
    }
  }
}
