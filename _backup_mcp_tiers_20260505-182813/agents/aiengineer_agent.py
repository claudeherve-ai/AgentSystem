"""
AgentSystem — AI Engineer Agent.

AI/ML implementation specialist agent for designing pipelines, crafting
prompt templates, evaluating models, designing recommendation engines,
and planning AI feature integrations.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


async def design_ml_pipeline(
    task_description: Annotated[str, "Description of the ML task to solve"],
    data_description: Annotated[str, "Description of available data"] = "",
    constraints: Annotated[str, "Budget, latency, compliance, or infra constraints"] = "",
) -> str:
    """
    Design an ML pipeline architecture. Returns pipeline stages, model
    recommendations, and data requirements.
    """
    log_action(
        "AIEngineerAgent",
        "design_ml_pipeline",
        f"task={task_description[:100]}, has_data={bool(data_description)}, has_constraints={bool(constraints)}",
    )

    pipeline = (
        f"🤖 ML PIPELINE DESIGN\n"
        f"{'═' * 50}\n\n"
        f"**Task:** {task_description}\n"
    )

    if data_description:
        pipeline += f"**Data:** {data_description}\n"
    if constraints:
        pipeline += f"**Constraints:** {constraints}\n"

    pipeline += (
        f"\n**Pipeline Stages:**\n\n"
        f"  1. DATA INGESTION\n"
        f"     → Collect, validate, and version raw data.\n"
        f"     Tools: Azure Data Factory, Databricks Auto Loader\n\n"
        f"  2. DATA PREPARATION\n"
        f"     → Clean, transform, feature engineering.\n"
        f"     Tools: PySpark, pandas, Delta Lake\n\n"
        f"  3. MODEL TRAINING\n"
        f"     → Train candidate models with cross-validation.\n"
        f"     Tools: MLflow, scikit-learn, PyTorch, or LLM fine-tuning\n\n"
        f"  4. EVALUATION\n"
        f"     → Metrics, fairness checks, bias analysis.\n"
        f"     Tools: MLflow tracking, responsible AI dashboard\n\n"
        f"  5. DEPLOYMENT\n"
        f"     → Serve via REST endpoint with monitoring.\n"
        f"     Tools: Databricks Model Serving, Azure ML endpoints\n\n"
        f"  6. MONITORING & FEEDBACK\n"
        f"     → Data drift detection, performance tracking, retraining triggers.\n"
        f"     Tools: Databricks Lakehouse Monitoring, custom alerts\n\n"
        f"**Model Recommendations:**\n"
        f"  • Start with a strong baseline (e.g., gradient boosting or pre-trained LLM).\n"
        f"  • Iterate based on evaluation metrics before optimizing.\n"
        f"{'═' * 50}"
    )

    return pipeline


async def generate_prompt_template(
    use_case: Annotated[str, "The use case for the prompt (e.g., summarization, Q&A)"],
    input_variables: Annotated[str, "Comma-separated list of input variable names"],
    tone: Annotated[str, "Desired tone: professional, casual, technical, friendly"] = "professional",
    max_tokens: Annotated[int, "Maximum token budget for the response"] = 4096,
) -> str:
    """
    Create an optimized prompt template for LLM integration.
    Returns the prompt template with placeholders for the specified input variables.
    """
    variables = [v.strip() for v in input_variables.split(",") if v.strip()]

    log_action(
        "AIEngineerAgent",
        "generate_prompt_template",
        f"use_case={use_case[:80]}, variables={variables}, tone={tone}",
    )

    placeholders = "\n".join(f"  {{{{{v}}}}}" for v in variables)

    template = (
        f"📝 PROMPT TEMPLATE\n"
        f"{'═' * 50}\n\n"
        f"**Use Case:** {use_case}\n"
        f"**Tone:** {tone}\n"
        f"**Max Tokens:** {max_tokens}\n"
        f"**Variables:** {', '.join(variables)}\n\n"
        f"--- TEMPLATE START ---\n\n"
        f"You are a {tone} assistant specializing in {use_case}.\n\n"
        f"Given the following inputs:\n"
        f"{placeholders}\n\n"
        f"Please provide a clear, accurate, and {tone} response that\n"
        f"addresses the user's request. Keep the response concise and\n"
        f"within {max_tokens} tokens.\n\n"
        f"If you are unsure about any aspect, state your uncertainty\n"
        f"rather than guessing.\n\n"
        f"--- TEMPLATE END ---\n\n"
        f"**Usage Notes:**\n"
        f"  • Replace placeholders with actual values at runtime.\n"
        f"  • Adjust system prompt and temperature based on task needs.\n"
        f"  • Test with diverse inputs before deploying to production.\n"
        f"{'═' * 50}"
    )

    return template


async def evaluate_model_options(
    task_type: Annotated[str, "Type of ML/AI task (e.g., classification, generation, embedding)"],
    requirements: Annotated[str, "Specific requirements (latency, accuracy, privacy)"] = "",
    budget: Annotated[str, "Budget constraints (e.g., $100/month, cost-sensitive)"] = "",
) -> str:
    """
    Compare model options (GPT-4o, Claude, Llama, etc.) for a given task.
    Returns a comparison table with pros, cons, and estimated costs.
    """
    log_action(
        "AIEngineerAgent",
        "evaluate_model_options",
        f"task_type={task_type}, requirements={requirements[:80]}, budget={budget}",
    )

    comparison = (
        f"📊 MODEL COMPARISON\n"
        f"{'═' * 60}\n\n"
        f"**Task:** {task_type}\n"
    )

    if requirements:
        comparison += f"**Requirements:** {requirements}\n"
    if budget:
        comparison += f"**Budget:** {budget}\n"

    comparison += (
        f"\n{'─' * 60}\n"
        f"{'Model':<20} {'Strengths':<20} {'Weaknesses':<20}\n"
        f"{'─' * 60}\n"
        f"{'GPT-4o':<20} {'Quality, tooling':<20} {'Cost, vendor lock':<20}\n"
        f"{'Claude Sonnet':<20} {'Long context, safety':<20} {'Availability':<20}\n"
        f"{'Llama 3':<20} {'Open-source, private':<20} {'Infra required':<20}\n"
        f"{'Mistral':<20} {'Speed, efficiency':<20} {'Smaller community':<20}\n"
        f"{'Gemini Pro':<20} {'Multimodal':<20} {'API maturity':<20}\n"
        f"{'─' * 60}\n\n"
        f"**Cost Estimates (per 1M tokens):**\n"
        f"  • GPT-4o:        ~$2.50 input / ~$10.00 output\n"
        f"  • Claude Sonnet:  ~$3.00 input / ~$15.00 output\n"
        f"  • Llama 3 (self): Infrastructure cost only\n"
        f"  • Mistral:        ~$0.25 input / ~$0.25 output\n\n"
        f"**Recommendation:**\n"
        f"  For '{task_type}': Start with a hosted API (GPT-4o or Claude)\n"
        f"  for rapid prototyping, then evaluate open-source alternatives\n"
        f"  if cost or privacy requirements dictate.\n"
        f"{'═' * 60}"
    )

    return comparison


async def design_recommendation_engine(
    item_type: Annotated[str, "Type of items to recommend (products, content, users)"],
    user_signals: Annotated[str, "Available user signals (clicks, purchases, ratings, views)"],
    cold_start_strategy: Annotated[str, "Strategy for new users: popular, content-based, hybrid"] = "popular",
) -> str:
    """
    Design a recommendation system architecture. Returns algorithm choice,
    data flow, and implementation plan.
    """
    log_action(
        "AIEngineerAgent",
        "design_recommendation_engine",
        f"item_type={item_type}, signals={user_signals[:80]}, cold_start={cold_start_strategy}",
    )

    design = (
        f"🎯 RECOMMENDATION ENGINE DESIGN\n"
        f"{'═' * 50}\n\n"
        f"**Item Type:** {item_type}\n"
        f"**User Signals:** {user_signals}\n"
        f"**Cold Start Strategy:** {cold_start_strategy}\n\n"
        f"**Algorithm Selection:**\n"
        f"  • Primary: Collaborative Filtering (ALS matrix factorization)\n"
        f"  • Secondary: Content-based filtering on item features\n"
        f"  • Hybrid: Weighted ensemble of both approaches\n\n"
        f"**Data Flow:**\n"
        f"  1. Ingest user interaction events → Delta Lake\n"
        f"  2. Feature engineering: user profiles, item embeddings\n"
        f"  3. Model training (batch): Spark ALS or neural CF\n"
        f"  4. Serve recommendations via low-latency endpoint\n"
        f"  5. Log impressions and clicks for feedback loop\n\n"
        f"**Cold Start Handling ({cold_start_strategy}):**\n"
    )

    if cold_start_strategy == "popular":
        design += "  → Serve globally popular items until enough signals are collected.\n"
    elif cold_start_strategy == "content-based":
        design += "  → Use item metadata and user profile attributes for initial recs.\n"
    else:
        design += "  → Blend popularity with content signals, increasing personalization over time.\n"

    design += (
        f"\n**Implementation Plan:**\n"
        f"  Phase 1: Data pipeline and feature store (2 weeks)\n"
        f"  Phase 2: Baseline model training and offline eval (1 week)\n"
        f"  Phase 3: Serving endpoint and A/B test framework (1 week)\n"
        f"  Phase 4: Online evaluation and iteration (ongoing)\n"
        f"{'═' * 50}"
    )

    return design


async def create_ai_integration_plan(
    feature_description: Annotated[str, "Description of the AI feature to integrate"],
    existing_stack: Annotated[str, "Current technology stack"] = "",
    timeline: Annotated[str, "Desired timeline for delivery"] = "",
) -> str:
    """
    Create an end-to-end AI feature integration plan.
    Returns phases, milestones, and technical requirements.
    """
    log_action(
        "AIEngineerAgent",
        "create_ai_integration_plan",
        f"feature={feature_description[:100]}, has_stack={bool(existing_stack)}, timeline={timeline}",
    )

    plan = (
        f"🚀 AI INTEGRATION PLAN\n"
        f"{'═' * 50}\n\n"
        f"**Feature:** {feature_description}\n"
    )

    if existing_stack:
        plan += f"**Existing Stack:** {existing_stack}\n"
    if timeline:
        plan += f"**Timeline:** {timeline}\n"

    plan += (
        f"\n**Phase 1: Discovery & Design (Week 1–2)**\n"
        f"  • Define success metrics and acceptance criteria.\n"
        f"  • Select model(s) and hosting strategy.\n"
        f"  • Design API contract and data flow.\n"
        f"  Milestone: Approved design document.\n\n"
        f"**Phase 2: Prototype (Week 3–4)**\n"
        f"  • Implement core AI logic with mock data.\n"
        f"  • Build prompt templates or training pipeline.\n"
        f"  • Integration smoke tests.\n"
        f"  Milestone: Working prototype in dev environment.\n\n"
        f"**Phase 3: Integration & Testing (Week 5–6)**\n"
        f"  • Connect to production data sources.\n"
        f"  • Load testing, latency benchmarks, cost projections.\n"
        f"  • Responsible AI review (bias, fairness, safety).\n"
        f"  Milestone: Passing integration tests and AI review.\n\n"
        f"**Phase 4: Rollout & Monitoring (Week 7–8)**\n"
        f"  • Staged rollout with feature flags.\n"
        f"  • Dashboards for quality, latency, cost.\n"
        f"  • Feedback loop for continuous improvement.\n"
        f"  Milestone: GA release with monitoring in place.\n\n"
        f"**Technical Requirements:**\n"
        f"  • API endpoint for model inference\n"
        f"  • Secrets management for API keys\n"
        f"  • Logging and observability pipeline\n"
        f"  • Fallback behavior when AI service is unavailable\n"
        f"{'═' * 50}"
    )

    return plan


# List of tools to register with the AI engineer agent
AIENGINEER_TOOLS = [
    design_ml_pipeline,
    generate_prompt_template,
    evaluate_model_options,
    design_recommendation_engine,
    create_ai_integration_plan,
]
