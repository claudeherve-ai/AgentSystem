import type { ReactNode } from "react";
import styles from "./Panel.module.css";

interface PanelProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  as?: "section" | "div";
}

/** A consistent card/panel wrapper used across every functional view. */
export function Panel({ title, description, actions, children, as = "section" }: PanelProps) {
  const Tag = as;
  return (
    <Tag className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>{title}</h2>
          {description ? <p className={styles.description}>{description}</p> : null}
        </div>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </div>
      <div className={styles.content}>{children}</div>
    </Tag>
  );
}
