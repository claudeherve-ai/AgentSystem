import { useEffect, useState } from "react";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import type { AgentInfo } from "../api/types";

export interface UseAgentsResult {
  agents: AgentInfo[];
  loading: boolean;
  error: ApiError | null;
}

/** Lists registered agents from the `/agents` compatibility route. */
export function useAgents(): UseAgentsResult {
  const { client } = useApi();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .listAgents()
      .then((res) => {
        if (!cancelled) setAgents(res.agents);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError(0, { code: "network_error", message: "Failed to load agents" }),
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  return { agents, loading, error };
}
