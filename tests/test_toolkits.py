"""Deterministic tests for the ``toolkits`` power-tools package.

Every tool performs real computation, returns a ``str``, and fails soft
(returns a ``"❌ ..."`` string) instead of raising. These tests assert both
the computed values (against known-good answers) and the fail-soft contract.
"""
from __future__ import annotations

import pytest

from toolkits import FINANCE_TOOLS, POWER_TOOLS_BASE
from toolkits.dataops import analyze_dataset, describe_numbers, table_query
from toolkits.datetime_tools import add_business_days, date_diff, sla_deadline
from toolkits.diagram import mermaid_flowchart, mermaid_gantt, mermaid_sequence
from toolkits.finance import (
    financial_npv_irr,
    investment_metrics,
    loan_amortization,
    saas_unit_economics,
)
from toolkits.reasoning import decision_matrix, decompose_task, risk_register
from toolkits.textutils import text_diff
from toolkits.validation import regex_extract, validate_json


# --------------------------------------------------------------------------- #
# Package wiring
# --------------------------------------------------------------------------- #
def test_package_exports_expected_counts():
    assert len(POWER_TOOLS_BASE) == 15
    assert len(FINANCE_TOOLS) == 4
    # Everything is callable and uniquely named.
    names = [t.__name__ for t in (*POWER_TOOLS_BASE, *FINANCE_TOOLS)]
    assert len(names) == len(set(names)) == 19
    assert all(callable(t) for t in (*POWER_TOOLS_BASE, *FINANCE_TOOLS))


# --------------------------------------------------------------------------- #
# Finance
# --------------------------------------------------------------------------- #
def test_npv_irr_positive_project_is_accept():
    out = financial_npv_irr(10, "[-1000, 300, 400, 500, 600]")
    assert "NPV & IRR" in out
    assert "388.77" in out  # NPV at 10% discount
    assert "IRR:" in out
    assert "ACCEPT" in out


def test_npv_irr_no_sign_change_is_undefined():
    out = financial_npv_irr(10, "[100, 200, 300]")
    assert "IRR undefined" in out


def test_loan_amortization_zero_interest_is_exact():
    out = loan_amortization(12000, 0, 12)
    assert "1,000.00" in out  # 12000 / 12 months, no interest


def test_loan_amortization_extra_payment_saves_time():
    out = loan_amortization(100000, 6, 360, 200)
    assert "Monthly payment" in out
    assert "saves" in out  # extra payment shortens the term


def test_saas_unit_economics_known_values():
    out = saas_unit_economics(50, 80, 5, 300)
    assert "800.00" in out  # LTV = (50*0.8)/0.05
    assert "2.67" in out    # LTV:CAC = 800/300
    assert "7.5 months" in out  # payback = 300/40


def test_investment_metrics_roi_and_cagr():
    out = investment_metrics(10000, 18500, 3)
    assert "85.00%" in out   # total ROI
    assert "22.76%" in out   # annualized CAGR


# --------------------------------------------------------------------------- #
# Reasoning
# --------------------------------------------------------------------------- #
def test_decision_matrix_ranks_winner():
    options = '[{"name":"AWS","scores":{"Cost":7,"Speed":9}},' \
              '{"name":"GCP","scores":{"Cost":9,"Speed":6}}]'
    criteria = '[{"name":"Cost","weight":0.5},{"name":"Speed","weight":0.5}]'
    out = decision_matrix(options, criteria)
    assert "Recommendation:** AWS" in out
    assert "8.000" in out  # AWS weighted score


def test_risk_register_sorts_and_rates():
    risks = '[{"risk":"Critical","likelihood":5,"impact":5},' \
            '{"risk":"Minor","likelihood":1,"impact":2}]'
    out = risk_register(risks)
    assert "🔴 Red" in out
    assert "**Red:** 1" in out
    # Critical (severity 25) must be listed before Minor.
    assert out.index("Critical") < out.index("Minor")


def test_decompose_task_orders_waves():
    subs = '[{"id":"t1","name":"Schema","deps":[]},' \
           '{"id":"t2","name":"API","deps":["t1"]},' \
           '{"id":"t3","name":"Tests","deps":["t2"]}]'
    out = decompose_task("Ship feature", subs)
    assert "3 execution wave" in out


def test_decompose_task_detects_cycle():
    subs = '[{"id":"a","name":"A","deps":["b"]},{"id":"b","name":"B","deps":["a"]}]'
    out = decompose_task("Broken", subs)
    assert "cycle detected" in out


