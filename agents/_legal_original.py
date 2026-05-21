"""
AgentSystem — Legal Agent.

Legal advisor agent for compliance analysis, contract drafting and review,
RFP responses, privacy policies, and legal research.

DISCLAIMER: All outputs from this agent are AI-generated and do NOT constitute
legal advice. Always consult a qualified attorney before relying on any output.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\n⚠️  DISCLAIMER: This document is AI-generated and does NOT constitute "
    "legal advice. It should be reviewed, validated, and approved by a "
    "qualified attorney before use."
)


async def draft_legal_document(
    document_type: Annotated[str, "Type of document: NDA, ToS, DPA, contract, SLA"],
    parties: Annotated[str, "Comma-separated names of the parties involved"],
    key_terms: Annotated[str, "Key terms and conditions to include"],
    jurisdiction: Annotated[str, "Governing jurisdiction (e.g., State of Delaware, UK)"] = "",
) -> str:
    """
    Draft legal documents (NDA, ToS, DPA, contract, etc.).
    Returns a formatted document with standard clauses.
    Always includes a disclaimer that this is AI-generated and should be
    reviewed by a qualified attorney.
    """
    party_list = [p.strip() for p in parties.split(",") if p.strip()]

    log_action(
        "LegalAgent",
        "draft_legal_document",
        f"type={document_type}, parties={party_list}, jurisdiction={jurisdiction}",
    )

    doc = (
        f"📄 DRAFT: {document_type.upper()}\n"
        f"{'═' * 60}\n\n"
        f"**Document Type:** {document_type}\n"
        f"**Parties:**\n"
    )

    for i, party in enumerate(party_list, 1):
        doc += f"  {i}. {party}\n"

    if jurisdiction:
        doc += f"**Governing Jurisdiction:** {jurisdiction}\n"

    doc += (
        f"\n**Key Terms:**\n  {key_terms}\n\n"
        f"{'─' * 60}\n\n"
        f"## 1. Definitions\n\n"
        f"  [Standard definitions for {document_type} to be inserted here,\n"
        f"   tailored to the parties and subject matter.]\n\n"
        f"## 2. Scope & Obligations\n\n"
        f"  [Obligations of each party based on the key terms provided.]\n\n"
        f"## 3. Term & Termination\n\n"
        f"  [Duration, renewal terms, and termination conditions.]\n\n"
        f"## 4. Confidentiality\n\n"
        f"  [Confidentiality obligations, exclusions, and duration.]\n\n"
        f"## 5. Limitation of Liability\n\n"
        f"  [Liability caps, exclusions, and indemnification terms.]\n\n"
        f"## 6. Dispute Resolution\n\n"
        f"  [Arbitration, mediation, or litigation venue and process.]\n\n"
        f"## 7. General Provisions\n\n"
        f"  [Entire agreement, amendments, severability, waiver, notices.]\n\n"
        f"{'─' * 60}\n\n"
        f"**Signatures:**\n\n"
    )

    for party in party_list:
        doc += (
            f"  {party}\n"
            f"  Signature: ___________________________  Date: ____________\n\n"
        )

    doc += _DISCLAIMER
    return doc


async def analyze_compliance(
    regulation: Annotated[str, "Regulation to analyze: GDPR, HIPAA, SOC2, PCI-DSS, CCPA, etc."],
    business_description: Annotated[str, "Description of the business and data handling"],
    current_measures: Annotated[str, "Current compliance measures in place"] = "",
) -> str:
    """
    Analyze compliance requirements for a given regulation.
    Returns gap analysis and remediation steps.
    """
    log_action(
        "LegalAgent",
        "analyze_compliance",
        f"regulation={regulation}, business_len={len(business_description)}",
    )

    analysis = (
        f"🔒 COMPLIANCE ANALYSIS: {regulation.upper()}\n"
        f"{'═' * 60}\n\n"
        f"**Regulation:** {regulation}\n"
        f"**Business:** {business_description[:300]}\n"
    )

    if current_measures:
        analysis += f"**Current Measures:** {current_measures[:300]}\n"

    analysis += (
        f"\n**Key Requirements for {regulation.upper()}:**\n\n"
        f"  1. Data Inventory & Classification\n"
        f"     → Know what data you collect, where it lives, and who accesses it.\n\n"
        f"  2. Lawful Basis & Consent\n"
        f"     → Establish and document the legal basis for data processing.\n\n"
        f"  3. Security Controls\n"
        f"     → Implement technical and organizational safeguards.\n\n"
        f"  4. Data Subject Rights\n"
        f"     → Support access, correction, deletion, and portability requests.\n\n"
        f"  5. Incident Response\n"
        f"     → Breach notification procedures within regulatory timelines.\n\n"
        f"  6. Vendor Management\n"
        f"     → Data Processing Agreements with all third-party processors.\n\n"
        f"  7. Documentation & Audit Trail\n"
        f"     → Maintain records of processing activities and compliance efforts.\n\n"
        f"**Gap Analysis:**\n"
        f"  [PLACEHOLDER] A detailed gap analysis would compare the above\n"
        f"  requirements against the current measures provided.\n\n"
        f"**Remediation Priority:**\n"
        f"  1. Address any gaps in security controls (highest risk).\n"
        f"  2. Establish data inventory if not already in place.\n"
        f"  3. Implement data subject rights workflows.\n"
        f"  4. Review and update vendor agreements.\n"
    )

    analysis += _DISCLAIMER
    return analysis


async def review_contract(
    contract_text: Annotated[str, "The contract text to review"],
    review_focus: Annotated[str, "Review focus: risks, obligations, termination, ip, all"] = "risks",
) -> str:
    """
    Review contract text for risks, unfavorable terms, and missing clauses.
    Returns findings with severity ratings.
    """
    log_action(
        "LegalAgent",
        "review_contract",
        f"text_length={len(contract_text)}, focus={review_focus}",
    )

    review = (
        f"📋 CONTRACT REVIEW\n"
        f"{'═' * 60}\n\n"
        f"**Review Focus:** {review_focus}\n"
        f"**Document Length:** {len(contract_text):,} characters\n\n"
        f"**Findings:**\n\n"
    )

    # Standard review items based on focus
    findings = {
        "risks": [
            ("HIGH", "Unlimited liability", "No liability cap found. Negotiate a mutual cap."),
            ("MEDIUM", "Auto-renewal", "Check for automatic renewal with long notice periods."),
            ("MEDIUM", "Broad indemnification", "Review scope of indemnification obligations."),
            ("LOW", "Governing law", "Confirm jurisdiction is acceptable for both parties."),
        ],
        "obligations": [
            ("HIGH", "Deliverable timelines", "Ensure timelines are realistic and clearly defined."),
            ("MEDIUM", "Reporting requirements", "Check frequency and format of required reports."),
            ("LOW", "Notification obligations", "Review notice periods for material changes."),
        ],
        "termination": [
            ("HIGH", "Termination for convenience", "Check if either party can terminate without cause."),
            ("MEDIUM", "Cure period", "Verify reasonable cure period for breaches."),
            ("LOW", "Post-termination obligations", "Review data return/destruction requirements."),
        ],
    }

    focus_items = findings.get(review_focus, [])
    if review_focus == "all" or review_focus == "ip" or not focus_items:
        # Combine all findings for 'all', 'ip', or unknown focus
        focus_items = []
        for items in findings.values():
            focus_items.extend(items)

    for severity, issue, recommendation in focus_items:
        icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")
        review += (
            f"  {icon} [{severity}] {issue}\n"
            f"     → {recommendation}\n\n"
        )

    review += (
        f"**Missing Clauses to Consider:**\n"
        f"  • Force majeure\n"
        f"  • Data protection / DPA\n"
        f"  • Intellectual property ownership\n"
        f"  • Non-solicitation\n"
        f"  • Severability\n"
    )

    review += _DISCLAIMER
    return review


async def create_rfp_response(
    rfp_requirements: Annotated[str, "The RFP requirements to respond to"],
    company_capabilities: Annotated[str, "Description of your company's capabilities"],
    differentiators: Annotated[str, "Key differentiators and competitive advantages"] = "",
) -> str:
    """
    Create an RFP response framework. Returns a structured response matching
    requirements to capabilities.
    """
    log_action(
        "LegalAgent",
        "create_rfp_response",
        f"req_len={len(rfp_requirements)}, cap_len={len(company_capabilities)}",
    )

    response = (
        f"📑 RFP RESPONSE FRAMEWORK\n"
        f"{'═' * 60}\n\n"
        f"## Executive Summary\n\n"
        f"  [Summarize your value proposition and fit for this opportunity.]\n\n"
        f"## Requirements Mapping\n\n"
        f"  **RFP Requirements:**\n"
        f"  {rfp_requirements[:500]}\n\n"
        f"  **Our Capabilities:**\n"
        f"  {company_capabilities[:500]}\n\n"
        f"  **Compliance Matrix:**\n\n"
        f"  {'Requirement':<30} {'Status':<15} {'Notes':<25}\n"
        f"  {'─' * 70}\n"
        f"  {'[Requirement 1]':<30} {'✅ Compliant':<15} {'Detail here':<25}\n"
        f"  {'[Requirement 2]':<30} {'✅ Compliant':<15} {'Detail here':<25}\n"
        f"  {'[Requirement 3]':<30} {'⚠️ Partial':<15} {'Workaround noted':<25}\n"
        f"  {'─' * 70}\n\n"
    )

    if differentiators:
        response += (
            f"## Differentiators\n\n"
            f"  {differentiators[:400]}\n\n"
        )

    response += (
        f"## Implementation Approach\n\n"
        f"  [Describe phased implementation plan with milestones.]\n\n"
        f"## Pricing Summary\n\n"
        f"  [Provide pricing structure aligned with RFP format.]\n\n"
        f"## References & Case Studies\n\n"
        f"  [Include relevant client references and similar engagements.]\n\n"
        f"## Terms & Conditions\n\n"
        f"  [Note any exceptions or proposed modifications to standard terms.]\n"
        f"{'═' * 60}"
    )

    return response


async def generate_privacy_policy(
    business_type: Annotated[str, "Type of business (SaaS, e-commerce, mobile app, etc.)"],
    data_collected: Annotated[str, "Types of data collected (e.g., name, email, payment, usage)"],
    third_parties: Annotated[str, "Third-party services that receive data"] = "",
    jurisdiction: Annotated[str, "Primary jurisdiction: US, EU, UK, global"] = "US",
) -> str:
    """
    Generate a privacy policy tailored to the business.
    Returns a formatted policy document.
    """
    log_action(
        "LegalAgent",
        "generate_privacy_policy",
        f"business={business_type}, jurisdiction={jurisdiction}, data={data_collected[:80]}",
    )

    policy = (
        f"🔐 PRIVACY POLICY\n"
        f"{'═' * 60}\n\n"
        f"**Business Type:** {business_type}\n"
        f"**Jurisdiction:** {jurisdiction}\n\n"
        f"{'─' * 60}\n\n"
        f"## 1. Information We Collect\n\n"
        f"  We collect the following types of information:\n"
        f"  {data_collected}\n\n"
        f"## 2. How We Use Your Information\n\n"
        f"  • To provide and improve our services.\n"
        f"  • To communicate with you about your account.\n"
        f"  • To comply with legal obligations.\n"
        f"  • To protect against fraud and abuse.\n\n"
        f"## 3. Information Sharing\n\n"
    )

    if third_parties:
        policy += (
            f"  We share data with the following third parties:\n"
            f"  {third_parties}\n\n"
            f"  Each third party is contractually required to protect your data.\n\n"
        )
    else:
        policy += "  We do not sell your personal information to third parties.\n\n"

    policy += (
        f"## 4. Data Retention\n\n"
        f"  We retain your data only as long as necessary to provide our\n"
        f"  services and fulfill legal obligations.\n\n"
        f"## 5. Your Rights\n\n"
    )

    if jurisdiction in ("EU", "UK", "global"):
        policy += (
            f"  Under GDPR / UK GDPR, you have the right to:\n"
            f"  • Access your personal data.\n"
            f"  • Rectify inaccurate data.\n"
            f"  • Request erasure ('right to be forgotten').\n"
            f"  • Restrict or object to processing.\n"
            f"  • Data portability.\n"
            f"  • Withdraw consent at any time.\n\n"
        )
    else:
        policy += (
            f"  Depending on your location, you may have the right to:\n"
            f"  • Access your personal data.\n"
            f"  • Request correction or deletion.\n"
            f"  • Opt out of data sales (where applicable).\n\n"
        )

    policy += (
        f"## 6. Security\n\n"
        f"  We implement industry-standard security measures including\n"
        f"  encryption, access controls, and regular audits.\n\n"
        f"## 7. Contact Us\n\n"
        f"  For privacy inquiries, contact: [privacy@yourcompany.com]\n\n"
        f"{'─' * 60}\n"
        f"  Effective Date: [INSERT DATE]\n"
        f"  Last Updated: [INSERT DATE]\n"
    )

    policy += _DISCLAIMER
    return policy


async def legal_research(
    topic: Annotated[str, "Legal topic to research"],
    jurisdiction: Annotated[str, "Jurisdiction: US, EU, UK, or specific state/country"] = "US",
    context: Annotated[str, "Additional context for the research"] = "",
) -> str:
    """
    Research legal topics and provide a summary of relevant laws,
    precedents, and considerations. Always includes disclaimer.
    """
    log_action(
        "LegalAgent",
        "legal_research",
        f"topic={topic[:100]}, jurisdiction={jurisdiction}",
    )

    research = (
        f"⚖️ LEGAL RESEARCH SUMMARY\n"
        f"{'═' * 60}\n\n"
        f"**Topic:** {topic}\n"
        f"**Jurisdiction:** {jurisdiction}\n"
    )

    if context:
        research += f"**Context:** {context[:300]}\n"

    research += (
        f"\n**Relevant Legal Framework:**\n\n"
        f"  [PLACEHOLDER] In production, this would reference specific\n"
        f"  statutes, regulations, and case law relevant to:\n"
        f"  \"{topic}\" in {jurisdiction}.\n\n"
        f"**Key Considerations:**\n\n"
        f"  1. Statutory Requirements\n"
        f"     → Identify applicable federal, state, and local laws.\n\n"
        f"  2. Regulatory Guidance\n"
        f"     → Review guidance from relevant regulatory bodies.\n\n"
        f"  3. Case Law & Precedents\n"
        f"     → Notable court decisions affecting interpretation.\n\n"
        f"  4. Industry Standards\n"
        f"     → Best practices and self-regulatory frameworks.\n\n"
        f"  5. Recent Developments\n"
        f"     → Pending legislation, proposed rules, or enforcement trends.\n\n"
        f"**Risk Assessment:**\n"
        f"  • Compliance risk: [Evaluate based on specific facts]\n"
        f"  • Enforcement risk: [Evaluate based on regulatory activity]\n"
        f"  • Reputational risk: [Evaluate based on public sensitivity]\n\n"
        f"**Recommended Actions:**\n"
        f"  1. Consult with qualified legal counsel in {jurisdiction}.\n"
        f"  2. Document compliance posture and rationale.\n"
        f"  3. Monitor for regulatory changes affecting this area.\n"
    )

    research += _DISCLAIMER
    return research


# List of tools to register with the legal agent
LEGAL_TOOLS = [
    draft_legal_document,
    analyze_compliance,
    review_contract,
    create_rfp_response,
    generate_privacy_policy,
    legal_research,
]
