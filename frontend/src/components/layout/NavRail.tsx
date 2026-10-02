import { ROUTES } from "../../app/routes";
import { navigate } from "../../hooks/useHashRoute";
import styles from "./NavRail.module.css";

interface NavRailProps {
  activePath: string;
  collapsed?: boolean;
}

/** Primary navigation landmark: the left-hand rail of the mission-control shell. */
export function NavRail({ activePath, collapsed }: NavRailProps) {
  return (
    <nav className={`${styles.rail} ${collapsed ? styles.collapsed : ""}`} aria-label="Primary">
      <ul className={styles.list}>
        {ROUTES.map((route) => {
          const isActive = activePath === route.path || (route.path === "/runs" && activePath.startsWith("/runs"));
          return (
            <li key={route.path}>
              <a
                href={`#${route.path}`}
                className={`${styles.link} ${isActive ? styles.active : ""}`}
                aria-current={isActive ? "page" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(route.path);
                }}
                title={route.description}
              >
                <span className={styles.label}>{route.label}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
