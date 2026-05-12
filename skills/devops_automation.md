# DevOps Automation Skill

## CI/CD Pipeline Stages
1. Security scan (dependency audit, SAST)
2. Unit + integration tests
3. Build + containerize
4. Deploy to staging
5. Smoke tests + health checks
6. Production deploy (blue-green/canary)
7. Post-deploy monitoring

## Infrastructure as Code
- Terraform for multi-cloud
- CloudFormation for AWS-only
- All infrastructure version-controlled
- No manual changes to production

## Deployment Strategies
- **Blue-Green**: Zero-downtime, instant rollback
- **Canary**: Gradual rollout (5% → 25% → 100%)
- **Rolling**: Sequential pod replacement
- Always include automated rollback criteria

## Monitoring Stack
- Metrics: Prometheus + Grafana
- Logs: ELK or Loki
- Traces: Jaeger or OpenTelemetry
- Alerts: PagerDuty/OpsGenie with severity levels
- SLA monitoring with error budgets
