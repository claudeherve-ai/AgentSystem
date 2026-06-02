"""
AgentSystem — Configuration loader.

Reads environment variables and YAML config files.
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env
load_dotenv(PROJECT_ROOT / ".env")


class MissingModelCredentialsError(RuntimeError):
    """Raised when no LLM provider has usable (non-placeholder) credentials.

    Callers should translate this into a clean, actionable 503 response rather
    than letting it surface as a generic 500.
    """


# Markers that indicate a value is still a template placeholder rather than a
# real secret/endpoint. Template defaults use angle brackets (e.g.
# `<your-azure-openai-key>`), so `<`/`>` catch them without risking false
# positives on legitimate values — an Azure endpoint may legitimately contain
# substrings like "your-company". Keep this list structural and conservative.
# The one literal host fragment below is the exact endpoint shipped in
# `.env.template`; it has no angle brackets, so a copied-but-unedited template
# would otherwise read as a real endpoint and flip ``has_azure_credentials``.
_PLACEHOLDER_MARKERS = (
    "<",
    ">",
    "changeme",
    "change-me",
    "change_me",
    "placeholder",
    "replace-me",
    "replace_me",
    "sk-...",
    "your-resource.cognitiveservices.azure.com",
)


def _clean_env(name: str, default: str = "") -> str:
    """Read an env var and normalize common accidental quoting/spacing."""
    value = os.getenv(name, default)
    if value is None:
        return ""
    return value.strip().strip('"').strip("'")


def _is_placeholder(value: str) -> bool:
    """True if a credential value is empty or a leftover template placeholder."""
    cleaned = (value or "").strip().lower()
    if not cleaned:
        return True
    return any(marker in cleaned for marker in _PLACEHOLDER_MARKERS)


_TRUTHY = {"1", "true", "yes", "on"}


def _clean_bool(name: str, default: bool = False) -> bool:
    """Read a boolean env var, tolerant of common truthy spellings."""
    raw = _clean_env(name, "true" if default else "false").lower()
    return raw in _TRUTHY


def _clean_int(name: str, default: int) -> int:
    """Read an int env var, falling back to ``default`` on anything invalid."""
    try:
        return int(_clean_env(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


class ModelConfig(BaseModel):
    """LLM model configuration."""
    provider: str = Field(default="azure_openai")
    deployment: str = Field(default="gpt-4o")
    temperature: float = Field(default=0.3)
    max_tokens: int = Field(default=4096)

    def _resolved_model_for(self, provider: str) -> str:
        """Resolve the model/deployment name for a specific provider."""
        if provider == "azure_openai":
            return (
                _clean_env("AZURE_OPENAI_CHAT_COMPLETION_MODEL")
                or _clean_env("AZURE_OPENAI_MODEL")
                or _clean_env("AZURE_OPENAI_DEPLOYMENT")
                or self.deployment
            )
        return (
            _clean_env("OPENAI_CHAT_COMPLETION_MODEL")
            or _clean_env("OPENAI_MODEL")
            or self.deployment
        )

    @property
    def resolved_model(self) -> str:
        return self._resolved_model_for(self.provider)

    @property
    def has_azure_credentials(self) -> bool:
        """True when both Azure endpoint and key are present and not placeholders."""
        return not _is_placeholder(self.azure_endpoint) and not _is_placeholder(
            self.azure_api_key
        )

    @property
    def has_openai_credentials(self) -> bool:
        """True when the OpenAI key is present and not a placeholder."""
        return not _is_placeholder(self.openai_api_key)

    @property
    def has_any_model_credentials(self) -> bool:
        """True when at least one supported provider has usable credentials."""
        return self.has_azure_credentials or self.has_openai_credentials

    @property
    def effective_provider(self) -> str:
        """The provider that will actually be used, after credential-aware fallback.

        Prefers the configured provider when it has usable credentials, otherwise
        falls back to whichever supported provider does. Unsupported providers
        (e.g. ``anthropic``) and providers with placeholder creds fall through to
        whatever is usable. Returns the configured provider unchanged when nothing
        is usable, so callers can raise a clear error.
        """
        configured = self.provider
        if configured == "azure_openai" and self.has_azure_credentials:
            return "azure_openai"
        if configured == "openai" and self.has_openai_credentials:
            return "openai"
        if self.has_azure_credentials:
            return "azure_openai"
        if self.has_openai_credentials:
            return "openai"
        return configured

    @property
    def effective_model(self) -> str:
        """Resolved model name for the effective (post-fallback) provider."""
        return self._resolved_model_for(self.effective_provider)

    @property
    def supports_custom_temperature(self) -> bool:
        """
        Whether the current model accepts explicit non-default temperature values.

        Azure GPT-5 chat deployments reject custom temperatures and only accept the
        service default, so we omit the parameter entirely for that family. This
        keys off ``effective_model`` (the provider actually used after
        credential-aware fallback), not the configured one, to avoid sending a
        custom temperature to a GPT-5 deployment reached via fallback.
        """
        return not self.effective_model.lower().startswith("gpt-5")

    @property
    def azure_endpoint(self) -> str:
        return _clean_env("AZURE_OPENAI_ENDPOINT")

    @property
    def azure_api_key(self) -> str:
        return _clean_env("AZURE_OPENAI_API_KEY")

    @property
    def azure_api_version(self) -> str:
        return _clean_env("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    @property
    def openai_api_key(self) -> str:
        return _clean_env("OPENAI_API_KEY")


class SystemConfig(BaseModel):
    """Top-level system configuration."""
    name: str = Field(default="AgentSystem")
    log_level: str = Field(default="INFO")
    approval_required: bool = Field(default=True)
    polling_interval_seconds: int = Field(default=300)


def load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML file from the config directory."""
    config_path = PROJECT_ROOT / "config" / filename
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_system_config() -> SystemConfig:
    """Load system configuration."""
    data = load_yaml("agents.yaml")
    return SystemConfig(**data.get("system", {}))


