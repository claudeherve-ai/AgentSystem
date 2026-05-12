"""
AgentSystem Monitoring Dashboard
Run with: streamlit run dashboard.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AgentSystem Dashboard",
    page_icon="🤖",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
AUDIT_DB = BASE_DIR / "memory" / "audit.db"
FINANCE_DB = BASE_DIR / "memory" / "finance.db"
BUSINESS_DB = BASE_DIR / "memory" / "business.db"


def _get_connection(db_path: Path) -> sqlite3.Connection | None:
    """Return a read-only SQLite connection or None if the file is missing."""
    if not db_path.exists():
        return None
    return sqlite3.connect(str(db_path))


def query_df(db_path: Path, sql: str, params: tuple = ()) -> pd.DataFrame | None:
    """Execute *sql* against *db_path* and return a DataFrame, or None."""
    conn = _get_connection(db_path)
    if conn is None:
        return None
    try:
        return pd.read_sql(sql, conn, params=params)
    except Exception as exc:
        st.error(f"Query error on {db_path.name}: {exc}")
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("🤖 AgentSystem")
page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Agent Activity", "Finance", "Customers", "System Health"],
)

# =========================================================================
# OVERVIEW
# =========================================================================
if page == "Overview":
    st.title("📊 Overview")

    if not AUDIT_DB.exists():
        st.info("Audit database not found. Run agents to generate data.")
    else:
        # --- Metric cards ---------------------------------------------------
        total_actions = query_df(AUDIT_DB, "SELECT COUNT(*) AS cnt FROM agent_actions")
        today_actions = query_df(
            AUDIT_DB,
            "SELECT COUNT(*) AS cnt FROM agent_actions WHERE date(timestamp) = date('now')",
        )
        error_count = query_df(
            AUDIT_DB,
            "SELECT COUNT(*) AS cnt FROM agent_actions WHERE status = 'error'",
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Actions", int(total_actions["cnt"].iloc[0]) if total_actions is not None else 0)
        col2.metric("Today's Actions", int(today_actions["cnt"].iloc[0]) if today_actions is not None else 0)
        col3.metric("Errors", int(error_count["cnt"].iloc[0]) if error_count is not None else 0)

        # --- Pie chart: actions by agent ------------------------------------
        agent_dist = query_df(
            AUDIT_DB,
            "SELECT agent_name, COUNT(*) AS count FROM agent_actions GROUP BY agent_name",
        )
        if agent_dist is not None and not agent_dist.empty:
            fig_pie = px.pie(
                agent_dist,
                names="agent_name",
                values="count",
                title="Actions by Agent",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- Bar chart: activity over last 30 days --------------------------
        activity_30d = query_df(
            AUDIT_DB,
            """
            SELECT date(timestamp) AS day, agent_name, COUNT(*) AS count
            FROM agent_actions
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY day, agent_name
            ORDER BY day
            """,
        )
        if activity_30d is not None and not activity_30d.empty:
            fig_bar = px.bar(
                activity_30d,
                x="day",
                y="count",
                color="agent_name",
                title="Activity Over Last 30 Days",
                labels={"day": "Date", "count": "Actions"},
            )
            st.plotly_chart(fig_bar, use_container_width=True)

# =========================================================================
# AGENT ACTIVITY
# =========================================================================
elif page == "Agent Activity":
    st.title("🕵️ Agent Activity")

    if not AUDIT_DB.exists():
        st.info("Audit database not found. Run agents to generate data.")
    else:
        agents = query_df(
            AUDIT_DB,
            "SELECT DISTINCT agent_name FROM agent_actions ORDER BY agent_name",
        )
        agent_names = ["All"] + (agents["agent_name"].tolist() if agents is not None else [])
        selected_agent = st.selectbox("Filter by Agent", agent_names)

        if selected_agent == "All":
            actions = query_df(
                AUDIT_DB,
                "SELECT * FROM agent_actions ORDER BY id DESC LIMIT 100",
            )
        else:
            actions = query_df(
                AUDIT_DB,
                "SELECT * FROM agent_actions WHERE agent_name = ? ORDER BY id DESC LIMIT 100",
                (selected_agent,),
            )

        if actions is not None and not actions.empty:
            st.dataframe(actions, use_container_width=True)
        else:
            st.info("No actions recorded yet.")

# =========================================================================
# FINANCE
# =========================================================================
elif page == "Finance":
    st.title("💰 Finance")

    if not FINANCE_DB.exists():
        st.info("Finance database not found. No financial data available yet.")
    else:
        # --- Bar chart: spending by category --------------------------------
        expenses = query_df(
            FINANCE_DB,
            "SELECT category, SUM(amount) AS total FROM expenses GROUP BY category ORDER BY total DESC",
        )
        if expenses is not None and not expenses.empty:
            fig_exp = px.bar(
                expenses,
                x="category",
                y="total",
                title="Spending by Category",
                labels={"category": "Category", "total": "Total Spent"},
            )
            st.plotly_chart(fig_exp, use_container_width=True)
        else:
            st.info("No expense records found.")

        # --- Budget limits table --------------------------------------------
        st.subheader("Budget Limits")
        budgets = query_df(FINANCE_DB, "SELECT * FROM budgets")
        if budgets is not None and not budgets.empty:
            st.dataframe(budgets, use_container_width=True)
        else:
            st.info("No budget records found.")

        # --- Recent invoices table ------------------------------------------
        st.subheader("Recent Invoices")
        invoices = query_df(
            FINANCE_DB,
            "SELECT * FROM invoices ORDER BY rowid DESC LIMIT 50",
        )
        if invoices is not None and not invoices.empty:
            st.dataframe(invoices, use_container_width=True)
        else:
            st.info("No invoice records found.")

# =========================================================================
# CUSTOMERS
# =========================================================================
elif page == "Customers":
    st.title("👥 Customers")

    if not BUSINESS_DB.exists():
        st.info("Business database not found. No customer data available yet.")
    else:
        # --- Customers table ------------------------------------------------
        st.subheader("Customers")
        customers = query_df(BUSINESS_DB, "SELECT * FROM customers")
        if customers is not None and not customers.empty:
            st.dataframe(customers, use_container_width=True)
        else:
            st.info("No customer records found.")

        # --- Recent interactions with customer name -------------------------
        st.subheader("Recent Interactions")
        interactions = query_df(
            BUSINESS_DB,
            """
            SELECT i.*, c.name AS customer_name
            FROM interactions i
            LEFT JOIN customers c ON i.customer_id = c.id
            ORDER BY i.rowid DESC
            LIMIT 50
            """,
        )
        if interactions is not None and not interactions.empty:
            st.dataframe(interactions, use_container_width=True)
        else:
            st.info("No interaction records found.")

        # --- Overdue follow-ups ---------------------------------------------
        st.subheader("Overdue Follow-ups")
        overdue = query_df(
            BUSINESS_DB,
            """
            SELECT i.*, c.name AS customer_name
            FROM interactions i
            LEFT JOIN customers c ON i.customer_id = c.id
            WHERE date(i.follow_up_date) <= date('now')
            ORDER BY i.follow_up_date ASC
            """,
        )
        if overdue is not None and not overdue.empty:
            st.dataframe(overdue, use_container_width=True)
        else:
            st.info("No overdue follow-ups.")

        # --- Proposals ------------------------------------------------------
        st.subheader("Proposals")
        proposals = query_df(BUSINESS_DB, "SELECT * FROM proposals ORDER BY rowid DESC LIMIT 50")
        if proposals is not None and not proposals.empty:
            st.dataframe(proposals, use_container_width=True)
        else:
            st.info("No proposal records found.")

# =========================================================================
# SYSTEM HEALTH
# =========================================================================
elif page == "System Health":
    st.title("🩺 System Health")

    if not AUDIT_DB.exists():
        st.info("Audit database not found. Run agents to generate data.")
    else:
        # --- Metrics --------------------------------------------------------
        total = query_df(AUDIT_DB, "SELECT COUNT(*) AS cnt FROM agent_actions")
        errors = query_df(
            AUDIT_DB,
            "SELECT COUNT(*) AS cnt FROM agent_actions WHERE status = 'error'",
        )

        total_val = int(total["cnt"].iloc[0]) if total is not None else 0
        error_val = int(errors["cnt"].iloc[0]) if errors is not None else 0
        error_rate = (error_val / total_val * 100) if total_val > 0 else 0.0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Actions", total_val)
        col2.metric("Errors", error_val)
        col3.metric("Error Rate", f"{error_rate:.1f}%")

        # --- Line chart: errors over last 30 days --------------------------
        error_trend = query_df(
            AUDIT_DB,
            """
            SELECT date(timestamp) AS day, COUNT(*) AS errors
            FROM agent_actions
            WHERE status = 'error' AND timestamp >= date('now', '-30 days')
            GROUP BY day
            ORDER BY day
            """,
        )
        if error_trend is not None and not error_trend.empty:
            fig_line = px.line(
                error_trend,
                x="day",
                y="errors",
                title="Errors Over Last 30 Days",
                labels={"day": "Date", "errors": "Error Count"},
            )
            st.plotly_chart(fig_line, use_container_width=True)

        # --- Recent errors table --------------------------------------------
        st.subheader("Recent Errors")
        recent_errors = query_df(
            AUDIT_DB,
            "SELECT * FROM agent_actions WHERE status = 'error' ORDER BY id DESC LIMIT 10",
        )
        if recent_errors is not None and not recent_errors.empty:
            st.dataframe(recent_errors, use_container_width=True)
        else:
            st.info("No errors recorded. 🎉")
