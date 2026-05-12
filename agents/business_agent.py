"""
AgentSystem — Business Operations Agent.

Manages customer relationships, proposals, and business workflows.
Uses local SQLite CRM for persistent storage.
"""

import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails import Guardrails
from guardrails.approval import HumanApproval
from tools.audit import log_action

logger = logging.getLogger(__name__)

_guardrails = Guardrails()
_approval = HumanApproval()

BUSINESS_DB = Path(__file__).resolve().parent.parent / "memory" / "business.db"


def _get_business_db() -> sqlite3.Connection:
    """Get a connection to the business CRM database."""
    BUSINESS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(BUSINESS_DB))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            company TEXT,
            status TEXT DEFAULT 'active',
            source TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            interaction_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            details TEXT,
            follow_up_date TEXT,
            follow_up_action TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'draft',
            valid_until TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status);
        CREATE INDEX IF NOT EXISTS idx_interactions_customer ON interactions(customer_id);
        CREATE INDEX IF NOT EXISTS idx_proposals_customer ON proposals(customer_id);
        CREATE INDEX IF NOT EXISTS idx_interactions_followup ON interactions(follow_up_date);
    """)
    conn.commit()
    return conn


async def create_customer(
    name: Annotated[str, "Customer/contact full name"],
    email: Annotated[str, "Customer email address"] = "",
    phone: Annotated[str, "Customer phone number"] = "",
    company: Annotated[str, "Customer company/organization"] = "",
    source: Annotated[str, "How the customer was acquired (referral, website, cold-outreach)"] = "",
    notes: Annotated[str, "Additional notes about the customer"] = "",
) -> str:
    """Create a new customer record in the CRM."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_business_db()
    try:
        cursor = conn.execute(
            """INSERT INTO customers (name, email, phone, company, source, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, email, phone, company, source, notes, now, now),
        )
        conn.commit()
        cid = cursor.lastrowid

        log_action("BusinessAgent", "create_customer", f"{name} ({email})", f"ID: {cid}")

        return (
            f"✅ Customer created:\n"
            f"  ID: {cid}\n"
            f"  Name: {name}\n"
            f"  Email: {email or 'N/A'}\n"
            f"  Company: {company or 'N/A'}\n"
            f"  Source: {source or 'N/A'}"
        )
    finally:
        conn.close()


async def log_interaction(
    customer_id: Annotated[int, "Customer ID from the CRM"],
    interaction_type: Annotated[str, "Type: email, call, meeting, chat, note"],
    summary: Annotated[str, "Brief summary of the interaction"],
    details: Annotated[str, "Full details of the interaction"] = "",
    follow_up_date: Annotated[str, "Follow-up date in YYYY-MM-DD format"] = "",
    follow_up_action: Annotated[str, "What follow-up action to take"] = "",
) -> str:
    """Log an interaction with a customer."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_business_db()
    try:
        # Verify customer exists
        customer = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return f"Error: Customer ID {customer_id} not found."

        conn.execute(
            """INSERT INTO interactions
               (customer_id, interaction_type, summary, details, follow_up_date, follow_up_action, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, interaction_type, summary, details,
             follow_up_date or None, follow_up_action or None, now),
        )
        conn.commit()

        log_action("BusinessAgent", "log_interaction", f"Customer {customer_id}: {interaction_type}", summary[:100])

        follow_up_msg = ""
        if follow_up_date:
            follow_up_msg = f"\n  📌 Follow-up: {follow_up_date} — {follow_up_action}"

        return (
            f"✅ Interaction logged for {customer[0]}:\n"
            f"  Type: {interaction_type}\n"
            f"  Summary: {summary}"
            f"{follow_up_msg}"
        )
    finally:
        conn.close()


async def list_customers(
    status: Annotated[str, "Filter: active, inactive, all"] = "active",
) -> str:
    """List customers from the CRM."""
    conn = _get_business_db()
    try:
        if status == "all":
            rows = conn.execute(
                "SELECT id, name, email, company, status FROM customers ORDER BY name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, email, company, status FROM customers WHERE status = ? ORDER BY name",
                (status,),
            ).fetchall()

        if not rows:
            return f"No customers found{' with status: ' + status if status != 'all' else ''}."

        report = f"👥 Customers ({status})\n{'═' * 65}\n"
        report += f"{'ID':<5} {'Name':<20} {'Email':<25} {'Company':<15}\n"
        report += f"{'─' * 65}\n"
        for cid, name, email, company, _ in rows:
            report += f"{cid:<5} {name:<20} {email or 'N/A':<25} {company or 'N/A':<15}\n"
        report += f"{'═' * 65}\n"
        report += f"Total: {len(rows)} customer(s)\n"

        log_action("BusinessAgent", "list_customers", f"Filter: {status}", f"Found: {len(rows)}")
        return report
    finally:
        conn.close()


async def draft_proposal(
    customer_id: Annotated[int, "Customer ID from the CRM"],
    title: Annotated[str, "Proposal title"],
    description: Annotated[str, "Proposal description and scope of work"],
    amount: Annotated[float, "Proposed amount/fee"],
    valid_days: Annotated[int, "Number of days the proposal is valid"] = 30,
) -> str:
    """Draft a business proposal for a customer. Does NOT send."""
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    proposal_number = f"PROP-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"
    valid_until = (now + timedelta(days=valid_days)).strftime("%Y-%m-%d")

    conn = _get_business_db()
    try:
        customer = conn.execute("SELECT name, email FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return f"Error: Customer ID {customer_id} not found."

        conn.execute(
            """INSERT INTO proposals
               (proposal_number, customer_id, title, description, amount, status, valid_until, created_at)
               VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)""",
            (proposal_number, customer_id, title, description, amount, valid_until, now.isoformat()),
        )
        conn.commit()

        log_action(
            "BusinessAgent",
            "draft_proposal",
            f"{proposal_number} for {customer[0]}",
            f"Amount: ${amount:.2f}",
            status="drafted",
        )

        return (
            f"📄 DRAFT PROPOSAL\n"
            f"{'═' * 45}\n"
            f"  Number: {proposal_number}\n"
            f"  Client: {customer[0]} ({customer[1] or 'N/A'})\n"
            f"  Title: {title}\n"
            f"  Amount: ${amount:,.2f}\n"
            f"  Valid until: {valid_until}\n"
            f"{'─' * 45}\n"
            f"  {description}\n"
            f"{'═' * 45}\n"
            f"  Status: DRAFT — approve to send to client"
        )
    finally:
        conn.close()


async def get_pending_followups() -> str:
    """Get all pending follow-ups that are due today or overdue."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = _get_business_db()
    try:
        rows = conn.execute(
            """SELECT i.follow_up_date, i.follow_up_action, i.summary, c.name, c.email
               FROM interactions i
               JOIN customers c ON i.customer_id = c.id
               WHERE i.follow_up_date IS NOT NULL AND i.follow_up_date <= ?
               ORDER BY i.follow_up_date""",
            (today,),
        ).fetchall()

        if not rows:
            return "✅ No pending follow-ups. You're all caught up!"

        report = f"📌 Pending Follow-ups (due ≤ {today})\n{'═' * 60}\n"
        for date, action, summary, name, email in rows:
            overdue = " 🚨 OVERDUE" if date < today else ""
            report += (
                f"  [{date}]{overdue} {name} ({email or 'no email'})\n"
                f"    Action: {action}\n"
                f"    Context: {summary}\n\n"
            )
        report += f"Total: {len(rows)} follow-up(s)\n"

        log_action("BusinessAgent", "get_pending_followups", today, f"Found: {len(rows)}")
        return report
    finally:
        conn.close()


BUSINESS_TOOLS = [
    create_customer,
    log_interaction,
    list_customers,
    draft_proposal,
    get_pending_followups,
]
