import styles from "./ConnectionBanner.module.css";

interface ConnectionBannerProps {
  offline: boolean;
  degraded?: boolean;
  degradedDetail?: string;
}

/** A persistent, honest banner surfacing offline/degraded connectivity — never silently hidden. */
export function ConnectionBanner({ offline, degraded, degradedDetail }: ConnectionBannerProps) {
  if (!offline && !degraded) return null;

  return (
    <div className={`${styles.banner} ${offline ? styles.offline : styles.degraded}`} role="status">
      {offline ? (
        <span>You are offline. Reconnect to create runs or receive live updates.</span>
      ) : (
        <span>Backend reports a degraded state.{degradedDetail ? ` ${degradedDetail}` : ""}</span>
      )}
    </div>
  );
}
