import { useState } from "react";
import { useLocalStore } from "../../hooks/useLocalStore";
import { workspaceStore, addWorkspace, setActiveWorkspace } from "../../state/workspaceStore";
import styles from "./WorkspaceSwitcher.module.css";

/**
 * Local-only workspace/project switcher. Grouping is a client-side
 * convenience — see `workspaceStore.ts` — the server does not yet scope
 * runs by workspace, so this never claims otherwise.
 */
export function WorkspaceSwitcher() {
  const state = useLocalStore(workspaceStore);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    addWorkspace(name);
    setName("");
    setCreating(false);
  };

  return (
    <div className={styles.wrapper}>
      <label className="visually-hidden" htmlFor="workspace-select">
        Active workspace
      </label>
      <select
        id="workspace-select"
        className={styles.select}
        value={state.activeWorkspaceId}
        onChange={(e) => setActiveWorkspace(e.target.value)}
      >
        {state.workspaces.map((ws) => (
          <option key={ws.id} value={ws.id}>
            {ws.name}
          </option>
        ))}
      </select>
      {creating ? (
        <form className={styles.createForm} onSubmit={handleCreate}>
          <input
            autoFocus
            className={styles.input}
            aria-label="New workspace name"
            placeholder="Workspace name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => !name && setCreating(false)}
          />
          <button type="submit" className={styles.addButton}>
            Add
          </button>
        </form>
      ) : (
        <button type="button" className={styles.newButton} onClick={() => setCreating(true)}>
          + New
        </button>
      )}
    </div>
  );
}