# --------------------------------------------------------------------------- #
# Data ops
# --------------------------------------------------------------------------- #
def test_analyze_dataset_csv_numeric_stats():
    out = analyze_dataset("a,b\n1,2\n3,4\n5,6")
    assert "Rows scanned:** 3" in out
    assert "Columns:** 2" in out
    assert "mean=3" in out  # column a: mean of 1,3,5


def test_describe_numbers_central_tendency():
    out = describe_numbers("[12, 7, 19, 3, 25, 8]")
    assert "Count:** 6" in out
    assert "Min:** 3" in out
    assert "Max:** 25" in out
    assert "Median:** 10" in out


def test_describe_numbers_flags_outlier():
    out = describe_numbers("[10, 11, 12, 13, 14, 15, 16, 1000]")
    assert "Outliers (>1.5×IQR):" in out


def test_table_query_filter_and_sort():
    rows = '[{"id":1,"status":"open"},{"id":2,"status":"closed"},' \
           '{"id":3,"status":"open"}]'
    ops = '{"where":[{"col":"status","op":"eq","value":"open"}],' \
          '"order_by":"id","desc":true}'
    out = table_query(rows, ops)
    assert "Rows returned:** 2" in out


def test_table_query_group_by_count():
    rows = '[{"status":"open"},{"status":"closed"},{"status":"open"}]'
    out = table_query(rows, '{"group_by_count":"status"}')
    assert "Groups:** 2" in out
    assert "| open | 2 |" in out


# --------------------------------------------------------------------------- #
# Diagrams
# --------------------------------------------------------------------------- #
def test_mermaid_flowchart_is_valid_block():
    nodes = '[{"id":"a","label":"Start","shape":"round"},{"id":"b","label":"End"}]'
    edges = '[{"from":"a","to":"b","label":"go"}]'
    out = mermaid_flowchart(nodes, edges)
    assert out.startswith("```mermaid")
    assert out.rstrip().endswith("```")
    assert "flowchart TD" in out
    assert 'a("Start")' in out
    assert "-->|go|" in out


def test_mermaid_sequence_renders_messages():
    out = mermaid_sequence('["User","API"]', '[{"from":"User","to":"API","text":"hi"}]')
    assert "sequenceDiagram" in out
    assert "->>" in out


def test_mermaid_gantt_groups_sections():
    tasks = '[{"name":"Design","start":"2024-01-01","duration":"5d","section":"P1"}]'
    out = mermaid_gantt("Plan", tasks)
    assert "gantt" in out
    assert "section P1" in out


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_validate_json_passes_good_payload():
    out = validate_json('{"id":1,"name":"x"}', '["id","name"]', '{"id":"int","name":"string"}')
    assert "PASSED" in out


def test_validate_json_reports_problems():
    out = validate_json('{"id":"oops"}', '["id","name"]', '{"id":"int"}')
    assert "FAILED" in out
    assert "missing required key: name" in out


def test_validate_json_rejects_bad_json():
    out = validate_json("{not valid json")
    assert "Invalid JSON" in out


def test_regex_extract_returns_groups():
    out = regex_extract("a1 b2 c3", r"[a-z](\d)", "1")
    assert "Matches:** 3" in out
    assert "`1`" in out


def test_regex_extract_bad_pattern_is_soft():
    out = regex_extract("x", "(", "0")
    assert "invalid regex" in out


def test_regex_extract_no_match():
    out = regex_extract("abc", r"\d")
    assert "No matches" in out


# --------------------------------------------------------------------------- #
# Date / business-day / SLA math
# --------------------------------------------------------------------------- #
def test_date_diff_days_and_hours():
    assert "7 days" in date_diff("2024-01-01", "2024-01-08", "days")
    assert "12 hours" in date_diff("2024-01-01T00:00:00", "2024-01-01T12:00:00", "hours")


def test_add_business_days_skips_weekend():
    out = add_business_days("2024-01-01", 5)  # Mon + 5 business days
    assert "2024-01-08" in out


def test_add_business_days_skips_holiday():
    out = add_business_days("2024-01-01", 5, '["2024-01-03"]')
    assert "2024-01-09" in out


def test_sla_deadline_calendar_hours():
    out = sla_deadline("2024-01-01T09:00:00", 4)
    assert "2024-01-01T13:00:00" in out


def test_sla_deadline_business_hours_rolls_over():
    out = sla_deadline("2024-01-01T09:00:00", 10, '{"start_hour":9,"end_hour":17}')
    assert "2024-01-02T11:00:00" in out  # 8h day 1 + 2h day 2


# --------------------------------------------------------------------------- #
# Text diff
# --------------------------------------------------------------------------- #
def test_text_diff_summary_counts():
    out = text_diff("line1\nline2\nline3", "line1\nlineX\nline3", "summary")
    assert "+1 added / -1 removed" in out


