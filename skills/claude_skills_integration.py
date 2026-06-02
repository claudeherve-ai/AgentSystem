"""
AgentSystem — Claude-Skills Deep Integration
=============================================
Maps 328 production skills from alirezarezvani/claude-skills to the multi-agent
orchestrator. Each skill's SKILL.md instructions + Python tools become callable
agent capabilities.

Skill → Agent mapping:
  C-Level Advisory (28 skills)  → CEO/CTO/CFO etc. personas → specific agents
  Engineering POWERFUL (25)     → SeniorDev, SoftwareArch, DevOps, Security
  RA/QM Compliance (14)         → Legal, LegalDoc, Security
  Finance (3)                   → FinanceAgent, InvestmentResearcher
  Business Growth (5)           → GrowthHacker, DealStrategist, BusinessAgent
  Marketing (45)                → GrowthHacker, SocialAgent, SalesProposal
  Product Team (13)             → ProductManager, ProjectManager
  Business Operations (7)       → BusinessAgent, ProjectShepherd
  Commercial (8)                → DealStrategist, SalesProposal
"""
import os
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("agentsystem.claude-skills")

# ── Repo paths ──────────────────────────────────────────────────────────────
CLAUDE_SKILLS_ROOT = Path.home() / "claude-skills"
if not CLAUDE_SKILLS_ROOT.exists():
    CLAUDE_SKILLS_ROOT = Path("/home/tedch/claude-skills")
if not CLAUDE_SKILLS_ROOT.exists():
    # Docker / cloud path
    CLAUDE_SKILLS_ROOT = Path("/app/claude-skills")

# ── Agent-to-skill-domain mapping ──────────────────────────────────────────
AGENT_SKILL_MAP: dict[str, list[str]] = {
    # ── Merged Agents v3.0 ───────────────────────────────────────────
    "EngineeringAgent": [
        # All engineering domains merged
        "c-level-advisor/skills/cto-advisor",
        "engineering",                    # POWERFUL: agent design, RAG, MCP, SLO, chaos
        "engineering-team/skills",        # Core: fullstack, AI/ML, DevOps, security
        "engineering/slo-architect",
        "engineering/chaos-engineering",
    ],
    "CloudDataAgent": [
        "engineering/docker-development",
        "engineering/kubernetes-operator",
        "engineering/terraform-patterns",
        "engineering/helm-chart-builder",
        "engineering/chaos-engineering",
        "project-management/skills",      # Atlassian, Jira, Confluence
    ],
    "RevenueAgent": [
        "c-level-advisor/skills/cro-advisor",
        "c-level-advisor/skills/cmo-advisor",
        "commercial/skills/deal-desk",
        "commercial/skills/commercial-forecaster",
        "commercial/skills/rfp-responder",
        "commercial/skills/pricing-strategist",
        "marketing-skill/skills",
        "business-growth/skills",
    ],
    "LegalAgent": [
        "c-level-advisor/skills/general-counsel-advisor",
        "ra-qm-team/skills/gdpr-dsgvo-expert",
        "ra-qm-team/skills/soc2-compliance",
        "ra-qm-team/skills/information-security-manager-iso27001",
        "ra-qm-team/skills/isms-audit-expert",
    ],
    "FinanceAgent": [
        "c-level-advisor/skills/cfo-advisor",
        "finance/skills/financial-analyst",
        "finance/skills/saas-metrics-coach",
        "finance/skills/business-investment-advisor",
    ],
    "ExecutionAgent": [
        "engineering/autoresearch-agent",
        "engineering/caveman",
        "engineering/grill-me",
        "engineering/grill-with-docs",
        "engineering/write-a-skill",
        "c-level-advisor/skills/decision-logger",
    ],
    # ── Standalone Agents ────────────────────────────────────────────
    "ProductManagerAgent": [
        "c-level-advisor/skills/cpo-advisor",
        "product-team",
    ],
    "ProjectManagerAgent": [
        "project-management/skills",
    ],
    "DealStrategistAgent": [
        "c-level-advisor/skills/cro-advisor",
        "commercial/skills/deal-desk",
        "commercial/skills/commercial-forecaster",
    ],
    "FinanceAgent": [
        "c-level-advisor/skills/cfo-advisor",
        "finance/skills/financial-analyst",
        "finance/skills/saas-metrics-coach",
    ],
    "BusinessAgent": [
        "business-operations/skills",
    ],
    "GrowthHackerAgent": [
        "c-level-advisor/skills/cmo-advisor",
        "marketing-skill/skills",
        "business-growth/skills",
    ],
    # Engineering
    "SeniorDevAgent": [
        "engineering-team/skills",
    ],
    "BackendArchitectAgent": [
        "engineering",
    ],
    "DevOpsAutomatorAgent": [
        "engineering/docker-development",
        "engineering/kubernetes-operator",
        "engineering/terraform-patterns",
        "engineering/helm-chart-builder",
        "engineering/chaos-engineering",
    ],
    "SecurityEngineerAgent": [
        "engineering/security-guidance",
        "ra-qm-team/skills/information-security-manager-iso27001",
    ],
    "AIEngineerAgent": [
        "engineering/llm-cost-optimizer",
        "engineering/prompt-governance",
        "engineering/llm-wiki",
    ],
    # Legal / Compliance
    "LegalAdvisorAgent": [
        "c-level-advisor/skills/general-counsel-advisor",
        "ra-qm-team/skills/gdpr-dsgvo-expert",
    ],
    "LegalDocReviewAgent": [
        "ra-qm-team/skills/gdpr-dsgvo-expert",
        "ra-qm-team/skills/soc2-compliance",
    ],
    # Sales
    "SalesProposalAgent": [
        "commercial/skills/rfp-responder",
        "business-growth/skills/sales-engineer",
    ],
    # Real Estate / Investment
    "RealEstateAgent": [
        "finance/skills/business-investment-advisor",
    ],
    "InvestmentResearcherAgent": [
        "finance/skills/financial-analyst",
        "finance/skills/business-investment-advisor",
    ],
    # Tax
    "TaxStrategistAgent": [
        "c-level-advisor/skills/cfo-advisor",
    ],
    # Enterprise
    "EnterpriseIntegrationAgent": [
        "engineering",
    ],
    # Problem Solver
    "ProblemSolverAgent": [
        "engineering/caveman",
        "engineering/grill-me",
    ],
    "ResearchAgent": [
        "engineering/autoresearch-agent",
    ],
    # People
    "ProjectShepherdAgent": [
        "c-level-advisor/skills/coo-advisor",
        "c-level-advisor/skills/change-management",
    ],
    "SocialAgent": [
        "marketing-skill/skills/x-twitter-growth",
        "marketing-skill/skills/content-production",
    ],
}


