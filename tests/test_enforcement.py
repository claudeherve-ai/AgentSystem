"""Tests for the enforcement module — domain classifier, grounding check, completion audit.

CITATION: Phase 1 implementation — "Operational discipline" (IMPLEMENTATION_PLAN.md).
"""

import pytest
from enforcement.domain_classifier import (
    classify_domain,
    DOMAIN_RULES,
    DOMAIN_KEYWORDS,
)
from enforcement.grounding_check import (
    verify_grounding,
    _extract_tool_calls_from_response,
)
from enforcement.completion_audit import (
    audit_completion,
    COMPLETION_SIGNALS,
    COMMENTARY_SIGNALS,
)


# ═══════════════════════════════════════════════════════════════════════════
# Domain Classifier Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDomainClassifier:
    """Test keyword-based domain classification."""

    def test_email_domain(self):
        result = classify_domain("check my email inbox")
        assert "email" in result.domains
        assert "EmailAgent" in result.required_specialists

    def test_calendar_domain(self):
        result = classify_domain("what's on my calendar tomorrow")
        assert "calendar" in result.domains
        assert "CalendarAgent" in result.required_specialists

    def test_azure_domain(self):
        result = classify_domain("how do I deploy to Azure using Bicep")
        assert "microsoft_azure" in result.domains
        assert "microsoft_docs_search" in result.required_tools

    def test_code_domain(self):
        result = classify_domain("write a Python function to sort a list")
        assert "code_generation" in result.domains
        assert "run_python" in result.required_tools

    def test_architecture_domain_is_high_stakes(self):
        result = classify_domain("design a microservice architecture for our platform")
        assert result.is_high_stakes
        assert "critique_response" in result.required_tools

    def test_security_domain(self):
        result = classify_domain("review this code for security vulnerabilities")
        assert "security" in result.domains
        assert "SecurityEngineerAgent" in result.required_specialists

    def test_finance_domain(self):
        result = classify_domain("calculate my quarterly tax estimate")
        assert "finance" in result.domains
        assert "run_python" in result.required_tools

    def test_legal_domain(self):
        result = classify_domain("review this NDA contract")
        assert "legal" in result.domains
        assert "LegalAgent" in result.required_specialists

    def test_customer_case_domain(self):
        result = classify_domain("look at case SR 12345")
        assert "customer_case" in result.domains
        assert "case_search" in result.required_tools

    def test_local_file_domain(self):
        result = classify_domain("read the file at /tmp/data.csv")
        assert "local_file" in result.domains
        assert "read_file" in result.required_tools

    def test_multi_domain_union(self):
        """When a task matches multiple domains, union the requirements."""
        result = classify_domain("design and implement a secure Azure architecture")
        domains = result.domains
        assert "microsoft_azure" in domains or "architecture_design" in domains
        # Should pull from multiple domains
        assert len(result.required_specialists) >= 1
        assert len(result.required_tools) >= 1

    def test_unknown_task_defaults_to_research(self):
        result = classify_domain("hello how are you")
        assert "research" in result.domains
        assert result.confidence < 0.5

    def test_confidence_scoring(self):
        """High keyword matches should yield higher confidence."""
        result_strong = classify_domain("check my email inbox for unread messages from Microsoft about Azure billing")
        result_weak = classify_domain("hi")
        assert result_strong.confidence > result_weak.confidence

    def test_all_domains_have_rules(self):
        """Every keyword domain must have a corresponding DOMAIN_RULES entry."""
        for domain in DOMAIN_KEYWORDS:
            assert domain in DOMAIN_RULES, f"Missing DOMAIN_RULES entry for '{domain}'"


# ═══════════════════════════════════════════════════════════════════════════
# Grounding Check Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestGroundingCheck:
    """Test post-hoc grounding verification."""

    def test_fully_grounded_response(self):
        response = (
            "Based on the web search, I found that Azure Container Apps supports "
            "GPU workloads in preview. According to Microsoft Docs (https://learn.microsoft.com/...), "
            "you can configure GPU profiles in the container app YAML."
        )
        result = verify_grounding(
            response,
            required_tools=["web_search", "microsoft_docs_search"],
            domains=["microsoft_azure"],
            specialist_name="CloudDataAgent",
        )
        assert result.passed
        assert result.evidence_quality == "full"

    def test_missing_grounding(self):
        response = (
            "Azure Container Apps is a great choice. You should consider using it "
            "for your deployment. In general, containerized apps work well on Azure."
        )
        result = verify_grounding(
            response,
            required_tools=["microsoft_docs_search", "web_search"],
            domains=["microsoft_azure"],
            specialist_name="CloudDataAgent",
        )
        assert not result.passed
        assert result.evidence_quality == "none"
        assert len(result.missing_tools) > 0

    def test_partial_grounding(self):
        response = (
            "I searched for this and found some info. Based on web search results, "
            "the best approach would be..."
        )
        result = verify_grounding(
            response,
            required_tools=["web_search", "microsoft_docs_search"],
            domains=["microsoft_azure"],
            specialist_name="CloudDataAgent",
        )
        assert result.evidence_quality in ("partial", "full")

    def test_no_tools_required(self):
        response = "Here's your social media post draft."
        result = verify_grounding(
            response,
            required_tools=[],
            domains=["social_media"],
            specialist_name="SocialAgent",
        )
        assert result.passed
        assert result.evidence_quality == "full"

    def test_code_as_evidence(self):
        response = (
            "Here's the implementation:\n```python\ndef sort_list(lst):\n    return sorted(lst)\n```\n"
            "I ran it and verified it works."
        )
        result = verify_grounding(
            response,
            required_tools=["run_python"],
            domains=["code_generation"],
            specialist_name="EngineeringAgent",
        )
        assert result.passed

    def test_annotation_when_failing(self):
        response = "You should use Azure Functions for that."
        result = verify_grounding(
            response,
            required_tools=["microsoft_docs_search"],
            domains=["microsoft_azure"],
            specialist_name="CloudDataAgent",
        )
        assert not result.passed
        assert result.annotation
        assert "Grounding gap" in result.annotation