def test_text_diff_identical():
    out = text_diff("same", "same")
    assert "100.0%" in out


# --------------------------------------------------------------------------- #
# Fail-soft contract: malformed input must never raise
# --------------------------------------------------------------------------- #
FAILSOFT_CASES = [
    lambda: financial_npv_irr(10, "[bad json"),
    lambda: loan_amortization(-5, 6, 360),
    lambda: saas_unit_economics(50, 999, 5, 300),
    lambda: investment_metrics(0, 100, 3),
    lambda: decision_matrix("[bad", '[{"name":"x","weight":1}]'),
    lambda: risk_register("not json"),
    lambda: decompose_task("g", "[bad"),
    lambda: analyze_dataset("[bad json", "json"),
    lambda: describe_numbers("[bad"),
    lambda: table_query("[bad", "{}"),
    lambda: mermaid_flowchart("[bad", "[]"),
    lambda: mermaid_sequence("[bad", "[]"),
    lambda: mermaid_gantt("t", "[bad"),
    lambda: validate_json("{bad"),
    lambda: regex_extract("x", "("),
    lambda: date_diff("not-a-date", "also-bad"),
    lambda: add_business_days("not-a-date", 3),
    lambda: sla_deadline("not-a-date", 4),
]


@pytest.mark.parametrize("call", FAILSOFT_CASES)
def test_tools_fail_soft_on_bad_input(call):
    result = call()
    assert isinstance(result, str)
    assert result.startswith("❌")


# --------------------------------------------------------------------------- #
# Robustness regressions (rubber-duck hardening)
# --------------------------------------------------------------------------- #
def test_table_query_order_by_handles_missing_and_mixed_values():
    """order_by must not raise TypeError when the sort column has missing,
    blank, numeric and non-numeric values mixed across rows."""
    rows = (
        '[{"id":1,"score":10},'      # numeric
        '{"id":2,"score":"high"},'   # text
        '{"id":3},'                  # missing key
        '{"id":4,"score":""},'       # blank
        '{"id":5,"score":2}]'        # numeric
    )
    out = table_query(rows, '{"order_by":"score"}')
    assert isinstance(out, str)
    assert "Rows returned:** 5" in out
    # numeric values sort numerically (2 before 10), not lexically ("10" < "2")
    assert out.index("| 5 | 2 |") < out.index("| 1 | 10 |")


def test_table_query_order_by_desc_with_missing_values_is_stable():
    rows = '[{"id":1,"v":5},{"id":2},{"id":3,"v":1}]'
    out = table_query(rows, '{"order_by":"v","desc":true}')
    assert isinstance(out, str)
    assert "Rows returned:** 3" in out


def test_regex_extract_rejects_catastrophic_pattern_instantly():
    """Nested unbounded quantifiers (e.g. (a+)+) can cause catastrophic
    backtracking that cannot be interrupted in-process (the C `re` engine holds
    the GIL on Windows). The tool must reject such patterns *before* running and
    return instantly, never pinning the worker."""
    import time

    evil = "(a+)+$"
    payload = "a" * 64 + "!"  # would force exponential backtracking, never matches
    start = time.monotonic()
    out = regex_extract(payload, evil, "0")
    elapsed = time.monotonic() - start

    assert isinstance(out, str)
    assert elapsed < 1.0  # rejected pre-flight; no matching is attempted
    assert out.startswith("❌")
    assert "rejected" in out


def test_regex_extract_allows_safe_quantified_groups():
    """The catastrophic-pattern guard must not reject benign patterns that
    contain quantified groups, e.g. (\\d+)-(\\d+) or (ab)+."""
    out = regex_extract("12-34 56-78", r"(\d+)-(\d+)", "0")
    assert "Matches:** 2" in out
    out2 = regex_extract("ababab", r"(ab)+", "0")
    assert "Matches:** 1" in out2


def test_toolkit_tools_are_schema_introspectable_by_framework():
    """Every power tool must be convertible into an agent_framework
    FunctionTool with a JSON-schema parameter map — this is exactly what
    ``Agent(tools=...)`` does at construction time."""
    from agent_framework import normalize_tools

    normalized = normalize_tools([*POWER_TOOLS_BASE, *FINANCE_TOOLS])
    assert len(normalized) == len(POWER_TOOLS_BASE) + len(FINANCE_TOOLS)
    for tool in normalized:
        assert getattr(tool, "name", ""), "tool is missing a name"
        params = tool.parameters
        params = params() if callable(params) else params
        assert isinstance(params, dict), f"{tool.name} produced no schema dict"
