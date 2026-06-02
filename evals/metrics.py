"""AgentSystem — Online LLM-quality metrics (PR3).

Thin wrapper around DeepEval's answer-relevancy metric with **two structured
skips** so it never hard-fails an offline/CI environment:

1. No LLM credentials configured  -> skip ``missing_llm_credentials``.
2. The optional ``deepeval`` package is not installed -> skip
   ``deepeval_not_installed``.

Only when both are satisfied do we actually call the model (via the credential-
aware router) and score the response. This module is import-safe without
``deepeval`` installed and without any credentials.
"""

from __future__ import annotations

import asyncio
from typing import Any

from config import MissingModelCredentialsError, get_model_config
from routing import ModelCatalogError, get_router


class MetricSkipped(Exception):
    """Raised to signal a metric was skipped for a structural reason."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _ensure_credentials() -> None:
    if not get_model_config().has_any_model_credentials:
        raise MetricSkipped("missing_llm_credentials")


def _import_deepeval() -> tuple[Any, Any]:
    try:
        from deepeval.metrics import AnswerRelevancyMetric  # type: ignore
        from deepeval.test_case import LLMTestCase  # type: ignore
    except Exception:  # pragma: no cover - exercised only when installed
        raise MetricSkipped("deepeval_not_installed")
    return AnswerRelevancyMetric, LLMTestCase


async def _generate(profile: str, prompt: str) -> str:
    """Build a minimal agent on the routed client and return its text reply."""
    from agent_framework import Agent  # local import keeps module import cheap

    client = get_router().build_client(profile)
    agent = Agent(
        name="EvalProbe",
        description="Ephemeral agent used only for evaluation.",
        client=client,
        instructions="You are a concise, helpful assistant. Answer directly.",
    )
    result = await agent.run(prompt)
    return str(getattr(result, "text", "") or "")


def answer_relevancy(
    *, profile: str, input_text: str, threshold: float = 0.5
) -> dict[str, Any]:
    """Score answer relevancy for ``input_text`` using the routed model.

    Raises :class:`MetricSkipped` (with a machine-readable ``reason``) when the
    check cannot run because credentials, the catalog, or ``deepeval`` are
    unavailable. Returns a secret-free result dict on success.
    """
    _ensure_credentials()
    answer_relevancy_metric, llm_test_case = _import_deepeval()

    try:
        actual_output = asyncio.run(_generate(profile, input_text))
    except MissingModelCredentialsError:
        # Router walked the whole chain and found no usable provider.
        raise MetricSkipped("missing_llm_credentials")
    except ModelCatalogError:
        raise MetricSkipped("model_catalog_invalid")

    metric = answer_relevancy_metric(threshold=threshold)
    test_case = llm_test_case(input=input_text, actual_output=actual_output)
    metric.measure(test_case)
    return {
        "score": getattr(metric, "score", None),
        "threshold": threshold,
        "passed": bool(metric.is_successful()),
    }
