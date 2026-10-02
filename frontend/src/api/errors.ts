/**
 * Error envelope parsing for the AgentSystem API.
 *
 * Every non-2xx response from the backend renders as
 * `{"error": {"code", "message", "request_id", "details"?}}`
 * (see `agentsystem/errors.py`). `ApiError` normalizes that shape — and the
 * rare case where the body isn't JSON at all (proxy errors, dev-server
 * failures) — into one predictable, typed error the UI can branch on.
 */

export type ApiErrorCode =
  | "validation_error"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "rate_limited"
  | "dependency_unavailable"
  | "sandbox_unavailable"
  | "provider_unavailable"
  | "internal_error"
  | "network_error"
  | "parse_error"
  | (string & {});

export interface ApiErrorBody {
  code: ApiErrorCode;
  message: string;
  request_id?: string;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  readonly requestId?: string;
  readonly details?: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.requestId = body.request_id;
    this.details = body.details;
  }

  /** True for the class of errors a retry button should recover from. */
  get isRetryable(): boolean {
    return (
      this.status === 429 ||
      this.status === 503 ||
      this.status === 504 ||
      this.code === "network_error"
    );
  }

  get isUnauthorized(): boolean {
    return this.status === 401 || this.code === "unauthorized";
  }

  get isForbidden(): boolean {
    return this.status === 403 || this.code === "forbidden";
  }
}

/** Parses a fetch Response body into an ApiError, tolerating non-JSON bodies. */
export async function toApiError(response: Response): Promise<ApiError> {
  const fallback: ApiErrorBody = {
    code: response.status === 401 ? "unauthorized" : "internal_error",
    message: `Request failed with status ${response.status}`,
  };

  let text: string;
  try {
    text = await response.text();
  } catch {
    return new ApiError(response.status, fallback);
  }

  if (!text) {
    return new ApiError(response.status, fallback);
  }

  try {
    const parsed = JSON.parse(text) as { error?: Partial<ApiErrorBody> };
    if (parsed && typeof parsed === "object" && parsed.error) {
      const { code, message, request_id, details } = parsed.error;
      return new ApiError(response.status, {
        code: code ?? fallback.code,
        message: message ?? fallback.message,
        request_id,
        details,
      });
    }
  } catch {
    // Body wasn't the expected JSON error envelope; fall through.
  }

  return new ApiError(response.status, {
    ...fallback,
    message: text.slice(0, 300) || fallback.message,
  });
}

export function networkApiError(cause: unknown): ApiError {
  const message =
    cause instanceof Error ? cause.message : "Network request failed";
  return new ApiError(0, { code: "network_error", message });
}