def discover_claude_skills() -> dict[str, list[dict[str, Any]]]:
    """Discover all available skills from the claude-skills repo."""
    inventory: dict[str, list[dict[str, Any]]] = {}

    if not CLAUDE_SKILLS_ROOT.exists():
        logger.warning("claude-skills repo not found at %s", CLAUDE_SKILLS_ROOT)
        return inventory

    # Walk all directories looking for SKILL.md files
    for skill_md in CLAUDE_SKILLS_ROOT.rglob("SKILL.md"):
        rel_path = skill_md.relative_to(CLAUDE_SKILLS_ROOT)
        domain = str(rel_path.parent)

        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            name, description = _parse_skill_frontmatter(content, domain)

            # Find Python tools
            scripts_dir = skill_md.parent / "scripts"
            tools = []
            if scripts_dir.exists():
                tools = [
                    str(p.relative_to(CLAUDE_SKILLS_ROOT))
                    for p in scripts_dir.glob("*.py")
                ]

            # Find reference docs
            refs_dir = skill_md.parent / "references"
            refs = []
            if refs_dir.exists():
                refs = [
                    str(p.relative_to(CLAUDE_SKILLS_ROOT))
                    for p in refs_dir.glob("*.md")
                ]

            inventory.setdefault(domain, []).append({
                "name": name,
                "description": description,
                "path": str(rel_path),
                "content": content,
                "tools": tools,
                "references": refs,
            })

        except Exception:
            logger.debug("Failed to parse %s", skill_md, exc_info=True)

    logger.info("Discovered %d skill domains from claude-skills", len(inventory))
    return inventory


