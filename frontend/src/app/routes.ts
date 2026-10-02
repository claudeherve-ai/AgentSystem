/** Central route table for the hash router and nav rail. */
export interface RouteDef {
  path: string;
  label: string;
  description: string;
}

export const ROUTES: RouteDef[] = [
  { path: "/", label: "Command", description: "Compose tasks and see recent activity" },
  { path: "/runs", label: "Run history", description: "Every run and its reproducibility inputs" },
  { path: "/approvals", label: "Approvals", description: "Human-in-the-loop approval inbox" },
  { path: "/artifacts", label: "Artifacts", description: "Files and outputs produced by runs" },
  { path: "/memory", label: "Memory", description: "Continuity and knowledge controls" },
  { path: "/integrations", label: "Integrations", description: "Providers, credentials, and permissions" },
  { path: "/evaluations", label: "Evaluations", description: "Quality, latency, and cost signals" },
  { path: "/operations", label: "Operations", description: "Dependency and system health" },
];

export function matchRoute(segments: string[]): RouteDef {
  if (segments[0] === "runs" && segments[1]) {
    return { path: "/runs/:id", label: "Run detail", description: "Live run detail" };
  }
  const top = segments[0] ? `/${segments[0]}` : "/";
  return ROUTES.find((r) => r.path === top) ?? ROUTES[0]!;
}
