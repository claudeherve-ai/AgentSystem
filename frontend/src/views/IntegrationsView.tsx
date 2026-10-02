import { useEffect, useState } from "react";
import { Panel } from "../components/common/Panel";
import { Loading } from "../components/common/Loading";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { StatusPill } from "../components/common/StatusPill";
import { useApi } from "../state/ApiProvider";
import { ApiError } from "../api/errors";
import type { ModelsDescribe } from "../api/types";
import styles from "./IntegrationsView.module.css";

/**
 * There is no dedicated integrations/permissions endpoint yet. The closest
 * real signal the backend exposes is the model/provider describe report,
 * which lists configured credentials, provider policy, and build warnings —
 * so that is shown here honestly, labeled for what it actually is.
 */
export function IntegrationsView() {
  const { client } = useApi();
  const [describe, setDescribe] = useState<ModelsDescribe | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    client
      .getModelsDescribe()
      .then((res) => {
        if (!cancelled) setDescribe(res);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof ApiError
              ? cause
              : new ApiError(0, { code: "network_error", message: "Failed to load provider status" }),
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, nonce]);

  return (
    <Panel
      title="Integrations & permissions"
      description="Model provider credentials and routing policy, as reported by the backend's models/describe endpoint."
      actions={
        <button type="button" className={styles.refresh} onClick={() => setNonce((n) => n + 1)}>
          Refresh
        </button>
      }
    >
      {loading ? (
        <Loading label="Loading provider status" rows={4} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => setNonce((n) => n + 1)} />
      ) : !describe ? (
        <EmptyState
          title="No provider status available"
          description="The models/describe endpoint is not configured on this deployment."
          notConfigured
        />
      ) : (
        <div className={styles.stack}>
          <section>
            <h3 className={styles.sectionTitle}>Credentials</h3>
            {Object.keys(describe.credentials).length === 0 ? (
              <EmptyState title="No provider credentials reported" notConfigured />
            ) : (
              <ul className={styles.credList}>
                {Object.entries(describe.credentials).map(([provider, present]) => (
                  <li key={provider} className={styles.credItem}>
                    <span>{provider}</span>
                    <StatusPill
                      label={present ? "Configured" : "Missing"}
                      tone={present ? "positive" : "danger"}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className={styles.sectionTitle}>Routing policy</h3>
            <p className={styles.policyLine}>Default profile: {describe.default_profile}</p>
            {Object.keys(describe.policy).length === 0 ? (
              <p className={styles.muted}>No policy overrides reported.</p>
            ) : (
              <dl className={styles.policyList}>
                {Object.entries(describe.policy).map(([key, value]) => (
                  <div key={key} className={styles.policyRow}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          {describe.warnings.length > 0 ? (
            <section>
              <h3 className={styles.sectionTitle}>Warnings</h3>
              <ul className={styles.warnings}>
                {describe.warnings.map((warning, i) => (
                  <li key={i}>{warning}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      )}
    </Panel>
  );
}