def get_model_config() -> ModelConfig:
    """Load model configuration."""
    data = load_yaml("agents.yaml")
    return ModelConfig(**data.get("model", {}))


def get_agent_configs() -> dict[str, dict[str, Any]]:
    """Load all agent configurations."""
    data = load_yaml("agents.yaml")
    return data.get("agents", {})


def get_guardrails_config() -> dict[str, Any]:
    """Load guardrails configuration."""
    return load_yaml("guardrails.yaml")


# ---------------------------------------------------------------------------
# PR2 — Sandboxed code execution configuration
# ---------------------------------------------------------------------------

# Execution engines for `tools.code_interpreter.run_python`:
#   auto       -> Docker sandbox if available, else a LOUD subprocess fallback
#                 (never silent: a warning is surfaced in output + audit + telemetry).
#   docker     -> strict; require Docker, never fall back. Refuse if unavailable.
#   subprocess -> legacy host subprocess (NOT a security boundary).
#   off        -> code execution disabled; calls return a clear refusal.
_VALID_SANDBOX_MODES = {"auto", "docker", "subprocess", "off"}


class SandboxConfig(BaseModel):
    """Configuration for sandboxed Python execution (PR2)."""

    mode: str = Field(default="auto")
    image: str = Field(default="python:3.12-slim")
    memory: str = Field(default="256m")
    cpus: str = Field(default="1")
    pids_limit: int = Field(default=128)
    tmpfs_size: str = Field(default="64m")
    timeout_default: int = Field(default=30)
    timeout_max: int = Field(default=120)
    max_code_bytes: int = Field(default=1_000_000)
    max_output_bytes: int = Field(default=32_000)
    auto_pull: bool = Field(default=False)


