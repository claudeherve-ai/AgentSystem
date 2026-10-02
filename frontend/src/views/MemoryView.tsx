import { Panel } from "../components/common/Panel";
import { EmptyState } from "../components/common/EmptyState";

/** Memory & continuity controls are not exposed by the current backend API surface. */
export function MemoryView() {
  return (
    <Panel
      title="Memory & continuity"
      description="Controls for long-term memory, knowledge retention, and cross-session continuity."
    >
      <EmptyState
        title="Memory controls are not configured"
        description="The backend does not currently expose an endpoint for inspecting or managing agent memory or knowledge stores. Session continuity today is limited to the session_id you supply when composing a task."
        notConfigured
      />
    </Panel>
  );
}
