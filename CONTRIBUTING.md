# Contributing

## Before opening a pull request

1. Branch from the current default branch and keep the change focused.
2. Do not commit generated runtime data, credentials, `.env` files, or build
   outputs.
3. Add or update tests for application behavior (when application code changes).
4. Run the validation commands in the [README](README.md) that apply to your
   change.
5. Describe behavior, risk, migration/rollback implications, and validation in
   the pull request.

## Quality gates

The `Verify` workflow is blocking: Python compilation, Ruff, tests with the
current 35% aggregate coverage floor, frontend typecheck/test/build, Bicep
builds, Docker builds, dependency review, CodeQL, secret scanning, Trivy, and
SBOM generation. A failed security check is not bypassed by changing its
threshold; remediate, update the dependency, or obtain a documented maintainer
risk decision.

## Design and operational changes

Document user-visible API changes, data migrations, deployment effects, and
operational procedures in `docs/`. Preserve API compatibility where possible.
For stateful changes, use additive/expand-contract migrations and include a
rollback path. Changes that modify the Azure target must be validated with a
non-production AZD preview before deployment.

## Review standards

Reviewers verify correctness, tenant isolation, input validation, secret
handling, failure behavior, observability, and tests. Do not claim a planned
Azure control is implemented until the matching infrastructure is deployed and
verified.
