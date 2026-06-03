"""
Database schema engine.

Parses an entity specification into real tables/columns and emits:
  * CREATE TABLE DDL for a chosen SQL dialect (postgresql / mysql / sqlite)
  * a Mermaid ``erDiagram`` reflecting inferred relationships
  * an "Assumptions" section documenting every inference made

For NoSQL targets (mongodb / dynamodb) it deliberately refuses to emit fake
SQL and returns a document-model sketch instead.

Entity spec formats accepted (mix freely, comma- or newline-separated):
    users, orders, products
    User(name:str, email:str unique, age:int?)
    Order(total:decimal, status:str, user_id)

Field grammar inside parentheses:
    <name>[:<type>] [unique] [?]      # '?' marks nullable, default NOT NULL
A trailing ``_id`` field becomes a foreign key *only* when the referenced
table is unambiguously present; otherwise it is flagged as a candidate FK.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

SQL_DIALECTS = {"postgresql", "postgres", "mysql", "sqlite"}
NOSQL_DIALECTS = {"mongodb", "mongo", "dynamodb", "dynamo"}

# Canonical type -> per-dialect physical type.
_TYPE_MAP = {
    "postgresql": {
        "int": "INTEGER", "integer": "INTEGER", "bigint": "BIGINT",
        "str": "VARCHAR(255)", "string": "VARCHAR(255)", "text": "TEXT",
        "bool": "BOOLEAN", "boolean": "BOOLEAN",
        "float": "DOUBLE PRECISION", "double": "DOUBLE PRECISION",
        "decimal": "NUMERIC(12,2)", "money": "NUMERIC(12,2)",
        "date": "DATE", "datetime": "TIMESTAMPTZ", "timestamp": "TIMESTAMPTZ",
        "uuid": "UUID", "json": "JSONB", "jsonb": "JSONB",
    },
    "mysql": {
        "int": "INT", "integer": "INT", "bigint": "BIGINT",
        "str": "VARCHAR(255)", "string": "VARCHAR(255)", "text": "TEXT",
        "bool": "TINYINT(1)", "boolean": "TINYINT(1)",
        "float": "DOUBLE", "double": "DOUBLE",
        "decimal": "DECIMAL(12,2)", "money": "DECIMAL(12,2)",
        "date": "DATE", "datetime": "DATETIME", "timestamp": "TIMESTAMP",
        "uuid": "CHAR(36)", "json": "JSON", "jsonb": "JSON",
    },
    "sqlite": {
        "int": "INTEGER", "integer": "INTEGER", "bigint": "INTEGER",
        "str": "TEXT", "string": "TEXT", "text": "TEXT",
        "bool": "INTEGER", "boolean": "INTEGER",
        "float": "REAL", "double": "REAL",
        "decimal": "NUMERIC", "money": "NUMERIC",
        "date": "TEXT", "datetime": "TEXT", "timestamp": "TEXT",
        "uuid": "TEXT", "json": "TEXT", "jsonb": "TEXT",
    },
}

_PK_TYPE = {
    "postgresql": "BIGINT GENERATED ALWAYS AS IDENTITY",
    "mysql": "BIGINT AUTO_INCREMENT",
    "sqlite": "INTEGER",
}

_QUOTE = {"postgresql": '"', "mysql": "`", "sqlite": '"'}


@dataclass
class Column:
    name: str
    canonical_type: str
    nullable: bool = False
    unique: bool = False
    is_pk: bool = False
    fk_table: Optional[str] = None  # resolved referenced table, if any
    explicit_type: bool = False  # True if the user typed `field:type` explicitly


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)


@dataclass
class SchemaResult:
    domain: str
    dialect: str
    tables: list[Table]
    ddl: str
    mermaid: str
    warnings: list[str]
    is_sql: bool

    def render(self) -> str:
        parts = [
            f"# Database Schema — {self.domain}",
            f"\n**Target:** `{self.dialect}`  |  **Tables:** {len(self.tables)}",
        ]
        if not self.is_sql:
            parts.append("\n" + self.ddl)  # document-model sketch lives in ddl
        else:
            parts.append("\n## DDL\n\n```sql\n" + self.ddl.rstrip() + "\n```")
            parts.append("\n## Entity-Relationship Diagram\n\n```mermaid\n" + self.mermaid.rstrip() + "\n```")
        if self.warnings:
            parts.append("\n## Assumptions & Notes\n")
            parts.extend(f"- {w}" for w in self.warnings)
        return "\n".join(parts) + "\n"


def _sanitize_ident(raw: str) -> str:
    """Lower-snake a token into a safe SQL identifier (never empty)."""
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", raw.strip()).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned:
        cleaned = "col"
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned.lower()


def _pluralize(name: str) -> str:
    if name.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    if name.endswith("y") and name[-2:-1] not in "aeiou":
        return name[:-1] + "ies"
    return name + "s"


def _singular(name: str) -> str:
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("es") and name[:-2].endswith(("s", "x", "z", "ch", "sh")):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


# Entity-with-fields:  Name(field, field, ...)
_ENTITY_RE = re.compile(r"^\s*([A-Za-z_][\w ]*)\s*\((.*)\)\s*$", re.DOTALL)


def _split_top_level(spec: str) -> list[str]:
    """Split on commas/newlines that are NOT inside parentheses."""
    out, buf, depth = [], [], 0
    for ch in spec:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch in ",\n" and depth == 0:
            token = "".join(buf).strip()
            if token:
                out.append(token)
            buf = []
        else:
            buf.append(ch)
    token = "".join(buf).strip()
    if token:
        out.append(token)
    return out


def _parse_field(token: str) -> Optional[Column]:
    token = token.strip()
    if not token:
        return None
    nullable = token.endswith("?") or " null" in f" {token.lower()} "
    token = token.rstrip("?").strip()
    unique = bool(re.search(r"\bunique\b", token, re.IGNORECASE))
    token = re.sub(r"\b(unique|null|not null)\b", "", token, flags=re.IGNORECASE).strip()
    if ":" in token:
        raw_name, raw_type = token.split(":", 1)
        explicit = True
    else:
        raw_name, raw_type = token, "str"
        explicit = False
    name = _sanitize_ident(raw_name)
    ctype = raw_type.strip().lower() or "str"
    return Column(
        name=name,
        canonical_type=ctype,
        nullable=nullable,
        unique=unique,
        explicit_type=explicit,
    )


def parse_entities(spec: str) -> list[Table]:
    tables: list[Table] = []
    seen: set[str] = set()
    for token in _split_top_level(spec):
        m = _ENTITY_RE.match(token)
        if m:
            raw_name, body = m.group(1), m.group(2)
            cols = [c for c in (_parse_field(f) for f in _split_top_level(body)) if c]
        else:
            raw_name, cols = token, []
        tname = _pluralize(_sanitize_ident(raw_name))
        if tname in seen:
            continue
        seen.add(tname)
        tables.append(Table(name=tname, columns=cols))
    return tables


def _base_type(phys: str) -> str:
    """Strip size/precision and modifiers to a bare Mermaid-safe type token."""
    return re.sub(r"\(.*\)", "", phys).split()[0].lower()


def _resolve_type(dialect: str, canonical: str) -> tuple[str, list[str]]:
    table = _TYPE_MAP[dialect]
    warns: list[str] = []
    phys = table.get(canonical)
    if phys is None:
        phys = table["str"]
        warns.append(f"Unknown type `{canonical}` mapped to `{phys}` (default).")
    return phys, warns


def _build_sql(domain: str, dialect: str, tables: list[Table]) -> SchemaResult:
    q = _QUOTE[dialect]
    table_names = {t.name for t in tables}
    warnings: list[str] = []
    ddl_blocks: list[str] = []
    mermaid_lines = ["erDiagram"]
    rels: list[str] = []

    def quote(ident: str) -> str:
        return f"{q}{ident}{q}"

    # Resolve each table's primary-key canonical type up front so foreign-key
    # columns can be typed to MATCH the key they reference. A surrogate PK is
    # `bigint`; an explicit id/pk column uses whatever type the user declared.
    # Without this, an untyped `user_id` defaults to `str`/VARCHAR and produces
    # DDL that PostgreSQL/MySQL reject ("incompatible types: ... and bigint").
    pk_canonical: dict[str, str] = {}
    for t in tables:
        explicit_pk = next((c for c in t.columns if c.name in ("id", "pk")), None)
        pk_canonical[t.name] = explicit_pk.canonical_type if explicit_pk else "bigint"

    for t in tables:
        # Surrogate PK unless the user supplied an explicit id/pk column.
        has_pk = any(c.name in ("id", "pk") for c in t.columns)
        lines: list[str] = []
        merm_cols: list[str] = []
        if not has_pk:
            lines.append(f"    {quote('id')} {_PK_TYPE[dialect]} PRIMARY KEY")
            merm_cols.append("        bigint id PK")
        index_cols: list[str] = []
        for col in t.columns:
            if col.name in ("id", "pk"):
                col.is_pk = True
            # Foreign-key inference: <singular_table>_id -> that table. Resolve
            # the target BEFORE picking the physical type so an untyped FK can
            # inherit the referenced PK's type and keep the DDL executable.
            fk_target = None
            if col.name.endswith("_id") and not col.is_pk:
                base = col.name[:-3]
                cand = _pluralize(base)
                if cand in table_names:
                    fk_target = cand
                elif base in table_names:
                    fk_target = base
            if fk_target and not col.explicit_type:
                col.canonical_type = pk_canonical.get(fk_target, "bigint")
            phys, w = _resolve_type(dialect, col.canonical_type)
            warnings.extend(w)
            constraints = []
            if col.is_pk:
                constraints.append("PRIMARY KEY")
            else:
                constraints.append("NULL" if col.nullable else "NOT NULL")
            if col.unique:
                constraints.append("UNIQUE")
            if col.name.endswith("_id") and not col.is_pk:
                if fk_target:
                    col.fk_table = fk_target
                    constraints.append(
                        f"REFERENCES {quote(fk_target)} ({quote('id')})"
                    )
                    index_cols.append(col.name)
                    rels.append(f"    {t.name} }}o--|| {fk_target} : references")
                else:
                    warnings.append(
                        f"`{t.name}.{col.name}` looks like a foreign key but no "
                        f"matching table was found — left as a plain column "
                        f"(candidate FK)."
                    )
            lines.append(f"    {quote(col.name)} {phys} {' '.join(constraints)}".rstrip())
            tag = " PK" if col.is_pk else (" FK" if fk_target else "")
            merm_type = _base_type(phys)
            merm_cols.append(f"        {merm_type} {col.name}{tag}")
        # audit timestamps
        ts_type, w = _resolve_type(dialect, "timestamp")
        warnings.extend(w)
        default_now = "DEFAULT CURRENT_TIMESTAMP"
        lines.append(f"    {quote('created_at')} {ts_type} NOT NULL {default_now}")
        lines.append(f"    {quote('updated_at')} {ts_type} NOT NULL {default_now}")
        merm_cols.append(f"        {_base_type(ts_type)} created_at")

        block = (
            f"CREATE TABLE {quote(t.name)} (\n"
            + ",\n".join(lines)
            + "\n);"
        )
        for ic in index_cols:
            block += (
                f"\nCREATE INDEX {q}idx_{t.name}_{ic}{q} "
                f"ON {quote(t.name)} ({quote(ic)});"
            )
        ddl_blocks.append(block)
        mermaid_lines.append(f"    {t.name} {{")
        mermaid_lines.extend(merm_cols)
        mermaid_lines.append("    }")

    mermaid_lines.extend(dict.fromkeys(rels))  # de-dupe, keep order
    warnings.insert(
        0,
        "Every table received a surrogate `id` primary key and "
        "`created_at`/`updated_at` audit columns automatically.",
    )
    # de-dupe warnings, preserve order
    warnings = list(dict.fromkeys(warnings))
    return SchemaResult(
        domain=domain,
        dialect=dialect,
        tables=tables,
        ddl="\n\n".join(ddl_blocks),
        mermaid="\n".join(mermaid_lines),
        warnings=warnings,
        is_sql=True,
    )


def _build_nosql(domain: str, dialect: str, tables: list[Table]) -> SchemaResult:
    lines = [
        f"## Document Model — {dialect}",
        "",
        "> DDL generation supports SQL dialects only "
        "(postgresql / mysql / sqlite). Below is a document-model sketch "
        "for your NoSQL target; no fake SQL is emitted.",
        "",
    ]
    for t in tables:
        coll = t.name
        lines.append(f"### Collection `{coll}`")
        lines.append("```json")
        doc = {"_id": "ObjectId | string"}
        for c in t.columns:
            doc[c.name] = c.canonical_type
        doc["created_at"] = "ISODate"
        doc["updated_at"] = "ISODate"
        body = ",\n".join(f'  "{k}": "{v}"' for k, v in doc.items())
        lines.append("{\n" + body + "\n}")
        lines.append("```")
        embed_hint = (
            "Embed related docs for read-heavy access; reference by id for "
            "high write/contention or unbounded growth."
        )
        lines.append(f"_Modeling hint:_ {embed_hint}\n")
    warnings = [
        "Access-pattern first: design NoSQL collections around your queries, "
        "not entities. Pick a partition/shard key with high cardinality.",
    ]
    return SchemaResult(
        domain=domain,
        dialect=dialect,
        tables=tables,
        ddl="\n".join(lines),
        mermaid="",
        warnings=warnings,
        is_sql=False,
    )


def design_schema(domain: str, entities_spec: str, database_type: str = "postgresql") -> SchemaResult:
    """Build a real schema artifact from an entity specification."""
    dialect = (database_type or "postgresql").strip().lower()
    if dialect in ("postgres",):
        dialect = "postgresql"
    if dialect in ("mongo",):
        dialect = "mongodb"
    if dialect in ("dynamo",):
        dialect = "dynamodb"
    if dialect == "multi":
        dialect = "postgresql"

    tables = parse_entities(entities_spec)
    if not tables:
        tables = [Table(name="records", columns=[])]

    if dialect in NOSQL_DIALECTS:
        return _build_nosql(domain, dialect, tables)
    if dialect not in SQL_DIALECTS:
        # Unknown dialect: fall back to postgres but warn.
        res = _build_sql(domain, "postgresql", tables)
        res.warnings.insert(0, f"Unknown dialect `{dialect}` — generated PostgreSQL DDL.")
        return res
    return _build_sql(domain, dialect, tables)
