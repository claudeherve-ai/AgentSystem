"""
AgentSystem — CYBER-MATRIX Console
==================================
A Streamlit control plane for the multi-agent orchestrator.

Design language: "Cyber-Matrix" — phosphor-green terminal glow on deep black,
scanline overlays, glitch accents, JetBrains Mono everywhere, neon green
primary (#00ff41) with cyan (#00e5ff) secondary and amber (#ffb000) alerts.
All orchestrator API calls preserved: build_orchestrator(), orch.agent_names,
orch.status(), orch.handle_user_input(), orch.reset_session(),
orch._registrations.
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
    page_title="AgentSystem · CYBER-MATRIX",
    page_icon="▓",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/claudeherve-ai/AgentSystem",
        "Report a bug": "https://github.com/claudeherve-ai/AgentSystem/issues",
        "About": "AgentSystem — Multi-Agent Enterprise Orchestrator",
    },
)

# ── Cyber-Matrix theme ──────────────────────────────────────────────────────
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Share+Tech+Mono&display=swap');

    :root {
        --bg-0: #020604;
        --bg-1: #04120a;
        --glass: rgba(4, 24, 12, 0.66);
        --glass-brd: rgba(0, 255, 65, 0.16);
        --txt: #c9ffd9;
        --txt-dim: #4d9a68;
        --neon: #00ff41;
        --neon-soft: rgba(0, 255, 65, 0.14);
        --cyan: #00e5ff;
        --amber: #ffb000;
        --grad: linear-gradient(120deg, #00ff41 0%, #00e5ff 100%);
        --grad-soft: linear-gradient(120deg, rgba(0,255,65,0.14), rgba(0,229,255,0.10));
    }

    /* Ambient background + scanlines */
    .stApp {
        background:
            radial-gradient(1000px 500px at 15% -10%, rgba(0,255,65,0.10), transparent 60%),
            radial-gradient(800px 500px at 110% 10%, rgba(0,229,255,0.07), transparent 55%),
            var(--bg-0);
        color: var(--txt);
        font-family: 'JetBrains Mono', 'Share Tech Mono', monospace;
    }
    .stApp::before {
        content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 9999;
        background: repeating-linear-gradient(
            0deg, rgba(0,0,0,0.22) 0px, rgba(0,0,0,0.22) 1px,
            transparent 1px, transparent 3px);
        opacity: 0.35;
    }

    .block-container { padding-top: 2.2rem; max-width: 1320px; }

    /* Typography — terminal */
    h1, h2, h3, h4 { font-family: 'JetBrains Mono', monospace !important; color: var(--neon) !important;
        letter-spacing: 0.02em; text-shadow: 0 0 18px rgba(0,255,65,0.45); }
    h1 { font-weight: 800 !important; }
    p, span, label, li { color: var(--txt); font-family: 'JetBrains Mono', monospace; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(2,10,5,0.97), rgba(2,6,4,0.97));
        border-right: 1px solid var(--glass-brd);
    }
    [data-testid="stSidebar"] * { color: var(--txt); }

    /* Metric tiles → terminal glass */
    [data-testid="stMetric"] {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-left: 3px solid var(--neon);
        border-radius: 4px;
        padding: 18px 20px;
        box-shadow: 0 0 24px rgba(0,255,65,0.07), inset 0 0 24px rgba(0,255,65,0.03);
    }
    [data-testid="stMetriclabel"], [data-testid="stMetricLabel"] p {
        color: var(--txt-dim) !important; font-size: 0.72rem !important;
        text-transform: uppercase; letter-spacing: 0.14em; font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--neon) !important; font-family: 'JetBrains Mono', monospace !important;
        font-weight: 800 !important; text-shadow: 0 0 12px rgba(0,255,65,0.5);
    }
    [data-testid="stMetricDelta"] { color: var(--cyan) !important; }

    /* Buttons */
    .stButton > button {
        background: rgba(0,255,65,0.06);
        border: 1px solid var(--glass-brd);
        color: var(--neon);
        border-radius: 3px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        padding: 10px 14px;
        transition: all 0.15s ease;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .stButton > button:hover {
        border-color: var(--neon);
        background: var(--neon-soft);
        box-shadow: 0 0 16px rgba(0,255,65,0.35);
        color: #eafff0;
    }

    /* Chat surfaces */
    [data-testid="stChatMessage"] {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: 4px;
    }
    [data-testid="stChatInput"] textarea {
        background: rgba(2,10,5,0.92) !important;
        border: 1px solid var(--glass-brd) !important;
        color: var(--neon) !important;
        border-radius: 4px !important;
        font-family: 'JetBrains Mono', monospace !important;
        caret-color: var(--neon);
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: var(--neon) !important;
        box-shadow: 0 0 0 1px rgba(0,255,65,0.35), 0 0 18px rgba(0,255,65,0.2) !important;
    }
    [data-testid="stChatInput"] button {
        background: linear-gradient(135deg, #00c832, var(--neon)) !important;
        border: none !important;
        border-radius: 3px !important;
        color: #021206 !important;
        cursor: pointer !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stChatInput"] button:hover {
        box-shadow: 0 0 16px rgba(0,255,65,0.6) !important;
    }
    [data-testid="stChatInput"] button:disabled { opacity: 0.4 !important; cursor: not-allowed !important; }
    [data-testid="stChatInput"] {
        background: rgba(2,10,5,0.7) !important;
        border-radius: 4px !important;
        padding: 4px !important;
    }

    /* Radio nav → terminal list */
    [data-testid="stSidebar"] [role="radiogroup"] label {
        background: rgba(0,255,65,0.03);
        border: 1px solid transparent;
        border-radius: 3px;
        padding: 9px 13px !important;
        margin-bottom: 6px;
        transition: all 0.15s ease;
        font-family: 'JetBrains Mono', monospace !important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: var(--neon-soft);
        border-color: var(--glass-brd);
    }

    hr { border-color: var(--glass-brd) !important; }
    code { color: var(--cyan); background: rgba(0,229,255,0.08); border-radius: 3px; }

    [data-testid="stJson"] {
        background: var(--glass) !important;
        border: 1px solid var(--glass-brd);
        border-radius: 4px; padding: 8px;
    }

    /* ── Custom components ─────────────────────────────────────────────── */
    .hero {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: 4px;
        padding: 26px 30px;
        margin-bottom: 18px;
        box-shadow: 0 0 40px rgba(0,255,65,0.08), inset 0 0 40px rgba(0,255,65,0.03);
        position: relative; overflow: hidden;
    }
    .hero::before {
        content: ""; position: absolute; inset: 0;
        background: repeating-linear-gradient(90deg,
            transparent 0px, transparent 38px,
            rgba(0,255,65,0.03) 38px, rgba(0,255,65,0.03) 39px);
    }
    .hero-eyebrow {
        font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
        letter-spacing: 0.28em; text-transform: uppercase;
        color: var(--cyan); position: relative;
    }
    .hero-eyebrow::before { content: "> "; color: var(--neon); }
    .hero-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.9rem; font-weight: 800; margin: 6px 0 4px; position: relative;
        color: var(--neon);
        text-shadow: 0 0 22px rgba(0,255,65,0.55);
        animation: flicker 4s infinite;
    }
    @keyframes flicker {
        0%, 92%, 96%, 100% { opacity: 1; }
        94% { opacity: 0.72; }
    }
    .hero-sub { color: var(--txt-dim); font-size: 0.92rem; position: relative; }
    .hero-sub::after {
        content: "▊"; color: var(--neon); margin-left: 6px;
        animation: blink 1.1s step-end infinite;
    }
    @keyframes blink { 50% { opacity: 0; } }

    .pill {
        display: inline-flex; align-items: center; gap: 7px;
        background: rgba(0,255,65,0.08); border: 1px solid rgba(0,255,65,0.35);
        color: var(--neon); border-radius: 2px;
        padding: 5px 13px; font-size: 0.74rem; font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 0.1em; text-transform: uppercase;
    }
    .dot { width: 8px; height: 8px; background: var(--neon);
           box-shadow: 0 0 12px var(--neon); animation: pulse 1.6s infinite; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

    .agent-card {
        background: var(--glass); border: 1px solid var(--glass-brd);
        border-left: 3px solid rgba(0,255,65,0.35);
        border-radius: 3px; padding: 14px 16px; margin-bottom: 10px;
        transition: all 0.16s ease;
    }
    .agent-card:hover {
        border-color: var(--neon);
        box-shadow: 0 0 20px rgba(0,255,65,0.22);
    }
    .agent-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .agent-name { font-weight: 700; font-size: 0.94rem; color: var(--txt); font-family: 'JetBrains Mono', monospace; }
    .agent-idx {
        font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
        color: var(--cyan); margin-right: 8px;
    }
    .agent-desc { color: var(--txt-dim); font-size: 0.8rem; margin-top: 5px; line-height: 1.45; }
    .tool-badge {
        font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
        background: var(--neon-soft); border: 1px solid var(--glass-brd);
        color: var(--neon); border-radius: 2px; padding: 3px 10px; white-space: nowrap;
        text-transform: uppercase; letter-spacing: 0.08em;
    }
    .section-label {
        font-family: 'JetBrains Mono', monospace; font-size: 0.74rem;
        letter-spacing: 0.22em; text-transform: uppercase; color: var(--txt-dim);
        margin: 6px 0 10px;
    }
    .section-label::before { content: "// "; color: var(--neon); }
</style>
""",
    unsafe_allow_html=True,
)


