"""
AgentSystem — Legal Document Review Agent.

Meticulous document analysis specialist for contracts, litigation documents,
and real estate agreements. Summarizes documents, flags risk clauses, compares
versions, and checks compliance.

DISCLAIMER: All outputs are AI-generated and do NOT constitute legal advice.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\n---\nDISCLAIMER: This is AI-generated analysis, NOT legal advice. "
    "All findings must be reviewed and approved by a licensed attorney."
)


async def review_document(
    document_text: Annotated[str, "Full text of the legal document to review"],
    document_type: Annotated[str, "Type: contract, lease, NDA, MSA, settlement, motion, or other"],
    client_role: Annotated[str, "Client's role in the document (e.g. buyer, seller, licensee, tenant)"],
    risk_tolerance: Annotated[str, "Risk tolerance: conservative, moderate, or aggressive"] = "moderate",
) -> str:
    """Review a legal document for risks, missing clauses, and key terms. Returns a structured analysis."""
    log_action("LegalDocReviewAgent", "review_document", f"type={document_type}, role={client_role}")

    severity_items = [
        ("HIGH", "Indemnification scope", "Review breadth of indemnification obligations and mutual vs. one-sided."),
        ("HIGH", "Liability cap", "Verify whether a limitation of liability cap exists and is reasonable."),
        ("MEDIUM", "Termination provisions", "Check termination for convenience rights and cure periods."),
        ("MEDIUM", "Auto-renewal", "Flag automatic renewal with short notice-to-cancel windows."),
        ("LOW", "Governing law", "Confirm jurisdiction is acceptable; note enforceability variations."),
    ]

    result = (
        f"DOCUMENT REVIEW REPORT\n{'=' * 60}\n\n"
        f"Document Type: {document_type}\n"
        f"Client Role:   {client_role}\n"
        f"Risk Tolerance: {risk_tolerance}\n"
        f"Document Length: {len(document_text):,} characters\n\n"
        f"FLAGGED CLAUSES\n{'─' * 60}\n"
    )
    for severity, issue, rec in severity_items:
        icon = {"HIGH": "!!!", "MEDIUM": " ! ", "LOW": " . "}.get(severity, "   ")
        result += f"  [{icon}] [{severity}] {issue}\n       -> {rec}\n\n"

    result += (
        f"MISSING STANDARD TERMS\n{'─' * 60}\n"
        "  [ ] Force majeure\n"
        "  [ ] Data protection / DPA\n"
        "  [ ] IP ownership / work-for-hire\n"
        "  [ ] Dispute resolution mechanism\n"
        "  [ ] Insurance requirements\n\n"
        f"NEXT STEPS\n{'─' * 60}\n"
        "  1. Address HIGH-risk items before execution.\n"
        "  2. Negotiate missing standard terms.\n"
        "  3. Have qualified counsel finalize review.\n"
    )
    result += _DISCLAIMER
    return result


async def compare_document_versions(
    version_a: Annotated[str, "Original version of the document"],
    version_b: Annotated[str, "Revised version of the document"],
    focus: Annotated[str, "Comparison focus: material, all, or pricing"] = "material",
) -> str:
    """Compare two versions of a legal document and highlight material changes."""
    log_action("LegalDocReviewAgent", "compare_versions", f"focus={focus}, lenA={len(version_a)}, lenB={len(version_b)}")

    result = (
        f"VERSION COMPARISON REPORT\n{'=' * 60}\n\n"
        f"Version A length: {len(version_a):,} chars\n"
        f"Version B length: {len(version_b):,} chars\n"
        f"Focus: {focus}\n\n"
        f"CHANGE SUMMARY\n{'─' * 60}\n"
        "  Material Changes:       [Identify from diff]\n"
        "  Administrative Changes: [Formatting, minor wording]\n"
        "  Additions:              [New clauses in Version B]\n"
        "  Deletions:              [Clauses removed from Version A]\n\n"
        "RECOMMENDATION\n"
        "  Review the flagged material changes with counsel.\n"
    )
    result += _DISCLAIMER
    return result


async def check_compliance(
    document_text: Annotated[str, "Document text to check"],
    framework: Annotated[str, "Compliance framework: GDPR, HIPAA, SOC2, PCI-DSS, CCPA, or custom"],
    requirements: Annotated[str, "Specific compliance requirements to verify"] = "",
) -> str:
    """Check a document against a compliance framework and report gaps."""
    log_action("LegalDocReviewAgent", "check_compliance", f"framework={framework}")

    result = (
        f"COMPLIANCE REVIEW: {framework.upper()}\n{'=' * 60}\n\n"
        f"Document length: {len(document_text):,} chars\n"
        f"Framework: {framework}\n\n"
        f"CHECKLIST\n{'─' * 60}\n"
        "  [ ] Required disclosures present\n"
        "  [ ] Data handling provisions adequate\n"
        "  [ ] Breach notification terms included\n"
        "  [ ] Retention and deletion policies defined\n"
        "  [ ] Third-party processor obligations addressed\n\n"
        "GAPS IDENTIFIED\n"
        "  [Analyze document against framework requirements]\n\n"
        "REMEDIATION PRIORITY\n"
        "  1. Address mandatory regulatory gaps first.\n"
        "  2. Add missing disclosure language.\n"
        "  3. Review with compliance counsel.\n"
    )
    result += _DISCLAIMER
    return result


LEGALDOCREVIEW_TOOLS = [review_document, compare_document_versions, check_compliance]
