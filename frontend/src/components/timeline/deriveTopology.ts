import type { RunEvent } from "../../api/types";

/**
 * Derives a planner → agent → tool → approval → artifact → output graph from
 * the real run-event stream.
 *
 * This is intentionally a pure function of `RunEvent[]` (no timers, no
 * randomness) so it's fully unit-testable and so the live `RunTopology`
 * component can be re-derived on every event without any hidden state. It
 * only reads fields the backend actually emits (see
 * `agentsystem/services/run_service.py`) — it never fabricates a tool name,
 * timestamp, or step that isn't present in the event payload.
 */

export type TopologyNodeKind =
  | "planner"
  | "agent"
  | "tool"
  | "approval"
  | "artifact"
  | "output";

export type TopologyStatus =
  | "pending"
  | "active"
  | "done"
  | "blocked"
  | "failed"
  | "cancelled";

export interface TopologyNode {
  id: string;
  kind: TopologyNodeKind;
  label: string;
  detail?: string;
  status: TopologyStatus;
  eventIds: number[];
  sequence: number;
}

export interface TopologyEdge {
  from: string;
  to: string;
}

export type TopologyRunStatus =
  | "idle"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface TopologyModel {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  runStatus: TopologyRunStatus;
  /** Full final response text, if `message.delta` has arrived. */
  outputText: string | null;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

export function deriveTopology(events: RunEvent[]): TopologyModel {
  const nodesById = new Map<string, TopologyNode>();
  const edges: TopologyEdge[] = [];
  const edgeKeys = new Set<string>();
  let runStatus: TopologyRunStatus = "idle";
  let outputText: string | null = null;
  let lastNodeId: string | null = null;
  let lastAgentNodeId: string | null = null;
  let sequence = 0;
  const seenEventIds = new Set<number>();
  const activeToolByAgent = new Map<string, string[]>(); // agent -> stack of active tool node ids

  const addNode = (
    id: string,
    kind: TopologyNodeKind,
    label: string,
    status: TopologyStatus,
    eventId: number,
    detail?: string,
  ): TopologyNode => {
    const existing = nodesById.get(id);
    if (existing) {
      existing.eventIds.push(eventId);
      return existing;
    }
    const node: TopologyNode = {
      id,
      kind,
      label,
      detail,
      status,
      eventIds: [eventId],
      sequence: sequence++,
    };
    nodesById.set(id, node);
    return node;
  };

  const linkFrom = (fromId: string | null, toId: string): void => {
    if (!fromId || fromId === toId) return;
    const key = `${fromId}->${toId}`;
    if (edgeKeys.has(key)) return;
    edgeKeys.add(key);
    edges.push({ from: fromId, to: toId });
  };

  const sorted = [...events].sort((a, b) => a.id - b.id);

  for (const evt of sorted) {
    if (seenEventIds.has(evt.id)) continue;
    seenEventIds.add(evt.id);
    const data = (evt.data ?? {}) as Record<string, unknown>;

    switch (evt.type) {
      case "run.started": {
        runStatus = "running";
        const planner = addNode("planner", "planner", "Planner", "active", evt.id);
        lastNodeId = planner.id;
        break;
      }
      case "plan.updated": {
        const phase = asString(data.phase);
        const steps = Array.isArray(data.steps) ? (data.steps as unknown[]) : undefined;
        const detail =
          [phase ? `Phase: ${phase}` : undefined, steps ? `Steps: ${steps.join(" → ")}` : undefined]
            .filter(Boolean)
            .join(" · ") || undefined;
        const planner = addNode("planner", "planner", "Planner", "active", evt.id, detail);
        planner.detail = detail ?? planner.detail;
        lastNodeId = planner.id;
        break;
      }
      case "agent.selected": {
        const agent = asString(data.agent) ?? "agent";
        const agentsUsed = Array.isArray(data.agents_used)
          ? (data.agents_used as unknown[]).filter((v): v is string => typeof v === "string")
          : [];
        const id = `agent:${agent}`;
        const detail = agentsUsed.length ? `Used: ${agentsUsed.join(", ")}` : undefined;
        const node = addNode(id, "agent", agent, "active", evt.id, detail);
        const planner = nodesById.get("planner");
        if (planner) {
          planner.status = "done";
          linkFrom(planner.id, node.id);
        }
        lastNodeId = node.id;
        lastAgentNodeId = node.id;
        break;
      }
      case "tool.started": {
        const agent = asString(data.agent) ?? "tool";
        const stack = activeToolByAgent.get(agent) ?? [];
        const id = `tool:${agent}:${stack.length}:${evt.id}`;
        const node = addNode(id, "tool", agent, "active", evt.id, "Invoked as a tool call");
        const parent = lastAgentNodeId ?? lastNodeId;
        linkFrom(parent, node.id);
        stack.push(node.id);
        activeToolByAgent.set(agent, stack);
        lastNodeId = node.id;
        break;
      }
      case "tool.completed": {
        const agent = asString(data.agent) ?? "tool";
        const stack = activeToolByAgent.get(agent);
        const nodeId = stack?.pop();
        if (nodeId) {
          const node = nodesById.get(nodeId);
          if (node) {
            node.status = "done";
            node.eventIds.push(evt.id);
          }
          lastNodeId = nodeId;
        }
        break;
      }
      case "approval.requested": {
        const approvalId = asString(data.approval_id) ?? `approval-${evt.id}`;
        const action = asString(data.action);
        const id = `approval:${approvalId}`;
        const node = addNode(id, "approval", action ?? "Approval requested", "blocked", evt.id);
        linkFrom(lastNodeId, node.id);
        lastNodeId = node.id;
        break;
      }
      case "approval.decided": {
        const approvalId = asString(data.approval_id);
        const approved = data.approved === true;
        const id = approvalId ? `approval:${approvalId}` : null;
        const node = id ? nodesById.get(id) : undefined;
        if (node) {
          node.status = approved ? "done" : "failed";
          node.detail = approved ? "Approved" : "Rejected";
          node.eventIds.push(evt.id);
          lastNodeId = node.id;
        }
        break;
      }
      case "artifact.created": {
        const artifactId = asString(data.artifact_id) ?? `artifact-${evt.id}`;
        const name = asString(data.name) ?? "Artifact";
        const id = `artifact:${artifactId}`;
        const node = addNode(id, "artifact", name, "done", evt.id);
        linkFrom(lastNodeId, node.id);
        lastNodeId = node.id;
        break;
      }
      case "message.delta": {
        const text = asString(data.text);
        if (text != null) outputText = text;
        break;
      }
      case "message.completed": {
        break;
      }
      case "run.completed": {
        runStatus = "completed";
        const agent = asString(data.agent);
        const length = typeof data.length === "number" ? data.length : undefined;
        const node = addNode(
          "output",
          "output",
          "Response delivered",
          "done",
          evt.id,
          [agent ? `Agent: ${agent}` : undefined, length != null ? `${length} chars` : undefined]
            .filter(Boolean)
            .join(" · ") || undefined,
        );
        linkFrom(lastNodeId, node.id);
        lastNodeId = node.id;
        break;
      }
      case "run.failed": {
        runStatus = "failed";
        const errorCode = asString(data.error_code);
        const node = addNode(
          "output",
          "output",
          "Run failed",
          "failed",
          evt.id,
          errorCode ? `Error: ${errorCode}` : undefined,
        );
        linkFrom(lastNodeId, node.id);
        lastNodeId = node.id;
        break;
      }
      case "run.cancelled": {
        runStatus = "cancelled";
        const node = addNode("output", "output", "Run cancelled", "cancelled", evt.id);
        linkFrom(lastNodeId, node.id);
        lastNodeId = node.id;
        break;
      }
      default:
        // Unknown/future event type — ignored by the topology view but not
        // an error; the raw transcript view still shows it.
        break;
    }
  }

  const nodes = Array.from(nodesById.values()).sort((a, b) => a.sequence - b.sequence);
  return { nodes, edges, runStatus, outputText };
}
