"""
AgentSystem — Finance Agent.

Tracks expenses, budgets, invoices, and generates financial reports.
Uses local SQLite for persistent storage.
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails import Guardrails
from guardrails.approval import HumanApproval
from tools.audit import log_action

logger = logging.getLogger(__name__)

_guardrails = Guardrails()
_approval = HumanApproval()

FINANCE_DB = Path(__file__).resolve().parent.parent / "memory" / "finance.db"


def _get_finance_db() -> sqlite3.Connection:
    """Get a connection to the finance database, creating tables if needed."""
    FINANCE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(FINANCE_DB))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            vendor TEXT,
            payment_method TEXT,
            recurring INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT UNIQUE NOT NULL,
            monthly_limit REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            alert_threshold REAL DEFAULT 0.8
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            client_email TEXT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'draft',
            issued_date TEXT,
            due_date TEXT,
            paid_date TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
        CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
        CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
    """)
    conn.commit()
    return conn


async def log_expense(
    category: Annotated[str, "Expense category (e.g., software, office, travel, marketing)"],
    description: Annotated[str, "What was this expense for"],
    amount: Annotated[float, "Amount spent"],
    vendor: Annotated[str, "Vendor/merchant name"] = "",
    payment_method: Annotated[str, "Payment method (credit, debit, cash, transfer)"] = "",
    recurring: Annotated[bool, "Is this a recurring expense"] = False,
    date: Annotated[str, "Date of expense in YYYY-MM-DD format (default: today)"] = "",
) -> str:
    """
    Log a new expense. Auto-approved (read/write to local DB only).
    Checks against budget limits and alerts if approaching threshold.
    """
    expense_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    conn = _get_finance_db()
    try:
        conn.execute(
            """INSERT INTO expenses (date, category, description, amount, vendor,
               payment_method, recurring, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                expense_date, category, description, amount, vendor,
                payment_method, int(recurring),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()

        # Check budget
        budget_row = conn.execute(
            "SELECT monthly_limit, alert_threshold FROM budgets WHERE category = ?",
            (category,),
        ).fetchone()

        month_start = expense_date[:7] + "-01"
        month_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE category = ? AND date >= ?",
            (category, month_start),
        ).fetchone()[0]

        alert = ""
        if budget_row:
            limit, threshold = budget_row
            pct = month_total / limit if limit > 0 else 0
            if pct >= 1.0:
                alert = f"\n🚨 OVER BUDGET: {category} — ${month_total:.2f}/${limit:.2f} ({pct:.0%})"
            elif pct >= threshold:
                alert = f"\n⚠️ APPROACHING LIMIT: {category} — ${month_total:.2f}/${limit:.2f} ({pct:.0%})"

        log_action("FinanceAgent", "log_expense", f"{category}: ${amount}", f"Total: ${month_total:.2f}")

        return (
            f"✅ Expense logged:\n"
            f"  Date: {expense_date}\n"
            f"  Category: {category}\n"
            f"  Amount: ${amount:.2f}\n"
            f"  Description: {description}\n"
            f"  Month total ({category}): ${month_total:.2f}"
            f"{alert}"
        )
    finally:
        conn.close()


async def set_budget(
    category: Annotated[str, "Budget category"],
    monthly_limit: Annotated[float, "Monthly spending limit"],
    alert_threshold: Annotated[float, "Alert when spending reaches this % of limit (0.0-1.0)"] = 0.8,
) -> str:
    """Set or update a monthly budget for a category."""
    conn = _get_finance_db()
    try:
        conn.execute(
            """INSERT INTO budgets (category, monthly_limit, alert_threshold)
               VALUES (?, ?, ?)
               ON CONFLICT(category) DO UPDATE SET
               monthly_limit = excluded.monthly_limit,
               alert_threshold = excluded.alert_threshold""",
            (category, monthly_limit, alert_threshold),
        )
        conn.commit()
        log_action("FinanceAgent", "set_budget", f"{category}: ${monthly_limit:.2f}")
        return f"✅ Budget set: {category} → ${monthly_limit:.2f}/month (alert at {alert_threshold:.0%})"
    finally:
        conn.close()


async def get_budget_report(
    month: Annotated[str, "Month in YYYY-MM format (default: current month)"] = "",
) -> str:
    """Generate a budget vs. actuals report for a given month."""
    if not month:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    month_start = f"{month}-01"
    conn = _get_finance_db()
    try:
        # Get all budgets
        budgets = conn.execute("SELECT category, monthly_limit FROM budgets").fetchall()

        # Get spending by category
        spending = conn.execute(
            """SELECT category, SUM(amount) as total
               FROM expenses WHERE date >= ? AND date < date(?, '+1 month')
               GROUP BY category ORDER BY total DESC""",
            (month_start, month_start),
        ).fetchall()

        spending_dict = {row[0]: row[1] for row in spending}
        total_spent = sum(v for v in spending_dict.values())

        report = f"📊 Budget Report — {month}\n{'═' * 45}\n"

        if budgets:
            report += f"{'Category':<20} {'Spent':>10} {'Budget':>10} {'%':>6}\n"
            report += f"{'─' * 20} {'─' * 10} {'─' * 10} {'─' * 6}\n"
            for cat, limit in budgets:
                spent = spending_dict.pop(cat, 0.0)
                pct = (spent / limit * 100) if limit > 0 else 0
                flag = " 🚨" if pct >= 100 else " ⚠️" if pct >= 80 else ""
                report += f"{cat:<20} ${spent:>9.2f} ${limit:>9.2f} {pct:>5.0f}%{flag}\n"

        # Uncategorized spending
        if spending_dict:
            report += f"\n{'Unbudgeted Spending'}\n{'─' * 45}\n"
            for cat, total in spending_dict.items():
                report += f"  {cat:<18} ${total:>9.2f}\n"

        report += f"{'═' * 45}\n"
        report += f"{'TOTAL SPENT':<20} ${total_spent:>9.2f}\n"

        log_action("FinanceAgent", "get_budget_report", f"Month: {month}", f"Total: ${total_spent:.2f}")
        return report
    finally:
        conn.close()


async def create_invoice(
    client_name: Annotated[str, "Client/customer name"],
    description: Annotated[str, "Invoice description/line items"],
    amount: Annotated[float, "Invoice total amount"],
    client_email: Annotated[str, "Client email address"] = "",
    due_days: Annotated[int, "Days until payment is due"] = 30,
) -> str:
    """
    Create a new invoice. REQUIRES human approval before sending.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    invoice_number = f"INV-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"
    due_date = (now + timedelta(days=due_days)).strftime("%Y-%m-%d")

    details = (
        f"Invoice: {invoice_number}\n"
        f"Client: {client_name}\n"
        f"Amount: ${amount:.2f}\n"
        f"Due: {due_date}\n"
        f"Description: {description}"
    )

    approved, feedback = await _approval.request_approval(
        agent_name="FinanceAgent",
        action="create_invoice",
        details=details,
    )

    if not approved:
        log_action("FinanceAgent", "create_invoice", details[:200], "Rejected", status="rejected")
        if feedback:
            return f"Invoice NOT created. Feedback: {feedback}"
        return "Invoice NOT created. Human rejected."

    conn = _get_finance_db()
    try:
        conn.execute(
            """INSERT INTO invoices (invoice_number, client_name, client_email,
               description, amount, status, issued_date, due_date, created_at)
               VALUES (?, ?, ?, ?, ?, 'issued', ?, ?, ?)""",
            (
                invoice_number, client_name, client_email, description,
                amount, now.strftime("%Y-%m-%d"), due_date,
                now.isoformat(),
            ),
        )
        conn.commit()

        log_action(
            "FinanceAgent",
            "create_invoice",
            f"{invoice_number}: {client_name}",
            f"Amount: ${amount:.2f}",
            approved_by="human",
            status="completed",
        )

        return (
            f"✅ Invoice created:\n"
            f"  Number: {invoice_number}\n"
            f"  Client: {client_name}\n"
            f"  Amount: ${amount:.2f}\n"
            f"  Due: {due_date}\n"
            f"  Status: issued"
        )
    finally:
        conn.close()


async def list_invoices(
    status: Annotated[str, "Filter by status: all, draft, issued, paid, overdue"] = "all",
) -> str:
    """List invoices filtered by status."""
    conn = _get_finance_db()
    try:
        if status == "all":
            rows = conn.execute(
                "SELECT invoice_number, client_name, amount, status, due_date FROM invoices ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT invoice_number, client_name, amount, status, due_date FROM invoices WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()

        if not rows:
            return f"No invoices found{' with status: ' + status if status != 'all' else ''}."

        report = f"📋 Invoices ({status})\n{'═' * 60}\n"
        report += f"{'Invoice':<20} {'Client':<15} {'Amount':>10} {'Status':<10} {'Due':<12}\n"
        report += f"{'─' * 60}\n"
        for inv_num, client, amount, inv_status, due in rows:
            report += f"{inv_num:<20} {client:<15} ${amount:>9.2f} {inv_status:<10} {due or 'N/A':<12}\n"
        report += f"{'═' * 60}\n"

        log_action("FinanceAgent", "list_invoices", f"Filter: {status}", f"Found: {len(rows)}")
        return report
    finally:
        conn.close()


FINANCE_TOOLS = [log_expense, set_budget, get_budget_report, create_invoice, list_invoices]
