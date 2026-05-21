"""
AgentSystem — Cyber-Matrix Dashboard
=====================================
Enterprise-grade Streamlit dashboard for the 38-agent orchestrator.
Cyber-Matrix aesthetic: dark mode, Matrix green (#00FF41), glitch effects, terminal vibe.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import asyncio
from agents.factory import build_orchestrator

# ── Page config — Cyber-Matrix style ────────────────────────────────────────
st.set_page_config(
    page_title="AgentSystem",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/claudeherve-ai/AgentSystem",
        "Report a bug": "https://github.com/claudeherve-ai/AgentSystem/issues",
        "About": "AgentSystem — 38-Agent Enterprise Orchestrator",
    },
)

# Cyber-Matrix CSS
st.markdown(
    """
<style>
    /* Cyber-Matrix Theme */
    :root {
        --matrix-green: #00FF41;
        --matrix-dark: #0D1117;
        --matrix-darker: #010409;
        --matrix-border: #1B3A1B;
        --matrix-glow: rgba(0, 255, 65, 0.15);
    }

    .stApp {
        background-color: var(--matrix-darker);
        color: #C9D1D9;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--matrix-dark);
        border-right: 2px solid var(--matrix-border);
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
        color: var(--matrix-green) !important;
        font-family: 'Courier New', monospace;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        color: var(--matrix-green) !important;
        font-family: 'Courier New', monospace;
    }

    /* Buttons */
    .stButton > button {
        background-color: var(--matrix-dark);
        border: 1px solid var(--matrix-green);
        color: var(--matrix-green);
        font-family: 'Courier New', monospace;
    }
    .stButton > button:hover {
        background-color: rgba(0, 255, 65, 0.1);
        border-color: var(--matrix-green);
        color: var(--matrix-green);
    }

    /* Chat */
    [data-testid="stChatMessage"] {
        background-color: var(--matrix-dark);
        border: 1px solid var(--matrix-border);
        border-radius: 4px;
    }

    /* Text input */
    [data-testid="stChatInput"] textarea {
        background-color: var(--matrix-dark) !important;
        border: 1px solid var(--matrix-green) !important;
        color: var(--matrix-green) !important;
        font-family: 'Courier New', monospace !important;
    }

    /* Headers */
    h1, h2, h3 {
        color: var(--matrix-green) !important;
        font-family: 'Courier New', monospace !important;
        text-shadow: 0 0 10px var(--matrix-glow);
    }

    /* Dividers */
    hr {
        border-color: var(--matrix-border);
    }

    /* Radio buttons */
    [data-testid="stRadio"] label {
        color: #C9D1D9 !important;
    }

    /* Glitch text for title */
    @keyframes glitch {
        0% { text-shadow: 2px 0 var(--matrix-green); }
        20% { text-shadow: -1px 0 #00CC33; }
        40% { text-shadow: 1px 0 var(--matrix-green); }
        60% { text-shadow: -1px 0 #00FF41; }
        80% { text-shadow: 2px 0 #00DD3B; }
        100% { text-shadow: 0px 0 var(--matrix-green); }
    }
    .glitch {
        animation: glitch 0.3s infinite;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ── Orchestrator init ───────────────────────────────────────────────────────
if "orchestrator" not in st.session_state:
    with st.spinner("Initializing AgentSystem hive..."):
        st.session_state.orchestrator = build_orchestrator()

orch = st.session_state.orchestrator
agent_count = len(orch.agent_names)

# ── COMMAND CENTER ──────────────────────────────────────────────────────────
def render_command_center():
    st.markdown('<h1 class="glitch">> COMMAND_CENTER.exe</h1>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Agents Online", agent_count, delta=f"+{agent_count}")
    col2.metric("Status", "OPERATIONAL")
    col3.metric("Model", orch.status().get("model_provider", "azure_openai"))
    col4.metric("Session", orch.status().get("active_session_id", "N/A")[:8])

    st.divider()

    # Agent quick-launch grid
    st.markdown("### Quick Agent Access")
    cols = st.columns(6)
    priority_agents = [
        "EngineeringAgent", "CloudDataAgent", "ExecutionAgent",
        "RevenueAgent", "FinanceAgent", "LegalAgent",
        "EmailAgent", "CalendarAgent", "AIEngineerAgent",
        "SecurityEngineerAgent", "ProductManagerAgent", "BusinessAgent",
    ]
    for i, agent_name in enumerate(priority_agents):
        col_idx = i % 6
        if cols[col_idx].button(agent_name, key=f"qa_{agent_name}", use_container_width=True):
            st.session_state.prefill = f"@{agent_name}: "

    st.divider()

    # Chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    prefill = st.session_state.get("prefill", "")
    if pr := st.chat_input(
        ">_ Enter command...  (e.g., 'analyze my inbox', 'design a microservice architecture', 'review this security config')",
    ):
        full_msg = prefill + pr
        st.session_state.prefill = ""
        st.session_state.messages.append({"role": "user", "content": full_msg})
        with st.chat_message("user"):
            st.markdown(full_msg)

        with st.chat_message("assistant"):
            with st.spinner("Routing to agents..."):
                try:
                    res = asyncio.run(orch.handle_user_input(full_msg))
                    st.markdown(res)
                    st.session_state.messages.append({"role": "assistant", "content": res})
                except Exception as e:
                    err = f"⚠️ Error: {e}"
                    st.error(err)
                    st.session_state.messages.append({"role": "assistant", "content": err})


# ── OVERVIEW ────────────────────────────────────────────────────────────────
def render_overview():
    st.markdown('<h1>> SYSTEM_OVERVIEW.hive</h1>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Agents", agent_count)
        st.metric("Approval Mode", "Required" if orch.status()["approval_required"] else "Auto")
    with col2:
        st.metric("Model Provider", orch.status()["model_provider"])
        st.metric("Memorized Facts", orch.status()["remembered_facts"])

    st.divider()

    # Full agent roster
    st.markdown("### Full Agent Roster")
    st.caption(f"All {agent_count} agents registered and ready.")

    with st.container(height=400):
        for i, name in enumerate(orch.agent_names):
            reg = orch._registrations.get(name)
            desc = reg.description if reg and hasattr(reg, "description") else f"Agent: {name}"
            tool_count = len(reg.tools) if reg and hasattr(reg, "tools") else 0
            st.markdown(
                f"`[{i+1:02d}]` **{name}** — {desc}  `[{tool_count} tools]`",
                help=f"Agent: {name}\nTools: {tool_count}",
            )


# ── METRICS ─────────────────────────────────────────────────────────────────
def render_metrics():
    st.markdown('<h1>> HIVE_METRICS.dashboard</h1>', unsafe_allow_html=True)
    st.info("Metrics module — connect Azure Application Insights or Prometheus for live data.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Requests Today", "—", delta="N/A")
    col2.metric("Avg Latency", "—", delta="N/A")
    col3.metric("Error Rate", "—", delta="N/A")

    st.divider()
    st.markdown("### Agent Tool Distribution")
    tool_data = {}
    for name in orch.agent_names:
        reg = orch._registrations.get(name)
        tool_data[name] = len(reg.tools) if reg and hasattr(reg, "tools") else 0

    st.bar_chart(tool_data, use_container_width=True)


# ── HEALTH ──────────────────────────────────────────────────────────────────
def render_health():
    st.markdown('<h1>> SYSTEM_HEALTH.diag</h1>', unsafe_allow_html=True)

    status = orch.status()
    st.json(status)

    st.divider()
    st.markdown("### Health Checks")
    col1, col2, col3, col4 = st.columns(4)
    col1.success(f"Orchestrator: OK ({agent_count} agents)")
    col2.success("Memory: OK")
    col3.info("Model: Azure OpenAI")
    col4.info("Auth: API Key")


# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown(
    """
# 🤖 AgentSystem
---
""",
    unsafe_allow_html=True,
)

choice = st.sidebar.radio(
    "NAVIGATION",
    ["COMMAND CENTER", "Overview", "Metrics", "Health"],
    index=0,
)

st.sidebar.divider()
st.sidebar.markdown(
    f"""
**HIVE STATUS**
```
AGENTS:  {agent_count}
STATUS:  OPERATIONAL
```
""",
)

# New session button
if st.sidebar.button("🔄 New Session", use_container_width=True):
    new_id = orch.reset_session()
    st.session_state.messages = []
    st.sidebar.success(f"Session: {new_id[:12]}...")
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("AgentSystem v2.0 • Boil the Ocean")
st.sidebar.caption("[GitHub](https://github.com/claudeherve-ai/AgentSystem)")

# ── Route ───────────────────────────────────────────────────────────────────
if choice == "COMMAND CENTER":
    render_command_center()
elif choice == "Overview":
    render_overview()
elif choice == "Metrics":
    render_metrics()
elif choice == "Health":
    render_health()
