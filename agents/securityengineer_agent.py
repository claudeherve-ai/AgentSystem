"""
AgentSystem — Security Engineer Agent.

Application security specialist for threat modeling, vulnerability assessment,
secure code review, and security architecture design.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action
from tools.mcp_tools import (
    MCP_DOCS_TOOLS,
    MCP_GITHUB_TOOLS,
    MCP_SENTRY_TOOLS,
    MCP_SEQUENTIAL_THINKING_TOOLS,
)

logger = logging.getLogger(__name__)


async def create_threat_model(
    application_name: Annotated[str, "Name of the application or system"],
    architecture_type: Annotated[str, "Type: monolith, microservices, serverless, or hybrid"],
    tech_stack: Annotated[str, "Languages, frameworks, databases, cloud provider"],
    data_types: Annotated[str, "Data classification: PII, financial, credentials, health, public"],
    external_integrations: Annotated[str, "External APIs, payment processors, OAuth providers"] = "",
) -> str:
    """Create a STRIDE-based threat model for an application."""
    log_action("SecurityEngineerAgent", "threat_model", f"app={application_name}")

    return (
        f"THREAT MODEL: {application_name}\n{'=' * 60}\n\n"
        f"Architecture: {architecture_type}\n"
        f"Tech Stack:   {tech_stack}\n"
        f"Data Types:   {data_types}\n"
        f"Integrations: {external_integrations or 'None listed'}\n\n"
        f"TRUST BOUNDARIES\n{'─' * 60}\n"
        f"  {'Boundary':<25} {'From':<15} {'To':<15} {'Controls'}\n"
        f"  {'Internet -> App':<25} {'User':<15} {'Gateway':<15} {'TLS, WAF, rate limit'}\n"
        f"  {'App -> Services':<25} {'Gateway':<15} {'Backend':<15} {'mTLS, JWT'}\n"
        f"  {'Service -> DB':<25} {'Backend':<15} {'Database':<15} {'Parameterized queries'}\n\n"
        f"STRIDE ANALYSIS\n{'─' * 60}\n"
        f"  {'Threat':<20} {'Component':<15} {'Risk':<6} {'Mitigation'}\n"
        f"  {'Spoofing':<20} {'Auth':<15} {'High':<6} {'MFA, token binding'}\n"
        f"  {'Tampering':<20} {'API':<15} {'High':<6} {'Input validation, HMAC'}\n"
        f"  {'Repudiation':<20} {'Actions':<15} {'Med':<6} {'Audit logging'}\n"
        f"  {'Info Disclosure':<20} {'Errors':<15} {'Med':<6} {'Generic errors'}\n"
        f"  {'DoS':<20} {'Public API':<15} {'High':<6} {'Rate limiting, WAF'}\n"
        f"  {'Priv Escalation':<20} {'Admin':<15} {'Crit':<6} {'RBAC, session isolation'}\n\n"
        f"ATTACK SURFACE INVENTORY\n"
        f"  External: APIs, OAuth flows, file uploads, WebSockets\n"
        f"  Internal: Service RPCs, message queues, caches\n"
        f"  Data:     DB queries, logs, backups\n"
        f"  Supply:   Dependencies, CDN scripts, CI/CD pipeline\n"
    )


async def review_security(
    code_or_config: Annotated[str, "Code snippet, configuration, or architecture description to review"],
    review_type: Annotated[str, "Type: code-review, config-review, architecture-review, or dependency-audit"],
    language: Annotated[str, "Programming language or technology"] = "general",
) -> str:
    """Perform a security review of code, configuration, or architecture."""
    log_action("SecurityEngineerAgent", "review_security", f"type={review_type}, lang={language}")

    return (
        f"SECURITY REVIEW\n{'=' * 60}\n\n"
        f"Review Type: {review_type}\n"
        f"Technology:  {language}\n"
        f"Input Size:  {len(code_or_config):,} characters\n\n"
        f"FINDINGS\n{'─' * 60}\n"
        f"  [!!!] CRITICAL: [Authentication bypass, injection, RCE]\n"
        f"  [ ! ] HIGH:     [Stored XSS, IDOR, privilege escalation]\n"
        f"  [ . ] MEDIUM:   [CSRF, missing headers, verbose errors]\n"
        f"  [   ] LOW:      [Info disclosure, best practice gaps]\n\n"
        f"SECURITY CHECKLIST\n{'─' * 60}\n"
        f"  [ ] Authentication: token validation, expiry, algorithm\n"
        f"  [ ] Authorization: IDOR, privilege escalation, mass assignment\n"
        f"  [ ] Input validation: boundary values, injection vectors\n"
        f"  [ ] Error handling: no stack traces, generic auth errors\n"
        f"  [ ] Security headers: CSP, HSTS, X-Frame-Options\n"
        f"  [ ] Rate limiting: login, sensitive endpoints\n\n"
        f"REMEDIATION\n"
        f"  [Prioritized fixes with copy-paste-ready code]\n"
    )


async def generate_security_checklist(
    project_type: Annotated[str, "Type: web-app, api, mobile, cloud-infra, or ci-cd"],
    compliance_requirements: Annotated[str, "Compliance: SOC2, HIPAA, PCI-DSS, GDPR, or none"] = "none",
) -> str:
    """Generate a security checklist for a project type with compliance mapping."""
    log_action("SecurityEngineerAgent", "security_checklist", f"type={project_type}")

    return (
        f"SECURITY CHECKLIST: {project_type.upper()}\n{'=' * 60}\n\n"
        f"Compliance: {compliance_requirements}\n\n"
        f"AUTHENTICATION & ACCESS\n{'─' * 60}\n"
        f"  [ ] MFA enforced for privileged accounts\n"
        f"  [ ] OAuth 2.0 + PKCE for public clients\n"
        f"  [ ] Least-privilege IAM roles\n"
        f"  [ ] Session management (timeout, invalidation)\n\n"
        f"DATA PROTECTION\n{'─' * 60}\n"
        f"  [ ] TLS 1.3 in transit\n"
        f"  [ ] AES-256 at rest\n"
        f"  [ ] Key rotation policy\n"
        f"  [ ] No secrets in code or logs\n\n"
        f"APPLICATION SECURITY\n{'─' * 60}\n"
        f"  [ ] Input validation at every trust boundary\n"
        f"  [ ] Parameterized queries (no string concat SQL)\n"
        f"  [ ] Output encoding (XSS prevention)\n"
        f"  [ ] CSRF protection on state-changing endpoints\n"
        f"  [ ] Security headers (CSP, HSTS)\n\n"
        f"CI/CD & SUPPLY CHAIN\n{'─' * 60}\n"
        f"  [ ] SAST scanning in pipeline\n"
        f"  [ ] Dependency vulnerability scanning\n"
        f"  [ ] Container image scanning\n"
        f"  [ ] Secrets detection (pre-commit)\n"
    )


SECURITYENGINEER_TOOLS = (
    [create_threat_model, review_security, generate_security_checklist]
    + list(MCP_DOCS_TOOLS)
    + list(MCP_GITHUB_TOOLS)
    + list(MCP_SENTRY_TOOLS)
    + list(MCP_SEQUENTIAL_THINKING_TOOLS)
)
