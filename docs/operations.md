# Operations, resilience, and cost

## SLOs and alerts

The approved initial objectives are 99.9% monthly product availability, API p95
under two seconds excluding model execution, run-event freshness p95 under two
seconds, zero cross-session leakage, RPO under 15 minutes, and RTO under 60
minutes. They are targets until dashboards and alert rules are deployed.

Alert on availability, API error rate/latency, dependency/readiness failures,
queue/run age, PostgreSQL saturation, Redis availability, model 401/429/5xx,
deployment failures, budget thresholds, and security changes. Every alert
needs an owner, severity, runbook link, and a tested notification path. Use
correlation/run IDs rather than sensitive request content in investigation.

## Backup, restore, and disaster recovery

PostgreSQL point-in-time recovery is the database recovery mechanism. Artifact
storage must use the configured versioning, soft-delete, and retention policy.
Before production cutover and at least periodically thereafter:

1. restore PostgreSQL to an isolated target at a chosen point in time;
2. validate schema, tenant-scoped data, and application read-only checks;
3. verify artifact recovery and revision provenance; and
4. record achieved RPO/RTO and remediation items.

Never restore over a live production server without an approved incident plan.
For regional/application failure, deploy the last verified commit-SHA image and
compatible infrastructure, restore data if required, validate tenant isolation,
then direct traffic only after health and smoke checks pass.

## Incident response

1. Declare severity, incident commander, communications owner, and timeline.
2. Stabilize: halt promotion, use a feature/traffic control where available,
   revoke exposed credentials, or shift to a prior revision.
3. Preserve sanitized logs, deployment IDs, run/correlation IDs, and evidence.
4. Recover with the least destructive action; verify health, SLO signals, and
   representative authenticated workflows.
5. Publish a blameless review within 48 hours with root cause, impact,
   corrective actions, owners, and dates.

## Release rollback

Application rollback means returning traffic to the previous verified revision;
keep prior images, SBOMs, and deployment metadata for the rollback period.
Stop a rollout if error rate, latency, cross-tenant access, critical security
finding, or dependency health violates the release guardrail. Database changes
must remain backward compatible through that period.

## Cost controls

Use the approved USD 500/month budget alerts at 50%, 80%, and 100%, a 1-GB/day
Log Analytics cap, zero warm Dynamic Sessions with a maximum of two concurrent
sessions, bounded Container App replicas, and per-run model token/latency/cost
telemetry. Review actual spend and top drivers monthly. Treat a cap or budget
alert as an operational event: throttle non-critical work before increasing a
limit, and record the business justification for any capacity increase.
