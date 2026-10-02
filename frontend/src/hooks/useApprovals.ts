import { useCallback, useEffect, useState } from "react";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import type { Approval } from "../api/types";

export interface UseApprovalsResult {
  approvals: Approval[];
  loading: boolean;
  error: ApiError | null;
  refresh: () => void;
  decide: (id: string, decision: "approve" | "reject", feedback?: string) => Promise<void>;
  decidingId: string | null;
  decideError: ApiError | null;
}

/** Lists approvals (optionally filtered by status) and exposes approve/reject actions. */
export function useApprovals(status?: string): UseApprovalsResult {
  const { client } = useApi();
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [nonce, setNonce] = useState(0);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [decideError, setDecideError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    client
      .listApprovals(status)
      .then((res) => {
        if (!cancelled) setApprovals(res.approvals);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError(0, { code: "network_error", message: "Failed to load approvals" }),
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, status, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  const decide = useCallback(
    async (id: string, decision: "approve" | "reject", feedback?: string) => {
      setDecidingId(id);
      setDecideError(null);
      try {
        const updated =
          decision === "approve"
            ? await client.approveApproval(id, { feedback })
            : await client.rejectApproval(id, { feedback });
        setApprovals((prev) => prev.map((a) => (a.id === id ? updated : a)));
      } catch (cause) {
        setDecideError(
          cause instanceof ApiError
            ? cause
            : new ApiError(0, { code: "network_error", message: "Failed to record decision" }),
        );
        throw cause;
      } finally {
        setDecidingId(null);
      }
    },
    [client],
  );

  return { approvals, loading, error, refresh, decide, decidingId, decideError };
}
