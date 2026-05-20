import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import asyncio
from agents.factory import build_orchestrator

st.set_page_config(page_title="AgentSystem Dashboard", page_icon="🤖", layout="wide")

# BUILD VERSION: 1778719094 - ENSURES REFRESH
if "build_ver" not in st.session_state or st.session_state.build_ver != "1778719094":
    st.session_state.orchestrator = build_orchestrator()
    st.session_state.build_ver = "1778719094"
    st.session_state.messages = []

def render_command_center():
    st.title("🎮 COMMAND CENTER")
    names = st.session_state.orchestrator.agent_names
    st.caption(f"System: {len(names)} Agents Online | Cluster: Azure eastus2")
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if pr := st.chat_input("Issue command (e.g., 'relink_account' or 'finish_link' or 'List mail')"):
        st.session_state.messages.append({"role": "user", "content": pr})
        st.rerun()

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_prompt = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        with st.spinner("Executing Azure-Native Hive..."):
            try:
                resp = asyncio.run(st.session_state.orchestrator.handle_user_input(last_prompt))
                st.session_state.messages.append({"role": "assistant", "content": resp})
                st.rerun()
            except Exception as e:
                st.error(f"Execution Error: {e}")

st.sidebar.title("🤖 AgentSystem")
choice = st.sidebar.radio("Navigation", ["COMMAND CENTER", "Overview", "Metrics", "Health"])

if choice == "COMMAND CENTER":
    render_command_center()
else:
    st.title(f"📊 {choice}")
    st.info("Switch to COMMAND CENTER to interact.")
