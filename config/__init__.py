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


def _clean_env(name: str, default: str = "") -> str:
    """Read an env var and normalize common accidental quoting/spacing."""
    value = os.getenv(name, default)
    if value is None:
        return ""
    return value.strip().strip('"').strip("'")


class ModelConfig(BaseModel):
    """LLM model configuration."""
    provider: str = Field(default="azure_openai")
    deployment: str = Field(default="gpt-4o")
    temperature: float = Field(default=0.3)
    max_tokens: int = Field(default=4096)

    @property
    def resolved_model(self) -> str:
        if self.provider == "azure_openai":
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
    def supports_custom_temperature(self) -> bool:
        """
        Whether the current model accepts explicit non-default temperature values.

        Azure GPT-5 chat deployments reject custom temperatures and only accept the
        service default, so we omit the parameter entirely for that family.
        """
        return not self.resolved_model.lower().startswith("gpt-5")

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
