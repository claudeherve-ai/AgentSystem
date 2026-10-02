import { useId, useState } from "react";
import { useApi } from "../../state/ApiProvider";
import { useLocalStore } from "../../hooks/useLocalStore";
import { preferencesStore } from "../../state/preferencesStore";
import { useAgents } from "../../hooks/useAgents";
import { navigate } from "../../hooks/useHashRoute";
import { ApiError } from "../../api/errors";
import type { RunSummary } from "../../api/types";
import styles from "./TaskComposer.module.css";

interface TaskComposerProps {
  onCreated?: (run: RunSummary) => void;
}

/**
 * Outcome-focused task composer. The operator describes what they want
 * done; routing is automatic by default, or they can pin a specific
 * registered agent. Submitting calls `POST /api/v1/runs` directly (there is
 * no dedicated hook for a one-shot mutation) and navigates to the new run's
 * live detail view on success.
 */
export function TaskComposer({ onCreated }: TaskComposerProps) {
  const { client } = useApi();
  const prefs = useLocalStore(preferencesStore);
  const { agents, loading: agentsLoading } = useAgents();
  const [message, setMessage] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [preferredAgent, setPreferredAgent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const messageId = useId();
  const sessionIdInputId = useId();
  const agentSelectId = useId();

  const mode = prefs.composerMode;
  const setMode = (next: "auto" | "specific") =>
    preferencesStore.set((prev) => ({ ...prev, composerMode: next }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const run = await client.createRun({
        message: message.trim(),
        session_id: sessionId.trim() || undefined,
        preferred_agent: mode === "specific" && preferredAgent ? preferredAgent : undefined,
      });
      setMessage("");
      onCreated?.(run);
      navigate(`/runs/${run.id}`);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError(0, { code: "network_error", message: "Failed to create run" }),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.field}>
        <label htmlFor={messageId} className={styles.label}>
          Describe the outcome you want
        </label>
        <textarea
          id={messageId}
          className={styles.textarea}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="e.g. Summarize last week's incident reports and flag any recurring root causes"
          rows={4}
          required
        />
      </div>

      <div className={styles.row}>
        <fieldset className={styles.modeGroup}>
          <legend className={styles.legend}>Routing</legend>
          <div className={styles.modeToggle}>
            <button
              type="button"
              className={`${styles.modeButton} ${mode === "auto" ? styles.modeActive : ""}`}
              aria-pressed={mode === "auto"}
              onClick={() => setMode("auto")}
            >
              Automatic
            </button>
            <button
              type="button"
              className={`${styles.modeButton} ${mode === "specific" ? styles.modeActive : ""}`}
              aria-pressed={mode === "specific"}
              onClick={() => setMode("specific")}
            >
              Specific agent
            </button>
          </div>
        </fieldset>

        {mode === "specific" ? (
          <div className={styles.field}>
            <label htmlFor={agentSelectId} className={styles.label}>
              Agent
            </label>
            <select
              id={agentSelectId}
              className={styles.select}
              value={preferredAgent}
              onChange={(e) => setPreferredAgent(e.target.value)}
              disabled={agentsLoading}
            >
              <option value="">Choose an agent…</option>
              {agents.map((agent) => (
                <option key={agent.name} value={agent.name} disabled={!agent.registered}>
                  {agent.name}
                  {agent.registered ? "" : " (unavailable)"}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className={styles.field}>
          <label htmlFor={sessionIdInputId} className={styles.label}>
            Session ID <span className={styles.optional}>(optional, for continuity)</span>
          </label>
          <input
            id={sessionIdInputId}
            className={styles.input}
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Leave blank to start a new session"
          />
        </div>
      </div>

      {error ? (
        <p className={styles.error} role="alert">
          {error.message}
        </p>
      ) : null}

      <div className={styles.actions}>
        <button type="submit" className={styles.submit} disabled={submitting || !message.trim()}>
          {submitting ? "Dispatching…" : "Dispatch task"}
        </button>
      </div>
    </form>
  );
}
