# Deployment and PostgreSQL migration

## Delivery workflow

`Staged Azure deployment` is intentionally manual. It selects the `staging` or
`production` GitHub Environment, so configure required reviewers and restrict
who can deploy production in GitHub before enabling it. Required variables and
the single required Environment secret are listed below.

The Azure application registration must have a federated credential scoped to
this repository and the allowed GitHub Environment/ref. Grant only the Azure
roles required by deployment. The workflow:

1. verifies the checked-out commit;
2. signs in with GitHub OIDC;
3. creates an ephemeral AZD environment configuration;
4. previews and provisions the foundation with the new registry temporarily
   reachable for image bootstrap, but with no Container Apps;
5. builds, scans, pushes, signs, and attests the frontend, API, worker, and
   operator images at the full commit SHA;
6. previews and provisions the four workloads while disabling registry public
   access; and
7. verifies private/public ingress, authentication, health, and registry
   posture.

The workflow creates a dedicated Premium registry for the replacement
environment. It does not modify the Basic registry used by the legacy
application, because that application has no VNet path to a private registry
and must remain restartable throughout the rollback window. If a workflow
fails after bootstrap, cleanup disables public access on the new registry.

The image tag is an immutable, full Git commit SHA. Bicep creates revisions
that consume the same SHA-tagged images; no floating tags are used.

Required non-secret GitHub Environment variables are:

`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`AZURE_ENV_NAME`, `AZURE_LOCATION`, `ALERT_RECEIVER_EMAIL`,
`POSTGRES_SERVER_RESOURCE_ID`, `POSTGRES_SERVER_FQDN`,
`POSTGRES_DATABASE_NAME`, `POSTGRES_API_USERNAME`,
`POSTGRES_WORKER_USERNAME`, `ENTRA_CLIENT_ID`, `ENTRA_AUDIENCE`,
`AZURE_OPENAI_RESOURCE_GROUP`, `AZURE_OPENAI_ACCOUNT_NAME`,
`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, and optionally
`AZURE_OPENAI_EMBEDDING_DEPLOYMENT`.

`ENTRA_CLIENT_SECRET` is the only required GitHub Environment secret. Bicep
materializes it as a Key Vault-backed Container Apps authentication secret;
it must never be written to source, deployment output, or logs.

Built-in authentication's token store is enabled on the frontend and operator.
Those proxies forward the signed Entra ID token to the internal API, which
validates it directly in `entra_jwt` mode. Principal headers are never the API's
source of trust.

## Database schema rollout and migration identity

Production schema changes run only through the manual Container Apps Job
`job-migrate-<token>` (`python -m alembic upgrade head`) using the immutable
API image and the dedicated `id-migrate-<token>` managed identity. The deploy
workflow starts the job after image publication and waits for success before any
application revision is deployed; a failed migration stops the release and
leaves the previous revision serving.

One-time bootstrap (PostgreSQL administrator; not automatable in Bicep): create
Entra database principals named exactly like the API, worker, and migration
identities, grant the migration principal DDL/ownership on the application
schema, and grant API/worker only DML. Migrations are additive (`6f3c2b8a9d11`
execution fencing + provisioning uniqueness; `81c44fd91a20` durable
conversation state). Recover from a failed migration by fixing forward with a
new compatible revision; never delete schema.

Revision names use a short `sha-<12 chars>` suffix; the full commit SHA remains
the image tag and runtime metadata.

## Environment progression

1. Merge only after `Verify` passes.
2. Deploy to staging, run authenticated API/UI, SSE resume, approval, artifact,
   cancellation, and recovery smoke tests.
3. Inspect Application Insights, dependency health, alerts, and cost signals.
4. Promote the same commit SHA to production through a protected Environment.
5. Start with a canary revision/low traffic. Promote only after SLO and
   isolation checks pass; retain the prior healthy revision.
6. Add the generated frontend and operator callback URLs to the Entra
   application registration before authenticated smoke tests.

## Existing PostgreSQL migration

This is a non-destructive, maintenance-window sequence for the existing Central
US PostgreSQL server:

1. Announce the window; record the current revision and connection settings.
2. Take an on-demand backup and prove a restore to an isolated target.
3. Apply only additive Alembic/schema migrations; validate backfill counts and
   rollback compatibility.
4. Resize to the approved capacity and expect a connection interruption.
5. Create/validate the private endpoint and private DNS from the East US 2
   application VNet.
6. Enable Entra authentication; create scoped API/worker database principals;
   validate migration, smoke, and load tests using those identities.
7. Switch application traffic. Only then disable password authentication and
   public network access after a documented rollback test.

Do not combine destructive schema changes, credential removal, and endpoint
cutover in one release. Use expand-contract migrations and defer deletion until
the rollback window has closed.

## Preflight and rollback

Before any state-changing step, run the AZD preview, Bicep builds, and staging
smoke tests. Check provider registration/capacity and compare the what-if
result to the approved plan. If validation fails, stop before provision.

To roll back an application release, shift traffic or reactivate the previous
healthy Container App revision, then verify authenticated health and event
streaming. Do not roll back a database by deleting schema. Roll forward with a
compatible migration, or restore to an isolated server and execute the approved
data-recovery procedure.
