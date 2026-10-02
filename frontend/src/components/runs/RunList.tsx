import { StatusPill } from "../common/StatusPill";
import { navigate } from "../../hooks/useHashRoute";
import type { RunSummary } from "../../api/types";
import styles from "./RunList.module.css";

interface RunListProps {
  runs: RunSummary[];
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

/** A compact, reusable table of runs used by the Command and Run History views. */
export function RunList({ runs }: RunListProps) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">Run</th>
          <th scope="col">Status</th>
          <th scope="col">Agent</th>
          <th scope="col">Session</th>
          <th scope="col">Created</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr key={run.id}>
            <td>
              <a
                href={`#/runs/${run.id}`}
                className={styles.link}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(`/runs/${run.id}`);
                }}
              >
                {run.input ? run.input.slice(0, 72) : run.id}
              </a>
            </td>
            <td>
              <StatusPill label={run.status} status={run.status} />
            </td>
            <td>{run.selected_agent ?? "—"}</td>
            <td className={styles.mono}>{run.session_id ?? "—"}</td>
            <td>{formatTimestamp(run.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
