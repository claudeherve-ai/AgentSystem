"""
AgentSystem — Aurora Dashboard
==============================
A premium Streamlit control plane for the multi-agent orchestrator.

Design language: "Aurora" — deep indigo glass surfaces, a violet→cyan accent
gradient, soft ambient glows, and clean Inter / JetBrains Mono typography.
All orchestrator API calls are preserved from the original dashboard:
build_orchestrator(), orch.agent_names, orch.status(), orch.handle_user_input(),
orch.reset_session(), orch._registrations.
"""
import sys
import os
import html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import asyncio
from agents.factory import build_orchestrator

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AgentSystem · Aurora",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/claudeherve-ai/AgentSystem",
        "Report a bug": "https://github.com/claudeherve-ai/AgentSystem/issues",
        "About": "AgentSystem — Multi-Agent Enterprise Orchestrator",
    },
)

# ── Aurora theme ────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-0: #070912;
        --bg-1: #0d1020;
        --glass: rgba(22, 27, 48, 0.55);
        --glass-brd: rgba(255, 255, 255, 0.08);
        --txt: #e7ecff;
        --txt-dim: #9aa3c7;
        --accent-a: #7c5cff;
        --accent-b: #28e0c8;
        --accent-c: #ff7ac6;
        --grad: linear-gradient(120deg, #7c5cff 0%, #4d8bff 45%, #28e0c8 100%);
        --grad-soft: linear-gradient(120deg, rgba(124,92,255,0.18), rgba(40,224,200,0.14));
    }

    /* Ambient gradient background */
    .stApp {
        background:
            radial-gradient(1100px 600px at 12% -8%, rgba(124,92,255,0.22), transparent 60%),
            radial-gradient(900px 520px at 110% 8%, rgba(40,224,200,0.16), transparent 55%),
            radial-gradient(700px 700px at 50% 120%, rgba(255,122,198,0.10), transparent 60%),
            var(--bg-0);
        color: var(--txt);
        font-family: 'Inter', -apple-system, system-ui, sans-serif;
    }

    .block-container { padding-top: 2.2rem; max-width: 1320px; }

    /* Typography */
    h1, h2, h3, h4 { font-family: 'Inter', sans-serif !important; color: var(--txt) !important; letter-spacing: -0.02em; }
    h1 { font-weight: 800 !important; }
    p, span, label, li { color: var(--txt); }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(13,16,32,0.95), rgba(7,9,18,0.95));
        border-right: 1px solid var(--glass-brd);
        backdrop-filter: blur(18px);
    }
    [data-testid="stSidebar"] * { color: var(--txt); }

    /* Native metric tiles → glass */
    [data-testid="stMetric"] {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: 18px;
        padding: 18px 20px;
        backdrop-filter: blur(14px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.35);
    }
    [data-testid="stMetriclabel"], [data-testid="stMetricLabel"] p {
        color: var(--txt-dim) !important; font-size: 0.78rem !important;
        text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--txt) !important; font-family: 'Inter', sans-serif !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricDelta"] { color: var(--accent-b) !important; }

    /* Buttons */
    .stButton > button {
        background: var(--grad-soft);
        border: 1px solid var(--glass-brd);
        color: var(--txt);
        border-radius: 14px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        padding: 10px 14px;
        transition: all 0.18s ease;
    }
    .stButton > button:hover {
        border-color: rgba(124,92,255,0.7);
        box-shadow: 0 0 0 1px rgba(124,92,255,0.4), 0 10px 28px rgba(124,92,255,0.25);
        transform: translateY(-1px);
        color: #fff;
    }

    /* Chat surfaces */
    [data-testid="stChatMessage"] {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: 16px;
        backdrop-filter: blur(12px);
    }
    [data-testid="stChatInput"] textarea {
        background: rgba(13,16,32,0.85) !important;
        border: 1px solid var(--glass-brd) !important;
        color: var(--txt) !important;
        border-radius: 14px !important;
        font-family: 'Inter', sans-serif !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: rgba(124,92,255,0.7) !important;
        box-shadow: 0 0 0 2px rgba(124,92,255,0.25) !important;
    }
    /* Send button — make it visible and clickable */
    [data-testid="stChatInput"] button {
        background: linear-gradient(135deg, var(--accent-a), #9b6dff) !important;
        border: none !important;
        border-radius: 10px !important;
        color: white !important;
        cursor: pointer !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stChatInput"] button:hover {
        background: linear-gradient(135deg, #9b6dff, var(--accent-b)) !important;
        box-shadow: 0 0 12px rgba(124,92,255,0.5) !important;
    }
    [data-testid="stChatInput"] button:disabled {
        opacity: 0.4 !important;
        cursor: not-allowed !important;
    }
    /* Input container background */
    [data-testid="stChatInput"] {
        background: rgba(13,16,32,0.6) !important;
        border-radius: 16px !important;
        padding: 4px !important;
    }

    /* Radio nav → pill list */
    [data-testid="stSidebar"] [role="radiogroup"] label {
        background: rgba(255,255,255,0.03);
        border: 1px solid transparent;
        border-radius: 12px;
        padding: 9px 13px !important;
        margin-bottom: 6px;
        transition: all 0.15s ease;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: var(--grad-soft);
        border-color: var(--glass-brd);
    }

    hr { border-color: var(--glass-brd) !important; }
    code { color: var(--accent-b); background: rgba(40,224,200,0.08); border-radius: 6px; }

    /* JSON / dataframe glass */
    [data-testid="stJson"] {
        background: var(--glass) !important;
        border: 1px solid var(--glass-brd);
        border-radius: 16px; padding: 8px;
    }

    /* ── Custom components ─────────────────────────────────────────────── */
    .hero {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: 24px;
        padding: 26px 30px;
        margin-bottom: 18px;
        backdrop-filter: blur(16px);
        box-shadow: 0 18px 50px rgba(0,0,0,0.45);
        position: relative; overflow: hidden;
    }
    .hero::before {
        content: ""; position: absolute; inset: 0;
        background: var(--grad); opacity: 0.10;
    }
    .hero-eyebrow {
        font-family: 'JetBrains Mono', monospace; font-size: 0.74rem;
        letter-spacing: 0.22em; text-transform: uppercase;
        color: var(--accent-b); position: relative;
    }
    .hero-title {
        font-size: 2.0rem; font-weight: 800; margin: 6px 0 4px; position: relative;
        background: var(--grad); -webkit-background-clip: text;
        -webkit-text-fill-color: transparent; background-clip: text;
    }
    .hero-sub { color: var(--txt-dim); font-size: 0.96rem; position: relative; }

    .pill {
        display: inline-flex; align-items: center; gap: 7px;
        background: rgba(40,224,200,0.10); border: 1px solid rgba(40,224,200,0.30);
        color: var(--accent-b); border-radius: 999px;
        padding: 5px 13px; font-size: 0.78rem; font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-b);
           box-shadow: 0 0 10px var(--accent-b); animation: pulse 1.8s infinite; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

    .agent-card {
        background: var(--glass); border: 1px solid var(--glass-brd);
        border-radius: 16px; padding: 14px 16px; margin-bottom: 10px;
        backdrop-filter: blur(10px); transition: all 0.18s ease;
    }
    .agent-card:hover {
        border-color: rgba(124,92,255,0.55);
        box-shadow: 0 10px 26px rgba(124,92,255,0.18);
        transform: translateY(-2px);
    }
    .agent-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .agent-name { font-weight: 700; font-size: 0.98rem; }
    .agent-idx {
        font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
        color: var(--accent-a); margin-right: 8px;
    }
    .agent-desc { color: var(--txt-dim); font-size: 0.84rem; margin-top: 5px; line-height: 1.4; }
    .tool-badge {
        font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
        background: var(--grad-soft); border: 1px solid var(--glass-brd);
        color: var(--txt); border-radius: 999px; padding: 3px 10px; white-space: nowrap;
    }
    .section-label {
        font-family: 'JetBrains Mono', monospace; font-size: 0.76rem;
        letter-spacing: 0.18em; text-transform: uppercase; color: var(--txt-dim);
        margin: 6px 0 10px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ── Orchestrator init ───────────────────────────────────────────────────────
if "orchestrator" not in st.session_state:
    with st.spinner("Spinning up the agent mesh…"):
        st.session_state.orchestrator = build_orchestrator()

orch = st.session_state.orchestrator
agent_count = len(orch.agent_names)


def _hero(eyebrow: str, title: str, sub: str):
    st.markdown(
        f"""
<div class="hero">
  <div class="hero-eyebrow">{html.escape(eyebrow)}</div>
  <div class="hero-title">{html.escape(title)}</div>
  <div class="hero-sub">{html.escape(sub)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ── COMMAND CENTER ──────────────────────────────────────────────────────────
def render_command_center():
    status = orch.status()
    _hero(
        "Command Center",
        "Talk to the hive",
        "Describe any goal in plain language — the orchestrator routes it to the "
        "right specialist agents and composes the answer.",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Agents Online", agent_count, delta="ready")
    c2.metric("Status", "Operational")
    c3.metric("Model Provider", status.get("model_provider", "azure_openai"))
    sid = (status.get("active_session_id") or "—")
    c4.metric("Session", sid[:8])

    st.markdown('<div class="section-label">Quick agent access</div>', unsafe_allow_html=True)
    cols = st.columns(6)
    priority_agents = [
        "EngineeringAgent", "CloudDataAgent", "ExecutionAgent",
        "RevenueAgent", "FinanceAgent", "LegalAgent",
        "EmailAgent", "CalendarAgent", "AIEngineerAgent",
        "SecurityEngineerAgent", "ProductManagerAgent", "BusinessAgent",
    ]
    for i, agent_name in enumerate(priority_agents):
        if cols[i % 6].button(agent_name, key=f"qa_{agent_name}", use_container_width=True):
            st.session_state.prefill = f"@{agent_name}: "

    st.divider()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    prefill = st.session_state.get("prefill", "")
    if pr := st.chat_input(
        "Ask anything — e.g. 'design a resilient microservice architecture', "
        "'model SaaS unit economics', 'triage this incident'",
    ):
        full_msg = prefill + pr
        st.session_state.prefill = ""
        st.session_state.messages.append({"role": "user", "content": full_msg})
        with st.chat_message("user"):
            st.markdown(full_msg)

        with st.chat_message("assistant"):
            with st.spinner("Routing across the agent mesh…"):
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
    status = orch.status()
    _hero(
        "System Overview",
        "The full roster",
        f"{agent_count} specialist agents are registered and standing by, each with "
        "its own toolset wired into the shared power-tools layer.",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Agents", agent_count)
    c2.metric("Approval Mode", "Required" if status["approval_required"] else "Auto")
    c3.metric("Model Provider", status["model_provider"])
    c4.metric("Memorized Facts", status["remembered_facts"])

    st.markdown('<div class="section-label">Agent roster</div>', unsafe_allow_html=True)

    with st.container(height=460):
        grid = st.columns(2)
        for i, name in enumerate(orch.agent_names):
            reg = orch._registrations.get(name)
            desc = reg.description if reg and hasattr(reg, "description") else f"Agent: {name}"
            tool_count = len(reg.tools) if reg and hasattr(reg, "tools") else 0
            grid[i % 2].markdown(
                f"""
<div class="agent-card">
  <div class="agent-head">
    <div><span class="agent-idx">{i+1:02d}</span><span class="agent-name">{html.escape(name)}</span></div>
    <span class="tool-badge">{tool_count} tools</span>
  </div>
  <div class="agent-desc">{html.escape(desc)}</div>
</div>
""",
                unsafe_allow_html=True,
            )


# ── METRICS ─────────────────────────────────────────────────────────────────
def render_metrics():
    _hero(
        "Hive Metrics",
        "Telemetry at a glance",
        "Live request metrics light up when Azure Application Insights or Prometheus "
        "is connected. Tool distribution below is computed from the live registry.",
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Requests Today", "—", delta="connect APM")
    c2.metric("Avg Latency", "—", delta="connect APM")
    c3.metric("Error Rate", "—", delta="connect APM")

    st.markdown('<div class="section-label">Agent tool distribution</div>', unsafe_allow_html=True)
    tool_data = {}
    for name in orch.agent_names:
        reg = orch._registrations.get(name)
        tool_data[name] = len(reg.tools) if reg and hasattr(reg, "tools") else 0
    st.bar_chart(tool_data, use_container_width=True, color="#7c5cff")


# ── HEALTH ──────────────────────────────────────────────────────────────────
def render_health():
    status = orch.status()
    _hero(
        "System Health",
        "Diagnostics",
        "Raw orchestrator status plus a quick read on the core subsystems.",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.success(f"Orchestrator · {agent_count} agents")
    c2.success("Memory · OK")
    c3.info(f"Model · {status.get('model_provider', 'azure_openai')}")
    c4.info("Auth · API Key")

    st.markdown('<div class="section-label">Raw status</div>', unsafe_allow_html=True)
    st.json(status)


# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown(
    """
<div style="padding: 6px 2px 14px;">
  <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; letter-spacing:0.22em;
              color:#28e0c8; text-transform:uppercase;">Aurora Console</div>
  <div style="font-size:1.5rem; font-weight:800; margin-top:4px;
              background:linear-gradient(120deg,#7c5cff,#28e0c8); -webkit-background-clip:text;
              -webkit-text-fill-color:transparent; background-clip:text;">✦ AgentSystem</div>
</div>
""",
    unsafe_allow_html=True,
)

choice = st.sidebar.radio(
    "Navigation",
    ["Command Center", "Overview", "Metrics", "Health"],
    index=0,
    label_visibility="collapsed",
)

st.sidebar.markdown(
    f"""
<div style="margin-top:10px; padding:14px 16px; border:1px solid rgba(255,255,255,0.08);
            border-radius:16px; background:rgba(22,27,48,0.55);">
  <div style="display:flex; align-items:center; gap:8px;">
    <span class="dot"></span>
    <span style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#9aa3c7;">SYSTEM ONLINE</span>
  </div>
  <div style="margin-top:10px; font-family:'JetBrains Mono',monospace; font-size:0.82rem; color:#e7ecff;">
    {agent_count} agents · operational
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.sidebar.write("")
if st.sidebar.button("🔄 New Session", use_container_width=True):
    new_id = orch.reset_session()
    st.session_state.messages = []
    st.sidebar.success(f"Session: {new_id[:12]}…")
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("AgentSystem · Aurora · Boil the Ocean")
st.sidebar.caption("[GitHub](https://github.com/claudeherve-ai/AgentSystem)")

# ── Route ───────────────────────────────────────────────────────────────────
if choice == "Command Center":
    render_command_center()
elif choice == "Overview":
    render_overview()
elif choice == "Metrics":
    render_metrics()
elif choice == "Health":
    render_health()