def get_sandbox_config() -> SandboxConfig:
    """Load sandbox configuration from the environment (all optional)."""
    mode = (_clean_env("CODE_SANDBOX_MODE", "auto") or "auto").lower()
    if mode not in _VALID_SANDBOX_MODES:
        mode = "auto"
    return SandboxConfig(
        mode=mode,
        image=_clean_env("SANDBOX_IMAGE", "python:3.12-slim") or "python:3.12-slim",
        memory=_clean_env("SANDBOX_MEMORY", "256m") or "256m",
        cpus=_clean_env("SANDBOX_CPUS", "1") or "1",
        pids_limit=_clean_int("SANDBOX_PIDS_LIMIT", 128),
        tmpfs_size=_clean_env("SANDBOX_TMPFS_SIZE", "64m") or "64m",
        timeout_default=_clean_int("SANDBOX_TIMEOUT", 30),
        timeout_max=_clean_int("SANDBOX_TIMEOUT_MAX", 120),
        max_code_bytes=_clean_int("SANDBOX_MAX_CODE_BYTES", 1_000_000),
        max_output_bytes=_clean_int("SANDBOX_MAX_OUTPUT_BYTES", 32_000),
        auto_pull=_clean_bool("CODE_SANDBOX_AUTO_PULL", False),
    )


# ---------------------------------------------------------------------------
# PR2 — Self-observability / telemetry configuration
# ---------------------------------------------------------------------------


class TelemetryConfig(BaseModel):
    """Configuration for the built-in tracer (PR2)."""

    enabled: bool = Field(default=True)
    capture_content: bool = Field(default=False)
    api_enabled: bool = Field(default=True)
    max_spans: int = Field(default=500)
    jsonl_enabled: bool = Field(default=False)
    jsonl_path: str = Field(default="")
    otlp_endpoint: str = Field(default="")
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    @property
    def otlp_enabled(self) -> bool:
        """OTLP export is active only when an endpoint is really set."""
        return not _is_placeholder(self.otlp_endpoint)

    @property
    def langfuse_enabled(self) -> bool:
        """Langfuse export needs both keys present and non-placeholder."""
        return not _is_placeholder(self.langfuse_public_key) and not _is_placeholder(
            self.langfuse_secret_key
        )


