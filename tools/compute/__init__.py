"""
Real-compute engines for the domain tools.

These modules turn agent inputs into *derived* artifacts (DDL, Mermaid
diagrams, AST-based code findings) instead of static templates. Everything
is deterministic and stdlib-only so it runs in CI without Docker, network,
or LLM credentials. Optional analyzers (ruff/bandit) are used only when
present and never cause failures when absent.
"""

from __future__ import annotations

from .architecture import ArchitectureResult, design_architecture
from .code_review import Finding, ReviewResult, review_source
from .schema import Column, SchemaResult, Table, design_schema, parse_entities

__all__ = [
    "design_schema",
    "SchemaResult",
    "Table",
    "Column",
    "parse_entities",
    "design_architecture",
    "ArchitectureResult",
    "review_source",
    "ReviewResult",
    "Finding",
]
