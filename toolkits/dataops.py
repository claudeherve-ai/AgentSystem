"""
toolkits.dataops — deterministic data-analysis compute tools (stdlib only).

Parses real CSV/JSON data and computes per-column statistics, descriptive stats
with outlier detection, and structured table queries (filter/select/sort/group)
WITHOUT a SQL parser. Fail-soft; no LLM, no network, no credentials.
"""
from __future__ import annotations

import csv
import io
import json
import statistics
from typing import Annotated, Any


def _loads(raw: str, label: str) -> Any:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"{label} is empty")
    return json.loads(raw)


def _is_number(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v.replace(",", "").strip())
            return True
        except ValueError:
            return False
    return False


def _to_float(v: Any) -> float:
    if isinstance(v, str):
        return float(v.replace(",", "").strip())
    return float(v)


def _rows_from_csv(text: str, max_rows: int) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []
    for i, row in enumerate(reader):
        if i >= max_rows:
            break
        rows.append(dict(row))
    return rows


def analyze_dataset(
    data: Annotated[str, "Raw dataset as CSV text OR a JSON array of objects (records)"],
    fmt: Annotated[str, "Format: 'auto' (default), 'csv', or 'json'"] = "auto",
    max_rows: Annotated[int, "Max rows to scan (default 5000)"] = 5000,
) -> str:
    """Profile a tabular dataset: row/column counts and per-column type & statistics.

    Accepts CSV text or a JSON array of record objects. For numeric columns reports
    count/min/max/mean/median/stdev; for text columns reports distinct count and top
    values. Caps rows for safety. Use this to ground analysis in real data.
    """
    try:
        cap = max(1, min(int(max_rows), 100000))
        text = str(data)
        chosen = fmt.lower().strip()
        rows: list[dict[str, Any]]
        if chosen == "json" or (chosen == "auto" and text.lstrip()[:1] in "[{"):
            parsed = _loads(text, "data")
            if isinstance(parsed, dict):
                parsed = [parsed]
            if not isinstance(parsed, list) or not parsed:
                return "❌ Error: JSON data must be a non-empty array of objects"
            rows = [r for r in parsed[:cap] if isinstance(r, dict)]
        else:
            rows = _rows_from_csv(text, cap)
        if not rows:
            return "❌ Error: no data rows found"

        columns: list[str] = []
        for r in rows:
            for k in r.keys():
                if k not in columns:
                    columns.append(k)

        lines = ["# Dataset Profile", "",
                 f"**Rows scanned:** {len(rows)} | **Columns:** {len(columns)}", ""]
        for col in columns:
            values = [r.get(col) for r in rows if r.get(col) not in (None, "")]
            non_null = len(values)
            numeric_vals = [_to_float(v) for v in values if _is_number(v)]
            if numeric_vals and len(numeric_vals) >= max(1, int(0.6 * non_null)):
                mn = min(numeric_vals)
                mx = max(numeric_vals)
                mean = statistics.fmean(numeric_vals)
                med = statistics.median(numeric_vals)
                std = statistics.pstdev(numeric_vals) if len(numeric_vals) > 1 else 0.0
                lines.append(
                    f"- **{col}** (numeric): n={non_null}, min={mn:g}, max={mx:g}, "
                    f"mean={mean:.3g}, median={med:g}, stdev={std:.3g}"
                )
            else:
                distinct = {str(v) for v in values}
                freq: dict[str, int] = {}
                for v in values:
                    freq[str(v)] = freq.get(str(v), 0) + 1
                top = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:3]
                top_txt = ", ".join(f"{k}({c})" for k, c in top)
                lines.append(
                    f"- **{col}** (text): n={non_null}, distinct={len(distinct)}, "
                    f"top: {top_txt or '—'}"
                )
        return "\n".join(lines)
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def describe_numbers(
    values_json: Annotated[str, "JSON array of numbers, e.g. [12, 7, 19, 3, 25, 8]"],
) -> str:
    """Descriptive statistics for a list of numbers with IQR-based outlier detection.

    Reports count, min/max, mean, median, stdev, quartiles (Q1/Q3), IQR, and any
    outliers beyond 1.5×IQR fences. Fails soft on non-numeric or empty input.
    """
    try:
        raw = _loads(values_json, "values_json")
        if not isinstance(raw, list) or not raw:
            return "❌ Error: values_json must be a non-empty JSON array of numbers"
        nums = []
        for v in raw:
            if not _is_number(v):
                return f"❌ Error: non-numeric value encountered: {v!r}"
            nums.append(_to_float(v))

        n = len(nums)
        s = sorted(nums)
        mn, mx = s[0], s[-1]
        mean = statistics.fmean(nums)
        med = statistics.median(nums)
        std = statistics.pstdev(nums) if n > 1 else 0.0

        lines = ["# Descriptive Statistics", "",
                 f"**Count:** {n} | **Min:** {mn:g} | **Max:** {mx:g}",
                 f"**Mean:** {mean:.4g} | **Median:** {med:g} | **Stdev (pop):** {std:.4g}"]
        if n >= 4:
            q = statistics.quantiles(nums, n=4, method="inclusive")
            q1, q3 = q[0], q[2]
            iqr = q3 - q1
            lo_fence = q1 - 1.5 * iqr
            hi_fence = q3 + 1.5 * iqr
            outliers = [x for x in nums if x < lo_fence or x > hi_fence]
            lines.append(f"**Q1:** {q1:g} | **Q3:** {q3:g} | **IQR:** {iqr:g}")
            if outliers:
                shown = ", ".join(f"{o:g}" for o in sorted(set(outliers)))
                lines.append(f"**Outliers (>1.5×IQR):** {shown}")
            else:
                lines.append("**Outliers:** none")
        else:
            lines.append("_Need ≥4 values for quartiles/outlier detection._")
        return "\n".join(lines)
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def table_query(
    rows_json: Annotated[str, "JSON array of record objects (the table)"],
    ops_json: Annotated[
        str,
        'JSON object of operations, e.g. {"where":[{"col":"status","op":"eq","value":"open"}],'
        '"select":["id","status"],"order_by":"id","desc":false,"limit":10,'
        '"group_by_count":"status"}. Supported ops: eq,ne,gt,ge,lt,le,contains.',
    ],
) -> str:
    """Query a JSON table: filter (where), project (select), sort, limit, and group-count.

    No SQL parsing — operations are passed structurally. Supports comparison and
    'contains' predicates, multi-condition AND filtering, column projection,
    ordering, limiting, and group-by-count aggregation. Returns a Markdown table.
    """
    try:
        rows = _loads(rows_json, "rows_json")
        ops = _loads(ops_json, "ops_json") if str(ops_json).strip() else {}
        if not isinstance(rows, list):
            return "❌ Error: rows_json must be a JSON array of objects"
        rows = [r for r in rows if isinstance(r, dict)]
        if not isinstance(ops, dict):
            return "❌ Error: ops_json must be a JSON object"

        def cmp(a: Any, op: str, b: Any) -> bool:
            try:
                if op == "contains":
                    return str(b).lower() in str(a).lower()
                if _is_number(a) and _is_number(b):
                    a2, b2 = _to_float(a), _to_float(b)
                else:
                    a2, b2 = str(a), str(b)
                return {
                    "eq": a2 == b2, "ne": a2 != b2, "gt": a2 > b2,
                    "ge": a2 >= b2, "lt": a2 < b2, "le": a2 <= b2,
                }.get(op, False)
            except Exception:  # noqa: BLE001
                return False

        for cond in ops.get("where", []) or []:
            col, op, val = cond.get("col"), cond.get("op", "eq"), cond.get("value")
            rows = [r for r in rows if cmp(r.get(col), op, val)]

        gb = ops.get("group_by_count")
        if gb:
            counts: dict[str, int] = {}
            for r in rows:
                key = str(r.get(gb, "(null)"))
                counts[key] = counts.get(key, 0) + 1
            ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
            lines = [f"# Group-by-count: {gb}", "", f"| {gb} | count |", "|---|---|"]
            lines += [f"| {k} | {c} |" for k, c in ordered]
            lines.append(f"\n**Groups:** {len(ordered)} | **Rows:** {sum(counts.values())}")
            return "\n".join(lines)

        order_by = ops.get("order_by")
        if order_by:
            def _sort_key(r: dict) -> tuple:
                v = r.get(order_by)
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    return (2, 0.0, "")  # missing/blank values sort last
                if _is_number(v):
                    return (0, _to_float(v), "")  # numbers grouped & sorted numerically
                return (1, 0.0, str(v))  # text grouped & sorted lexically

            rows.sort(key=_sort_key, reverse=bool(ops.get("desc", False)))

        limit = ops.get("limit")
        if isinstance(limit, int) and limit >= 0:
            rows = rows[:limit]

        select = ops.get("select")
        if select and isinstance(select, list):
            cols = [str(c) for c in select]
        else:
            cols = []
            for r in rows:
                for k in r.keys():
                    if k not in cols:
                        cols.append(k)

        if not rows:
            return "# Query Result\n\n_No rows matched._"
        lines = ["# Query Result", "", "| " + " | ".join(cols) + " |",
                 "|" + "|".join("---" for _ in cols) + "|"]
        for r in rows:
            lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
        lines.append(f"\n**Rows returned:** {len(rows)}")
        return "\n".join(lines)
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


DATAOPS_TOOLS = [analyze_dataset, describe_numbers, table_query]
