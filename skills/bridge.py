"""
AgentSystem — Skills Integration Bridge
========================================

Bridges the 313+ production skills from claude-skills and awesome-claude-code-plugins
into the AgentSystem orchestrator. Each external skill becomes a tool that specialist
agents can invoke.

Architecture:
    1. Skill Discovery — scans ~/agency-agents and ~/awesome-claude-code-plugins/plugins
    2. Skill Loading — parses SKILL.md / agent persona files into agent tools
    3. Tool Generation — creates async tool functions that wrap skill instructions
    4. Agent Augmentation — injects skill tools into matching specialist agents

Priority skill domains:
    - C-Level Advisory (CEO, CTO, CFO, CMO, CISO, CPO)
    - Engineering Powerful (code review, debugging, API design, RAG, security)
    - Regulatory Compliance (GDPR, SOC2, ISO 27001, FDA, MDR 2017/745)
    - DevOps & Cloud (Azure, Docker, K8s, CI/CD)
    - Research & Analysis (arXiv, web search, market data)
    - Creative & Design (diagrams, infographics, ASCII art)
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("agentsystem.skills")

# ── Skill source directories ────────────────────────────────────────────────
SKILL_SOURCES = [
    Path.home() / "agency-agents",
    Path.home() / "awesome-claude-code-plugins" / "plugins",
    Path(__file__).resolve().parent.parent / "skills",  # Local skills
]

# Priority skill domains and their target agents
DOMAIN_AGENT_MAP = {
    "c-level-advisory": [
        "SoftwareArchitectAgent", "ProductManagerAgent",
        "ProjectManagerAgent", "DealStrategistAgent",
    ],
    "engineering-powerful": [
        "SeniorDevAgent", "SoftwareArchitectAgent",
        "BackendArchitectAgent", "FrontendDevAgent",
        "SecurityEngineerAgent", "DevOpsAutomatorAgent",
    ],
    "regulatory-compliance": [
        "LegalAdvisorAgent", "LegalDocReviewAgent",
        "SecurityEngineerAgent", "TaxStrategistAgent",
    ],
    "devops": [
        "DevOpsAutomatorAgent", "AzureSolutionArchitectAgent",
        "OptimizationArchitectAgent",
    ],
    "research": [
        "ResearchAgent", "InvestmentResearcherAgent",
        "DocumentAnalystAgent", "ProblemSolverAgent",
    ],
    "social-media": ["SocialAgent", "GrowthHackerAgent"],
    "creative": ["UXArchitectAgent", "FrontendDevAgent"],
    "security": ["SecurityEngineerAgent", "DevOpsAutomatorAgent"],
}


# ── Skill Discovery ─────────────────────────────────────────────────────────


def discover_skills() -> list[dict[str, Any]]:
    """Scan all skill source directories and return discovered skills."""
    discovered = []

    for source_dir in SKILL_SOURCES:
        src = Path(source_dir)
        if not src.exists():
            logger.debug("Skill source not found: %s", src)
            continue

        # Scan for SKILL.md files
        for skill_md in src.rglob("SKILL.md"):
            try:
                skill = _parse_skill_md(skill_md)
                if skill:
                    discovered.append(skill)
            except Exception:
                logger.debug("Failed to parse %s", skill_md, exc_info=True)

        # Scan for agent persona .md files
        for persona_md in src.rglob("*.md"):
            if persona_md.name == "SKILL.md":
                continue  # Already handled
            if "agents/" in str(persona_md) or "personas/" in str(persona_md):
                try:
                    skill = _parse_persona_md(persona_md)
                    if skill:
                        discovered.append(skill)
                except Exception:
                    logger.debug("Failed to parse persona %s", persona_md, exc_info=True)

    logger.info("Discovered %d external skills/personas", len(discovered))
    return discovered


def _parse_skill_md(path: Path) -> dict[str, Any] | None:
    """Parse a SKILL.md file into a skill descriptor."""
    content = path.read_text(encoding="utf-8", errors="replace")

    # Extract YAML frontmatter
    name = path.parent.name
    description = ""

    if content.startswith("---"):
        try:
            end = content.index("---", 3)
            frontmatter = content[3:end].strip()
            for line in frontmatter.split("\n"):
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
        except (ValueError, IndexError):
            pass

    if not description:
        # Use first non-empty, non-heading line
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                description = stripped[:200]
                break

    return {
        "name": name,
        "path": str(path),
        "description": description,
        "content": content,
        "type": "skill",
    }


def _parse_persona_md(path: Path) -> dict[str, Any] | None:
    """Parse an agent persona .md file into a skill descriptor."""
    content = path.read_text(encoding="utf-8", errors="replace")

    # Extract name from first heading
    name = path.stem
    description = ""

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            name = stripped[2:].strip()
            break

    # Get first paragraph as description
    in_content = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        if in_content and stripped and len(stripped) > 10:
            description = stripped[:200]
            break
        if stripped.startswith("# "):
            in_content = True

    return {
        "name": name,
        "path": str(path),
        "description": description,
        "content": content,
        "type": "persona",
    }


# ── Tool Generation ─────────────────────────────────────────────────────────


def create_skill_tool(skill: dict[str, Any]) -> callable:
    """Create an async tool function that wraps a skill/persona instruction."""

    skill_name = skill["name"]
    skill_content = skill["content"]

    async def skill_tool(query: str) -> str:
        """Execute a skill-backed tool. The LLM sees the skill instructions as context."""
        return (
            f"Using skill '{skill_name}':\n\n"
            f"Instructions:\n{skill_content[:3000]}\n\n"
            f"Query: {query}\n\n"
            f"[This tool provides the skill context. The agent should synthesize "
            f"a response following the skill's instructions.]"
        )

    skill_tool.__name__ = f"skill__{skill_name.lower().replace(' ', '_').replace('-', '_')}"
    skill_tool.__doc__ = skill.get("description", f"Skill: {skill_name}")
    return skill_tool


# ── Agent Augmentation ──────────────────────────────────────────────────────


def get_skills_for_agent(agent_name: str) -> list[dict[str, Any]]:
    """Find skills relevant to a specific agent based on domain mapping."""
    all_skills = discover_skills()

    # Find which domains this agent belongs to
    relevant_domains = []
    for domain, agents in DOMAIN_AGENT_MAP.items():
        if agent_name in agents:
            relevant_domains.append(domain)

    if not relevant_domains:
        return []

    # Filter skills by domain relevance (fuzzy match)
    relevant = []
    for skill in all_skills:
        skill_path = skill["path"].lower()
        skill_name = skill["name"].lower()
        for domain in relevant_domains:
            domain_path = domain.replace("-", "/")
            if domain_path in skill_path or domain.replace("-", " ") in skill_name:
                relevant.append(skill)
                break

    return relevant[:10]  # Cap at 10 to avoid overwhelming the agent


def augment_agent_tools(agent_name: str, current_tools: list) -> list:
    """Augment an agent's tools with relevant skill tools."""
    skills = get_skills_for_agent(agent_name)
    if not skills:
        return current_tools

    new_tools = list(current_tools)
    for skill in skills:
        tool = create_skill_tool(skill)
        new_tools.append(tool)

    logger.info(
        "Augmented %s with %d skill tools (had %d, now %d)",
        agent_name,
        len(skills),
        len(current_tools),
        len(new_tools),
    )
    return new_tools


# ── CLI / Testing ───────────────────────────────────────────────────────────


def print_skill_inventory():
    """Print a formatted inventory of all discovered skills."""
    skills = discover_skills()

    print("\n" + "=" * 70)
    print("  AGENTSYSTEM — EXTERNAL SKILL INVENTORY")
    print("=" * 70)
    print(f"  Total discovered: {len(skills)}")
    print(f"  Sources:")
    for src in SKILL_SOURCES:
        exists = "✓" if Path(src).exists() else "✗"
        print(f"    {exists} {src}")
    print("-" * 70)

    # Group by type
    by_type: dict[str, list] = {}
    for s in skills:
        by_type.setdefault(s["type"], []).append(s)

    for stype, items in by_type.items():
        print(f"\n  [{stype.upper()}] {len(items)} items:")
        for item in items[:20]:
            print(f"    • {item['name']}: {item['description'][:100]}")

    print("\n" + "=" * 70)
    print("  AGENT → SKILL MAPPING")
    print("-" * 70)
    for agent_name, skills_list in DOMAIN_AGENT_MAP.items():
        count = len(skills_list)
        print(f"  {agent_name}: {count} mapped agents")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    print_skill_inventory()
