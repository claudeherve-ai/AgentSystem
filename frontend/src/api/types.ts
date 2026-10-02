/**
 * Wire types for the AgentSystem API (`/api/v1/*`, `/health/*`).
 *
 * These mirror the FastAPI response shapes in `api/routes/*.py` exactly —
 * fields the backend can legitimately omit are optional/nullable here too,
 * so the UI never has to guess at data the server didn't send.
 */

export type RunStatus =
  | "pending"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface RunUsage {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  latency_ms: number | null;
  cost_usd: number | null;
}

export interface RunSummary {
  id: string;
  status: string;
  session_id: string | null;
  workspace_id: string | null;
  project_id: string | null;
  input: string | null;
  output: string | null;
  selected_agent: string | null;
  route: string | null;
  error_code: string | null;
  usage: RunUsage;
  created_at: string | null;
  updated_at: string | null;
}

/** Canonical run-event vocabulary emitted by `agentsystem/services/run_service.py`. */
export type RunEventType =
  | "run.started"
  | "plan.updated"
  | "agent.selected"
  | "tool.started"
  | "tool.completed"
  | "approval.requested"
  | "approval.decided"
  | "artifact.created"
  | "message.delta"
  | "message.completed"
  | "run.completed"
  | "run.failed"
  | "run.cancelled"
  | (string & {});

export interface RunEvent {
  id: number;
  type: RunEventType;
  data: Record<string, unknown>;
}

export interface RunDetail extends RunSummary {
  events: RunEvent[];
}

export interface RunListResponse {
  runs: RunSummary[];
  count: number;
}

export interface CreateRunRequest {
  message: string;
  session_id?: string;
  preferred_agent?: string;
  idempotency_key?: string;
}

export interface AgentInfo {
  name: string;
  description: string | null;
  registered: boolean;
}

export interface AgentTool {
  name: string;
  description?: string;
}

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "expired"
  | "cancelled";

export interface Approval {
  id: string;
  agent_name: string;
  action: string;
  details: string;
  status: ApprovalStatus | string;
  feedback: string;
  requested_at: string;
  decided_at: string | null;
  decided_by: string | null;
  expires_at: string | null;
}

export interface ApprovalListResponse {
  approvals: Approval[];
  count: number;
}

export interface HealthDependency {
  healthy: boolean;
  required: boolean;
  detail: string;
}

export interface HealthReport {
  ready: boolean;
  status: string;
  dependencies: Record<string, HealthDependency>;
}

export interface ModelProfileStatus {
  name: string;
  defined: boolean;
  provider: string;
  model: string;
  tier?: string;
  cost_per_1k_input?: number | null;
  cost_per_1k_output?: number | null;
  buildable: boolean;
  available: boolean;
  fallback: string[];
  resolvable: boolean;
  resolves_to?: string | null;
}

export interface ModelsDescribe {
  default_profile: string;
  buildable_providers: string[];
  credentials: Record<string, boolean>;
  policy: Record<string, string>;
  warnings: string[];
  profiles: Record<string, ModelProfileStatus>;
}

export interface ObservabilityStats {
  [key: string]: unknown;
}

export interface ObservabilitySpan {
  [key: string]: unknown;
}

export interface ObservabilityTraces {
  count: number;
  limit: number;
  spans: ObservabilitySpan[];
}
