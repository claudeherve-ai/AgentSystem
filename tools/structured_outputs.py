"""
Structured output templates for AgentSystem specialists.

FUNCTION TOOLS that enforce output schemas — agents MUST call these
to format their final output in a verifiable, machine-usable structure.

If an agent returns unstructured text where a schema was expected, the
orchestrator can detect this and flag the response.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── EMAIL INTELLIGENCE ───────────────────────────────────────────────────

EMAIL_INTEL_SCHEMA = {
    "thread_summary": "",
    "decisions_made": [],
    "open_questions": [],
    "action_items": [],
    "participants": [],
    "risk_flags": [],
    "thread_id": "",
    "analyzed_at": "",
}


async def email_intel_report(thread_data: str) -> str:
    """Produce a structured email intelligence report.

    Call this as the FINAL step after analyzing an email thread.
    Pass your analysis as a JSON string matching this schema:
    {
        "thread_summary": "One-paragraph summary of the thread",
        "decisions_made": ["Decision 1", "Decision 2"],
        "open_questions": ["Question 1", "Question 2"],
        "action_items": [
            {"owner": "Name", "task": "What to do", "due_date": "YYYY-MM-DD", "confidence": 0.9}
        ],
        "participants": [
            {"name": "Name", "role": "Role", "stance": "Stance", "influence": "high|medium|low"}
        ],
        "risk_flags": ["Flag 1", "Flag 2"],
        "thread_id": "optional-thread-id"
    }
    """
    try:
        parsed = json.loads(thread_data)
    except json.JSONDecodeError:
        return json.dumps({
            "error": "Invalid JSON input",
            "received": thread_data[:500],
            "hint": "Pass a valid JSON string matching the email_intel_report schema",
        }, indent=2)

    report = {
        **EMAIL_INTEL_SCHEMA,
        **parsed,
        "analyzed_at": datetime.now().isoformat(),
    }
    return json.dumps(report, indent=2, ensure_ascii=False)


# ── DEAL QUALIFICATION ───────────────────────────────────────────────────

MEDDPICC_SCHEMA = {
    "deal_name": "",
    "metrics": {"description": "", "quantified": False, "value": ""},
    "economic_buyer": {"name": "", "identified": False, "engaged": False},
    "decision_criteria": [],
    "decision_process": {"steps": [], "timeline": "", "known": False},
    "paper_process": {"legal": "", "procurement": "", "security_review": ""},
    "implicate_pain": {"pain_points": [], "cost_of_inaction": ""},
    "champion": {"name": "", "identified": False, "power": "", "coaching": False},
    "competition": [{"name": "", "position": "", "threat_level": ""}],
    "overall_score": 0.0,
    "recommendation": "",
    "next_steps": [],
}


async def deal_qualification_report(deal_data: str) -> str:
    """Produce a structured MEDDPICC deal qualification report.

    Call this as the FINAL step after qualifying a deal.
    Pass a JSON string with MEDDPICC fields filled in.

    Schema fields:
    - metrics: {description, quantified (bool), value}
    - economic_buyer: {name, identified (bool), engaged (bool)}
    - decision_criteria: [list of criteria]
    - decision_process: {steps, timeline, known (bool)}
    - paper_process: {legal, procurement, security_review}
    - implicate_pain: {pain_points, cost_of_inaction}
    - champion: {name, identified, power, coaching}
    - competition: [{name, position, threat_level}]
    - overall_score: 0.0-1.0
    - recommendation: text
    - next_steps: [list of actions]
    """
    try:
        parsed = json.loads(deal_data)
    except json.JSONDecodeError:
        return json.dumps({
            "error": "Invalid JSON input",
            "received": deal_data[:500],
            "hint": "Pass a valid JSON string matching the MEDDPICC schema",
        }, indent=2)

    report = {**MEDDPICC_SCHEMA, **parsed, "qualified_at": datetime.now().isoformat()}
    return json.dumps(report, indent=2, ensure_ascii=False)


# ── LEGAL RISK ASSESSMENT ────────────────────────────────────────────────

LEGAL_RISK_SCHEMA = {
    "document_type": "",
    "parties": [],
    "our_client": "",
    "jurisdiction": "",
    "high_risk_findings": [],
    "medium_risk_findings": [],
    "low_risk_findings": [],
    "missing_standard_terms": [],
    "overall_risk": "low|medium|high|critical",
    "recommended_actions": [],
    "disclaimer": "AI-generated review — NOT legal advice. Review by licensed attorney required.",
}


async def legal_risk_assessment(findings: str) -> str:
    """Produce a structured legal risk assessment report.

    Call this as the FINAL step after reviewing a legal document or contract.
    Pass a JSON string matching the legal risk schema.

    Finding entries should be:
    {
        "clause": "Section reference",
        "risk": "Description of the risk",
        "market_standard": "What standard practice is",
        "impact": "Potential business impact",
        "severity": "high|medium|low",
        "recommendation": "Suggested revision"
    }
    """
    try:
        parsed = json.loads(findings)
    except json.JSONDecodeError:
        return json.dumps({
            "error": "Invalid JSON input",
            "received": findings[:500],
            "hint": "Pass a valid JSON string matching the legal_risk_assessment schema",
        }, indent=2)

    report = {**LEGAL_RISK_SCHEMA, **parsed, "reviewed_at": datetime.now().isoformat()}
    return json.dumps(report, indent=2, ensure_ascii=False)


# ── FINANCIAL ANALYSIS ───────────────────────────────────────────────────

FINANCIAL_ANALYSIS_SCHEMA = {
    "analysis_title": "",
    "assumptions": [],
    "calculations": [],
    "sensitivity_analysis": [],
    "scenarios": [],
    "key_metrics": {},
    "recommendation": "",
    "risk_factors": [],
    "disclaimer": "AI-generated analysis — NOT financial advice. Review by qualified professional required.",
}


async def financial_analysis_report(model_data: str) -> str:
    """Produce a structured financial analysis report.

    Call this as the FINAL step after performing financial modeling.
    Pass a JSON string matching the financial analysis schema.

    Key fields:
    - assumptions: [{variable, value, rationale}]
    - calculations: [{name, formula, result, verified (bool)}]
    - sensitivity_analysis: [{variable, low_case, base_case, high_case, impact}]
    - scenarios: [{name, description, probability, outcome}]
    - key_metrics: {metric_name: value, ...}
    """
    try:
        parsed = json.loads(model_data)
    except json.JSONDecodeError:
        return json.dumps({
            "error": "Invalid JSON input",
            "received": model_data[:500],
            "hint": "Pass a valid JSON string matching the financial_analysis schema",
        }, indent=2)

    report = {**FINANCIAL_ANALYSIS_SCHEMA, **parsed, "analyzed_at": datetime.now().isoformat()}
    return json.dumps(report, indent=2, ensure_ascii=False)


# ── TOOL EXPORT ──────────────────────────────────────────────────────────

STRUCTURED_OUTPUT_TOOLS = [
    email_intel_report,
    deal_qualification_report,
    legal_risk_assessment,
    financial_analysis_report,
]

__all__ = [
    "STRUCTURED_OUTPUT_TOOLS",
    "email_intel_report",
    "deal_qualification_report",
    "legal_risk_assessment",
    "financial_analysis_report",
]
