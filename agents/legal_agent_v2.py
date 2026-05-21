"""LegalAgent — Legal advisory and compliance powerhouse.
Merges: LegalAdvisor + LegalDocReview"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.legal_agent import draft_legal_document,analyze_compliance,review_contract,create_rfp_response,generate_privacy_policy,legal_research
from agents.legaldocreview_agent import (review_document as ldr_review,compare_document_versions,check_compliance as ldr_check_compliance)
LEGAL_TOOLS_V2 = [draft_legal_document,analyze_compliance,review_contract,create_rfp_response,generate_privacy_policy,legal_research,ldr_review,compare_document_versions,ldr_check_compliance]
__all__=["LEGAL_TOOLS_V2"]
