"""
toolkits.finance — deterministic financial-modeling compute tools.

DOMAIN-scoped (wired only into finance-relevant agents, not every agent).
All functions perform real arithmetic, fail soft, and state their assumptions.
No LLM, no network, no credentials.
"""
from __future__ import annotations

import json
from typing import Annotated, Any


def _loads(raw: str, label: str) -> Any:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"{label} is empty")
    return json.loads(raw)


def _npv(rate: float, cashflows: list[float]) -> float:
    return sum(cf / ((1.0 + rate) ** t) for t, cf in enumerate(cashflows))


def financial_npv_irr(
    discount_rate_pct: Annotated[float, "Annual discount rate as a percent, e.g. 10 for 10%"],
    cashflows_json: Annotated[
        str,
        'JSON array of period cashflows starting at t=0, e.g. [-1000, 300, 400, 500, 600]. '
        "Negative = outflow, positive = inflow.",
    ],
) -> str:
    """Compute NPV at a given discount rate and the IRR (internal rate of return).

    NPV discounts each period cashflow back to present value. IRR is found by
    bisection and requires at least one sign change; multiple sign changes are
    flagged (IRR may be non-unique). Returns NPV, IRR%, and an accept/reject signal.
    """
    try:
        rate = float(discount_rate_pct) / 100.0
        cfs = _loads(cashflows_json, "cashflows_json")
        if not isinstance(cfs, list) or len(cfs) < 2:
            return "❌ Error: cashflows_json must be a JSON array of >=2 numbers"
        cashflows = [float(x) for x in cfs]

        npv = _npv(rate, cashflows)

        signs = [1 if c > 0 else (-1 if c < 0 else 0) for c in cashflows if c != 0]
        changes = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i - 1])

        lines = ["# NPV & IRR Analysis", "",
                 f"**Periods:** {len(cashflows)} (t=0 … t={len(cashflows) - 1})",
                 f"**Discount rate:** {discount_rate_pct}%",
                 f"**NPV:** {npv:,.2f}"]

        if changes == 0:
            lines.append("⚠️ IRR undefined: cashflows never change sign (all inflows or all "
                         "outflows) — no break-even rate exists.")
            return "\n".join(lines)

        irr = _bisect_irr(cashflows)
        if irr is None:
            lines.append("⚠️ IRR not found within search bounds (-99% to +1000%). The "
                         "cashflow stream may have no real root in range.")
        else:
            lines.append(f"**IRR:** {irr * 100:.2f}%")
            verdict = "ACCEPT ✅" if irr > rate else "REJECT ❌"
            lines.append(f"**Decision (IRR vs hurdle {discount_rate_pct}%):** {verdict}")
            if changes > 1:
                lines.append(f"⚠️ Warning: {changes} sign changes detected — IRR may be "
                             "non-unique (multiple roots). Prefer NPV for the decision.")
        lines.append("")
        lines.append("_Assumption: cashflows occur at end of each equal period; "
                     "rate is per-period._")
        return "\n".join(lines)
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def _bisect_irr(cashflows: list[float], lo: float = -0.99, hi: float = 10.0,
                tol: float = 1e-7, max_iter: int = 200) -> float | None:
    f_lo = _npv(lo, cashflows)
    f_hi = _npv(hi, cashflows)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        return None  # no sign change in bracket
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        f_mid = _npv(mid, cashflows)
        if abs(f_mid) < tol or (hi - lo) / 2.0 < tol:
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid
    return (lo + hi) / 2.0