def _parse_skill_frontmatter(content: str, domain: str) -> tuple[str, str]:
    """Extract name and description from SKILL.md frontmatter."""
    name = domain.split("/")[-1] if "/" in domain else domain
    description = ""

    if content.startswith("---"):
        try:
            end = content.index("---", 3)
            fm = content[3:end].strip()
            for line in fm.split("\n"):
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip('"')
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"')
        except (ValueError, IndexError):
            pass

    if not description:
        for line in content.split("\n"):
            s = line.strip()
            if s and not s.startswith("#") and not s.startswith("---") and len(s) > 20:
                description = s[:200]
                break

    return name, description


def get_skills_for_agent(agent_name: str) -> list[dict[str, Any]]:
    """Get all claude-skills relevant to a given agent."""
    domains = AGENT_SKILL_MAP.get(agent_name, [])
    if not domains:
        return []

    inventory = discover_claude_skills()
    relevant: list[dict[str, Any]] = []

    for domain, skills in inventory.items():
        for target_domain in domains:
            # Match domain prefix (e.g., "engineering/" matches "engineering/security-guidance")
            if domain.startswith(target_domain.rstrip("/")) or target_domain in domain:
                relevant.extend(skills)
                break

    # Deduplicate
    seen = set()
    deduped = []
    for s in relevant:
        key = s["path"]
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    return deduped[:15]


def build_skill_context_for_agent(agent_name: str) -> str:
    """Build a system context injection with relevant skill instructions."""
    skills = get_skills_for_agent(agent_name)
    if not skills:
        return ""

    lines = [
        "\n\n## 🔧 Available Expert Skills (from claude-skills)",
        f"You have access to {len(skills)} specialized skills. When relevant, apply their frameworks.",
        "",
    ]

    for i, skill in enumerate(skills[:8], 1):
        lines.append(f"### Skill {i}: {skill['name']}")
        lines.append(f"**Description:** {skill['description']}")
        # Extract key instructions (first 500 chars of non-frontmatter content)
        content = skill["content"]
        if content.startswith("---"):
            try:
                content = content[content.index("---", 3) + 3:]
            except ValueError:
                pass
        # Get first substantive section
        key_lines = []
        in_section = False
        for line in content.split("\n"):
            s = line.strip()
            if s.startswith("## ") and not in_section:
                in_section = True
                key_lines.append(s)
            elif in_section and s:
                key_lines.append(s)
                if sum(len(l) for l in key_lines) > 500:
                    break
        if key_lines:
            lines.append(f"**Key Instructions:**")
            lines.extend(f"  {l}" for l in key_lines[:8])

        # List tools
        if skill["tools"]:
            tool_names = [Path(t).stem for t in skill["tools"][:5]]
            lines.append(f"**Tools:** {', '.join(tool_names)}")
        lines.append("")

    return "\n".join(lines)


def list_tools_for_agent(agent_name: str) -> list[str]:
    """List Python tool paths available for an agent."""
    skills = get_skills_for_agent(agent_name)
    tools = []
    for skill in skills:
        for tool_path in skill.get("tools", []):
            full_path = CLAUDE_SKILLS_ROOT / tool_path
            if full_path.exists():
                tools.append(str(full_path))
    return tools


# ── CLI ─────────────────────────────────────────────────────────────────────

def print_inventory():
    """Print the full claude-skills inventory and agent mapping."""
    inventory = discover_claude_skills()

    print("\n" + "=" * 70)
    print("  CLAUDE-SKILLS INTEGRATION INVENTORY")
    print("=" * 70)
    print(f"  Root: {CLAUDE_SKILLS_ROOT}")
    print(f"  Domains: {len(inventory)}")
    total_skills = sum(len(s) for s in inventory.values())
    print(f"  Skills: {total_skills}")
    total_tools = sum(
        len(tool) for skills in inventory.values()
        for skill in skills for tool in skill.get("tools", [])
    )
    print(f"  Python tools: {total_tools}")
    print("-" * 70)

    # Per-agent mapping
    print("\n  AGENT → SKILL MAPPING")
    print("-" * 70)
    for agent_name, domains in sorted(AGENT_SKILL_MAP.items()):
        skills = get_skills_for_agent(agent_name)
        tools = list_tools_for_agent(agent_name)
        print(f"  {agent_name}:")
        print(f"    Skills: {len(skills)} | Tools: {len(tools)} | Domains: {', '.join(d[:30] for d in domains)}")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    print_inventory()
