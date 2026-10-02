import { createLocalStore } from "./localStore";

/**
 * "Workspace" here is an honest, client-side-only organizing concept.
 *
 * The backend currently resolves every run against a hardcoded
 * `workspace_id`/`project_id` of `"default"` (see `api/context.py` /
 * `api/routes/runs.py`) — there is no server-side multi-tenant scoping yet.
 * Rather than fake a backend feature, this store lets an operator group
 * their *own* work locally (e.g. by initiative) while the UI always shows
 * the real `workspace_id`/`project_id` the server actually recorded.
 */
export interface WorkspaceRecord {
  id: string;
  name: string;
  note?: string;
  createdAt: string;
}

export interface WorkspaceState {
  workspaces: WorkspaceRecord[];
  activeWorkspaceId: string;
}

const DEFAULT_WORKSPACE: WorkspaceRecord = {
  id: "local",
  name: "Local workspace",
  note: "Default local grouping — the backend does not yet scope runs by workspace.",
  createdAt: new Date(0).toISOString(),
};

const DEFAULT_STATE: WorkspaceState = {
  workspaces: [DEFAULT_WORKSPACE],
  activeWorkspaceId: DEFAULT_WORKSPACE.id,
};

export const workspaceStore = createLocalStore<WorkspaceState>(
  "agentsystem.ui.workspaces",
  DEFAULT_STATE,
);

export function addWorkspace(name: string, note?: string): WorkspaceRecord {
  const record: WorkspaceRecord = {
    id: `ws-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
    name: name.trim() || "Untitled workspace",
    note,
    createdAt: new Date().toISOString(),
  };
  workspaceStore.set((prev) => ({
    workspaces: [...prev.workspaces, record],
    activeWorkspaceId: record.id,
  }));
  return record;
}

export function setActiveWorkspace(id: string): void {
  workspaceStore.set((prev) =>
    prev.workspaces.some((w) => w.id === id) ? { ...prev, activeWorkspaceId: id } : prev,
  );
}

export function removeWorkspace(id: string): void {
  workspaceStore.set((prev) => {
    if (prev.workspaces.length <= 1) return prev; // always keep at least one
    const workspaces = prev.workspaces.filter((w) => w.id !== id);
    const activeWorkspaceId =
      prev.activeWorkspaceId === id ? workspaces[0]!.id : prev.activeWorkspaceId;
    return { workspaces, activeWorkspaceId };
  });
}
