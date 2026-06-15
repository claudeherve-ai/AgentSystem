"""Domain Classifier — Maps user tasks to required specialists and grounding domains.

CITATION: Cloud agent self-assessment feedback — "mandatory grounding rules by domain"
(session 2026-06-15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Domain-to-grounding-rules mapping ───────────────────────────────────
# Each domain maps to the required specialist + mandatory grounding tools.
# When a task matches multiple domains, ALL required tools are unioned.

DOMAIN_RULES: dict[str, dict] = {
    "email": {
        "specialists": ["EmailAgent"],
        "required_tools": ["read_inbox", "check_inbox"],
        "description": "Email reading, drafting, sending, or inbox management",
    },
    "calendar": {
        "specialists": ["CalendarAgent"],
        "required_tools": ["read_calendar", "check_calendar"],
        "description": "Appointments, scheduling, conflict detection",
    },
    "microsoft_azure": {
        "specialists": ["CloudDataAgent", "EngineeringAgent"],
        "required_tools": ["microsoft_docs_search", "web_search"],
        "description": "Microsoft, Azure, .NET, M365, Fabric, Entra topics",
    },
    "github_repo": {
        "specialists": ["EngineeringAgent"],
        "required_tools": ["github_search_code", "github_search_repositories", "github_get_file_contents"],
        "description": "GitHub repo, source code, issue, or PR questions",
    },
    "code_generation": {
        "specialists": ["EngineeringAgent", "CodeExecutorAgent", "ExecutionAgent"],
        "required_tools": ["run_python", "code_executor"],
        "description": "Code writing, generation, or debugging",
    },
    "architecture_design": {
        "specialists": ["EngineeringAgent", "CloudDataAgent"],
        "required_tools": ["critique_response"],
        "description": "Architecture, design decisions, system planning",
    },
    "security": {
        "specialists": ["SecurityEngineerAgent"],
        "required_tools": ["web_search", "microsoft_docs_search"],
        "description": "Security, threat modeling, vulnerability analysis",
    },
    "ai_ml": {
        "specialists": ["AIEngineerAgent", "ExecutionAgent"],
        "required_tools": ["web_search", "huggingface_model_search"],
        "description": "AI/ML, LLM integration, model deployment",
    },
    "finance": {
        "specialists": ["FinanceAgent"],
        "required_tools": ["run_python"],
        "description": "Financial calculations, budgeting, investment analysis",
    },
    "legal": {
        "specialists": ["LegalAgent"],
        "required_tools": ["web_search"],
        "description": "Legal documents, compliance, contract review",
    },
    "revenue_sales": {
        "specialists": ["RevenueAgent"],
        "required_tools": ["web_search"],
        "description": "Deal strategy, proposals, sales, growth",
    },
    "social_media": {
        "specialists": ["SocialAgent"],
        "required_tools": [],
        "description": "Social media posting, engagement",
    },
    "customer_case": {
        "specialists": ["ExecutionAgent", "CloudDataAgent"],
        "required_tools": ["case_search", "read_file"],
        "description": "Customer case files, SR numbers, Work_cases folders",
    },
    "local_file": {
        "specialists": ["ExecutionAgent", "EngineeringAgent"],
        "required_tools": ["read_file", "list_dir", "search_in_file"],
        "description": "Local file, PDF, DOCX, log, CSV, or code inspection",
    },
    "calculation": {
        "specialists": ["CodeExecutorAgent", "ExecutionAgent"],
        "required_tools": ["run_python"],
        "description": "Computation, data transformation, report generation",
    },
    "research": {
        "specialists": ["ExecutionAgent"],
        "required_tools": ["web_search", "web_fetch"],
        "description": "General research, web search, fact-finding",
    },
    "enterprise_integration": {
        "specialists": ["EnterpriseIntegrationAgent"],
        "required_tools": ["web_search"],
        "description": "Enterprise system integrations, API orchestration",
    },
    "product_management": {
        "specialists": ["ProductManagerAgent"],
        "required_tools": [],
        "description": "PRDs, roadmaps, user stories, GTM",
    },
    "project_management": {
        "specialists": ["ProjectManagerAgent", "ProjectShepherdAgent"],
        "required_tools": [],
        "description": "Project plans, risks, stakeholder reports",
    },
    "real_estate": {
        "specialists": ["RealEstateAgent"],
        "required_tools": ["web_search"],
        "description": "Property analysis, CMA, investment analysis",
    },
}


# ── Keyword triggers for domain classification ─────────────────────────
# Each domain has a set of keyword patterns. First-match wins if unambiguous;
# multiple matches result in a union of requirements.

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "email": [
        "email", "inbox", "mail", "draft reply", "unread",
        "send email", "read email", "check email",
    ],
    "calendar": [
        "calendar", "schedule", "appointment", "meeting",
        "event", "availability", "time slot",
    ],
    "microsoft_azure": [
        "azure", "microsoft", ".net", "m365", "entra",
        "fabric", "power platform", "databricks",
        "azure openai", "bicep", "arm template",
    ],
    "github_repo": [
        "github", "repo", "repository", "git", "pull request",
        "issue", "commit", "branch", "merge",
    ],
    "code_generation": [
        "code", "implement", "build", "program", "script",
        "function", "class", "api endpoint", "debug",
        "fix bug", "write a", "create a function",
    ],
    "architecture_design": [
        "architecture", "design", "system", "schema",
        "migration", "infrastructure", "terraform",
        "pipeline", "strategy", "planning",
    ],
    "security": [
        "security", "threat", "vulnerability", "secure",
        "auth", "compliance", "audit", "encrypt",
        "pen test", "attack",
    ],
    "ai_ml": [
        "ai", "ml", "machine learning", "llm", "model",
        "prompt", "fine-tune", "inference", "training",
        "neural", "transformer", "embedding",
    ],
    "finance": [
        "finance", "budget", "expense", "invoice",
        "tax", "investment", "portfolio", "price",
        "cost", "revenue forecast", "cash flow",
    ],
    "legal": [
        "legal", "contract", "compliance", "gdpr",
        "hipaa", "soc2", "nda", "terms of service",
        "privacy policy", "regulatory",
    ],
    "revenue_sales": [
        "deal", "sales", "proposal", "rfp", "meddpicc",
        "revenue", "growth", "funnel", "customer",
        "pricing", "win theme",
    ],
    "social_media": [
        "social media", "post", "tweet", "linkedin",
        "twitter", "instagram", "facebook", "engagement",
    ],
    "customer_case": [
        "case", "sr", "work_cases", "customer file",
        "ticket", "incident report",
    ],
    "local_file": [
        "file", "read", "open", "document", "pdf",
        "docx", "csv", "log", "inspect", "show me",
        "look at",
    ],
    "calculation": [
        "calculate", "compute", "run", "transform",
        "convert", "sum", "average", "analyze data",
        "report",
    ],
    "enterprise_integration": [
        "integration", "salesforce", "hubspot", "api",
        "webhook", "sync", "orchestration", "sap",
    ],
    "product_management": [
        "prd", "roadmap", "user story", "product",
        "feature", "backlog", "prioritize",
    ],
    "project_management": [
        "project plan", "timeline", "milestone",
        "stakeholder", "status report", "risk",
        "dependency",
    ],
    "real_estate": [
        "real estate", "property", "house", "mortgage",
        "cma", "offer", "listing",
    ],
}

# High-stakes markers — these domains ALWAYS require critique
HIGH_STAKES_DOMAINS = {
    "architecture_design",
    "security",
    "finance",
    "legal",
    "revenue_sales",
    "code_generation",
}


@dataclass(frozen=True, slots=True)
class DomainClassification:
    """Result of classifying a user task into one or more domains."""

    domains: list[str] = field(default_factory=list)
    required_specialists: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    is_high_stakes: bool = False
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "domains": self.domains,
            "required_specialists": self.required_specialists,
            "required_tools": self.required_tools,
            "is_high_stakes": self.is_high_stakes,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


def classify_domain(task: str) -> DomainClassification:
    """Classify a user task into one or more enforcement domains.

    Uses keyword matching (fast, deterministic, no LLM call).
    """
    task_lower = (task or "").lower()
    matched_domains: list[str] = []
    matched_scores: list[tuple[str, int]] = []

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in task_lower)
        if score > 0:
            matched_scores.append((domain, score))

    # Sort by score descending, take top matches
    matched_scores.sort(key=lambda x: x[1], reverse=True)

    if not matched_scores:
        return DomainClassification(
            domains=["research"],
            required_specialists=["ExecutionAgent"],
            required_tools=["web_search"],
            is_high_stakes=False,
            confidence=0.1,
            reasoning="No keywords matched; defaulting to research domain.",
        )

    # If the top score is significantly higher, use only that domain
    # Otherwise union all matches within 50% of top score
    top_score = matched_scores[0][1]
    for domain, score in matched_scores:
        if score >= top_score * 0.5:  # within 50% of top
            matched_domains.append(domain)

    # Union all required specialists and tools
    specialists: list[str] = []
    tools: list[str] = []
    for domain in matched_domains:
        rules = DOMAIN_RULES.get(domain, {})
        for s in rules.get("specialists", []):
            if s not in specialists:
                specialists.append(s)
        for t in rules.get("required_tools", []):
            if t not in tools:
                tools.append(t)

    is_high_stakes = any(d in HIGH_STAKES_DOMAINS for d in matched_domains)

    # Confidence: higher when top score dominates
    confidence = min(1.0, top_score / max(1, len(task_lower.split()) * 0.1))

    return DomainClassification(
        domains=matched_domains,
        required_specialists=specialists,
        required_tools=tools,
        is_high_stakes=is_high_stakes,
        confidence=round(confidence, 2),
        reasoning=f"Matched domain(s): {', '.join(matched_domains)} (top score: {top_score})",
    )
