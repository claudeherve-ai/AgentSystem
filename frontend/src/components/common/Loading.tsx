import styles from "./Loading.module.css";

interface LoadingProps {
  label?: string;
  rows?: number;
}

/** A themed skeleton/loading placeholder; announces itself once via aria-live polite. */
export function Loading({ label = "Loading…", rows = 3 }: LoadingProps) {
  return (
    <div className={styles.wrapper} aria-live="polite" aria-busy="true">
      <span className="visually-hidden">{label}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={styles.bar} style={{ width: `${88 - i * 14}%` }} />
      ))}
    </div>
  );
}
