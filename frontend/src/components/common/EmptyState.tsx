import type { ReactNode } from "react";
import styles from "./EmptyState.module.css";

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  /** Marks this as an honest "capability not available yet" state rather than merely "no data yet". */
  notConfigured?: boolean;
}

/** Honest empty/not-configured placeholder — never renders fabricated sample data. */
export function EmptyState({ title, description, action, notConfigured }: EmptyStateProps) {
  return (
    <div className={styles.wrapper} role="status">
      <p className={styles.badge}>{notConfigured ? "Not configured" : "Nothing here yet"}</p>
      <h3 className={styles.title}>{title}</h3>
      {description ? <p className={styles.description}>{description}</p> : null}
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}
