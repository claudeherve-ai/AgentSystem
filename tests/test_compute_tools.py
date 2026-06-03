"""
Deterministic tests for the real-compute engines and the agent hardening.

These exercise the schema / architecture / code-review engines plus the
BOIL_THE_OCEAN directive injection and the auto-critique gate helpers. They are
fully stdlib-only: no Docker, no network, no LLM credentials required, so they
run green in CI.
"""

from __future__ import annotations

from tools.compute import (
    ArchitectureResult,
    ReviewResult,
    SchemaResult,
    design_architecture,
    design_schema,
    parse_entities,
    review_source,
)


# ── schema engine ─────────────────────────────────────────────────────────
def test_design_schema_emits_ddl_and_erd():
    spec = "User(id:int, email:str unique, name:str), Order(id:int, user_id:int, total:float)"
    result = design_schema("commerce", spec, database_type="postgresql")
    assert isinstance(result, SchemaResult)
    rendered = result.render()
    # Real DDL
    assert "CREATE TABLE" in rendered
    assert "user" in rendered.lower()
    # FK inference: order.user_id -> users
    assert "REFERENCES" in rendered
    # Mermaid ER diagram
    assert "erDiagram" in rendered


def test_parse_entities_handles_grammar():
    tables = parse_entities("Product(id:int, sku:str unique, price:float, note:str?)")
    assert len(tables) == 1
    table = tables[0]
    col_names = {c.name for c in table.columns}
    assert {"id", "sku", "price", "note"}.issubset(col_names)


def test_design_schema_nosql_produces_document():
    result = design_schema("logs", "Event(id:str, payload:str)", database_type="mongodb")
    rendered = result.render()
    assert rendered.strip()  # non-empty doc sketch
    assert "CREATE TABLE" not in rendered  # not relational DDL


def test_untyped_fk_matches_surrogate_pk_type():
    """An untyped FK column must inherit the referenced surrogate PK type.

    Regression: previously `user_id` (no explicit type) defaulted to VARCHAR
    while the referenced `users.id` surrogate PK was BIGINT, producing DDL that
    PostgreSQL/MySQL reject at execution ("incompatible types").
    """
    spec = "User(name:str, email:str unique), Order(total:decimal, status:str, user_id)"
    result = design_schema("commerce", spec, database_type="postgresql")
    # Locate the FK column line in the emitted DDL.
    fk_lines = [ln for ln in result.ddl.splitlines() if '"user_id"' in ln]
    assert fk_lines, "expected a user_id column in the DDL"
    fk_line = fk_lines[0]
    assert "BIGINT" in fk_line, f"FK column should be BIGINT, got: {fk_line!r}"
    assert "VARCHAR" not in fk_line, f"FK column must not be VARCHAR: {fk_line!r}"
    assert "REFERENCES" in fk_line
    # The Mermaid ERD should also reflect the corrected type + FK tag.
    assert "bigint user_id FK" in result.mermaid


def test_explicit_fk_type_is_respected():
    """An explicitly typed FK column keeps the user's declared type."""
    spec = "User(id:int, name:str), Order(id:int, user_id:int, total:float)"
    result = design_schema("commerce", spec, database_type="postgresql")
    fk_lines = [ln for ln in result.ddl.splitlines() if '"user_id"' in ln]
    assert fk_lines
    # id:int -> INTEGER, so the explicit FK stays INTEGER (matches the PK).
    assert "INTEGER" in fk_lines[0]
    assert "BIGINT" not in fk_lines[0]


# ── architecture engine ───────────────────────────────────────────────────
def test_design_architecture_microservices():
    result = design_architecture(
        "payments",
        "high throughput, must scale independently, async processing",
        pattern="microservices",
    )
    assert isinstance(result, ArchitectureResult)
    rendered = result.render()
    assert "flowchart TD" in rendered
    assert result.components  # derived components
    assert result.pattern == "microservices"


def test_design_architecture_defaults_pattern():
    result = design_architecture("blog", "simple CRUD app", pattern="hybrid")
    # hybrid normalizes to auto-selection (empty) and still renders
    assert result.render().strip()


# ── code-review engine ────────────────────────────────────────────────────
def test_review_source_flags_real_issues():
    code = "import os\n\ndef run(cmd=[]):\n    return eval(cmd)\n"
    result = review_source(code, language="python", focus="quality")
    assert isinstance(result, ReviewResult)
    assert result.syntax_ok is True
    assert result.line_count == len(code.splitlines())
    rules = {f.rule for f in result.findings}
    assert "dangerous-call" in rules  # eval
    assert "mutable-default" in rules  # cmd=[]
    assert "ast" in result.tools_run


def test_review_source_security_focus_filters():
    code = "PASSWORD = 'hunter2'\nx = eval('1')\n"
    result = review_source(code, language="python", focus="security")
    rules = {f.rule for f in result.findings}
    assert "hardcoded-secret" in rules


def test_review_source_syntax_error():
    result = review_source("def broken(:\n", language="python")
    assert result.syntax_ok is False
    rules = {f.rule for f in result.findings}
    assert "syntax-error" in rules


def test_review_source_empty_code():
    result = review_source("", language="python")
    assert result.line_count == 0
    # empty code yields notes, not a crash
    assert result.render().strip()


def test_review_source_non_python_heuristics():
    sql = "SELECT * FROM users;\nDELETE FROM users;\n"
    result = review_source(sql, language="sql", focus="quality")
    assert "regex-heuristics" in result.tools_run
    rules = {f.rule for f in result.findings}
    assert "select-star" in rules or "unbounded-delete" in rules


# ── agent hardening: directive + critique gate ─────────────────────────────
class _FakeModelClient:
    """Stand-in chat client so agents build without real credentials in CI."""


def test_boil_the_ocean_directive_injected():
    from main import build_orchestrator

    orch = build_orchestrator()
    # Bypass credential resolution: agents are built lazily against this client.
    orch._model_client = _FakeModelClient()
    name = orch.agent_names[0]
    agent = orch._get_or_create_agent(name)
    assert agent is not None
    # Injected instructions live on the agent's default options, not `.instructions`.
    instructions = agent.default_options["instructions"]
    assert "BOIL THE OCEAN" in instructions
    assert "VERIFY BEFORE YOU CLAIM" in instructions


def test_should_auto_critique_gate():
    from tools.critique import should_auto_critique

    big = "x" * 600
    # high-stakes keyword + substantial draft -> True
    assert should_auto_critique("Please design the database schema for billing", big) is True
    # trivial draft -> False even with keyword
    assert should_auto_critique("design a database schema", "ok") is False
    # no high-stakes keyword -> False
    assert should_auto_critique("say hello", big) is False


def test_has_material_findings_parsing():
    from tools.critique import has_material_findings

    ship = "## Verdict\nShip it — no blocking issues.\n## Critical findings\nNone.\n"
    assert has_material_findings(ship) is False

    flagged = (
        "## Verdict\nNeeds work.\n"
        "## Critical findings\n- SQL injection in the query builder.\n"
    )
    assert has_material_findings(flagged) is True

    assert has_material_findings("") is False
