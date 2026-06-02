"""
AgentSystem — Configuration loader.

Reads environment variables and YAML config files.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

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
