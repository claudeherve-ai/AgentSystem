"""
toolkits — runtime power-tools that make every agent "boil the ocean".

These are deterministic, stdlib-only, credential-free utility functions that
perform REAL computation (not template interpolation). They are introspected by
the agent framework and attached to agents at registration time.

Two export groups:

- ``POWER_TOOLS_BASE`` — general-purpose tools attached to EVERY agent
  (reasoning, data analysis, diagramming, validation, date/SLA math, text diff).
- ``FINANCE_TOOLS`` — domain tools attached only to finance/revenue/real-estate
  /business agents (NPV/IRR, amortization, SaaS unit economics, investment metrics).

Each tool is a plain function with primitive-typed, ``Annotated`` parameters that
accepts complex inputs as JSON strings and returns Markdown. Tools fail soft —
they return ``"❌ Error: ..."`` strings rather than raising.
"""
from __future__ import annotations

from .dataops import DATAOPS_TOOLS
from .datetime_tools import DATETIME_TOOLS
from .diagram import DIAGRAM_TOOLS
from .finance import FINANCE_TOOLS
from .reasoning import REASONING_TOOLS
from .textutils import TEXT_TOOLS
from .validation import VALIDATION_TOOLS

# General-purpose toolkit attached to every agent.
POWER_TOOLS_BASE = (
    list(REASONING_TOOLS)
    + list(DATAOPS_TOOLS)
    + list(DIAGRAM_TOOLS)
    + list(VALIDATION_TOOLS)
    + list(DATETIME_TOOLS)
    + list(TEXT_TOOLS)
)

__all__ = [
    "POWER_TOOLS_BASE",
    "FINANCE_TOOLS",
    "REASONING_TOOLS",
    "DATAOPS_TOOLS",
    "DIAGRAM_TOOLS",
    "VALIDATION_TOOLS",
    "DATETIME_TOOLS",
    "TEXT_TOOLS",
]
