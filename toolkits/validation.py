"""
toolkits.validation — JSON validation & regex extraction (stdlib only).

Validates JSON payloads against required keys and a lightweight type schema
(no external `jsonschema` dependency), and extracts regex matches safely with
input-size guards. Fail-soft; no LLM, no network, no credentials.
"""
from __future__ import annotations

import json
import re
from typing import Annotated, Any

_MAX_TEXT = 200_000

# Best-effort detector for the classic catastrophic-backtracking signature:
# a group containing an unbounded quantifier that is itself quantified, e.g.
# (a+)+, (a*)*, (.*)+, (x+){2,}. Python's `re` runs in C and holds the GIL for
# the entire match, so a runaway pattern cannot be interrupted in-process on
# Windows (no signal.alarm; thread joins never wake because the GIL is held).
# The only reliable, stdlib-only, cross-platform mitigation is to reject these
# patterns *before* compiling/running them. This is a heuristic, not a proof —
# it catches the common exponential forms without flagging safe patterns like
# (ab)+ or (\d+)-(\d+).
_CATASTROPHIC = re.compile(
    r"\([^()]*(?:[+*]|\{\d+,\}|\{\d+,\d+\})[^()]*\)\s*(?:[+*]|\{\d+,\}|\{\d+,\d+\})"
)

_TYPE_MAP: dict[str, tuple] = {
    "string": (str,),
    "str": (str,),
    "number": (int, float),
    "int": (int,),
    "integer": (int,),
    "float": (float,),
    "bool": (bool,),
    "boolean": (bool,),
    "array": (list,),
    "list": (list,),
    "object": (dict,),
    "dict": (dict,),
    "null": (type(None),),
}


def _loads(raw: str, label: str) -> Any:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"{label} is empty")
    return json.loads(raw)


def _type_ok(value: Any, expected: str) -> bool:
    types = _TYPE_MAP.get(str(expected).lower())
    if types is None:
        return True  # unknown type → don't fail
    if bool in types and not isinstance(value, bool):
        # "bool" must match exactly
        pass
    if (int in types or float in types) and isinstance(value, bool):
        return False  # bool is not a number here
    return isinstance(value, types)


def _check_schema(value: Any, schema: Any, path: str, errors: list[str]) -> None:
    if isinstance(schema, str):
        if not _type_ok(value, schema):
            errors.append(f"{path or 'root'}: expected {schema}, got {type(value).__name__}")
        return
    if isinstance(schema, dict):
        if not isinstance(value, dict):
            errors.append(f"{path or 'root'}: expected object, got {type(value).__name__}")
            return
        for key, sub in schema.items():
            if key not in value:
                errors.append(f"{path + '.' if path else ''}{key}: missing")
            else:
                _check_schema(value[key], sub, f"{path + '.' if path else ''}{key}", errors)
        return
    if isinstance(schema, list) and schema:
        if not isinstance(value, list):
            errors.append(f"{path or 'root'}: expected array, got {type(value).__name__}")
            return
        item_schema = schema[0]
        for i, item in enumerate(value):
            _check_schema(item, item_schema, f"{path}[{i}]", errors)


def validate_json(
    data: Annotated[str, "JSON document to validate (object or array)"],
    required_keys_json: Annotated[
        str, 'Optional JSON array of top-level required keys, e.g. ["id","name"]'
    ] = "",
    type_schema_json: Annotated[
        str,
        'Optional type schema, e.g. {"id":"int","name":"string","tags":["string"]}. '
        "Types: string,number,int,float,bool,array,object,null.",
    ] = "",
) -> str:
    """Validate JSON: parseability, required top-level keys, and a recursive type schema.

    No external dependencies — the schema is a plain JSON object mapping keys to type
    names (or nested objects/arrays). Reports every problem with its path. Returns a
    ✅/❌ summary so agents can gate on structured output.
    """
    try:
        try:
            doc = _loads(data, "data")
        except json.JSONDecodeError as e:
            return f"❌ Invalid JSON: {e}"

        errors: list[str] = []
        if str(required_keys_json).strip():
            req = _loads(required_keys_json, "required_keys_json")
            if isinstance(req, list):
                if not isinstance(doc, dict):
                    errors.append("required_keys given but document is not an object")
                else:
                    for k in req:
                        if k not in doc:
                            errors.append(f"missing required key: {k}")
        if str(type_schema_json).strip():
            schema = _loads(type_schema_json, "type_schema_json")
            _check_schema(doc, schema, "", errors)

        kind = type(doc).__name__
        if errors:
            body = "\n".join(f"- {e}" for e in errors)
            return f"❌ Validation FAILED ({len(errors)} issue(s)) — root is {kind}\n{body}"
        return f"✅ Validation PASSED — root is {kind}, all checks satisfied"
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON in schema/keys — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def regex_extract(
    text: Annotated[str, "Text to search (max 200k chars)"],
    pattern: Annotated[str, "Python regular expression"],
    group: Annotated[str, "Capture group to return: '0' = whole match (default), or name/number"] = "0",
    flags: Annotated[str, "Optional flags as letters: i (ignorecase), m (multiline), s (dotall)"] = "",
    max_matches: Annotated[int, "Maximum matches to return (default 50)"] = 50,
) -> str:
    """Extract regex matches from text with safety guards (size cap, match cap).

    Compiles the pattern with optional i/m/s flags, returns up to ``max_matches``
    captured values (whole match or a specific group). Fails soft on bad patterns
    or oversized input instead of raising.
    """
    try:
        t = str(text)
        if len(t) > _MAX_TEXT:
            return f"❌ Error: input too large ({len(t)} chars > {_MAX_TEXT})"
        if _CATASTROPHIC.search(pattern or ""):
            return (
                "❌ Error: pattern rejected — nested unbounded quantifiers "
                "(e.g. (a+)+) risk catastrophic backtracking and cannot be safely "
                "interrupted. Simplify the pattern (use a single, non-nested "
                "quantifier)."
            )
        f = 0
        fl = flags.lower()
        if "i" in fl:
            f |= re.IGNORECASE
        if "m" in fl:
            f |= re.MULTILINE
        if "s" in fl:
            f |= re.DOTALL
        try:
            rx = re.compile(pattern, f)
        except re.error as e:
            return f"❌ Error: invalid regex — {e}"

        cap = max(1, min(int(max_matches), 1000))

        out: list[str] = []
        for m in rx.finditer(t):
            try:
                if group.isdigit():
                    val = m.group(int(group))
                else:
                    val = m.group(group)
            except (IndexError, re.error):
                val = m.group(0)
            out.append("" if val is None else val)
            if len(out) >= cap:
                break

        if not out:
            return "# Regex Extract\n\n_No matches found._"
        lines = ["# Regex Extract", "", f"**Matches:** {len(out)}", ""]
        lines += [f"{i + 1}. `{v}`" for i, v in enumerate(out)]
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


VALIDATION_TOOLS = [validate_json, regex_extract]