def get_telemetry_config() -> TelemetryConfig:
    """Load telemetry configuration from the environment (all optional)."""
    default_jsonl = str(PROJECT_ROOT / "data" / "telemetry" / "spans.jsonl")
    return TelemetryConfig(
        enabled=_clean_bool("TELEMETRY_ENABLED", True),
        capture_content=_clean_bool("TELEMETRY_CAPTURE_CONTENT", False),
        api_enabled=_clean_bool("OBSERVABILITY_API_ENABLED", True),
        max_spans=_clean_int("TELEMETRY_MAX_SPANS", 500),
        jsonl_enabled=_clean_bool("TELEMETRY_JSONL_ENABLED", False),
        jsonl_path=_clean_env("TELEMETRY_JSONL_PATH", default_jsonl) or default_jsonl,
        otlp_endpoint=_clean_env("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
        langfuse_public_key=_clean_env("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=_clean_env("LANGFUSE_SECRET_KEY", ""),
        langfuse_host=_clean_env("LANGFUSE_HOST", "https://cloud.langfuse.com")
        or "https://cloud.langfuse.com",
    )


# ---------------------------------------------------------------------------
# PR3 — Multi-model router configuration
# ---------------------------------------------------------------------------


class ModelsConfig(BaseModel):
    """Configuration for the multi-model router (PR3).

    The router itself reads credentials live from :class:`ModelConfig`; this
    only governs whether routing is enabled and where the catalog lives.
    """

    enabled: bool = Field(default=True)
    config_path: str = Field(default="")


def get_models_config() -> ModelsConfig:
    """Load model-router configuration from the environment (all optional)."""
    default_path = str(PROJECT_ROOT / "config" / "models.yaml")
    return ModelsConfig(
        enabled=_clean_bool("MODEL_ROUTER_ENABLED", True),
        config_path=_clean_env("MODEL_ROUTER_CONFIG", default_path) or default_path,
    )


# ---------------------------------------------------------------------------
# PR4 — Durable human-in-the-loop approvals + Azure AI Search
# ---------------------------------------------------------------------------

APPROVAL_MODES = {"auto", "interactive", "durable"}


def _clean_float(name: str, default: float) -> float:
    """Read a float env var, falling back to ``default`` on anything invalid."""
    try:
        return float(_clean_env(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


class ApprovalConfig(BaseModel):
    """Human-in-the-loop approval behaviour (PR4).

    ``mode`` selects how :class:`guardrails.approval.HumanApproval` resolves a
    request for a sensitive action:

      * ``auto`` (default) — preserve historical behaviour: prompt on a TTY,
        otherwise auto-approve. Keeps server/headless runs non-blocking and the
        existing test suite green.
      * ``interactive`` — always require a TTY prompt; if no terminal is
        attached, FAIL CLOSED (never silently auto-approve).
      * ``durable`` — persist a PENDING request to the approval store and block
        until a human decides via ``/api/v1/approvals`` (or the wait times out →
        fail closed). Any store/config failure also fails closed.

    Timeout / poll values apply only to ``durable`` mode and are clamped to safe
    bounds so a misconfigured env can't request a 0s poll or an unbounded wait.
    """

    mode: str = Field(default="auto")
    wait_timeout_seconds: int = Field(default=300)
    poll_interval_seconds: float = Field(default=2.0)

    @property
    def is_durable(self) -> bool:
        return self.mode == "durable"


def get_approval_config() -> ApprovalConfig:
    """Load approval configuration from the environment (all optional)."""
    raw_mode = _clean_env("APPROVAL_MODE", "auto").lower()
    if not raw_mode:
        # Unset / empty preserves historical non-blocking behaviour.
        mode = "auto"
    elif raw_mode in APPROVAL_MODES:
        mode = raw_mode
    else:
        # An explicitly-set but UNKNOWN mode (e.g. a typo like "durabl") must
        # NOT silently fall back to auto-approve — that would fail OPEN. Force
        # the most restrictive mode so a misconfiguration fails closed.
        logger.warning(
            "Unknown APPROVAL_MODE=%r — defaulting to 'durable' (fail-closed).",
            raw_mode,
        )
        mode = "durable"
    # Clamp wait to 1..600s and poll to 0.5..60s; never trust raw env here.
    wait = max(1, min(_clean_int("APPROVAL_WAIT_TIMEOUT", 300), 600))
    poll = max(0.5, min(_clean_float("APPROVAL_POLL_INTERVAL", 2.0), 60.0))
    return ApprovalConfig(
        mode=mode,
        wait_timeout_seconds=wait,
        poll_interval_seconds=poll,
    )


class AzureSearchConfig(BaseModel):
    """Optional Azure AI Search vector backend for case memory (PR4).

    Purely additive: when disabled (no creds, or the SDK is not installed) case
    search falls back to the existing local FTS / embedding index with
    byte-for-byte behaviour.
    """

    endpoint: str = Field(default="")
    api_key: str = Field(default="")
    index_name: str = Field(default="agentsystem-cases")

    @property
    def enabled(self) -> bool:
        return (
            not _is_placeholder(self.endpoint)
            and not _is_placeholder(self.api_key)
        )


def get_azure_search_config() -> AzureSearchConfig:
    """Load Azure AI Search configuration from the environment (all optional)."""
    return AzureSearchConfig(
        endpoint=_clean_env("AZURE_SEARCH_ENDPOINT", ""),
        api_key=_clean_env("AZURE_SEARCH_KEY", ""),
        index_name=_clean_env("AZURE_SEARCH_INDEX", "agentsystem-cases")
        or "agentsystem-cases",
    )
