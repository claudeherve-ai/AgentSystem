import styles from "./StatusPill.module.css";

export type PillTone = "neutral" | "info" | "positive" | "caution" | "danger";

const STATUS_TONE: Record<string, PillTone> = {
  pending: "neutral",
  queued: "neutral",
  running: "info",
  active: "info",
  completed: "positive",
  done: "positive",
  approved: "positive",
  healthy: "positive",
  blocked: "caution",
  awaiting_approval: "caution",
  degraded: "caution",
  failed: "danger",
  rejected: "danger",
  cancelled: "neutral",
  expired: "danger",
  unhealthy: "danger",
};

export function toneForStatus(status: string): PillTone {
  return STATUS_TONE[status.toLowerCase()] ?? "neutral";
}

interface StatusPillProps {
  label: string;
  tone?: PillTone;
  status?: string;
}

/** A small labeled state indicator; tone can be given explicitly or derived from `status`. */
export function StatusPill({ label, tone, status }: StatusPillProps) {
  const resolvedTone = tone ?? (status ? toneForStatus(status) : "neutral");
  return <span className={`${styles.pill} ${styles[resolvedTone]}`}>{label}</span>;
}
