"""
AgentSystem — DevOps Automator Agent.

DevOps engineer specializing in infrastructure automation, CI/CD pipelines,
container orchestration, and cloud operations. Designs production-grade
deployment and reliability solutions.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from tools.mcp_tools import MCP_FILESYSTEM_TOOLS, MCP_GIT_TOOLS

logger = logging.getLogger(__name__)


async def design_cicd_pipeline(
    project_type: Annotated[str, "Project type: python, node, java, dotnet, go, docker"],
    repo_platform: Annotated[str, "Repository platform: github, azure-devops, gitlab"] = "github",
    deploy_target: Annotated[str, "Deployment target: azure, aws, gcp, kubernetes, on-prem"] = "",
    stages: Annotated[str, "Comma-separated custom stages to include"] = "",
) -> str:
    """Design CI/CD pipeline. Returns YAML config with build, test, security, and deploy."""
    logger.info(f"Designing CI/CD pipeline for {project_type} on {repo_platform}")

    custom_stages = [s.strip() for s in stages.split(",") if s.strip()] if stages else []

    build_commands = {
        "python": ("pip install -r requirements.txt", "pytest --cov --junitxml=results.xml"),
        "node": ("npm ci", "npm test -- --coverage"),
        "java": ("mvn clean install -DskipTests", "mvn test"),
        "dotnet": ("dotnet restore && dotnet build", "dotnet test --logger trx"),
        "go": ("go build ./...", "go test -race -coverprofile=coverage.out ./..."),
        "docker": ("docker build -t $IMAGE_NAME:$TAG .", "docker run --rm $IMAGE_NAME:$TAG test"),
    }

    build_cmd, test_cmd = build_commands.get(
        project_type.lower(),
        ("echo 'Build step'", "echo 'Test step'"),
    )

    platform_format = {
        "github": "GitHub Actions",
        "azure-devops": "Azure Pipelines",
        "gitlab": "GitLab CI/CD",
    }

    report = (
        f"🔧 CI/CD PIPELINE DESIGN ({platform_format.get(repo_platform, repo_platform)})\n"
        f"{'═' * 65}\n"
        f"  Project: {project_type}  |  Platform: {repo_platform}  |  Target: {deploy_target or 'TBD'}\n"
        f"{'─' * 65}\n\n"
        f"📋 Pipeline Stages:\n\n"
        f"  Stage 1: 🔨 BUILD\n"
        f"    trigger: push to main, pull_request\n"
        f"    steps:\n"
        f"      - checkout code\n"
        f"      - setup {project_type} environment\n"
        f"      - {build_cmd}\n"
        f"      - cache dependencies\n\n"
        f"  Stage 2: 🧪 TEST\n"
        f"    depends_on: build\n"
        f"    steps:\n"
        f"      - {test_cmd}\n"
        f"      - upload coverage report\n"
        f"      - publish test results\n\n"
        f"  Stage 3: 🔒 SECURITY SCAN\n"
        f"    depends_on: build\n"
        f"    parallel: true\n"
        f"    steps:\n"
        f"      - SAST scan (Semgrep/CodeQL)\n"
        f"      - Dependency vulnerability scan (Trivy/Snyk)\n"
        f"      - Secret detection (Gitleaks)\n"
        f"      - License compliance check\n\n"
        f"  Stage 4: 📦 PACKAGE\n"
        f"    depends_on: [test, security_scan]\n"
        f"    condition: main branch only\n"
        f"    steps:\n"
        f"      - build production artifact\n"
        f"      - tag with version (semantic versioning)\n"
        f"      - push to artifact registry\n\n"
    )

    if deploy_target:
        report += (
            f"  Stage 5: 🚀 DEPLOY\n"
            f"    depends_on: package\n"
            f"    target: {deploy_target}\n"
            f"    steps:\n"
            f"      - deploy to staging\n"
            f"      - run smoke tests\n"
            f"      - deploy to production (manual approval)\n"
            f"      - post-deployment health check\n\n"
        )

    if custom_stages:
        report += f"  Custom Stages:\n"
        for cs in custom_stages:
            report += f"    • {cs}\n"
        report += "\n"

    report += (
        f"{'─' * 65}\n"
        f"  ⚙️ Quality Gates:\n"
        f"    • Test coverage ≥ 80%\n"
        f"    • Zero critical/high vulnerabilities\n"
        f"    • All tests passing\n"
        f"    • Code review approved\n"
        f"{'═' * 65}\n"
    )

    log_action(
        "DevOpsAutomatorAgent",
        "design_cicd_pipeline",
        f"{project_type} on {repo_platform}",
        f"Target: {deploy_target or 'N/A'}, Custom stages: {len(custom_stages)}",
    )
    return report


async def create_infrastructure(
    cloud_provider: Annotated[str, "Cloud provider: azure, aws, gcp"],
    service_type: Annotated[str, "Service type: web-app, api, database, data-pipeline, ml-platform"],
    environment: Annotated[str, "Environment: development, staging, production"] = "production",
    scaling: Annotated[str, "Scaling strategy: manual, auto, serverless"] = "auto",
) -> str:
    """Design Infrastructure as Code. Returns IaC template with networking, compute, storage."""
    logger.info(f"Creating infrastructure for {service_type} on {cloud_provider}")

    iac_tool = {
        "azure": "Terraform (azurerm provider)",
        "aws": "Terraform (aws provider)",
        "gcp": "Terraform (google provider)",
    }

    service_resources = {
        "web-app": [
            "Virtual Network / VPC with subnets",
            "Application Gateway / Load Balancer",
            "App Service / ECS / Cloud Run",
            "CDN for static assets",
            "SSL/TLS certificate",
        ],
        "api": [
            "Virtual Network / VPC with subnets",
            "API Gateway / API Management",
            "Compute (containers or serverless)",
            "Key Vault / Secrets Manager",
            "Application Insights / CloudWatch",
        ],
        "database": [
            "Virtual Network with private subnets",
            "Managed database service",
            "Read replicas (production)",
            "Automated backups (7/30 day retention)",
            "Private endpoint / VPC peering",
        ],
        "data-pipeline": [
            "Data Lake / Storage account",
            "Compute cluster (Spark/Databricks)",
            "Orchestration (Data Factory / Step Functions)",
            "Event Hub / Kinesis for streaming",
            "Monitoring and alerting",
        ],
        "ml-platform": [
            "ML Workspace / SageMaker",
            "GPU compute cluster",
            "Model registry",
            "Feature store",
            "Serving endpoint with auto-scaling",
        ],
    }

    resources = service_resources.get(service_type, service_resources["api"])

    report = (
        f"🏗️ INFRASTRUCTURE AS CODE: {service_type.upper()}\n"
        f"{'═' * 65}\n"
        f"  Provider:    {cloud_provider.upper()}\n"
        f"  Environment: {environment}\n"
        f"  Scaling:     {scaling}\n"
        f"  IaC Tool:    {iac_tool.get(cloud_provider, 'Terraform')}\n"
        f"{'─' * 65}\n\n"
        f"📦 Resources:\n"
    )

    for resource in resources:
        report += f"  • {resource}\n"

    report += (
        f"\n🔒 Security Configuration:\n"
        f"  • Network: Private subnets, NSG/Security Groups, no public IPs\n"
        f"  • Identity: Managed Identity / IAM roles (no stored credentials)\n"
        f"  • Encryption: At-rest (AES-256) and in-transit (TLS 1.2+)\n"
        f"  • Secrets: Key Vault / Secrets Manager integration\n"
        f"  • Logging: Diagnostic logs to central SIEM\n\n"
    )

    if scaling == "auto":
        report += (
            f"📈 Auto-Scaling Configuration:\n"
            f"  • Scale metric: CPU utilization\n"
            f"  • Scale-out threshold: 70% for 5 minutes\n"
            f"  • Scale-in threshold: 30% for 10 minutes\n"
            f"  • Min instances: {'1' if environment == 'development' else '2'}\n"
            f"  • Max instances: {'4' if environment == 'development' else '20'}\n"
            f"  • Cool-down period: 300 seconds\n\n"
        )

    report += (
        f"🏷️ Tagging Strategy:\n"
        f"  environment: {environment}\n"
        f"  service:     {service_type}\n"
        f"  managed_by:  terraform\n"
        f"  cost_center: <to-be-assigned>\n"
        f"  owner:       <team-name>\n"
        f"{'═' * 65}\n"
    )

    log_action(
        "DevOpsAutomatorAgent",
        "create_infrastructure",
        f"{cloud_provider}/{service_type}/{environment}",
        f"Resources: {len(resources)}, Scaling: {scaling}",
    )
    return report


async def design_container_setup(
    application_description: Annotated[str, "Description of the application to containerize"],
    orchestrator: Annotated[str, "Container orchestrator: kubernetes, docker-compose, ecs, aca"] = "kubernetes",
    registry: Annotated[str, "Container registry: acr, ecr, gcr, dockerhub"] = "",
) -> str:
    """Create containerization strategy. Returns Dockerfile, manifests, and service mesh config."""
    logger.info(f"Designing container setup with {orchestrator}")

    report = (
        f"🐳 CONTAINERIZATION STRATEGY\n"
        f"{'═' * 65}\n"
        f"  Application:  {application_description}\n"
        f"  Orchestrator: {orchestrator}\n"
        f"  Registry:     {registry or 'TBD'}\n"
        f"{'─' * 65}\n\n"
        f"📄 Dockerfile Best Practices:\n"
        f"  • Multi-stage build (builder + runtime)\n"
        f"  • Non-root user (UID 1000)\n"
        f"  • Minimal base image (alpine/distroless)\n"
        f"  • Layer caching for dependencies\n"
        f"  • Health check instruction\n"
        f"  • .dockerignore for build context\n\n"
    )

    if orchestrator == "kubernetes":
        report += (
            f"☸️ Kubernetes Manifests:\n"
            f"  Deployment:\n"
            f"    replicas: 3 (production)\n"
            f"    strategy: RollingUpdate (maxSurge: 1, maxUnavailable: 0)\n"
            f"    resources:\n"
            f"      requests: cpu=100m, memory=128Mi\n"
            f"      limits:   cpu=500m, memory=512Mi\n"
            f"    probes:\n"
            f"      liveness:  /healthz (period: 10s)\n"
            f"      readiness: /ready   (period: 5s)\n"
            f"      startup:   /healthz (failureThreshold: 30)\n\n"
            f"  Service:\n"
            f"    type: ClusterIP\n"
            f"    port: 80 → targetPort: 8080\n\n"
            f"  Ingress:\n"
            f"    TLS termination\n"
            f"    Path-based routing\n"
            f"    Rate limiting annotations\n\n"
            f"  HorizontalPodAutoscaler:\n"
            f"    minReplicas: 2\n"
            f"    maxReplicas: 10\n"
            f"    targetCPU: 70%\n\n"
            f"  🕸️ Service Mesh (Istio/Linkerd):\n"
            f"    • mTLS between services\n"
            f"    • Circuit breaking\n"
            f"    • Retry policies (3 retries, 2s timeout)\n"
            f"    • Traffic splitting for canary\n"
        )
    elif orchestrator == "docker-compose":
        report += (
            f"🐙 Docker Compose:\n"
            f"  services:\n"
            f"    app:\n"
            f"      build: .\n"
            f"      ports: 8080:8080\n"
            f"      restart: unless-stopped\n"
            f"      healthcheck: curl -f http://localhost:8080/healthz\n"
            f"      deploy:\n"
            f"        resources:\n"
            f"          limits: cpus=0.5, memory=512M\n"
        )
    else:
        report += (
            f"📋 {orchestrator.upper()} Configuration:\n"
            f"  • Task/container definition with resource limits\n"
            f"  • Health check configuration\n"
            f"  • Auto-scaling rules\n"
            f"  • Load balancer integration\n"
        )

    report += f"\n{'═' * 65}\n"

    log_action(
        "DevOpsAutomatorAgent",
        "design_container_setup",
        f"Orchestrator: {orchestrator}, Registry: {registry or 'TBD'}",
        f"Application: {application_description[:80]}",
    )
    return report


async def create_monitoring_stack(
    services_json: Annotated[str, "JSON array of services with fields: name, type, sla_target"],
    alert_channels: Annotated[str, "Comma-separated alert channels: email, slack, pagerduty, teams"] = "email",
    sla_targets: Annotated[str, "Overall SLA targets (e.g., 99.9% availability, <200ms P95)"] = "",
) -> str:
    """Design monitoring and observability stack. Returns config with dashboards and alerts."""
    logger.info("Creating monitoring stack")

    try:
        services = json.loads(services_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON format for services data."

    if not isinstance(services, list):
        return "❌ Error: services_json must be a JSON array."

    channels = [c.strip() for c in alert_channels.split(",") if c.strip()]

    report = (
        f"📡 MONITORING & OBSERVABILITY STACK\n"
        f"{'═' * 65}\n\n"
        f"🔧 Stack Components:\n"
        f"  Metrics:     Prometheus + Grafana\n"
        f"  Logging:     Loki / ELK Stack\n"
        f"  Tracing:     Jaeger / Zipkin\n"
        f"  Alerting:    Alertmanager → {', '.join(channels)}\n\n"
    )

    if sla_targets:
        report += f"🎯 SLA Targets: {sla_targets}\n\n"

    report += f"📊 Service Dashboards:\n"
    for svc in services:
        name = svc.get("name", "unknown")
        svc_type = svc.get("type", "service")
        sla = svc.get("sla_target", "99.9%")
        report += (
            f"\n  📋 {name} ({svc_type})\n"
            f"  {'─' * 45}\n"
            f"  SLA Target: {sla}\n"
            f"  Panels:\n"
            f"    • Request rate (req/s)\n"
            f"    • Error rate (4xx/5xx %)\n"
            f"    • Latency (P50/P95/P99)\n"
            f"    • Saturation (CPU, memory, connections)\n"
        )

    report += (
        f"\n{'─' * 65}\n"
        f"🚨 Alert Rules:\n\n"
        f"  P1 — CRITICAL (page immediately):\n"
        f"    • Service down > 1 minute\n"
        f"    • Error rate > 5% for 5 minutes\n"
        f"    • P99 latency > 5s for 5 minutes\n\n"
        f"  P2 — WARNING (notify within 15 min):\n"
        f"    • Error rate > 1% for 15 minutes\n"
        f"    • P95 latency > 2s for 10 minutes\n"
        f"    • CPU > 80% for 10 minutes\n"
        f"    • Memory > 85% for 10 minutes\n\n"
        f"  P3 — INFO (daily digest):\n"
        f"    • Disk usage > 70%\n"
        f"    • Certificate expiry < 30 days\n"
        f"    • Dependency deprecation warnings\n\n"
        f"📧 Alert Channels: {', '.join(channels)}\n"
        f"{'═' * 65}\n"
    )

    log_action(
        "DevOpsAutomatorAgent",
        "create_monitoring_stack",
        f"Services: {len(services)}, Channels: {', '.join(channels)}",
        f"SLA: {sla_targets or 'default'}",
    )
    return report


async def design_disaster_recovery(
    system_description: Annotated[str, "Description of the system to protect"],
    rto_minutes: Annotated[int, "Recovery Time Objective in minutes"] = 60,
    rpo_minutes: Annotated[int, "Recovery Point Objective in minutes"] = 15,
    backup_strategy: Annotated[str, "Preferred backup strategy: snapshot, continuous, incremental"] = "",
) -> str:
    """Create disaster recovery plan with backup strategy, failover, and recovery runbooks."""
    logger.info(f"Designing DR plan: RTO={rto_minutes}m, RPO={rpo_minutes}m")

    strategy = backup_strategy or ("continuous" if rpo_minutes <= 5 else "incremental" if rpo_minutes <= 30 else "snapshot")

    report = (
        f"🛡️ DISASTER RECOVERY PLAN\n"
        f"{'═' * 60}\n\n"
        f"📋 System: {system_description}\n\n"
        f"🎯 Recovery Objectives:\n"
        f"  RTO (Recovery Time):  {rto_minutes} minutes\n"
        f"  RPO (Recovery Point): {rpo_minutes} minutes\n"
        f"  Backup Strategy:      {strategy.title()}\n\n"
    )

    report += (
        f"💾 Backup Strategy ({strategy.title()}):\n"
        f"  {'─' * 50}\n"
    )
    if strategy == "continuous":
        report += (
            f"  • Real-time replication to secondary region\n"
            f"  • Transaction log shipping (async, <5min lag)\n"
            f"  • Point-in-time recovery capability\n"
            f"  • Retention: 30 days continuous + 12 monthly snapshots\n"
        )
    elif strategy == "incremental":
        report += (
            f"  • Full backup: Daily at 02:00 UTC\n"
            f"  • Incremental: Every {rpo_minutes} minutes\n"
            f"  • Geo-redundant storage for all backups\n"
            f"  • Retention: 7 daily + 4 weekly + 12 monthly\n"
        )
    else:
        report += (
            f"  • Automated snapshots: Every {rpo_minutes} minutes\n"
            f"  • Cross-region snapshot replication\n"
            f"  • Retention: 24 hourly + 7 daily + 4 weekly\n"
        )

    report += (
        f"\n🔄 Failover Procedure:\n"
        f"  {'─' * 50}\n"
        f"  Step 1: Detection (automated)\n"
        f"    • Health check failure for 3 consecutive intervals\n"
        f"    • Alert fires to on-call + incident channel\n\n"
        f"  Step 2: Assessment (0-5 minutes)\n"
        f"    • Confirm outage scope and impact\n"
        f"    • Determine if failover is required\n\n"
        f"  Step 3: Failover Execution (5-{rto_minutes} minutes)\n"
        f"    • Promote secondary region/replica\n"
        f"    • Update DNS/traffic manager\n"
        f"    • Verify data integrity\n"
        f"    • Validate application health\n\n"
        f"  Step 4: Communication\n"
        f"    • Notify stakeholders of failover\n"
        f"    • Update status page\n"
        f"    • Begin root cause investigation\n\n"
    )

    report += (
        f"📖 Recovery Runbooks:\n"
        f"  {'─' * 50}\n"
        f"  1. Database failover runbook\n"
        f"  2. Application tier failover runbook\n"
        f"  3. DNS/networking cutover runbook\n"
        f"  4. Data validation and integrity check runbook\n"
        f"  5. Failback procedure runbook\n\n"
        f"🧪 DR Testing Schedule:\n"
        f"  • Tabletop exercise: Monthly\n"
        f"  • Partial failover test: Quarterly\n"
        f"  • Full DR drill: Semi-annually\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "DevOpsAutomatorAgent",
        "design_disaster_recovery",
        f"RTO: {rto_minutes}m, RPO: {rpo_minutes}m, Strategy: {strategy}",
        f"System: {system_description[:80]}",
    )
    return report


async def create_deployment_strategy(
    application_type: Annotated[str, "Application type: web, api, microservice, monolith, mobile-backend"],
    strategy: Annotated[str, "Deployment strategy: blue-green, canary, rolling, recreate"] = "blue-green",
    rollback_criteria: Annotated[str, "Conditions that trigger automatic rollback"] = "",
) -> str:
    """Design deployment strategy with health checks, canary analysis, and rollback plan."""
    logger.info(f"Creating deployment strategy: {strategy} for {application_type}")

    rollback_conditions = (
        [c.strip() for c in rollback_criteria.split(",") if c.strip()]
        if rollback_criteria
        else [
            "Error rate > 1% for 5 minutes",
            "P95 latency > 3x baseline",
            "Health check failures > 3 consecutive",
            "Critical alert fires",
        ]
    )

    report = (
        f"🚀 DEPLOYMENT STRATEGY: {strategy.upper().replace('-', ' ')}\n"
        f"{'═' * 60}\n"
        f"  Application: {application_type}\n"
        f"  Strategy:    {strategy}\n"
        f"{'─' * 60}\n\n"
    )

    if strategy == "blue-green":
        report += (
            f"  📋 Blue-Green Procedure:\n"
            f"  ────────────────────────\n"
            f"  1. Deploy new version to GREEN environment\n"
            f"  2. Run smoke tests against GREEN\n"
            f"  3. Run integration tests against GREEN\n"
            f"  4. Switch traffic: BLUE → GREEN (instant cutover)\n"
            f"  5. Monitor for {10} minutes\n"
            f"  6. If healthy: decommission BLUE\n"
            f"  7. If unhealthy: revert traffic to BLUE\n\n"
            f"  Advantage: Instant rollback, zero-downtime\n"
            f"  Trade-off: Requires 2x infrastructure during deploy\n"
        )
    elif strategy == "canary":
        report += (
            f"  📋 Canary Procedure:\n"
            f"  ────────────────────\n"
            f"  1. Deploy new version to canary (5% traffic)\n"
            f"  2. Monitor canary metrics for 15 minutes\n"
            f"  3. If pass: increase to 25% (15 min observation)\n"
            f"  4. If pass: increase to 50% (15 min observation)\n"
            f"  5. If pass: roll to 100%\n"
            f"  6. Any failure: instant rollback to 0%\n\n"
            f"  Advantage: Gradual risk exposure\n"
            f"  Trade-off: Slower rollout, requires traffic splitting\n"
        )
    elif strategy == "rolling":
        report += (
            f"  📋 Rolling Update Procedure:\n"
            f"  ────────────────────────────\n"
            f"  1. Update instances one-by-one (or batch)\n"
            f"  2. Wait for health check pass before next batch\n"
            f"  3. Max surge: 25% (extra capacity during update)\n"
            f"  4. Max unavailable: 0 (maintain full capacity)\n"
            f"  5. Rollback: reverse rolling update\n\n"
            f"  Advantage: No extra infrastructure needed\n"
            f"  Trade-off: Mixed versions during deploy window\n"
        )
    else:
        report += (
            f"  📋 Recreate Procedure:\n"
            f"  ──────────────────────\n"
            f"  1. Scale down all old instances\n"
            f"  2. Deploy new version\n"
            f"  3. Scale up new instances\n"
            f"  4. Verify health\n\n"
            f"  Advantage: Clean cut, no version mixing\n"
            f"  Trade-off: Downtime during deployment\n"
        )

    report += (
        f"\n🏥 Health Checks:\n"
        f"  • Liveness:  GET /healthz  (period: 10s, threshold: 3)\n"
        f"  • Readiness: GET /ready    (period: 5s, threshold: 1)\n"
        f"  • Startup:   GET /healthz  (period: 5s, failureThreshold: 30)\n\n"
        f"⏪ Rollback Criteria (automatic):\n"
    )
    for condition in rollback_conditions:
        report += f"  🔴 {condition}\n"

    report += (
        f"\n📋 Rollback Procedure:\n"
        f"  1. Automated: Traffic reverted to previous version\n"
        f"  2. Alert sent to deployment channel\n"
        f"  3. Incident ticket auto-created\n"
        f"  4. Post-mortem required for all rollbacks\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "DevOpsAutomatorAgent",
        "create_deployment_strategy",
        f"{application_type}, Strategy: {strategy}",
        f"Rollback criteria: {len(rollback_conditions)}",
    )
    return report


DEVOPSAUTOMATOR_TOOLS = [
    design_cicd_pipeline,
    create_infrastructure,
    design_container_setup,
    create_monitoring_stack,
    design_disaster_recovery,
    create_deployment_strategy,
] + list(MCP_GIT_TOOLS) + list(MCP_FILESYSTEM_TOOLS)
