import { useHashRoute } from "./hooks/useHashRoute";
import { AppShell } from "./components/layout/AppShell";
import { CommandView } from "./views/CommandView";
import { RunHistoryView } from "./views/RunHistoryView";
import { RunDetailView } from "./views/RunDetailView";
import { ApprovalsView } from "./views/ApprovalsView";
import { ArtifactsView } from "./views/ArtifactsView";
import { MemoryView } from "./views/MemoryView";
import { IntegrationsView } from "./views/IntegrationsView";
import { EvaluationsView } from "./views/EvaluationsView";
import { OperationsView } from "./views/OperationsView";

export function App() {
  const route = useHashRoute();

  return <AppShell>{renderRoute(route.segments)}</AppShell>;
}

function renderRoute(segments: string[]) {
  if (segments[0] === "runs" && segments[1]) {
    return <RunDetailView runId={decodeURIComponent(segments[1])} />;
  }

  switch (segments[0] ?? "") {
    case "":
      return <CommandView />;
    case "runs":
      return <RunHistoryView />;
    case "approvals":
      return <ApprovalsView />;
    case "artifacts":
      return <ArtifactsView />;
    case "memory":
      return <MemoryView />;
    case "integrations":
      return <IntegrationsView />;
    case "evaluations":
      return <EvaluationsView />;
    case "operations":
      return <OperationsView />;
    default:
      return <CommandView />;
  }
}
