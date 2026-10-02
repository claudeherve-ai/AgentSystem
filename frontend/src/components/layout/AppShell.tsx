import type { ReactNode } from "react";
import { useHashRoute } from "../../hooks/useHashRoute";
import { useOnlineStatus } from "../../hooks/useOnlineStatus";
import { useHealth } from "../../hooks/useHealth";
import { TopBar } from "./TopBar";
import { NavRail } from "./NavRail";
import { ConnectionBanner } from "./ConnectionBanner";
import { matchRoute } from "../../app/routes";
import styles from "./AppShell.module.css";

interface AppShellProps {
  children: ReactNode;
}

/**
 * Application shell: skip link, header/nav/main landmarks, connection
 * banner, and the primary responsive grid (rail + content) used by every
 * view.
 */
export function AppShell({ children }: AppShellProps) {
  const route = useHashRoute();
  const online = useOnlineStatus();
  const { report } = useHealth();
  const active = matchRoute(route.segments);

  return (
    <div className={styles.shell}>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <TopBar />
      <ConnectionBanner
        offline={!online}
        degraded={online && report ? !report.ready : false}
        degradedDetail={report?.status}
      />
      <div className={styles.body}>
        <NavRail activePath={active.path === "/runs/:id" ? "/runs" : route.path} />
        <main id="main-content" className={styles.main} tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
