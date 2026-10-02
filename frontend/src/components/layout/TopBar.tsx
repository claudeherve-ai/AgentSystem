import { useHealth } from "../../hooks/useHealth";
import { useOnlineStatus } from "../../hooks/useOnlineStatus";
import { StatusPill, type PillTone } from "../common/StatusPill";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";
import styles from "./TopBar.module.css";

/** Top application bar: brand, workspace switcher, and a live system-health indicator. */
export function TopBar() {
  const { report, loading } = useHealth();
  const online = useOnlineStatus();

  const healthLabel = !online
    ? "Offline"
    : loading && !report
      ? "Checking…"
      : report
        ? report.ready
          ? "Operational"
          : "Degraded"
        : "Unknown";

  const healthTone: PillTone = !online ? "danger" : report ? (report.ready ? "positive" : "caution") : "neutral";

  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <span className={styles.mark} aria-hidden="true" />
        <span className={styles.wordmark}>AgentSystem</span>
        <span className={styles.subtitle}>Mission Control</span>
      </div>
      <div className={styles.actions}>
        <WorkspaceSwitcher />
        <div aria-live="polite" className={styles.health}>
          <StatusPill label={healthLabel} tone={healthTone} />
        </div>
      </div>
    </header>
  );
}