def loan_amortization(
    principal: Annotated[float, "Loan principal amount, e.g. 250000"],
    annual_rate_pct: Annotated[float, "Annual nominal interest rate percent, e.g. 6.5"],
    term_months: Annotated[int, "Loan term in months, e.g. 360"],
    extra_payment: Annotated[float, "Optional extra principal payment per month (default 0)"] = 0.0,
) -> str:
    """Compute a loan's monthly payment, total interest, and payoff schedule summary.

    Handles the zero-interest case, detects negative amortization (payment can't
    cover interest), validates inputs, and applies an optional extra monthly
    principal payment (showing months/interest saved). Iteration-capped for safety.
    """
    try:
        p = float(principal)
        annual = float(annual_rate_pct)
        n = int(term_months)
        extra = max(0.0, float(extra_payment))
        if p <= 0:
            return "❌ Error: principal must be > 0"
        if n <= 0:
            return "❌ Error: term_months must be > 0"
        if annual < 0:
            return "❌ Error: annual_rate_pct cannot be negative"

        r = annual / 100.0 / 12.0
        if r == 0:
            payment = p / n
        else:
            payment = p * r * (1 + r) ** n / ((1 + r) ** n - 1)

        # Negative amortization guard (scheduled payment, before extra).
        if r > 0 and payment <= p * r:
            return ("⚠️ Negative amortization: the scheduled payment "
                    f"({payment:,.2f}) does not cover monthly interest "
                    f"({p * r:,.2f}); the balance would grow. Check inputs.")

        def simulate(extra_amt: float) -> tuple[int, float, float]:
            bal = p
            total_int = 0.0
            months = 0
            cap = n + 600  # safety cap beyond scheduled term
            while bal > 1e-6 and months < cap:
                interest = bal * r
                pay = payment + extra_amt
                principal_paid = pay - interest
                if principal_paid <= 0:
                    return months, total_int, bal  # cannot progress
                if principal_paid > bal:
                    principal_paid = bal
                bal -= principal_paid
                total_int += interest
                months += 1
            return months, total_int, bal

        base_months, base_interest, _ = simulate(0.0)
        lines = ["# Loan Amortization", "",
                 f"**Principal:** {p:,.2f}",
                 f"**Rate:** {annual:.3f}% annual ({r * 100:.4f}% monthly)",
                 f"**Term:** {n} months",
                 f"**Monthly payment:** {payment:,.2f}",
                 f"**Total interest (no extra):** {base_interest:,.2f}",
                 f"**Total cost:** {p + base_interest:,.2f}"]
        if extra > 0:
            ex_months, ex_interest, _ = simulate(extra)
            lines += ["",
                      f"**With extra {extra:,.2f}/mo:**",
                      f"- Payoff in **{ex_months} months** (saves {base_months - ex_months} months)",
                      f"- Total interest **{ex_interest:,.2f}** (saves {base_interest - ex_interest:,.2f})"]
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def saas_unit_economics(
    arpu_monthly: Annotated[float, "Average revenue per user per month, e.g. 50"],
    gross_margin_pct: Annotated[float, "Gross margin percent, 0-100, e.g. 80"],
    monthly_churn_pct: Annotated[float, "Monthly customer churn percent, e.g. 3"],
    cac: Annotated[float, "Customer acquisition cost, e.g. 300"],
) -> str:
    """Compute SaaS unit economics: LTV, LTV:CAC ratio, and CAC payback (months).

    LTV = (ARPU × gross margin) / churn rate. Guards churn=0 (infinite lifetime),
    CAC=0, and out-of-range margin. Flags the health of the LTV:CAC ratio
    (>=3 healthy, <1 unsustainable) and payback period (<12mo strong).
    """
    try:
        arpu = float(arpu_monthly)
        gm = float(gross_margin_pct) / 100.0
        churn = float(monthly_churn_pct) / 100.0
        cac_v = float(cac)
        if arpu < 0:
            return "❌ Error: arpu_monthly cannot be negative"
        if not (0.0 <= gm <= 1.0):
            return "❌ Error: gross_margin_pct must be between 0 and 100"
        if not (0.0 <= churn <= 1.0):
            return "❌ Error: monthly_churn_pct must be between 0 and 100"
        if cac_v < 0:
            return "❌ Error: cac cannot be negative"

        margin_rev = arpu * gm  # monthly gross-margin revenue per customer
        lines = ["# SaaS Unit Economics", "",
                 f"**ARPU:** {arpu:,.2f}/mo | **Gross margin:** {gm:.0%} | "
                 f"**Monthly churn:** {churn:.2%} | **CAC:** {cac_v:,.2f}",
                 f"**Monthly gross-margin/customer:** {margin_rev:,.2f}", ""]

        if churn == 0:
            lines.append("**LTV:** ∞ (0% churn assumed — lifetime is unbounded; treat with caution)")
            ltv = None
        else:
            avg_lifetime = 1.0 / churn
            ltv = margin_rev / churn
            lines.append(f"**Avg customer lifetime:** {avg_lifetime:.1f} months")
            lines.append(f"**LTV (gross-margin):** {ltv:,.2f}")

        if ltv is not None and cac_v > 0:
            ratio = ltv / cac_v
            if ratio >= 3:
                health = "🟢 Healthy (≥3)"
            elif ratio >= 1:
                health = "🟠 Thin (1-3)"
            else:
                health = "🔴 Unsustainable (<1)"
            lines.append(f"**LTV:CAC:** {ratio:.2f} — {health}")
        elif cac_v == 0:
            lines.append("**LTV:CAC:** n/a (CAC = 0)")

        if margin_rev > 0 and cac_v > 0:
            payback = cac_v / margin_rev
            tag = "🟢 strong" if payback < 12 else ("🟠 ok" if payback < 18 else "🔴 slow")
            lines.append(f"**CAC payback:** {payback:.1f} months — {tag}")
        elif cac_v == 0:
            lines.append("**CAC payback:** 0 months (no acquisition cost)")
        else:
            lines.append("**CAC payback:** never (zero gross-margin revenue)")

        lines += ["", "_Assumption: constant monthly churn & margin; revenue measured monthly._"]
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def investment_metrics(
    initial: Annotated[float, "Initial investment/value, must be > 0, e.g. 10000"],
    final: Annotated[float, "Final value, e.g. 18500"],
    years: Annotated[float, "Holding period in years, must be > 0, e.g. 3"],
) -> str:
    """Compute total ROI and annualized CAGR for an investment over a holding period.

    ROI = (final − initial) / initial. CAGR = (final/initial)^(1/years) − 1.
    Requires initial > 0 and years > 0. Handles total-loss (final ≤ 0) gracefully.
    """
    try:
        i = float(initial)
        f = float(final)
        y = float(years)
        if i <= 0:
            return "❌ Error: initial must be > 0"
        if y <= 0:
            return "❌ Error: years must be > 0"

        roi = (f - i) / i
        lines = ["# Investment Metrics", "",
                 f"**Initial:** {i:,.2f} | **Final:** {f:,.2f} | **Period:** {y:g} year(s)",
                 f"**Total ROI:** {roi:.2%} ({f - i:,.2f})"]
        if f <= 0:
            lines.append("**CAGR:** -100% (total loss — final value ≤ 0)")
        else:
            cagr = (f / i) ** (1.0 / y) - 1.0
            lines.append(f"**CAGR (annualized):** {cagr:.2%}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


FINANCE_TOOLS = [
    financial_npv_irr,
    loan_amortization,
    saas_unit_economics,
    investment_metrics,
]
