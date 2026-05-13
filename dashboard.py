import sys; import os; sys.path.insert(0, os.getcwd())
import streamlit as st
import asyncio
from agents.factory import build_orchestrator

st.set_page_config(page_title="AgentSystem Dashboard", page_icon="🤖", layout="wide")

def render_command_center():
    st.title("🎮 COMMAND CENTER")
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = build_orchestrator()
    
    names = st.session_state.orchestrator.agent_names
    st.caption(f"Status: {len(names)} Agents Active in Azure Backend.")

    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if pr := st.chat_input("Command the hive..."):
        st.session_state.messages.append({"role": "user", "content": pr})
        with st.chat_message("user"): st.markdown(pr)
        with st.chat_message("assistant"):
            with st.spinner("Executing via Azure Agents..."):
                try:
                    res = asyncio.run(st.session_state.orchestrator.handle_user_input(pr))
                    st.markdown(res)
                    st.session_state.messages.append({"role": "assistant", "content": res})
                except Exception as e: st.error(f"Execution Error: {e}")

st.sidebar.title("🤖 AgentSystem")
# FORCE THE OPTION LIST TO BE CLEAN
choice = st.sidebar.radio("Navigation", ["COMMAND CENTER", "Overview", "Metrics", "Health"])

if choice == "COMMAND CENTER":
    render_command_center()
else:
    st.title(f"📊 {choice}")
    st.info("System monitoring operational. Switch to COMMAND CENTER to interact.")

