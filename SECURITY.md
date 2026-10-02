# Security Policy

## Supported deployment posture

This repository supports local development and an Azure production target.
Production controls described in [docs/security.md](docs/security.md) become
effective only after the corresponding Azure infrastructure and GitHub
Environment configuration are deployed. Do not treat local defaults as
production-safe.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include credentials,
tenant identifiers, customer data, or exploit details in logs. Report it
privately to the repository maintainers through the GitHub Security Advisory
reporting flow, including:

- affected revision and component;
- reproduction steps and impact;
- whether data, credentials, or tenants may be exposed; and
- a safe contact method.

Maintainers will acknowledge the report, assess severity and scope, coordinate
mitigation, and publish a disclosure only after affected operators have had a
reasonable opportunity to remediate.

## Security expectations

- Never commit `.env` files, keys, tokens, connection strings, or customer data.
- Use least-privilege test identities and disposable test data.
- Keep dependencies and GitHub Actions current through Dependabot.
- Treat high/critical findings from required CI checks as release blockers unless
  explicitly risk-accepted and tracked by maintainers.
- Preserve tenant, workspace, and owner boundaries in every new data path.
