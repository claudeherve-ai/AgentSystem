import { useEffect, useState } from "react";

/**
 * Minimal hash-based route reader/navigator.
 *
 * Kept dependency-lean (no router package) since the app only has a
 * handful of top-level views plus one dynamic run-detail segment. Routes
 * look like `#/runs` or `#/runs/<id>`.
 */
export interface HashRoute {
  path: string;
  segments: string[];
}

function readHash(): HashRoute {
  const raw = typeof window === "undefined" ? "" : window.location.hash;
  const path = raw.startsWith("#") ? raw.slice(1) : raw;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const segments = normalized.split("/").filter(Boolean);
  return { path: normalized === "/" || normalized === "" ? "/" : normalized, segments };
}

export function navigate(path: string): void {
  const target = path.startsWith("/") ? path : `/${path}`;
  window.location.hash = target;
}

export function useHashRoute(): HashRoute {
  const [route, setRoute] = useState<HashRoute>(() => readHash());

  useEffect(() => {
    const onChange = () => setRoute(readHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}