# ── Orchestrator init ───────────────────────────────────────────────────────
if "orchestrator" not in st.session_state:
    with st.spinner("Booting the agent mesh…"):
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
        "TALK TO THE HIVE_",
        "Describe any goal in plain language — the orchestrator routes it to the "
        "right specialist agents and composes the answer.",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Agents Online", agent_count, delta="ready")
    c2.metric("Status", "OPERATIONAL")
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
        "THE FULL ROSTER_",
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
    <div><span class="agent-idx">[{i+1:02d}]</span><span class="agent-name">{html.escape(name)}</span></div>
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
        "TELEMETRY AT A GLANCE_",
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
    st.bar_chart(tool_data, use_container_width=True, color="#00ff41")


# ── HEALTH ──────────────────────────────────────────────────────────────────
def render_health():
    status = orch.status()
    _hero(
        "System Health",
        "DIAGNOSTICS_",
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
  <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; letter-spacing:0.28em;
              color:#00e5ff; text-transform:uppercase;">Cyber-Matrix Console</div>
  <div style="font-family:'JetBrains Mono',monospace; font-size:1.4rem; font-weight:800; margin-top:4px;
              color:#00ff41; text-shadow:0 0 18px rgba(0,255,65,0.55);">▓ AgentSystem</div>
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
<div style="margin-top:10px; padding:14px 16px; border:1px solid rgba(0,255,65,0.16);
            border-radius:3px; background:rgba(4,24,12,0.66);">
  <div style="display:flex; align-items:center; gap:8px;">
    <span class="dot"></span>
    <span style="font-family:'JetBrains Mono',monospace; font-size:0.74rem; color:#4d9a68;
                 letter-spacing:0.14em;">SYSTEM ONLINE</span>
  </div>
  <div style="margin-top:10px; font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#00ff41;">
    {agent_count} agents · operational
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.sidebar.write("")
if st.sidebar.button("↻ NEW SESSION", use_container_width=True):
    new_id = orch.reset_session()
    st.session_state.messages = []
    st.sidebar.success(f"Session: {new_id[:12]}…")
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("AgentSystem · Cyber-Matrix · Boil the Ocean")
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