# ═══════════════════════════════════════════════════════════════════════════
# Completion Audit Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestCompletionAudit:
    """Test completion vs. commentary detection."""

    def test_completed_response(self):
        response = (
            "I've created the deployment script. Here's the result:\n"
            "```bash\naz containerapp update ...\n```\n"
            "Task completed — the app is now deployed with the new configuration."
        )
        result = audit_completion(response)
        assert result.completed
        assert result.completion_signals_count > 0

    def test_commentary_only_response(self):
        response = (
            "You could deploy this using Azure Container Apps. Here's how you could "
            "set it up: first, you would need to create a resource group. Then you might "
            "want to configure the container. I recommend using Bicep for infrastructure."
        )
        result = audit_completion(response)
        assert not result.completed
        assert result.commentary_signals_count > result.completion_signals_count

    def test_code_plus_evidence_overrides_commentary(self):
        response = (
            "I suggest using this approach:\n```python\nresult = compute_metrics(data)\n```\n"
            "Based on the web search, this is the recommended pattern."
        )
        result = audit_completion(response)
        assert result.completed
        assert result.has_code
        assert result.has_evidence

    def test_short_direct_answer(self):
        response = "Your inbox has 3 unread messages."
        result = audit_completion(response)
        assert result.completed

    def test_empty_response(self):
        result = audit_completion("")
        assert not result.completed
        assert "Empty" in result.annotation

    def test_annotation_when_commentary_heavy(self):
        response = (
            "You could implement this in several ways. I recommend using a microservice "
            "architecture. Here's how you can start: first, you would need to..."
        )
        result = audit_completion(response)
        if not result.completed:
            assert result.annotation
            assert "Completion gap" in result.annotation

    def test_mixed_but_completed(self):
        response = (
            "I recommend using this pattern. I've written the implementation below.\n"
            "```python\ndef handler():\n    pass\n```\n"
            "I verified it works. Task completed."
        )
        result = audit_completion(response)
        # Should be completed because code + evidence overrides commentary
        assert result.completed


# ═══════════════════════════════════════════════════════════════════════════
# Integration: end-to-end enforcement pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestEnforcementPipeline:
    """Test the full classification → grounding → completion pipeline."""

    def test_pipeline_on_well_grounded_response(self):
        from enforcement.domain_classifier import classify_domain
        from enforcement.grounding_check import verify_grounding
        from enforcement.completion_audit import audit_completion

        task = "design and implement a secure Azure microservice architecture"
        response = (
            "Based on Microsoft Docs (https://learn.microsoft.com/azure/architecture/), "
            "I've designed the following architecture. After reviewing my draft with a "
            "self-review, here's the final output:\n"
            "```python\n# Implementation\n```\n"
            "I ran the code and verified it works. Source: Azure Architecture Center."
        )

        # Step 1: Classify
        domain = classify_domain(task)
        assert domain.is_high_stakes

        # Step 2: Verify grounding
        grounding = verify_grounding(
            response,
            required_tools=domain.required_tools,
            domains=domain.domains,
            specialist_name="EngineeringAgent",
        )
        assert grounding.passed

        # Step 3: Audit completion
        completion = audit_completion(response)
        assert completion.completed

        # Full pipeline passes
        assert grounding.passed and completion.completed

    def test_pipeline_flags_ungrounded_commentary(self):
        from enforcement.domain_classifier import classify_domain
        from enforcement.grounding_check import verify_grounding
        from enforcement.completion_audit import audit_completion

        task = "how do I deploy to Azure with Bicep"
        response = (
            "You could use Bicep for Azure deployments. Here's how you can start: "
            "first, you might want to install the Bicep CLI. I recommend using "
            "modules for reusability. In general, declarative IaC works well."
        )

        domain = classify_domain(task)
        grounding = verify_grounding(
            response,
            required_tools=domain.required_tools,
            domains=domain.domains,
            specialist_name="CloudDataAgent",
        )
        completion = audit_completion(response)

        # Should flag issues
        assert not grounding.passed or not completion.completed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
