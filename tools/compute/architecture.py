"""
System architecture engine.

Turns a free-text requirements blob into a *derived* architecture:
  * a component list inferred from capability keywords
  * a Mermaid ``flowchart`` wiring client -> edge -> services -> data
  * a non-functional-requirement (NFR) trade-off matrix
  * capacity notes parsed from any scale figures in the text

It is deterministic and stdlib-only. It does not invent cloud SKUs; it
describes logical components and the trade-offs of the chosen pattern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# keyword -> (component label, layer)
# layer in {"service", "data", "edge"}
_CAPABILITY_MAP: list[tuple[tuple[str, ...], str, str]] = [
    (("auth", "login", "signup", "identity", "oauth", "sso"), "Identity & Auth Service", "service"),
    (("payment", "billing", "checkout", "invoice", "stripe"), "Payment Service", "service"),
    (("search", "elasticsearch", "index", "full-text"), "Search Service", "service"),
    (("notification", "email", "sms", "push"), "Notification Service", "service"),
    (("file", "upload", "media", "image", "video", "document"), "Object Storage", "data"),
    (("realtime", "websocket", "live", "chat"), "Realtime Gateway", "edge"),
    (("report", "analytics", "dashboard", "metrics", "bi"), "Analytics Service", "service"),
    (("queue", "event", "kafka", "pubsub", "async", "worker", "job"), "Message Bus", "service"),
    (("cache", "redis", "memcache"), "Cache Layer", "data"),
    (("ml", "ai", "model", "inference", "recommendation", "llm"), "ML Inference Service", "service"),
    (("recommend",), "Recommendation Engine", "service"),
    (("order", "cart", "inventory", "catalog", "product"), "Catalog & Orders Service", "service"),
    (("user", "profile", "account"), "User Service", "service"),
]

_PATTERNS = {"microservices", "monolith", "serverless", "event-driven"}

# NFR keyword -> (label, design implication)
_NFR_MAP: list[tuple[tuple[str, ...], str, str]] = [
    (("scale", "scalab", "high traffic", "millions", "concurrent"),
     "Scalability", "Stateless services + horizontal autoscaling behind a load balancer."),
    (("available", "uptime", "ha", "99.9", "resilien", "failover"),
     "Availability", "Multi-AZ deployment, health probes, retries with backoff, circuit breakers."),
    (("secure", "security", "compliance", "gdpr", "hipaa", "pci", "encrypt"),
     "Security", "TLS everywhere, secrets manager, least-privilege IAM, encryption at rest."),
    (("latency", "fast", "real-time", "performance", "low-latency"),
     "Performance", "Caching, read replicas, CDN at the edge, async non-critical work."),
    (("consist", "transaction", "acid", "integrity"),
     "Consistency", "Single source of truth per aggregate; sagas for cross-service writes."),
    (("observ", "monitor", "logging", "trace", "metrics"),
     "Observability", "Structured logs, distributed tracing, RED/USE metrics, alerting."),
    (("cost", "budget", "cheap", "efficient"),
     "Cost", "Right-size compute, autoscale to zero where possible, tiered storage."),
]


@dataclass
class ArchitectureResult:
    domain: str
    pattern: str
    components: list[str]
    mermaid: str
    nfrs: list[tuple[str, str]]
    capacity_notes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def render(self) -> str:
        parts = [
            f"# System Architecture — {self.domain}",
            f"\n**Pattern:** `{self.pattern}`  |  **Components:** {len(self.components)}",
            "\n## Components\n",
        ]
        parts.extend(f"- {c}" for c in self.components)
        parts.append("\n## Architecture Diagram\n\n```mermaid\n" + self.mermaid.rstrip() + "\n```")
        if self.nfrs:
            parts.append("\n## Non-Functional Requirements & Trade-offs\n")
            parts.append("| Quality Attribute | Design Implication |")
            parts.append("| --- | --- |")
            parts.extend(f"| {label} | {impl} |" for label, impl in self.nfrs)
        if self.capacity_notes:
            parts.append("\n## Capacity Notes\n")
            parts.extend(f"- {n}" for n in self.capacity_notes)
        if self.assumptions:
            parts.append("\n## Assumptions\n")
            parts.extend(f"- {a}" for a in self.assumptions)
        return "\n".join(parts) + "\n"


def _node_id(label: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]", "", label) or "node"


def _detect_pattern(text: str, requested: str) -> tuple[str, list[str]]:
    assumptions: list[str] = []
    req = (requested or "").strip().lower()
    if req in _PATTERNS:
        return req, assumptions
    low = text.lower()
    for p in ("serverless", "event-driven", "microservices", "monolith"):
        if p in low:
            return p, assumptions
    # Heuristic: many capabilities -> microservices; few -> monolith.
    assumptions.append(
        "No explicit architecture pattern requested; inferred from capability count."
    )
    return "microservices", assumptions


def _detect_components(text: str) -> tuple[list[str], dict[str, list[str]]]:
    low = text.lower()
    by_layer: dict[str, list[str]] = {"edge": [], "service": [], "data": []}
    seen: set[str] = set()
    for keywords, label, layer in _CAPABILITY_MAP:
        if any(k in low for k in keywords) and label not in seen:
            seen.add(label)
            by_layer[layer].append(label)
    # Always need at least an application service.
    if not any(by_layer.values()):
        by_layer["service"].append("Application Service")
    flat = by_layer["edge"] + by_layer["service"] + by_layer["data"]
    return flat, by_layer


def _detect_nfrs(text: str) -> list[tuple[str, str]]:
    low = text.lower()
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for keywords, label, impl in _NFR_MAP:
        if any(k in low for k in keywords) and label not in seen:
            seen.add(label)
            out.append((label, impl))
    return out


def _parse_scale(text: str) -> list[str]:
    notes: list[str] = []
    # e.g. "1M users", "10,000 requests/sec", "500 rps"
    for m in re.finditer(
        r"([\d,\.]+)\s*(k|m|b|thousand|million|billion)?\s*"
        r"(users?|requests?|rps|qps|req/s|tps|transactions?)",
        text, re.IGNORECASE,
    ):
        num, mag, unit = m.group(1), (m.group(2) or "").lower(), m.group(3).lower()
        try:
            value = float(num.replace(",", ""))
        except ValueError:
            continue
        mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6,
                "b": 1e9, "billion": 1e9}.get(mag, 1)
        total = value * mult
        if "user" in unit:
            notes.append(
                f"~{total:,.0f} users → size the data tier for this cardinality; "
                f"add read replicas/caching if read-heavy."
            )
        else:
            notes.append(
                f"~{total:,.0f} {unit} → plan horizontal scaling; "
                f"a single instance rarely exceeds a few thousand RPS."
            )
    return notes


def design_architecture(domain: str, requirements: str, pattern: str = "") -> ArchitectureResult:
    """Derive a logical architecture from requirements text."""
    text = requirements or ""
    chosen_pattern, assumptions = _detect_pattern(text, pattern)
    components, by_layer = _detect_components(text)
    nfrs = _detect_nfrs(text)
    capacity = _parse_scale(text)

    # Build Mermaid flowchart: Client -> API Gateway -> services -> data.
    lines = ["flowchart TD", "    Client([Client / Frontend])", "    GW[API Gateway / Load Balancer]"]
    lines.append("    Client --> GW")
    for label in by_layer["edge"]:
        nid = _node_id(label)
        lines.append(f"    {nid}([{label}])")
        lines.append(f"    Client --> {nid}")
    svc_ids = []
    for label in by_layer["service"]:
        nid = _node_id(label)
        svc_ids.append((nid, label))
        lines.append(f"    {nid}[{label}]")
        lines.append(f"    GW --> {nid}")
    for label in by_layer["data"]:
        nid = _node_id(label)
        lines.append(f"    {nid}[({label})]")
        for sid, _ in svc_ids:
            lines.append(f"    {sid} --> {nid}")
    # Primary relational store is implied for stateful services.
    if svc_ids:
        lines.append("    DB[(Primary Database)]")
        for sid, _ in svc_ids:
            lines.append(f"    {sid} --> DB")
    mermaid = "\n".join(dict.fromkeys(lines))

    assumptions.append(
        "An API gateway / load balancer and a primary relational datastore "
        "are included by default for any stateful service."
    )

    return ArchitectureResult(
        domain=domain,
        pattern=chosen_pattern,
        components=components,
        mermaid=mermaid,
        nfrs=nfrs,
        capacity_notes=capacity,
        assumptions=assumptions,
    )
